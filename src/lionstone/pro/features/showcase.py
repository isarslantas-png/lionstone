"""FX Showcase Reel (Studio) — turn any preset into a 6.4 s vertical "one command" reel.

The format: a dark Lionstone console, the command ``lionstone fx apply <preset>``
types itself, a suggestion card names the effect with its one-line promise, the
original clip dissolves through a two-tone pixel dither and the real render
scales up to fill the screen with an "Edited with Lionstone" pill.

Everything is FFmpeg: the "after" clip is rendered with the very same adapter
builder as the export, so the reel never shows a fake result.

    lionstone fx showcase stage-light talk.mp4 -o stage-light-reel.mp4
    python -m lionstone.pro.features.showcase stage-light talk.mp4   # same thing

Beats (1080x1920, 30 fps, 6.4 s = 192 frames):
  0.00–1.00  empty console, clip chip, blinking cursor
  1.00–2.50  command types in; suggestion card appears above the composer
  2.50–3.80  status line "Rendering …  REAL RENDER"; clip dissolves through the dither
  3.80–6.40  the finished clip scales up to full screen; pill fades in; hold
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

W, H, FPS, DUR = 1080, 1920, 30, 6.4
INK = "0x0F1014"
PANEL = "0x1A1C22"
LINE = "0x2A2D35"
GOLD = "0xE8A33D"
GREY = "0x8A8F98"
CARD_W, CARD_H = 640, 1138
CARD_Y = 210


def _line(desc: str) -> str:
    """The one-line promise is the part of the description before the em dash."""
    return desc.split(" — ")[0].strip() or desc[:60]


def _txt(wd: Path, name: str, text: str) -> str:
    p = wd / f"{name}.txt"
    p.write_text(text, encoding="utf-8")
    return p.name


def build_graph(slug: str, name: str, line: str, wd: Path, font: str | None,
                mono: str | None = None) -> str:
    from .paths import filter_path

    def dt(textfile, size, color, x, y, enable="1", fnt=None):
        f = fnt or font
        ff = f"fontfile={filter_path(f)}:" if f else ""
        return (f"drawtext={ff}textfile={textfile}:fontsize={size}:fontcolor={color}:"
                f"x='{x}':y='{y}':enable='{enable}'")

    cmd = f"lionstone fx apply {slug}"
    prefix = "lionstone fx apply "
    t0, t1 = 1.0, 2.5
    step = (t1 - t0 - 0.15) / len(cmd)
    typed = []
    for k in range(1, len(cmd) + 1):
        a = t0 + (k - 1) * step
        b = t0 + k * step if k < len(cmd) else 2.5
        gold, white = cmd[:min(k, len(prefix))], cmd[len(prefix):k]
        on = f"between(t,{a:.3f},{b:.3f})"
        typed.append(dt(_txt(wd, f"g{k}", gold), 38, GOLD, 120, 1702, on, mono))
        if white:  # monospace advance is 0.602 em
            typed.append(dt(_txt(wd, f"w{k}", white), 38, "white",
                            f"{120 + round(len(gold) * 38 * 0.602)}", 1702, on, mono))
    yshift = 1480
    ui = ",".join([
        # header
        f"drawbox=0:0:iw:150:color={INK}:t=fill",
        dt(_txt(wd, "brand", "LIONSTONE"), 34, "white", 80, 62),
        dt(_txt(wd, "fx", "FX"), 34, GOLD, 312, 62),
        dt(_txt(wd, "studio", "studio console"), 26, GREY, "w-tw-80", 68),
        f"drawbox=0:149:iw:2:color={LINE}:t=fill",
        # composer
        f"drawbox=80:1640:920:180:color={PANEL}:t=fill",
        f"drawbox=80:1640:920:180:color={LINE}:t=2",
        dt(_txt(wd, "ph", "type a command…"), 36, GREY, 120, 1700, "lt(t,1)"),
        f"drawbox=118:1696:4:46:color={GOLD}:t=fill:enable='lt(t,1)*lt(mod(t,0.8),0.4)'",
        f"drawbox=920:1760:56:44:color={GOLD}:t=fill:enable='lt(t,2.5)'",
        dt(_txt(wd, "go", "→"), 34, INK, 932, 1762, "lt(t,2.5)"),
        *typed,
        # suggestion card
        f"drawbox=80:{yshift}:920:130:color={PANEL}:t=fill:enable='between(t,1,2.5)'",
        dt(_txt(wd, "sname", name), 40, "white", 120, f"{yshift}+22", "between(t,1,2.5)"),
        dt(_txt(wd, "sline", line), 30, GREY, 120, f"{yshift}+78", "between(t,1,2.5)"),
        # status line
        dt(_txt(wd, "star", "✦"), 40, GOLD, 120, 1496, "between(t,2.5,3.8)"),
        dt(_txt(wd, "status", f"Rendering {name}…"), 34, "white", 175, 1500, "between(t,2.5,3.8)"),
        dt(_txt(wd, "real", "REAL RENDER"), 24, GREY, "w-tw-120", 1508, "between(t,2.5,3.8)"),
    ])
    # card animation: inside the console until 3.8 s, then scales up to full screen
    grow = "min(1,max(0,(t-3.8)/0.6))"
    ease = f"(1-pow(1-{grow},3))"
    cw = f"trunc(({CARD_W}+({W}-{CARD_W})*{ease})/2)*2"
    ch = f"trunc(({CARD_H}+({H}-{CARD_H})*{ease})/2)*2"
    pill = ("drawbox=(iw-480)/2:1730:480:84:color=black@0.72:t=fill:enable='gte(t,4.4)',"
            + dt(_txt(wd, "p1", "Edited with"), 34, "white", "(w-480)/2+52", 1752, "gte(t,4.4)") + ","
            + dt(_txt(wd, "p2", "Lionstone"), 34, GOLD, "(w-480)/2+282", 1752, "gte(t,4.4)"))
    return (
        f"color=c={INK}:s={W}x{H}:r={FPS}:d={DUR},format=rgba,{ui}[bg];"
        f"[0:v]scale={CARD_W}:{CARD_H}:force_original_aspect_ratio=increase,crop={CARD_W}:{CARD_H},"
        f"fps={FPS},setsar=1,format=gbrp[bef];"
        f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,"
        f"format=gbrp,split=2[aft][aftc];"
        f"[aftc]scale={CARD_W}:{CARD_H},format=gbrp[aftsm];"
        f"[bef][aftsm]overlay=0:0:enable='gte(t,3.0)':format=gbrp[mix];"
        f"[mix]DITHER[card0];"
        f"[card0]scale=w='{cw}':h='{ch}':eval=frame[card];"
        f"[bg][card]overlay=x='({W}-overlay_w)/2':y='{CARD_Y}*(1-{ease})':shortest=1[comp];"
        f"[comp][aft]overlay=0:0:enable='gte(t,4.4)':shortest=1,{pill},format=yuv420p[out]"
    )


def make_showcase(preset: str, clip: str, out: str, *, start: float = 0.0,
                  params: dict | None = None, check_entitlement: bool = True) -> Path:
    from lionstone.ff import font_path, run

    from . import entitlements
    from .catalog import Catalog
    from .params import resolve
    from .renderers import ffmpeg_adapter as fa

    cat = Catalog()
    p = cat.get(preset)
    if check_entitlement:
        entitlements.current().require("studio", "FX Showcase Reel")
    if p.kind != "effect" and p.kind != "look":
        raise ValueError("showcase reels support effect and look presets")
    if p.pipeline != "filter" or p.renderer_id not in fa.FILTERS:
        raise ValueError(f"{p.name} has no filter renderer for showcase reels")
    prm = resolve(p.parameters, params)
    wd = Path(tempfile.mkdtemp(prefix="lsreel-"))
    try:
        src = Path(clip).resolve()
        seg = ["-ss", f"{start:.3f}", "-t", f"{DUR:.3f}", "-i", str(src)]
        # 1) the real render ("after"), full frame, same builder as the export
        ctx = fa.RCtx(W, H, FPS, DUR)
        frag = fa.FILTERS[p.renderer_id](prm, [(0.0, DUR + 1)], ctx)
        (wd / "fx.txt").write_text(
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
            f"setsar=1,format=yuv420p[s];[s]{frag},format=yuv420p[o]", encoding="utf-8")
        from lionstone.render import _script_flag
        run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", *seg, _script_flag(), "fx.txt",
             "-map", "[o]", "-t", f"{DUR:.3f}", "-c:v", "libx264", "-crf", "16",
             "-preset", "veryfast", "after.mp4"], cwd=wd)
        # 2) the console reel, with the brand dither dissolve between before and after
        dither = fa.FILTERS.get("lionstone.pixel-resolve")
        dctx = fa.RCtx(CARD_W, CARD_H, FPS, DUR)
        dfrag = dither({"duration": 1.2, "tone_a": "#14161C", "tone_b": "#E8A33D"},
                       [(2.6, 3.8)], dctx) if dither else "null"
        graph = build_graph(p.id.split(".", 1)[1], p.name, _line(p.description), wd,
                            font_path(), font_path("DejaVu Sans Mono:style=Bold"))
        graph = graph.replace("DITHER", dfrag)
        (wd / "reel.txt").write_text(graph, encoding="utf-8")
        dst = Path(out).resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", *seg, "-i", "after.mp4",
             _script_flag(), "reel.txt", "-map", "[out]", "-t", f"{DUR:.3f}", "-r", str(FPS),
             "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(dst)], cwd=wd)
        return dst
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m lionstone.pro.features.showcase",
                                 description="[Studio] 6.4 s vertical one-command reel for a preset")
    ap.add_argument("preset", help="effect or look preset, e.g. stage-light")
    ap.add_argument("clip", help="talking-head clip (any aspect; cropped to 9:16)")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--start", type=float, default=0.0, help="start time in the clip (s)")
    ap.add_argument("--param", action="append", default=[], help="key=value preset parameter")
    a = ap.parse_args(argv)
    from .params import parse_cli
    out = a.output or f"{a.preset}-reel.mp4"
    path = make_showcase(a.preset, a.clip, out, start=a.start, params=parse_cli(a.param))
    print(f"reel → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
