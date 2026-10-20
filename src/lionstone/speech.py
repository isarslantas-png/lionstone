"""Speech Editing Agent — decide *what to remove* without breaking meaning.

Pure functions over (silences, words) so every rule is unit-testable. The
golden rule: **a cut never enters a word**. Every candidate is clamped to the
gap between neighbouring words with a safety pad, and every cut carries a
human-readable reason so it can be reviewed and restored.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .models import Cut, Segment, Word
from .presets import Intensity

# --- lexicons ---------------------------------------------------------------
# Pure hesitation sounds (EN + TR). Matched on the normalised token.
_FILLER_RE = re.compile(
    r"^(u+m+|u+h+m*|e+r+m*|a+h+|h+m+|m{2,}|mhm|ı{2,}|ıh+|e{2,}h*|e+h+|e{2,}m+|ö{2,}|a{2,}|ha{2,}|uh-?huh)$"
)
# Discourse markers: only removed in `dynamic`, and only when isolated by pauses.
_DISCOURSE = {
    "yani", "hani", "şey", "işte", "aslında", "like", "basically", "actually", "literally",
    "so", "well", "okay", "ok",
}
_DISCOURSE_BIGRAMS = {("you", "know"), ("i", "mean"), ("kind", "of"), ("sort", "of")}
_SENTENCE_END = re.compile(r"[.!?…]$")


def norm(token: str) -> str:
    t = unicodedata.normalize("NFC", token).strip()
    t = t.replace("İ", "i").replace("I", "ı") if _looks_turkish(t) else t
    t = t.lower()
    return re.sub(r"[^\w\-ıışğüöç]", "", t)


def _looks_turkish(t: str) -> bool:
    return any(c in t for c in "ıİşŞğĞ")


def is_filler(token: str) -> bool:
    return bool(_FILLER_RE.match(norm(token).strip("-")))


# --- helpers -----------------------------------------------------------------
def _gap_bounds(words: list[Word], t0: float, t1: float, pre: float, post: float,
                duration: float) -> tuple[float, float] | None:
    """Clamp [t0, t1] so it does not touch any word (with pads)."""
    lo, hi = t0, t1
    for w in words:
        if w.end <= t0:
            lo = max(lo, w.end + post)
        elif w.start >= t1:
            hi = min(hi, w.start - pre)
            break
        else:  # overlap -> the interval contains speech; shrink around it
            if w.start - t0 > t1 - w.end:
                hi = min(hi, w.start - pre)
            else:
                lo = max(lo, w.end + post)
    lo, hi = max(0.0, lo), min(duration, hi)
    return (lo, hi) if hi > lo else None


def _cut(i: int, start: float, end: float, kind: str, reason: str, conf: float = 1.0) -> Cut:
    return Cut(id=f"c{i:04d}", start=round(start, 3), end=round(end, 3), kind=kind,
               reason=reason, confidence=round(conf, 2))


# --- rules ---------------------------------------------------------------------
def silence_cuts(silences: Iterable[tuple[float, float]], words: list[Word],
                 preset: Intensity, duration: float) -> list[Cut]:
    cuts: list[Cut] = []
    words = sorted(words, key=lambda w: w.start)
    first_speech = words[0].start if words else None
    last_speech = words[-1].end if words else None
    for s, e in silences:
        if e - s < preset.min_silence:
            continue
        # leading / trailing dead air: trim hard, keep a short breath-in/out
        if s <= 0.05 and (first_speech is None or e <= first_speech + 0.05):
            start, end = 0.0, max(0.0, e - 0.25)
            reason = f"leading silence {e - s:.2f}s"
        elif e >= duration - 0.05 and (last_speech is None or s >= last_speech - 0.05):
            start, end = min(duration, s + 0.4), duration
            reason = f"trailing silence {e - s:.2f}s"
        else:
            prev = next((w for w in reversed(words) if w.end <= s + 0.3), None)
            keep = preset.sentence_pause if prev and _SENTENCE_END.search(prev.text) \
                else preset.keep_pause
            start, end = s + keep / 2, e - keep / 2
            reason = f"pause {e - s:.2f}s → {keep:.2f}s" + (
                " (sentence beat kept)" if keep == preset.sentence_pause else "")
        if words:
            b = _gap_bounds(words, start, end, preset.pad_before, preset.pad_after, duration)
            if not b:
                continue
            start, end = b
        if end - start >= preset.min_cut:
            cuts.append(_cut(len(cuts), start, end, "silence", reason))
    return cuts


def word_cuts(words: list[Word], preset: Intensity, duration: float) -> list[Cut]:
    """Fillers, stutters, repeated phrases, false starts, isolated discourse markers."""
    words = sorted(words, key=lambda w: w.start)
    out: list[Cut] = []
    n = len(words)

    def span(i: int, j: int, kind: str, reason: str, conf: float) -> None:
        """Remove words[i..j] inclusive, leaving neighbours untouched."""
        # Ideal: a little air around the removed words, a safety pad from neighbours.
        # If the gap is too tight for pads, cut right up to (never into) the neighbour.
        lo_hard = words[i - 1].end + 0.01 if i > 0 else 0.0
        hi_hard = words[j + 1].start - 0.01 if j + 1 < n else duration
        prev_pad = words[i - 1].end + preset.pad_after if i > 0 else 0.0
        next_pad = words[j + 1].start - preset.pad_before if j + 1 < n else duration
        start = max(lo_hard, min(words[i].start, max(prev_pad, words[i].start - 0.04)))
        end = min(hi_hard, max(words[j].end, min(next_pad, words[j].end + 0.05)))
        if end - start >= preset.min_cut:
            out.append(_cut(len(out), start, end, kind, reason, conf))

    i = 0
    while i < n:
        w = words[i]
        t = norm(w.text)
        nxt = norm(words[i + 1].text) if i + 1 < n else ""
        gap_before = w.start - words[i - 1].end if i > 0 else 9.0
        gap_after = words[i + 1].start - w.end if i + 1 < n else 9.0

        if preset.remove_fillers and is_filler(w.text):
            span(i, i, "filler", f'filler "{w.text}"', 0.95)
        elif preset.remove_repeats and t and t == nxt and len(t) > 0 and gap_after < 0.6:
            span(i, i, "repeat", f'repeated word "{w.text} {words[i + 1].text}"', 0.9)
        elif (preset.remove_repeats and i + 3 < n and t
              and (t, norm(words[i + 1].text)) == (norm(words[i + 2].text), norm(words[i + 3].text))
              and words[i + 2].start - words[i + 1].end < 0.6):
            span(i, i + 1, "repeat",
                 f'repeated phrase "{w.text} {words[i + 1].text}"', 0.85)
            i += 1
        elif (preset.remove_false_starts and len(t) >= 2 and nxt and nxt != t
              and (w.text.rstrip().endswith(("-", "—", "–")) or
                   (nxt.startswith(t) and len(nxt) >= len(t) + 2 and len(t) <= 4))
              and gap_after < 0.8):
            span(i, i, "false_start", f'false start "{w.text}" → "{words[i + 1].text}"', 0.75)
        elif (preset.remove_discourse and gap_before > 0.25 and gap_after > 0.25):
            if t in _DISCOURSE:
                span(i, i, "filler", f'isolated discourse marker "{w.text}"', 0.6)
            elif (t, nxt) in _DISCOURSE_BIGRAMS and (
                    i + 2 >= n or words[i + 2].start - words[i + 1].end > 0.25):
                span(i, i + 1, "filler", f'isolated "{w.text} {words[i + 1].text}"', 0.6)
                i += 1
        i += 1
    return out


def merge_cuts(cuts: list[Cut], words: list[Word], min_keep: float = 0.15) -> list[Cut]:
    """Union overlapping cuts; absorb tiny kept slivers that contain no words."""
    items = sorted((c for c in cuts if c.enabled), key=lambda c: c.start)
    merged: list[Cut] = []
    for c in items:
        if merged:
            last = merged[-1]
            sliver = c.start - last.end
            has_word = any(w.start < c.start and w.end > last.end for w in words)
            if c.start <= last.end or (sliver < min_keep and not has_word):
                last.end = max(last.end, c.end)
                if c.reason not in last.reason:
                    last.reason = f"{last.reason}; {c.reason}"
                    last.kind = last.kind if last.kind == c.kind else "mixed"
                last.confidence = min(last.confidence, c.confidence)
                continue
        merged.append(Cut(**c.__dict__))
    for i, c in enumerate(merged):
        c.id = f"c{i:04d}"
    disabled = [c for c in cuts if not c.enabled]
    return merged + disabled


def segments_from_cuts(cuts: list[Cut], duration: float, words: list[Word],
                       source: str = "main") -> list[Segment]:
    active = sorted((c for c in cuts if c.enabled), key=lambda c: c.start)
    segs: list[Segment] = []
    t = 0.0
    for c in active:
        if c.start > t:
            segs.append(Segment(id="", start=t, end=c.start, source=source))
        t = max(t, c.end)
    if t < duration:
        segs.append(Segment(id="", start=t, end=duration, source=source))
    segs = [s for s in segs if s.duration >= 0.04]
    for i, s in enumerate(segs):
        s.id = f"s{i:04d}"
        s.start, s.end = round(s.start, 3), round(s.end, 3)
        s.text = " ".join(w.text for w in words if w.start >= s.start - 0.01 and w.end <= s.end + 0.01)
    return segs


def plan_cuts(silences: list[tuple[float, float]], words: list[Word], preset: Intensity,
              duration: float) -> list[Cut]:
    cuts = silence_cuts(silences, words, preset, duration)
    if words:
        cuts += word_cuts(words, preset, duration)
    return merge_cuts(cuts, words)


def cut_hits_word(cut: Cut, words: list[Word], tolerance: float = 0.0) -> Word | None:
    """Return a kept word whose audio would be clipped by this cut, if any."""
    for w in words:
        if w.start + tolerance < cut.end and w.end - tolerance > cut.start:
            inside = w.start >= cut.start - 1e-3 and w.end <= cut.end + 1e-3
            if not inside:  # partially clipped (fully removed words are intentional)
                return w
    return None
