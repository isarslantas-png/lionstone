"""Vision features (Pro): face-aware vertical reframing and "graphics cover a face" QA.

Uses OpenCV (``pip install "lionstone[vision]"``). Without it, reframing
falls back to centre crop and the face QA check reports ``skipped`` — never a
silent pass.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from lionstone.captions import STYLES
from lionstone.models import EditPlan, QACheck, QAIssue, QAReport


def _cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except ImportError:
        return None


def available() -> bool:
    cv2 = _cv2()
    if cv2 is None:
        return False
    try:
        return Path(cv2.data.haarcascades, "haarcascade_frontalface_default.xml").exists()
    except AttributeError:
        return False


class FaceFinder:
    def __init__(self):
        cv2 = _cv2()
        if cv2 is None:
            raise RuntimeError('OpenCV missing: pip install "lionstone[vision]"')
        self.cv2 = cv2
        self.det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.caps: dict[str, object] = {}

    def faces(self, path: str, t: float) -> tuple[list[tuple[float, float, float, float]], tuple[int, int]]:
        """Face boxes (x, y, w, h) normalised 0..1 at time t, plus frame size."""
        cap = self.caps.get(path)
        if cap is None:
            cap = self.cv2.VideoCapture(path)
            self.caps[path] = cap
        cap.set(self.cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            return [], (0, 0)
        h, w = frame.shape[:2]
        scale = 480 / max(w, h)
        small = self.cv2.resize(frame, (int(w * scale), int(h * scale)))
        gray = self.cv2.cvtColor(small, self.cv2.COLOR_BGR2GRAY)
        found = self.det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                          minSize=(24, 24))
        sh, sw = gray.shape
        return [(x / sw, y / sh, fw / sw, fh / sh) for x, y, fw, fh in found], (w, h)


def _output_to_source(plan: EditPlan, t: float) -> tuple[float, str]:
    acc = 0.0
    for s in plan.segments:
        if t <= acc + s.duration:
            return s.start + (t - acc), s.source
        acc += s.duration
    last = plan.segments[-1]
    return last.end, last.source


def _src_path(plan: EditPlan, source: str) -> tuple[str, float]:
    srcs = plan.meta.get("sources") or {}
    if source in srcs:
        return srcs[source]["path"], float(srcs[source].get("offset", 0.0))
    return plan.source, 0.0


# --- reframing ---------------------------------------------------------------------
def face_reframer(*, plan: EditPlan, info, W: int, H: int, workdir: Path) -> str:
    """Crop expression that follows the main face (9:16 / 1:1 / 4:5 from landscape)."""
    fallback = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if not available() or not info.video:
        return fallback
    finder = FaceFinder()
    total = plan.output_duration
    step = max(0.5, total / 300)
    keys: list[tuple[float, float]] = []
    t = 0.0
    last = 0.5
    while t <= total:
        st, src = _output_to_source(plan, t)
        path, off = _src_path(plan, src)
        faces, _ = finder.faces(path, st + off)
        if faces:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            last = x + w / 2
        keys.append((t, last))
        t += step
    if not keys:
        return fallback
    # median-smooth then limit pan speed so the camera feels operated, not jittery
    xs = [k[1] for k in keys]
    sm = [statistics.median(xs[max(0, i - 3): i + 4]) for i in range(len(xs))]
    for i in range(1, len(sm)):
        sm[i] = sm[i - 1] + max(-0.04, min(0.04, sm[i] - sm[i - 1]))
    iw, ih = info.video.width, info.video.height
    sw = int(round(iw * H / ih / 2) * 2)
    if sw <= W:
        return fallback

    def px(c: float) -> int:
        return int(min(max(c * sw - W / 2, 0), sw - W))

    expr = str(px(sm[-1]))
    for i in range(len(keys) - 2, -1, -1):
        t0, t1 = keys[i][0], keys[i + 1][0]
        a, b = px(sm[i]), px(sm[i + 1])
        expr = f"if(lt(t,{t1:.2f}),{a}+({b - a})*(t-{t0:.2f})/{t1 - t0:.2f},{expr})"
    (workdir / "reframe.txt").write_text(expr, encoding="utf-8")
    return f"scale=-2:{H},crop={W}:{H}:x='{expr}':y=0"


# --- QA -----------------------------------------------------------------------------
def _overlap(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy / max(aw * ah, 1e-9)


def faces_qa(report: QAReport, ctx: dict) -> None:
    plan: EditPlan | None = ctx.get("plan")
    path = str(ctx.get("path"))
    if plan is None:
        return
    report.checks[:] = [c for c in report.checks if c.name != "faces_covered"]
    if not available():
        report.checks.append(QACheck("faces_covered", "editorial", "skipped",
                                     'needs OpenCV with face models: '
                                     'pip install "lionstone[vision]"'))
        return
    finder = FaceFinder()
    style = STYLES.get((plan.meta.get("options") or {}).get("caption_style", "clean"),
                       STYLES["clean"])
    cap_h = style.size_ratio * 2.4
    cap_box = (0.08, 1 - style.margin_v_ratio - cap_h, 0.84, cap_h)
    probes: list[tuple[float, tuple, str]] = []
    for g in plan.graphics:
        box = (0.05, 0.74, 0.5, 0.16) if g.layer == "lower_thirds" else (0.1, 0.38, 0.8, 0.24)
        probes.append((g.at + g.duration / 2, box, f'graphic "{g.text}"'))
    total = plan.output_duration
    if plan.words:
        n = min(24, int(total / 5) + 1)
        probes += [(total * (i + 0.5) / n, cap_box, "captions") for i in range(n)]
    hits = 0
    for t, box, what in probes:
        faces, _ = finder.faces(path, t)
        for f in faces:
            if _overlap(f, box) > 0.2:
                hits += 1
                report.issues.append(QAIssue("faces_covered", "medium",
                                             f"{what} covers a face", at=round(t, 2)))
                break
    report.checks.append(QACheck("faces_covered", "editorial", "passed" if not hits else "warning",
                                 f"{len(probes)} moments sampled, {hits} with a covered face"))
