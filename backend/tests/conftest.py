import math
import struct
import subprocess
import wave
from pathlib import Path

import pytest


def write_wav(path: Path, rate=48000, channels=1, kind="mixed"):
    # Five seconds: silence [0,1], [2,3], [4,5], tones in between.
    with wave.open(str(path), "wb") as wav:
        wav.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        samples = bytearray()
        for i in range(rate * 5):
            active = kind == "tone" or (kind == "mixed" and int(i / rate) in (1, 3))
            value = int(12000 * math.sin(2 * math.pi * 440 * i / rate)) if active else 0
            samples.extend(struct.pack("<" + "h" * channels, *([value] * channels)))
        wav.writeframes(samples)


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "Narration & spaces.wav"
    write_wav(path)
    return path


@pytest.fixture
def encode():
    def run(*args):
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *map(str, args)], check=True, capture_output=True)
    return run
