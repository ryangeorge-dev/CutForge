"""Local media inspection and decoding. Never invoke a shell with user input."""
import json
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .models import Metadata

SUPPORTED = {".wav", ".mp3", ".mp4", ".mov"}
INPUT_RESTRICTIONS = ["-protocol_whitelist", "file,pipe", "-format_whitelist", "wav,mp3,mov"]


class MediaError(ValueError):
    pass


def run(args: list[str], timeout: int = 7200) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run([args[0], *INPUT_RESTRICTIONS, *args[1:]], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise MediaError(f"Missing {args[0]}. Install FFmpeg and add ffmpeg/ffprobe to PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"Media processing exceeded {timeout} seconds. Try a shorter recording.") from exc
    if result.returncode:
        raise MediaError("Media could not be decoded: " + result.stderr[-1500:])
    return result


def source_origin(path: Path, metadata: Metadata) -> Fraction:
    """BWF's first sample is timed from midnight, not the start of the file.

    Read at export so existing projects need no migration. Edit decisions remain
    zero-relative. Nonzero video timecodes are already rejected during import.
    """
    if metadata.has_video or path.suffix.lower() != ".wav":
        return Fraction(0)
    data = json.loads(run([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
        "stream=sample_rate:format_tags=time_reference", "-of", "json", str(path),
    ], timeout=30).stdout)
    streams = data.get("streams", [])
    if len(streams) != 1 or int(streams[0].get("sample_rate", 0)) != metadata.sample_rate:
        raise MediaError("WAV sample rate no longer matches the imported project.")
    reference = data.get("format", {}).get("tags", {}).get("time_reference", "0")
    if not str(reference).isdigit() or int(reference) > 2**64 - 1:
        raise MediaError("Invalid Broadcast Wave time reference.")
    return Fraction(int(reference), metadata.sample_rate)


def probe(path: Path) -> Metadata:
    if path.suffix.lower() not in SUPPORTED:
        raise MediaError("Supported files: WAV, MP3, MP4, and MOV.")
    data = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]).stdout)
    streams = data.get("streams", [])
    audio = [s for s in streams if s["codec_type"] == "audio"]
    video = [s for s in streams if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")]
    if len(audio) > 1 or len(video) > 1:
        raise MediaError("This MVP supports one audio stream and one video stream. Remux your selected streams first.")
    if not audio and not video:
        raise MediaError("No playable audio or video stream found.")
    expected = {".wav": "wav", ".mp3": "mp3", ".mp4": "mov", ".mov": "mov"}[path.suffix.lower()]
    if expected not in data.get("format", {}).get("format_name", "").split(","):
        raise MediaError("The file contents do not match its supported extension.")
    if path.suffix.lower() in {".wav", ".mp3"} and video:
        raise MediaError("Audio files must not contain video.")
    if video:
        return probe_video(path, video[0], audio[0] if audio else None, data)
    a = audio[0]
    channels = int(a["channels"])
    if channels not in (1, 2, 6) or (channels == 6 and a.get("channel_layout") not in {"5.1", "5.1(side)"}):
        raise MediaError("Supported channel configurations are mono, stereo, and 5.1 (6 channels).")
    sample_rate = int(a["sample_rate"])
    # Decode to count actual samples, including MP3 encoder-delay/padding removal.
    # astats reports a count without writing a huge PCM copy.
    import re
    decoded = run(["ffmpeg", "-hide_banner", "-nostdin", "-xerror", "-i", str(path), "-map", "0:a:0",
                   "-af", "astats=metadata=0:reset=0", "-vn", "-f", "null", "-"])
    counts = re.findall(r"Number of samples:\s*(\d+)", decoded.stderr)
    if not counts or int(counts[-1]) <= 0:
        raise MediaError("Audio has no decodable samples.")
    return Metadata(duration_ticks=int(counts[-1]), rate=str(sample_rate), audio_codec=a["codec_name"],
                    sample_rate=sample_rate, channels=channels, channel_layout=a.get("channel_layout"))


def probe_video(path: Path, video: dict, audio: dict | None, data: dict) -> Metadata:
    rate = Fraction(video.get("r_frame_rate", "0/1"))
    if rate <= 0 or rate > 240:
        raise MediaError("Video has an unsupported or unknown frame rate (expected 1–240 fps).")
    if video.get("field_order", "unknown") not in {"unknown", "progressive"}:
        raise MediaError("Interlaced video is not supported. Convert a copy to progressive video first.")
    if any(s.get("rotation", 0) != 0 for s in video.get("side_data_list", [])):
        raise MediaError("Rotated video metadata is not supported yet. Bake the rotation into a new copy first.")
    timecodes = [s.get("tags", {}).get("timecode", "00:00:00:00") for s in data.get("streams", [])]
    timecodes.append(data.get("format", {}).get("tags", {}).get("timecode", "00:00:00:00"))
    if any(tc not in {"00:00:00:00", "00:00:00;00"} for tc in timecodes):
        raise MediaError("Nonzero source timecode is not supported yet. Remux a copy with zero timecode before import.")
    timebase = Fraction(video["time_base"])
    # Full decoded frame scan: bounded RAM even for long recordings. Comparing
    # timestamps to an exact expected grid tolerates container tick rounding.
    with tempfile.TemporaryFile(mode="w+t") as frames:
        try:
            result = subprocess.run(["ffprobe", *INPUT_RESTRICTIONS, "-v", "error", "-select_streams", "v:0", "-show_frames",
                                     "-show_entries", "frame=best_effort_timestamp", "-of", "csv=p=0", str(path)],
                                    stdout=frames, stderr=subprocess.PIPE, text=True, timeout=7200)
        except subprocess.TimeoutExpired as exc:
            raise MediaError("Video inspection exceeded two hours. Try a shorter recording.") from exc
        if result.returncode or result.stderr.strip():
            raise MediaError("Video frame decoding failed: " + result.stderr[-1500:])
        frames.seek(0)
        first = None
        count = 0
        for line in frames:
            token = line.strip().split(",")[0]
            if not token:
                continue
            try:
                timestamp = int(token) * timebase
            except ValueError as exc:
                raise MediaError("Video contains frames without usable timestamps.") from exc
            if first is None:
                first = timestamp
                if abs(first) > timebase:
                    raise MediaError("Video starts at a nonzero presentation timestamp. Remux to start at zero first.")
            expected = first + Fraction(count, 1) / rate
            if abs(timestamp - expected) > max(2 * timebase, Fraction(1, 1000000)):
                raise MediaError("Variable-frame-rate or discontinuous video is not supported. Convert a copy to constant frame rate first.")
            count += 1
    if count <= 0:
        raise MediaError("Video contains no decodable frames.")
    warnings = []
    if video.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
        warnings.append("HDR source: preview colors depend on your browser. Configure Resolve color management manually.")
    if audio:
        channels = int(audio["channels"])
        layout = audio.get("channel_layout")
        if channels not in (1, 2, 6) or (channels == 6 and layout not in {"5.1", "5.1(side)"}):
            raise MediaError("Supported audio configurations are mono, stereo, and recognized 5.1 layouts.")
        sample_rate = int(audio["sample_rate"])
        start = Fraction(audio.get("start_time", "0"))
        if abs(start) > Fraction(1, sample_rate):
            raise MediaError("Audio and video have different starting timestamps. Remux aligned streams before import.")
        duration = Fraction(audio.get("duration", str(float(Fraction(count, 1) / rate))))
        if abs(duration - Fraction(count, 1) / rate) > max(Fraction(1, 10), 2 / rate):
            raise MediaError("Audio/video stream lengths differ substantially. Align their lengths before import.")
        run(["ffmpeg", "-v", "error", "-nostdin", "-xerror", "-i", str(path), "-map", "0:a:0", "-vn", "-f", "null", "-"])
    else:
        warnings.append("This video has no audio. Silence analysis will return no suggestions.")
    return Metadata(duration_ticks=count, rate=str(rate), has_video=True, has_audio=audio is not None,
                    video_codec=video["codec_name"], width=video["width"], height=video["height"],
                    audio_codec=audio["codec_name"] if audio else None,
                    sample_rate=int(audio["sample_rate"]) if audio else None,
                    channels=int(audio["channels"]) if audio else None,
                    channel_layout=audio.get("channel_layout") if audio else None, warnings=warnings)
