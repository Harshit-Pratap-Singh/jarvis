import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.utils import download_models

download_models()

SAMPLE_RATE = 16000
CHUNK_SAMPLES=1280

WAKE_WORD = "alexa"
THERSHOLD=0.5

print("Loading wake word model...")

oww_Model=Model(wakeword_models=[WAKE_WORD], inference_framework="onnx")

print(f"Listening for '{WAKE_WORD}'... (Ctrl+C to stop)")

import time

last_detection=0;
COOLDOWN_SECONDS = 2 

def audio_callback(indata, frames, time_info,status):
    """Called by sounddevice every time a new audio chunk arrives."""
    global last_detection

    if status:
        print(f"[audio status] {status}")
    
    # indata shape: (CHUNK_SAMPLES, 1). We need shape (CHUNK_SAMPLES,) as int16.

    audio_chunk = (indata[:, 0] * 32767).astype(np.int16) # we are flattening the array indata and converting it into int16

    prediction=oww_Model.predict(audio_chunk)
    score=prediction[WAKE_WORD]

    now=time.time()
    print(f"(score={score:.2f})")
    if score>THERSHOLD and (now-last_detection)>COOLDOWN_SECONDS:
        print(f"🎯 WAKE WORD DETECTED! (score={score:.2f})")
        last_detection = now

# Open the mic stream and let the callback do the work
with sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype=np.float32,
    blocksize=CHUNK_SAMPLES,
    callback=audio_callback,
):
    try:
        while True:
            sd.sleep(1000)   # main thread sleeps; audio_callback runs in background
    except KeyboardInterrupt:
        print("\nStopping.")


