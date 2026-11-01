"""Lionstone creative decision engine.

Editing first, effects second. The agent proposes a consistent look, a small
effect budget, transitions only on meaningful cuts, emphasis motion on strong
lines, and captions/CTA per platform — every decision with a reason, all
reversible (they're plan instances with ``created_by="agent"``).

Policy
* subtle   — natural grade, soft motion, hard cuts
* balanced — consistent grade, few transitions, meaningful title motion, light texture
* bold     — more visible motion & kinetic type; readability still enforced
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lionstone.models import EditPlan

from . import timeline as tl
from .catalog import Catalog
from .entitlements import Entitlement

CONTENT = ("podcast", "interview", "talk", "lecture", "real-estate", "product", "vlog",
           "music", "corporate")
STYLES = ("cinematic", "minimal", "energetic", "documentary", "social")
INTENSITY = {"subtle": 0.45, "balanced": 0.65, "bold": 0.85}

# (content, style) → preferred looks, best first (falls back down the list by tier)
LOOKS = {
    "real-estate": ["look-bright-interior", "look-natural-exterior", "look-clean-daylight"],
    "product": ["look-product-neutral", "look-detail-pop", "look-natural-neutral"],
    "music": ["look-neon-balance", "look-punchy-social"],
    "cinematic": ["look-warm-cinema", "look-muted-film", "look-soft-contrast"],
    "documentary": ["look-true-to-life", "look-low-saturation"],
    "social": ["look-soft-skin-safe", "look-punchy-social"],
    "energetic": ["look-punchy-social", "look-natural-neutral"],
    "minimal": ["look-matte-editorial", "look-soft-contrast", "look-natural-neutral"],
}
TRANSITIONS = {
    "cinematic": ["blur-cut", "dip-to-black", "light-leak-flash"],
    "documentary": ["dip-to-black"],
    "minimal": [],
    "energetic": ["zoom-through", "whip-pan", "dip-to-white"],
    "social": ["zoom-through", "whip-pan", "glitch-cut"],
}
PER_MINUTE = {"subtle": 0.0, "balanced": 1.0, "bold": 3.0}
HOOK = re.compile(r"(\d|!|\?|\b(never|always|secret|mistake|important|key|asla|önemli|dikkat|"
                  r"sır|hata|kesinlikle)\b)", re.I)


@dataclass
class Decision:
    preset: str
    anchor: dict
    params: dict
    reason: str


@dataclass
class Proposal:
    decisions: list[Decision] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def table(self) -> list[tuple[str, str, str]]:
        return [(d.preset.replace("lionstone.", ""), d.anchor.get("type", ""), d.reason)
                for d in self.decisions]


def _pick(cands: list[str], catalog: Catalog, ent: Entitlement, notes: list[str]) -> str | None:
    for c in cands:
        pid = f"lionstone.{c}"
        p = catalog.presets.get(pid)
        if p and p.usable and ent.allows(p.tier):
            return pid
        if p and not ent.allows(p.tier):
            notes.append(f"{p.name} would fit but needs {p.tier.title()} — using an alternative")
    return None


def propose(plan: EditPlan, catalog: Catalog, ent: Entitlement, *, content: str = "podcast",
            style: str = "minimal", intensity: str = "balanced", platform: str = "youtube"
            ) -> Proposal:
    if content not in CONTENT or style not in STYLES or intensity not in INTENSITY:
        raise ValueError(f"content∈{CONTENT}, style∈{STYLES}, intensity∈{tuple(INTENSITY)}")
    pr = Proposal()
    k = INTENSITY[intensity]
    segs = plan.segments
    total = sum(s.duration for s in segs)
    if not segs:
        pr.notes.append("empty edit — nothing to decorate")
        return pr

    # 1. one consistent look for the whole video
    cands = LOOKS.get(content if content in LOOKS else style, LOOKS["minimal"])
    if intensity == "subtle":
        cands = ["look-natural-neutral", "look-true-to-life"]
    look = _pick(cands, catalog, ent, pr.notes) or _pick(["look-natural-neutral"], catalog, ent,
                                                         pr.notes)
    if look:
        pr.decisions.append(Decision(look, {"type": "global"}, {"intensity": round(k, 2)},
                                     f"one consistent grade for {content}/{style}"))

    # 2. a light helper texture only where it serves the style
    if style in ("cinematic", "documentary") and intensity != "subtle":
        v = _pick(["soft-vignette"], catalog, ent, pr.notes)
        if v:
            pr.decisions.append(Decision(v, {"type": "global"}, {"intensity": round(0.3 * k + 0.1, 2)},
                                         "helper effect: subtle vignette for focus"))
        if style == "cinematic" and intensity == "bold":
            g = _pick(["film-grain"], catalog, ent, pr.notes)
            if g:
                pr.decisions.append(Decision(g, {"type": "global"}, {"intensity": 0.25},
                                             "fine grain for film texture"))

    # 3. emphasis on strong lines (never two in a row, ≥ 20 s apart)
    if intensity != "subtle" and plan.words and content not in ("real-estate",):
        emph = _pick(["quick-punch-in"] if style in ("social", "energetic") else ["smooth-zoom"],
                     catalog, ent, pr.notes)
        last_t = -1e9
        from lionstone.textedit import sentences as split_sentences
        for s in split_sentences(plan.words):
            if s["end"] - s["start"] < 1.2 or not HOOK.search(s["text"]):
                continue
            if s["start"] - last_t < (20 if intensity == "balanced" else 10):
                continue
            if emph:
                pr.decisions.append(Decision(emph, {"type": "source", "start": s["start"],
                                                    "end": min(s["end"], s["start"] + 3.5)},
                                             {"amount": round(0.35 + 0.4 * (k - 0.45), 2)},
                                             f"emphasis: “{s['text'][:48]}”"))
                last_t = s["start"]

    # 4. slow camera motion for still-heavy content (never pans off a face: centre zooms only)
    if content in ("real-estate", "product"):
        moves = ["gentle-push-in", "slow-pull-back", "vertical-drift", "ken-burns-pan"]
        usable = [m for m in moves if _pick([m], catalog, ent, [])]
        prev = None
        for i, s in enumerate(segs):
            if s.duration < 3.0 or not usable:
                continue
            m = usable[i % len(usable)]
            if m == prev:
                m = usable[(i + 1) % len(usable)]
            pr.decisions.append(Decision(f"lionstone.{m}", {"type": "segment", "start": s.start,
                                                            "end": s.end},
                                         {"amount": round(0.3 + 0.3 * (k - 0.45), 2)},
                                         "slow, stable architectural/product motion"))
            prev = m

    # 5. transitions only on meaningful cuts, rotating, within a per-minute budget
    budget = int(PER_MINUTE[intensity] * total / 60 + 0.5)
    choices = [c for c in TRANSITIONS.get(style, []) if _pick([c], catalog, ent, [])]
    chapter_src = [c.get("at") for c in (plan.meta.get("options") or {}).get("chapters", [])]
    joins = []
    for i in range(len(segs) - 1):
        gap = segs[i + 1].start - segs[i].end
        at_chapter = any(abs(segs[i + 1].start - (c or -99)) < 1.5 for c in chapter_src)
        if gap > 2.5 or at_chapter:
            joins.append((i, "chapter change" if at_chapter else f"topic change ({gap:.1f}s removed)"))
    if choices and budget:
        last = None
        for n, (i, why) in enumerate(joins[:budget]):
            c = choices[n % len(choices)]
            if c == last and len(choices) > 1:
                c = choices[(n + 1) % len(choices)]
            if min(segs[i].duration, segs[i + 1].duration) < 0.8:
                pr.notes.append(f"cut {i}: clips too short — kept a hard cut")
                continue
            pr.decisions.append(Decision(f"lionstone.{c}", tl.join_anchor(plan, i), {},
                                         f"transition on {why}"))
            last = c
    elif joins:
        pr.notes.append(f"{len(joins)} topic changes kept as hard cuts ({style}/{intensity})")

    # 6. captions per platform
    if platform in ("reels", "tiktok", "shorts") or style == "social":
        cap = _pick(["caption-active-word", "caption-clean"], catalog, ent, pr.notes)
    else:
        cap = _pick(["caption-clean"], catalog, ent, pr.notes)
    if cap and plan.words:
        pr.decisions.append(Decision(cap, {"type": "global"}, {}, f"captions for {platform}"))
    return pr


def apply(plan: EditPlan, proposal: Proposal, catalog: Catalog) -> int:
    """Replace previous agent decisions; user and brand-kit instances are untouched."""
    keep = [i for i in tl.instances(plan) if i.created_by != "agent"]
    tl.save_instances(plan, keep)
    for d in proposal.decisions:
        p = catalog.get(d.preset)
        tl.add(plan, tl.FxInstance(preset=p.id, version=p.version, anchor=d.anchor,
                                   params=d.params, created_by="agent", reason=d.reason))
    return len(proposal.decisions)
