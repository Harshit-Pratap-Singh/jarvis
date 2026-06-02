import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

import sounddevice as sd
import numpy as np
from piper.voice import PiperVoice

TEST_TEXT = "Hello. I am your voice assistant. It's nice to finally speak."


def load_voice():
    return PiperVoice.load(config.PIPER_MODEL_PATH)


def speak(voice: PiperVoice, text: str):
    audio_bytes = b""

    for chunk in voice.synthesize(text):
        audio_bytes += chunk.audio_int16_bytes

    audio = np.frombuffer(audio_bytes, dtype=np.int16)

    sd.play(audio, samplerate=voice.config.sample_rate)
    sd.wait()
    sd.play(audio, samplerate=voice.config.sample_rate)
    sd.wait()
    sd.play(audio, samplerate=voice.config.sample_rate)
    sd.wait()


if __name__ == "__main__":
    print("Loading voice…")
    voice = load_voice()
    print("Speaking…")
    speak(voice, TEST_TEXT)
    print("Done.")
