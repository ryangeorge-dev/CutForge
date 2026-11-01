"""Minimal FCPXML 1.7: a single source asset, retained ranges in a spine."""
from fractions import Fraction
import logging
from pathlib import Path
from lxml import etree as ET

from .engine import Clip, timeline, xml_time
from .media import source_origin
from .models import Project


AUDIO_SEQUENCE_RATE = Fraction(25)
logger = logging.getLogger(__name__)


class ExportDecisionError(ValueError):
    """An actionable review error, safe to show in the browser."""


class EmptyTimelineError(ExportDecisionError):
    pass


def sequence_rate(project: Project) -> Fraction:
    return Fraction(project.metadata.rate) if project.metadata.has_video else AUDIO_SEQUENCE_RATE


def align_clips(clips: list[Clip], rate: Fraction, fps: Fraction, source_duration: int) -> list[Clip]:
    """Export adapter only: project decisions and the edit engine stay exact.

    Round cumulative boundaries, not each duration (which accumulates drift).
    At a join, apply the same delta to the outgoing OUT and incoming IN. Thus
    removed gaps retain their lengths and source ranges cannot overlap.
    """
    if not clips:
        return []
    if rate <= 0 or fps <= 0:
        raise ValueError("Export rates must be positive")
    step = rate / fps
    if step.denominator != 1:
        raise ExportDecisionError("The sequence frame grid does not fall on whole source samples. "
                                  "This sample-rate/frame-rate combination cannot be exported safely.")
    step = int(step)
    boundaries = [c.offset for c in clips] + [clips[-1].offset + clips[-1].duration]
    # Integer nearest-frame rounding, with exact half-frame ties going later.
    aligned = [((2 * value + step) // (2 * step)) * step for value in boundaries]
    # A final partial frame cannot be extended beyond the physical source.
    last = clips[-1]
    limit = boundaries[-1] + source_duration - (last.source_start + last.duration)
    aligned[-1] = min(aligned[-1], (limit // step) * step)
    result = []
    for i, clip in enumerate(clips):
        duration = aligned[i + 1] - aligned[i]
        if duration <= 0:
            raise ExportDecisionError(
                f"Retained segment {i + 1} collapses on the export frame grid. "
                "Adjust or reject a neighboring cut to retain a longer segment; no clips were discarded.")
        start = clip.source_start + aligned[i] - clip.offset
        if start < 0 or start + duration > source_duration:
            raise ValueError("Aligned source range is outside the recording")
        if result and start < result[-1].source_start + result[-1].duration:
            raise ValueError("Aligned source ranges overlap")
        result.append(Clip(start, duration, aligned[i]))
    return result


def export_clips(project: Project) -> tuple[list[Clip], list[Clip]]:
    original = timeline(((c.start, c.end) for c in project.cuts if c.decision == "accepted"),
                        project.metadata.duration_ticks)
    return original, align_clips(original, Fraction(project.metadata.rate), sequence_rate(project),
                                 project.metadata.duration_ticks)


def alignment_impact(original: list[Clip], aligned: list[Clip]) -> dict[str, int]:
    """Counts in source ticks (samples for audio, frames for video)."""
    maximum = 0
    for a, b in zip(original, aligned, strict=True):
        maximum = max(maximum, abs(b.source_start - a.source_start),
                      abs(b.source_start + b.duration - a.source_start - a.duration))
    # Intersect the entire selections: an edge may move past a tiny removed gap
    # into the next original segment. Per-clip intersections would overcount loss.
    i = j = overlap = 0
    while i < len(original) and j < len(aligned):
        a, b = original[i], aligned[j]
        a_end, b_end = a.source_start + a.duration, b.source_start + b.duration
        overlap += max(0, min(a_end, b_end) - max(a.source_start, b.source_start))
        if a_end <= b_end:
            i += 1
        else:
            j += 1
    added = sum(c.duration for c in aligned) - overlap
    removed = sum(c.duration for c in original) - overlap
    return dict(added_ticks=added, removed_ticks=removed, max_boundary_shift_ticks=maximum,
                duration_delta_ticks=added - removed)


def audio_layout(channels: int) -> str:
    return {1: "mono", 2: "stereo", 6: "surround"}[channels]


def audio_channels(channels: int) -> str:
    # One component with all source channels; two components would be dual mono.
    return ", ".join(str(channel) for channel in range(1, channels + 1))


def source_time(origin: Fraction, ticks: int, rate: Fraction) -> str:
    seconds = origin + ticks / rate
    return f"{seconds.numerator}/{seconds.denominator}s"


def export_fcpxml(project: Project, media: Path) -> bytes:
    metadata = project.metadata
    rate = Fraction(metadata.rate)
    original, clips = export_clips(project)
    if not clips:
        raise EmptyTimelineError("Every source interval is removed. Reject or restore at least one cut before exporting.")
    origin = source_origin(media, metadata)
    root = ET.Element("fcpxml", version="1.7")
    impact = alignment_impact(original, clips)
    if impact["added_ticks"] or impact["removed_ticks"]:
        message = (f"CutForge frame-aligned export at {sequence_rate(project)} fps: "
                   f"added {impact['added_ticks']} and removed {impact['removed_ticks']} source ticks "
                   f"at {rate} ticks/s; maximum boundary shift {impact['max_boundary_shift_ticks']} ticks; "
                   f"duration change {impact['duration_delta_ticks']} ticks. "
                   "Saved sample-accurate decisions are unchanged; exported edge samples differ.")
        root.append(ET.Comment(message))
        logger.warning(message)
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", id="r1", frameDuration=xml_time(1, sequence_rate(project)),
                  width=str(metadata.width or 1920), height=str(metadata.height or 1080))
    attrs = dict(id="r2", name=project.name, src=media.resolve().as_uri(), start=source_time(origin, 0, rate),
                 duration=xml_time(metadata.duration_ticks, rate))
    if metadata.has_video:
        attrs.update(hasVideo="1", format="r1")
    if metadata.has_audio:
        attrs.update(hasAudio="1", audioSources="1", audioChannels=str(metadata.channels), audioRate=str(metadata.sample_rate))
    ET.SubElement(resources, "asset", **attrs)
    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name="CutForge")
    node = ET.SubElement(event, "project", name=f"{project.name} rough cut")
    attrs = dict(format="r1", duration=xml_time(sum(c.duration for c in clips), rate), tcStart="0s", tcFormat="NDF")
    if metadata.has_audio:
        attrs.update(audioLayout=audio_layout(metadata.channels),
                     audioRate={44100: "44.1k", 48000: "48k", 32000: "32k", 96000: "96k", 88200: "88.2k",
                                176400: "176.4k", 192000: "192k"}.get(metadata.sample_rate, "48k"))
    sequence = ET.SubElement(node, "sequence", **attrs)
    spine = ET.SubElement(sequence, "spine")
    for clip in clips:
        attrs = dict(name=project.name, ref="r2", offset=xml_time(clip.offset, rate),
                     start=source_time(origin, clip.source_start, rate), duration=xml_time(clip.duration, rate))
        if metadata.has_audio:
            attrs["audioRole"] = "dialogue"
        node = ET.SubElement(spine, "asset-clip", **attrs)
        if metadata.has_audio:
            ET.SubElement(node, "audio-channel-source", srcCh=audio_channels(metadata.channels), role="dialogue")
    xml = ET.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True, doctype="<!DOCTYPE fcpxml>")
    validate_export(xml, project, media)
    return xml


def validate_export(xml: bytes, project: Project, media: Path) -> None:
    parser = ET.XMLParser(resolve_entities=False, no_network=True)
    root = ET.fromstring(xml, parser)
    dtd_path = Path(__file__).parent / "schemas" / "FCPXMLv1_7.dtd"
    with dtd_path.open("rb") as source:
        dtd = ET.DTD(source)
        if not dtd.validate(root):
            raise ValueError(f"FCPXML structural validation failed: {dtd.error_log}")
    assets = root.findall("resources/asset")
    if len(assets) != 1 or assets[0].get("id") != "r2":
        raise ValueError("Export must declare exactly one canonical source asset")
    asset = assets[0]
    if not media.is_file() or asset.get("src") != media.resolve().as_uri():
        raise ValueError("Export must reference existing canonical workspace media")
    with media.open("rb") as source:
        if not source.read(1):
            raise ValueError("Export source media is empty")
    _, expected = export_clips(project)
    actual = root.findall(".//spine/asset-clip")
    rate = Fraction(project.metadata.rate)
    origin = source_origin(media, project.metadata)
    if (Fraction(asset.get("start", "0s")[:-1]) != origin or
            Fraction(asset.get("duration", "0s")[:-1]) != project.metadata.duration_ticks / rate):
        raise ValueError("Export asset range does not match source media")
    if asset.get("hasVideo", "0") != str(int(project.metadata.has_video)):
        raise ValueError("Export video declaration does not match source media")
    if asset.get("hasAudio", "0") != str(int(project.metadata.has_audio)):
        raise ValueError("Export audio declaration does not match source media")
    if len(actual) != len(expected):
        raise ValueError("Export clip count does not match approved decisions")
    sequence = root.find(".//sequence")
    format_node = root.find("resources/format")
    if (sequence is None or sequence.get("format") != "r1" or format_node is None
            or format_node.get("id") != "r1"
            or Fraction(format_node.get("frameDuration", "0s")[:-1]) != 1 / sequence_rate(project)):
        raise ValueError("Export sequence frame grid does not match alignment")
    if sequence is None or Fraction(sequence.get("duration", "0s")[:-1]) != sum(c.duration for c in expected) / rate:
        raise ValueError("Export sequence duration does not match aligned retained media")
    if project.metadata.has_audio:
        if (asset.get("audioSources") != "1" or asset.get("audioChannels") != str(project.metadata.channels)
                or asset.get("audioRate") != str(project.metadata.sample_rate)
                or sequence.get("audioLayout") != audio_layout(project.metadata.channels)):
            raise ValueError("Export audio configuration does not match source media")
    for node, clip in zip(actual, expected):
        if node.get("ref") != "r2":
            raise ValueError("Export clip does not reference the canonical source asset")
        mappings = node.findall("audio-channel-source")
        if project.metadata.has_audio:
            if len(mappings) != 1 or mappings[0].get("srcCh") != audio_channels(project.metadata.channels):
                raise ValueError("Export audio mapping does not match source media")
        elif mappings:
            raise ValueError("Export must not add audio to video-only media")
        for attr, value in (("start", clip.source_start), ("duration", clip.duration), ("offset", clip.offset)):
            expected_time = Fraction(value, 1) / rate + (origin if attr == "start" else 0)
            if Fraction(node.get(attr)[:-1]) != expected_time:
                raise ValueError(f"Export {attr} does not match approved decisions")
