"""Native FFmpeg renderers for the free title pack.

These are the zero-dependency path: no Node, no browser. Remotion components in
``remotion/`` are the reference look; these match them closely and double as
the declared ``fallback`` when Remotion is unavailable or fails.

Every builder returns filtergraph fragments that take ``inp`` and produce a new
label, so effects compose on top of each other in one pass.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..models import GraphicEvent
from .catalog import Effect


@dataclass
class FxContext:
    width: int
    height: int
    fps: float
    font: str | None
    workdir: Path
    accent: str = "0xE8B04B"  # Lionstone gold
    text_color: str = "white"
    _n: int = 0
    notes: list[str] = field(default_factory=list)

    def label(self, prefix: str = "fx") -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def textfile(self, text: str) -> str:
        self._n += 1
        p = self.workdir / f"text_{self._n:03d}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p.name  # FFmpeg runs with cwd=workdir; quoted values must stay unescaped

    def fontopt(self) -> str:
        return f"fontfile='{Path(self.font).as_posix()}':" if self.font else ""


def _num(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


def envelope(t0: float, t_in: float, t1: float, t_out: float, ease: str = "quad") -> str:
    """Opacity 0→1→0 expression in global time `t`."""
    p = f"(t-{_num(t0)})/{_num(max(t_in, 1e-3))}"
    rise = f"(1-pow(1-{p},2))" if ease == "quad" else p
    return (f"if(lt(t,{_num(t0)}),0,if(lt(t,{_num(t0 + t_in)}),{rise},"
            f"if(lt(t,{_num(t1 - t_out)}),1,if(lt(t,{_num(t1)}),({_num(t1)}-t)/{_num(max(t_out, 1e-3))},0))))")


def ease_out(t0: float, t_in: float, power: int = 3) -> str:
    """0→1 eased progress expression, clamped."""
    p = f"min(1,max(0,(t-{_num(t0)})/{_num(max(t_in, 1e-3))}))"
    return f"(1-pow(1-{p},{power}))"


def _timing(fx: Effect, ev: GraphicEvent) -> tuple[float, float, float, float]:
    t_in = float(ev.params.get("enter", fx.duration["enter"]))
    t_out = float(ev.params.get("exit", fx.duration["exit"]))
    t0 = ev.at
    t1 = ev.at + max(ev.duration, t_in + t_out + 0.2)
    return t0, t_in, t1, t_out


def _alpha_layer(ctx: FxContext, color: str, w: int, h: int, t0: float, t_in: float,
                 t1: float, t_out: float) -> tuple[str, str]:
    """A solid (possibly translucent) layer that fades in/out at the right time."""
    lab = ctx.label("lay")
    dur = t1 - t0
    part = (f"color=c={color}:s={w}x{h}:r={_num(ctx.fps)}:d={_num(dur)},format=yuva420p,"
            f"fade=t=in:st=0:d={_num(t_in)}:alpha=1,"
            f"fade=t=out:st={_num(max(0, dur - t_out))}:d={_num(t_out)}:alpha=1,"
            f"setpts=PTS+{_num(t0)}/TB[{lab}]")
    return part, lab


def _overlay(inp: str, layer: str, out: str, x: str = "0", y: str = "0") -> str:
    return f"[{inp}][{layer}]overlay=x='{x}':y='{y}':eof_action=pass:format=auto[{out}]"


def _drawtext(ctx: FxContext, inp: str, out: str, text: str, size: int, x: str, y: str,
              alpha: str, color: str | None = None, extra: str = "") -> str:
    return (f"[{inp}]drawtext={ctx.fontopt()}textfile='{ctx.textfile(text)}':expansion=none:"
            f"fontsize={size}:fontcolor={color or ctx.text_color}:x='{x}':y='{y}':"
            f"alpha='{alpha}'{(':' + extra) if extra else ''}[{out}]")


# --- free pack -------------------------------------------------------------------
def f01_cinematic_fade(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    parts: list[str] = []
    dim = float(ev.params.get("dimBackground", fx.parameters.get("dimBackground", 0.35)))
    cur = inp
    if dim > 0:
        lay, lab = _alpha_layer(ctx, f"black@{dim:.2f}", W, H, t0, t_in, t1, t_out)
        nxt = ctx.label()
        parts += [lay, _overlay(cur, lab, nxt)]
        cur = nxt
    size = int(H * float(fx.parameters.get("fontSize", 0.075)))
    a = envelope(t0, t_in, t1, t_out)
    out = ctx.label()
    parts.append(_drawtext(ctx, cur, out, ev.text, size, "(w-tw)/2", "(h-th)/2", a,
                           extra="shadowcolor=black@0.45:shadowx=0:shadowy=3"))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.42), "(w-tw)/2",
                               f"(h/2)+{int(size * 0.85)}", a, color="0xDDDDDD"))
        cur = out
    return parts, cur


def f02_slow_rise(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    size = int(H * float(fx.parameters.get("fontSize", 0.07)))
    dist = int(H * float(fx.parameters.get("distance", 0.03)))
    y = f"(h-th)/2+{dist}*(1-{ease_out(t0, t_in, 3)})"
    a = envelope(t0, t_in * 0.8, t1, t_out)
    out = ctx.label()
    parts = [_drawtext(ctx, inp, out, ev.text, size, "(w-tw)/2", y, a,
                       extra="shadowcolor=black@0.4:shadowx=0:shadowy=2")]
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.45), "(w-tw)/2",
                               f"(h/2)+{int(size * 0.8)}+{dist}*(1-{ease_out(t0 + 0.15, t_in, 3)})",
                               envelope(t0 + 0.15, t_in, t1, t_out), color="0xDDDDDD"))
        cur = out
    return parts, cur


def f03_line_reveal(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    size = int(H * float(fx.parameters.get("fontSize", 0.065)))
    lw = int(W * float(fx.parameters.get("lineWidth", 0.28)))
    th = int(fx.parameters.get("lineThickness", 4)) * max(1, H // 1080)
    dur = t1 - t0
    lab = ctx.label("line")
    color = ctx.accent if fx.parameters.get("lineColor") == "accent" else fx.parameters["lineColor"]
    # line grows from the centre using a per-frame scale (local time inside the layer)
    parts = [
        f"color=c={color}:s={lw}x{th}:r={_num(ctx.fps)}:d={_num(dur)},format=yuva420p,"
        f"scale=w='max(2,{lw}*(1-pow(1-min(1,t/{_num(t_in)}),3)))':h={th}:eval=frame,"
        f"fade=t=out:st={_num(max(0, dur - t_out))}:d={_num(t_out)}:alpha=1,"
        f"setpts=PTS+{_num(t0)}/TB[{lab}]"
    ]
    nxt = ctx.label()
    parts.append(_overlay(inp, lab, nxt, x="(W-w)/2", y=f"H/2+{int(size * 0.75)}"))
    out = ctx.label()
    parts.append(_drawtext(ctx, nxt, out, ev.text, size, "(w-tw)/2", "(h/2)-th",
                           envelope(t0 + t_in * 0.35, t_in * 0.65, t1, t_out)))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.45), "(w-tw)/2",
                               f"(h/2)+{int(size * 1.15)}",
                               envelope(t0 + t_in * 0.6, t_in * 0.5, t1, t_out), color="0xDDDDDD"))
        cur = out
    return parts, cur


def f04_chapter_card(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    bg = str(fx.parameters.get("background", "#0E0E10")).replace("#", "0x")
    lay, lab = _alpha_layer(ctx, bg, W, H, t0, t_in, t1, t_out)
    cur = ctx.label()
    parts = [lay, _overlay(inp, lab, cur)]
    size = int(H * float(fx.parameters.get("fontSize", 0.08)))
    number = ev.params.get("number")
    if number is not None and fx.parameters.get("showNumber", True):
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, f"{int(number):02d}", int(size * 0.5),
                               "(w-tw)/2", f"(h/2)-{int(size * 1.2)}",
                               envelope(t0 + 0.1, t_in, t1, t_out), color=ctx.accent))
        cur = out
    out = ctx.label()
    parts.append(_drawtext(ctx, cur, out, ev.text, size, "(w-tw)/2", "(h-th)/2",
                           envelope(t0 + 0.2, t_in, t1, t_out)))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, int(size * 0.4), "(w-tw)/2",
                               f"(h/2)+{int(size * 0.9)}", envelope(t0 + 0.3, t_in, t1, t_out),
                               color="0xBBBBBB"))
        cur = out
    return parts, cur


def f05_lower_third(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    p = fx.parameters
    name_px = int(H * float(p.get("nameSize", 0.042)))
    title_px = int(H * float(p.get("titleSize", 0.028)))
    margin_x = int(W * 0.07)  # inside 90% action-safe
    base_y = int(H * 0.80)
    slide = f"{int(W * 0.02)}*(1-{ease_out(t0, t_in, 3)})"
    a = envelope(t0, t_in, t1, t_out)
    op = float(p.get("plateOpacity", 0.55))
    parts: list[str] = []
    cur = inp
    if p.get("accentBar", True):
        bar_h = name_px + (title_px + int(H * 0.012) if ev.subtext else 0) + int(H * 0.02)
        lay, lab = _alpha_layer(ctx, ctx.accent, max(4, W // 320), bar_h, t0, t_in, t1, t_out)
        nxt = ctx.label()
        parts += [lay, _overlay(cur, lab, nxt, x=f"{margin_x - W // 120}",
                                y=f"{base_y - int(H * 0.01)}")]
        cur = nxt
    out = ctx.label()
    box = f"box=1:boxcolor=black@{op:.2f}:boxborderw={int(H * 0.012)}"
    parts.append(_drawtext(ctx, cur, out, ev.text, name_px, f"{margin_x}+{slide}",
                           f"{base_y}", a, extra=box))
    cur = out
    if ev.subtext:
        out = ctx.label()
        parts.append(_drawtext(ctx, cur, out, ev.subtext, title_px, f"{margin_x}+{slide}",
                               f"{base_y + name_px + int(H * 0.022)}",
                               envelope(t0 + 0.12, t_in, t1, t_out), color="0xE6E6E6",
                               extra=f"box=1:boxcolor=black@{op:.2f}:boxborderw={int(H * 0.01)}"))
        cur = out
    return parts, cur


def f06_letter_spacing(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    # drawtext has no tracking control: approximate with a slow fade + slight rise.
    ctx.notes.append(f"{ev.id}: F06 tracking animation needs Remotion; rendered FFmpeg approximation")
    return f02_slow_rise(fx, ev, inp, ctx)


BUILDERS: dict[str, Callable] = {
    "F01": f01_cinematic_fade,
    "F02": f02_slow_rise,
    "F03": f03_line_reveal,
    "F04": f04_chapter_card,
    "F05": f05_lower_third,
    "F06": f06_letter_spacing,
    "simple_fade": f01_cinematic_fade,
}


def register_builder(effect_id: str, fn: Callable) -> None:
    """Plugins call this to add native renderers for their effects."""
    BUILDERS[effect_id] = fn


def build_graphics(events: list[GraphicEvent], catalog, inp: str, ctx: FxContext,
                   allow_tiers: set[str]) -> tuple[list[str], str, list[dict]]:
    """Chain all graphic events onto `inp`. Returns (parts, out_label, render_log)."""
    parts: list[str] = []
    log: list[dict] = []
    cur = inp
    for ev in sorted(events, key=lambda e: e.at):
        fx = catalog.get(ev.effect)
        engine = "ffmpeg"
        if fx.tier not in allow_tiers:
            log.append({"event": ev.id, "effect": fx.id, "status": "blocked",
                        "detail": f"{fx.tier} effect without an active {fx.tier} license — "
                                  f"rendered fallback {fx.fallback!r}"})
            builder = BUILDERS.get(fx.fallback, f01_cinematic_fade)
            fx = catalog.get("F01")
            engine = "fallback"
        else:
            builder = BUILDERS.get(fx.id)
            if builder is None:
                builder = BUILDERS.get(fx.fallback, f01_cinematic_fade)
                engine = "fallback"
                log.append({"event": ev.id, "effect": fx.id, "status": "fallback",
                            "detail": f"no native renderer; used {fx.fallback!r}"})
        new_parts, cur = builder(fx, ev, cur, ctx)
        parts += new_parts
        if engine == "ffmpeg":
            log.append({"event": ev.id, "effect": fx.id, "status": "rendered", "engine": "ffmpeg"})
    return parts, cur, log
