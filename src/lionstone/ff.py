"""Thin, dependency-free wrappers around FFmpeg / FFprobe."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise FFmpegError(
                f"`{tool}` was not found on PATH. Install FFmpeg 5+ "
                "(macOS: brew install ffmpeg · Ubuntu: apt install ffmpeg · "
                "Windows: winget install ffmpeg)."
            )


def run(args: list[str], *, check: bool = True, capture: bool = True,
        cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(args, capture_output=capture, text=True, errors="replace", cwd=cwd)
    if check and proc.returncode != 0:
        tail = (proc.stderr or "")[-2000:]
        raise FFmpegError(f"command failed ({proc.returncode}): {' '.join(args[:6])} …\n{tail}")
    return proc


_FILTERS: set[str] | None = None


def filters() -> set[str]:
    """Names of the filters this FFmpeg build provides (cached).

    Some builds (e.g. recent Homebrew bottles) ship without libfreetype/libass,
    so `drawtext` / `subtitles` may be missing. Callers degrade gracefully.
    """
    global _FILTERS
    if _FILTERS is None:
        out = run(["ffmpeg", "-hide_banner", "-filters"], check=False).stdout or ""
        _FILTERS = {parts[1] for line in out.splitlines()
                    if len(parts := line.split()) > 2 and "->" in parts[2]}
    return _FILTERS


def has_filter(name: str) -> bool:
    return name in filters()


def ffprobe_json(path: str | Path) -> dict:
    proc = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    return json.loads(proc.stdout or "{}")


def analyze_filter(path: str | Path, *, af: str | None = None, vf: str | None = None,
                   extra: list[str] | None = None) -> str:
    """Run a detection filter over a file and return FFmpeg's stderr log."""
    args = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path)]
    if af:
        args += ["-af", af]
    else:
        args += ["-an"] if vf else []
    if vf:
        args += ["-vf", vf]
    else:
        args += ["-vn"] if af else []
    args += (extra or []) + ["-f", "null", "-"]
    return run(args, check=False).stderr or ""


def parse_rate(rate: str | None) -> float | None:
    if not rate or rate in ("0/0", "N/A"):
        return None
    if "/" in rate:
        n, d = rate.split("/", 1)
        try:
            return float(n) / float(d) if float(d) else None
        except ValueError:
            return None
    try:
        return float(rate)
    except ValueError:
        return None


_FLOAT = r"(-?\d+(?:\.\d+)?)"


def parse_silences(log: str, duration: float) -> list[tuple[float, float]]:
    starts = [float(x) for x in re.findall(rf"silence_start: {_FLOAT}", log)]
    ends = [float(x) for x in re.findall(rf"silence_end: {_FLOAT}", log)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else duration
        out.append((max(0.0, s), min(duration, e)))
    return out


def parse_loudness(log: str) -> dict[str, float | None]:
    """Parse the summary block of the ebur128 filter (peak=true)."""
    summary = log.split("Summary:")[-1] if "Summary:" in log else log

    def grab(label: str) -> float | None:
        m = re.search(rf"{label}:\s+{_FLOAT}", summary)
        return float(m.group(1)) if m else None

    return {
        "integrated_lufs": grab("I"),
        "lra": grab("LRA"),
        "true_peak_dbtp": grab("Peak"),
    }


def font_path(preferred: str | None = None) -> str | None:
    """Resolve a font file that supports Turkish (and Latin-extended) glyphs."""
    if preferred and Path(preferred).exists():
        return preferred
    if shutil.which("fc-match"):
        query = preferred or "DejaVu Sans:style=Bold"
        proc = run(["fc-match", "-f", "%{file}", query], check=False)
        if proc.returncode == 0 and proc.stdout and Path(proc.stdout).exists():
            return proc.stdout
    for cand in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        if Path(cand).exists():
            return cand
    return None


def escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg's drawtext `text=` option."""
    return (
        text.replace("\\", "\\\\\\\\")
        .replace("'", "\u2019")
        .replace(":", "\\:")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def escape_filter_path(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
