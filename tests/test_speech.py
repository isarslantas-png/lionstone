from lionstone.models import Cut, Word
from lionstone.presets import INTENSITIES
from lionstone.speech import (
    cut_hits_word,
    is_filler,
    merge_cuts,
    norm,
    plan_cuts,
    segments_from_cuts,
    silence_cuts,
    word_cuts,
)


def W(text, s, e, spk=None):
    return Word(text, s, e, speaker=spk)


def test_filler_lexicon_en_tr():
    for f in ["um", "Uhh", "erm", "hmm", "ııı", "Eee", "eeh", "öö", "umm,"]:
        assert is_filler(f), f
    for w in ["a", "e", "I", "um-brella", "the", "evet", "şey"]:
        assert not is_filler(w), w


def test_turkish_normalisation():
    assert norm("İstanbul,") == "istanbul"
    assert norm("IŞIK") == "ışık"


def test_silence_cut_keeps_pause_and_never_touches_words():
    words = [W("Hello.", 1.0, 1.5), W("Next", 4.0, 4.4)]
    cuts = silence_cuts([(1.55, 3.95)], words, INTENSITIES["balanced"], 6.0)
    assert len(cuts) == 1
    c = cuts[0]
    assert c.start >= 1.5 + INTENSITIES["balanced"].pad_after - 1e-6
    assert c.end <= 4.0 - INTENSITIES["balanced"].pad_before + 1e-6
    assert "sentence beat" in c.reason  # pause after "." keeps a longer beat


def test_short_silence_untouched_in_natural():
    words = [W("a", 0, 0.3), W("b", 1.0, 1.3)]
    assert silence_cuts([(0.3, 1.0)], words, INTENSITIES["natural"], 2.0) == []


def test_filler_removed_without_clipping_neighbours():
    words = [W("Today", 0.0, 0.40), W("um,", 0.45, 0.70), W("we", 0.72, 0.90)]
    cuts = word_cuts(words, INTENSITIES["balanced"], 2.0)
    assert [c.kind for c in cuts] == ["filler"]
    c = cuts[0]
    assert c.start >= 0.40 and c.end <= 0.72
    assert c.start <= 0.45 and c.end >= 0.70  # filler fully removed
    assert cut_hits_word(c, words) is None


def test_repeat_and_false_start():
    words = [W("the", 0.0, 0.2), W("the", 0.25, 0.45), W("edit", 0.5, 0.8),
             W("gel", 1.0, 1.2), W("geldim", 1.25, 1.7)]
    kinds = sorted(c.kind for c in word_cuts(words, INTENSITIES["balanced"], 3.0))
    assert kinds == ["false_start", "repeat"]


def test_phrase_repeat():
    ws = [W("I", 0, .1), W("think", .15, .4), W("I", .45, .55), W("think", .6, .9), W("so", 1, 1.2)]
    cuts = word_cuts(ws, INTENSITIES["balanced"], 2.0)
    assert len(cuts) == 1 and "phrase" in cuts[0].reason


def test_discourse_markers_only_in_dynamic_and_isolated():
    ws = [W("Bu", 0, .3), W("yani", .9, 1.2), W("güzel", 1.8, 2.2)]
    assert word_cuts(ws, INTENSITIES["balanced"], 3) == []
    assert len(word_cuts(ws, INTENSITIES["dynamic"], 3)) == 1
    tight = [W("Bu", 0, .3), W("yani", .32, .5), W("güzel", .52, .9)]
    assert word_cuts(tight, INTENSITIES["dynamic"], 3) == []


def test_merge_and_segments_cover_timeline():
    cuts = [Cut("a", 1.0, 2.0, "silence", "x"), Cut("b", 1.8, 2.5, "filler", "y"),
            Cut("c", 2.6, 3.0, "silence", "z")]
    merged = merge_cuts(cuts, [])
    assert len(merged) == 1 and merged[0].start == 1.0 and merged[0].end == 3.0
    segs = segments_from_cuts(merged, 5.0, [])
    assert [(s.start, s.end) for s in segs] == [(0.0, 1.0), (3.0, 5.0)]


def test_disabled_cut_restores_material():
    cuts = [Cut("a", 1.0, 2.0, "silence", "x", enabled=False)]
    segs = segments_from_cuts(cuts, 5.0, [])
    assert len(segs) == 1 and segs[0].duration == 5.0


def test_plan_cuts_signal_only():
    cuts = plan_cuts([(0.0, 1.5), (3.0, 5.0), (8.0, 10.0)], [], INTENSITIES["balanced"], 10.0)
    assert cuts[0].reason.startswith("leading")
    assert cuts[-1].reason.startswith("trailing")
    assert all(c.enabled for c in cuts)
