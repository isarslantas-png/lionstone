from lionstone import textedit
from lionstone.captions import build_cues, is_rtl, output_words, to_srt, to_vtt, tr_upper
from lionstone.effects import Catalog
from lionstone.models import EditPlan, Word
from lionstone.planner import (
    Chapter,
    EditOptions,
    Speaker,
    build_plan,
    parse_chapter,
    parse_speaker,
    parse_timecode,
)


def words_fixture():
    text = ["Merhaba", "ve", "hoş", "geldiniz.", "Bugün", "ııı", "yapay", "zekâ", "ile", "kurgu", "konuşacağız.", "Bu", "bir", "test.", "Teşekkürler."]
    out, t = [], 1.0
    for w in text:
        out.append(Word(w, t, t + 0.3))
        t += 0.35 + (1.2 if w.endswith(".") else 0)
    return out, t + 1.0


def test_parsers():
    assert parse_timecode("01:02:03.5") == 3723.5
    assert parse_chapter("00:05:10 Giriş").title == "Giriş"
    sp = parse_speaker("Ayşe Yılmaz|Editör|SPEAKER_01")
    assert (sp.name, sp.title, sp.label) == ("Ayşe Yılmaz", "Editör", "SPEAKER_01")


def test_build_plan_graphics_rules():
    words, dur = words_fixture()
    silences = [(w.end + 0.05, nxt.start - 0.05) for w, nxt in zip(words, words[1:])
                if nxt.start - w.end > 1.0]
    opts = EditOptions(title="Bölüm 12", speakers=[Speaker("İsmail", "Host")],
                       chapters=[Chapter(5.0, "Konu")], outro="Görüşmek üzere")
    plan = build_plan("x.mp4", dur, silences, words, opts, Catalog())
    assert plan.output_duration < dur
    assert any(c.kind == "filler" for c in plan.cuts)
    g = sorted(plan.graphics, key=lambda e: e.at)
    for a, b in zip(g, g[1:]):  # never two animated graphics at once
        assert b.at >= a.at + a.duration
    assert all(e.at + e.duration <= plan.output_duration + 1e-6 for e in g)
    # plan round-trips through JSON
    again = EditPlan.from_dict(plan.to_dict())
    assert again.output_duration == plan.output_duration


def test_captions_drop_cut_words_and_format():
    words, dur = words_fixture()
    plan = build_plan("x.mp4", dur, [], words, EditOptions(), Catalog())
    ow = output_words(plan)
    assert "ııı" not in [w.text for w in ow]
    cues = build_cues(ow)
    srt = to_srt(cues)
    assert srt.startswith("1\n00:00:")
    assert to_vtt(cues).startswith("WEBVTT")
    for a, b in zip(cues, cues[1:]):
        assert b.start >= a.end - 1e-6


def test_rtl_and_turkish_upper():
    assert is_rtl("مرحبا بكم")
    assert is_rtl("שלום עולם")
    assert not is_rtl("Merhaba")
    assert tr_upper("istanbul ılık") == "İSTANBUL ILIK"


def test_text_based_editing_delete_and_reorder():
    words, dur = words_fixture()
    plan = build_plan("x.mp4", dur, [], words, EditOptions(), Catalog())
    md = textedit.export(plan)
    lines = [l for l in md.splitlines() if l.startswith("[t")]
    assert len(lines) == 4
    before = plan.output_duration
    # delete sentence 3, move sentence 4 before sentence 2
    edited = "\n".join([lines[0], lines[3], lines[1]])
    stats = textedit.apply(plan, edited)
    assert stats["deleted"] == 1 and stats["reordered"]
    assert plan.output_duration < before
    first_text = [s.text for s in plan.segments if s.text]
    assert first_text[1].startswith("Teşekkürler")
    # re-applying the same file is idempotent
    d1 = plan.output_duration
    textedit.apply(plan, edited)
    assert abs(plan.output_duration - d1) < 1e-6
