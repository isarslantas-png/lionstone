"""Windows-safe file paths inside FFmpeg filter options."""

from __future__ import annotations

import re
from pathlib import Path

try:  # core >= 0.1.x with Windows fixes
    from lionstone.effects.ffmpeg_fx import filter_path
except ImportError:  # older core

    def filter_path(path: str | Path) -> str:
        """Unquoted option value: escapes ``\\ ' :`` then ``\\ ' [ ] , ;`` (FFmpeg unescapes twice)."""
        s = re.sub(r"([\\':])", r"\\\1", Path(path).as_posix())
        return re.sub(r"([\\'\[\],;])", r"\\\1", s)

__all__ = ["filter_path"]
