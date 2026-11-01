"""Pro caption styles: per-word highlight ("karaoke pop") for Shorts / Reels."""

from __future__ import annotations

from lionstone.captions import (
    CaptionStyle,
    Cue,
    _ass_escape,
    register_dialogue,
    register_style,
    smart_upper,
)


def _bgr(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{b}{g}{r}&".upper()


def highlight_dialogue(accent: str = "#E8B04B"):
    acc = _bgr(accent)

    def fn(cue: Cue, style: CaptionStyle) -> str:
        n_first = len(cue.lines[0].split()) if len(cue.lines) > 1 else len(cue.words)
        out = []
        for i, w in enumerate(cue.words):
            s = max(0, int((w.start - cue.start) * 1000))
            e = max(s + 40, int((w.end - cue.start) * 1000))
            text = _ass_escape(smart_upper(w.text) if style.uppercase else w.text)
            tag = (f"{{\\1c&HFFFFFF&\\t({s},{s + 1},\\1c{acc}\\fscx110\\fscy110)"
                   f"\\t({e},{e + 1},\\1c&HFFFFFF&\\fscx100\\fscy100)}}")
            sep = "\\N" if i == n_first and i > 0 else (" " if i else "")
            out.append(f"{sep}{tag}{text}")
        return "".join(out)

    return fn


def register(accent: str = "#E8B04B") -> None:
    register_style(CaptionStyle("highlight", size_ratio=0.07, outline=5.0, shadow=0.0,
                                margin_v_ratio=0.24, uppercase=True))
    register_dialogue("highlight", highlight_dialogue(accent))
    register_style(CaptionStyle("highlight-landscape", size_ratio=0.058, outline=4.0,
                                shadow=0.0, margin_v_ratio=0.08))
    register_dialogue("highlight-landscape", highlight_dialogue(accent))


def karaoke_dialogue(accent: str = "#E8B04B"):
    """Words fill with the accent colour as they're spoken (ASS \\kf)."""
    acc = _bgr(accent)

    def fn(cue: Cue, style: CaptionStyle) -> str:
        n_first = len(cue.lines[0].split()) if len(cue.lines) > 1 else len(cue.words)
        out = [f"{{\\1c{acc}\\2c&HFFFFFF&}}"]
        for i, w in enumerate(cue.words):
            nxt = cue.words[i + 1].start if i + 1 < len(cue.words) else w.end
            cs = max(1, int(round((max(nxt, w.end) - w.start) * 100)))
            if i == 0 and w.start > cue.start:
                out.append(f"{{\\k{int(round((w.start - cue.start) * 100))}}}")
            text = _ass_escape(smart_upper(w.text) if style.uppercase else w.text)
            sep = "\\N" if i == n_first and i > 0 else (" " if i else "")
            out.append(f"{sep}{{\\kf{cs}}}{text}")
        return "".join(out)

    return fn


def register_karaoke(accent: str = "#E8B04B") -> None:
    register_style(CaptionStyle("karaoke", size_ratio=0.058, outline=4.0, shadow=0.0,
                                margin_v_ratio=0.08))
    register_dialogue("karaoke", karaoke_dialogue(accent))
