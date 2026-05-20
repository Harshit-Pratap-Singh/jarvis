"""Record 3 seconds from mic, play it back. Sanity check for audio I/O."""
import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000  # samples per second; 16kHz is standard for speech models
DURATION = 3         # seconds

print("Available audio devices:")
print(sd.query_devices())
print()

print(f"Recording {DURATION} seconds... speak now!")
audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,        # mono — speech models want one channel
    dtype=np.float32,  # 32-bit floats; standard for ML
)
sd.wait()  # block until recording is done
print("Done recording.")

print("Playing back...")
sd.play(audio, samplerate=SAMPLE_RATE)
sd.wait()
print("Done. If you heard yourself, audio works!")
