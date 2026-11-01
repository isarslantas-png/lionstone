"""Reel FX pack: catalog entries, renderers and the Studio showcase reel."""

import subprocess

import pytest

from lionstone.ff import has_filter
from lionstone.pro.features.catalog import Catalog
from lionstone.pro.features.params import ParamError, resolve
from lionstone.pro.features.renderers import ffmpeg_adapter as fa
from lionstone.pro.features.renderers import reel_fx

CAT = Catalog()
REEL = [p for p in CAT.presets.values() if p.category == "reel-fx"]


def test_pack_size_and_tiers():
    assert len(REEL) == 12
    tiers = [p.tier for p in REEL]
    assert tiers.count("pro") == 8 and tiers.count("studio") == 4
    for p in REEL:
        assert p.usable and p.kind == "effect" and p.pipeline == "filter"
        assert p.license["source"] == "lionstone-original"
        assert fa.implemented(p.id), p.id
        assert " — " in p.description  # one-line promise — details


def test_registry_is_complete():
    assert set(reel_fx.REEL_FILTERS) == {p.id for p in REEL}


def _render(pid, w, h, params=None):
    p = CAT.get(pid)
    prm = resolve(p.parameters, params)
    c = fa.RCtx(w, h, 25, 2.0)
    frag = fa.FILTERS[p.id](prm, [(0.3, 1.7)], c)
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=25:d=2",
         "-filter_complex", f"[0:v]format=yuv420p[s];[s]{frag},format=yuv420p[o]",
         "-map", "[o]", "-f", "null", "-"], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[-800:]


@pytest.mark.parametrize("pid", [p.id for p in REEL])
def test_renders_vertical_and_landscape(pid):
    _render(pid, 108, 192)   # 9:16 reel
    _render(pid, 192, 108)   # 16:9


def test_parameters_change_the_graph():
    c = fa.RCtx(1080, 1920, 30, 4)
    a = reel_fx.insight_split(resolve(CAT.get("insight-split").parameters, None), [(0, 4)], c)
    b = reel_fx.insight_split(resolve(CAT.get("insight-split").parameters,
                                      {"values": [0.2, 0.9], "bars": 2}), [(0, 4)], c)
    assert a != b and a.count("overlay=x=") == 5 and b.count("overlay=x=") == 2
    with pytest.raises(ParamError):
        resolve(CAT.get("frost-panels").parameters, {"panels": 9})


def test_showcase_graph_uses_textfiles(tmp_path):
    from lionstone.pro.features import showcase
    g = showcase.build_graph("stage-light", "Stage Light", "the room goes dark, you stay lit",
                             tmp_path, None)
    assert "textfile=" in g and "drawtext=text=" not in g and ":text=" not in g
    assert (tmp_path / "sname.txt").read_text(encoding="utf-8") == "Stage Light"
    assert showcase._line(CAT.get("stage-light").description) == "the room goes dark, you stay lit"


@pytest.mark.skipif(not has_filter("drawtext"), reason="FFmpeg build without drawtext")
def test_showcase_reel_renders(tmp_path):
    from lionstone.pro.features import showcase
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=360x640:r=30:d=7", "-pix_fmt", "yuv420p", str(clip)], check=True)
    out = showcase.make_showcase("duotone-pop", str(clip), str(tmp_path / "r.mp4"),
                                 check_entitlement=False)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True, check=True).stdout.strip()
    assert probe == "1080,1920"


def test_compiles_into_a_plan(plan_copy):
    from lionstone.models import EditPlan
    from lionstone.pro.features import timeline as tl
    from lionstone.pro.features.compile import compile_plan
    from lionstone.pro.features.entitlements import for_tier
    plan = EditPlan.load(plan_copy)
    for pid, anchor in (("stage-light", tl.segment_anchor(plan, 0)),
                        ("insight-split", tl.segment_anchor(plan, 1))):
        p = CAT.get(pid)
        tl.add(plan, tl.FxInstance(preset=p.id, version=p.version, anchor=anchor, params={}))
    rep = compile_plan(plan, CAT, for_tier("studio"))
    assert len(rep.applied) == 2 and not rep.skipped
    assert "vignette=" in plan.color["filter"] and "overlay=" in plan.color["filter"]
