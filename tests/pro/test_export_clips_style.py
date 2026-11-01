import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from lionstone.models import EditPlan, Segment, Word
from lionstone.pro import clips
from lionstone.pro.export import to_edl, to_fcpxml
from lionstone.pro.style import StyleProfile, color_filter, learn

needs_ff = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    d = tmp_path_factory.mktemp("v")
    p = d / "v.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=s=320x180:r=25:d=6", "-f", "lavfi", "-i",
                    "sine=f=300:d=6", "-shortest", "-pix_fmt", "yuv420p", str(p)], check=True)
    return p


@needs_ff
def test_edl_and_fcpxml(video):
    plan = EditPlan(source=str(video), duration=6, intensity="balanced",
                    segments=[Segment("s0", 0.0, 2.0), Segment("s1", 3.0, 5.5)])
    edl = to_edl(plan, 25)
    assert "001  AX" in edl and "01:00:02:00" in edl
    root = ET.fromstring(to_fcpxml(plan).split("\n", 2)[2])
    clips_ = root.findall(".//spine/asset-clip")
    assert len(clips_) == 2 and clips_[1].get("offset") == "2s"


@needs_ff
def test_style_learn(video):
    p = learn([str(video)], "t")
    assert p.tempo in ("slow", "medium", "fast")
    assert p.color_filter.startswith("eq=")


def test_color_filter_bounded():
    f = color_filter(StyleProfile("x", saturation=5, contrast=5, warmth=1))
    assert "saturation=1.300" in f and "contrast=1.200" in f


def test_clip_scoring_prefers_hooks():
    words, t = [], 0.0
    text = ("Why do most people fail at editing? Because they never plan the story first. "
            "It is simple. ") * 4
    for w in text.split():
        words.append(Word(w, t, t + 0.3))
        t += 0.38
    plan = EditPlan(source="x", duration=t, intensity="balanced", words=words,
                    segments=[Segment("s0", 0, t)])
    c = clips.candidates(plan, 5, 20, 10)
    assert c and c[0].hook.startswith("Why")
    chosen = clips.pick(c, 2)
    assert all(a.end <= b.start for a, b in zip(chosen, chosen[1:]))
