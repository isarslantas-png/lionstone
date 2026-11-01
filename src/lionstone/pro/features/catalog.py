"""Preset catalog: definitions (data) are separate from timeline instances.

Each preset has a stable id (``lionstone.<slug>``), a version, a parameter
schema and an ``implementationStatus``:

* ``ready``   — preview and final render implemented and tested
* ``partial`` — renders, with documented limitations
* ``planned`` — listed for the roadmap; can't be applied (no fake controls)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

KINDS = ("effect", "transition", "look", "motion", "text", "caption")
TIERS = ("free", "pro", "studio")
STATUSES = ("ready", "partial", "planned")
COSTS = ("low", "medium", "high")
REQUIRED = ("id", "name", "kind", "category", "tier", "implementationStatus", "version",
            "parameters", "performanceCost", "license")


class CatalogError(ValueError):
    pass


@dataclass
class Preset:
    id: str
    name: str
    kind: str
    category: str
    tier: str
    implementationStatus: str
    version: int
    parameters: dict[str, dict]
    performanceCost: str
    license: dict[str, Any]
    description: str = ""
    tags: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    supportedRenderers: list[str] = field(default_factory=lambda: ["ffmpeg"])
    compatibleMedia: list[str] = field(default_factory=lambda: ["video", "image"])
    duration: dict[str, float] = field(default_factory=dict)  # seconds: default/min/max
    intensityRange: list[float] = field(default_factory=lambda: [0.0, 1.0])
    fallbackEffectId: str | None = None
    limitations: list[str] = field(default_factory=list)
    graphicEffect: str | None = None  # text presets: core graphic effect id (e.g. T01)
    pipeline: str = "filter"  # filter | transform | graphic
    base: str | None = None  # custom presets: the built-in preset whose renderer they use
    owner: str | None = None  # custom presets: author (personal) or team id
    source: str = "builtin"  # builtin | personal | team:<id>

    @property
    def defaults(self) -> dict[str, Any]:
        return {k: s.get("default") for k, s in self.parameters.items()}

    @property
    def renderer_id(self) -> str:
        return self.base or self.id

    @property
    def usable(self) -> bool:
        return self.implementationStatus in ("ready", "partial")

    def card(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "category": self.category,
                "tier": self.tier, "status": self.implementationStatus,
                "cost": self.performanceCost, "media": self.compatibleMedia,
                "description": self.description, "limitations": self.limitations}


def validate(d: dict, origin: str = "?") -> None:
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise CatalogError(f"{origin}: missing {missing}")
    if not str(d["id"]).startswith(("lionstone.", "personal.", "team.")):
        raise CatalogError(f"{origin}: id must be namespaced (lionstone./personal./team.)")
    for key, allowed in (("kind", KINDS), ("tier", TIERS),
                         ("implementationStatus", STATUSES), ("performanceCost", COSTS)):
        if d[key] not in allowed:
            raise CatalogError(f"{origin}: {key}={d[key]!r} not in {allowed}")
    if not isinstance(d["version"], int) or d["version"] < 1:
        raise CatalogError(f"{origin}: version must be a positive integer")
    lic = d["license"]
    if not lic.get("source") or "verified" not in lic:
        raise CatalogError(f"{origin}: license.source and license.verified are required")
    if d["implementationStatus"] != "planned" and not lic.get("verified"):
        raise CatalogError(f"{origin}: unverified license — cannot be marked usable")
    for name, spec in d["parameters"].items():
        if "default" not in spec:
            raise CatalogError(f"{origin}: parameter {name} has no default")
        from .params import validate_value
        validate_value(f"{origin}:{name}", spec, spec["default"])


def _builtin_files() -> list[Path]:
    try:
        root = Path(str(resources.files("lionstone.pro.features") / "presets"))
    except (ModuleNotFoundError, TypeError):
        root = Path(__file__).parent / "presets"
    return sorted(root.glob("*.json"))


class Catalog:
    def __init__(self, extra: list[dict] | None = None):
        self.presets: dict[str, Preset] = {}
        for f in _builtin_files():
            for d in json.loads(f.read_text(encoding="utf-8")):
                self.add(d, origin=f.name)
        for d in extra or []:
            self.add(d, origin=d.get("source", "extra"))

    def add(self, d: dict, origin: str = "?") -> Preset:
        validate(d, origin)
        if d["id"] in self.presets and self.presets[d["id"]].source == "builtin" \
                and d.get("source", "builtin") != "builtin":
            raise CatalogError(f"{d['id']}: custom presets can't replace built-in ids")
        known = {k: v for k, v in d.items() if k in Preset.__dataclass_fields__}
        p = Preset(**known)
        self.presets[p.id] = p
        return p

    def get(self, pid: str) -> Preset:
        if pid in self.presets:
            return self.presets[pid]
        short = f"lionstone.{pid}"
        if short in self.presets:
            return self.presets[short]
        raise CatalogError(f"unknown preset {pid!r}. Try `lionstone fx list`.")

    def search(self, *, kind=None, category=None, tier=None, style=None, cost=None,
               status=None, text=None, ids: set[str] | None = None) -> list[Preset]:
        out = list(self.presets.values())
        if kind:
            out = [p for p in out if p.kind == kind]
        if category:
            out = [p for p in out if p.category == category]
        if tier and tier != "all":
            out = [p for p in out if p.tier == tier]
        if style:
            out = [p for p in out if style in p.styles]
        if cost:
            out = [p for p in out if p.performanceCost == cost]
        if status:
            out = [p for p in out if p.implementationStatus == status]
        if text:
            q = text.lower()
            out = [p for p in out if q in p.name.lower() or q in p.description.lower()
                   or any(q in t for t in p.tags) or q in p.id]
        if ids is not None:
            out = [p for p in out if p.id in ids]
        return sorted(out, key=lambda p: (KINDS.index(p.kind), p.category, TIERS.index(p.tier),
                                          p.name))


# --- favourites & recents (per user, local) ---------------------------------------
def _user_file(name: str) -> Path:
    from ..identity import config_dir
    p = config_dir() / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def favorites() -> set[str]:
    p = _user_file("fx-favorites.json")
    return set(json.loads(p.read_text())) if p.exists() else set()


def toggle_favorite(pid: str) -> bool:
    fav = favorites()
    on = pid not in fav
    (fav.add if on else fav.discard)(pid)
    _user_file("fx-favorites.json").write_text(json.dumps(sorted(fav)))
    return on


def recents(limit: int = 12) -> list[str]:
    p = _user_file("fx-recent.json")
    return json.loads(p.read_text())[:limit] if p.exists() else []


def touch_recent(pid: str) -> None:
    r = [x for x in recents(50) if x != pid]
    r.insert(0, pid)
    _user_file("fx-recent.json").write_text(json.dumps(r[:50]))
    _ = time.time()
