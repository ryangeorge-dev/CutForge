from fractions import Fraction
from uuid import uuid4
from lxml import etree as ET
import pytest

from cutforge.analysis import analyze
from cutforge.engine import timeline, xml_time
from cutforge.export import export_fcpxml
from cutforge.media import probe, MediaError
from cutforge.models import Project, Settings, ReviewRequest
from cutforge.review import merge_analysis, review


@pytest.mark.parametrize("extension,rate,audio", [("mp4", "25", True), ("mov", "30000/1001", True), ("mp4", "24", False)])
def test_video_pipeline(tmp_path, wav, encode, extension, rate, audio):
    path = tmp_path / f"Video & sync.{extension}"
    args = ["-f", "lavfi", "-i", f"testsrc2=size=320x180:rate={rate}:duration=5"]
    if audio:
        args += ["-i", wav, "-c:a", "aac"]
    encode(*args, "-c:v", "libx264", "-pix_fmt", "yuv420p", path)
    metadata = probe(path)
    assert metadata.has_video and metadata.has_audio == audio
    assert Fraction(metadata.rate) == Fraction(rate)
    assert metadata.width == 320 and metadata.height == 180
    cuts = analyze(path, metadata, Settings())
    assert len(cuts) == (3 if audio else 0)
    p = Project(id=uuid4().hex, name=path.name, media_name=path.name, media_size=path.stat().st_size, metadata=metadata)
    merge_analysis(p, cuts)
    review(p, ReviewRequest(revision=0, action="accept_all"))
    root = ET.fromstring(export_fcpxml(p, path))
    asset = root.find("resources/asset")
    assert asset.get("hasVideo") == "1"
    assert asset.get("hasAudio") == ("1" if audio else None)
    assert asset.get("src") == path.resolve().as_uri()
    expected = timeline(cuts, metadata.duration_ticks)
    clips = root.findall(".//asset-clip")
    assert len(clips) == len(expected)
    for node, clip in zip(clips, expected):
        assert node.get("start") == xml_time(clip.source_start, Fraction(rate))
        assert node.get("duration") == xml_time(clip.duration, Fraction(rate))
        # One asset-clip references both streams: no independent audio boundary
        # can drift from the video boundary.
        assert node.get("ref") == "r2"
        assert (Fraction(node.get("start")[:-1]) * Fraction(rate)).denominator == 1
    if not audio:
        assert not root.findall(".//audio")
        assert not root.findall(".//*[@audioRole]")


def test_vfr_is_rejected(tmp_path, encode):
    path = tmp_path / "vfr.mp4"
    encode("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=2", "-vf", "select='if(lt(t,1),1,not(mod(n,2)))'",
           "-fps_mode", "vfr", "-c:v", "libx264", path)
    with pytest.raises(MediaError, match="Variable-frame-rate"):
        probe(path)


def test_nonzero_timecode_rejected(tmp_path, encode):
    path = tmp_path / "timecode.mov"
    encode("-f", "lavfi", "-i", "testsrc2=size=160x90:rate=25:duration=1", "-c:v", "libx264", "-timecode", "01:00:00:00", path)
    with pytest.raises(MediaError, match="timecode"):
        probe(path)
