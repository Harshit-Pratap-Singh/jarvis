"""Settings that may differ between Mac and Pi."""
import platform

IS_MAC = platform.system() == "Darwin"
IS_PI = platform.system() == "Linux"

# Audio
SAMPLE_RATE = 16000
INPUT_DEVICE = None   # None = system default; we'll set explicitly on Pi later
OUTPUT_DEVICE = None

# Models — kept small so Mac dev matches Pi performance
WHISPER_MODEL = "tiny.en"
OLLAMA_MODEL = "qwen2.5:1.5b"
WAKE_WORD = "hey_jarvis"

# Paths
MODELS_DIR = "models"