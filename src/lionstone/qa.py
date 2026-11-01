"""QA Agent — technical and editorial verification of a rendered file.

Principle: a check that did not run is reported as ``skipped`` with a reason.
Lionstone never claims a check it did not perform. Severity drives delivery:
``critical`` blocks delivery, ``high`` triggers auto-fix, ``medium``/``low``
are reported for review.
"""

from __future__ import annotations

import json
import re
import subprocess
from array import array
from pathlib import Path

from .captions import build_cues, output_words
from .effects import Catalog
from .ff import analyze_filter, parse_loudness, run
from .ingest import probe
from .models import EditPlan, QACheck, QAIssue, QAReport
from .planner import reading_time
from .presets import LOUDNESS
from .speech import cut_hits_word


def _intentional(plan: EditPlan, catalog: Catalog | None, t0: float, t1: float) -> bool:
    """Is [t0,t1] covered by a full-frame or dimming graphic (expected dark/static)?"""
    for g in plan.graphics:
        full = False
        if catalog:
            try:
                fx = catalog.get(g.effect)
                full = bool(fx.constraints.get("fullFrame")) or "dimBackground" in fx.parameters
            except Exception:
                full = False
        if full and t0 >= g.at - 0.5 and t1 <= g.at + g.duration + 0.5:
            return True
    return False


# --- technical -------------------------------------------------------------------
def check_decode(path: Path, r: QAReport) -> None:
    proc = run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
               check=False)
    errors = [l for l in (proc.stderr or "").splitlines() if l.strip()]
    if proc.returncode != 0 or errors:
        r.checks.append(QACheck("decode_full", "technical", "failed", f"{len(errors)} decoder errors"))
        r.issues.append(QAIssue("decode_full", "critical",
                                "file does not decode cleanly end-to-end: " + "; ".join(errors[:3])))
    else:
        r.checks.append(QACheck("decode_full", "technical", "passed",
                                "every frame and audio packet decoded without errors"))


def check_format(path: Path, r: QAReport, expect: dict) -> float:
    info = probe(path)
    v, a = info.video, info.audio
    if not a:
        r.checks.append(QACheck("streams", "technical", "failed", "no audio stream"))
        r.issues.append(QAIssue("streams", "critical", "output has no audio"))
        return info.duration
    m = {"duration": info.duration, "video_duration": v.duration if v else None,
         "audio_duration": a.duration}
    r.checks.append(QACheck("streams", "technical", "passed", "video + audio present", m))
    if v and v.duration and a.duration:
        drift = abs(v.duration - a.duration)
        frame = 1 / (v.avg_fps or 30)
        ok = drift <= frame * 2 + 0.05
        r.checks.append(QACheck("av_length", "technical", "passed" if ok else "failed",
                                f"video/audio length difference {drift * 1000:.0f} ms",
                                {"drift_ms": round(drift * 1000, 1)}))
        if not ok:
            r.issues.append(QAIssue("av_length", "critical" if drift > 0.5 else "high",
                                    f"audio and video lengths differ by {drift:.2f}s"))
    if expect.get("duration"):
        diff = abs(info.duration - expect["duration"])
        ok = diff <= max(0.25, expect["duration"] * 0.005)
        r.checks.append(QACheck("plan_duration", "technical", "passed" if ok else "warning",
                                f"output {info.duration:.2f}s vs plan {expect['duration']:.2f}s"))
        if not ok:
            r.issues.append(QAIssue("plan_duration", "medium",
                                    f"output length differs from plan by {diff:.2f}s"))
    if v and expect.get("width"):
        fps_ok = abs((v.avg_fps or 0) - expect["fps"]) < 0.02
        size_ok = (v.width, v.height) == (expect["width"], expect["height"])
        ok = fps_ok and size_ok
        r.checks.append(QACheck("format", "technical", "passed" if ok else "failed",
                                f"{v.width}x{v.height} @ {v.avg_fps:.3f} fps "
                                f"(target {expect['width']}x{expect['height']} @ {expect['fps']})"))
        if not ok:
            r.issues.append(QAIssue("format", "medium", "resolution or frame rate off target"))
    return info.duration


def check_black_freeze(path: Path, r: QAReport, plan: EditPlan | None, catalog, duration: float) -> None:
    log = analyze_filter(path, vf="blackdetect=d=0.4:pix_th=0.10,freezedetect=n=-60dB:d=3")
    blacks = [(float(a), float(b)) for a, b in
              re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)]
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", log)]
    fe = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", log)]
    freezes = [(s, fe[i] if i < len(fe) else duration) for i, s in enumerate(fs)]
    bad_black = [(a, b) for a, b in blacks if not (plan and _intentional(plan, catalog, a, b))]
    r.checks.append(QACheck("black_frames", "technical", "passed" if not bad_black else "failed",
                            f"{len(blacks)} dark intervals, {len(blacks) - len(bad_black)} intentional",
                            {"intervals": blacks}))
    for a, b in bad_black:
        edge = a < 0.2 or b > duration - 0.2
        r.issues.append(QAIssue("black_frames", "medium" if edge or b - a < 1 else "high",
                                f"unexpected black frames {a:.2f}–{b:.2f}s", at=a))
    bad_freeze = [(a, b) for a, b in freezes if not (plan and _intentional(plan, catalog, a, b))
                  and b - a > 5]
    r.checks.append(QACheck("frozen_frames", "technical", "passed" if not bad_freeze else "warning",
                            f"{len(freezes)} static intervals ≥3 s, {len(bad_freeze)} unexplained",
                            {"intervals": freezes}))
    for a, b in bad_freeze:
        r.issues.append(QAIssue("frozen_frames", "medium",
                                f"picture frozen {a:.1f}–{b:.1f}s (check camera / source)", at=a))


def check_loudness(path: Path, r: QAReport, profile: str) -> dict:
    prof = LOUDNESS[profile]
    log = analyze_filter(path, af="ebur128=peak=true", extra=["-vn"])
    m = parse_loudness(log)
    i, tp = m["integrated_lufs"], m["true_peak_dbtp"]
    if i is None:
        r.checks.append(QACheck("loudness", "technical", "skipped", "could not measure"))
        return m
    ok_i = abs(i - prof.integrated) <= prof.tolerance
    ok_tp = tp is None or tp <= prof.true_peak + 0.5
    r.checks.append(QACheck("loudness", "technical", "passed" if ok_i else "failed",
                            f"{i:.1f} LUFS (target {prof.integrated} ±{prof.tolerance})", m))
    r.checks.append(QACheck("true_peak", "technical", "passed" if ok_tp else "failed",
                            f"{tp:.1f} dBTP (ceiling {prof.true_peak})" if tp is not None else "n/a"))
    if not ok_i:
        r.issues.append(QAIssue("loudness", "high",
                                f"integrated loudness {i:.1f} LUFS, target {prof.integrated}",
                                auto_fixable=True))
    if not ok_tp:
        r.issues.append(QAIssue("true_peak", "high", f"true peak {tp:.1f} dBTP exceeds ceiling",
                                auto_fixable=True))
    return m


def check_joins(path: Path, r: QAReport, joins: list[float], sr: int = 24000) -> None:
    """Stream the whole audio once and inspect ±12 ms around every join for clicks."""
    if not joins:
        r.checks.append(QACheck("join_clicks", "technical", "skipped", "no joins (single segment)"))
        return
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                             "-ar", str(sr), "-f", "s16le", "-"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    win = int(0.05 * sr)
    targets = sorted(int(t * sr) for t in joins)
    buf = array("h")
    pos = 0  # absolute sample index of buf[0]
    clicks: list[float] = []
    checked = 0
    ti = 0
    assert proc.stdout
    while ti < len(targets):
        chunk = proc.stdout.read(sr * 2 * 4)
        if not chunk:
            break
        a = array("h")
        a.frombytes(chunk[: len(chunk) // 2 * 2])
        buf.extend(a)
        while ti < len(targets) and targets[ti] + win < pos + len(buf):
            c = targets[ti] - pos
            seg = buf[max(0, c - win): c + win]
            if len(seg) > 10:
                diffs = [abs(seg[k] - seg[k - 1]) for k in range(1, len(seg))]
                center, half = len(diffs) // 2, int(0.012 * sr)
                near = diffs[max(0, center - half): center + half]
                outer = diffs[: max(0, center - half)] + diffs[center + half:]
                peak = max(near) if near else 0
                ref = max(outer) if outer else 0
                # a click is a discontinuity much sharper than anything in the
                # surrounding 50 ms of programme audio
                if peak > 2000 and peak > ref * 2.5:
                    clicks.append(targets[ti] / sr)
                checked += 1
            ti += 1
        keep_from = max(0, (targets[ti] - win - pos) if ti < len(targets) else len(buf))
        keep_from = min(keep_from, len(buf))
        if keep_from > 0:
            del buf[:keep_from]
            pos += keep_from
    proc.kill()  # we may stop reading early once the last join is inspected
    proc.stdout.close()
    proc.wait()
    status = "passed" if not clicks else "warning"
    r.checks.append(QACheck("join_clicks", "technical", status,
                            f"inspected {checked}/{len(joins)} joins, {len(clicks)} suspicious",
                            {"suspicious_at": [round(c, 3) for c in clicks]}))
    for c in clicks:
        r.issues.append(QAIssue("join_clicks", "medium", "possible click / pop at a cut", at=c))


# --- editorial -------------------------------------------------------------------
def check_editorial(plan: EditPlan, r: QAReport, catalog: Catalog | None, duration: float) -> None:
    active = [c for c in plan.cuts if c.enabled]
    if plan.words:
        hits = [(c, cut_hits_word(c, plan.words)) for c in active]
        hits = [(c, w) for c, w in hits if w]
        r.checks.append(QACheck("word_integrity", "editorial", "passed" if not hits else "failed",
                                f"{len(active)} cuts verified against {len(plan.words)} word timestamps"))
        for c, w in hits:
            r.issues.append(QAIssue("word_integrity", "high",
                                    f'cut {c.id} clips the word "{w.text}"',
                                    at=plan.source_to_output(c.start - 0.01), auto_fixable=True))
        review = [c for c in active if c.confidence < 0.7]
        r.checks.append(QACheck("low_confidence_cuts", "editorial",
                                "passed" if not review else "warning",
                                f"{len(review)} cuts flagged for human review"))
        for c in review:
            r.issues.append(QAIssue("low_confidence_cuts", "low", f"review cut {c.id}: {c.reason}",
                                    at=plan.source_to_output(c.start - 0.01)))
        choppy = [s for s in plan.segments if s.duration < 0.45 and s.text]
        r.checks.append(QACheck("choppiness", "editorial",
                                "passed" if len(choppy) <= 3 else "warning",
                                f"{len(choppy)} very short kept fragments"))
        if len(choppy) > 3:
            r.issues.append(QAIssue("choppiness", "medium",
                                    f"{len(choppy)} fragments under 0.45 s — consider a softer intensity"))
        cues = build_cues(output_words(plan))
        bad = [c for c in cues if c.end > duration + 0.1 or c.start < 0]
        overl = sum(1 for a, b in zip(cues, cues[1:]) if b.start < a.end - 1e-3)
        ok = not bad and not overl
        r.checks.append(QACheck("caption_timing", "editorial", "passed" if ok else "failed",
                                f"{len(cues)} cues inside timeline, {overl} overlaps"))
        if not ok:
            r.issues.append(QAIssue("caption_timing", "high", "caption cues out of range or overlapping"))
    else:
        r.checks.append(QACheck("word_integrity", "editorial", "skipped",
                                "no transcript — signal-only edit (cuts limited to silences)"))
        r.checks.append(QACheck("caption_timing", "editorial", "skipped", "no transcript"))

    g = sorted(plan.graphics, key=lambda e: e.at)
    overlaps = [(a.id, b.id) for a, b in zip(g, g[1:]) if b.at < a.at + a.duration]
    short = [e for e in g if e.duration < reading_time(f"{e.text} {e.subtext}") * 0.8]
    outside = [e for e in g if e.at + e.duration > duration + 0.05]
    ok = not overlaps and not short and not outside
    r.checks.append(QACheck("graphics_rules", "editorial", "passed" if ok else "failed",
                            f"{len(g)} graphics · overlaps {len(overlaps)} · too short {len(short)} "
                            f"· outside video {len(outside)}"))
    for a, b in overlaps:
        r.issues.append(QAIssue("graphics_rules", "medium", f"graphics {a} and {b} overlap"))
    for e in short:
        r.issues.append(QAIssue("graphics_rules", "medium",
                                f'"{e.text}" is on screen too briefly to read', at=e.at))
    r.checks.append(QACheck("faces_covered", "editorial", "skipped",
                            "needs face detection (vision QA, needs OpenCV)"))
    r.checks.append(QACheck("camera_choice", "editorial", "skipped",
                            "single-camera edit" if not plan.meta.get("multicam") else
                            "verified by multicam plugin"))


def joins_from_plan(plan: EditPlan) -> list[float]:
    t, out = 0.0, []
    for s in plan.segments[:-1]:
        t += s.duration
        out.append(t)
    return out


def run_qa(path: str | Path, plan: EditPlan | None = None, *, expect: dict | None = None,
           catalog: Catalog | None = None) -> QAReport:
    p = Path(path)
    r = QAReport(file=str(p))
    check_decode(p, r)
    duration = check_format(p, r, expect or {})
    check_black_freeze(p, r, plan, catalog, duration)
    check_loudness(p, r, plan.audio_profile if plan else "youtube")
    if plan:
        check_joins(p, r, joins_from_plan(plan))
        check_editorial(plan, r, catalog, duration)
    from .plugins import registry
    for hook in registry().qa_hooks:
        try:
            hook(r, {"path": p, "plan": plan})
        except Exception as e:  # plugin failure is reported, never hidden
            r.checks.append(QACheck(f"plugin:{getattr(hook, '__name__', 'hook')}", "technical",
                                    "skipped", f"plugin error: {e}"))
    return r


SEV_ICON = {"critical": "🛑", "high": "🔴", "medium": "🟠", "low": "🟡"}
STATUS_ICON = {"passed": "✅", "failed": "❌", "warning": "⚠️", "skipped": "⏭️"}


def to_markdown(r: QAReport) -> str:
    lines = [f"# QA report — `{Path(r.file).name}`", "",
             f"**Deliverable:** {'yes' if r.deliverable else 'NO — critical issues'}", ""]
    for group in ("technical", "editorial"):
        lines += [f"## {group.title()} checks", "", "| | Check | Result |", "|---|---|---|"]
        for c in r.checks:
            if c.group == group:
                lines.append(f"| {STATUS_ICON.get(c.status, '')} | `{c.name}` | {c.detail} |")
        lines.append("")
    if r.issues:
        lines += ["## Issues", "", "| Severity | Check | At | Message |", "|---|---|---|---|"]
        for i in sorted(r.issues, key=lambda i: ["critical", "high", "medium", "low"].index(i.severity)):
            at = f"{i.at:.2f}s" if i.at is not None else "—"
            lines.append(f"| {SEV_ICON[i.severity]} {i.severity} | `{i.check}` | {at} | {i.message} |")
    else:
        lines += ["No issues found."]
    lines += ["", "_Skipped checks were not performed and are not counted as passed._", ""]
    return "\n".join(lines)


def save(r: QAReport, outdir: Path, stem: str = "qa") -> tuple[Path, Path]:
    j = outdir / f"{stem}.json"
    m = outdir / f"{stem}.md"
    j.write_text(json.dumps(r.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    m.write_text(to_markdown(r), encoding="utf-8")
    return j, m
