import pytest

from lionstone.cli import _catalog
from lionstone.color import LOOKS
from lionstone.presets import ASPECTS, INTENSITIES, LOUDNESS
from lionstone.pro.styles_cmd import DATA, command_for, load, resolve


def _flags(args):
    return {args[i]: args[i + 1] for i in range(0, len(args), 2)}


def test_every_style_uses_valid_options():
    data = load()
    effects = {e.id for e in _catalog().filter()}
    for g in data["groups"]:
        for s in g["styles"]:
            f = _flags(s["args"])
            assert f.get("--intensity", "natural") in INTENSITIES, s["code"]
            assert f.get("--profile", "youtube") in LOUDNESS, s["code"]
            assert f.get("--color", "natural") in LOOKS, s["code"]
            assert f.get("--aspect", "16:9") in ASPECTS, s["code"]
            assert f.get("--denoise", "light") in {"off", "light", "strong"}, s["code"]
            assert f.get("--captions", "burn") in {"burn", "file", "none"}, s["code"]
            for key in ("--title-effect", "--chapter-effect", "--lower-third-effect"):
                assert f.get(key, "F01") in effects, s["code"]


def test_codes_unique_and_presets_valid():
    data = load()
    codes = [s["code"] for g in data["groups"] for s in g["styles"]]
    assert len(codes) == len(set(codes))
    for p in data["presets"]:
        resolve(p["codes"], data)  # one per group, all known


def test_command_for_and_conflicts():
    cmd = command_for(["o4", "W3", "A3"], "talk.mp4")
    assert cmd[:3] == ["lionstone", "edit", "talk.mp4"]
    assert "P01" in cmd and "social" in cmd and "face" in cmd
    with pytest.raises(ValueError):
        resolve(["O1", "O2"])
    with pytest.raises(ValueError):
        resolve(["Z9"])


def test_generated_files_in_sync():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "build_styles", Path(__file__).resolve().parents[2] / "tools" / "build_styles.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    before = {p: p.read_text(encoding="utf-8") for p in (DATA / "styles.md", DATA / "guide" / "index.html")}
    mod.build()
    for p, text in before.items():
        assert p.read_text(encoding="utf-8") == text, f"{p.name} is stale: run tools/build_styles.py"
