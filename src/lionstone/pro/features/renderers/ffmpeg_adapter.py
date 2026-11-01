"""FFmpeg render adapter for effects, transitions, looks and motion.

Adapters are independent of the catalog: a builder receives validated
parameters and *output-time* windows and returns a filtergraph fragment that
consumes the current video stream and ends with an unlabeled filter, so
fragments chain. Preview and final export call the very same builders.

Pipelines
* ``filter``    — per-window filters (``enable=`` / time expressions)
* ``transform`` — contributions to one merged scale/crop/rotate pass
                  (zoom, pan, rotation; motion presets, punch-ins, zoom/whip transitions)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..easing import _f, expr, progress


@dataclass
class RCtx:
    W: int
    H: int
    fps: float
    total: float  # output duration (seconds)
    brand: dict = field(default_factory=dict)
    _n: int = 0

    def L(self, prefix: str = "x") -> str:
        self._n += 1
        return f"ls{prefix}{self._n}"

    @property
    def k(self) -> float:  # resolution scale vs 1080p
        return min(self.W, self.H) / 1080


Win = tuple[float, float]


def en(wins: list[Win]) -> str:
    return "+".join(f"between(t,{_f(a)},{_f(b)})" for a, b in wins) or "0"


def env(wins: list[Win], att: float, rel: float, var: str = "t") -> str:
    """Trapezoid envelope 0→1→0 inside each window (for ramped effects).

    `var` is the time variable: `t` in most filters, `T` inside blend expressions.
    """
    terms = []
    for a, b in wins:
        at = min(att, (b - a) / 2) or 1e-3
        rt = min(rel, (b - a) / 2) or 1e-3
        terms.append(f"if(between({var},{_f(a)},{_f(b)}),min(1,min(({var}-{_f(a)})/{_f(at)},"
                     f"({_f(b)}-{var})/{_f(rt)})),0)")
    return "(" + "+".join(terms) + ")" if terms else "0"


def tri(joins: list[Win], var: str = "t") -> str:
    """Triangle 0→1→0 centred on each cut (tj, duration)."""
    return "+".join(f"if(between({var},{_f(tj - d / 2)},{_f(tj + d / 2)}),"
                    f"1-abs({var}-{_f(tj)})/{_f(d / 2)},0)" for tj, d in joins) or "0"


def ensure_even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


# ======================================================================= effects
def soft_bloom(p, wins, c):
    a, b = c.L("a"), c.L("b")
    sig = max(1.0, p["radius"] * c.k)
    return (f"format=gbrp,split=2[{a}][{b}];[{b}]gblur=sigma={_f(sig)}[{b}g];"
            f"[{a}][{b}g]blend=all_mode=screen:all_opacity={_f(p['intensity'] * 0.55)}:"
            f"enable='{en(wins)}'")


def light_leak(p, wins, c):
    a, g = c.L("a"), c.L("g")
    warm = p["color"].lstrip("#")
    return (f"null[{a}];gradients=s={c.W}x{c.H}:c0=0x{warm}:c1=0x000000:c2=0xFFD9A0:"
            f"c3=0x000000:n=4:speed={_f(0.01 + 0.03 * p['motion'])}:r={_f(c.fps)}:"
            f"d={_f(c.total + 1)},format=gbrp[{g}];[{a}]format=gbrp[{a}f];"
            f"[{a}f][{g}]blend=all_mode=screen:all_opacity={_f(p['intensity'] * 0.45)}:"
            f"shortest=1:enable='{en(wins)}'")


def directional_blur(p, wins, c):
    return (f"dblur=angle={_f(p['angle'])}:radius={_f(max(1, p['amount'] * 12 * c.k))}:"
            f"enable='{en(wins)}'")


def focus_pull(p, wins, c):
    """Rack focus from soft to sharp (or reverse) in 5 stepped stages."""
    parts = []
    steps = 5
    for a, b in wins:
        d = (b - a) / steps
        for i in range(steps):
            frac = (steps - i) / steps if p["direction"] == "in" else (i + 1) / steps
            sig = max(0.5, p["amount"] * 14 * c.k * frac)
            parts.append(f"gblur=sigma={_f(sig)}:enable='between(t,{_f(a + i * d)},"
                         f"{_f(a + (i + 1) * d)})'")
    return ",".join(parts) or "null"


def motion_blur(p, wins, c):
    n = 3 if p["amount"] < 0.5 else 5
    w = "1 2 1" if n == 3 else "1 2 3 2 1"
    return f"tmix=frames={n}:weights='{w}':enable='{en(wins)}'"


def subtle_glitch(p, wins, c):
    """Short RGB-split bursts with noise; spaced, never strobing."""
    parts = []
    px = max(2, int(p["amount"] * 14 * c.k))
    for a, b in wins:
        t, i = a, 0
        while t < b:
            dur = 2 / c.fps * (1 + (i % 2))
            parts.append(f"rgbashift=rh={px if i % 2 else -px}:bh={-px if i % 2 else px}:"
                         f"enable='between(t,{_f(t)},{_f(min(b, t + dur))})'")
            t += max(0.35, 1.2 - p["amount"])  # ≤ ~3 bursts/s (photosensitivity)
            i += 1
    parts.append(f"noise=alls={int(6 + 10 * p['amount'])}:allf=t:enable='{en(wins)}'")
    return ",".join(parts)


def chromatic_shift(p, wins, c):
    px = max(1, int(p["amount"] * 8 * c.k))
    return f"rgbashift=rh={px}:bh={-px}:enable='{en(wins)}'"


def film_grain(p, wins, c):
    return f"noise=alls={int(4 + 26 * p['intensity'])}:allf=t+u:enable='{en(wins)}'"


def halation(p, wins, c):
    a, b = c.L("a"), c.L("b")
    return (f"format=gbrp,split=2[{a}][{b}];[{b}]colorchannelmixer=rr=1:gg=0.25:bb=0.1,"
            f"gblur=sigma={_f(10 * c.k + 20 * p['intensity'] * c.k)}[{b}g];"
            f"[{a}][{b}g]blend=all_mode=screen:all_opacity={_f(0.35 * p['intensity'])}:"
            f"enable='{en(wins)}'")


def vhs_texture(p, wins, c):
    e = en(wins)
    i = p["intensity"]
    return (f"chromashift=cbh={int(2 + 6 * i)}:crh={-int(2 + 6 * i)}:enable='{e}',"
            f"eq=saturation={_f(1 - 0.25 * i)}:contrast={_f(1 - 0.1 * i)}:enable='{e}',"
            f"noise=alls={int(8 + 18 * i)}:allf=t:enable='{e}',"
            f"boxblur=1:1:enable='{e}'")


def soft_vignette(p, wins, c):
    import math
    ang = math.pi / 5 + (math.pi / 3.2 - math.pi / 5) * p["intensity"]
    return f"vignette=angle={_f(ang)}:enable='{en(wins)}'"


def film_burn(p, wins, c):
    a, g = c.L("a"), c.L("g")
    return (f"null[{a}];gradients=s={c.W}x{c.H}:c0=0xFF7A1A:c1=0x000000:c2=0xFFC46B:"
            f"c3=0x000000:n=4:speed=0.05:r={_f(c.fps)}:d={_f(c.total + 1)},format=gbrp[{g}];"
            f"[{a}]format=gbrp[{a}f];[{a}f][{g}]blend=all_mode=screen:"
            f"all_expr='min(255,A+B*{_f(0.6 * p['intensity'])}*{env(wins, 0.25, 0.4, 'T')})':"
            f"shortest=1")


def letterbox(p, wins, c):
    ratio = p["ratio"]
    bar = max(0, int((c.H - c.W / ratio) / 2))
    if bar <= 0:
        return "null"
    e = en(wins)
    return (f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill:enable='{e}',"
            f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill:enable='{e}'")


def beat_flash(p, wins, c):
    times = list(p.get("times") or [])
    if not times:
        for a, b in wins:
            t = a
            while t < b:
                times.append(t)
                t += max(0.34, p["every"])
    times = sorted(times)
    # photosensitivity guard: never more than 3 flashes per second
    kept: list[float] = []
    for t in times:
        if not kept or t - kept[-1] >= 0.34:
            kept.append(t)
    d = 3 / c.fps
    terms = "+".join(f"if(between(t,{_f(t)},{_f(t + d)}),1-(t-{_f(t)})/{_f(d)},0)" for t in kept)
    return f"eq=brightness='{_f(0.35 * p['intensity'])}*({terms or 0})':eval=frame"


def haze(p, wins, c):
    a, b = c.L("a"), c.L("b")
    i = p["intensity"]
    return (f"format=gbrp,split=2[{a}][{b}];[{b}]gblur=sigma={_f(25 * c.k)},"
            f"eq=brightness={_f(0.06 * i)}:contrast={_f(1 - 0.25 * i)}[{b}g];"
            f"[{a}][{b}g]blend=all_mode=normal:all_opacity={_f(0.3 * i)}:enable='{en(wins)}'")


def exposure_balance(p, wins, c):
    return f"eq=gamma={_f(1 + p['stops'] * 0.35)}:enable='{en(wins)}'"


def noise_reduction(p, wins, c):
    s = 2 + 6 * p["strength"]
    return f"hqdn3d={_f(s)}:{_f(s * 0.75)}:{_f(s * 1.5)}:{_f(s * 1.1)}:enable='{en(wins)}'"


def stabilization(p, wins, c):
    # deshake has no timeline support → whole-stream; documented as `partial`
    return f"deshake=rx={int(16 + 32 * p['strength'])}:ry={int(16 + 32 * p['strength'])}:edge=mirror"


# ======================================================================= looks
LOOK_RECIPES: dict[str, dict] = {
    "natural-neutral": {"contrast": 1.03, "saturation": 1.04},
    "clean-daylight": {"gamma": 1.04, "contrast": 1.04, "temp": 6900, "vibrance": 0.1},
    "warm-cinema": {"contrast": 1.08, "saturation": 0.95, "temp": 5200, "shadows": 0.02,
                    "highlights": -0.03, "vignette": 0.3},
    "cool-cinema": {"contrast": 1.08, "saturation": 0.92, "temp": 8200, "shadows": 0.015,
                    "vignette": 0.3},
    "muted-film": {"contrast": 0.96, "saturation": 0.78, "fade": 0.05, "grain": 0.25},
    "soft-contrast": {"contrast": 0.95, "fade": 0.03, "saturation": 1.0},
    "matte-editorial": {"contrast": 1.02, "fade": 0.07, "saturation": 0.9, "temp": 6200},
    "true-to-life": {"contrast": 1.01, "saturation": 1.0},
    "low-saturation": {"saturation": 0.75, "contrast": 1.02},
    "golden-hour": {"temp": 4600, "saturation": 1.06, "gamma": 1.03, "highlights": -0.02},
    "warm-interior": {"temp": 5000, "gamma": 1.05, "shadows": 0.02},
    "steel-blue": {"temp": 9500, "saturation": 0.85, "contrast": 1.06},
    "cool-shadow": {"temp": 7600, "shadows": -0.01, "contrast": 1.05, "tint": -0.02},
    "analog-soft": {"fade": 0.05, "saturation": 0.88, "temp": 5800, "grain": 0.3},
    "vintage-fade": {"fade": 0.09, "saturation": 0.7, "temp": 5400, "contrast": 0.93,
                     "grain": 0.35, "vignette": 0.25},
    "night-detail": {"gamma": 1.12, "contrast": 1.04, "shadows": 0.03, "denoise": 0.4},
    "neon-balance": {"vibrance": 0.35, "contrast": 1.06, "temp": 7600},
    "classic-bw": {"mono": True, "contrast": 1.06},
    "high-contrast-mono": {"mono": True, "contrast": 1.22, "fade": -0.02},
    "product-neutral": {"contrast": 1.04, "saturation": 1.0, "sharpen": 0.3},
    "detail-pop": {"contrast": 1.08, "vibrance": 0.2, "sharpen": 0.6},
    "bright-interior": {"gamma": 1.1, "temp": 6200, "shadows": 0.03, "vibrance": 0.1},
    "window-balance": {"highlights": -0.06, "shadows": 0.03, "contrast": 0.98},
    "natural-exterior": {"vibrance": 0.18, "contrast": 1.04, "temp": 6300},
    "punchy-social": {"contrast": 1.1, "vibrance": 0.3, "saturation": 1.08, "sharpen": 0.3},
    "soft-skin-safe": {"contrast": 1.0, "vibrance": 0.12, "temp": 6100, "highlights": -0.02},
}


def look_chain(recipe: dict, intensity: float, e: str, c: RCtx) -> str:
    """Compose a look from bounded primitives; intensity scales every delta."""
    k = intensity
    parts = []
    g = 1 + (recipe.get("gamma", 1) - 1) * k
    con = 1 + (recipe.get("contrast", 1) - 1) * k
    sat = 1 + (recipe.get("saturation", 1) - 1) * k
    sat = min(sat, 1.25)  # skin-tone guard
    if recipe.get("mono"):
        parts.append(f"hue=s=0:enable='{e}'" if k >= 0.999 else
                     f"eq=saturation={_f(1 - k)}:enable='{e}'")
    if any(abs(x - 1) > 1e-3 for x in (g, con, sat)):
        parts.append(f"eq=gamma={_f(g)}:contrast={_f(con)}:saturation={_f(sat)}:enable='{e}'")
    if "temp" in recipe:
        parts.append(f"colortemperature=temperature={int(recipe['temp'])}:"
                     f"mix={_f(min(1, 0.6 * k))}:pl=1:enable='{e}'")
    if recipe.get("tint"):
        parts.append(f"colorbalance=gm={_f(recipe['tint'] * k)}:enable='{e}'")
    lift = recipe.get("shadows", 0) * k + recipe.get("fade", 0) * k
    roll = recipe.get("highlights", 0) * k
    if abs(lift) > 1e-4 or abs(roll) > 1e-4:
        b0 = max(0.0, min(0.2, lift))
        w1 = max(0.8, min(1.0, 1 + roll))
        q1 = max(0.0, min(0.5, 0.25 + lift * 0.8))
        q3 = max(0.5, min(1.0, 0.75 + roll * 0.8))
        parts.append(f"curves=all='0/{_f(b0)} 0.25/{_f(q1)} 0.75/{_f(q3)} 1/{_f(w1)}':"
                     f"enable='{e}'")
    if recipe.get("vibrance"):
        parts.append(f"vibrance=intensity={_f(recipe['vibrance'] * k)}:enable='{e}'")
    if recipe.get("denoise"):
        s = 2 + 4 * recipe["denoise"] * k
        parts.append(f"hqdn3d={_f(s)}:{_f(s * 0.75)}:{_f(s * 1.5)}:{_f(s)}:enable='{e}'")
    if recipe.get("sharpen"):
        parts.append(f"unsharp=5:5:{_f(0.8 * recipe['sharpen'] * k)}:enable='{e}'")
    if recipe.get("vignette"):
        import math
        parts.append(f"vignette=angle={_f(math.pi / 5 + 0.25 * recipe['vignette'] * k)}:"
                     f"enable='{e}'")
    if recipe.get("grain"):
        parts.append(f"noise=alls={int(18 * recipe['grain'] * k)}:allf=t:enable='{e}'")
    return ",".join(parts) or "null"


def make_look(name: str) -> Callable:
    def build(p, wins, c):
        return look_chain(LOOK_RECIPES[name], p["intensity"], en(wins), c)
    return build


def color_controls(p, wins, c):
    e = en(wins)
    parts = [f"eq=brightness={_f(p['brightness'])}:contrast={_f(p['contrast'])}:"
             f"saturation={_f(p['saturation'])}:gamma={_f(2 ** (p['exposure'] * 0.5))}:"
             f"enable='{e}'"]
    if abs(p["temperature"] - 6500) > 50:
        parts.append(f"colortemperature=temperature={int(p['temperature'])}:mix=0.6:pl=1:"
                     f"enable='{e}'")
    if abs(p["tint"]) > 1e-3:
        parts.append(f"colorbalance=gm={_f(p['tint'])}:enable='{e}'")
    b0, w1 = p["blacks"], 1 + p["whites"]
    q1 = 0.25 + p["shadows"] * 0.2
    q3 = 0.75 + p["highlights"] * 0.2
    if any(abs(x) > 1e-3 for x in (p["blacks"], p["whites"], p["shadows"], p["highlights"])):
        parts.append(f"curves=all='0/{_f(max(0, b0))} 0.25/{_f(q1)} 0.75/{_f(q3)} "
                     f"1/{_f(min(1, w1))}':enable='{e}'")
    if p["vibrance"]:
        parts.append(f"vibrance=intensity={_f(p['vibrance'])}:enable='{e}'")
    if p["sharpen"]:
        parts.append(f"unsharp=5:5:{_f(p['sharpen'])}:enable='{e}'")
    if p["vignette"]:
        import math
        parts.append(f"vignette=angle={_f(math.pi / 5 + 0.3 * p['vignette'])}:enable='{e}'")
    if p["grain"]:
        parts.append(f"noise=alls={int(25 * p['grain'])}:allf=t:enable='{e}'")
    return ",".join(parts)


def lut_look(p, wins, c):
    from pathlib import Path
    path = Path(p["file"])
    if not path.exists():
        raise FileNotFoundError(f"LUT not found: {path}")
    if not p["license_source"].strip():
        raise PermissionError("record where the LUT came from (license_source) before using it")
    from ..paths import filter_path
    return (f"lut3d=file={filter_path(path.resolve())}:interp=tetrahedral:"
            f"enable='{en(wins)}'")


# ======================================================================= transitions
# Transitions act around a cut at output time tj; d = total duration (s), split
# evenly unless one side is too short (compile clamps to neighbour lengths).
def dip(color: str):
    sign = -1 if color == "black" else 1

    def build(p, joins, c):
        amt = tri(joins)
        return f"eq=brightness='{sign}*({amt})':contrast='1-0.6*({amt})':eval=frame"
    return build


def fade_through_color(p, joins, c):
    a, col = c.L("a"), c.L("c")
    terms = tri(joins, "T")
    hexc = p["color"].lstrip("#")
    return (f"null[{a}];color=c=0x{hexc}:s={c.W}x{c.H}:r={_f(c.fps)}:d={_f(c.total + 1)},"
            f"format=gbrp[{col}];[{a}]format=gbrp[{a}f];[{a}f][{col}]blend="
            f"all_expr='A*(1-({terms}))+B*({terms})':shortest=1")


def flash_overlay(kind: str):
    def build(p, joins, c):
        a, g = c.L("a"), c.L("g")
        c0, c2 = ("0xFFB36B", "0xFFE2B0") if kind == "leak" else ("0xFF6A00", "0xFFC46B")
        terms = tri(joins, "T")
        return (f"null[{a}];gradients=s={c.W}x{c.H}:c0={c0}:c1=0x000000:c2={c2}:c3=0x000000:"
                f"n=4:speed=0.04:r={_f(c.fps)}:d={_f(c.total + 1)},format=gbrp[{g}];"
                f"[{a}]format=gbrp[{a}f];[{a}f][{g}]blend=all_mode=screen:"
                f"all_expr='min(255,A+B*{_f(0.9 * p['intensity'])}*({terms}))':shortest=1")
    return build


def blur_cut(p, joins, c):
    parts = []
    for tj, d in joins:
        h = d / 2
        for i, frac in enumerate((0.35, 0.7, 1.0, 0.7, 0.35)):
            a = tj - h + i * d / 5
            sig = max(0.5, 12 * c.k * frac * p["intensity"])
            parts.append(f"gblur=sigma={_f(sig)}:enable='between(t,{_f(a)},{_f(a + d / 5)})'")
    return ",".join(parts) or "null"


def glitch_cut(p, joins, c):
    parts = []
    px = max(2, int(10 * c.k * p["intensity"]))
    for tj, d in joins:
        parts.append(f"rgbashift=rh={px}:bh={-px}:enable='between(t,{_f(tj - d / 2)},{_f(tj)})'")
        parts.append(f"rgbashift=rh={-px}:gh={px}:enable='between(t,{_f(tj)},{_f(tj + d / 2)})'")
        parts.append(f"noise=alls=14:allf=t:enable='between(t,{_f(tj - d / 3)},{_f(tj + d / 3)})'")
    return ",".join(parts) or "null"


def rgb_shift_cut(p, joins, c):
    px = max(2, int(14 * c.k * p["intensity"]))
    return ",".join(f"rgbashift=rh={px}:gh=0:bh={-px}:enable='between(t,{_f(tj - d / 2)},"
                    f"{_f(tj + d / 2)})'" for tj, d in joins) or "null"


def whip_blur(p, joins, c):
    return ",".join(f"dblur=angle=0:radius={_f(30 * c.k * p['intensity'])}:"
                    f"enable='between(t,{_f(tj - d / 2)},{_f(tj + d / 2)})'" for tj, d in joins) \
        or "null"


# ======================================================================= transform
@dataclass
class Transform:
    """One contribution to the merged transform pass, active on [a, b]."""
    a: float
    b: float
    zoom: str = "1"
    panx: str = "0"
    pany: str = "0"
    rot: str = "0"  # degrees


def zoom_window(p, wins, c, peak_key="amount", scale=0.18, ease_name="ease-in-out",
                hold=False) -> list[Transform]:
    out = []
    for a, b in wins:
        pr = progress(a, b - a)
        z = f"1+{_f(scale * p[peak_key])}*{expr(ease_name, pr)}"
        if hold:
            z = f"1+{_f(scale * p[peak_key])}"
        out.append(Transform(a, b, zoom=z))
    return out


def punch_in(p, wins, c) -> list[Transform]:
    out = []
    for a, b in wins:
        att = min(0.12, (b - a) / 3)
        pr = progress(a, att)
        out.append(Transform(a, b, zoom=f"1+{_f(0.08 + 0.14 * p['amount'])}*{expr('ease-out', pr)}"))
    return out


def zoom_through(p, joins, c) -> list[Transform]:
    out = []
    amt = 0.12 + 0.25 * p["intensity"]
    for tj, d in joins:
        h = d / 2
        out.append(Transform(tj - h, tj, zoom=f"1+{_f(amt)}*{expr('ease-in', progress(tj - h, h))}"))
        out.append(Transform(tj, tj + h,
                             zoom=f"1+{_f(amt)}*(1-{expr('ease-out', progress(tj, h))})"))
    return out


def whip_pan(p, joins, c) -> list[Transform]:
    out = []
    for tj, d in joins:
        h = d / 2
        s = 1 if p["direction"] == "left" else -1
        out.append(Transform(tj - h, tj, zoom="1.18",
                             panx=f"{s}*{expr('ease-in', progress(tj - h, h))}"))
        out.append(Transform(tj, tj + h, zoom="1.18",
                             panx=f"{-s}*(1-{expr('ease-out', progress(tj, h))})"))
    return out


def keyframed(tracks: dict[str, list], wins: list[Win]) -> list[Transform]:
    from ..keyframes import expression
    out = []
    for a, b in wins:
        t = Transform(a, b)
        for key in ("zoom", "panx", "pany", "rot"):
            if tracks.get(key):
                setattr(t, key, expression(tracks[key], a))
        out.append(t)
    return out


def merge_transforms(ts: list[Transform], c: RCtx) -> str:
    """Single scale/crop(/rotate) pass; identity outside every window."""
    if not ts:
        return ""
    ts = sorted(ts, key=lambda t: t.a)

    def chain(attr: str, default: str) -> str:
        e = default
        for t in reversed(ts):
            v = getattr(t, attr)
            if v != default:
                e = f"if(between(t,{_f(t.a)},{_f(t.b)}),{v},{e})"
        return e

    Z = f"max(1,{chain('zoom', '1')})"
    PX, PY, R = chain("panx", "0"), chain("pany", "0"), chain("rot", "0")
    W, H = c.W, c.H
    frag = (f"scale=w='trunc({W}*{Z}/2)*2':h='trunc({H}*{Z}/2)*2':eval=frame,"
            f"crop={W}:{H}:x='(in_w-out_w)/2*(1+max(-1,min(1,{PX})))':"
            f"y='(in_h-out_h)/2*(1+max(-1,min(1,{PY})))'")
    if R != "0":
        frag += f",rotate=a='({R})*PI/180':fillcolor=black"
    return frag


# ======================================================================= registry
FILTERS: dict[str, Callable] = {
    "lionstone.soft-bloom": soft_bloom,
    "lionstone.light-leak": light_leak,
    "lionstone.directional-blur": directional_blur,
    "lionstone.focus-pull": focus_pull,
    "lionstone.motion-blur": motion_blur,
    "lionstone.subtle-glitch": subtle_glitch,
    "lionstone.chromatic-shift": chromatic_shift,
    "lionstone.film-grain": film_grain,
    "lionstone.halation": halation,
    "lionstone.vhs-texture": vhs_texture,
    "lionstone.soft-vignette": soft_vignette,
    "lionstone.film-burn": film_burn,
    "lionstone.letterbox": letterbox,
    "lionstone.beat-flash": beat_flash,
    "lionstone.haze": haze,
    "lionstone.exposure-balance": exposure_balance,
    "lionstone.noise-reduction": noise_reduction,
    "lionstone.stabilization": stabilization,
    "lionstone.color-controls": color_controls,
    "lionstone.lut": lut_look,
    **{f"lionstone.look-{n}": make_look(n) for n in LOOK_RECIPES},
}

TRANSFORMS: dict[str, Callable] = {
    "lionstone.smooth-zoom": lambda p, w, c: zoom_window(p, w, c, scale=0.15),
    "lionstone.quick-punch-in": punch_in,
    "lionstone.gentle-push-in": lambda p, w, c: zoom_window(p, w, c, scale=0.10,
                                                           ease_name="ease-in-out"),
    "lionstone.slow-pull-back": lambda p, w, c: [
        Transform(t.a, t.b, zoom=f"(2+{_f(0.10 * p['amount'])})-({t.zoom})")
        for t in zoom_window(p, w, c, scale=0.10)],
    "lionstone.ken-burns-pan": lambda p, w, c: [
        Transform(a, b, zoom=f"{_f(1.08 + 0.1 * p['amount'])}",
                  panx=f"{_f(-0.8 if p['direction'] == 'right' else 0.8)}*"
                       f"(1-2*{expr('ease-in-out', progress(a, b - a))})")
        for a, b in w],
    "lionstone.vertical-drift": lambda p, w, c: [
        Transform(a, b, zoom=f"{_f(1.06 + 0.08 * p['amount'])}",
                  pany=f"{_f(0.8 if p['direction'] == 'up' else -0.8)}*"
                       f"(1-2*{expr('linear', progress(a, b - a))})")
        for a, b in w],
    "lionstone.product-hero-reveal": lambda p, w, c: zoom_window(p, w, c, scale=0.2,
                                                                 ease_name="ease-out"),
    "lionstone.keyframe-transform": lambda p, w, c: keyframed(
        {"zoom": p.get("zoom"), "panx": p.get("panx"), "pany": p.get("pany"),
         "rot": p.get("rotation")}, w),
}

JOIN_FILTERS: dict[str, Callable] = {
    "lionstone.dip-to-black": dip("black"),
    "lionstone.dip-to-white": dip("white"),
    "lionstone.fade-through-color": fade_through_color,
    "lionstone.light-leak-flash": flash_overlay("leak"),
    "lionstone.film-burn-flash": flash_overlay("burn"),
    "lionstone.blur-cut": blur_cut,
    "lionstone.glitch-cut": glitch_cut,
    "lionstone.rgb-shift-cut": rgb_shift_cut,
    "lionstone.whip-pan": whip_blur,
}

JOIN_TRANSFORMS: dict[str, Callable] = {
    "lionstone.zoom-through": zoom_through,
    "lionstone.whip-pan": whip_pan,
}

# extra effects that also need a filter pass alongside their transform
COMPANION_FILTERS: dict[str, Callable] = {
    "lionstone.product-hero-reveal": lambda p, w, c: soft_vignette({"intensity": 0.6}, w, c),
}


def implemented(preset_id: str) -> bool:
    return any(preset_id in reg for reg in (FILTERS, TRANSFORMS, JOIN_FILTERS, JOIN_TRANSFORMS))
