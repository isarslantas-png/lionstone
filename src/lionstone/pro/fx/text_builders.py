"""FFmpeg renderers for the Pro typography pack (T01–T12).

Registered as core graphic builders, so they use the same graphics layer,
safe-area rules, collision handling and QA as the free titles.
All text goes through `textfile=` (no filtergraph escaping of user text);
Unicode incl. Turkish is supported by the resolved font.
"""

from __future__ import annotations

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


def _p(ev: GraphicEvent, fx: Effect, key: str, default):
    return ev.params.get(key, fx.parameters.get(key, default))


def _color(ev, ctx, key="color"):
    c = ev.params.get(key)
    return c.replace("#", "0x") if isinstance(c, str) and c.startswith("#") else ctx.text_color


def _spring(t0: float, w: float = 12.0, z: float = 0.5) -> str:
    p = f"max(0,t-{_num(t0)})"
    return f"min(1.15,1-exp(-{_num(z * w)}*{p}*3)*cos({_num(w * 0.87)}*{p}*3))"


def _wrap(text: str, limit: int) -> list[str]:
    lines: list[str] = []
    for w in text.split():
        if lines and len(lines[-1]) + 1 + len(w) <= limit:
            lines[-1] += " " + w
        else:
            lines.append(w)
    return lines or [""]


def t01_word_pop(fx: Effect, ev: GraphicEvent, inp: str, ctx: FxContext):
    t0, t_in, t1, t_out = _timing(fx, ev)
    words = ev.text.split() or [""]
    H, W = ctx.height, ctx.width
    size = int(min(H * 0.1, W * 0.12))
    slot = max(0.18, (t1 - t0 - t_out) / len(words))
    parts, cur = [], inp
    y = f"{int(H * 0.28)}" if ev.params.get("position") == "upper" else "(h-th)/2"
    for i, w in enumerate(words):
        a = t0 + i * slot
        b = t1 if i == len(words) - 1 else a + slot
        out = ctx.label()
        fs = f"{size}*(0.78+0.22*{_spring(a)})"
        parts.append(
            f"[{cur}]drawtext={ctx.fontopt()}textfile='{ctx.textfile(smart_upper(w))}':"
            f"expansion=none:fontsize='{fs}':fontcolor="
            f"{ctx.accent if i == len(words) - 1 and len(words) > 1 else ctx.text_color}:"
            f"borderw={max(2, size // 14)}:bordercolor=black@0.85:x='(w-tw)/2':y='{y}':"
            f"alpha='{envelope(a, 0.06, b, 0.08 if i < len(words) - 1 else t_out)}'[{out}]")
        cur = out
    return parts, cur


def t02_phrase_build(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    lines = [s.strip() for s in ev.text.split("/")] if "/" in ev.text else _wrap(ev.text, 22)
    size = int(min(H * 0.065, ctx.width * 0.07))
    lh = int(size * 1.25)
    top = f"(h-{len(lines) * lh})/2"
    parts, cur = [], inp
    for i, line in enumerate(lines):
        a = t0 + i * 0.35
        out = ctx.label()
        y = f"{top}+{i * lh}+{int(size * 0.4)}*(1-{ease_out(a, t_in, 3)})"
        parts.append(_drawtext(ctx, cur, out, line, size, "(w-tw)/2", y,
                               envelope(a, t_in, t1, t_out),
                               color=ctx.accent if i == len(lines) - 1 and len(lines) > 1 else None,
                               extra="shadowcolor=black@0.5:shadowx=0:shadowy=3"))
        cur = out
    return parts, cur


def t03_pin_label(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    x, y = float(_p(ev, fx, "x", 0.6)) * W, float(_p(ev, fx, "y", 0.4)) * H
    size = int(H * 0.034)
    o1, o2 = ctx.label(), ctx.label()
    parts = [
        _drawtext(ctx, inp, o1, "●", int(size * 1.1), f"{int(x)}-tw/2", f"{int(y)}-th/2",
                  envelope(t0, t_in * 0.5, t1, t_out), color=ctx.accent,
                  extra="borderw=3:bordercolor=white@0.9"),
        _drawtext(ctx, o1, o2, ev.text, size, f"{int(x + size * 1.2)}+{int(W * 0.01)}*"
                  f"(1-{ease_out(t0 + 0.15, t_in, 3)})", f"{int(y)}-th/2",
                  envelope(t0 + 0.15, t_in, t1, t_out),
                  extra=f"box=1:boxcolor=black@0.6:boxborderw={int(size * 0.35)}"),
    ]
    return parts, o2


def t04_counter(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    a = float(ev.params.get("from", 0))
    b = float(ev.params.get("to", 100))
    count = max(0.6, min(2.5, (t1 - t0) * 0.45))
    pr = f"(1-pow(1-min(1,max(0,(t-{_num(t0)})/{_num(count)})),3))"

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("%", "\\%")

    body = (f"{esc(str(ev.params.get('prefix', '')))}%{{eif:{_num(a)}+({_num(b - a)})*{pr}:d}}"
            f"{esc(str(ev.params.get('suffix', '')))}")
    size = int(min(H * 0.14, ctx.width * 0.16))
    out = ctx.label()
    parts = [f"[{inp}]drawtext={ctx.fontopt()}textfile='{ctx.textfile(body)}':expansion=normal:"
             f"fontsize={size}:fontcolor={ctx.accent}:x='(w-tw)/2':y='(h-th)/2-{int(size*0.2)}':"
             f"shadowcolor=black@0.5:shadowy=4:alpha='{envelope(t0, t_in * 0.5, t1, t_out)}'[{out}]"]
    cur = out
    if ev.subtext:
        o = ctx.label()
        parts.append(_drawtext(ctx, cur, o, ev.subtext, int(size * 0.28), "(w-tw)/2",
                               f"(h/2)+{int(size * 0.7)}", envelope(t0 + 0.2, t_in, t1, t_out)))
        cur = o
    return parts, cur


def t05_price(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    size = int(min(H * 0.11, ctx.width * 0.13))
    parts, cur = [], inp
    old = str(ev.params.get("old", "")).strip()
    if old:
        o = ctx.label()
        struck = "".join(ch + "̶" for ch in old)
        parts.append(_drawtext(ctx, cur, o, struck, int(size * 0.4), "(w-tw)/2",
                               f"(h/2)-{int(size * 1.15)}", envelope(t0, t_in, t1, t_out),
                               color="0xBBBBBB"))
        cur = o
    o = ctx.label()
    fs = f"{size}*(0.8+0.2*{_spring(t0 + 0.15)})"
    parts.append(f"[{cur}]drawtext={ctx.fontopt()}textfile='{ctx.textfile(ev.text)}':"
                 f"expansion=none:fontsize='{fs}':fontcolor=0x111111:box=1:"
                 f"boxcolor={ctx.accent}@0.95:boxborderw={int(size * 0.25)}:"
                 f"x='(w-tw)/2':y='(h-th)/2':alpha='{envelope(t0 + 0.15, 0.2, t1, t_out)}'[{o}]")
    cur = o
    if ev.subtext:
        o = ctx.label()
        parts.append(_drawtext(ctx, cur, o, ev.subtext, int(size * 0.3), "(w-tw)/2",
                               f"(h/2)+{int(size * 0.85)}", envelope(t0 + 0.3, t_in, t1, t_out)))
        cur = o
    return parts, cur


def t06_stat(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    size = int(min(H * 0.16, ctx.width * 0.18))
    o1 = ctx.label()
    parts = [_drawtext(ctx, inp, o1, ev.text, size, "(w-tw)/2",
                       f"(h-th)/2-{int(size * 0.25)}+{int(size * 0.2)}*(1-{ease_out(t0, t_in)})",
                       envelope(t0, t_in, t1, t_out), color=ctx.accent,
                       extra="shadowcolor=black@0.45:shadowy=4")]
    cur = o1
    if ev.subtext:
        o2 = ctx.label()
        parts.append(_drawtext(ctx, cur, o2, smart_upper(ev.subtext), int(size * 0.22),
                               "(w-tw)/2", f"(h/2)+{int(size * 0.55)}",
                               envelope(t0 + 0.25, t_in, t1, t_out)))
        cur = o2
    return parts, cur


def _lower_left(ctx, inp, t0, t_in, t1, t_out, main, sub, glyph=None):
    W, H = ctx.width, ctx.height
    mx, y = int(W * 0.07), int(H * 0.8)
    size = int(H * 0.04)
    slide = f"{int(W * 0.02)}*(1-{ease_out(t0, t_in, 3)})"
    parts, cur = [], inp
    text = f"{glyph}  {main}" if glyph else main
    o = ctx.label()
    parts.append(_drawtext(ctx, cur, o, text, size, f"{mx}+{slide}", f"{y}",
                           envelope(t0, t_in, t1, t_out),
                           extra=f"box=1:boxcolor=black@0.6:boxborderw={int(H * 0.012)}"))
    cur = o
    if sub:
        o = ctx.label()
        parts.append(_drawtext(ctx, cur, o, sub, int(size * 0.68), f"{mx}+{slide}",
                               f"{y + size + int(H * 0.022)}", envelope(t0 + 0.12, t_in, t1, t_out),
                               color="0xE6E6E6",
                               extra=f"box=1:boxcolor=black@0.6:boxborderw={int(H * 0.01)}"))
        cur = o
    return parts, cur


def t07_location(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    return _lower_left(ctx, inp, t0, t_in, t1, t_out, ev.text, ev.subtext, glyph="◉")


def t08_info_bar(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    bh = int(H * 0.085)
    lay, lab = _alpha_layer(ctx, "black@0.72", W, bh, t0, t_in, t1, t_out)
    o1 = ctx.label()
    y = f"H-{bh}+{bh}*(1-{ease_out(t0, t_in, 3)})"
    parts = [lay, _overlay(inp, lab, o1, x="0", y=y)]
    o2 = ctx.label()
    text = f"{ev.text}   ·   {ev.subtext}" if ev.subtext else ev.text
    parts.append(_drawtext(ctx, o1, o2, text, int(bh * 0.42), f"{int(W * 0.05)}",
                           f"h-{bh}+({bh}-th)/2+{bh}*(1-{ease_out(t0, t_in, 3)})",
                           envelope(t0 + 0.1, t_in, t1, t_out)))
    return parts, o2


def t09_cta(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    size = int(min(H * 0.05, ctx.width * 0.06))
    pulse = f"(0.88+0.12*sin(2*PI*(t-{_num(t0)})/1.4))"
    o = ctx.label()
    parts = [f"[{inp}]drawtext={ctx.fontopt()}textfile='{ctx.textfile(smart_upper(ev.text))}':"
             f"expansion=none:fontsize={size}:fontcolor=0x111111:box=1:boxcolor={ctx.accent}:"
             f"boxborderw={int(size * 0.55)}:x='(w-tw)/2':y='h*0.66':"
             f"alpha='{envelope(t0, t_in, t1, t_out)}*{pulse}'[{o}]"]
    cur = o
    if ev.subtext:
        o2 = ctx.label()
        parts.append(_drawtext(ctx, cur, o2, ev.subtext, int(size * 0.55), "(w-tw)/2",
                               f"h*0.66+{int(size * 1.9)}", envelope(t0 + 0.2, t_in, t1, t_out)))
        cur = o2
    return parts, cur


def t10_speaker(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    size = int(H * 0.03)
    lay, lab = _alpha_layer(ctx, ctx.accent, max(4, W // 320), int(size * 1.6), t0, t_in, t1, t_out)
    o1, o2 = ctx.label(), ctx.label()
    parts = [lay, _overlay(inp, lab, o1, x=f"{int(W * 0.06)}", y=f"{int(H * 0.07)}"),
             _drawtext(ctx, o1, o2, smart_upper(ev.text), size, f"{int(W * 0.06) + 14}",
                       f"{int(H * 0.07) + int(size * 0.3)}", envelope(t0, t_in, t1, t_out),
                       extra=f"box=1:boxcolor=black@0.55:boxborderw={int(size * 0.3)}")]
    return parts, o2


def t11_type_on(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    H = ctx.height
    text = ev.text[:80]
    size = int(min(H * 0.06, ctx.width * 1.6 / max(12, len(text))))
    cps = 22.0
    parts, cur = [], inp
    n = len(text)
    for k in range(1, n + 1):
        a = t0 + (k - 1) / cps
        b = t0 + k / cps if k < n else t1
        o = ctx.label()
        shown = text[:k] + ("▍" if k < n else "")
        parts.append(f"[{cur}]drawtext={ctx.fontopt()}textfile='{ctx.textfile(shown)}':"
                     f"expansion=none:fontsize={size}:fontcolor={ctx.text_color}:"
                     f"x='(w-text_w)/2':y='(h-th)/2':"
                     f"alpha='{envelope(t0, 0.01, t1, t_out) if k == n else 1}':"
                     f"enable='between(t,{_num(a)},{_num(b)})'[{o}]")
        cur = o
    return parts, cur


def t12_end_card(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    W, H = ctx.width, ctx.height
    lay, lab = _alpha_layer(ctx, "0x0B0B0D", W, H, t0, t_in * 0.6, t1, t_out)
    cur = ctx.label()
    parts = [lay, _overlay(inp, lab, cur)]
    size = int(min(H * 0.075, W * 0.08))
    logo = ev.params.get("logo")
    if logo:
        from pathlib import Path
        if Path(logo).exists():
            lg, nxt = ctx.label("logo"), ctx.label()
            lh = int(H * 0.12)
            from ..features.paths import filter_path
            parts.append(f"movie=filename={filter_path(Path(logo).resolve())},scale=-2:{lh},"
                         f"format=yuva420p,loop=-1:1,trim=duration={_num(t1 - t0)},"
                         f"fade=t=in:st=0.2:d={_num(t_in)}:alpha=1,"
                         f"fade=t=out:st={_num(t1 - t0 - t_out)}:d={_num(t_out)}:alpha=1,"
                         f"setpts=PTS+{_num(t0)}/TB[{lg}]")
            parts.append(_overlay(cur, lg, nxt, x="(W-w)/2", y=f"H/2-{int(size * 1.6) + lh}"))
            cur = nxt
    o = ctx.label()
    parts.append(_drawtext(ctx, cur, o, ev.text, size, "(w-tw)/2",
                           f"(h-th)/2-{int(size * 0.3)}+{int(size * 0.3)}*(1-{ease_out(t0 + 0.2, t_in)})",
                           envelope(t0 + 0.2, t_in, t1, t_out)))
    cur = o
    if ev.subtext:
        o = ctx.label()
        parts.append(_drawtext(ctx, cur, o, ev.subtext, int(size * 0.42), "(w-tw)/2",
                               f"(h/2)+{int(size * 0.75)}", envelope(t0 + 0.45, t_in, t1, t_out),
                               color="0xBBBBBB"))
        cur = o
    cta = ev.params.get("cta")
    if cta:
        o = ctx.label()
        parts.append(_drawtext(ctx, cur, o, smart_upper(str(cta)), int(size * 0.38), "(w-tw)/2",
                               f"(h/2)+{int(size * 1.8)}", envelope(t0 + 0.7, t_in, t1, t_out),
                               color="0x111111",
                               extra=f"box=1:boxcolor={ctx.accent}:boxborderw={int(size * 0.25)}"))
        cur = o
    return parts, cur


BUILDERS = {
    "T01": t01_word_pop, "T02": t02_phrase_build, "T03": t03_pin_label, "T04": t04_counter,
    "T05": t05_price, "T06": t06_stat, "T07": t07_location, "T08": t08_info_bar,
    "T09": t09_cta, "T10": t10_speaker, "T11": t11_type_on, "T12": t12_end_card,
}

DEFINITIONS = [
    ("T01", "Word Pop", ["social", "dynamic"], (0.2, 2.6, 0.3)),
    ("T02", "Phrase Build", ["social", "minimal"], (0.5, 3.0, 0.5)),
    ("T03", "Pin Label", ["minimal", "corporate"], (0.4, 3.0, 0.4)),
    ("T04", "Counter Up", ["corporate", "dynamic"], (0.3, 3.0, 0.4)),
    ("T05", "Price Reveal", ["social", "corporate"], (0.3, 3.0, 0.4)),
    ("T06", "Stat Emphasis", ["corporate", "minimal"], (0.5, 3.0, 0.5)),
    ("T07", "Location Label", ["documentary", "minimal"], (0.6, 4.0, 0.5)),
    ("T08", "Minimal Info Bar", ["corporate", "minimal"], (0.5, 4.0, 0.5)),
    ("T09", "Call to Action", ["social", "corporate"], (0.4, 3.0, 0.4)),
    ("T10", "Speaker Label", ["editorial", "minimal"], (0.3, 3.0, 0.3)),
    ("T11", "Type-On", ["minimal", "social"], (0.2, 3.0, 0.4)),
    ("T12", "Signature End Card", ["cinematic", "corporate"], (0.8, 3.0, 0.6)),
]
