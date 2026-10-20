"""Editing intensity presets and delivery loudness profiles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Intensity:
    name: str
    min_silence: float        # silences shorter than this are never touched
    keep_pause: float         # pause left in place of a removed silence
    sentence_pause: float     # longer pause kept after . ? ! (dramatic beat)
    silence_db: float         # silencedetect noise floor
    remove_fillers: bool
    remove_repeats: bool
    remove_false_starts: bool
    remove_discourse: bool    # "yani", "like", "you know"… only when isolated
    pad_before: float = 0.06  # never cut closer than this to a word start
    pad_after: float = 0.09   # …or to a word end (protects trailing consonants)
    min_cut: float = 0.08     # cuts shorter than this are dropped (inaudible gain)


INTENSITIES: dict[str, Intensity] = {
    # Obvious mistakes and long dead air only. Keeps the speaker's rhythm.
    "natural": Intensity("natural", min_silence=1.2, keep_pause=0.6, sentence_pause=0.9,
                         silence_db=-38, remove_fillers=False, remove_repeats=True,
                         remove_false_starts=False, remove_discourse=False),
    # Default. Fillers and stutters go; breaths and meaningful pauses stay.
    "balanced": Intensity("balanced", min_silence=0.7, keep_pause=0.35, sentence_pause=0.55,
                          silence_db=-35, remove_fillers=True, remove_repeats=True,
                          remove_false_starts=True, remove_discourse=False),
    # Tight, fast cuts for Shorts / Reels / TikTok.
    "dynamic": Intensity("dynamic", min_silence=0.35, keep_pause=0.14, sentence_pause=0.25,
                         silence_db=-32, remove_fillers=True, remove_repeats=True,
                         remove_false_starts=True, remove_discourse=True,
                         pad_before=0.04, pad_after=0.06),
}


@dataclass(frozen=True)
class LoudnessProfile:
    name: str
    integrated: float  # LUFS
    true_peak: float   # dBTP
    lra: float
    tolerance: float = 1.0  # ± LU accepted by QA


LOUDNESS: dict[str, LoudnessProfile] = {
    "youtube": LoudnessProfile("youtube", -14.0, -1.0, 11.0),
    "podcast": LoudnessProfile("podcast", -16.0, -1.0, 9.0),     # Apple / Spotify spoken word
    "social": LoudnessProfile("social", -14.0, -1.0, 7.0),       # Reels / TikTok / Shorts
    "broadcast": LoudnessProfile("broadcast", -23.0, -2.0, 15.0),  # EBU R128
}


ASPECTS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}
