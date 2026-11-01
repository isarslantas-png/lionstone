"""QA checks for creative features (registered as a core QA hook).

* fx_compiled  — effects were compiled for *this* edit (catches stale plans)
* fx_rendered  — every enabled instance rendered, or why not
* flicker      — ≤ 3 strong luminance flashes per second (photosensitivity)
* exposure     — no long stretches of clipped highlights / crushed shadows
* saturation   — no runaway saturation after looks/effects
"""

from __future__ import annotations

import re

from lionstone.ff import analyze_filter
from lionstone.models import QACheck, QAIssue, QAReport


def _series(path, fps: float = 10.0) -> list[dict]:
    log = analyze_filter(str(path), vf=f"fps={fps},scale=96:-2,signalstats,metadata=print")
    frames: list[dict] = []
    cur: dict = {}
    for line in log.splitlines():
        if "pts_time:" in line:
            if cur:
                frames.append(cur)
            m = re.search(r"pts_time:([\d.]+)", line)
            cur = {"t": float(m.group(1)) if m else 0.0}
        m = re.search(r"lavfi\.signalstats\.(YAVG|YHIGH|YLOW|SATAVG)=([\d.]+)", line)
        if m and cur is not None:
            cur[m.group(1)] = float(m.group(2))
    if cur:
        frames.append(cur)
    return [f for f in frames if "YAVG" in f]


def fx_qa(report: QAReport, ctx: dict) -> None:
    plan = ctx.get("plan")
    if plan is None or not (plan.meta.get("lionstone_fx") or {}).get("instances"):
        return
    from .compile import is_stale
    comp = plan.meta["lionstone_fx"].get("compiled") or {}
    if is_stale(plan):
        report.checks.append(QACheck("fx_compiled", "editorial", "failed",
                                     "effects were compiled for a different edit"))
        report.issues.append(QAIssue("fx_compiled", "high",
                                     "effects/transitions don't match this edit — run "
                                     "`lionstone fx render plan.json`"))
    else:
        report.checks.append(QACheck("fx_compiled", "editorial", "passed",
                                     f"compiled for this edit ({comp.get('fingerprint')})"))
    rep = comp.get("report") or {}
    skipped = rep.get("skipped", [])
    report.checks.append(QACheck("fx_rendered", "technical",
                                 "passed" if not skipped else "warning",
                                 f"{len(rep.get('applied', []))} applied, {len(skipped)} skipped"))
    for s in skipped:
        report.issues.append(QAIssue("fx_rendered", "medium" if s.get("severity") == "error"
                                     else "low", f"{s['preset']} ({s['id']}): {s['reason']}"))

    frames = _series(ctx["path"])
    if not frames:
        report.checks.append(QACheck("flicker", "technical", "skipped", "no frames measured"))
        return
    # flicker: big frame-to-frame luma jumps
    jumps = [b["t"] for a, b in zip(frames, frames[1:]) if abs(b["YAVG"] - a["YAVG"]) > 40]
    worst = 0
    for t in jumps:
        worst = max(worst, sum(1 for u in jumps if t <= u < t + 1.0))
    ok = worst <= 3
    report.checks.append(QACheck("flicker", "technical", "passed" if ok else "failed",
                                 f"max {worst} strong flashes in any 1 s window (limit 3)"))
    if not ok:
        report.issues.append(QAIssue("flicker", "high",
                                     f"{worst} flashes/second — photosensitivity risk"))
    clipped = sum(1 for f in frames if f.get("YHIGH", 0) >= 252 and f["YAVG"] > 200)
    crushed = sum(1 for f in frames if f.get("YLOW", 255) <= 2 and f["YAVG"] < 25)
    frac = (clipped + crushed) / len(frames)
    report.checks.append(QACheck("exposure", "technical", "passed" if frac < 0.15 else "warning",
                                 f"{frac * 100:.0f}% of sampled frames clipped or crushed"))
    if frac >= 0.15:
        report.issues.append(QAIssue("exposure", "medium",
                                     "look/effects clip highlights or crush shadows — lower intensity"))
    sat = max(f.get("SATAVG", 0) for f in frames)
    src = _series(plan.source, fps=2.0)
    src_sat = max((f.get("SATAVG", 0) for f in src), default=0)
    too_much = sat >= 95 and sat > src_sat * 1.15
    report.checks.append(QACheck("saturation", "technical", "warning" if too_much else "passed",
                                 f"peak average saturation {sat:.0f} vs source {src_sat:.0f} "
                                 "(warn if ≥ 95 and +15% over source)"))
    if too_much:
        report.issues.append(QAIssue("saturation", "medium",
                                     "saturation is very high — check skin tones / brand colours"))
