"""Color Agent (core): exposure normalisation + tasteful looks + optional LUT.

Order follows the spec: exposure/white balance → (camera match: Pro) →
skin-safe contrast/saturation → optional creative LUT.
"""

from __future__ import annotations

import math
import re
import shutil
from pathlib import Path

from .ff import analyze_filter

LOOKS: dict[str, str] = {
    "none": "",
    "natural": "eq=contrast=1.03:saturation=1.06",
    "warm": "colorbalance=rs=0.035:bs=-0.035:rm=0.025:bm=-0.025,eq=contrast=1.03:saturation=1.05",
    "cool": "colorbalance=rs=-0.03:bs=0.035:rm=-0.02:bm=0.025,eq=contrast=1.04",
    "punchy": "eq=contrast=1.09:saturation=1.14,unsharp=5:5:0.35",
    "film": "curves=preset=medium_contrast,eq=saturation=0.92,colorbalance=rh=0.02:bh=-0.02",
}


def measure_luma(path: str, duration: float, samples: int = 24) -> float | None:
    """Mean luma (0..1) sampled across the clip."""
    if duration <= 0:
        return None
    step = max(duration / samples, 0.5)
    log = analyze_filter(path, vf=f"fps=1/{step:.3f},scale=320:-2,signalstats,metadata=print",
                         extra=["-frames:v", str(samples)])
    vals = [float(x) for x in re.findall(r"lavfi\.signalstats\.YAVG=([\d.]+)", log)]
    if not vals:
        return None
    mean = sum(vals) / len(vals)
    return min(1.0, max(0.0, (mean - 16) / 219))


def exposure_filter(mean_luma: float | None, target: float = 0.46) -> tuple[str, dict]:
    if mean_luma is None or mean_luma <= 0.02 or mean_luma >= 0.98:
        return "", {"exposure": "skipped (no luma measurement)"}
    gamma = math.log(mean_luma) / math.log(target)
    gamma = min(1.25, max(0.82, gamma))
    if abs(gamma - 1) < 0.03:
        return "", {"exposure": f"ok (mean luma {mean_luma:.2f})"}
    return f"eq=gamma={gamma:.3f}", {"exposure": f"gamma {gamma:.2f} (mean luma {mean_luma:.2f})"}


def color_chain(preset: str, lut: str | None, workdir: Path, mean_luma: float | None) -> tuple[str, dict]:
    parts: list[str] = []
    info: dict = {"look": preset}
    if preset != "none":
        f, meta = exposure_filter(mean_luma)
        info.update(meta)
        if f:
            parts.append(f)
    look = LOOKS.get(preset, LOOKS["natural"])
    if look:
        parts.append(look)
    if lut:
        src = Path(lut)
        if not src.exists():
            raise FileNotFoundError(f"LUT not found: {lut}")
        dst = workdir / f"look{src.suffix.lower()}"
        shutil.copyfile(src, dst)
        parts.append(f"lut3d=file='{dst.name}'")
        info["lut"] = src.name
    return ",".join(parts), info
