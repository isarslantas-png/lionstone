import math

import pytest

from lionstone.pro.features import easing, keyframes
from lionstone.pro.features.catalog import Catalog, CatalogError, validate
from lionstone.pro.features.entitlements import EntitlementError, for_tier
from lionstone.pro.features.params import ParamError, resolve, validate_value
from lionstone.pro.features.renderers import ffmpeg_adapter as fa


def ff_eval(expr: str, **vars_):
    """Evaluate an FFmpeg expression in Python (subset used by Lionstone)."""
    env = {"IF": lambda c, a, b: a if c else b, "lt": lambda a, b: float(a < b),
           "gte": lambda a, b: float(a >= b), "between": lambda x, a, b: float(a <= x <= b),
           "min": min, "max": max, "pow": pow, "exp": math.exp, "cos": math.cos,
           "abs": abs, "PI": math.pi, **vars_}
    return eval(expr.replace("if(", "IF("), {"__builtins__": {}}, env)


def test_params_reject_bad_values():
    spec = {"type": "number", "min": 0, "max": 1, "default": 0.5}
    assert validate_value("x", spec, "0.25") == 0.25
    for bad in (float("nan"), float("inf"), 2, "abc", True):
        with pytest.raises(ParamError):
            validate_value("x", spec, bad)
    with pytest.raises(ParamError):
        validate_value("c", {"type": "color", "default": "#000000"}, "red")
    with pytest.raises(ParamError):
        resolve({"a": spec}, {"b": 1})


@pytest.mark.parametrize("name", ["linear", "ease-in", "ease-out", "ease-in-out",
                                  "cubic-bezier", "spring"])
def test_easing_python_and_ffmpeg_agree(name):
    for i in range(0, 21):
        p = i / 20
        py = easing.ease(name, p)
        ff = ff_eval(easing.expr(name, "p"), p=p)
        tol = 0.02 if name == "cubic-bezier" else 1e-6
        assert abs(py - ff) < tol, (name, p, py, ff)
        assert -0.01 <= py <= 1.16
    assert abs(easing.ease(name, 0)) < 1e-9
    assert abs(easing.ease(name, 1) - 1) < 1e-6


def test_keyframes_validation_and_parity():
    with pytest.raises(keyframes.KeyframeError):
        keyframes.validate_track("z", [{"t": 1, "v": 1}, {"t": 1, "v": 2}])
    with pytest.raises(keyframes.KeyframeError):
        keyframes.validate_track("z", [{"t": 0, "v": float("nan")}])
    tr = keyframes.validate_track("z", [{"t": 0, "v": 1}, {"t": 2, "v": 1.3, "ease": "ease-out"},
                                        {"t": 4, "v": 1.1, "ease": "linear"}])
    e = keyframes.expression(tr, t0=10.0)
    for t in (9, 10, 11, 12, 13.5, 20):
        assert abs(ff_eval(e, t=t) - keyframes.value_at(tr, t - 10)) < 1e-4


def test_fps_conversion_round_trip():
    for fps in (23.976, 25, 29.97, 30, 60):
        f = keyframes.to_frames(2.5, fps)
        assert abs(keyframes.frames_to_seconds(f, fps) - 2.5) <= 0.5 / fps + 1e-9


def test_entitlements():
    free, pro, studio = for_tier("free"), for_tier("pro"), for_tier("studio")
    assert free.allows("free") and not free.allows("pro")
    assert pro.allows("pro") and not pro.allows("studio")
    assert studio.allows("studio") and studio.level == "studio"
    with pytest.raises(EntitlementError):
        free.require("pro", "Soft Bloom")


def test_catalog_integrity():
    cat = Catalog()
    assert len(cat.presets) >= 130
    for p in cat.presets.values():
        assert p.license["verified"] and p.license["source"] == "lionstone-original"
        if p.implementationStatus == "planned":
            assert p.supportedRenderers == [] and p.limitations, p.id
        elif p.kind in ("effect", "transition", "look", "motion") and p.id != "lionstone.hard-cut":
            assert fa.implemented(p.renderer_id), f"{p.id} is marked usable but has no renderer"
        if p.kind == "text" and p.usable:
            assert p.graphicEffect


def test_catalog_rejects_unverified_and_unnamespaced():
    good = Catalog().get("film-grain")
    d = {**good.__dict__}
    d["license"] = {"source": "unknown", "verified": False}
    with pytest.raises(CatalogError):
        validate(d)
    d = {**good.__dict__, "id": "soft-bloom"}
    with pytest.raises(CatalogError):
        validate(d)


def test_search_and_filters():
    cat = Catalog()
    assert all(p.kind == "transition" for p in cat.search(kind="transition"))
    assert any("glow" in p.tags for p in cat.search(text="glow"))
    assert all(p.tier == "free" for p in cat.search(tier="free"))


def test_merge_transforms_identity_outside_windows():
    c = fa.RCtx(640, 360, 25, 10)
    ts = fa.punch_in({"amount": 0.5}, [(2, 4)], c)
    frag = fa.merge_transforms(ts, c)
    z = frag.split("w='trunc(640*")[1].split("/2)*2'")[0]
    assert abs(ff_eval(z, t=1) - 1) < 1e-9 and ff_eval(z, t=3) > 1.05


def test_photosensitivity_guard_in_beat_flash():
    c = fa.RCtx(640, 360, 25, 10)
    frag = fa.beat_flash({"intensity": 1, "every": 0.34, "times": [1.0, 1.1, 1.2, 1.5, 1.9]},
                         [(0, 10)], c)
    assert frag.count("if(between") == 3  # 1.0, 1.5, 1.9 kept; 1.1 / 1.2 dropped
