"""Native FFmpeg renderers for Pro titles.

Remotion components (``remotion/``) are the reference look. These builders let
P03–P06 render without Node; P01/P02 need Remotion (gradient sheen / footage
masks) and otherwise fall back to F01 with a logged note.
"""

from __future__ import annotations

from pathlib import Path

from lionstone.captions import smart_upper
from lionstone.effects.catalog import Effect
from lionstone.effects.ffmpeg_fx import (
    FxContext,
    _alpha_layer,
    _drawtext,
    _num,
    _overlay,
    _timing,
    ease_out,
    envelope,
)
from lionstone.models import GraphicEvent

try:
    from lionstone.effects.ffmpeg_fx import filter_path
except ImportError:  # core installed before filter_path existed
    import re

    def filter_path(path) -> str:
        s = re.sub(r"([\\':])", r"\\\1", Path(path).as_posix())
        return re.sub(r"([\\'\[\],;])", r"\\\1", s)


def _center_y(ev: GraphicEvent, H: int) -> str:
    return f"{int(H * 0.28)}" if ev.params.get("position") == "upper" else "h/2"


def p03_depth_parallax(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    zoom = float(fx.parameters.get("bgZoom", 1.08)) - 1
    drift = float(fx.parameters.get("titleDrift", 0.025))
    dur = t1 - t0
    a, b, z, o = ctx.label("pa"), ctx.label("pb"), ctx.label("pz"), ctx.label()
    p = f"min(1,t/{_num(dur)})"
    parts = [
        f"[{inp}]split[{a}][{b}]",
        f"[{b}]trim=start={_num(t0)}:end={_num(t1)},setpts=PTS-STARTPTS,"
        f"scale=w='trunc({W}*(1+{zoom}*{p})/2)*2':h='trunc({H}*(1+{zoom}*{p})/2)*2':eval=frame,"
        f"crop={W}:{H},format=yuva420p,fade=t=in:st=0:d={_num(t_in * 0.6)}:alpha=1,"
        f"fade=t=out:st={_num(dur - t_out)}:d={_num(t_out)}:alpha=1,"
        f"setpts=PTS+{_num(t0)}/TB[{z}]",
        _overlay(a, z, o),
    ]
    size = int(H * float(fx.parameters.get("fontSize", 0.075)))
    out = ctx.label()
    x = f"(w-tw)/2+{int(W * drift)}*(0.5-min(1,(t-{_num(t0)})/{_num(dur)}))"
    parts.append(_drawtext(ctx, o, out, ev.text, size, x, f"{_center_y(ev, H)}-th/2",
                           envelope(t0, t_in, t1, t_out),
                           extra="shadowcolor=black@0.5:shadowx=0:shadowy=4"))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.42), x,
                               f"{_center_y(ev, H)}+{int(size * 0.75)}",
                               envelope(t0 + 0.2, t_in, t1, t_out), color="0xDDDDDD"))
        cur = out
    return parts, cur


def p04_film_grain(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    prm = fx.parameters
    grain = int(10 + 30 * float(prm.get("grain", 0.35)))
    warm = float(prm.get("warmth", 0.03))
    dur = t1 - t0
    a, b, g, o = ctx.label("ga"), ctx.label("gb"), ctx.label("gz"), ctx.label()
    parts = [
        f"[{inp}]split[{a}][{b}]",
        f"[{b}]trim=start={_num(t0)}:end={_num(t1)},setpts=PTS-STARTPTS,"
        f"noise=alls={grain}:allf=t,vignette=angle=PI/4.5,"
        f"colorbalance=rm={warm:.3f}:bm={-warm:.3f},eq=saturation=0.85,format=yuva420p,"
        f"fade=t=in:st=0:d={_num(t_in)}:alpha=1,"
        f"fade=t=out:st={_num(dur - t_out)}:d={_num(t_out)}:alpha=1,"
        f"setpts=PTS+{_num(t0)}/TB[{g}]",
        _overlay(a, g, o),
    ]
    size = int(H * float(prm.get("fontSize", 0.07)))
    out = ctx.label()
    parts.append(_drawtext(ctx, o, out, ev.text, size, "(w-tw)/2", f"{_center_y(ev, H)}-th/2",
                           envelope(t0 + 0.3, t_in, t1, t_out), color="0xF4EDE2",
                           extra="shadowcolor=black@0.6:shadowx=0:shadowy=2"))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.42), "(w-tw)/2",
                               f"{_center_y(ev, H)}+{int(size * 0.75)}",
                               envelope(t0 + 0.5, t_in, t1, t_out), color="0xD8CFC2"))
        cur = out
    return parts, cur


def p05_staggered_kinetic(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    prm = fx.parameters
    words = ev.text.split()
    stagger = float(prm.get("stagger", 0.12))
    rise = int(H * float(prm.get("rise", 0.04)))
    vertical = ctx.height > ctx.width
    size = int(min(H * float(prm.get("fontSize", 0.075)), ctx.width * 0.09))
    # group words into lines of ~14 chars (vertical) / ~22 chars (landscape)
    limit = 14 if vertical else 22
    lines: list[str] = []
    for w in words:
        if lines and len(lines[-1]) + 1 + len(w) <= limit:
            lines[-1] += " " + w
        else:
            lines.append(w)
    lh = int(size * 1.15)
    top = f"{_center_y(ev, H)}-{len(lines) * lh // 2}"
    parts, cur = [], inp
    for k, line in enumerate(lines):
        st = t0 + k * stagger * 2
        out = ctx.label()
        y = f"{top}+{k * lh}+{rise}*(1-{ease_out(st, t_in * 0.6, 3)})"
        color = ctx.accent if k == len(lines) - 1 and len(lines) > 1 else None
        parts.append(_drawtext(ctx, cur, out, smart_upper(line), size, "(w-tw)/2", y,
                               envelope(st, t_in * 0.5, t1, t_out), color=color,
                               extra=f"borderw={max(2, size // 16)}:bordercolor=black@0.85"))
        cur = out
    return parts, cur


def p06_signature_brand(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    lay, lab = _alpha_layer(ctx, "0x0B0B0D", W, H, t0, t_in * 0.5, t1, t_out)
    cur = ctx.label()
    parts = [lay, _overlay(inp, lab, cur)]
    dur = t1 - t0
    lw = int(W * 0.22)
    size = int(H * float(fx.parameters.get("fontSize", 0.06)))
    for k, dy in enumerate((-int(size * 1.1), int(size * 1.1))):
        ln = ctx.label("bl")
        parts.append(
            f"color=c={ctx.accent}:s={lw}x{max(2, H // 540)}:r={_num(ctx.fps)}:d={_num(dur)},"
            f"format=yuva420p,scale=w='max(2,{lw}*(1-pow(1-min(1,max(0,t-{0.2 + k * 0.15})/"
            f"{_num(t_in)}),3)))':h={max(2, H // 540)}:eval=frame,"
            f"fade=t=out:st={_num(dur - t_out)}:d={_num(t_out)}:alpha=1,"
            f"setpts=PTS+{_num(t0)}/TB[{ln}]")
        nxt = ctx.label()
        parts.append(_overlay(cur, ln, nxt, x="(W-w)/2", y=f"H/2+{dy}"))
        cur = nxt
    logo = ev.params.get("logo") or fx.parameters.get("logo")
    if logo and Path(logo).exists():
        lg, nxt = ctx.label("logo"), ctx.label()
        lh = int(H * 0.14)
        path = filter_path(Path(logo).resolve())
        parts.append(f"movie=filename={path},scale=-2:{lh},format=yuva420p,loop=-1:1,"
                     f"trim=duration={_num(dur)},fade=t=in:st=0.1:d={_num(t_in)}:alpha=1,"
                     f"fade=t=out:st={_num(dur - t_out)}:d={_num(t_out)}:alpha=1,"
                     f"setpts=PTS+{_num(t0)}/TB[{lg}]")
        parts.append(_overlay(cur, lg, nxt, x="(W-w)/2", y=f"H/2-{int(size * 1.4) + lh}"))
        cur = nxt
    out = ctx.label()
    parts.append(_drawtext(ctx, cur, out, smart_upper(ev.text), size, "(w-tw)/2", "(h-th)/2",
                           envelope(t0 + 0.35, t_in * 0.7, t1, t_out)))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.4), "(w-tw)/2",
                               f"h/2+{int(size * 1.4)}", envelope(t0 + 0.6, t_in, t1, t_out),
                               color="0xBBBBBB"))
        cur = out
    return parts, cur


def remotion_only_fallback(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    """P01/P02 need Remotion. Without it, render the declared fallback (F01) with
    F01's own parameters — and say so in the render notes."""
    from lionstone.effects import Catalog as CoreCatalog
    from lionstone.effects.ffmpeg_fx import f01_cinematic_fade
    ctx.notes.append(f"{ev.id}: {fx.id} {fx.name} needs Remotion — rendered fallback F01")
    return f01_cinematic_fade(CoreCatalog().get("F01"), ev, inp, ctx)


BUILDERS = {
    "P01": remotion_only_fallback,
    "P02": remotion_only_fallback,
    "P03": p03_depth_parallax,
    "P04": p04_film_grain,
    "P05": p05_staggered_kinetic,
    "P06": p06_signature_brand,
}
