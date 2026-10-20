"""Effect catalog — load, validate and filter effect definitions.

Effects are JSON files (see ``schemas/effect.schema.json``). The free pack
ships with the core; plugins (e.g. Lionstone Pro) register extra directories.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

REQUIRED = ("id", "name", "category", "tier", "style", "duration", "parameters",
            "constraints", "renderEngine", "supportsPreview", "fallback")
TIERS = ("free", "pro", "studio")
CATEGORIES = ("title", "lower_third", "transition", "image", "audio", "caption")


class EffectError(ValueError):
    pass


@dataclass
class Effect:
    id: str
    name: str
    category: str
    tier: str
    style: list[str]
    duration: dict[str, float]
    parameters: dict[str, Any]
    constraints: dict[str, Any]
    renderEngine: str
    supportsPreview: bool
    fallback: str
    description: str = ""
    use: list[str] = field(default_factory=list)
    composition: str = ""
    fallbackEngine: str = "ffmpeg"
    preview: str = ""
    license: dict[str, str] = field(default_factory=dict)
    remotionProject: str = ""  # Remotion project dir, relative to this JSON file
    source: str = ""  # file it was loaded from

    @property
    def total(self) -> float:
        d = self.duration
        return float(d["enter"]) + float(d["hold"]) + float(d["exit"])


def validate(d: dict[str, Any], origin: str = "?") -> None:
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise EffectError(f"{origin}: missing keys {missing}")
    if d["tier"] not in TIERS:
        raise EffectError(f"{origin}: tier must be one of {TIERS}")
    if d["category"] not in CATEGORIES:
        raise EffectError(f"{origin}: category must be one of {CATEGORIES}")
    for k in ("enter", "hold", "exit"):
        v = d["duration"].get(k)
        if not isinstance(v, (int, float)) or v < 0:
            raise EffectError(f"{origin}: duration.{k} must be a non-negative number")
    c = d["constraints"]
    if c.get("minDuration", 0) > c.get("maxDuration", 1e9):
        raise EffectError(f"{origin}: constraints.minDuration > maxDuration")


def _builtin_dirs() -> list[Path]:
    dirs: list[Path] = []
    try:  # installed wheel
        p = Path(str(resources.files("lionstone") / "_catalog"))
        if p.exists():
            dirs.append(p)
    except (ModuleNotFoundError, TypeError):
        pass
    repo = Path(__file__).resolve().parents[3] / "effects" / "catalog"
    if repo.exists() and repo not in dirs:
        dirs.append(repo)
    return dirs


class Catalog:
    def __init__(self, extra_dirs: list[Path] | None = None):
        self.effects: dict[str, Effect] = {}
        for d in _builtin_dirs() + list(extra_dirs or []):
            self.load_dir(d)

    def load_dir(self, directory: Path) -> None:
        for f in sorted(Path(directory).rglob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            validate(data, str(f))
            known = {k: v for k, v in data.items() if k in Effect.__dataclass_fields__}
            self.effects[data["id"]] = Effect(**known, source=str(f))

    def get(self, effect_id: str) -> Effect:
        try:
            return self.effects[effect_id]
        except KeyError as e:
            raise EffectError(f"unknown effect {effect_id!r}. Try `lionstone effects list`.") from e

    def filter(self, *, category: str | None = None, style: str | None = None,
               tier: str | None = None) -> list[Effect]:
        out = list(self.effects.values())
        if category:
            out = [e for e in out if e.category == category]
        if style:
            out = [e for e in out if style in e.style]
        if tier and tier != "all":
            out = [e for e in out if e.tier == tier]
        return sorted(out, key=lambda e: (TIERS.index(e.tier), e.id))
