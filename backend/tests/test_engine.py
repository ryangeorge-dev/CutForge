from fractions import Fraction
import pytest
from cutforge.engine import normalize, complement, inward, timeline, xml_time


@pytest.mark.parametrize("cuts, expected", [
    ([(4, 8), (1, 5), (8, 9)], [(1, 9)]),
    ([(-3, 2), (9, 20)], [(0, 2), (9, 10)]),
    ([(2, 2), (5, 4), (15, 20)], []),
    ([], []), ([(0, 10)], [(0, 10)]),
])
def test_normalize(cuts, expected):
    assert normalize(cuts, 10) == expected


def test_complement_boundaries():
    assert complement([(0, 2), (8, 10)], 10) == [(2, 8)]
    assert complement([], 10) == [(0, 10)]
    assert complement([(0, 10)], 10) == []
    assert complement([], 0) == []


def test_rational_frames_and_samples():
    rate = Fraction(30000, 1001)
    assert inward(Fraction(1), Fraction(2), rate) == (30, 59)
    assert xml_time(30, rate) == "1001/1000s"
    assert xml_time(1, Fraction(44100)) == "1/44100s"
    clips = timeline([(30, 60)], 90)
    assert [(c.source_start, c.duration, c.offset) for c in clips] == [(0, 30, 0), (60, 30, 30)]


def test_partition_invariant():
    for seed in range(100):
        import random
        r = random.Random(seed)
        cuts = [(r.randrange(-10, 110), r.randrange(-10, 110)) for _ in range(30)]
        removed = normalize(cuts, 100)
        kept = complement(cuts, 100)
        assert sum(b-a for a,b in removed + kept) == 100
        assert all(b > a for a,b in removed + kept)
