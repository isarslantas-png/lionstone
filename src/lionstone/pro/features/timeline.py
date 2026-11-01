"""Timeline instances of presets, stored inside the existing plan.json.

``plan.meta["lionstone_fx"] = {"schema": 1, "instances": [...], "compiled": {...}}``

An instance references a preset id + version and an *anchor* on the source
timeline, so it survives re-cuts and transcript edits:

* ``global``   — whole output
* ``source``   — [start, end] in source seconds (maps to every kept piece)
* ``segment``  — a kept segment, by source start/end at creation time
* ``join``     — the cut between two segments (transitions), by their source edges
* ``output``   — [start, end] in output seconds (text / CTA placement)

Unknown presets or versions are never deleted: the instance is kept and marked.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from lionstone.models import EditPlan

from . import SCHEMA_VERSION

ANCHORS = ("global", "source", "segment", "join", "output")


@dataclass
class FxInstance:
    preset: str
    version: int
    anchor: dict[str, Any]
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    id: str = field(default_factory=lambda: "fx" + uuid.uuid4().hex[:8])
    created_by: str = "user"  # user | agent | batch | brand-kit
    reason: str = ""
    status: str = "ok"  # ok | missing-preset | migrated | orphaned | error | locked

    def to_dict(self) -> dict:
        return asdict(self)


def _store(plan: EditPlan) -> dict:
    st = plan.meta.setdefault("lionstone_fx", {"schema": SCHEMA_VERSION, "instances": []})
    migrate_store(st)
    return st


def migrate_store(st: dict) -> dict:
    """Schema migrations for older project files (never drops data)."""
    v = st.get("schema", 0)
    if v < 1:  # v0 stored a flat list under "effects"
        st["instances"] = st.pop("effects", st.get("instances", []))
        for inst in st["instances"]:
            inst.setdefault("version", 1)
            inst.setdefault("anchor", {"type": "global"})
            inst.setdefault("params", {})
        st["schema"] = 1
    return st


def instances(plan: EditPlan) -> list[FxInstance]:
    out = []
    for d in _store(plan)["instances"]:
        known = {k: v for k, v in d.items() if k in FxInstance.__dataclass_fields__}
        out.append(FxInstance(**known))
    return out


def save_instances(plan: EditPlan, items: list[FxInstance]) -> None:
    _store(plan)["instances"] = [i.to_dict() for i in items]


def add(plan: EditPlan, inst: FxInstance) -> FxInstance:
    if inst.anchor.get("type") not in ANCHORS:
        raise ValueError(f"anchor type must be one of {ANCHORS}")
    items = instances(plan)
    items.append(inst)
    save_instances(plan, items)
    return inst


def remove(plan: EditPlan, fx_id: str) -> bool:
    items = instances(plan)
    keep = [i for i in items if i.id != fx_id]
    save_instances(plan, keep)
    return len(keep) != len(items)


def segment_anchor(plan: EditPlan, index: int) -> dict:
    s = plan.segments[index]
    return {"type": "segment", "start": s.start, "end": s.end}


def join_anchor(plan: EditPlan, index: int) -> dict:
    """Join `index` = cut between segment index and index+1."""
    a, b = plan.segments[index], plan.segments[index + 1]
    return {"type": "join", "left_end": a.end, "right_start": b.start}


def migrate_instances(plan: EditPlan, catalog) -> list[str]:
    """Bring instances to the catalog's preset versions; mark (don't drop) unknowns."""
    notes, items = [], instances(plan)
    for inst in items:
        try:
            p = catalog.get(inst.preset)
        except Exception:
            inst.status = "missing-preset"
            notes.append(f"{inst.id}: preset {inst.preset} not in catalog — kept, not rendered")
            continue
        if inst.version < p.version:
            for old_key, new_key in MIGRATIONS.get(p.id, {}).get(inst.version, {}).items():
                if old_key in inst.params:
                    inst.params[new_key] = inst.params.pop(old_key)
            inst.params = {k: v for k, v in inst.params.items() if k in p.parameters}
            notes.append(f"{inst.id}: {p.id} v{inst.version} → v{p.version}")
            inst.version, inst.status = p.version, "migrated"
        elif inst.version > p.version:
            inst.status = "error"
            notes.append(f"{inst.id}: made with a newer {p.id} v{inst.version}; update Lionstone Pro")
    save_instances(plan, items)
    return notes


# preset id → {from_version: {old_param: new_param}}
MIGRATIONS: dict[str, dict[int, dict[str, str]]] = {
    "lionstone.film-grain": {1: {"amount": "intensity"}},
}
