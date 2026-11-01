"""Pure edit algebra. All boundaries are integer source ticks, never floats.

A tick is a video frame or an audio sample. Analysis adapters convert seconds
once; persistence and export retain those exact boundaries.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor
from typing import Iterable

Interval = tuple[int, int]


def normalize(intervals: Iterable[Interval], duration: int) -> list[Interval]:
    if duration < 0:
        raise ValueError("Duration cannot be negative")
    result: list[Interval] = []
    for start, end in sorted((max(0, a), min(duration, b)) for a, b in intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def complement(cuts: Iterable[Interval], duration: int) -> list[Interval]:
    result = []
    cursor = 0
    for start, end in normalize(cuts, duration):
        if start > cursor:
            result.append((cursor, start))
        cursor = end
    if cursor < duration:
        result.append((cursor, duration))
    return result


def inward(start: Fraction, end: Fraction, rate: Fraction) -> Interval:
    """Never remove speech outside a detector's requested removal interval."""
    return ceil(start * rate), floor(end * rate)


@dataclass(frozen=True)
class Clip:
    source_start: int
    duration: int
    offset: int


def timeline(cuts: Iterable[Interval], duration: int) -> list[Clip]:
    result = []
    offset = 0
    for start, end in complement(cuts, duration):
        result.append(Clip(start, end - start, offset))
        offset += end - start
    return result


def xml_time(ticks: int, rate: Fraction) -> str:
    seconds = Fraction(ticks, 1) / rate
    return f"{seconds.numerator}/{seconds.denominator}s"
