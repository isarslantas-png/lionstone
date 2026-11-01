"""Real previews: the same adapter builders as the final render, at low resolution.

* effects / looks / motion — applied to the window [0.4 s, end-0.4 s]
* transitions — two different shots joined at the midpoint, transition on the cut
* text — rendered through the core graphics builders (same as export)

Locked presets may be previewed with a visible watermark; they can't be
rendered into a deliverable (see compile.py). Previews are labelled as
low-resolution so they're never mistaken for the export.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from lionstone.ff import font_path, has_filter, run
from lionstone.models import GraphicEvent

from .catalog import Catalog
from .entitlements import Entitlement
from .params import resolve
from .renderers import ffmpeg_adapter as fa


class PreviewError(RuntimeError):
    pass


def _label(ctx_font: str | None, text: str, x: str, y: str, size: int, color="white") -> str:
    if not has_filter("drawtext"):  # FFmpeg without libfreetype (e.g. some Homebrew builds)
        return "null"
    from .paths import filter_path
    font = f"fontfile={filter_path(ctx_font)}:" if ctx_font else ""
    safe = text.replace("'", "").replace(":", " ").replace(",", " ").replace("%", "")
    return (f"drawtext={font}text='{safe}':fontsize={size}:fontcolor={color}:x={x}:y={y}:"
            f"box=1:boxcolor=black@0.55:boxborderw=6")


def build_preview_graph(preset_id: str, catalog: Catalog, ent: Entitlement, *,
                        params: dict | None, width: int, height: int, fps: float,
                        seconds: float, before_after: bool, workdir: Path) -> tuple[str, list[str]]:
    p = catalog.get(preset_id)
    if not p.usable:
        raise PreviewError(f"{p.name} is {p.implementationStatus}: {'; '.join(p.limitations)}")
    rid = p.renderer_id
    prm = resolve(p.parameters, params)
    ctx = fa.RCtx(width, height, fps, seconds)
    notes: list[str] = []
    font = font_path()
    win = [(0.4, max(0.8, seconds - 0.4))]
    if p.kind == "transition":
        tj = seconds / 2
        d = min(prm.get("frames", 12) / fps, seconds * 0.8)
        frag = ""
        if rid in fa.JOIN_TRANSFORMS:
            frag = fa.merge_transforms(fa.JOIN_TRANSFORMS[rid](prm, [(tj, d)], ctx), ctx)
        if rid in fa.JOIN_FILTERS:
            frag = ",".join(x for x in (frag, fa.JOIN_FILTERS[rid](prm, [(tj, d)], ctx)) if x)
        frag = frag or "null"
    elif p.kind == "text":
        if not has_filter("drawtext"):
            raise PreviewError(f"{p.name}: this FFmpeg build has no drawtext (libfreetype); "
                               "install a full FFmpeg build to preview text presets")
        from lionstone.effects import Catalog as CoreCatalog
        from lionstone.effects.ffmpeg_fx import FxContext, build_graphics, register_builder
        from lionstone.plugins import registry

        from ..fx.text_builders import BUILDERS as TEXT_BUILDERS
        # make the text builders available to the preview
        for fid, fn in TEXT_BUILDERS.items():
            register_builder(fid, fn)
        dirs = list(registry().effect_dirs)  # built-in catalog incl. pro-text
        core = CoreCatalog(dirs)
        ev = GraphicEvent(id="pv", effect=p.graphicEffect, at=0.3,
                          duration=max(1.5, seconds - 0.6), text=prm.get("text", ""),
                          subtext=prm.get("subtext", ""),
                          params={k: v for k, v in prm.items()
                                  if k not in ("text", "subtext", "duration")} | {"number": 1})
        fctx = FxContext(width, height, fps, font, workdir)
        parts, last, log = build_graphics([ev], core, "pvin", fctx, ent.tiers | {"pro", "studio"})
        notes += fctx.notes
        tag = f"{width}px preview" if ent.allows(p.tier) else f"LOCKED {p.tier.upper()} PREVIEW"
        lab = _label(font, tag, "w-tw-12", "h-th-12", max(12, height // 28))
        return ";".join(["[0:v]null[pvin]", *parts, f"[{last}]{lab}[pvout]"]), notes
    elif p.pipeline == "transform":
        frag = fa.merge_transforms(fa.TRANSFORMS[rid](prm, win, ctx), ctx)
        if rid in fa.COMPANION_FILTERS:
            frag += "," + fa.COMPANION_FILTERS[rid](prm, win, ctx)
    elif rid in fa.FILTERS:
        frag = fa.FILTERS[rid](prm, win, ctx)
    else:
        raise PreviewError(f"{p.name}: no preview renderer")

    tag = f"{width}px preview"
    if not has_filter("drawtext"):
        notes.append("preview label omitted: this FFmpeg build has no drawtext")
    if not ent.allows(p.tier):
        tag = f"LOCKED {p.tier.upper()} PREVIEW"
        notes.append(f"{p.name} needs {p.tier.title()}: watermarked preview only")
    if before_after:
        g = (f"[0:v]split=2[pvA][pvB];[pvB]{frag},null[pvB2];"
             f"[pvA]{_label(font, 'Before', '12', '12', max(14, height // 22))}[pvA2];"
             f"[pvB2]{_label(font, 'After', '12', '12', max(14, height // 22))}[pvB3];"
             f"[pvA2][pvB3]hstack=2,{_label(font, tag, 'w-tw-12', 'h-th-12', max(12, height // 28))}"
             f"[pvout]")
    else:
        g = (f"[0:v]{frag},null,{_label(font, tag, 'w-tw-12', 'h-th-12', max(12, height // 28))}"
             f"[pvout]")
    return g, notes


def render_preview(preset_id: str, out: Path, catalog: Catalog, ent: Entitlement, *,
                   input_path: str | None = None, start: float = 0.0, seconds: float = 4.0,
                   params: dict | None = None, width: int = 640, before_after: bool = False,
                   gif: bool = False) -> dict:
    p = catalog.get(preset_id)
    height = int(round(width * 9 / 16 / 2) * 2)
    fps = 25.0
    wd = Path(tempfile.mkdtemp(prefix="lsfx-"))
    try:
        graph, notes = build_preview_graph(preset_id, catalog, ent, params=params, width=width,
                                           height=height, fps=fps, seconds=seconds,
                                           before_after=before_after, workdir=wd)
        (wd / "g.txt").write_text(graph, encoding="utf-8")
        if input_path:
            src = ["-ss", f"{start:.3f}", "-t", f"{seconds:.3f}", "-i",
                   str(Path(input_path).resolve())]
            pre = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                   f"crop={width}:{height},fps={fps},setsar=1")
            if p.kind == "transition":
                half = seconds / 2
                src = ["-ss", f"{start:.3f}", "-t", f"{half:.3f}", "-i",
                       str(Path(input_path).resolve()), "-ss", f"{start + seconds:.3f}", "-t",
                       f"{half:.3f}", "-i", str(Path(input_path).resolve())]
        else:
            if p.kind == "transition":
                half = seconds / 2
                src = ["-f", "lavfi", "-i", f"testsrc2=s={width}x{height}:r={fps}:d={half}",
                       "-f", "lavfi", "-i", f"smptehdbars=s={width}x{height}:r={fps}:d={half}"]
            else:
                src = ["-f", "lavfi", "-i", f"testsrc2=s={width}x{height}:r={fps}:d={seconds}"]
            pre = "setsar=1"
        if p.kind == "transition":
            head = (f"[0:v]{pre}[pv0];[1:v]{pre}[pv1];[pv0][pv1]concat=n=2:v=1:a=0,"
                    f"format=yuv420p[pvsrc];")
            graph = head + graph.replace("[0:v]", "[pvsrc]", 1)
        else:
            graph = f"[0:v]{pre},format=yuv420p[pvsrc];" + graph.replace("[0:v]", "[pvsrc]", 1)
        (wd / "g.txt").write_text(graph, encoding="utf-8")
        from lionstone.render import _script_flag
        out = Path(out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", *src, _script_flag(), "g.txt",
             "-map", "[pvout]", "-t", f"{seconds:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-crf", "23", "-preset", "veryfast", str(out)], cwd=wd)
        result = {"video": str(out), "notes": notes, "lowres": True, "width": width}
        if gif:
            g = out.with_suffix(".gif")
            run(["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-i", str(out), "-vf",
                 "fps=12,scale=480:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];"
                 "[b][p]paletteuse=dither=none", str(g)])
            result["gif"] = str(g)
        return result
    finally:
        shutil.rmtree(wd, ignore_errors=True)
