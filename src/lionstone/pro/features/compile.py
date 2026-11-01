"""Compile timeline instances into the render plan.

Deterministic: the same plan.json + catalog + entitlement always yields the same
filtergraph. The result goes into the fields the open-source core already
renders (``plan.color["filter"]`` and ``plan.graphics``) — so preview
(``features.preview``) and final export (``lionstone render``) share one path.

Entitlement is enforced *here*, in the render path: a locked preset is skipped
with an explicit error, never silently rendered.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field

from lionstone.ingest import probe
from lionstone.models import EditPlan, GraphicEvent, MediaInfo
from lionstone.planner import reading_time
from lionstone.render import _snap_src, output_geometry, video_sources

from . import timeline as tl
from .catalog import Catalog, Preset
from .entitlements import Entitlement, EntitlementError
from .params import ParamError, resolve
from .renderers import ffmpeg_adapter as fa

MAX_CONCURRENT_EFFECTS = 2  # one main + one helper
MAX_CONCURRENT_HIGH = 1


@dataclass
class CompileReport:
    applied: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    fingerprint: str = ""
    filter_chars: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @property
    def ok(self) -> bool:
        return not any(s.get("severity") == "error" for s in self.skipped)


@dataclass
class Geometry:
    W: int
    H: int
    fps: float
    segs: list[tuple[float, float, str]]  # snapped (src_start, src_end, source)
    starts: list[float]  # output start of each segment
    total: float


def geometry(plan: EditPlan) -> Geometry:
    info = probe(plan.source)
    cams = video_sources(plan)
    if cams and info.video is None:
        first = probe(next(iter(cams.values()))["path"])
        info = MediaInfo(path=info.path, duration=info.duration, format_name=info.format_name,
                         streams=[first.video] + [s for s in info.streams if s.kind == "audio"])
    aspect = (plan.meta.get("options") or {}).get("aspect")
    W, H, fps = output_geometry(info, aspect)
    segs = _snap_src(plan, fps)
    starts, acc = [], 0.0
    for a, b, _ in segs:
        starts.append(acc)
        acc += b - a
    return Geometry(W, H, fps, segs, starts, acc)


def fingerprint(plan: EditPlan, g: Geometry) -> str:
    h = hashlib.sha1()
    h.update(json.dumps([(round(a, 3), round(b, 3), s) for a, b, s in g.segs]).encode())
    h.update(json.dumps([i.to_dict() for i in tl.instances(plan)], sort_keys=True,
                        default=str).encode())
    h.update(f"{g.W}x{g.H}@{g.fps}".encode())
    return h.hexdigest()[:16]


def output_windows(anchor: dict, g: Geometry) -> list[tuple[float, float]]:
    t = anchor.get("type")
    if t == "global":
        return [(0.0, g.total)]
    if t == "output":
        a, b = max(0.0, float(anchor["start"])), min(g.total, float(anchor["end"]))
        return [(a, b)] if b - a > 1e-3 else []
    if t in ("source", "segment"):
        s0, s1 = float(anchor["start"]), float(anchor["end"])
        out = []
        for (a, b, _), o in zip(g.segs, g.starts):
            lo, hi = max(a, s0), min(b, s1)
            if hi - lo > 1 / g.fps:
                out.append((round(o + lo - a, 4), round(o + hi - a, 4)))
        return out
    return []


def find_join(anchor: dict, g: Geometry) -> tuple[float, float, float] | None:
    """(output time of the cut, left segment length, right segment length)."""
    for i in range(len(g.segs) - 1):
        a, b, _ = g.segs[i]
        c, d, _ = g.segs[i + 1]
        if abs(b - anchor["left_end"]) < 0.06 and abs(c - anchor["right_start"]) < 0.06:
            return g.starts[i + 1], b - a, d - c
    return None


def _graphic_tier_ok(effect_id: str, ent: Entitlement) -> bool:
    try:
        from lionstone.effects import Catalog as CoreCatalog
        from lionstone.plugins import registry
        fx = CoreCatalog(registry().effect_dirs).get(effect_id)
        return ent.allows(fx.tier)
    except Exception:
        return False


def compile_plan(plan: EditPlan, catalog: Catalog, ent: Entitlement, *,
                 strict: bool = False) -> CompileReport:
    rep = CompileReport()
    rep.notes += tl.migrate_instances(plan, catalog)
    g = geometry(plan)
    ctx = fa.RCtx(g.W, g.H, g.fps, g.total)
    transforms: list[fa.Transform] = []
    looks, effects, joins_f = [], [], []
    graphics: list[GraphicEvent] = []
    caption_style = None
    active_effects: list[tuple[float, float, str, str]] = []  # (a, b, cost, id)
    items = tl.instances(plan)

    def skip(inst, reason, severity="warning"):
        rep.skipped.append({"id": inst.id, "preset": inst.preset, "reason": reason,
                            "severity": severity})

    for inst in items:
        if not inst.enabled:
            continue
        if inst.status in ("missing-preset", "error"):
            skip(inst, f"status {inst.status}", "error")
            continue
        try:
            p: Preset = catalog.get(inst.preset)
        except Exception as e:
            skip(inst, str(e), "error")
            continue
        if not p.usable:
            skip(inst, f"{p.name} is {p.implementationStatus}: {'; '.join(p.limitations)}", "error")
            continue
        try:
            ent.require(p.tier, f"{p.name} ({p.id})")
        except EntitlementError as e:
            inst.status = "locked"
            skip(inst, str(e), "error")
            if strict:
                raise
            continue
        try:
            params = resolve(p.parameters, inst.params)
        except ParamError as e:
            skip(inst, f"invalid parameters: {e}", "error")
            continue

        try:
            if p.kind == "transition":
                rid = p.renderer_id
                if rid == "lionstone.hard-cut":
                    rep.applied.append({"id": inst.id, "preset": p.id, "note": "deliberate cut"})
                    continue
                j = find_join(inst.anchor, g) if inst.anchor.get("type") == "join" else None
                if j is None:
                    inst.status = "orphaned"
                    skip(inst, "the cut this transition belonged to no longer exists")
                    continue
                tj, dl, dr = j
                d = params.get("frames", 12) / g.fps
                limit = 2 * min(dl, dr) * 0.8
                if d > limit:
                    if limit < 4 / g.fps:
                        skip(inst, "neighbouring clips too short for a transition — kept a hard cut")
                        continue
                    rep.notes.append(f"{inst.id}: shortened {p.name} to {limit:.2f}s "
                                     "(clips too short)")
                    d = limit
                if rid in fa.JOIN_TRANSFORMS:
                    transforms += fa.JOIN_TRANSFORMS[rid](params, [(tj, d)], ctx)
                if rid in fa.JOIN_FILTERS:
                    joins_f.append(fa.JOIN_FILTERS[rid](params, [(tj, d)], ctx))
                rep.applied.append({"id": inst.id, "preset": p.id, "at": round(tj, 3),
                                    "seconds": round(d, 3)})
                continue

            wins = output_windows(inst.anchor, g)
            if not wins:
                inst.status = "orphaned"
                skip(inst, "its material was cut from the edit")
                continue

            if p.kind == "text":
                at, end = wins[0]
                dur = float(params.get("duration", 4.0))
                need = reading_time(f"{params.get('text', '')} {params.get('subtext', '')}")
                if dur < need:
                    rep.notes.append(f"{inst.id}: extended to {need:.1f}s so it can be read")
                    dur = need
                if at + dur > g.total:
                    at = max(0.0, g.total - dur)
                if not _graphic_tier_ok(p.graphicEffect, ent):
                    skip(inst, f"graphic {p.graphicEffect} is locked for this plan", "error")
                    continue
                extra = {k: v for k, v in params.items()
                         if k not in ("text", "subtext", "duration")}
                graphics.append(GraphicEvent(
                    id=f"fx-{inst.id}", effect=p.graphicEffect, at=round(at, 3),
                    duration=round(min(dur, g.total - at), 3), text=params.get("text", ""),
                    subtext=params.get("subtext", ""), params=extra,
                    layer="lower_thirds" if p.category == "lower-thirds" else "titles",
                    reason=f"{p.name} ({inst.created_by})"))
                rep.applied.append({"id": inst.id, "preset": p.id, "at": round(at, 3)})
                continue

            if p.kind == "caption":
                caption_style = {"lionstone.caption-clean": "clean",
                                 "lionstone.caption-active-word": "highlight",
                                 "lionstone.caption-karaoke": "karaoke"}[p.renderer_id]
                rep.applied.append({"id": inst.id, "preset": p.id})
                continue

            if p.kind == "effect":
                busy = [x for x in active_effects
                        if any(x[0] < b and a < x[1] for a, b in wins)]
                if len(busy) >= MAX_CONCURRENT_EFFECTS:
                    skip(inst, "effect budget: already one main + one helper effect here")
                    continue
                if p.performanceCost == "high" and any(x[2] == "high" for x in busy):
                    skip(inst, "effect budget: another high-cost effect overlaps")
                    continue
                for a, b in wins:
                    active_effects.append((a, b, p.performanceCost, p.id))

            rid = p.renderer_id
            if p.pipeline == "transform":
                transforms += fa.TRANSFORMS[rid](params, wins, ctx)
                if rid in fa.COMPANION_FILTERS:
                    effects.append(fa.COMPANION_FILTERS[rid](params, wins, ctx))
            elif p.kind == "look":
                looks.append(fa.FILTERS[rid](params, wins, ctx))
            else:
                effects.append(fa.FILTERS[rid](params, wins, ctx))
            rep.applied.append({"id": inst.id, "preset": p.id,
                                "windows": [(round(a, 2), round(b, 2)) for a, b in wins]})
        except (FileNotFoundError, PermissionError, KeyError, ValueError) as e:
            inst.status = "error"
            skip(inst, f"{type(e).__name__}: {e}", "error")
    tl.save_instances(plan, items)

    frags = [f for f in [fa.merge_transforms(transforms, ctx), *looks, *effects, *joins_f] if f]
    chain = ",".join(frags)
    st = plan.meta.setdefault("lionstone_fx", {"schema": 1, "instances": []})
    prev = st.setdefault("core_color_preset", plan.color.get("preset", "natural"))
    has_global_look = any(i.enabled and i.anchor.get("type") == "global"
                          and catalog.presets.get(i.preset) is not None
                          and catalog.presets[i.preset].kind == "look"
                          and i.status not in ("locked", "error") for i in items)
    plan.color["preset"] = "none" if has_global_look else prev
    if chain:
        plan.color["filter"] = chain + ",null"
    else:
        plan.color.pop("filter", None)
    base = [ge for ge in plan.graphics if not ge.id.startswith("fx-")]
    placed: list[GraphicEvent] = []
    for ge in sorted(graphics, key=lambda e: e.at):
        busy = sorted(base + placed, key=lambda e: e.at)
        for other in busy:  # never two animated graphics at once: shift later, or drop
            if ge.at < other.at + other.duration + 0.3 and other.at < ge.at + ge.duration + 0.3:
                ge.at = round(other.at + other.duration + 0.3, 3)
        if ge.at + ge.duration > g.total + 1e-3:
            rep.skipped.append({"id": ge.id[3:], "preset": ge.effect, "severity": "warning",
                                "reason": "no free slot without overlapping another title"})
            continue
        if ge.reason and any(ge.at != x.get("at") for x in rep.applied if x["id"] == ge.id[3:]):
            rep.notes.append(f"{ge.id[3:]}: moved to {ge.at:.2f}s to avoid overlapping a title")
        placed.append(ge)
    plan.graphics = base + placed
    if caption_style:
        plan.meta.setdefault("options", {})["caption_style"] = caption_style
    hdr = hdr_warning(plan.source)
    if hdr:
        rep.notes.append(hdr)
    rep.fingerprint = fingerprint(plan, g)
    rep.filter_chars = len(chain)
    st["compiled"] = {"fingerprint": rep.fingerprint, "report": rep.to_dict(),
                      "geometry": [g.W, g.H, g.fps]}
    return rep


def is_stale(plan: EditPlan) -> bool:
    st = plan.meta.get("lionstone_fx") or {}
    if not st.get("instances"):
        return False
    comp = st.get("compiled") or {}
    try:
        return comp.get("fingerprint") != fingerprint(plan, geometry(plan))
    except Exception:
        return True


def hdr_warning(path: str) -> str | None:
    """HDR / log footage: we don't fake a colour-space conversion — we warn."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                              "-show_entries", "stream=color_transfer,color_primaries",
                              "-of", "json", path], capture_output=True, text=True).stdout
        s = (json.loads(out).get("streams") or [{}])[0]
    except Exception:
        return None
    trc = s.get("color_transfer", "")
    if trc in ("smpte2084", "arib-std-b67") or "log" in trc:
        return (f"source uses {trc} (HDR/log). Lionstone does not convert colour spaces; "
                "looks are applied as-is — grade from a Rec.709 proxy for accurate colour.")
    return None
