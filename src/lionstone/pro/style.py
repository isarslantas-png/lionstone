"""Style Learning Agent (Pro).

Learns a reusable Style Profile from 1–3 reference videos: cut rhythm, pause
behaviour, loudness, and colour (brightness, contrast, saturation, warmth).
Users choose which traits to apply: tempo, color, audio — or all.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

from lionstone.ff import analyze_filter, parse_loudness, parse_silences
from lionstone.ingest import probe


@dataclass
class StyleProfile:
    name: str
    references: list[str] = field(default_factory=list)
    avg_shot_seconds: float = 0.0
    cuts_per_minute: float = 0.0
    tempo: str = "medium"  # slow | medium | fast
    pause_ratio: float = 0.0  # share of runtime that is silence
    avg_pause: float = 0.0
    intensity: str = "balanced"
    loudness_lufs: float | None = None
    loudness_profile: str = "youtube"
    luma: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0
    warmth: float = 0.0
    color_filter: str = ""
    apply: list[str] = field(default_factory=lambda: ["tempo", "color", "audio"])

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> StyleProfile:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _shots(path: str, duration: float) -> list[float]:
    log = analyze_filter(path, vf="scale=320:-2,scdet=threshold=12,metadata=print")
    times = sorted(float(x) for x in re.findall(r"lavfi\.scd\.time=([\d.]+)", log))
    edges = [0.0] + [t for t in times if 0.2 < t < duration - 0.2] + [duration]
    return [b - a for a, b in zip(edges, edges[1:]) if b - a > 0.15]


def _color(path: str, duration: float) -> dict[str, float]:
    step = max(duration / 40, 0.5)
    log = analyze_filter(path, vf=f"fps=1/{step:.2f},scale=320:-2,signalstats,metadata=print",
                         extra=["-frames:v", "40"])

    def series(key: str) -> list[float]:
        return [float(x) for x in re.findall(rf"lavfi\.signalstats\.{key}=([\d.\-]+)", log)]

    yavg, ylow, yhigh = series("YAVG"), series("YLOW"), series("YHIGH")
    sat, uavg, vavg = series("SATAVG"), series("UAVG"), series("VAVG")
    m = lambda xs: statistics.fmean(xs) if xs else 0.0  # noqa: E731
    return {"luma": (m(yavg) - 16) / 219, "contrast": (m(yhigh) - m(ylow)) / 219,
            "saturation": m(sat) / 128, "warmth": (m(vavg) - m(uavg)) / 128}


def learn(refs: list[str], name: str = "my-style") -> StyleProfile:
    shots, pauses, pause_ratio, loud, colors = [], [], [], [], []
    for r in refs:
        info = probe(r)
        d = info.duration
        if info.video:
            shots += _shots(r, d)
            colors.append(_color(r, d))
        sil = parse_silences(analyze_filter(r, af="silencedetect=noise=-35dB:d=0.25"), d)
        pauses += [b - a for a, b in sil]
        pause_ratio.append(sum(b - a for a, b in sil) / max(d, 1e-9))
        li = parse_loudness(analyze_filter(r, af="ebur128=peak=true", extra=["-vn"]))
        if li["integrated_lufs"] is not None:
            loud.append(li["integrated_lufs"])
    p = StyleProfile(name=name, references=[Path(r).name for r in refs])
    if shots:
        p.avg_shot_seconds = round(statistics.fmean(shots), 2)
        p.cuts_per_minute = round(60 / max(p.avg_shot_seconds, 0.1), 1)
        p.tempo = "fast" if p.avg_shot_seconds < 3 else "slow" if p.avg_shot_seconds > 8 else "medium"
    if pauses:
        p.avg_pause = round(statistics.fmean(pauses), 2)
    p.pause_ratio = round(statistics.fmean(pause_ratio), 3) if pause_ratio else 0.0
    # tight references (few/short pauses) → tighter speech editing
    p.intensity = ("dynamic" if p.pause_ratio < 0.06 or p.tempo == "fast"
                   else "natural" if p.pause_ratio > 0.18 and p.tempo == "slow" else "balanced")
    if loud:
        p.loudness_lufs = round(statistics.fmean(loud), 1)
        p.loudness_profile = min(
            {"youtube": -14, "podcast": -16, "broadcast": -23}.items(),
            key=lambda kv: abs(kv[1] - p.loudness_lufs))[0]
    if colors:
        for k in ("luma", "contrast", "saturation", "warmth"):
            setattr(p, k, round(statistics.fmean(c[k] for c in colors), 3))
        p.color_filter = color_filter(p)
    return p


def color_filter(p: StyleProfile, base_sat: float = 0.28, base_contrast: float = 0.72) -> str:
    """Nudge footage toward the reference look — bounded so skin stays natural."""
    sat = min(1.3, max(0.75, 1 + (p.saturation - base_sat) * 1.5))
    con = min(1.2, max(0.88, 1 + (p.contrast - base_contrast) * 0.6))
    warm = min(0.06, max(-0.06, p.warmth * 0.5))
    parts = [f"eq=contrast={con:.3f}:saturation={sat:.3f}"]
    if abs(warm) > 0.008:
        parts.append(f"colorbalance=rm={warm:.3f}:bm={-warm:.3f}")
    return ",".join(parts)


def describe(p: StyleProfile) -> str:
    return (f"Style “{p.name}” from {', '.join(p.references)}\n"
            f"  tempo      {p.tempo} · avg shot {p.avg_shot_seconds}s · {p.cuts_per_minute} cuts/min\n"
            f"  speech     pauses {p.pause_ratio * 100:.0f}% of runtime, avg {p.avg_pause}s → "
            f"intensity {p.intensity}\n"
            f"  audio      {p.loudness_lufs} LUFS → profile {p.loudness_profile}\n"
            f"  color      luma {p.luma:.2f} · contrast {p.contrast:.2f} · sat {p.saturation:.2f} "
            f"· warmth {p.warmth:+.2f}\n"
            f"  filter     {p.color_filter or '—'}")


def plan_hook(plan, ctx: dict) -> None:
    """`lionstone edit … --x style=brand.json [--x style_apply=tempo,color]`"""
    opts = ctx.get("options")
    extras = getattr(opts, "extras", {}) or {}
    path = extras.get("style")
    if not path:
        return
    from lionstone.planner import plan_graphics
    from lionstone.presets import INTENSITIES
    from lionstone.speech import plan_cuts, segments_from_cuts

    prof = StyleProfile.load(path)
    apply = set((extras.get("style_apply") or ",".join(prof.apply)).split(","))
    applied = []
    if "tempo" in apply and prof.intensity != plan.intensity:
        a = ctx["analysis"]
        plan.intensity = prof.intensity
        plan.cuts = plan_cuts(a.silences, a.words, INTENSITIES[prof.intensity], plan.duration)
        plan.segments = segments_from_cuts(plan.cuts, plan.duration, plan.words)
        opts.intensity = prof.intensity
        plan.graphics = plan_graphics(plan, opts, ctx["catalog"])
        applied.append(f"tempo→{prof.intensity}")
    if "color" in apply and prof.color_filter:
        plan.color["filter"] = prof.color_filter
        applied.append("color")
    if "audio" in apply:
        plan.audio_profile = prof.loudness_profile
        applied.append(f"loudness→{prof.loudness_profile}")
    plan.meta["style"] = {"profile": prof.name, "applied": applied}
