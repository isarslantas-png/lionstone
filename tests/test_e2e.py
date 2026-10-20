"""End-to-end: synthesize a talking clip with FFmpeg, edit it, verify with QA."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lionstone.cli import main

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("media")
    # speech-like tone bursts separated by long pauses with a quiet noise floor
    parts = []
    for i, (kind, dur) in enumerate([("s", 1.2), ("t", 2.0), ("s", 2.5), ("t", 2.5), ("s", 1.5),
                                     ("t", 1.8), ("s", 1.0)]):
        p = d / f"p{i}.wav"
        src = (f"anoisesrc=d={dur}:c=pink:a=0.003:r=48000" if kind == "s" else
               f"sine=f={180 + 40 * i}:d={dur}:r=48000,volume=0.4,tremolo=f=5:d=0.6")
        _ff("-f", "lavfi", "-i", src, "-ac", "1", str(p))
        parts.append(p)
    inputs = sum((["-i", str(p)] for p in parts), [])
    _ff(*inputs, "-filter_complex", f"concat=n={len(parts)}:v=0:a=1", str(d / "a.wav"))
    out = d / "talk.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=12.5", "-i", str(d / "a.wav"),
        "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(out))
    return out


def test_edit_signal_only(clip: Path, tmp_path: Path):
    out = tmp_path / "out"
    code = main(["edit", str(clip), "-o", str(out), "--no-asr", "--fast",
                 "--title", "Bölüm 1 — Giriş", "--profile", "podcast"])
    assert code == 0
    video = out / "talk.edit.mp4"
    assert video.exists()
    plan = json.loads((out / "plan.json").read_text())
    assert plan["meta"]["asr"] is False
    assert sum(s["end"] - s["start"] for s in plan["segments"]) < plan["duration"] - 3
    qa = json.loads((out / "qa.json").read_text())
    assert qa["deliverable"]
    checks = {c["name"]: c["status"] for c in qa["checks"]}
    assert checks["decode_full"] == "passed"
    assert checks["loudness"] == "passed"
    assert checks["word_integrity"] == "skipped"  # honest: no transcript, not "passed"


def test_cuts_restore_roundtrip(clip: Path, tmp_path: Path):
    out = tmp_path / "o2"
    assert main(["plan", str(clip), "-o", str(out), "--no-asr"]) == 0
    plan_path = out / "plan.json"
    before = json.loads(plan_path.read_text())
    first = before["cuts"][1]["id"]
    assert main(["cuts", str(plan_path), "--restore", first]) == 0
    after = json.loads(plan_path.read_text())
    dur = lambda p: sum(s["end"] - s["start"] for s in p["segments"])
    assert dur(after) > dur(before)


def test_degrades_without_drawtext_and_libass(clip: Path, tmp_path: Path, monkeypatch):
    """Builds without libfreetype/libass (e.g. Homebrew) must still deliver, and say so."""
    import lionstone.ff as ff
    import lionstone.render as render
    monkeypatch.setattr(render, "has_filter", lambda name: name not in ("drawtext", "subtitles"))
    out = tmp_path / "o3"
    words = tmp_path / "w.json"
    words.write_text(json.dumps({"words": [{"word": "hello.", "start": 1.3, "end": 1.9}]}))
    code = main(["edit", str(clip), "-o", str(out), "--fast", "--transcript", str(words),
                 "--title", "Başlık", "--renderer", "ffmpeg"])
    assert code == 0
    qa = json.loads((out / "qa.json").read_text())
    names = {i["check"] for i in qa["issues"]}
    assert {"graphics_rendered", "captions_burn"} <= names
    assert (out / "talk.edit.srt").exists()
    assert ff.has_filter("loudnorm")
