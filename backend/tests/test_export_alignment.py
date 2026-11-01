"""Export frame-grid adapter: keep exact review data; account for changed samples."""
from fractions import Fraction as F
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from lxml import etree as ET

from cutforge.api import create_app
from cutforge.engine import Clip, timeline
from cutforge.export import align_clips, alignment_impact, export_fcpxml, ExportDecisionError, validate_export
from cutforge.media import probe
from cutforge.models import Cut, Project


def test_matches_manually_verified_ten_clip_diagnostic():
    # Sample coordinates from diagnostic A and B. No media paths or recordings.
    a = [(81362,81748,0),(208167,30234,81748),(286124,198338,111982),
         (513148,89748,310320),(626857,377285,400068),(1041794,96451,777353),
         (1250839,49965,873804),(1458788,14641,923769),(1515228,79913,938410),
         (1766082,200830,1018323)]
    b = [(81362,82560,0),(208979,28800,82560),(285502,199680,111360),
         (513868,88320,311040),(626149,378240,399360),(1042041,96000,777600),
         (1250635,49920,873600),(1458539,15360,923520),(1515698,78720,938880),
         (1765359,201600,1017600)]
    original = [Clip(*x) for x in a]
    aligned = align_clips(original,F(48000),F(25),2100000)
    assert aligned == [Clip(*x) for x in b]
    assert alignment_impact(original,aligned) == dict(added_ticks=4802,removed_ticks=4755,
                                                     max_boundary_shift_ticks=812,duration_delta_ticks=47)


@pytest.mark.parametrize('rate,fps', [(48000,F(25)),(44100,F(25)),(48000,F(24)),(48000,F(30))])
def test_hundreds_of_segments_no_drift_or_repeated_samples(rate,fps):
    # Deterministic varied durations, including tiny removed gaps.
    clips=[]; source=1000; offset=0
    for i in range(400):
        duration=rate//10+(i*197)%rate
        clips.append(Clip(source,duration,offset))
        source+=duration+1+(i*331)%(rate//5)
        offset+=duration
    aligned=align_clips(clips,F(rate),fps,source)
    step=int(F(rate)/fps)
    assert len(aligned)==400
    cursor=0
    for i,(a,b) in enumerate(zip(clips,aligned)):
        assert b.offset==cursor and b.offset%step==b.duration%step==0 and b.duration>0
        assert b.source_start-a.source_start==b.offset-a.offset
        assert b.source_start+b.duration-a.source_start-a.duration==b.offset+b.duration-a.offset-a.duration
        assert abs(b.source_start-a.source_start)<=step//2
        if i:
            old_gap=a.source_start-clips[i-1].source_start-clips[i-1].duration
            new_gap=b.source_start-aligned[i-1].source_start-aligned[i-1].duration
            assert new_gap==old_gap>0
        cursor+=b.duration
    assert abs(cursor-offset)<=step//2  # Total error does not accumulate per clip.


def test_accounting_for_tiny_removed_gap_uses_union_of_source_ranges():
    a=[Clip(0,1001,0),Clip(1002,2839,1001)]
    b=align_clips(a,F(48000),F(25),5000)
    old={s for c in a for s in range(c.source_start,c.source_start+c.duration)}
    new=[s for c in b for s in range(c.source_start,c.source_start+c.duration)]
    assert len(new)==len(set(new))
    assert len(set(new)-old)==len(old-set(new))==1
    impact=alignment_impact(a,b)
    assert impact['added_ticks']==impact['removed_ticks']==1


@pytest.mark.parametrize('clips,total', [([Clip(0,1,0)],1),
    ([Clip(0,48000,0),Clip(50000,10,48000),Clip(51000,48000,48010)],100000),
    ([Clip(0,1930,0),Clip(2000,1,1930)],2001)])
def test_collapsed_segments_fail_without_discarding_decisions(clips,total):
    before=list(clips)
    with pytest.raises(ExportDecisionError,match='collapses'):
        align_clips(clips,F(48000),F(25),total)
    assert clips==before


def test_short_segment_can_survive_and_empty_input_is_safe():
    assert align_clips([],F(48000),F(25),0)==[]
    assert align_clips([Clip(0,1000,0)],F(48000),F(25),3000)==[Clip(0,1920,0)]


def test_source_end_uses_last_available_frame():
    assert align_clips([Clip(0,48001,0)],F(48000),F(25),48001)==[Clip(0,48000,0)]
    # Nearest would extend 896 samples past EOF; floor is the closest legal end.
    assert align_clips([Clip(0,49024,0)],F(48000),F(25),49024)==[Clip(0,48000,0)]


def test_exact_ties_and_fractional_sample_grids():
    assert align_clips([Clip(0,2880,0)],F(48000),F(25),4000)==[Clip(0,3840,0)]
    with pytest.raises(ExportDecisionError,match='whole source samples'):
        align_clips([Clip(0,44100,0)],F(44100),F(24),44100)


@pytest.mark.parametrize('fps',[F(25),F(30000,1001),F(24000,1001)])
def test_video_frame_boundaries_are_unchanged(fps):
    original=timeline([(31,59),(70,73)],300)
    assert align_clips(original,fps,fps,300)==original


def test_declared_sequence_grid_drives_export_and_validation(wav,monkeypatch):
    import cutforge.export as exporter
    p=Project(id=uuid4().hex,name='audio',media_name=wav.name,media_size=wav.stat().st_size,metadata=probe(wav),
              cuts=[Cut(id='a',start=50001,end=100001,decision='accepted')])
    monkeypatch.setattr(exporter,'AUDIO_SEQUENCE_RATE',F(24))
    xml=export_fcpxml(p,wav)
    r=ET.fromstring(xml)
    assert r.find('resources/format').get('frameDuration')=='1/24s'
    for c in r.findall('.//asset-clip'):
        for key in ('offset','duration'):
            assert (F(c.get(key)[:-1])*24).denominator==1
    r.find('resources/format').set('frameDuration','1/25s')
    with pytest.raises(ValueError,match='frame grid'):
        validate_export(ET.tostring(r),p,wav)


def test_collapse_is_actionable_http_400_and_project_unchanged(wav,tmp_path):
    p=Project(id=uuid4().hex,name='audio',media_name=wav.name,media_size=wav.stat().st_size,metadata=probe(wav),
              cuts=[Cut(id='a',start=1,end=240000,decision='accepted')])
    app=create_app(tmp_path/'workspace')
    app.state.store.save(p)
    directory=app.state.store.directory(p.id)
    (directory/p.media_name).write_bytes(wav.read_bytes())
    before=(directory/'project.json').read_bytes()
    with TestClient(app) as client:
        response=client.get(f'/api/projects/{p.id}/export?revision=0')
        assert response.status_code==400 and 'collapses' in response.json()['detail']
        assert 'Content-Disposition' not in response.headers
    assert (directory/'project.json').read_bytes()==before
