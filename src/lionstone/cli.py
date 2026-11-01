"""`lionstone` command line."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__, textedit
from . import qa as qa_mod
from .effects import Catalog, EffectError
from .ff import FFmpegError, font_path, run
from .ingest import describe, probe
from .models import EditPlan, GraphicEvent
from .pipeline import ASROptions, make_plan, render_and_verify, replan_graphics
from .planner import EditOptions, parse_chapter, parse_speaker
from .plugins import registry
from .presets import ASPECTS, INTENSITIES, LOUDNESS
from .render import RenderOptions, render

BANNER = "🦁 Lionstone — AI editing agent · v" + __version__


def _catalog() -> Catalog:
    return Catalog(registry().effect_dirs)


# --- shared option groups --------------------------------------------------------------
def _add_edit_options(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("editing")
    g.add_argument("--intensity", choices=list(INTENSITIES), default="balanced",
                   help="natural · balanced (default) · dynamic")
    g.add_argument("--profile", choices=list(LOUDNESS), default="youtube",
                   help="loudness target: youtube -14 · podcast -16 · social -14 · broadcast -23 LUFS")
    g.add_argument("--aspect", choices=list(ASPECTS), help="output aspect (default: keep source)")
    g = p.add_argument_group("speech recognition")
    g.add_argument("--model", default="small", help="faster-whisper model (tiny…large-v3)")
    g.add_argument("--language", help="force language code, e.g. tr, en")
    g.add_argument("--transcript", help="use an existing word-timestamp JSON instead of ASR")
    g.add_argument("--no-asr", action="store_true", help="signal-only editing (silences)")
    g = p.add_argument_group("graphics")
    g.add_argument("--title", default="", help="opening title")
    g.add_argument("--subtitle", default="", help="line under the opening title")
    g.add_argument("--outro", default="", help="closing card text")
    g.add_argument("--speaker", action="append", default=[], metavar='"Name|Title[|LABEL]"',
                   help="lower third for a speaker (repeatable)")
    g.add_argument("--chapter", action="append", default=[], metavar='"00:05:10 Title"',
                   help="chapter card at a source timecode (repeatable)")
    g.add_argument("--title-effect", default="F01")
    g.add_argument("--chapter-effect", default="F04")
    g.add_argument("--lower-third-effect", default="F05")
    g.add_argument("--accent", default="#E8B04B", help="brand accent color")
    g.add_argument("--font", help="font file or fontconfig name for titles")
    g = p.add_argument_group("look & sound")
    g.add_argument("--captions", choices=["burn", "file", "none"], default="burn")
    g.add_argument("--caption-style", default="clean", help="clean · bold · social (+ plugins)")
    g.add_argument("--color", default="natural", help="none · natural · warm · cool · punchy · film")
    g.add_argument("--lut", help=".cube LUT applied after correction")
    g.add_argument("--denoise", choices=["off", "light", "strong"], default="light")
    g.add_argument("--reframe", default="center",
                   help="aspect reframing: center · face (needs OpenCV)")
    g.add_argument("--renderer", choices=["auto", "ffmpeg", "remotion"], default="auto",
                   help="title renderer: Remotion when installed, FFmpeg otherwise")
    p.add_argument("--x", action="append", default=[], metavar="KEY=VALUE",
                   help="plugin option, e.g. --x style=mystyle.json")


def _edit_options(a: argparse.Namespace) -> EditOptions:
    return EditOptions(
        intensity=a.intensity, profile=a.profile, aspect=a.aspect, title=a.title,
        subtitle=a.subtitle, outro=a.outro,
        speakers=[parse_speaker(s) for s in a.speaker],
        chapters=[parse_chapter(c) for c in a.chapter],
        captions=a.captions, caption_style=a.caption_style, color=a.color, lut=a.lut,
        denoise=a.denoise, title_effect=a.title_effect, chapter_effect=a.chapter_effect,
        lower_third_effect=a.lower_third_effect, outro_effect=a.title_effect,
        accent=a.accent, font=a.font,
        extras=dict(kv.split("=", 1) for kv in a.x if "=" in kv),
    )


def _render_options(a: argparse.Namespace, opts: EditOptions | None = None) -> RenderOptions:
    o = opts
    return RenderOptions(
        aspect=getattr(a, "aspect", None) or (o.aspect if o else None),
        captions=getattr(a, "captions", None) or (o.captions if o else "burn"),
        caption_style=getattr(a, "caption_style", None) or (o.caption_style if o else "clean"),
        denoise=getattr(a, "denoise", None) or (o.denoise if o else "light"),
        crf=getattr(a, "crf", 18), preset="veryfast" if getattr(a, "fast", False) else "medium",
        font=getattr(a, "font", None) or (o.font if o else None),
        accent=getattr(a, "accent", None) or (o.accent if o else "#E8B04B"),
        reframe=getattr(a, "reframe", "center"),
        renderer=getattr(a, "renderer", "auto"),
    )


def _check_tiers(opts: EditOptions, catalog: Catalog) -> None:
    tiers = registry().tiers
    for fid in {opts.title_effect, opts.chapter_effect, opts.lower_third_effect}:
        fx = catalog.get(fid)
        if fx.tier not in tiers:
            raise EffectError(
                f"{fx.id} {fx.name} is a {fx.tier.upper()} effect. Free effects: "
                f"{', '.join(e.id for e in catalog.filter(tier='free'))}. "
                "Run `lionstone doctor` to see which features are available.")


# --- commands ------------------------------------------------------------------------
def cmd_edit(a: argparse.Namespace, plan_only: bool = False) -> int:
    src = Path(a.input)
    outdir = Path(a.out or f"{src.stem}_lionstone")
    outdir.mkdir(parents=True, exist_ok=True)
    opts = _edit_options(a)
    catalog = _catalog()
    _check_tiers(opts, catalog)
    asr = ASROptions(mode="none" if a.no_asr else "auto", model=a.model, language=a.language,
                     transcript=a.transcript)
    print(BANNER)
    plan = make_plan(src, outdir, opts, asr, catalog=catalog)
    if plan_only:
        print(f"\nPlan → {outdir / 'plan.json'}" + (
            f"\nEdit by text → {outdir / 'transcript.md'}" if plan.words else ""))
        return 0
    res, report = render_and_verify(plan, outdir, f"{src.stem}.edit.mp4", _render_options(a, opts),
                                    catalog=catalog)
    print(f"\nDelivered → {res.output}")
    for v in res.captions.values():
        print(f"            {v}")
    print(f"QA report → {outdir / 'qa.md'}")
    return 0 if report.deliverable else 2


def cmd_render(a: argparse.Namespace) -> int:
    plan = EditPlan.load(a.plan)
    outdir = Path(a.plan).parent
    from .pipeline import options_from_meta
    opts = options_from_meta(plan)
    if a.no_qa:
        res = render(plan, a.output or outdir / (Path(plan.source).stem + ".edit.mp4"),
                     _render_options(a, opts), catalog=_catalog(), workdir=outdir / ".lionstone")
        print(f"Rendered → {res.output} (QA skipped — not verified)")
        return 0
    name = Path(a.output).name if a.output else Path(plan.source).stem + ".edit.mp4"
    res, report = render_and_verify(plan, Path(a.output).parent if a.output else outdir, name,
                                    _render_options(a, opts), catalog=_catalog())
    return 0 if report.deliverable else 2


def cmd_transcript(a: argparse.Namespace) -> int:
    plan = EditPlan.load(a.plan)
    if not plan.words:
        print("This plan has no transcript (signal-only edit).", file=sys.stderr)
        return 1
    out = Path(a.output or Path(a.plan).parent / "transcript.md")
    textedit.write(plan, out)
    plan.save(a.plan)
    print(f"Transcript → {out}\nEdit it, then: lionstone apply-transcript {a.plan} {out}")
    return 0


def cmd_apply_transcript(a: argparse.Namespace) -> int:
    plan = EditPlan.load(a.plan)
    stats = textedit.apply(plan, Path(a.transcript).read_text(encoding="utf-8"))
    replan_graphics(plan, _catalog())
    plan.save(a.plan)
    print(f"Applied: {stats['deleted']} sentences cut, {stats['restored']} cuts restored"
          f"{', order changed' if stats['reordered'] else ''}. "
          f"New length {plan.output_duration:.1f}s.\nRender: lionstone render {a.plan}")
    return 0


def cmd_cuts(a: argparse.Namespace) -> int:
    plan = EditPlan.load(a.plan)
    if a.restore or a.disable:
        ids = set(a.restore or []) | set(a.disable or [])
        for c in plan.cuts:
            if c.id in ids:
                c.enabled = bool(a.disable and c.id in a.disable)
        from .speech import segments_from_cuts
        plan.segments = segments_from_cuts(plan.cuts, plan.duration, plan.words)
        replan_graphics(plan, _catalog())
        plan.save(a.plan)
    print(f"{'id':6} {'on':3} {'source':>17} {'len':>6}  kind         reason")
    for c in plan.cuts:
        print(f"{c.id:6} {'✓' if c.enabled else '·':3} {c.start:8.2f}–{c.end:<8.2f} "
              f"{c.duration:5.2f}s  {c.kind:12} {c.reason}")
    print(f"\n{plan.duration:.1f}s → {plan.output_duration:.1f}s · "
          "restore with: lionstone cuts plan.json --restore c0003 c0007")
    return 0


def cmd_qa(a: argparse.Namespace) -> int:
    plan = EditPlan.load(a.plan) if a.plan else None
    r = qa_mod.run_qa(a.video, plan, catalog=_catalog())
    outdir = Path(a.video).parent
    j, m = qa_mod.save(r, outdir, Path(a.video).stem + ".qa")
    print(qa_mod.to_markdown(r))
    print(f"→ {m}\n→ {j}")
    return 0 if r.deliverable else 2


def cmd_probe(a: argparse.Namespace) -> int:
    info = probe(a.input)
    print(json.dumps(info.__dict__, default=lambda o: o.__dict__, indent=2) if a.json
          else describe(info))
    return 0


def cmd_effects(a: argparse.Namespace) -> int:
    cat = _catalog()
    tiers = registry().tiers
    if a.action == "list":
        for e in cat.filter(category=a.category, style=a.style, tier=a.tier):
            lock = "" if e.tier in tiers else "  🔒"
            print(f"{e.id:4} {e.tier.upper():6} {e.name:26} {e.category:12} "
                  f"{'/'.join(e.style):28} {e.total:.1f}s{lock}")
        return 0
    if a.action == "show":
        e = cat.get(a.id)
        print(json.dumps({k: v for k, v in e.__dict__.items() if k != "source"},
                         indent=2, ensure_ascii=False))
        return 0
    # preview: render the effect over a neutral backdrop with FFmpeg
    e = cat.get(a.id)
    from .ff import has_filter
    if not has_filter("drawtext"):
        print("This FFmpeg build has no `drawtext` (libfreetype). Install a full build "
              "(e.g. `conda install -c conda-forge ffmpeg`) or preview in Remotion: "
              "cd remotion && npm install && npm run studio", file=sys.stderr)
        return 1
    out = Path(a.output or f"preview-{e.id}.mp4").resolve()
    wd = out.parent / ".lionstone-preview"
    wd.mkdir(parents=True, exist_ok=True)
    from .effects.ffmpeg_fx import FxContext, build_graphics
    W, H = (1280, 720) if not a.vertical else (720, 1280)
    total = e.total + 0.8
    ev = GraphicEvent(id="preview", effect=e.id, at=0.3, duration=e.total,
                      text=a.text or e.name, subtext=a.subtext or "", params={"number": 1})
    ctx = FxContext(W, H, 30, font_path(a.font), wd, accent=a.accent.replace("#", "0x"))
    bg = (f"gradients=s={W}x{H}:c0=0x2b3a4a:c1=0x6b4e3d:x0=0:y0=0:x1={W}:y1={H}:d={total}:r=30:speed=0.002"
          if not a.background else None)
    parts, last, _ = build_graphics([ev], cat, "bg", ctx, tiers | {"pro", "studio"} if a.force
                                    else tiers)
    graph = ";".join(parts)
    inputs = ["-f", "lavfi", "-i", bg] if bg else ["-stream_loop", "-1", "-i",
                                                    str(Path(a.background).resolve())]
    (wd / "g.txt").write_text(f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                              f"crop={W}:{H},fps=30,format=yuv420p[bg];{graph}", encoding="utf-8")
    from .render import _script_flag
    run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", *inputs, "-t", f"{total:.2f}",
         _script_flag(), "g.txt", "-map", f"[{last}]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "20", str(out)], cwd=wd)
    if a.gif:
        gif = out.with_suffix(".gif")
        run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-i", str(out), "-vf",
             "fps=15,scale=640:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];"
             "[b][p]paletteuse=dither=bayer:bayer_scale=4", str(gif)])
        print(f"Preview → {gif}")
    print(f"Preview → {out}")
    shutil.rmtree(wd, ignore_errors=True)
    return 0


def cmd_doctor(a: argparse.Namespace) -> int:
    print(BANNER)
    ok = True

    def line(good: bool, name: str, detail: str) -> None:
        print(f"  {'✅' if good else '⚠️ '} {name:18} {detail}")

    ff = shutil.which("ffmpeg")
    if ff:
        ver = (run(["ffmpeg", "-hide_banner", "-version"], check=False).stdout or "").splitlines()[0]
        flt = run(["ffmpeg", "-hide_banner", "-filters"], check=False).stdout or ""
        line(True, "ffmpeg", ver)
        for f in ("drawtext", "subtitles", "loudnorm", "ebur128", "afftdn", "lut3d"):
            has = f" {f} " in flt
            ok &= has or f in ("lut3d",)
            line(has, f"  filter {f}", "available" if has else "missing — install a full FFmpeg build")
    else:
        ok = False
        line(False, "ffmpeg", "not found")
    try:
        import faster_whisper  # noqa: F401
        line(True, "faster-whisper", "installed")
    except ImportError:
        line(False, "faster-whisper", 'optional — pip install "lionstone[whisper]"')
    line(bool(font_path()), "title font", font_path() or "no font found — pass --font")
    line(bool(shutil.which("node")), "node (Remotion)", shutil.which("node") or
         "optional — needed only for Remotion previews/renders")
    reg = registry()
    line(True, "edition", "Lionstone Pro & Studio (every feature unlocked)")
    for p in reg.loaded:
        line(p["status"] == "ok", f"plugin {p['name']}", p["status"])
    if not reg.loaded:
        line(True, "plugins", "none")
    return 0 if ok else 1


def cmd_mcp(a: argparse.Namespace) -> int:
    from .mcp_server import main as mcp_main
    mcp_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lionstone", description=BANNER,
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Quick start:  lionstone edit podcast.mp4 --title \"Episode 12\"")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("edit", help="analyze → plan → render → QA in one go")
    e.add_argument("input")
    e.add_argument("-o", "--out", help="output folder (default: <name>_lionstone)")
    e.add_argument("--fast", action="store_true", help="faster encode (veryfast preset)")
    e.add_argument("--crf", type=int, default=18)
    _add_edit_options(e)
    e.set_defaults(fn=cmd_edit)

    pl = sub.add_parser("plan", help="analyze and write plan.json + transcript.md (no render)")
    pl.add_argument("input")
    pl.add_argument("-o", "--out")
    _add_edit_options(pl)
    pl.set_defaults(fn=lambda a: cmd_edit(a, plan_only=True))

    r = sub.add_parser("render", help="render a plan.json (then QA)")
    r.add_argument("plan")
    r.add_argument("-o", "--output")
    r.add_argument("--fast", action="store_true")
    r.add_argument("--crf", type=int, default=18)
    r.add_argument("--no-qa", action="store_true")
    r.add_argument("--renderer", choices=["auto", "ffmpeg", "remotion"], default="auto")
    r.set_defaults(fn=cmd_render)

    t = sub.add_parser("transcript", help="export transcript.md for text-based editing")
    t.add_argument("plan")
    t.add_argument("-o", "--output")
    t.set_defaults(fn=cmd_transcript)

    at = sub.add_parser("apply-transcript", help="apply an edited transcript.md to the plan")
    at.add_argument("plan")
    at.add_argument("transcript")
    at.set_defaults(fn=cmd_apply_transcript)

    c = sub.add_parser("cuts", help="list cuts with reasons; restore or disable them")
    c.add_argument("plan")
    c.add_argument("--restore", nargs="+", metavar="ID", help="bring cut material back")
    c.add_argument("--disable", nargs="+", metavar="ID", help="re-enable (cut again)")
    c.set_defaults(fn=cmd_cuts)

    q = sub.add_parser("qa", help="run technical + editorial QA on a video")
    q.add_argument("video")
    q.add_argument("--plan", help="plan.json for editorial checks")
    q.set_defaults(fn=cmd_qa)

    pr = sub.add_parser("probe", help="inspect media metadata and warnings")
    pr.add_argument("input")
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(fn=cmd_probe)

    fx = sub.add_parser("effects", help="browse and preview the effect catalog")
    fx.add_argument("action", choices=["list", "show", "preview"])
    fx.add_argument("id", nargs="?")
    fx.add_argument("--category")
    fx.add_argument("--style")
    fx.add_argument("--tier", default="all", choices=["free", "pro", "studio", "all"])
    fx.add_argument("--text")
    fx.add_argument("--subtext")
    fx.add_argument("--background", help="video/image to preview on")
    fx.add_argument("--vertical", action="store_true")
    fx.add_argument("--accent", default="#E8B04B")
    fx.add_argument("--font")
    fx.add_argument("--gif", action="store_true", help="also write a GIF")
    fx.add_argument("-o", "--output")
    fx.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    fx.set_defaults(fn=cmd_effects)

    d = sub.add_parser("doctor", help="check FFmpeg, ASR, fonts and plugins")
    d.set_defaults(fn=cmd_doctor)

    m = sub.add_parser("mcp", help="run as an MCP server (Claude, Cursor, any MCP client)")
    m.set_defaults(fn=cmd_mcp)

    for name, command in registry().commands.items():
        sp = sub.add_parser(name, help=command.help)
        command.configure(sp)
        sp.set_defaults(fn=command.run)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    a = parser.parse_args(argv)
    if a.cmd == "effects" and a.action in ("show", "preview") and not a.id:
        parser.error("effects show/preview needs an effect id, e.g. F01")
    try:
        return int(a.fn(a) or 0)
    except (FFmpegError, EffectError, FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"lionstone: error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
