"""Renderer — executes an EditPlan with FFmpeg. Makes no editorial decisions.

One pass, sample-accurate: trim/atrim per kept segment snapped to the frame
grid, 8 ms audio micro-fades at every join (no clicks), concat, constant
frame rate, color, titles, captions, then two-pass EBU R128 loudness.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .captions import write_captions
from .color import color_chain, measure_luma
from .effects import Catalog
from .effects.ffmpeg_fx import FxContext, build_graphics
from .ff import font_path, has_filter, run
from .ingest import probe
from .models import EditPlan, MediaInfo
from .plugins import registry
from .presets import ASPECTS, LOUDNESS

FADE = 0.008  # seconds of audio fade at each join


@dataclass
class RenderOptions:
    aspect: str | None = None
    captions: str = "burn"  # burn | file | none
    caption_style: str = "clean"
    denoise: str = "light"
    crf: int = 18
    preset: str = "medium"
    font: str | None = None
    accent: str = "#E8B04B"
    reframe: str = "center"  # center | <plugin modes, e.g. "face">
    renderer: str = "auto"  # auto | ffmpeg | remotion  (titles/lower thirds)
    extra_video_filters: list[str] = field(default_factory=list)


@dataclass
class RenderResult:
    output: Path
    width: int
    height: int
    fps: float
    duration: float
    captions: dict[str, str]
    loudness_target: dict
    graphics_log: list[dict]
    notes: list[str]
    color: dict

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["output"] = str(self.output)
        return d


def _ffmpeg_major() -> int:
    out = run(["ffmpeg", "-hide_banner", "-version"], check=False).stdout or ""
    m = re.search(r"ffmpeg version n?(\d+)", out)
    return int(m.group(1)) if m else 6


def _script_flag() -> str:
    return "-/filter_complex" if _ffmpeg_major() >= 8 else "-filter_complex_script"


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _snap(plan: EditPlan, fps: float) -> list[tuple[float, float]]:
    return [(a, b) for a, b, _ in _snap_src(plan, fps)]


def _snap_src(plan: EditPlan, fps: float) -> list[tuple[float, float, str]]:
    out = []
    for s in plan.segments:
        a = round(s.start * fps) / fps
        b = round(s.end * fps) / fps
        if b - a >= 1 / fps:
            out.append((a, b, s.source))
    return out


def video_sources(plan: EditPlan) -> dict[str, dict]:
    """Extra camera sources of a multi-source plan: {id: {path, offset, input}}.

    Segment times live on the master (audio) timeline; a camera's frame for
    master time t is at t + offset in its own file. Inputs 1..n in order.
    """
    srcs = plan.meta.get("sources") or {}
    out: dict[str, dict] = {}
    for i, (sid, d) in enumerate(sorted(srcs.items())):
        out[sid] = {"path": d["path"], "offset": float(d.get("offset", 0.0)), "input": i + 1}
    return out


def _denoise(level: str) -> str:
    return {
        "off": "",
        "light": "afftdn=nr=8:nf=-45:tn=1",
        "strong": "afftdn=nr=16:nf=-40:tn=1,anlmdn=s=0.0005",
    }.get(level, "")


def output_geometry(info: MediaInfo, aspect: str | None) -> tuple[int, int, float]:
    v = info.video
    fps = (v.avg_fps or v.fps or 30.0) if v else 30.0
    fps = min(max(fps, 12.0), 120.0)
    if aspect:
        w, h = ASPECTS[aspect]
    elif v and v.width and v.height:
        w, h = _even(v.width), _even(v.height)
    else:
        w, h = 1920, 1080
    return w, h, round(fps, 3)


def build_graph(plan: EditPlan, info: MediaInfo, opts: RenderOptions, workdir: Path,
                *, catalog: Catalog, loudnorm: str, audio_only: bool = False,
                prerendered: dict[str, int] | None = None) -> tuple[str, dict]:
    prerendered = prerendered or {}
    reg = registry()
    W, H, fps = output_geometry(info, opts.aspect)
    has_video = info.video is not None
    segs_src = _snap_src(plan, fps)
    segs = [(a, b) for a, b, _ in segs_src]
    if not segs:
        raise ValueError("edit plan keeps nothing — check cuts or restore some")
    cams = video_sources(plan)
    multi = bool(cams)
    has_video = has_video or multi
    parts: list[str] = []
    labels: list[str] = []
    for i, (a, b, src) in enumerate(segs_src):
        dur = b - a
        fade_out = max(0.0, dur - FADE)
        if has_video and not audio_only:
            cam = cams.get(src)
            if cam:
                off = cam["offset"]
                parts.append(f"[{cam['input']}:v]trim=start={a + off:.6f}:end={b + off:.6f},"
                             f"setpts=PTS-STARTPTS,fps={fps},scale={W}:{H}:"
                             f"force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v{i}]")
            elif multi:
                parts.append(f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS,"
                             f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,"
                             f"crop={W}:{H},setsar=1[v{i}]")
            else:
                parts.append(f"[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS[v{i}]")
            labels.append(f"[v{i}]")
        # apad: a segment that runs past the end of the source audio (audio shorter than
        # video) is padded with silence so audio and video keep the same length.
        parts.append(
            f"[0:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,"
            f"apad=whole_dur={dur:.6f},"
            f"afade=t=in:d={FADE}:curve=qsin,afade=t=out:st={fade_out:.6f}:d={FADE}:curve=qsin[a{i}]"
        )
        labels.append(f"[a{i}]")
    n = len(segs)
    v_on = 1 if (has_video and not audio_only) else 0
    parts.append(f"{''.join(labels)}concat=n={n}:v={v_on}:a=1" + ("[vc][ac]" if v_on else "[ac]"))

    # ---- audio ----------------------------------------------------------
    achain = ["aresample=48000", "highpass=f=70"]
    if _denoise(opts.denoise):
        achain.append(_denoise(opts.denoise))
    achain += [loudnorm, "aresample=48000"]
    meta: dict = {"W": W, "H": H, "fps": fps, "segments": n, "graphics_log": [], "notes": [],
                  "color": {}}
    if audio_only:
        parts.append(f"[ac]{','.join(achain)}[aout]")
        return ";\n".join(parts), meta
    total = sum(b - a for a, b in segs)
    if not v_on:  # audio-only podcast → audiogram
        parts.append(f"[ac]{','.join(achain)},asplit=2[aout][awave]")
        parts.append(f"color=c=0x111114:s={W}x{H}:r={fps}:d={total:.3f}[bg]")
        parts.append(f"[awave]showwaves=s={W}x{H // 3}:mode=cline:rate={fps}:colors=0xE8B04B,"
                     f"format=yuva420p[wave]")
        parts.append("[bg][wave]overlay=0:(H-h)/2:shortest=1[vc]")
        meta["notes"].append("no video stream: rendered an audiogram")
    else:
        parts.append(f"[ac]{','.join(achain)}[aout]")

    # ---- video ------------------------------------------------------------
    vchain = [f"fps={fps}"]
    v = info.video
    if v_on and v and not multi and (v.width, v.height) != (W, H):
        mode = opts.reframe
        if mode in reg.reframers:
            vchain.append(reg.reframers[mode](plan=plan, info=info, W=W, H=H, workdir=workdir))
        else:
            vchain.append(f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
    vchain.append("setsar=1")
    if v_on:
        cf, cinfo = color_chain(plan.color.get("preset", "natural"), plan.color.get("lut"),
                                workdir, measure_luma(plan.source, plan.duration)
                                if plan.color.get("preset", "natural") != "none" else None)
        meta["color"] = cinfo
        if cf:
            vchain.append(cf)
        if plan.color.get("filter"):  # e.g. a learned style look (plugins)
            vchain.append(plan.color["filter"])
            cinfo["style_filter"] = plan.color["filter"]
    vchain += opts.extra_video_filters
    vchain.append("format=yuv420p")
    parts.append(f"[vc]{','.join(vchain)}[vb]")
    cur = "vb"

    if plan.graphics:
        native, glog = [], []
        for ev in plan.graphics:
            if ev.id in prerendered:  # Remotion clip with alpha, input index k
                k = prerendered[ev.id]
                g, nxt = f"g{k}", f"gv{k}"
                parts.append(f"[{k}:v]fps={fps},format=yuva420p,"
                             f"setpts=PTS-STARTPTS+{ev.at:.3f}/TB[{g}]")
                parts.append(f"[{cur}][{g}]overlay=eof_action=pass:format=auto[{nxt}]")
                cur = nxt
                glog.append({"event": ev.id, "effect": ev.effect, "status": "rendered",
                             "engine": "remotion"})
            else:
                native.append(ev)
        if native and not has_filter("drawtext"):
            # Safe default (spec §3.8): never fail the whole render over a title.
            for ev in native:
                glog.append({"event": ev.id, "effect": ev.effect, "status": "skipped",
                             "detail": "FFmpeg build has no drawtext (libfreetype) and "
                                       "Remotion is not set up"})
            meta["notes"].append(f"{len(native)} graphic(s) not rendered: this FFmpeg lacks "
                                 "`drawtext`. Install a full FFmpeg build or set up Remotion.")
        elif native:
            ctx = FxContext(width=W, height=H, fps=fps, font=font_path(opts.font),
                            workdir=workdir, accent=opts.accent.replace("#", "0x"))
            gparts, cur, nlog = build_graphics(native, catalog, cur, ctx, reg.tiers)
            parts += gparts
            glog += nlog
            meta["notes"] += ctx.notes
        meta["graphics_log"] = glog

    burn = opts.captions == "burn" and plan.words
    if burn and not has_filter("subtitles"):
        meta["notes"].append("captions delivered as SRT/VTT only: this FFmpeg lacks libass "
                             "(`subtitles` filter), so they were not burned in")
        burn = False
    meta["captions_burned"] = bool(burn)
    if burn:
        parts.append(f"[{cur}]subtitles=filename='captions.ass'[vout]")
    else:
        parts.append(f"[{cur}]null[vout]")
    return ";\n".join(parts), meta


def _measure_loudness(plan: EditPlan, info: MediaInfo, opts: RenderOptions, workdir: Path,
                      catalog: Catalog) -> dict | None:
    prof = LOUDNESS[plan.audio_profile]
    ln = f"loudnorm=I={prof.integrated}:TP={prof.true_peak}:LRA={prof.lra}:print_format=json"
    graph, _ = build_graph(plan, info, opts, workdir, catalog=catalog, loudnorm=ln,
                           audio_only=True)
    script = workdir / "graph_measure.txt"
    script.write_text(graph, encoding="utf-8")
    proc = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(Path(plan.source).resolve()),
                _script_flag(), script.name, "-map", "[aout]", "-f", "null", "-"],
               check=False, cwd=workdir)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", proc.stderr or "", re.DOTALL)
    if not m:
        return None
    return json.loads(m.group(0))


def _prerender_graphics(plan: EditPlan, opts: RenderOptions, catalog: Catalog, wd: Path,
                       W: int, H: int, base: int = 1) -> tuple[dict[str, int], list[str], list[str]]:
    """Render graphics with Remotion when requested/available; FFmpeg is the fallback."""
    from .effects import remotion
    if opts.renderer == "ffmpeg" or not plan.graphics:
        return {}, [], []
    if not remotion.available():
        if opts.renderer == "remotion":
            return {}, [], ["Remotion not available — titles rendered with FFmpeg fallback"]
        return {}, [], []
    tiers = registry().tiers
    mapping: dict[str, int] = {}
    inputs: list[str] = []
    notes: list[str] = []
    for ev in plan.graphics:
        fx = catalog.get(ev.effect)
        if fx.tier not in tiers or fx.renderEngine != "remotion" or not fx.composition:
            continue
        clip = wd / "graphics" / f"{ev.id}-{fx.id}.mov"
        try:
            remotion.render_event(fx, ev, W, H, clip, accent=opts.accent)
        except Exception as e:  # spec: fallback must run and be reported
            notes.append(f"{ev.id} {fx.id}: Remotion failed ({str(e)[:160]}) — FFmpeg fallback")
            continue
        mapping[ev.id] = base + len(mapping)
        inputs += ["-i", str(clip)]
    return mapping, inputs, notes


def render(plan: EditPlan, output: str | Path, opts: RenderOptions | None = None,
           *, catalog: Catalog | None = None, workdir: str | Path | None = None) -> RenderResult:
    opts = opts or RenderOptions()
    out = Path(output).resolve()
    wd = Path(workdir or out.parent / ".lionstone").resolve()
    wd.mkdir(parents=True, exist_ok=True)
    catalog = catalog or Catalog(registry().effect_dirs)
    info = probe(plan.source)
    cams0 = video_sources(plan)
    if cams0 and info.video is None:  # multicam with a separate audio master
        first = probe(next(iter(cams0.values()))["path"])
        info = MediaInfo(path=info.path, duration=info.duration, format_name=info.format_name,
                         streams=[first.video] + [s for s in info.streams if s.kind == "audio"],
                         warnings=info.warnings)
    W, H, fps = output_geometry(info, opts.aspect)

    captions: dict[str, str] = {}
    if opts.captions != "none" and plan.words:
        paths = write_captions(plan, wd, W, H, opts.caption_style, vertical=H > W)
        for k, p in paths.items():
            if k in ("srt", "vtt"):
                dst = out.with_suffix(f".{k}")
                dst.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
                captions[k] = str(dst)

    prof = LOUDNESS[plan.audio_profile]
    measured = _measure_loudness(plan, info, opts, wd, catalog)
    if measured and measured.get("input_i") not in (None, "-inf"):
        ln = (f"loudnorm=I={prof.integrated}:TP={prof.true_peak}:LRA={prof.lra}:"
              f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
              f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
              f"offset={measured['target_offset']}:linear=true")
    else:
        ln = f"loudnorm=I={prof.integrated}:TP={prof.true_peak}:LRA={prof.lra}"

    cams = video_sources(plan)
    cam_inputs = [x for c in cams.values() for x in ("-i", str(Path(c["path"]).resolve()))]
    prerendered, extra_inputs, pre_notes = _prerender_graphics(plan, opts, catalog, wd, W, H,
                                                               base=1 + len(cams))
    extra_inputs = cam_inputs + extra_inputs
    graph, meta = build_graph(plan, info, opts, wd, catalog=catalog, loudnorm=ln,
                              prerendered=prerendered)
    meta["notes"] = pre_notes + meta["notes"]
    script = wd / "graph_render.txt"
    script.write_text(graph, encoding="utf-8")
    cmd = ["ffmpeg", "-hide_banner", "-y", "-nostats", "-i", str(Path(plan.source).resolve()),
           *extra_inputs, _script_flag(), script.name, "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", opts.preset, "-crf", str(opts.crf),
           "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", str(out)]
    (wd / "render.sh").write_text("cd " + shlex.quote(str(wd)) + " && " +
                                  " ".join(shlex.quote(c) for c in cmd) + "\n", encoding="utf-8")
    run(cmd, cwd=wd)
    result = RenderResult(output=out, width=W, height=H, fps=fps,
                          duration=sum(b - a for a, b in _snap(plan, fps)), captions=captions,
                          loudness_target={"profile": prof.name, "I": prof.integrated,
                                           "TP": prof.true_peak, "measured_input": measured},
                          graphics_log=meta["graphics_log"], notes=meta["notes"],
                          color=meta["color"])
    (wd / "render.json").write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                                    encoding="utf-8")
    return result
