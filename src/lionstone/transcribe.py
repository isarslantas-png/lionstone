"""Speech recognition with word-level timestamps.

Backends
--------
* ``faster-whisper`` (``pip install "lionstone[whisper]"``) — local, free, offline.
* ``json``  — bring your own transcript: Whisper / WhisperX / Deepgram-style
  JSON with word timestamps. Lets you plug in any ASR (cloud or local).
* ``none``  — no ASR: Lionstone falls back to signal-only (silence) editing.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Word


class TranscriptionUnavailable(RuntimeError):
    pass


def transcribe(path: str | Path, *, model: str = "small", language: str | None = None,
               device: str = "auto") -> list[Word]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as e:  # pragma: no cover - optional dependency
        raise TranscriptionUnavailable(
            'faster-whisper is not installed. Run: pip install "lionstone[whisper]" '
            "or pass --transcript words.json / --no-asr"
        ) from e

    compute = "int8" if device in ("cpu", "auto") else "float16"
    wm = WhisperModel(model, device=device, compute_type=compute)
    # Keep disfluencies: the default prompt makes Whisper "clean up" fillers,
    # which is exactly what we need to detect. A filler-rich prompt keeps them.
    prompt = (
        "Umm, let me think like, hmm... Okay, here's what I'm, like, thinking. "
        "Eee, şey, yani, ııı, hani..."
    )
    segments, _info = wm.transcribe(
        str(path), language=language, word_timestamps=True, vad_filter=False,
        initial_prompt=prompt, condition_on_previous_text=False,
    )
    words: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            words.append(Word(text=w.word.strip(), start=float(w.start), end=float(w.end),
                              confidence=float(getattr(w, "probability", 1.0))))
    return [w for w in words if w.text]


def load_words(path: str | Path) -> list[Word]:
    """Load words from common JSON transcript shapes."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw: list[dict] = []
    if isinstance(data, list):
        raw = data
    elif "words" in data:
        raw = data["words"]
    elif "segments" in data:  # whisper / whisperx
        for seg in data["segments"]:
            for w in seg.get("words", []):
                w = dict(w)
                w.setdefault("speaker", seg.get("speaker"))
                raw.append(w)
    elif "results" in data:  # deepgram
        alt = data["results"]["channels"][0]["alternatives"][0]
        raw = alt.get("words", [])
    words = []
    for w in raw:
        text = (w.get("word") or w.get("text") or w.get("punctuated_word") or "").strip()
        if not text or w.get("start") is None or w.get("end") is None:
            continue
        words.append(Word(
            text=text, start=float(w["start"]), end=float(w["end"]),
            confidence=float(w.get("probability", w.get("confidence", w.get("score", 1.0)))),
            speaker=w.get("speaker"),
        ))
    return words


def save_words(words: list[Word], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps({"words": [w.__dict__ for w in words]}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
