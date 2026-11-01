"""Reel FX pack — one-command social effects for vertical talking-head videos.

Twelve original Lionstone effects (8 Pro, 4 Studio) built only from FFmpeg
filter math: no stock overlays, no third-party assets, no fonts. Every builder
follows the adapter contract in ``ffmpeg_adapter``: it receives validated
parameters and output-time windows and returns a fragment that consumes the
current stream and ends with an unlabeled filter, so fragments chain and the
preview uses the very same code as the export.

Geometry is relative (fractions of the frame), so the same preset works on
9:16 Reels/Shorts, 1:1 and 16:9. Layout effects (Studio) swap the whole frame
inside their window only and fall back to the untouched clip outside it.

Registered into the adapter registries on import (see ``renderers/__init__``).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from ..easing import _f, expr, progress
from . import ffmpeg_adapter as fa
from .ffmpeg_adapter import en, ensure_even, env

Win = tuple[float, float]


# ----------------------------------------------------------------------- helpers
def _hex(col: str) -> str:
    return "0x" + col.lstrip("#").upper()


def _rgb(col: str) -> tuple[int, int, int]:
    h = col.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _src(c, color: str, w: int, h: int, alpha: float = 1.0) -> str:
    """Solid colour source as long as the timeline (+1 s), RGBA."""
    return (f"color=c={_hex(color)}@{_f(alpha)}:s={w}x{h}:r={_f(c.fps)}:d={_f(c.total + 1)},"
            f"format=rgba")


def _prog(wins: list[Win], ease_name: str = "linear", delay: float = 0.0,
          dur: float | None = None) -> str:
    """0→1 progress inside each window (optionally delayed / shorter), 0 outside."""
    terms = []
    for a, b in wins:
        d = (b - a - delay) if dur is None else dur
        terms.append(f"if(between(t,{_f(a)},{_f(b)}),{expr(ease_name, progress(a + delay, d))},0)")
    return "(" + "+".join(terms) + ")" if terms else "0"


def _swap_frame(c, layout: str, wins: list[Win]) -> str:
    """Run `layout` on a copy of the stream and show it only inside the windows."""
    a, b, lay = c.L("sa"), c.L("sb"), c.L("sl")
    return (f"split=2[{a}][{b}];[{b}]{layout}[{lay}];"
            f"[{a}][{lay}]overlay=0:0:shortest=1:enable='{en(wins)}'")


# ======================================================================= PRO
def stage_light(p, wins, c):
    """Room lights fade down, a soft pool of light stays on the speaker."""
    i = p["intensity"]
    peak = min(1.45, (0.55 + 0.75 * i) * (1.25 - 0.5 * p["size"]))
    ramp = env(wins, 0.5, 0.35)
    ang = f"0.05+{_f(peak - 0.05)}*{ramp}"
    pos = f"x0=w*{_f(p['x'])}:y0=h*{_f(p['y'])}"
    e = en(wins)
    return (f"vignette=angle='{ang}':{pos}:eval=frame:enable='{e}',"
            f"eq=brightness='-{_f(0.04 * i)}*{ramp}':saturation='1-{_f(0.2 * i)}*{ramp}':"
            f"contrast='1+{_f(0.08 * i)}*{ramp}':eval=frame:enable='{e}'")


def press_mono(p, wins, c):
    """Newspaper-print monochrome: crushed blacks, paper-tinted whites, ink grain."""
    i = p["intensity"]
    e = en(wins)
    r, g, b = _rgb(p["paper"])
    lo, hi = _f(0.12 * i), _f(1 - 0.08 * i)
    return (f"hue=s=0:enable='{e}',"
            f"curves=all='0/0 {lo}/0 0.5/0.5 {hi}/1 1/1':enable='{e}',"
            f"format=gbrp,lutrgb=r='val*{r}/255':g='val*{g}/255':b='val*{b}/255':enable='{e}',"
            f"unsharp=5:5:{_f(0.6 + 0.6 * i)}:enable='{e}',"
            f"noise=alls={int(6 + 30 * p['grain'])}:allf=t+u:enable='{e}',"
            f"vignette=angle={_f(math.pi / 5 + 0.15 * i)}:enable='{e}'")


PANELS_PORTRAIT = ((0.04, 0.46, 0.27, 0.12), (0.69, 0.36, 0.27, 0.12), (0.04, 0.64, 0.27, 0.10))
PANELS_LANDSCAPE = ((0.04, 0.10, 0.24, 0.22), (0.04, 0.39, 0.24, 0.22), (0.04, 0.68, 0.24, 0.22))


def frost_panels(p, wins, c):
    """Frosted-glass cards float in beside the speaker (room for your own text/icons)."""
    n = int(p["panels"])
    f = p["frost"]
    base = c.L("fb")
    outs = [c.L("fs") for _ in range(n)]
    g = [f"split={n + 1}[{base}]" + "".join(f"[{o}]" for o in outs)]
    bt = max(1, int(round(2 * c.k)))
    cur = base
    panels = PANELS_LANDSCAPE if c.W > c.H else PANELS_PORTRAIT
    for idx, (fx, fy, fw, fh) in enumerate(panels[:n]):
        x, y = ensure_even(c.W * fx), ensure_even(c.H * fy)
        w = ensure_even(c.W * fw)
        h = ensure_even(c.H * fh)
        pan, nxt = c.L("fp"), c.L("fo")
        g.append(f"[{outs[idx]}]crop={w}:{h}:{x}:{y},"
                 f"gblur=sigma={_f(max(1.0, (6 + 18 * f) * c.k))},"
                 f"eq=brightness={_f(0.08 + 0.1 * f)}:saturation={_f(1 - 0.35 * f)},"
                 f"drawbox=0:0:iw:ih:color={_hex(p['tint'])}@0.18:t=fill,"
                 f"drawbox=iw*0.1:ih*0.32:iw*0.55:ih*0.1:color=white@0.55:t=fill,"
                 f"drawbox=iw*0.1:ih*0.56:iw*0.35:ih*0.08:color=white@0.35:t=fill,"
                 f"drawbox=0:0:iw:ih:color=white@0.6:t={bt}[{pan}]")
        stag = [(a + 0.12 * idx, b) for a, b in wins]
        last = idx == n - 1
        g.append(f"[{cur}][{pan}]overlay={x}:{y}:enable='{en(stag)}'" + ("" if last else f"[{nxt}]"))
        cur = nxt
    return ";".join(g)


def duotone(p, wins, c):
    """Two-colour poster look: shadows in one colour, highlights in another."""
    a, b, d = c.L("da"), c.L("db"), c.L("dd")
    sr, sg, sb = _rgb(p["shadow"])
    hr, hg, hb = _rgb(p["highlight"])
    lut = ":".join(f"{ch}='{s}+({h - s})*val/255'"
                   for ch, s, h in (("r", sr, hr), ("g", sg, hg), ("b", sb, hb)))
    return (f"format=gbrp,split=2[{a}][{b}];[{b}]hue=s=0,format=gbrp,"
            f"curves=all='0/0 0.25/0.15 0.75/0.9 1/1',lutrgb={lut}[{d}];"
            f"[{a}][{d}]blend=all_expr='A*{_f(1 - p['intensity'])}+B*{_f(p['intensity'])}':"
            f"enable='{en(wins)}'")


def scan_line(p, wins, c):
    """A glowing scan line sweeps down the frame, like an AI analysing the shot."""
    line, glow = c.L("ln"), c.L("gl")
    o1, base = c.L("so"), c.L("sb")
    lh = max(2, ensure_even(4 * c.k))
    gh = ensure_even(c.H * 0.08)
    period = 1 / p["speed"]
    ph = "(" + "+".join(f"if(between(t,{_f(a)},{_f(b)}),mod(t-{_f(a)},{_f(period)})/{_f(period)},0)"
                        for a, b in wins) + ")"
    y_line = f"-{lh}+{c.H + lh}*{ph}"
    i = p["intensity"]
    return (f"null[{base}];{_src(c, p['color'], c.W, lh, min(1.0, 0.5 + 0.5 * i))}[{line}];"
            f"{_src(c, p['color'], c.W, gh, 0.08 + 0.2 * i)}[{glow}];"
            f"[{base}][{glow}]overlay=x=0:y='{y_line}-{gh}':shortest=1:enable='{en(wins)}'[{o1}];"
            f"[{o1}][{line}]overlay=x=0:y='{y_line}':shortest=1:enable='{en(wins)}'")


def afterimage(p, wins, c):
    """Light trails follow every movement (hands, head turns, products)."""
    a, b, t = c.L("aa"), c.L("ab"), c.L("at")
    return (f"format=gbrp,split=2[{a}][{b}];[{b}]lagfun=decay={_f(p['decay'])}[{t}];"
            f"[{a}][{t}]blend=all_mode=lighten:all_opacity={_f(p['intensity'])}:"
            f"enable='{en(wins)}'")


def halo_orbit(p, wins, c):
    """Glowing dots orbit the speaker's head on a tilted ring."""
    n = int(p["dots"])
    R = max(8.0, c.W * p["radius"])
    dot = max(3.0, 22 * c.k)
    S = ensure_even(2 * R + 6 * dot)
    cx = S / 2
    terms = "+".join(
        f"exp(-(pow(X-{_f(cx + R * math.cos(2 * math.pi * k / n))},2)"
        f"+pow(Y-{_f(cx + R * math.sin(2 * math.pi * k / n))},2))/{_f(2 * dot * dot)})"
        for k in range(n))
    ring = f"exp(-pow(hypot(X-{_f(cx)},Y-{_f(cx)})-{_f(R)},2)/{_f(2 * max(1.0, 2.2 * c.k) ** 2)})"
    r, g, b = _rgb(p["color"])
    spr, out = c.L("hs"), c.L("hb")
    sh = ensure_even(S * 0.34)
    x = _f(c.W * p["x"] - S / 2)
    y = _f(c.H * p["y"] - sh / 2)
    return (f"null[{out}];color=c=black@0:s={S}x{S}:r={_f(c.fps)}:d={_f(2 / c.fps)},format=rgba,"
            f"geq=r={r}:g={g}:b={b}:a='min(255,420*({terms})+170*{ring})',"
            f"trim=end_frame=1,loop=loop=-1:size=1:start=0,setpts=N/{_f(c.fps)}/TB,"
            f"rotate=a='2*PI*{_f(p['speed'])}*t':c=none:ow={S}:oh={S},"
            f"scale={S}:{sh}[{spr}];"
            f"[{out}][{spr}]overlay=x={x}:y={y}:shortest=1:enable='{en(wins)}'")


def neon_outline(p, wins, c):
    """Glowing neon edges trace the speaker and the room."""
    a, b, e1, e2, eg, ee = (c.L(x) for x in ("na", "nb", "n1", "n2", "ng", "ne"))
    r, g, bl = _rgb(p["color"])
    gain = 1.6 + 1.4 * p["intensity"]
    lo = _f(0.05 + 0.1 * (1 - p["detail"]))
    hi = _f(0.15 + 0.2 * (1 - p["detail"]))
    return (f"format=gbrp,split=2[{a}][{b}];[{b}]edgedetect=low={lo}:high={hi},format=gbrp,"
            f"dilation,lutrgb=r='min(255,val*{_f(r * gain)}/255)':g='min(255,val*{_f(g * gain)}/255)':"
            f"b='min(255,val*{_f(bl * gain)}/255)',split=2[{e1}][{e2}];"
            f"[{e1}]gblur=sigma={_f(max(1.0, 5 * c.k))}[{eg}];"
            f"[{e2}][{eg}]blend=all_mode=addition[{ee}];"
            f"[{a}][{ee}]blend=all_mode=screen:all_opacity={_f(min(1.0, 0.4 + 0.6 * p['intensity']))}:"
            f"enable='{en(wins)}'")


# ======================================================================= STUDIO
def insight_split(p, wins, c):
    """Brand chart panel on top, the speaker below; bars rise one by one."""
    top = ensure_even(c.H * p["split"])
    ph = c.H - top
    y0 = ensure_even((c.H - ph) * 0.35)
    n = int(p["bars"])
    vals = list(p.get("values") or [])
    vals = [min(1.0, max(0.05, v)) for v in vals][:n] or \
        [0.35 + 0.55 * (k + 1) / n for k in range(n)]
    n = len(vals)
    base = top - ensure_even(top * 0.16)
    maxh = int(top * 0.62)
    area_x, area_w = c.W * 0.12, c.W * 0.76
    slot = area_w / n
    bw = ensure_even(slot * 0.58)
    cv, lay = c.L("cv"), c.L("ly")
    parts = [f"{_src(c, p['bg'], c.W, top)},"
             + ",".join(f"drawbox=0:{int(base - maxh * f)}:iw:{max(1, int(c.k))}:color=white@0.10:t=fill"
                        for f in (0.33, 0.66, 1.0)) + f"[{cv}0]"]
    cur = f"{cv}0"
    for k, v in enumerate(vals):
        bar, nxt = c.L("br"), c.L("cv")
        alpha = 1.0 if k == n - 1 else 0.55
        grow = _prog(wins, "ease-out", delay=0.15 + 0.18 * k, dur=0.6)
        parts.append(f"{_src(c, p['accent'], bw, maxh, alpha)}[{bar}]")
        parts.append(f"[{cur}][{bar}]overlay=x={int(area_x + slot * k + (slot - bw) / 2)}:"
                     f"y='{base}-{_f(maxh * v)}*{grow}+{maxh}*(1-gt({grow},0))':shortest=1[{nxt}]")
        cur = nxt
    lt = max(2, ensure_even(3 * c.k))
    parts.append(f"[{cur}]drawbox=0:{base}:iw:ih-{base}:color={_hex(p['bg'])}:t=fill,"
                 f"drawbox=iw*0.1:{base}:iw*0.8:{lt}:color={_hex(p['accent'])}:t=fill[{lay}c]")
    speaker = (f"crop={c.W}:{ph}:0:{y0},pad={c.W}:{c.H}:0:{top}:color={_hex(p['bg'])},"
               f"format=rgba[{lay}s];[{lay}s][{lay}c]overlay=0:0:shortest=1,"
               f"drawbox=0:{top - lt // 2}:iw:{lt}:color={_hex(p['accent'])}:t=fill")
    # the chart graph is a separate source chain; the speaker chain consumes the stream
    a, b, sp = c.L("ia"), c.L("ib"), c.L("is")
    return (f"split=2[{a}][{b}];" + ";".join(parts) + ";"
            f"[{b}]{speaker}[{sp}];[{a}][{sp}]overlay=0:0:shortest=1:enable='{en(wins)}'")


def brand_frame(p, wins, c):
    """The clip sits inside a framed card on your brand colour with an accent tab."""
    s = p["inset"]
    w, h = ensure_even(c.W * s), ensure_even(c.H * s)
    x = ensure_even((c.W - w) / 2)
    y = ensure_even((c.H - h) * 0.42)
    bt = max(2, ensure_even(4 * c.k))
    tab_y = y + h + ensure_even(c.H * 0.02)
    layout = (f"scale={w}:{h},pad={c.W}:{c.H}:{x}:{y}:color={_hex(p['bg'])},"
              f"drawbox={x - bt}:{y - bt}:{w + 2 * bt}:{h + 2 * bt}:color={_hex(p['accent'])}:t={bt},"
              f"drawbox={x}:{tab_y}:{ensure_even(c.W * 0.22)}:{max(2, ensure_even(8 * c.k))}:"
              f"color={_hex(p['accent'])}:t=fill,"
              f"drawbox={x + ensure_even(c.W * 0.24)}:{tab_y}:{ensure_even(c.W * 0.08)}:"
              f"{max(2, ensure_even(8 * c.k))}:color=white@0.35:t=fill")
    return _swap_frame(c, layout, wins)


def progress_rail(p, wins, c):
    """A brand rail fills as you talk; step dots light up — for lists and how-tos."""
    n = int(p["steps"])
    th = max(4, ensure_even(14 * c.k))
    vertical = p["side"] in ("left", "right")
    if vertical:
        L = ensure_even(c.H * 0.6)
        x = ensure_even(c.W * 0.06) if p["side"] == "left" else ensure_even(c.W * 0.94 - th)
        y = ensure_even(c.H * 0.2)
        rw, rh = th, L
    else:
        L = ensure_even(c.W * 0.8)
        x, y = ensure_even(c.W * 0.1), ensure_even(c.H * 0.06)
        rw, rh = L, th
    cv, fill, base, rail = c.L("rc"), c.L("rf"), c.L("rb"), c.L("rr")
    pr = _prog(wins, "ease-in-out")
    pos = (f"x=0:y='-{L}+{L}*{pr}'" if vertical else f"x='-{L}+{L}*{pr}':y=0")
    g = [f"null[{base}]", f"{_src(c, p['track'], rw, rh, 0.4)}[{cv}]",
         f"{_src(c, p['accent'], rw, rh)}[{fill}]",
         f"[{cv}][{fill}]overlay={pos}:shortest=1[{rail}]"]
    dot = max(6, ensure_even(th * 3))
    boxes = []
    for k in range(n):
        f = k / (n - 1) if n > 1 else 1.0
        if vertical:
            dx, dy = x + th // 2 - dot // 2, ensure_even(y + L * f - dot / 2)
        else:
            dx, dy = ensure_even(x + L * f - dot / 2), y + th // 2 - dot // 2
        on = "+".join(f"between(t,{_f(a + (b - a) * f * 0.98)},{_f(b)})" for a, b in wins)
        boxes.append(f"drawbox={dx}:{dy}:{dot}:{dot}:color={_hex(p['track'])}@0.7:t=fill:"
                     f"enable='{en(wins)}'")
        boxes.append(f"drawbox={dx}:{dy}:{dot}:{dot}:color={_hex(p['accent'])}:t=fill:"
                     f"enable='{on}'")
    g.append(f"[{base}][{rail}]overlay={x}:{y}:shortest=1:enable='{en(wins)}'," + ",".join(boxes))
    return ";".join(g)


def pixel_resolve(p, wins, c):
    """Signature reveal: the shot dissolves out of a two-tone pixel dither into full clarity."""
    stages = (40, 26, 16, 9, 4)
    n = len(stages)
    d = p["duration"]
    a1, a2 = _rgb(p["tone_a"]), _rgb(p["tone_b"])
    split = [c.L("pr") for _ in range(n)]
    base = c.L("pb")
    g = [f"format=gbrp,split={n + 1}[{base}]" + "".join(f"[{s}]" for s in split)]
    cur = base
    for j, bs in enumerate(stages):
        b = max(2, int(round(bs * c.k)))
        w, h = max(1, c.W // b), max(1, c.H // b)
        st, nxt = c.L("ps"), c.L("pc")
        chain = f"[{split[j]}]scale={w}:{h}:flags=area"
        if j < 3:  # two-tone dither stages
            lut = ":".join(f"{ch}='if(gt(val,128),{hi},{lo})'"
                           for ch, lo, hi in zip("rgb", a1, a2))
            chain += (f",format=yuv444p,noise=c0s={40 - 10 * j}:c0f=u,"
                      f"lutyuv=y='if(gt(val,100),255,0)':u=128:v=128,format=gbrp,lutrgb={lut}")
        chain += f",scale={c.W}:{c.H}:flags=neighbor,format=gbrp[{st}]"
        g.append(chain)
        on = [(a + d * j / n, a + d * (j + 1) / n) for a, _ in wins]
        last = j == n - 1
        g.append(f"[{cur}][{st}]overlay=0:0:format=gbrp:enable='{en(on)}'" + ("" if last else f"[{nxt}]"))
        cur = nxt
    return ";".join(g)


REEL_FILTERS: dict[str, Callable] = {
    "lionstone.stage-light": stage_light,
    "lionstone.press-mono": press_mono,
    "lionstone.frost-panels": frost_panels,
    "lionstone.duotone-pop": duotone,
    "lionstone.scan-line": scan_line,
    "lionstone.afterimage": afterimage,
    "lionstone.halo-orbit": halo_orbit,
    "lionstone.neon-outline": neon_outline,
    "lionstone.insight-split": insight_split,
    "lionstone.brand-frame": brand_frame,
    "lionstone.progress-rail": progress_rail,
    "lionstone.pixel-resolve": pixel_resolve,
}


def register() -> None:
    fa.FILTERS.update(REEL_FILTERS)


register()
