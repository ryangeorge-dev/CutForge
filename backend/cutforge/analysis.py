import re
from fractions import Fraction
from pathlib import Path

from .engine import inward, normalize
from .media import run
from .models import Metadata, Settings


def parse_silences(log: str, duration: Fraction) -> list[tuple[Fraction, Fraction]]:
    result = []
    start = None
    for match in re.finditer(r"silence_(start|end):\s*(-?[\d.]+(?:e[+-]?\d+)?)", log):
        kind, value = match.groups()
        time = max(Fraction(0), min(duration, Fraction(value)))
        if kind == "start":
            start = time
        elif start is not None:
            if time > start:
                result.append((start, time))
            start = None
    if start is not None and start < duration:
        result.append((start, duration))
    return result


def analyze(path: Path, metadata: Metadata, settings: Settings) -> list[tuple[int, int]]:
    if not metadata.has_audio:
        return []
    rate = Fraction(metadata.rate)
    duration = Fraction(metadata.duration_ticks, 1) / rate
    # Combined-channel detection requires silence across every channel. No downmix
    # that could cancel opposite-phase speech, and no video decode during analysis.
    result = run(["ffmpeg", "-hide_banner", "-nostdin", "-xerror", "-i", str(path), "-map", "0:a:0",
                  "-vn", "-af", f"asetpts=PTS-STARTPTS,silencedetect=noise={settings.threshold_db}dB:d={settings.min_silence}",
                  "-f", "null", "-"])
    padding = Fraction(str(settings.padding))
    cuts = []
    for start, end in parse_silences(result.stderr, duration):
        # Keep padding only beside speech, not beside the source's outer edges.
        left = start + padding if start > 0 else start
        right = end - padding if end < duration - Fraction(1, metadata.sample_rate or 48000) else duration
        if right > left:
            cuts.append(inward(left, right, rate))
    return normalize(cuts, metadata.duration_ticks)
