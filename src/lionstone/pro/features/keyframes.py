"""Keyframe tracks → FFmpeg expressions.

A track is a list of ``{"t": <seconds from effect start>, "v": <value>, "ease": <name>}``.
Times are stored in seconds and converted to frames only at render time
(``to_frames``), so a project survives FPS changes. NaN/∞ and unsorted or
duplicate times are rejected.
"""

from __future__ import annotations

import math

from .easing import NAMES, _f, ease, expr


class KeyframeError(ValueError):
    pass


def validate_track(name: str, track) -> list[dict]:
    if not isinstance(track, list) or len(track) < 1:
        raise KeyframeError(f"{name}: a keyframe track needs at least one keyframe")
    out, last = [], -math.inf
    for i, k in enumerate(track):
        try:
            t, v = float(k["t"]), float(k["v"])
        except (KeyError, TypeError, ValueError) as e:
            raise KeyframeError(f"{name}[{i}]: keyframes need numeric 't' and 'v'") from e
        if any(math.isnan(x) or math.isinf(x) for x in (t, v)):
            raise KeyframeError(f"{name}[{i}]: NaN / infinite values are not allowed")
        if t < 0 or t <= last:
            raise KeyframeError(f"{name}[{i}]: times must be ≥0 and strictly increasing")
        e = k.get("ease", "ease-in-out")
        if e not in NAMES:
            raise KeyframeError(f"{name}[{i}]: unknown easing {e!r}")
        out.append({"t": t, "v": v, "ease": e})
        last = t
    return out


def to_frames(seconds: float, fps: float) -> int:
    if fps <= 0:
        raise KeyframeError("fps must be > 0")
    return int(round(seconds * fps))


def frames_to_seconds(frames: int, fps: float) -> float:
    return frames / fps


def value_at(track: list[dict], t: float) -> float:
    """Python evaluation (tests / preview curves)."""
    if t <= track[0]["t"]:
        return track[0]["v"]
    for a, b in zip(track, track[1:]):
        if t <= b["t"]:
            p = (t - a["t"]) / (b["t"] - a["t"])
            return a["v"] + (b["v"] - a["v"]) * ease(b["ease"], p)
    return track[-1]["v"]


def expression(track: list[dict], t0: float, var: str = "t") -> str:
    """FFmpeg expression of the track, with keyframe times relative to output time t0."""
    k = track
    if len(k) == 1:
        return _f(k[0]["v"])
    e = _f(k[-1]["v"])
    for a, b in reversed(list(zip(k, k[1:]))):
        ta, tb = t0 + a["t"], t0 + b["t"]
        p = f"min(1,max(0,({var}-{_f(ta)})/{_f(tb - ta)}))"
        seg = f"{_f(a['v'])}+({_f(b['v'] - a['v'])})*{expr(b['ease'], p)}"
        e = f"if(lt({var},{_f(tb)}),{seg},{e})"
    return f"if(lt({var},{_f(t0 + k[0]['t'])}),{_f(k[0]['v'])},{e})"
