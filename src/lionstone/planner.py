"""Edit Decision Engine — turn analysis into a reviewable EditPlan.

Rules first, models second: deterministic rules produce the plan; plugins and
optional LLM review can *propose* changes, but every change lands in the same
JSON plan with a reason attached.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .effects import Catalog
from .models import EditPlan, GraphicEvent, Word
from .presets import INTENSITIES
from .speech import plan_cuts, segments_from_cuts


@dataclass
class Speaker:
    name: str
    title: str = ""
    label: str | None = None  # diarization label, e.g. "SPEAKER_00"


@dataclass
class Chapter:
    at: float  # source seconds
    title: str


@dataclass
class EditOptions:
    intensity: str = "balanced"
    profile: str = "youtube"
    aspect: str | None = None  # None = keep source aspect
    title: str = ""
    subtitle: str = ""
    outro: str = ""
    speakers: list[Speaker] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    captions: str = "burn"  # burn | file | none
    caption_style: str = "clean"
    color: str = "natural"
    lut: str | None = None
    denoise: str = "light"  # off | light | strong
    title_effect: str = "F01"
    chapter_effect: str = "F04"
    lower_third_effect: str = "F05"
    outro_effect: str = "F01"
    accent: str = "#E8B04B"
    font: str | None = None
    extras: dict[str, str] = field(default_factory=dict)  # plugin options: --x key=value


def parse_timecode(s: str) -> float:
    parts = [float(p) for p in s.strip().split(":")]
    t = 0.0
    for p in parts:
        t = t * 60 + p
    return t


def parse_chapter(spec: str) -> Chapter:
    m = re.match(r"^\s*([\d:.]+)\s+(.+)$", spec)
    if not m:
        raise ValueError(f'chapter must look like "00:05:10 Title", got {spec!r}')
    return Chapter(parse_timecode(m.group(1)), m.group(2).strip())


def parse_speaker(spec: str) -> Speaker:
    name, _, rest = spec.partition("|")
    title, _, label = rest.partition("|")
    return Speaker(name.strip(), title.strip(), label.strip() or None)


def reading_time(text: str) -> float:
    return 1.2 + 0.32 * len(text.split())


def build_plan(source: str, duration: float, silences: list[tuple[float, float]],
               words: list[Word], opts: EditOptions, catalog: Catalog) -> EditPlan:
    preset = INTENSITIES[opts.intensity]
    cuts = plan_cuts(silences, words, preset, duration)
    segments = segments_from_cuts(cuts, duration, words)
    plan = EditPlan(source=source, duration=duration, intensity=opts.intensity,
                    segments=segments, cuts=cuts, words=words, audio_profile=opts.profile,
                    color={"preset": opts.color, "lut": opts.lut},
                    meta={"asr": bool(words), "options": _opts_meta(opts)})
    plan.graphics = plan_graphics(plan, opts, catalog)
    return plan


def _opts_meta(opts: EditOptions) -> dict:
    d = dict(opts.__dict__)
    d["speakers"] = [s.__dict__ for s in opts.speakers]
    d["chapters"] = [c.__dict__ for c in opts.chapters]
    return d


def _next_kept(plan: EditPlan, t: float) -> float | None:
    o = plan.source_to_output(t)
    if o is not None:
        return o
    acc = 0.0
    for s in plan.segments:
        if s.start >= t:
            return acc
        acc += s.duration
    return None


def plan_graphics(plan: EditPlan, opts: EditOptions, catalog: Catalog) -> list[GraphicEvent]:
    events: list[GraphicEvent] = []
    total = plan.output_duration
    out_words = [(plan.source_to_output(w.start), w) for w in plan.words]
    out_words = [(t, w) for t, w in out_words if t is not None]
    first_speech = out_words[0][0] if out_words else 0.5

    def add(effect_id: str, at: float, text: str, subtext: str, reason: str, layer: str,
            **params) -> None:
        fx = catalog.get(effect_id)
        hold = max(fx.duration["hold"], reading_time(f"{text} {subtext}"))
        dur = fx.duration["enter"] + hold + fx.duration["exit"]
        c = fx.constraints
        dur = min(max(dur, c.get("minDuration", 0)), c.get("maxDuration", 1e9))
        events.append(GraphicEvent(id="", effect=effect_id, at=round(at, 3),
                                   duration=round(dur, 3), text=text, subtext=subtext,
                                   params=params, layer=layer, reason=reason))

    if opts.title:
        add(opts.title_effect, 0.2, opts.title, opts.subtitle, "video opening", "titles")
    for i, ch in enumerate(sorted(opts.chapters, key=lambda c: c.at), 1):
        t = _next_kept(plan, ch.at)
        if t is not None:
            add(opts.chapter_effect, t, ch.title, "", f"chapter {i} at source {ch.at:.1f}s",
                "titles", number=i)
    if opts.speakers:
        labelled = any(w.speaker for _, w in out_words)
        for k, sp in enumerate(opts.speakers):
            at = None
            if labelled and sp.label:
                at = next((t for t, w in out_words if w.speaker == sp.label), None)
                reason = f"first line from {sp.label}"
            if at is None:
                at = first_speech + 1.0 + k * 9.0
                reason = "speaker introduction" + (" (no diarization: staggered)" if k else "")
            add(opts.lower_third_effect, at + 0.5, sp.name, sp.title, reason, "lower_thirds")
    if opts.outro:
        fx = catalog.get(opts.outro_effect)
        add(opts.outro_effect, max(0.0, total - fx.total - 0.3), opts.outro, "", "closing",
            "titles")

    return resolve_collisions(events, total)


def resolve_collisions(events: list[GraphicEvent], total: float, gap: float = 0.3) -> list[GraphicEvent]:
    """No two animated graphics on screen at once; keep everything inside the video."""
    out: list[GraphicEvent] = []
    for ev in sorted(events, key=lambda e: (e.at, e.layer != "titles")):
        while out and ev.at < out[-1].at + out[-1].duration + gap:
            prev = out[-1]
            if ev.reason == "closing":  # outro wins: shorten the previous one, or drop it
                room = ev.at - prev.at - gap
                if room >= reading_time(f"{prev.text} {prev.subtext}") * 0.8:
                    prev.duration = round(room, 3)
                else:
                    out.pop()
            else:
                ev.reason += " · shifted to avoid overlap"
                ev.at = round(prev.at + prev.duration + gap, 3)
        if ev.at + ev.duration > total:
            if total - ev.at >= reading_time(f"{ev.text} {ev.subtext}") * 0.8:
                ev.duration = round(total - ev.at, 3)
            else:
                continue  # can't be read in the time left: dropping is a valid edit
        out.append(ev)
    for i, ev in enumerate(out):
        ev.id = f"g{i:03d}"
    return out
