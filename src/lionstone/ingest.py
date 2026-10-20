"""Media Ingestion Agent — validate inputs and extract metadata.

Never modifies the source file. Flags conditions that silently break edits
later: variable frame rate, missing audio, odd sample rates, unreadable files.
"""

from __future__ import annotations

from pathlib import Path

from .ff import ffprobe_json, parse_rate, require_ffmpeg
from .models import MediaInfo, StreamInfo


def probe(path: str | Path) -> MediaInfo:
    require_ffmpeg()
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    data = ffprobe_json(p)
    fmt = data.get("format", {})
    streams: list[StreamInfo] = []
    timecode = (fmt.get("tags") or {}).get("timecode")
    for s in data.get("streams", []):
        kind = s.get("codec_type")
        if kind not in ("video", "audio"):
            continue
        if kind == "video" and (s.get("disposition") or {}).get("attached_pic"):
            continue  # cover art, not a real video stream
        timecode = timecode or (s.get("tags") or {}).get("timecode")
        streams.append(StreamInfo(
            index=int(s.get("index", 0)),
            kind=kind,
            codec=s.get("codec_name", "?"),
            duration=float(s["duration"]) if s.get("duration") not in (None, "N/A") else None,
            width=s.get("width"),
            height=s.get("height"),
            fps=parse_rate(s.get("r_frame_rate")),
            avg_fps=parse_rate(s.get("avg_frame_rate")),
            sample_rate=int(s["sample_rate"]) if s.get("sample_rate") else None,
            channels=s.get("channels"),
        ))
    duration = float(fmt.get("duration") or 0.0)
    info = MediaInfo(path=str(p), duration=duration, format_name=fmt.get("format_name", "?"),
                     streams=streams, timecode=timecode)
    info.warnings = validate(info)
    return info


def validate(info: MediaInfo) -> list[str]:
    w: list[str] = []
    if info.duration <= 0:
        w.append("critical: container reports zero duration — file may be truncated or corrupt")
    if not info.audio:
        w.append("critical: no audio stream — speech editing needs audio")
    v = info.video
    if v and v.fps and v.avg_fps and abs(v.fps - v.avg_fps) / v.fps > 0.01:
        w.append(
            f"warning: variable frame rate detected (r={v.fps:.3f}, avg={v.avg_fps:.3f}). "
            "Lionstone renders to constant frame rate; sync is re-checked in QA."
        )
    a = info.audio
    if a and a.sample_rate and a.sample_rate not in (44100, 48000):
        w.append(f"warning: unusual sample rate {a.sample_rate} Hz — will resample to 48 kHz")
    if v and a and v.duration and a.duration and abs(v.duration - a.duration) > 0.25:
        w.append(
            f"warning: video ({v.duration:.2f}s) and audio ({a.duration:.2f}s) lengths differ"
        )
    return w


def describe(info: MediaInfo) -> str:
    lines = [f"{Path(info.path).name}  ·  {info.duration:.2f}s  ·  {info.format_name}"]
    for s in info.streams:
        if s.kind == "video":
            lines.append(f"  video  {s.codec} {s.width}x{s.height} @ {s.avg_fps or s.fps:.3f} fps")
        else:
            lines.append(f"  audio  {s.codec} {s.sample_rate} Hz × {s.channels} ch")
    if info.timecode:
        lines.append(f"  timecode {info.timecode}")
    lines += [f"  ! {w}" for w in info.warnings]
    return "\n".join(lines)
