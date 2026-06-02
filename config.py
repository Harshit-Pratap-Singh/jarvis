"""Settings that may differ between Mac and Pi."""

import platform
import os

IS_MAC = platform.system() == "Darwin"
IS_PI = platform.system() == "Linux"

# Audio
SAMPLE_RATE = 16000
INPUT_DEVICE = None  # None = system default; we'll set explicitly on Pi later
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
VAD_AGGRESSIVENESS = 3  # 0-3; higher = more aggressive filtering (fewer false-positive speech detections)
VAD_FRAME_MS = 30  # VAD wants 10, 20, or 30 ms frames
SILENCE_TIMEOUT_MS = 800  # stop recording after this much continuous silence
MAX_RECORDING_SECONDS = (
    10  # safety cap — even if VAD says still talking, stop after this
)
MIN_RECORDING_SECONDS = 0.5  # too-short recordings get discarded (likely false trigger)

# Piper
PIPER_MODEL_DIR = "models/piper"
PIPER_VOICE = "en_US-lessac-medium"
PIPER_MODEL_PATH = f"{PIPER_MODEL_DIR}/{PIPER_VOICE}.onnx"
PIPER_CONFIG_PATH = f"{PIPER_MODEL_DIR}/{PIPER_VOICE}.onnx.json"


_checks = [
    (WHISPER_BINARY, "Whisper binary (build whisper.cpp first?)"),
    (WHISPER_MODEL_PATH, "Whisper model (run download-ggml-model.sh?)"),
    (PIPER_MODEL_PATH, "Piper voice model (download .onnx from HuggingFace?)"),
    (PIPER_CONFIG_PATH, "Piper voice config (download .onnx.json from HuggingFace?)"),
]
for path, hint in _checks:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing: {path}  --  {hint}")
