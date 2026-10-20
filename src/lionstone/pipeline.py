"""Orchestrator — runs the agents in order, caches analysis, loops QA → fix.

Steps are idempotent: analysis results are cached by file fingerprint, so
re-planning or re-rendering never re-transcribes a 90-minute recording.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import qa as qa_mod
from . import textedit
from .effects import Catalog
from .ff import analyze_filter, parse_silences, run
from .ingest import describe, probe
from .models import EditPlan, MediaInfo, QAReport, Word
from .planner import EditOptions, build_plan, plan_graphics
from .plugins import registry
from .presets import INTENSITIES, LOUDNESS
from .render import RenderOptions, RenderResult, render
from .speech import cut_hits_word, segments_from_cuts
from .transcribe import TranscriptionUnavailable, load_words, save_words, transcribe

Log = Callable[[str], None]


def _default_log(msg: str) -> None:
    print(msg, flush=True)


def fingerprint(path: Path) -> str:
    st = path.stat()
    h = hashlib.sha1(f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}".encode())
    with path.open("rb") as f:
        h.update(f.read(1 << 20))
    return h.hexdigest()[:16]


@dataclass
class ASROptions:
    mode: str = "auto"  # auto | whisper | json | none
    model: str = "small"
    language: str | None = None
    transcript: str | None = None  # path for mode=json


@dataclass
class Analysis:
    info: MediaInfo
    words: list[Word]
    silences: list[tuple[float, float]]
    asr_note: str


def analyze(src: Path, outdir: Path, asr: ASROptions, silence_db: float, log: Log) -> Analysis:
    cache = outdir / ".lionstone" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    log("① Ingest — validating media")
    info = probe(src)
    log("   " + describe(info).replace("\n", "\n   "))
    if any(w.startswith("critical") for w in info.warnings):
        raise RuntimeError("source failed validation: " + "; ".join(info.warnings))
    (outdir / "media.json").write_text(json.dumps(info.__dict__, default=lambda o: o.__dict__,
                                                  indent=2), encoding="utf-8")
    fp = fingerprint(src)

    log("② Speech — transcribing with word timestamps")
    words: list[Word] = []
    note = ""
    wcache = cache / f"words-{fp}-{asr.model}-{asr.language or 'auto'}.json"
    if asr.transcript:
        words = load_words(asr.transcript)
        note = f"transcript loaded from {Path(asr.transcript).name}"
    elif asr.mode == "none":
        note = "ASR disabled — signal-only editing"
    elif wcache.exists():
        words = load_words(wcache)
        note = "transcript from cache"
    else:
        try:
            t0 = time.time()
            words = transcribe(src, model=asr.model, language=asr.language)
            save_words(words, wcache)
            note = f"faster-whisper/{asr.model}: {len(words)} words in {time.time() - t0:.0f}s"
        except TranscriptionUnavailable as e:
            if asr.mode == "whisper":
                raise
            note = f"{e} — continuing with signal-only editing"
        except Exception as e:  # model download / runtime failure: degrade, don't die
            if asr.mode == "whisper":
                raise
            note = (f"ASR failed ({type(e).__name__}: {str(e)[:120]}) — continuing with "
                    "signal-only editing")
    if words:
        save_words(words, outdir / "words.json")
    log(f"   {note}")

    log("③ Signal — detecting silence")
    scache = cache / f"silence-{fp}-{silence_db}.json"
    if scache.exists():
        silences = [tuple(x) for x in json.loads(scache.read_text())]
    else:
        lg = analyze_filter(src, af=f"silencedetect=noise={silence_db}dB:d=0.25")
        silences = parse_silences(lg, info.duration)
        scache.write_text(json.dumps(silences))
    log(f"   {len(silences)} silent intervals")
    return Analysis(info, words, silences, note)


def make_plan(src: Path, outdir: Path, opts: EditOptions, asr: ASROptions, *,
              catalog: Catalog, log: Log = _default_log) -> EditPlan:
    preset = INTENSITIES[opts.intensity]
    a = analyze(src, outdir, asr, preset.silence_db, log)
    log(f"④ Decide — building {opts.intensity} edit plan")
    plan = build_plan(str(src.resolve()), a.info.duration, a.silences, a.words, opts, catalog)
    plan.meta["asr_note"] = a.asr_note
    for hook in registry().plan_hooks:
        hook(plan, {"options": opts, "analysis": a, "catalog": catalog, "outdir": outdir})
    plan.save(outdir / "plan.json")
    if plan.words:
        textedit.write(plan, outdir / "transcript.md")
        plan.save(outdir / "plan.json")  # sentences table stored in meta
    removed = plan.duration - plan.output_duration
    by_kind: dict[str, int] = {}
    for c in plan.cuts:
        if c.enabled:
            by_kind[c.kind] = by_kind.get(c.kind, 0) + 1
    log(f"   {plan.duration:.1f}s → {plan.output_duration:.1f}s "
        f"(−{removed:.1f}s, {removed / max(plan.duration, 1e-9) * 100:.0f}%) · "
        + " · ".join(f"{v} {k}" for k, v in sorted(by_kind.items()))
        + f" · {len(plan.graphics)} graphics")
    return plan


def options_from_meta(plan: EditPlan) -> EditOptions:
    from .planner import Chapter, Speaker
    d = dict(plan.meta.get("options", {}))
    d["speakers"] = [Speaker(**s) for s in d.get("speakers", [])]
    d["chapters"] = [Chapter(**c) for c in d.get("chapters", [])]
    known = EditOptions.__dataclass_fields__
    return EditOptions(**{k: v for k, v in d.items() if k in known})


def replan_graphics(plan: EditPlan, catalog: Catalog) -> None:
    plan.graphics = plan_graphics(plan, options_from_meta(plan), catalog)


# --- auto-fix ------------------------------------------------------------------------
def fix_word_clipping(plan: EditPlan) -> int:
    preset = INTENSITIES.get(plan.intensity, INTENSITIES["balanced"])
    fixed = 0
    for c in plan.cuts:
        if not c.enabled:
            continue
        for _ in range(4):
            w = cut_hits_word(c, plan.words)
            if not w:
                break
            if w.start < c.start:  # word sticks into the cut from the left
                c.start = round(w.end + preset.pad_after, 3)
            else:
                c.end = round(w.start - preset.pad_before, 3)
            fixed += 1
        if c.end - c.start < preset.min_cut:
            c.enabled = False
            c.reason += " · disabled by QA (would clip speech)"
    plan.segments = segments_from_cuts(plan.cuts, plan.duration, plan.words)
    return fixed


def renormalize(path: Path, profile: str) -> None:
    prof = LOUDNESS[profile]
    base = f"loudnorm=I={prof.integrated}:TP={prof.true_peak}:LRA={prof.lra}"
    p1 = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
              "-af", base + ":print_format=json", "-f", "null", "-"], check=False)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr or "", re.DOTALL)
    af = base
    if m:
        j = json.loads(m.group(0))
        af = (f"{base}:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
              f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:"
              f"offset={j['target_offset']}:linear=true")
    tmp = path.with_suffix(".fix" + path.suffix)
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(path), "-c:v", "copy",
         "-af", af + ",aresample=48000", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(tmp)])
    shutil.move(tmp, path)


def render_and_verify(plan: EditPlan, outdir: Path, out_name: str, ropts: RenderOptions, *,
                      catalog: Catalog, log: Log = _default_log, max_rounds: int = 2
                      ) -> tuple[RenderResult, QAReport]:
    out = outdir / out_name
    rounds = 0
    while True:
        rounds += 1
        log(f"⑤ Render — pass {rounds}")
        t0 = time.time()
        res = render(plan, out, ropts, catalog=catalog, workdir=outdir / ".lionstone")
        log(f"   {out.name} · {res.width}x{res.height} @ {res.fps} · "
            f"{res.duration:.1f}s in {time.time() - t0:.0f}s")
        for n in res.notes:
            log(f"   note: {n}")
        log("⑥ QA — technical + editorial checks")
        W, H, fps = res.width, res.height, res.fps
        report = qa_mod.run_qa(out, plan, catalog=catalog,
                               expect={"duration": res.duration, "width": W, "height": H,
                                       "fps": fps})
        high = [i for i in report.issues if i.severity in ("critical", "high")]
        if not high or rounds > max_rounds:
            break
        log(f"⑦ Auto-fix — {len(high)} high/critical issue(s)")
        rerender = False
        if any(i.check == "word_integrity" for i in high):
            n = fix_word_clipping(plan)
            log(f"   widened {n} cut boundaries that clipped words")
            replan_graphics(plan, catalog)
            plan.save(outdir / "plan.json")
            rerender = True
        handled = False
        for hook in registry().autofix_hooks:
            handled = hook(report, {"plan": plan, "path": out, "outdir": outdir}) or handled
        if not rerender and any(i.check in ("loudness", "true_peak") for i in high):
            log("   re-normalising audio (two-pass loudnorm, video stream copied)")
            renormalize(out, plan.audio_profile)
            report = qa_mod.run_qa(out, plan, catalog=catalog,
                                   expect={"duration": res.duration, "width": W, "height": H,
                                           "fps": fps})
            break
        if not rerender and not handled:
            break
    qa_mod.save(report, outdir)
    status = "deliverable ✅" if report.deliverable else "BLOCKED 🛑 (critical issues)"
    counts = {s: sum(1 for i in report.issues if i.severity == s)
              for s in ("critical", "high", "medium", "low")}
    summary = " · ".join(f"{v} {k}" for k, v in counts.items() if v) or "no issues"
    checked = sum(1 for c in report.checks if c.status != "skipped")
    skipped = sum(1 for c in report.checks if c.status == "skipped")
    log(f"   {checked} checks run, {skipped} skipped (reported) · {summary}")
    log(f"   QA: {status} · report → qa.md")
    return res, report
