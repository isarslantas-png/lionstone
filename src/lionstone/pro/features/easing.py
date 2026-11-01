"""Easing curves — as Python functions and as FFmpeg expressions (same math).

Every curve maps p∈[0,1] → [0,1] (spring may overshoot slightly, bounded).
"""

from __future__ import annotations

import math

NAMES = ("linear", "ease-in", "ease-out", "ease-in-out", "cubic-bezier", "spring")


def _bezier_y_for_x(x: float, x1: float, y1: float, x2: float, y2: float) -> float:
    # Newton + bisection on the parametric curve, like CSS cubic-bezier()
    lo, hi, t = 0.0, 1.0, x
    for _ in range(30):
        cx = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3
        if abs(cx - x) < 1e-6:
            break
        if cx < x:
            lo = t
        else:
            hi = t
        t = (lo + hi) / 2
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3


def ease(name: str, p: float, bezier: tuple[float, float, float, float] = (0.25, 0.1, 0.25, 1.0),
         damping: float = 0.55) -> float:
    p = min(1.0, max(0.0, p))
    if name == "linear":
        return p
    if name == "ease-in":
        return p ** 3
    if name == "ease-out":
        return 1 - (1 - p) ** 3
    if name == "ease-in-out":
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if name == "cubic-bezier":
        x1, y1, x2, y2 = bezier
        if not (0 <= x1 <= 1 and 0 <= x2 <= 1):
            raise ValueError("cubic-bezier x values must be within [0, 1]")
        return _bezier_y_for_x(p, x1, y1, x2, y2)
    if name == "spring":
        z = min(0.95, max(0.2, damping))
        w = 12.0
        wd = w * math.sqrt(1 - z * z)
        v = 1 - math.exp(-z * w * p) * math.cos(wd * p)
        return min(1.15, v) if p < 1 else 1.0
    raise ValueError(f"unknown easing {name!r}; use one of {NAMES}")


def _f(x: float) -> str:
    return f"{x:.5f}".rstrip("0").rstrip(".") or "0"


def expr(name: str, p: str, bezier=(0.25, 0.1, 0.25, 1.0), damping: float = 0.55) -> str:
    """FFmpeg expression of the same curve; `p` must already be clamped to [0,1]."""
    if name == "linear":
        return f"({p})"
    if name == "ease-in":
        return f"pow({p},3)"
    if name == "ease-out":
        return f"(1-pow(1-({p}),3))"
    if name == "ease-in-out":
        return f"if(lt({p},0.5),4*pow({p},3),1-pow(-2*({p})+2,3)/2)"
    if name == "cubic-bezier":
        # piecewise-linear table, 16 segments — deterministic and exact at the knots
        n = 16
        ys = [ease("cubic-bezier", i / n, bezier) for i in range(n + 1)]
        e = _f(ys[-1])
        for i in range(n - 1, -1, -1):
            a, b = ys[i], ys[i + 1]
            e = f"if(lt({p},{_f((i + 1) / n)}),{_f(a)}+({_f(b - a)})*(({p})-{_f(i / n)})*{n},{e})"
        return e
    if name == "spring":
        z = min(0.95, max(0.2, damping))
        w = 12.0
        wd = w * math.sqrt(1 - z * z)
        return (f"if(gte({p},1),1,min(1.15,1-exp(-{_f(z * w)}*({p}))*cos({_f(wd)}*({p}))))")
    raise ValueError(f"unknown easing {name!r}")


def progress(t0: float, dur: float) -> str:
    """Clamped 0→1 progress in output time `t`."""
    return f"min(1,max(0,(t-{_f(t0)})/{_f(max(dur, 1e-3))}))"
