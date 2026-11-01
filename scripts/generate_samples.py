"""Generate original synthetic fixtures and optional persistent example projects."""
import argparse
import math
from pathlib import Path
import struct
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def wav(path: Path, rate: int, kind: str, channels: int = 1):
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        for second in range(5):
            buffer = bytearray()
            for i in range(rate):
                active = kind == "tone" or (kind == "mixed" and second in (1, 3))
                value = int(10000 * math.sin(2 * math.pi * 440 * i / rate)) if active else 0
                buffer.extend(struct.pack("<" + "h" * channels, *([value] * channels)))
            output.writeframes(buffer)


def generate(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    for name, rate, kind, channels in [("narration 48k.wav", 48000, "mixed", 2), ("narration 44k.wav", 44100, "mixed", 1), ("silence.wav", 48000, "silence", 1), ("no silence.wav", 48000, "tone", 1)]:
        wav(output / name, rate, kind, channels)
    def ff(*args):
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", *map(str, args)], check=True)
    ff("-i", output / "narration 48k.wav", "-c:a", "libmp3lame", output / "narration.mp3")
    for suffix, fps, audio in [("mp4", "25", True), ("mov", "30000/1001", True), ("mp4", "24", False)]:
        args = ["-f", "lavfi", "-i", f"testsrc2=size=640x360:rate={fps}:duration=5"]
        if audio:
            args += ["-i", output / "narration 48k.wav", "-c:a", "aac"]
        ff(*args, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output / f"{'video with audio' if audio else 'video only'}.{suffix}")
    print(f"Generated samples in {output}")


def projects(output: Path):
    from shutil import copy2
    from uuid import uuid4
    from cutforge.analysis import analyze
    from cutforge.export import export_fcpxml
    from cutforge.media import probe
    from cutforge.models import Project
    from cutforge.review import merge_analysis
    from cutforge.store import Store

    store = Store(ROOT / "workspace")
    export_dir = ROOT / "samples" / "exports"
    export_dir.mkdir(exist_ok=True)
    for source in sorted(output.iterdir()):
        if not source.is_file() or source.suffix not in {".wav", ".mp3", ".mp4", ".mov"}:
            continue
        identifier = uuid4().hex
        directory = store.directory(identifier)
        directory.mkdir()
        target = directory / ("source" + source.suffix)
        copy2(source, target)
        p = Project(id=identifier, name=source.name, media_name=target.name, media_size=target.stat().st_size, metadata=probe(target))
        merge_analysis(p, analyze(target, p.metadata, p.settings))
        # Deliberately reject the middle silence: proves rejected intervals survive export.
        for index, cut in enumerate(p.cuts):
            cut.decision = "accepted" if index != 1 else "rejected"
        store.save(p)
        if any(c.start == 0 and c.end == p.metadata.duration_ticks and c.decision == "accepted" for c in p.cuts):
            continue
        (export_dir / (source.name + ".fcpxml")).write_bytes(export_fcpxml(p, target))
    print(f"Example projects saved in {store.root}; FCPXML files in {export_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", action="store_true", help="Also create persistent demo projects and FCPXML exports")
    args = parser.parse_args()
    destination = ROOT / "samples"
    generate(destination)
    if args.projects:
        projects(destination)
