from fractions import Fraction
from uuid import uuid4
from lxml import etree as ET
import pytest

from cutforge.analysis import analyze, parse_silences
from cutforge.media import probe, MediaError
from cutforge.models import Project, Settings, ReviewRequest
from cutforge.review import merge_analysis, review
from cutforge.export import export_fcpxml
from conftest import write_wav


@pytest.mark.parametrize("rate,channels", [(44100, 1), (48000, 2), (48000, 6)])
def test_audio_metadata_and_silences(tmp_path, rate, channels, encode):
    path = tmp_path / "sample.wav"
    write_wav(path, rate, channels)
    if channels == 6:
        labeled = tmp_path / "5.1.wav"
        encode("-i", path, "-channel_layout", "5.1", labeled)
        path = labeled
    metadata = probe(path)
    assert metadata.duration_ticks == rate * 5
    assert metadata.channels == channels
    cuts = analyze(path, metadata, Settings())
    assert len(cuts) == 3
    assert cuts[0][0] == 0 and cuts[-1][1] == rate * 5
    assert abs(cuts[1][0] / rate - 2.15) < .001
    assert abs(cuts[1][1] / rate - 2.85) < .001


@pytest.mark.parametrize("kind,expected", [("tone", []), ("silence", [(0, 240000)])])
def test_no_silence_and_all_silence(tmp_path, kind, expected):
    path = tmp_path / "sample.wav"
    write_wav(path, kind=kind)
    assert analyze(path, probe(path), Settings()) == expected


def test_mp3(wav, tmp_path, encode):
    path = tmp_path / "sample.mp3"
    encode("-i", wav, "-c:a", "libmp3lame", path)
    metadata = probe(path)
    assert metadata.audio_codec == "mp3"
    assert metadata.duration_ticks == 240000
    assert len(analyze(path, metadata, Settings())) == 3


def test_trailing_parser():
    assert parse_silences("silence_start: 3.0", Fraction(5)) == [(Fraction(3), Fraction(5))]


def test_export_approved_only_and_unicode_path(wav):
    p = Project(id=uuid4().hex, name="Voice & test", media_name=wav.name, media_size=wav.stat().st_size, metadata=probe(wav))
    merge_analysis(p, [(0, 48000), (96000, 144000), (192000, 240000)])
    review(p, ReviewRequest(revision=0, action="accept", cut_id=p.cuts[1].id))
    review(p, ReviewRequest(revision=0, action="reject", cut_id=p.cuts[0].id))
    xml = export_fcpxml(p, wav)
    root = ET.fromstring(xml)
    assert root.find("resources/asset").get("src") == wav.resolve().as_uri()
    assert b"%20" in xml and b"%26" in xml
    assert root.find("resources/asset").get("hasVideo") is None
    clips = root.findall(".//asset-clip")
    assert [(c.get("start"), c.get("duration")) for c in clips] == [("0/1s", "2/1s"), ("3/1s", "2/1s")]
    review(p, ReviewRequest(revision=0, action="reject_all"))
    assert len(ET.fromstring(export_fcpxml(p, wav)).findall(".//asset-clip")) == 1


def test_empty_export_has_clear_error(wav):
    p = Project(id=uuid4().hex, name="test", media_name=wav.name, media_size=wav.stat().st_size, metadata=probe(wav))
    merge_analysis(p, [(0, p.metadata.duration_ticks)])
    review(p, ReviewRequest(revision=0, action="accept_all"))
    with pytest.raises(ValueError, match="Every source"):
        export_fcpxml(p, wav)


def test_malformed_and_unsupported(tmp_path):
    for name in ["broken.wav", "unsupported.txt"]:
        path = tmp_path / name
        path.write_bytes(b"not media")
        with pytest.raises(MediaError):
            probe(path)


def test_speech_on_one_channel_is_not_removed(tmp_path, encode):
    path = tmp_path / "stereo.wav"
    encode("-f", "lavfi", "-i", "aevalsrc=0|0.5*sin(440*2*PI*t):s=48000:d=2", path)
    assert analyze(path, probe(path), Settings()) == []


def test_opposite_phase_channels_are_not_downmixed(tmp_path, encode):
    path = tmp_path / "opposite.wav"
    encode("-f", "lavfi", "-i", "aevalsrc=0.5*sin(440*2*PI*t)|-0.5*sin(440*2*PI*t):s=48000:d=2", path)
    assert analyze(path, probe(path), Settings()) == []


def test_unknown_multichannel_layout_is_reported(tmp_path):
    path = tmp_path / "unknown.wav"
    write_wav(path, channels=6)
    with pytest.raises(MediaError, match="channel"):
        probe(path)
