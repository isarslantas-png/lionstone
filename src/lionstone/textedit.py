"""Edit video by editing text.

``lionstone transcript`` writes ``transcript.md``. Delete a line to cut that
sentence, move lines to reorder, uncomment a removed line to restore it, then
``lionstone apply-transcript``. The plan (and only the plan) changes; render
again to see the result.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Cut, EditPlan, Word
from .speech import segments_from_cuts

HEADER = """<!--
  Lionstone transcript — edit video by editing text.
  • Delete a line            → that sentence is cut.
  • Move a line up/down      → sentences are reordered.
  • Uncomment a removed line → it comes back (restores automatic cuts inside it).
  Keep the [tNNNN …] tags intact. Text after the tag is for reading only;
  editing words does not change the audio.
-->
"""

_LINE = re.compile(r"^\s*(?:<!--\s*removed:\s*)?\[(t\d{4})[^\]]*\]\s?(.*?)(?:\s*-->)?\s*$")


def sentences(words: list[Word], max_words: int = 28, gap: float = 0.8) -> list[dict]:
    out: list[dict] = []
    cur: list[Word] = []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = w.text.rstrip().endswith((".", "?", "!", "…"))
        if nxt is None or end or (nxt.start - w.end) > gap or len(cur) >= max_words or \
                (nxt.speaker and w.speaker and nxt.speaker != w.speaker):
            out.append({"id": f"t{len(out) + 1:04d}", "start": cur[0].start, "end": cur[-1].end,
                        "text": " ".join(x.text for x in cur), "speaker": cur[0].speaker})
            cur = []
    return out


def _regions(sents: list[dict], duration: float) -> list[tuple[float, float]]:
    bounds = [0.0]
    for a, b in zip(sents, sents[1:]):
        bounds.append((a["end"] + b["start"]) / 2)
    bounds.append(duration)
    return list(zip(bounds[:-1], bounds[1:]))


def _fmt(t: float) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


def export(plan: EditPlan) -> str:
    sents = plan.meta.get("sentences") or sentences(plan.words)
    plan.meta["sentences"] = sents
    order = plan.meta.get("sentence_order") or [s["id"] for s in sents]
    by_id = {s["id"]: s for s in sents}
    lines = [HEADER]
    for sid in order:
        s = by_id[sid]
        mid = (s["start"] + s["end"]) / 2
        kept = plan.source_to_output(mid) is not None
        who = f" {s['speaker']}" if s.get("speaker") else ""
        tag = f"[{sid} {_fmt(s['start'])}{who}]"
        lines.append(f"{tag} {s['text']}" if kept else f"<!-- removed: {tag} {s['text']} -->")
    return "\n".join(lines) + "\n"


def apply(plan: EditPlan, markdown: str) -> dict:
    sents = plan.meta.get("sentences") or sentences(plan.words)
    by_id = {s["id"]: s for s in sents}
    regions = dict(zip([s["id"] for s in sents], _regions(sents, plan.duration)))
    active_ids, removed_ids = [], []
    for raw in markdown.splitlines():
        m = _LINE.match(raw)
        if not m or m.group(1) not in by_id:
            continue
        (removed_ids if raw.lstrip().startswith("<!--") else active_ids).append(m.group(1))
    deleted = [sid for sid in by_id if sid not in active_ids]
    stats = {"deleted": 0, "restored": 0, "reordered": False}

    # drop previous transcript cuts, then re-derive from the file (idempotent)
    plan.cuts = [c for c in plan.cuts if c.kind != "transcript"]
    for sid in active_ids:  # restore: disable auto cuts that sit inside a kept sentence
        s = by_id[sid]
        # word-level cleanups inside a kept sentence stay; only a sentence that was
        # removed wholesale (its midpoint is cut) gets its covering cut disabled.
        mid = (s["start"] + s["end"]) / 2
        if plan.source_to_output(mid) is None:
            for c in plan.cuts:
                if c.enabled and c.start <= mid <= c.end:
                    c.enabled = False
                    stats["restored"] += 1
    for sid in deleted:
        a, b = regions[sid]
        plan.cuts.append(Cut(id=f"x{sid[1:]}", start=round(a, 3), end=round(b, 3),
                             kind="transcript", reason=f"sentence {sid} deleted in transcript"))
        stats["deleted"] += 1

    segs = segments_from_cuts(plan.cuts, plan.duration, plan.words)
    natural = [sid for sid in (s["id"] for s in sents) if sid in active_ids]
    if active_ids != natural:  # reorder: split kept segments on sentence regions
        stats["reordered"] = True
        rank = {sid: i for i, sid in enumerate(active_ids)}
        pieces = []
        for seg in segs:
            for sid, (a, b) in regions.items():
                lo, hi = max(seg.start, a), min(seg.end, b)
                if hi - lo > 0.04 and sid in rank:
                    pieces.append((rank[sid], lo, hi, seg.source))
        pieces.sort(key=lambda p: (p[0], p[1]))
        from .models import Segment
        segs = [Segment(id=f"s{i:04d}", start=round(lo, 3), end=round(hi, 3), source=src,
                        text=" ".join(w.text for w in plan.words
                                      if w.start >= lo - 0.01 and w.end <= hi + 0.01))
                for i, (_, lo, hi, src) in enumerate(pieces)]
    plan.segments = segs
    plan.meta["sentence_order"] = active_ids + [s for s in removed_ids if s not in active_ids]
    return stats


def write(plan: EditPlan, path: Path) -> Path:
    path.write_text(export(plan), encoding="utf-8")
    return path
