# Voice Assistant Project — Handoff Context

This document hands off an in-progress learning project from a chat-based Claude session to Claude Code. The user is building a fully-offline voice assistant as a learning project. Read this completely before taking any action.

---

## About the user

- **Background:** Pretty new to Linux command line, has used Git "a couple of times." Wants to deeply *understand* every step, not just copy-paste.
- **Accent:** Indian English — relevant because off-the-shelf wake-word models trained on American/British accents didn't work for him. We learned this together early and used it to teach the broader lesson about dataset bias in AI models.
- **Hardware available right now:** MacBook Air M1 (used for development). Raspberry Pi 4 (deployment target, but no USB mic yet — user is ordering one). 3.5mm headset exists but Pi 4 jack is output-only, so unusable as mic.
- **Goal:** Build the full pipeline on Mac, deploy to Pi when hardware arrives. **No Docker** — we discussed and decided against it (audio passthrough mess on macOS, architecture issues, learning value of going native).

## Pedagogical style — IMPORTANT

The user explicitly asked to **understand every step** so he can extend things on his own later. This is a learning project, not a "just ship it" project. When you write code or run commands:

- Explain *why*, not just *what*. Walk through code conceptually before/after writing it.
- When something fails, treat it as a teaching moment about the broader pattern, not just a bug to swat.
- Don't over-abstract. He's learning; clarity beats cleverness.
- When introducing a new concept (subprocess, callbacks, VAD, threads vs processes, etc.), give the one-paragraph mental model before diving in.
- Match his pace — he asks great clarifying questions like "explain how things look at the process level" and "explain this function." Welcome those.
- He likes the pattern of: high-level picture → step-by-step build → "what success looks like" → "what might go wrong" → "your move."

## Project layout

```
~/voice-assistant/
├── venv/                       # Python 3.11 virtualenv (gitignored)
├── models/                     # for downloaded model files (gitignored, mostly unused so far)
├── data/                       # any recordings (gitignored)
├── scripts/
│   ├── test_audio.py           # Stage 0: mic record + playback sanity check ✅ working
│   ├── test_wakeword.py        # Stage 1: wake word detection ✅ working
│   └── test_stt.py             # Stage 2: wake word + VAD + Whisper ✅ working
├── whisper.cpp/                # cloned & built. Binary at: whisper.cpp/build/bin/whisper-cli
│                                 # Model at: whisper.cpp/models/ggml-tiny.en.bin
├── assistant.py                # main entrypoint — empty / placeholder
├── config.py                   # central config, imported by scripts
├── requirements.txt            # pip freeze output
├── README.md                   # not really written yet
└── .gitignore                  # venv/, models/, data/, __pycache__/, *.pyc, .env, .DS_Store
```

Git is initialized. Commits made at the end of each stage.

## What works right now (end-to-end)

Running `python scripts/test_stt.py` does:
1. Listens continuously for the wake word **"alexa"** (using openWakeWord)
2. On detection, opens a fresh InputStream and records using webrtcvad until ~800ms of sustained silence
3. Writes the audio to a temp WAV, shells out to `whisper-cli` with `tiny.en` model
4. Prints the transcription
5. Returns to listening

Latency end-to-end on the M1: roughly 1.5-3 seconds from end-of-speech to transcription printed.

## Key decisions and why

- **Wake word: "alexa", not "hey_jarvis".** The pretrained openWakeWord "hey_jarvis" model didn't fire reliably on the user's Indian-English accent. "alexa" works. The user wants to train a custom "hey jarvis" model later as a separate project — do NOT pursue that in this thread; he's deferred it to a dedicated session.
- **webrtcvad-wheels, not webrtcvad.** The original webrtcvad imports `pkg_resources` which was removed in setuptools 81+. We hit this error and switched to `webrtcvad-wheels` — drop-in replacement, modern. Same `import webrtcvad`.
- **whisper.cpp built via cmake, not make.** The repo recently moved to cmake. Binary is at `build/bin/whisper-cli`, not `main`. We discovered this together. Reflected in config.py.
- **Subprocess invocation of whisper-cli, not Python bindings.** Chosen for *learning clarity* — you can run the same command in the terminal and see what happens. We know this re-loads the model every call (~500ms-1s overhead) and we'll improve it later. Don't prematurely optimize to Python bindings unless quality/speed actually becomes a blocker.
- **Two separate InputStreams (wake-word stream and VAD stream).** Different chunk sizes required by each library. Production systems would use one continuous stream and demux in software; we chose two streams for clarity while learning. Worth knowing this exists but not worth rewriting now.
- **Models kept Pi-sized even on Mac.** Using `tiny.en` Whisper and (next) `qwen2.5:1.5b` Ollama, even though the M1 could run larger. Reason: we want Mac-dev performance to match Pi-dev performance so we don't ship surprises to the Pi.

## What's in config.py

```python
"""Settings that may differ between Mac and Pi."""
import platform
import os

IS_MAC = platform.system() == "Darwin"
IS_PI = platform.system() == "Linux"

# Audio
SAMPLE_RATE = 16000
INPUT_DEVICE = None
OUTPUT_DEVICE = None

# Models — kept small so Mac dev matches Pi performance
WHISPER_MODEL = "tiny.en"
OLLAMA_MODEL = "qwen2.5:1.5b"
WAKE_WORD = "alexa"

# Paths
MODELS_DIR = "models"

# Whisper
WHISPER_CPP_DIR = "whisper.cpp"
WHISPER_BINARY = f"{WHISPER_CPP_DIR}/build/bin/whisper-cli"
WHISPER_MODEL_PATH = f"{WHISPER_CPP_DIR}/models/ggml-tiny.en.bin"

# VAD
VAD_AGGRESSIVENESS = 2
VAD_FRAME_MS = 30
SILENCE_TIMEOUT_MS = 800
MAX_RECORDING_SECONDS = 10
MIN_RECORDING_SECONDS = 0.5

# Sanity checks
_checks = [
    (WHISPER_BINARY, "Whisper binary (build whisper.cpp first?)"),
    (WHISPER_MODEL_PATH, "Whisper model (run download-ggml-model.sh?)"),
]
for path, hint in _checks:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing: {path}  --  {hint}")
```

## The planned stages (where we are, where we're going)

- ✅ **Stage 0:** Audio I/O sanity check
- ✅ **Stage 1:** Wake word detection (openWakeWord, "alexa")
- ✅ **Stage 2:** VAD recording + Whisper transcription
- ▶️ **Stage 3 (NEXT):** LLM brain — Ollama + qwen2.5:1.5b. Take transcribed text, send to local LLM with a voice-optimized system prompt ("answer in 1-2 sentences, no markdown"), print the response.
- **Stage 4:** TTS — Piper. Take LLM response, speak it through the speaker.
- **Stage 5:** Polish — consolidate scripts into `assistant.py`, make it a proper state machine, error recovery, maybe a status indicator (LED on Pi later).
- **Stage 6+:** Optional/later — tool calling (control lights, query weather), interruption handling, follow-up turns without re-saying wake word, deploy to Pi, etc.

## What to do first in this session

The natural next step is **Stage 3: plug in the LLM brain.** Concretely:

1. **Confirm Ollama isn't already installed** (`which ollama`). If not, install it via the official installer for macOS.
2. **Pull `qwen2.5:1.5b`** (smaller for Pi-parity; ~1GB download).
3. **Test it works** with a one-shot prompt from the terminal so the user sees the model alive.
4. **Add LLM functions to a new script** (e.g., `scripts/test_llm.py`) that takes the transcription and sends it to Ollama via its HTTP API at `localhost:11434/api/generate` or `/api/chat`. Use `requests` (already installed? if not, install it).
5. **Critical:** explain the *system prompt* and why it's the single most important lever for voice-assistant feel. A good starting one:
   > You are a helpful voice assistant. Answer in 1-2 short sentences. Never use bullet points, asterisks, headers, or markdown formatting — your response will be read aloud. Speak naturally and conversationally.
6. **Wire it into the existing pipeline:** after Whisper transcribes, send the text to the LLM, print the response. (Still text-only at this stage — TTS comes in Stage 4.)
7. **Have the user test it with real questions** and tune the system prompt based on what feels right.

Don't rush past explanation. The user will want to understand:
- Why Ollama vs running llama.cpp directly (Ollama is a friendlier wrapper)
- What the HTTP API looks like and why local models expose one
- What a system prompt is and how it shapes behavior
- The streaming vs non-streaming response tradeoff
- Why we picked qwen2.5:1.5b specifically (Pi-friendly size, decent quality)

## Honest expectations for Stage 3

- On the M1, `qwen2.5:1.5b` will respond in ~1-3 seconds. Fine.
- On the Pi 4 eventually, same model will take ~10-30 seconds. The user has been warned about this and chose "fully offline" with eyes open. Don't re-litigate.
- Quality of a 1.5B model is limited. It's good at short factual answers and conversational replies; weak at reasoning, math, current events (no internet). System prompt does a lot of work here. Be ready to discuss falling back to a cloud API later if quality bothers him — that's a Stage 6 conversation, not now.

## Honest expectations for the future Pi deployment

- The user is on `git`, so the deploy is mostly: `git clone` on the Pi, `pip install -r requirements.txt`, `ollama pull qwen2.5:1.5b`, plus a `setup-pi.sh` for system packages (portaudio, ffmpeg, build deps for whisper.cpp).
- We'll need to rebuild whisper.cpp on the Pi (arm64 Linux binary, not Mac one).
- Audio device names will differ — `config.py` is set up to hold device overrides. Once mic is plugged in we'll do `python -c "import sounddevice; print(sounddevice.query_devices())"` on the Pi and update INPUT_DEVICE/OUTPUT_DEVICE.
- Performance discovery on the Pi will probably reveal that some choices need tuning (thread count, model size, VAD aggressiveness).

## Style notes for code in this project

- Type hints used loosely (`audio_int16: np.ndarray -> str`) — helpful for readers, not enforced.
- Subprocess calls always have `timeout=`. Always.
- Temp files cleaned up in `finally:`.
- "Fail loudly and early" — `config.py` checks for missing binaries at import time so we don't fail mid-recording.
- Cross-platform-friendly libraries chosen wherever possible (`sounddevice` not `pyalsaaudio`, etc.).

## Things NOT to do in this session

- Don't introduce Docker. We discussed and rejected.
- Don't pursue the custom wake-word training. Deferred to a separate session.
- Don't swap to a cloud LLM API silently. He explicitly chose fully offline. If you think a cloud LLM would help, raise it and let him decide.
- Don't refactor the working stage scripts into "production" architecture yet. That's Stage 5. Keep adding new scripts side-by-side.
- Don't skip explanations. He's learning.

## How to start the conversation

A short greeting that:
1. Confirms you've read this context and know where the project stands (Stages 0-2 done, working end-to-end).
2. Briefly previews Stage 3 (what we're building, what'll feel different at the end).
3. Asks whether he wants to dive in or has any questions about what's been built so far.

Don't repeat the whole roadmap back; he already knows it. Just acknowledge you have context and propose the next concrete step.
