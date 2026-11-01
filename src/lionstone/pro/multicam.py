"""Synchronization Agent + Camera & Edit Decision Agent (Pro).

Sync
----
Coarse alignment on onset envelopes (10 ms), refined on raw audio (0.125 ms),
then re-measured in the middle and at the end of the recording to detect clock
drift. A single start alignment is not trusted on long recordings.

Switching
---------
Per-mic loudness (10 Hz) → active speaker with hysteresis → camera timeline
with a minimum shot length, a wide shot for crosstalk, and cutaways to the wide
on very long monologues. Every switch carries a reason.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from lionstone.ingest import probe
from lionstone.models import EditPlan, Segment

from .audio_io import decode_mono, onset_envelope, rms_db, xcorr_lag

SR = 8000


@dataclass
class SyncResult:
    source: str
    offset: float  # other_time = master_time + offset
    confidence: float
    drift_ppm: float = 0.0
    checks: list[dict] = field(default_factory=list)
    warning: str = ""


def _offset_at(ref: str, other: str, t: float, win: float, max_lag_s: float,
               approx: float | None = None) -> tuple[float, float]:
    """Offset (s) such that other(t + off) ≈ ref(t), measured around master time t."""
    a = decode_mono(ref, SR, t, win)
    if approx is None:
        b = decode_mono(other, SR, max(0.0, t - max_lag_s), win + 2 * max_lag_s)
        pad = t - max(0.0, t - max_lag_s)
        ea, eb = onset_envelope(a, SR), onset_envelope(b, SR)
        lag, conf = xcorr_lag(ea, eb, max_lag=len(eb))
        coarse = lag * 0.01 - pad
    else:
        coarse, conf = approx, 1.0
    # fine: raw-audio correlation in a ±50 ms window around the coarse estimate
    start_b = max(0.0, t + coarse - 0.05)
    b2 = decode_mono(other, SR, start_b, win + 0.1)
    lag2, conf2 = xcorr_lag(a - a.mean(), b2 - b2.mean(), max_lag=int(0.1 * SR))
    fine = start_b - t + lag2 / SR
    if abs(fine - coarse) > 0.06:  # fine search drifted off: keep coarse
        return coarse, conf
    return fine, max(conf, conf2) if approx is None else conf2


def sync(master: str, other: str, *, name: str = "", max_lag_s: float = 30.0,
         win: float = 20.0) -> SyncResult:
    dur = min(probe(master).duration, probe(other).duration + max_lag_s)
    t0 = min(5.0, max(0.0, dur * 0.05))
    off0, conf0 = _offset_at(master, other, t0, min(win, dur / 3), max_lag_s)
    res = SyncResult(source=name or Path(other).stem, offset=round(off0, 4),
                     confidence=round(conf0, 3))
    res.checks.append({"at": round(t0, 1), "offset": round(off0, 4)})
    if dur > 3 * win:
        for frac in (0.5, 0.9):
            t = dur * frac - win
            if t <= t0 + win:
                continue
            o, c = _offset_at(master, other, t, win, max_lag_s, approx=off0)
            res.checks.append({"at": round(t, 1), "offset": round(o, 4), "confidence": round(c, 3)})
        last = res.checks[-1]
        span = last["at"] - t0
        if span > 0:
            res.drift_ppm = round((last["offset"] - off0) / span * 1e6, 1)
    if res.confidence < 0.15:
        res.warning = "low correlation — check that both files recorded the same room audio"
    if abs(res.drift_ppm) > 20:
        res.warning = (f"clock drift {res.drift_ppm} ppm "
                       f"(≈{abs(res.drift_ppm) * dur / 1e6 * 1000:.0f} ms over the recording)")
    return res


# --- speaker activity & camera choice ---------------------------------------------
@dataclass
class SwitchRules:
    min_shot: float = 2.2
    max_shot: float = 22.0
    cutaway: float = 3.0
    margin_db: float = 6.0
    vad_db: float = -42.0
    lead: float = 0.12  # cut slightly before the new speaker's first syllable
    persist: float = 0.8  # a new speaker must hold the floor this long ("yeah" ≠ a turn)


def activity(mics: dict[str, str], offsets: dict[str, float], duration: float,
             hop: float = 0.1) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    n = int(duration / hop) + 1
    for spk, path in mics.items():
        off = offsets.get(spk, 0.0)
        x = decode_mono(path, SR, max(0.0, off))
        pad = int(max(0.0, -off) * SR)
        if pad:
            x = np.concatenate([np.zeros(pad, dtype=np.float32), x])
        e = rms_db(x, SR, hop)
        e = np.pad(e, (0, max(0, n - len(e))), constant_values=-120.0)[:n]
        # 300 ms median smoothing removes plosives and clicks
        k = 3
        e = np.array([np.median(e[max(0, i - k): i + k + 1]) for i in range(len(e))])
        out[spk] = e
    return out


def camera_timeline(act: dict[str, np.ndarray], cam_of: dict[str, str], wide: str | None,
                    rules: SwitchRules, hop: float = 0.1) -> list[dict]:
    """Return [{start, end, camera, reason}] covering the whole master timeline."""
    speakers = list(act)
    n = len(next(iter(act.values())))
    E = np.stack([act[s] for s in speakers])  # (speakers, frames)
    raw: list[str | None] = []
    for i in range(n):
        col = E[:, i]
        order = np.argsort(col)[::-1]
        top = col[order[0]]
        if top < rules.vad_db:
            raw.append(None)  # silence: hold current shot
        elif len(col) > 1 and top - col[order[1]] < rules.margin_db and col[order[1]] > rules.vad_db:
            raw.append("__both__")
        else:
            raw.append(speakers[order[0]])
    shots: list[dict] = []
    cur_cam = cam_of.get(speakers[0], wide or next(iter(cam_of.values())))
    cur_start = 0.0
    reason = "opening"
    for i, who in enumerate(raw):
        t = i * hop
        if who is None:
            continue
        want = (wide if who == "__both__" and wide else cam_of.get(who, cur_cam))
        if want != cur_cam and t - cur_start >= rules.min_shot:
            # hysteresis: the new state must persist before we cut to it
            window = raw[i: i + int(rules.persist / hop)]
            if sum(1 for w in window if w == who) >= len(window) * 0.7:
                cut = max(cur_start + rules.min_shot, t - rules.lead)
                shots.append({"start": round(cur_start, 3), "end": round(cut, 3),
                              "camera": cur_cam, "reason": reason})
                cur_cam, cur_start = want, cut
                reason = "crosstalk → wide" if who == "__both__" else f"{who} speaks"
        elif wide and cur_cam != wide and t - cur_start >= rules.max_shot:
            shots.append({"start": round(cur_start, 3), "end": round(t, 3), "camera": cur_cam,
                          "reason": reason})
            shots.append({"start": round(t, 3), "end": round(t + rules.cutaway, 3),
                          "camera": wide, "reason": "long monologue → wide cutaway"})
            cur_start = t + rules.cutaway
            reason = "back from cutaway"
    shots.append({"start": round(cur_start, 3), "end": round(n * hop, 3), "camera": cur_cam,
                  "reason": reason})
    return [s for s in shots if s["end"] - s["start"] > 0.05]


def coverage(cams: dict[str, str], offsets: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Master-time range each camera actually recorded (cameras start/stop at different times)."""
    out = {}
    for name, path in cams.items():
        off = offsets.get(name, 0.0)
        out[name] = (max(0.0, -off), probe(path).duration - off)
    return out


def _cover(lo: float, hi: float, want: str, cov: dict[str, tuple[float, float]],
           prefer: list[str]) -> list[tuple[float, float, str]]:
    """Assign [lo, hi] to `want`, handing parts it did not record to another camera."""
    a, b = cov.get(want, (float("-inf"), float("inf")))
    if a <= lo and hi <= b:
        return [(lo, hi, want)]
    pieces = []
    for x0, x1 in ((lo, min(hi, a)), (max(lo, a), min(hi, b)), (max(lo, b), hi)):
        if x1 - x0 <= 1e-3:
            continue
        if a <= x0 and x1 <= b:
            pieces.append((x0, x1, want))
            continue
        alt = next((c for c in prefer if c != want and cov[c][0] <= x0 and x1 <= cov[c][1]),
                   want)
        pieces.append((x0, x1, alt))
    return pieces


def apply_timeline(plan: EditPlan, shots: list[dict],
                   cov: dict[str, tuple[float, float]] | None = None,
                   prefer: list[str] | None = None) -> None:
    """Split kept segments at camera switches; tag each piece with its camera."""
    new: list[Segment] = []
    cov = cov or {}
    prefer = prefer or list(cov)
    for seg in plan.segments:
        for sh in shots:
            lo, hi = max(seg.start, sh["start"]), min(seg.end, sh["end"])
            if hi - lo > 0.04:
                for x0, x1, cam in _cover(lo, hi, sh["camera"], cov, prefer):
                    new.append(Segment(id="", start=round(x0, 3), end=round(x1, 3), source=cam))
    # no camera flashes: a piece shorter than min_piece takes its neighbour's camera
    min_piece = 0.6
    for i, s in enumerate(new):
        if s.end - s.start < min_piece and len(new) > 1:
            prev = new[i - 1] if i > 0 else None
            nxt = new[i + 1] if i + 1 < len(new) else None
            touches_prev = prev is not None and abs(prev.end - s.start) < 1e-3
            touches_next = nxt is not None and abs(nxt.start - s.end) < 1e-3
            order = ([nxt, prev] if touches_next and not touches_prev else [prev, nxt])
            for cand in order:
                if cand is None:
                    continue
                a, b = cov.get(cand.source, (float("-inf"), float("inf")))
                if a <= s.start and s.end <= b:  # never assign footage a camera didn't record
                    s.source = cand.source
                    break
    # merge adjacent pieces from the same camera that are contiguous in source time
    merged: list[Segment] = []
    for s in new:
        if merged and merged[-1].source == s.source and abs(merged[-1].end - s.start) < 1e-3:
            merged[-1].end = s.end
        else:
            merged.append(s)
    for i, s in enumerate(merged):
        s.id = f"s{i:04d}"
        s.text = " ".join(w.text for w in plan.words
                          if w.start >= s.start - 0.01 and w.end <= s.end + 0.01)
    plan.segments = merged


def mix_mics(mics: dict[str, str], offsets: dict[str, float], out: Path, duration: float) -> Path:
    """Sync and mix isolated mics; idle mics are gated to cut room bleed."""
    args = ["ffmpeg", "-v", "error", "-y"]
    chains = []
    for i, (spk, path) in enumerate(mics.items()):
        off = offsets.get(spk, 0.0)
        if off >= 0:
            args += ["-ss", f"{off:.4f}", "-i", path]
            pre = ""
        else:
            args += ["-i", path]
            pre = f"adelay={-off * 1000:.1f}:all=1,"
        chains.append(f"[{i}:a]{pre}aresample=48000,highpass=f=70,"
                      f"agate=threshold=0.02:ratio=3:attack=5:release=250:range=0.25[m{i}]")
    n = len(mics)
    graph = ";".join(chains) + ";" + "".join(f"[m{i}]" for i in range(n)) + \
        f"amix=inputs={n}:normalize=0:duration=longest,atrim=0:{duration:.3f}[out]"
    args += ["-filter_complex", graph, "-map", "[out]", "-ac", "1", "-c:a", "pcm_s16le", str(out)]
    subprocess.run(args, check=True)
    return out


def report(syncs: list[SyncResult], shots: list[dict]) -> dict:
    counts: dict[str, float] = {}
    for s in shots:
        counts[s["camera"]] = counts.get(s["camera"], 0) + s["end"] - s["start"]
    return {"sync": [asdict(s) for s in syncs], "shots": len(shots),
            "screen_time": {k: round(v, 1) for k, v in counts.items()}}


def save_report(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
