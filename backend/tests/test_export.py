"""Interchange regressions: source clock differs from the edit/timeline clock."""
from fractions import Fraction
import logging
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from lxml import etree as ET
import pytest

from cutforge.api import create_app
from cutforge.export import export_fcpxml, validate_export
from cutforge.media import probe, source_origin, MediaError
from cutforge.models import Cut, Project
from conftest import write_wav


def project_for(path):
    return Project(id=uuid4().hex, name='Voice & "test" <é>', media_name=path.name,
                   media_size=path.stat().st_size, metadata=probe(path))


def seconds(node, attribute):
    return Fraction(node.get(attribute)[:-1])


@pytest.mark.parametrize("channels,rate,reference", [(1, 48000, 175164288), (2, 44100, 44100001), (1, 48000, 0)])
def test_bwf_origin_channels_paths_and_accounted_retained_samples(tmp_path, encode, channels, rate, reference):
    original = tmp_path / "original.wav"
    write_wav(original, rate=rate, channels=channels)
    path = tmp_path / 'Voice é & #100% "test".wav'
    encode("-i", original, "-c:a", "pcm_s24le", "-write_bext", "1",
           "-metadata", f"time_reference={reference}", path)
    p = project_for(path)
    # Overlap, adjacency and duplicate approvals remove each source sample once.
    intervals = [(0, rate), (2*rate, 2*rate+10), (2*rate+5, 3*rate),
                 (3*rate, 3*rate+1), (2*rate, 2*rate+10), (4*rate, 5*rate)]
    p.cuts = [Cut(id=str(i), start=a, end=b, decision="accepted") for i, (a, b) in enumerate(intervals)]
    p.cuts += [Cut(id="rejected", start=rate, end=2*rate, decision="rejected"),
               Cut(id="pending", start=3*rate+1, end=4*rate)]
    before = p.model_dump_json()
    media_before = path.read_bytes()
    xml = export_fcpxml(p, path)  # Includes the declared 1.7 DTD check.
    assert p.model_dump_json() == before and path.read_bytes() == media_before
    root = ET.fromstring(xml)
    asset, = root.findall("resources/asset")
    origin = Fraction(reference, rate)
    assert seconds(asset, "start") == origin
    assert seconds(asset, "duration") == 5
    assert asset.get("name") == p.name  # XML escaping round-trips.
    uri = urlsplit(asset.get("src"))
    assert uri.scheme == "file" and not uri.netloc and not uri.fragment and not uri.query
    assert Path(unquote(uri.path)) == path.resolve()
    assert Path(unquote(uri.path)).read_bytes() == media_before
    sequence = root.find(".//sequence")
    assert sequence.get("audioLayout") == ("mono" if channels == 1 else "stereo")
    assert asset.get("audioChannels") == str(channels)
    assert asset.get("audioSources") == "1"
    assert asset.get("audioRate") == str(rate)
    assert seconds(sequence, "duration") == 2
    clips = root.findall(".//spine/asset-clip")
    assert len(clips) == 2
    assert [seconds(c, "start")-origin for c in clips] == [Fraction(1), Fraction(3*rate+1, rate)]
    assert [seconds(c, "duration") for c in clips] == [Fraction(1), Fraction(1)]
    assert [seconds(c, "offset") for c in clips] == [0, 1]
    retained = []
    for clip in clips:
        assert clip.get("ref") == asset.get("id")
        mapping, = clip.findall("audio-channel-source")
        assert mapping.get("srcCh") == ("1" if channels == 1 else "1, 2")
        start = (seconds(clip, "start")-origin)*rate
        length = seconds(clip, "duration")*rate
        assert start.denominator == length.denominator == 1
        retained.extend(range(int(start), int(start+length)))
    removed = {sample for a, b in intervals for sample in range(a, b)}
    # Nearest cumulative frame adds exactly the first sample of trailing silence.
    assert retained == [i for i in range(5*rate) if i not in removed or i == 4*rate]
    assert b"added 1 and removed 0" in xml


@pytest.mark.parametrize("mutation", ["path", "ref", "origin", "channels", "mapping", "duration", "offset", "start", "dtd"])
def test_validation_rejects_incorrect_exports(wav, mutation):
    p = project_for(wav)
    root = ET.fromstring(export_fcpxml(p, wav))
    asset = root.find("resources/asset")
    clip = root.find(".//asset-clip")
    if mutation == "path":
        asset.set("src", wav.with_name("missing.wav").as_uri())
    elif mutation == "ref":
        clip.set("ref", "r1")  # Existing ID, but a format is not the source asset.
    elif mutation == "origin":
        asset.set("start", "1s")
    elif mutation == "channels":
        asset.set("audioChannels", "2")
    elif mutation == "mapping":
        clip.find("audio-channel-source").set("srcCh", "1, 2")
    elif mutation == "duration":
        root.find(".//sequence").set("duration", "7s")
    elif mutation in {"offset", "start"}:
        clip.set(mutation, "1s")
    else:
        root.set("version", "1.99")
    with pytest.raises(ValueError):
        validate_export(ET.tostring(root), p, wav)


def test_bwf_probe_failure_is_not_silently_treated_as_zero(wav, monkeypatch):
    import cutforge.media as media
    metadata = probe(wav)
    def fail(*args, **kwargs):
        raise MediaError("cannot read private source path")
    monkeypatch.setattr(media, "run", fail)
    with pytest.raises(MediaError):
        source_origin(wav, metadata)


@pytest.mark.parametrize("error", [RuntimeError, ValueError, PermissionError, FileNotFoundError])
def test_export_failure_logs_diagnostic_without_leaking_paths(tmp_path, wav, monkeypatch, caplog, error):
    import cutforge.api as api
    p = project_for(wav)
    app = create_app(tmp_path / "workspace")
    app.state.store.save(p)
    (app.state.store.directory(p.id) / p.media_name).write_bytes(wav.read_bytes())
    def fail(*args):
        raise error("sensitive /private/recordings/source.wav")
    with TestClient(app) as client:
        url = f"/api/projects/{p.id}/export?revision=0"
        assert client.get(url).status_code == 200
        real_export = api.export_fcpxml
        monkeypatch.setattr(api, "export_fcpxml", fail)
        with caplog.at_level(logging.ERROR):
            response = client.get(url)
        assert response.status_code == 500
        assert "sensitive" not in response.text and "/private/" not in response.text
        assert "diagnostic" in response.json()["detail"]
        diagnostic = response.json()["detail"].split("diagnostic ")[1].split(")")[0]
        assert diagnostic in caplog.text and p.id in caplog.text and "sensitive" in caplog.text
        assert "Content-Disposition" not in response.headers
        assert "X-CutForge-Validation" not in response.headers
        monkeypatch.setattr(api, "export_fcpxml", real_export)
        assert client.get(url).status_code == 200  # Failure does not poison subsequent exports.


def test_empty_timeline_is_an_actionable_400(tmp_path, wav):
    p = project_for(wav)
    p.cuts = [Cut(id="all", start=0, end=p.metadata.duration_ticks, decision="accepted")]
    app = create_app(tmp_path / "workspace")
    app.state.store.save(p)
    (app.state.store.directory(p.id) / p.media_name).write_bytes(wav.read_bytes())
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{p.id}/export?revision=0")
        assert response.status_code == 400
        assert "Every source interval" in response.json()["detail"]
