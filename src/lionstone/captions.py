"""Graphics & Subtitle Agent — captions on the *output* timeline.

Produces SRT, WebVTT and a styled ASS file for burn-in. Handles Turkish
casing/diacritics and right-to-left scripts (Arabic, Hebrew, Persian).
Captions live on their own layer, separate from title animations.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .models import EditPlan, Word

RLM = "‏"


@dataclass
class Cue:
    start: float
    end: float
    lines: list[str]
    words: list[Word]


@dataclass(frozen=True)
class CaptionStyle:
    name: str
    font: str = "DejaVu Sans"
    size_ratio: float = 0.052     # of video height
    bold: bool = True
    primary: str = "&H00FFFFFF"   # ASS AABBGGRR
    outline_color: str = "&H00000000"
    back_color: str = "&H80000000"
    border_style: int = 1         # 1 outline+shadow, 3 opaque box
    outline: float = 3.0
    shadow: float = 1.0
    margin_v_ratio: float = 0.075  # keep inside title-safe area
    uppercase: bool = False


STYLES: dict[str, CaptionStyle] = {
    "clean": CaptionStyle("clean"),
    "bold": CaptionStyle("bold", size_ratio=0.06, border_style=3, outline=0.0, shadow=0.0,
                         back_color="&H64000000"),
    "social": CaptionStyle("social", size_ratio=0.068, outline=4.5, shadow=0.0,
                           margin_v_ratio=0.22, uppercase=False),
}


def register_style(style: CaptionStyle) -> None:
    STYLES[style.name] = style


def is_rtl(text: str) -> bool:
    strong = [unicodedata.bidirectional(c) for c in text if c.strip()]
    rtl = sum(1 for b in strong if b in ("R", "AL"))
    ltr = sum(1 for b in strong if b == "L")
    return rtl > ltr


def tr_upper(s: str) -> str:
    """Turkish-aware uppercase (i→İ, ı→I)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


_TR_CHARS = set("ıİşŞğĞçÇöÖüÜ")


def smart_upper(s: str) -> str:
    """Uppercase that respects Turkish dotted/dotless i when the text is Turkish."""
    return tr_upper(s) if any(c in _TR_CHARS for c in s) else s.upper()


def output_words(plan: EditPlan) -> list[Word]:
    """Kept words, re-timed to the output timeline."""
    out: list[Word] = []
    for w in plan.words:
        if plan.source_to_output((w.start + w.end) / 2) is None:
            continue  # word was cut
        s = plan.source_to_output(w.start)
        e = plan.source_to_output(w.end)
        if s is None and e is None:
            continue
        if s is None:
            s = max(0.0, e - (w.end - w.start))
        if e is None:
            e = s + (w.end - w.start)
        out.append(Word(text=w.text, start=s, end=max(e, s + 0.05),
                        confidence=w.confidence, speaker=w.speaker))
    return out


def build_cues(words: list[Word], *, max_chars: int = 42, max_lines: int = 2,
               max_dur: float = 6.0, min_dur: float = 0.9, pause_break: float = 0.55) -> list[Cue]:
    cues: list[Cue] = []
    cur: list[Word] = []

    def flush():
        if not cur:
            return
        lines = _wrap([w.text for w in cur], max_chars, max_lines)
        cues.append(Cue(cur[0].start, cur[-1].end, lines, list(cur)))
        cur.clear()

    for w in words:
        if cur:
            text_len = len(" ".join(x.text for x in cur + [w]))
            gap = w.start - cur[-1].end
            too_long = text_len > max_chars * max_lines
            too_slow = w.end - cur[0].start > max_dur
            speaker_change = bool(w.speaker and cur[-1].speaker and w.speaker != cur[-1].speaker)
            if too_long or too_slow or gap > pause_break or speaker_change:
                flush()
        cur.append(w)
        if w.text.rstrip().endswith((".", "?", "!", "…")) and \
                len(" ".join(x.text for x in cur)) > max_chars * 0.6:
            flush()
    flush()
    # enforce readable minimum durations without overlapping the next cue
    for i, c in enumerate(cues):
        nxt = cues[i + 1].start if i + 1 < len(cues) else c.end + min_dur
        if c.end - c.start < min_dur:
            c.end = min(c.start + min_dur, max(c.end, nxt - 0.02))
    return cues


def _wrap(tokens: list[str], max_chars: int, max_lines: int) -> list[str]:
    text = " ".join(tokens)
    if len(text) <= max_chars or max_lines == 1:
        return [text]
    # balanced two-line split, preferring a break after punctuation
    best, best_score = None, 1e9
    for i in range(1, len(tokens)):
        a, b = " ".join(tokens[:i]), " ".join(tokens[i:])
        score = abs(len(a) - len(b)) - (8 if tokens[i - 1][-1:] in ",.;:?!" else 0)
        if max(len(a), len(b)) > max_chars:
            score += 50
        if score < best_score:
            best, best_score = [a, b], score
    return best or [text]


def _ts(t: float, sep: str = ",") -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def _bidi(line: str) -> str:
    return f"{RLM}{line}" if is_rtl(line) else line


def to_srt(cues: list[Cue]) -> str:
    blocks = []
    for i, c in enumerate(cues, 1):
        body = "\n".join(_bidi(l) for l in c.lines)
        blocks.append(f"{i}\n{_ts(c.start)} --> {_ts(c.end)}\n{body}\n")
    return "\n".join(blocks)


def to_vtt(cues: list[Cue]) -> str:
    out = ["WEBVTT", ""]
    for c in cues:
        out.append(f"{_ts(c.start, '.')} --> {_ts(c.end, '.')}")
        out += [_bidi(l) for l in c.lines]
        out.append("")
    return "\n".join(out)


def _ass_ts(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


DialogueFn = Callable[[Cue, CaptionStyle], str]


def default_dialogue(cue: Cue, style: CaptionStyle) -> str:
    lines = [smart_upper(l) if style.uppercase else l for l in cue.lines]
    return "\\N".join(_ass_escape(l) for l in lines)


def to_ass(cues: list[Cue], width: int, height: int, style: CaptionStyle,
           dialogue: DialogueFn = default_dialogue,
           avoid: list[tuple[float, float]] | None = None) -> str:
    """`avoid`: output-time windows (lower thirds) during which captions are raised."""
    size = int(min(width, height) * style.size_ratio)  # vertical: scale by width
    margin_v = int(height * style.margin_v_ratio)
    margin_h = int(width * 0.06)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{size},{style.primary},&H0000D7FF,{style.outline_color},{style.back_color},{-1 if style.bold else 0},0,0,0,100,100,0,0,{style.border_style},{style.outline},{style.shadow},2,{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    raised = int(height * 0.30)
    rows = []
    for c in cues:
        mv = raised if any(c.start < b and c.end > a for a, b in (avoid or [])) else 0
        rows.append(f"Dialogue: 0,{_ass_ts(c.start)},{_ass_ts(c.end)},Default,,0,0,{mv},,"
                    f"{dialogue(c, style)}")
    return head + "\n".join(rows) + "\n"


def write_captions(plan: EditPlan, outdir: Path, width: int, height: int,
                   style_name: str = "clean", vertical: bool = False) -> dict[str, Path]:
    words = output_words(plan)
    cues = build_cues(words, max_chars=16 if vertical else 42, max_lines=2)
    style = STYLES.get(style_name, STYLES["clean"])
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {
        "srt": outdir / "captions.srt",
        "vtt": outdir / "captions.vtt",
        "ass": outdir / "captions.ass",
    }
    paths["srt"].write_text(to_srt(cues), encoding="utf-8")
    paths["vtt"].write_text(to_vtt(cues), encoding="utf-8")
    avoid = [(g.at, g.at + g.duration) for g in plan.graphics if g.layer == "lower_thirds"]
    paths["ass"].write_text(to_ass(cues, width, height, style, _dialogue_hook(style_name), avoid),
                            encoding="utf-8")
    return paths


_DIALOGUE_HOOKS: dict[str, DialogueFn] = {}


def register_dialogue(style_name: str, fn: DialogueFn) -> None:
    """Plugins can provide per-word animated captions (e.g. keyword highlight)."""
    _DIALOGUE_HOOKS[style_name] = fn


def _dialogue_hook(style_name: str) -> DialogueFn:
    return _DIALOGUE_HOOKS.get(style_name, default_dialogue)
