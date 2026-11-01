"""Minimal FCPXML 1.7: a single source asset, retained ranges in a spine."""
from fractions import Fraction
from pathlib import Path
from lxml import etree as ET

from .engine import timeline, xml_time
from .models import Project


def export_fcpxml(project: Project, media: Path) -> bytes:
    metadata = project.metadata
    rate = Fraction(metadata.rate)
    clips = timeline(((c.start, c.end) for c in project.cuts if c.decision == "accepted"), metadata.duration_ticks)
    if not clips:
        raise ValueError("Every source interval is removed. Reject or restore at least one cut before exporting.")
    root = ET.Element("fcpxml", version="1.7")
    resources = ET.SubElement(root, "resources")
    ET.SubElement(resources, "format", id="r1", frameDuration=xml_time(1, rate if metadata.has_video else Fraction(25)),
                  width=str(metadata.width or 1920), height=str(metadata.height or 1080))
    attrs = dict(id="r2", name=project.name, src=media.resolve().as_uri(), start="0s",
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
        attrs.update(audioLayout="surround" if metadata.channels == 6 else "stereo",
                     audioRate={44100: "44.1k", 48000: "48k", 32000: "32k", 96000: "96k", 88200: "88.2k",
                                176400: "176.4k", 192000: "192k"}.get(metadata.sample_rate, "48k"))
    sequence = ET.SubElement(node, "sequence", **attrs)
    spine = ET.SubElement(sequence, "spine")
    for clip in clips:
        attrs = dict(name=project.name, ref="r2", offset=xml_time(clip.offset, rate),
                     start=xml_time(clip.source_start, rate), duration=xml_time(clip.duration, rate))
        if metadata.has_audio:
            attrs["audioRole"] = "dialogue"
        ET.SubElement(spine, "asset-clip", **attrs)
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
    if not media.is_file() or root.find("resources/asset").get("src") != media.resolve().as_uri():
        raise ValueError("Export must reference existing canonical workspace media")
    expected = timeline(((c.start, c.end) for c in project.cuts if c.decision == "accepted"), project.metadata.duration_ticks)
    actual = root.findall(".//spine/asset-clip")
    rate = Fraction(project.metadata.rate)
    if len(actual) != len(expected):
        raise ValueError("Export clip count does not match approved decisions")
    sequence = root.find(".//sequence")
    if sequence is None or Fraction(sequence.get("duration", "0s")[:-1]) != sum(c.duration for c in expected) / rate:
        raise ValueError("Export sequence duration does not match retained media")
    for node, clip in zip(actual, expected):
        if node.get("ref") != "r2":
            raise ValueError("Export clip does not reference the canonical source asset")
        for attr, value in (("start", clip.source_start), ("duration", clip.duration), ("offset", clip.offset)):
            if Fraction(node.get(attr)[:-1]) != Fraction(value, 1) / rate:
                raise ValueError(f"Export {attr} does not match approved decisions")
