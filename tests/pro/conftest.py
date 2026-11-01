import shutil
import subprocess

import pytest


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Each test gets its own ~/.config/lionstone (favourites, personal presets)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("LIONSTONE_STUDIO_DIR", raising=False)
    monkeypatch.delenv("LIONSTONE_USER", raising=False)


def _ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def media(tmp_path_factory) -> dict:
    """Synthetic talking clip with pauses (→ several segments and joins) + a plan."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("needs ffmpeg")
    d = tmp_path_factory.mktemp("fxmedia")
    parts = []
    for i, (kind, dur) in enumerate([("t", 3.6), ("s", 3.6), ("t", 3.8), ("s", 3.4), ("t", 3.6),
                                     ("s", 3.8), ("t", 3.6)]):
        p = d / f"p{i}.wav"
        src = (f"anoisesrc=d={dur}:c=pink:a=0.002:r=48000" if kind == "s" else
               f"sine=f={200 + 30 * i}:d={dur}:r=48000,volume=0.4,tremolo=f=5:d=0.5")
        _ff("-f", "lavfi", "-i", src, "-ac", "1", str(p))
        parts.append(p)
    ins = sum((["-i", str(p)] for p in parts), [])
    _ff(*ins, "-filter_complex", f"concat=n={len(parts)}:v=0:a=1", str(d / "a.wav"))
    clip = d / "talk.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=480x270:r=25:d=40", "-i", str(d / "a.wav"), "-shortest",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip))
    from lionstone.cli import main
    out = d / "plan"
    assert main(["plan", str(clip), "-o", str(out), "--no-asr"]) == 0
    return {"clip": clip, "plan": out / "plan.json", "dir": d}


@pytest.fixture
def plan_copy(media, tmp_path):
    from lionstone.models import EditPlan
    p = tmp_path / "plan.json"
    EditPlan.load(media["plan"]).save(p)
    return p
