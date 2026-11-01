from uuid import uuid4

import pytest
from lxml import etree as ET

from cutforge.export import export_fcpxml, validate_export
from cutforge.models import Cut, Metadata, Project, ReviewRequest
from cutforge.review import merge_analysis, review
from cutforge.store import Store


def project():
    return Project(id=uuid4().hex, name="video.mp4", media_name="source.mp4", media_size=1,
                   metadata=Metadata(duration_ticks=300, rate="30000/1001", has_video=True),
                   cuts=[Cut(id="30:60", start=30, end=60, decision="accepted")])


def test_adjust_undo_redo_and_reanalysis_persist(tmp_path):
    p = project()
    review(p, ReviewRequest(revision=0, action="adjust", cut_id="30:60", start=31, end=59))
    assert (p.cuts[0].start, p.cuts[0].end, p.cuts[0].decision) == (31, 59, "accepted")
    store = Store(tmp_path)
    store.save(p)
    p = store.load(p.id)
    review(p, ReviewRequest(revision=0, action="undo"))
    assert (p.cuts[0].start, p.cuts[0].end, p.cuts[0].adjusted) == (30, 60, False)
    review(p, ReviewRequest(revision=0, action="redo"))
    assert (p.cuts[0].start, p.cuts[0].end, p.cuts[0].adjusted) == (31, 59, True)
    merge_analysis(p, [(30, 60)])
    assert (p.cuts[0].start, p.cuts[0].end) == (31, 59)
    merge_analysis(p, [(35, 65)])
    assert next(c for c in p.cuts if c.id == "30:60").decision == "accepted"


@pytest.mark.parametrize("start,end", [(40, 40), (50, 20), (0, 301), (None, 50)])
def test_invalid_adjustment_is_atomic(start, end):
    p = project()
    before = p.model_dump_json()
    with pytest.raises(ValueError, match="boundaries"):
        review(p, ReviewRequest(revision=0, action="adjust", cut_id="30:60", start=start, end=end))
    assert p.model_dump_json() == before


def test_legacy_history_remains_undoable():
    p = project()
    p.schema_version = 1
    p.history = [{"30:60": "pending"}]
    p = Project.model_validate_json(p.model_dump_json())
    review(p, ReviewRequest(revision=0, action="undo"))
    assert p.cuts[0].decision == "pending"
    review(p, ReviewRequest(revision=0, action="redo"))
    assert p.cuts[0].decision == "accepted"


def test_adjusted_export_exact_ranges_and_validation(tmp_path):
    p = project()
    p.metadata.has_audio = False
    path = tmp_path / "video.mp4"
    path.write_bytes(b"fixture: serializer test only")
    review(p, ReviewRequest(revision=0, action="adjust", cut_id="30:60", start=31, end=59))
    root = ET.fromstring(export_fcpxml(p, path))
    clips = root.findall(".//asset-clip")
    assert clips[0].get("duration") == "31031/30000s"
    assert clips[1].get("start") == "59059/30000s"
    root.find(".//sequence").set("duration", "999s")
    with pytest.raises(ValueError, match="sequence duration"):
        validate_export(ET.tostring(root), p, path)
