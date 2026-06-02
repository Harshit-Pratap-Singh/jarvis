"""Stage 2: Wake word -> VAD-based recording -> Whisper transcription."""

import os
import sys
import time
import subprocess
import tempfile
import collections
import requests
import json

import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.io import wavfile
from openwakeword.model import Model
from openwakeword.utils import download_models

import queue
import threading

from piper.voice import PiperVoice

import re


# Add parent dir to path so we can import config.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# --- Setup ---
download_models()
print("Loading wake word model...")
oww = Model(wakeword_models=[config.WAKE_WORD], inference_framework="onnx")

vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)

SAMPLE_RATE = config.SAMPLE_RATE
WAKE_CHUNK = 1280  # openWakeWord chunk size (80ms at 16kHz)
VAD_CHUNK = int(SAMPLE_RATE * config.VAD_FRAME_MS / 1000)  # samples per VAD frame
WAKE_THRESHOLD = 0.8
COOLDOWN_S = 1.5
OLLAMA_URL = "http://localhost:11434/api/generate"
# SYSTEM_PROMPT = """CRITICAL: Maximum 2 sentences. Stop after 2 sentences, no matter what.
# You are a helpful voice assistant. Answer in 1-2 short sentences.Never use bullet points, asterisks, headers, or markdown formatting — your response will be read aloud. Speak naturally and conversationally."""

SYSTEM_PROMPT = """You are a helpful voice assistant. Your response will be read aloud, so:
- Answer in 1-2 short sentences.
- No bullets, asterisks, headers, or markdown.
- Speak naturally and conversationally.

Example of good output:

User: How do I make tea?
Assistant: Boil some water, steep tea leaves or a tea bag for a few minutes, then add milk or sugar if you like.
"""
print("Loading Piper voice…")
VOICE = PiperVoice.load(config.PIPER_MODEL_PATH)

SENTENCE_END = re.compile(r"(?<=[.?!])\s+")


def transcribe_with_whisper(audio_int16: np.ndarray) -> str:
    """Save audio to temp WAV, run whisper.cpp on it, return text."""
    # whisper.cpp wants a WAV file on disk. Use a temp file.
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    try:
        wavfile.write(tmp_path, SAMPLE_RATE, audio_int16)
        result = subprocess.run(
            [
                config.WHISPER_BINARY,
                "-m",
                config.WHISPER_MODEL_PATH,
                "-f",
                tmp_path,
                "--no-timestamps",
                "--language",
                "en",
                "--threads",
                "4",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # whisper.cpp prints transcription to stdout, status info to stderr
        return result.stdout.strip()
    finally:
        os.unlink(tmp_path)


def ask(prompt: str, sentence_queue: queue.Queue) -> str:
    output_string = ""
    buffer = ""
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True,
            "system": SYSTEM_PROMPT,
        },
        timeout=60,
        stream=True,
    )

    response.raise_for_status()

    for item in response.iter_lines():
        if not item:
            continue

        chunk = json.loads(item)
        print(chunk["response"], end="", flush=True)
        output_string += chunk["response"]

        buffer += chunk["response"]
        parts = SENTENCE_END.split(buffer, maxsplit=1)

        if len(parts) == 2:
            sentence, buffer = parts
            sentence_queue.put(sentence)

        if chunk["done"]:
            print()
            break

    if buffer.strip():
        sentence_queue.put(buffer)
    sentence_queue.put(None)

    return output_string


def record_until_silence() -> np.ndarray | None:
    """After wake word, record audio using VAD to detect end-of-speech.
    Returns int16 numpy array of recorded audio, or None if it was too short."""
    print("   🎙️  Listening for your command...")

    silence_ms_needed = config.SILENCE_TIMEOUT_MS
    silence_frames_needed = silence_ms_needed // config.VAD_FRAME_MS
    max_frames = int(config.MAX_RECORDING_SECONDS * 1000 / config.VAD_FRAME_MS)

    recorded_frames = []
    silent_frames_in_a_row = 0
    has_heard_speech = False
    frame_count = 0

    speech_frames_in_a_row = 0
    SPEECH_FRAMES_NEEDED = 3

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
        blocksize=VAD_CHUNK,
    ) as stream:
        # Throw away stale OS-buffered audio before VAD starts
        for _ in range(15):
            stream.read(VAD_CHUNK)

        while frame_count < max_frames:
            frame, _ = stream.read(VAD_CHUNK)
            frame_bytes = frame.tobytes()
            is_speech = vad.is_speech(frame_bytes, SAMPLE_RATE)

            recorded_frames.append(frame.flatten())
            frame_count += 1

            if is_speech:
                speech_frames_in_a_row += 1
                if speech_frames_in_a_row >= SPEECH_FRAMES_NEEDED:
                    has_heard_speech = True
                silent_frames_in_a_row = 0
            else:
                silent_frames_in_a_row += 1
                speech_frames_in_a_row = 0

            # End-of-speech: heard some speech, then sustained silence
            if has_heard_speech and silent_frames_in_a_row >= silence_frames_needed:
                break

    if not has_heard_speech:
        print("   (no speech detected)")
        return None

    audio = np.concatenate(recorded_frames)
    duration_s = len(audio) / SAMPLE_RATE
    if duration_s < config.MIN_RECORDING_SECONDS:
        print(f"   (recording too short: {duration_s:.2f}s)")
        return None

    print(f"   Recorded {duration_s:.2f}s")
    return audio


# def player_worker(audio_queue: queue.Queue):
#     while True:
#         audio = audio_queue.get()
#         if audio is None:
#             break
#         sd.play(audio, VOICE.config.sample_rate)
#         sd.wait()


def player_worker(audio_queue: queue.Queue):
    with sd.OutputStream(
        samplerate=VOICE.config.sample_rate, channels=1, dtype=np.int16, latency="high"
    ) as stream:
        while True:
            audio = audio_queue.get()
            if audio is None:
                tail = np.zeros(int(VOICE.config.sample_rate * 0.3), dtype=np.int16)
                stream.write(tail)
                break
            stream.write(audio)


def synthesizer_worker(sentence_queue: queue.Queue, audio_queue: queue.Queue):
    while True:
        item = sentence_queue.get()
        if item is None:
            audio_queue.put(None)
            break

        audio_bytes = b""

        for chunk in VOICE.synthesize(item):
            audio_bytes += chunk.audio_int16_bytes

        audio = np.frombuffer(audio_bytes, dtype=np.int16)
        silence = np.zeros(int(VOICE.config.sample_rate * 0.2), dtype=np.int16)
        audio = np.concatenate([audio, silence])
        audio_queue.put(audio)


def speak(prompt: str) -> str:
    sentence_queue = queue.Queue()
    audio_queue = queue.Queue()

    synthesizer = threading.Thread(
        target=synthesizer_worker, args=(sentence_queue, audio_queue)
    )
    player = threading.Thread(target=player_worker, args=(audio_queue,))

    synthesizer.start()
    player.start()

    reply = ask(prompt, sentence_queue)

    synthesizer.join()
    player.join()

    return reply


# --- Main loop ---
print(f"Listening for '{config.WAKE_WORD}'... (Ctrl+C to stop)")
last_detection = 0

# Use a separate input stream for wake-word listening
with sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype=np.float32,
    blocksize=WAKE_CHUNK,
) as wake_stream:
    print("Warming up wake word model...")
    for _ in range(10):
        chunk, _ = wake_stream.read(WAKE_CHUNK)
        audio_int16 = (chunk[:, 0] * 32767).astype(np.int16)
        oww.predict(audio_int16)
    print(f"Listening for '{config.WAKE_WORD}'...")
    try:
        while True:
            chunk, _ = wake_stream.read(WAKE_CHUNK)
            audio_int16 = (chunk[:, 0] * 32767).astype(np.int16)
            score = oww.predict(audio_int16)[config.WAKE_WORD]
            if score > 0.3:
                print(f"   [score={score:.2f}]")

            now = time.time()
            if score > WAKE_THRESHOLD and (now - last_detection) > COOLDOWN_S:
                last_detection = now
                print(f"\n🎯 Wake word! (score={score:.2f})")

                # Stop the wake stream so we can open a fresh one for VAD recording
                wake_stream.stop()

                audio = record_until_silence()
                if audio is not None:
                    print("   🧠 Transcribing...")
                    t0 = time.time()
                    text = transcribe_with_whisper(audio)
                    elapsed = time.time() - t0
                    print(f'   📝 "{text}"  ({elapsed:.1f}s)\n')
                    if text.strip():
                        print("   🤖 Thinking...")
                        reply = speak(text)
                        print()

                # Reset wake word model state and resume listening
                oww.reset()
                wake_stream.start()
                print(f"Listening for '{config.WAKE_WORD}'...")

    except KeyboardInterrupt:
        print("\nStopping.")
