import json
from pathlib import Path

import pytest

from lionstone.effects import Catalog, EffectError
from lionstone.effects.catalog import validate

ROOT = Path(__file__).resolve().parents[1]


def test_free_pack_matches_spec():
    cat = Catalog()
    free = cat.filter(tier="free")
    assert [e.id for e in free] == ["F01", "F02", "F03", "F04", "F05", "F06"]
    f01 = cat.get("F01")
    assert f01.duration == {"enter": 1.2, "hold": 3.0, "exit": 0.6}
    assert f01.fallback == "simple_fade"
    assert cat.get("F05").category == "lower_third"


def test_every_catalog_file_validates_against_rules():
    for f in (ROOT / "effects" / "catalog").rglob("*.json"):
        validate(json.loads(f.read_text()), str(f))


def test_schema_is_valid_json():
    schema = json.loads((ROOT / "schemas" / "effect.schema.json").read_text())
    assert "tier" in schema["required"]


def test_invalid_effect_rejected():
    bad = json.loads((ROOT / "effects/catalog/free/F01-cinematic-fade.json").read_text())
    bad["tier"] = "gold"
    with pytest.raises(EffectError):
        validate(bad)


def test_unknown_effect():
    with pytest.raises(EffectError):
        Catalog().get("Z99")


def test_filter_path_escapes_drive_letter():
    from lionstone.effects.ffmpeg_fx import filter_path
    assert filter_path("C:/Windows/Fonts/arialbd.ttf") == r"C\\:/Windows/Fonts/arialbd.ttf"
    assert filter_path("/tmp/it's [1].png") == r"/tmp/it\\\'s \[1\].png"
    assert filter_path("/usr/share/fonts/DejaVuSans.ttf") == "/usr/share/fonts/DejaVuSans.ttf"


def test_filters():
    cat = Catalog()
    assert all("cinematic" in e.style for e in cat.filter(style="cinematic"))
    assert "F05" in [e.id for e in cat.filter(category="lower_third")]
