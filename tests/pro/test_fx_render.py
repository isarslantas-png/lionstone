import json
import subprocess

import pytest

from lionstone.ff import has_filter
from lionstone.models import EditPlan
from lionstone.pro.features import timeline as tl
from lionstone.pro.features.catalog import Catalog
from lionstone.pro.features.compile import compile_plan, is_stale
from lionstone.pro.features.entitlements import EntitlementError, for_tier
from lionstone.pro.features.preview import render_preview
from lionstone.pro.features.renderers import ffmpeg_adapter as fa

CAT = Catalog()
READY = [p.id for p in CAT.presets.values()
         if p.usable and p.kind != "caption" and p.id != "lionstone.lut"]


def _add(plan, pid, anchor=None, **params):
    p = CAT.get(pid)
    return tl.add(plan, tl.FxInstance(preset=p.id, version=p.version,
                                      anchor=anchor or {"type": "global"}, params=params))


@pytest.mark.parametrize("pid", READY)
def test_every_ready_preset_previews(pid, tmp_path):
    if CAT.get(pid).kind == "text" and not has_filter("drawtext"):
        pytest.skip("FFmpeg build without drawtext")
    params = {"text": "Ölçülü başlık ığüşöç"} if CAT.get(pid).kind == "text" else {}
    r = render_preview(pid, tmp_path / "p.mp4", CAT, for_tier("studio"), params=params,
                       seconds=2.0, width=192)
    assert (tmp_path / "p.mp4").stat().st_size > 1000 and r["lowres"]


def test_text_preview_explains_missing_drawtext(tmp_path, monkeypatch):
    from lionstone.pro.features import preview as pv
    from lionstone.pro.features.preview import PreviewError
    monkeypatch.setattr(pv, "has_filter", lambda name: False)
    with pytest.raises(PreviewError, match="drawtext"):
        render_preview("word-pop", tmp_path / "p.mp4", CAT, for_tier("pro"), seconds=1.0,
                       width=192)
    r = render_preview("soft-vignette", tmp_path / "v.mp4", CAT, for_tier("pro"), seconds=1.0,
                       width=192)
    assert any("drawtext" in n for n in r["notes"])


def test_locked_preview_is_watermarked_but_allowed(tmp_path):
    r = render_preview("soft-bloom", tmp_path / "p.mp4", CAT, for_tier("free"), seconds=1.5,
                       width=192)
    assert any("needs Pro" in n for n in r["notes"])


def test_final_render_with_many_features(media, plan_copy, tmp_path):
    from lionstone.cli import main
    plan = EditPlan.load(plan_copy)
    assert len(plan.segments) >= 3
    _add(plan, "look-warm-cinema", intensity=0.8)
    _add(plan, "film-grain", intensity=0.3)
    _add(plan, "soft-bloom", tl.segment_anchor(plan, 1))
    _add(plan, "quick-punch-in", tl.segment_anchor(plan, 2))
    _add(plan, "dip-to-black", tl.join_anchor(plan, 0))
    _add(plan, "zoom-through", tl.join_anchor(plan, 1))
    _add(plan, "keyframe-transform", tl.segment_anchor(plan, 0),
         zoom=[{"t": 0, "v": 1}, {"t": 1, "v": 1.2, "ease": "spring"}])
    plan.save(plan_copy)
    import argparse

    from lionstone.pro.commands_fx import _render
    from lionstone.pro.features import entitlements
    orig = entitlements.current
    entitlements.current = lambda: for_tier("studio")
    try:
        code = _render(argparse.Namespace(plan=str(plan_copy), output=str(tmp_path / "o.mp4"),
                                          fast=True, renderer="ffmpeg", profile=None),
                       CAT, for_tier("studio"))
    finally:
        entitlements.current = orig
    qa_md = tmp_path / "qa.md"
    assert code == 0, qa_md.read_text(encoding="utf-8") if qa_md.exists() else "no qa.md"
    qa = json.loads((tmp_path / "qa.json").read_text())
    names = {c["name"]: c["status"] for c in qa["checks"]}
    assert names["fx_compiled"] == "passed" and names["flicker"] == "passed"
    rep = EditPlan.load(plan_copy).meta["lionstone_fx"]["compiled"]["report"]
    assert len(rep["applied"]) == 7 and not rep["skipped"]
    del main


def test_free_user_cannot_render_pro(plan_copy):
    plan = EditPlan.load(plan_copy)
    _add(plan, "soft-bloom")
    _add(plan, "look-natural-neutral")
    rep = compile_plan(plan, CAT, for_tier("free"))
    assert [s["preset"] for s in rep.skipped] == ["lionstone.soft-bloom"]
    assert "gblur" not in plan.color.get("filter", "")
    assert "eq=" in plan.color["filter"]
    with pytest.raises(EntitlementError):
        compile_plan(plan, CAT, for_tier("free"), strict=True)


def test_effect_budget_and_short_clip_transition(plan_copy):
    plan = EditPlan.load(plan_copy)
    for pid in ("soft-bloom", "halation", "haze"):
        _add(plan, pid)
    _add(plan, "dip-to-black", tl.join_anchor(plan, 0), frames=60)
    rep = compile_plan(plan, CAT, for_tier("pro"))
    reasons = " ".join(s["reason"] for s in rep.skipped)
    assert "effect budget" in reasons


def test_orphaned_transition_after_re_edit(plan_copy):
    plan = EditPlan.load(plan_copy)
    _add(plan, "dip-to-black", tl.join_anchor(plan, 0))
    compile_plan(plan, CAT, for_tier("pro"))
    assert not is_stale(plan)
    # simulate a re-edit that removes the cut (merge the first two segments)
    a, b = plan.segments[0], plan.segments[1]
    plan.segments = [type(a)(id=a.id, start=a.start, end=b.end)] + plan.segments[2:]
    assert is_stale(plan)
    rep = compile_plan(plan, CAT, for_tier("pro"))
    assert rep.skipped and "no longer exists" in rep.skipped[0]["reason"]
    assert tl.instances(plan)[0].status == "orphaned"  # kept, not deleted


def test_missing_lut_is_reported_not_fatal(plan_copy, tmp_path):
    plan = EditPlan.load(plan_copy)
    _add(plan, "lut", file=str(tmp_path / "nope.cube"), license_source="my own grade")
    _add(plan, "film-grain")
    rep = compile_plan(plan, CAT, for_tier("pro"))
    assert any("LUT not found" in s["reason"] for s in rep.skipped)
    assert "noise=" in plan.color["filter"]


def test_preset_migration_keeps_old_projects(plan_copy):
    plan = EditPlan.load(plan_copy)
    plan.meta["lionstone_fx"] = {"schema": 0, "effects": [
        {"id": "fxold", "preset": "lionstone.film-grain", "version": 1,
         "params": {"amount": 0.6}, "anchor": {"type": "global"}},
        {"id": "fxgone", "preset": "lionstone.deleted-thing", "version": 1, "params": {},
         "anchor": {"type": "global"}}]}
    rep = compile_plan(plan, CAT, for_tier("pro"))
    insts = {i.id: i for i in tl.instances(plan)}
    assert insts["fxold"].params == {"intensity": 0.6} and insts["fxold"].version == 2
    assert insts["fxgone"].status == "missing-preset"  # kept
    assert any("v1 → v2" in n for n in rep.notes)


def _frame_stats(path, t):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v",
                          "1", "-vf", "scale=96:54,format=gray", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return list(out)


def test_preview_export_parity(media, tmp_path):
    """Same builder → same pixels: a preview of a look on the clip vs the final render."""
    import math
    clip = media["clip"]
    plan = EditPlan.load(media["plan"])
    plan.segments = plan.segments[:1]
    plan.graphics, plan.words = [], []
    a = plan.segments[0]
    p = tmp_path / "plan.json"
    _add(plan, "look-steel-blue", intensity=0.9)
    compile_plan(plan, CAT, for_tier("pro"))
    plan.save(p)
    from lionstone.render import RenderOptions, render
    plan.color["preset"] = "none"
    render(plan, tmp_path / "final.mp4", RenderOptions(captions="none", denoise="off",
                                                       preset="veryfast", renderer="ffmpeg"),
           workdir=tmp_path / "wd")
    render_preview("look-steel-blue", tmp_path / "pv.mp4", CAT, for_tier("pro"),
                   input_path=str(clip), start=a.start, seconds=min(2.0, a.end - a.start),
                   params={"intensity": 0.9}, width=480)
    f1, f2 = _frame_stats(tmp_path / "final.mp4", 0.5), _frame_stats(tmp_path / "pv.mp4", 0.5)
    mse = sum((x - y) ** 2 for x, y in zip(f1, f2)) / len(f1)
    psnr = 99 if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    assert psnr > 28, psnr  # tolerant: different encodes / label corner


def test_visual_regression_metrics(tmp_path):
    """Reference metrics on a fixed test pattern (tests/golden/fx_metrics.json)."""
    import pathlib
    golden_p = pathlib.Path(__file__).parent / "golden" / "fx_metrics.json"
    ids = ["look-golden-hour", "look-steel-blue", "look-classic-bw", "look-punchy-social",
           "soft-vignette", "exposure-balance", "film-grain"]
    got = {}
    for pid in ids:
        c = fa.RCtx(320, 180, 25, 2)
        frag = fa.FILTERS[f"lionstone.{pid}"](CAT.get(pid).defaults, [(0, 2)], c)
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=1",
             "-vf", f"{frag},signalstats,metadata=print:file=-", "-frames:v", "1", "-f", "null",
             "-"], capture_output=True, text=True, check=True).stdout
        vals = dict(line.split("=", 1) for line in out.splitlines() if "signalstats" in line)
        got[pid] = {k: round(float(vals[f"lavfi.signalstats.{k}"]), 1)
                    for k in ("YAVG", "SATAVG", "UAVG", "VAVG")}
    if not golden_p.exists():
        golden_p.write_text(json.dumps(got, indent=1))
        pytest.skip("golden metrics created")
    golden = json.loads(golden_p.read_text())
    for pid, m in got.items():
        for k, v in m.items():
            assert abs(v - golden[pid][k]) <= 3.0, (pid, k, v, golden[pid][k])
    assert got["look-classic-bw"]["SATAVG"] < 3  # mono really is mono
