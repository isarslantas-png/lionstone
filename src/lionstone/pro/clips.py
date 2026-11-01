"""Short-clip generator (Pro): long video → vertical Shorts / Reels / TikToks.

Finds self-contained moments (complete sentences, strong opening line, good
speech density), reframes to 9:16, adds a hook title and word-highlight
captions, and runs the same QA as full edits. Optional LLM re-ranking with
your own API key (``--llm``); heuristics work offline.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from lionstone.models import EditPlan, GraphicEvent, Segment
from lionstone.textedit import sentences

HOOK_WORDS = {
    "en": ["why", "how", "secret", "mistake", "nobody", "never", "biggest", "stop", "truth",
           "here's", "the one", "most people", "you need", "don't"],
    "tr": ["neden", "nasıl", "sır", "hata", "kimse", "asla", "en büyük", "dikkat", "gerçek",
           "çoğu insan", "bilmiyor", "yapmayın", "işte"],
}


@dataclass
class ClipCandidate:
    start: float
    end: float
    text: str
    hook: str
    score: float
    reasons: list[str]

    @property
    def duration(self) -> float:
        return self.end - self.start


def _kept_words(plan: EditPlan):
    return [w for w in plan.words if plan.source_to_output((w.start + w.end) / 2) is not None]


def candidates(plan: EditPlan, min_s: float = 18, max_s: float = 60,
               target: float = 35) -> list[ClipCandidate]:
    sents = sentences(_kept_words(plan), max_words=40, gap=1.2)
    out: list[ClipCandidate] = []
    for i, first in enumerate(sents):
        j = i
        while j < len(sents):
            end = sents[j]["end"]
            dur = plan.source_to_output(end) - plan.source_to_output(first["start"]) \
                if plan.source_to_output(end) is not None and \
                plan.source_to_output(first["start"]) is not None else end - first["start"]
            if dur > max_s:
                break
            if dur >= min_s:
                body = " ".join(s["text"] for s in sents[i: j + 1])
                score, why = _score(first["text"], body, sents[j]["text"], dur, target)
                out.append(ClipCandidate(first["start"], end, body, first["text"], score, why))
            j += 1
    return sorted(out, key=lambda c: -c.score)


def _score(hook: str, body: str, last: str, dur: float, target: float) -> tuple[float, list[str]]:
    s, why = 0.0, []
    h = hook.lower()
    if hook.rstrip().endswith("?"):
        s += 2
        why.append("opens with a question")
    if re.search(r"\d", hook):
        s += 1
        why.append("concrete number in the hook")
    if any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", h)
           for lang in HOOK_WORDS.values() for k in lang):
        s += 1.5
        why.append("hook phrase")
    if len(hook.split()) <= 14:
        s += 0.5
        why.append("short first line")
    if last.rstrip().endswith((".", "!", "?")):
        s += 1
        why.append("ends on a complete sentence")
    wps = len(body.split()) / max(dur, 1e-9)
    if 2.0 <= wps <= 3.9:
        s += 1
        why.append(f"good pace {wps:.1f} words/s")
    s -= abs(dur - target) / target
    return round(s, 3), why


def pick(cands: list[ClipCandidate], n: int) -> list[ClipCandidate]:
    chosen: list[ClipCandidate] = []
    for c in cands:
        if all(c.end <= x.start or c.start >= x.end for x in chosen):
            chosen.append(c)
        if len(chosen) == n:
            break
    return sorted(chosen, key=lambda c: c.start)


def llm_rerank(cands: list[ClipCandidate], n: int, language: str = "") -> list[ClipCandidate]:
    """Ask Claude to pick the most engaging, self-contained moments (BYO API key)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not cands:
        return cands
    pool = cands[: max(n * 4, 12)]
    listing = "\n".join(f"[{i}] ({c.duration:.0f}s) {c.text[:600]}" for i, c in enumerate(pool))
    prompt = (
        f"You are a short-form video editor. From these candidate clips, choose the {n} "
        "that would perform best as standalone Shorts/Reels: strong first line, one clear idea, "
        "makes sense without context, satisfying ending. Reply with JSON only: "
        '{"picks": [{"index": 0, "title": "<=7 word on-screen hook' +
        (f' in {language}' if language else '') + '"}]}\n\n' + listing)
    body = json.dumps({"model": os.environ.get("LIONSTONE_LLM_MODEL", "claude-sonnet-4-5"),
                       "max_tokens": 800,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = json.loads(r.read())["content"][0]["text"]
        picks = json.loads(text[text.index("{"): text.rindex("}") + 1])["picks"]
    except Exception:
        return cands  # never fail the job because the LLM did
    ranked = []
    for p in picks:
        i = int(p["index"])
        if 0 <= i < len(pool):
            c = pool[i]
            c.hook = p.get("title") or c.hook
            c.reasons.append("chosen by LLM editor")
            c.score += 10
            ranked.append(c)
    return ranked + [c for c in cands if c not in ranked]


def subplan(plan: EditPlan, c: ClipCandidate, hook_effect: str, caption_hook: str) -> EditPlan:
    segs = []
    for s in plan.segments:
        lo, hi = max(s.start, c.start - 0.15), min(s.end, c.end + 0.35)
        if hi - lo > 0.04:
            segs.append(Segment(id=f"s{len(segs):04d}", start=round(lo, 3), end=round(hi, 3),
                                source=s.source))
    sub = EditPlan(source=plan.source, duration=plan.duration, intensity="dynamic",
                   segments=segs, cuts=[], words=[w for w in plan.words
                                                  if c.start - 0.2 <= w.start <= c.end + 0.2],
                   audio_profile="social", color=dict(plan.color),
                   meta={k: v for k, v in plan.meta.items() if k in ("sources", "options")})
    hook = " ".join(caption_hook.split()[:8])
    sub.graphics = [GraphicEvent(id="g000", effect=hook_effect, at=0.15, duration=3.2, text=hook,
                                 layer="titles", reason="clip hook")]
    return sub


def write_manifest(chosen: list[ClipCandidate], paths: list[str], out: Path) -> Path:
    data = [{**asdict(c), "duration": round(c.duration, 2), "file": p}
            for c, p in zip(chosen, paths)]
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
