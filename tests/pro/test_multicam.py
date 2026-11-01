import shutil
import subprocess

import numpy as np
import pytest

from lionstone.models import EditPlan, Segment
from lionstone.pro import multicam as mc

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
SR = 48000


def _write(x, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1",
                    "-i", "-", str(path)], input=x.astype(np.float32).tobytes(), check=True)


def _bursts(seed, seconds=40):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.003, SR * seconds)
    t = 0.5
    while t < seconds - 2:
        n = int(rng.uniform(0.2, 1.2) * SR)
        i = int(t * SR)
        x[i:i + n] += rng.normal(0, 0.3, n) * np.hanning(n)
        t += rng.uniform(0.4, 2.0)
    return x


def test_sync_finds_offset_and_no_drift(tmp_path):
    room = _bursts(1)
    _write(room, tmp_path / "master.wav")
    _write(room[int(1.25 * SR):], tmp_path / "late.wav")  # camera started 1.25 s late
    r = mc.sync(str(tmp_path / "master.wav"), str(tmp_path / "late.wav"), win=8)
    assert abs(r.offset - (-1.25)) < 0.003
    assert abs(r.drift_ppm) < 50


def test_camera_timeline_rules():
    hop = 0.1
    n = 300
    a = np.full(n, -60.0)
    b = np.full(n, -60.0)
    a[0:100] = -20          # A speaks 0–10 s
    b[100:200] = -20        # B speaks 10–20 s
    a[200:205] = -20        # 0.5 s interjection by A: too short to switch
    b[205:300] = -20
    shots = mc.camera_timeline({"A": a, "B": b}, {"A": "camA", "B": "camB"}, None,
                               mc.SwitchRules(min_shot=2.0), hop)
    cams = [s["camera"] for s in shots]
    assert cams == ["camA", "camB"]
    assert abs(shots[1]["start"] - (10 - 0.12)) < 0.2


def test_apply_timeline_respects_coverage():
    plan = EditPlan(source="m.wav", duration=10, intensity="balanced",
                    segments=[Segment("s0", 0.5, 9.5)])
    shots = [{"start": 0, "end": 10, "camera": "A", "reason": ""}]
    mc.apply_timeline(plan, shots, {"A": (2.0, 10.0), "W": (0.0, 10.0)}, prefer=["W", "A"])
    assert [(s.source, s.start, s.end) for s in plan.segments] == [("W", 0.5, 2.0), ("A", 2.0, 9.5)]
