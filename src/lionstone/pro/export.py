"""Editable project delivery (Pro): CMX3600 EDL and FCPXML 1.10.

Opens in DaVinci Resolve, Final Cut Pro, Premiere Pro (EDL) and most NLEs.
Every kept segment becomes a clip pointing at the *original* media — the edit
stays fully adjustable by a human editor. Cut reasons travel as comments.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from lionstone.ingest import probe
from lionstone.models import EditPlan


def _rate(fps: float) -> tuple[Fraction, bool]:
    """Frame duration as a fraction + whether it's an NTSC (x/1.001) rate."""
    for nominal in (24, 30, 60):
        if abs(fps - nominal / 1.001) < 0.01:
            return Fraction(1001, nominal * 1000), True
    return Fraction(1, round(fps)), False


def _tc(frames: int, fps_int: int) -> str:
    h, rem = divmod(frames, fps_int * 3600)
    m, rem = divmod(rem, fps_int * 60)
    s, f = divmod(rem, fps_int)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def _sources(plan: EditPlan) -> dict[str, dict]:
    srcs = {"main": {"path": plan.source, "offset": 0.0}}
    for k, v in (plan.meta.get("sources") or {}).items():
        srcs[k] = {"path": v["path"], "offset": float(v.get("offset", 0.0))}
    return srcs


def to_edl(plan: EditPlan, fps: float, title: str = "LIONSTONE EDIT") -> str:
    fi = round(fps)
    srcs = _sources(plan)
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    rec = fi * 3600  # record starts at 01:00:00:00
    multi = len(srcs) > 1
    for n, seg in enumerate(plan.segments, 1):
        src = srcs.get(seg.source, srcs["main"])
        off = src["offset"]
        a = round((seg.start + off) * fps)
        b = round((seg.end + off) * fps)
        length = b - a
        reel = (seg.source[:8] if multi else "AX").upper()
        track = "V" if multi else "B"
        lines.append(f"{n:03d}  {reel:<8} {track:<5} C        "
                     f"{_tc(a, fi)} {_tc(b, fi)} {_tc(rec, fi)} {_tc(rec + length, fi)}")
        lines.append(f"* FROM CLIP NAME: {Path(src['path']).name}")
        if multi:
            ma, mb = round(seg.start * fps), round(seg.end * fps)
            lines.append(f"{n:03d}  AUD      A     C        "
                         f"{_tc(ma, fi)} {_tc(mb, fi)} {_tc(rec, fi)} {_tc(rec + length, fi)}")
            lines.append(f"* FROM CLIP NAME: {Path(plan.source).name}")
        lines.append("")
        rec += length
    return "\n".join(lines)


def to_fcpxml(plan: EditPlan, name: str = "Lionstone Edit") -> str:
    srcs = _sources(plan)
    cams = {k: v for k, v in srcs.items() if k != "main"}
    ref_video = probe(next(iter(cams.values()))["path"] if cams else plan.source)
    v = ref_video.video
    fps = (v.avg_fps or v.fps or 30.0) if v else 30.0
    W, H = (v.width, v.height) if v else (1920, 1080)
    fd, _ = _rate(fps)

    def t(sec: float) -> str:
        frames = round(Fraction(sec).limit_denominator(100000) / fd)
        val = frames * fd
        return f"{val.numerator}/{val.denominator}s" if val.denominator != 1 else f"{val.numerator}s"

    res = [f'<format id="r1" frameDuration="{fd.numerator}/{fd.denominator}s" width="{W}" '
           f'height="{H}"/>']
    ids: dict[str, str] = {}
    for i, (k, s) in enumerate(srcs.items(), start=2):
        info = probe(s["path"])
        ids[k] = f"r{i}"
        uri = Path(s["path"]).resolve().as_uri()
        res.append(
            f'<asset id="r{i}" name={quoteattr(Path(s["path"]).stem)} start="0s" '
            f'duration="{t(info.duration)}" hasVideo="{1 if info.video else 0}" '
            f'hasAudio="{1 if info.audio else 0}" format="r1" audioSources="1" '
            f'audioChannels="{(info.audio.channels if info.audio else 2) or 2}">'
            f'<media-rep kind="original-media" src={quoteattr(uri)}/></asset>')
    spine, offset = [], 0.0
    for seg in plan.segments:
        dur = seg.end - seg.start
        if cams and seg.source in cams:
            cam = cams[seg.source]
            spine.append(
                f'<asset-clip ref="{ids[seg.source]}" name={quoteattr(seg.source)} '
                f'offset="{t(offset)}" start="{t(seg.start + cam["offset"])}" '
                f'duration="{t(dur)}"><adjust-volume amount="-96dB"/>'
                f'<asset-clip ref="{ids["main"]}" lane="-1" offset="{t(seg.start + cam["offset"])}" '
                f'start="{t(seg.start)}" duration="{t(dur)}" name="master audio"/></asset-clip>')
        else:
            spine.append(f'<asset-clip ref="{ids["main"]}" name={quoteattr(seg.id)} '
                         f'offset="{t(offset)}" start="{t(seg.start)}" duration="{t(dur)}"/>')
        offset += dur
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n'
            '<fcpxml version="1.10">\n  <resources>\n    ' + "\n    ".join(res) +
            '\n  </resources>\n  <library>\n    <event name="Lionstone">\n'
            f'      <project name={quoteattr(name)}>\n'
            f'        <sequence format="r1" duration="{t(offset)}" tcStart="0s" tcFormat="NDF" '
            'audioLayout="stereo" audioRate="48k">\n          <spine>\n            ' +
            "\n            ".join(spine) +
            "\n          </spine>\n        </sequence>\n      </project>\n"
            f"      <!-- generated by Lionstone · {escape(str(len(plan.segments)))} clips -->\n"
            "    </event>\n  </library>\n</fcpxml>\n")


def export_all(plan: EditPlan, outdir: Path) -> dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(plan.source).stem
    cams = plan.meta.get("sources") or {}
    ref = probe(next(iter(cams.values()))["path"] if cams else plan.source)
    fps = (ref.video.avg_fps or ref.video.fps) if ref.video else 30.0
    edl = outdir / f"{stem}.edl"
    xml = outdir / f"{stem}.fcpxml"
    edl.write_text(to_edl(plan, fps, stem.upper()[:60]), encoding="utf-8")
    xml.write_text(to_fcpxml(plan, f"{stem} — Lionstone"), encoding="utf-8")
    return {"edl": str(edl), "fcpxml": str(xml)}
