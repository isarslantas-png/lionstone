"""Personal presets (Pro), brand kits (Pro: personal · Studio: team), team roles,
versioning and batch application.

Storage is plain files so a team can share it through any synced folder or a
private git repo:

    <root>/team.json                    team id, owner, members → role
    <root>/<kind>/<id>/v0001.json       immutable versions
    <root>/<kind>/<id>/history.jsonl    who / when / what changed

Personal root: ~/.config/lionstone/personal   ·   Team root: $LIONSTONE_STUDIO_DIR
Permissions are checked here (business logic), not only in the CLI.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .entitlements import Entitlement, EntitlementError

ROLES = ("viewer", "editor", "admin", "owner")
PERMS = {
    "viewer": {"use"},
    "editor": {"use", "batch", "create_preset", "edit_draft"},
    "admin": {"use", "batch", "create_preset", "edit_draft", "edit_kit", "publish", "lock",
              "manage_members"},
    "owner": {"use", "batch", "create_preset", "edit_draft", "edit_kit", "publish", "lock",
              "manage_members", "transfer"},
}
KINDS = ("preset", "kit", "profile")


class StudioError(PermissionError):
    pass


def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower().replace("ı", "i").replace("ş", "s")
               .replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c"))
    return s.strip("-")[:48] or "item"


def personal_root() -> Path:
    from ..identity import config_dir
    return config_dir() / "personal"


def team_root() -> Path | None:
    p = os.environ.get("LIONSTONE_STUDIO_DIR")
    return Path(p) if p else None


# --- versioned store ------------------------------------------------------------------
class Store:
    def __init__(self, root: Path, scope: str):
        self.root = Path(root)
        self.scope = scope  # "personal" | "team:<id>"

    def _dir(self, kind: str, item: str) -> Path:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}")
        return self.root / kind / slug(item)

    def versions(self, kind: str, item: str) -> list[int]:
        d = self._dir(kind, item)
        return sorted(int(p.stem[1:]) for p in d.glob("v*.json")) if d.exists() else []

    def load(self, kind: str, item: str, version: int | None = None) -> dict:
        vs = self.versions(kind, item)
        if not vs:
            raise FileNotFoundError(f"{kind} {item!r} not found in {self.scope}")
        v = version or vs[-1]
        if v not in vs:
            raise FileNotFoundError(f"{kind} {item!r} has no version {v} (has {vs})")
        return json.loads((self._dir(kind, item) / f"v{v:04d}.json").read_text(encoding="utf-8"))

    def save(self, kind: str, item: str, data: dict, author: str, note: str = "") -> int:
        d = self._dir(kind, item)
        d.mkdir(parents=True, exist_ok=True)
        v = (self.versions(kind, item) or [0])[-1] + 1
        data = {**data, "version": data.get("version", 1) if kind == "preset" else v,
                "revision": v, "updated_by": author}
        raw = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
        if "api_key" in raw.lower() or "secret" in raw.lower():
            raise StudioError("refusing to store something that looks like a secret")
        (d / f"v{v:04d}.json").write_text(raw + "\n", encoding="utf-8")
        entry = {"revision": v, "author": author, "at": dt.datetime.now(dt.timezone.utc)
                 .isoformat(timespec="seconds"), "note": note,
                 "sha": hashlib.sha1(raw.encode()).hexdigest()[:12]}
        with (d / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return v

    def history(self, kind: str, item: str) -> list[dict]:
        p = self._dir(kind, item) / "history.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def items(self, kind: str) -> list[str]:
        d = self.root / kind
        return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []


# --- team & roles ----------------------------------------------------------------------
@dataclass
class Team:
    id: str
    name: str
    owner: str
    members: dict[str, str] = field(default_factory=dict)

    def role(self, user: str) -> str | None:
        """Emails match case-insensitively. Roles organise the team's work; anyone who can
        write the shared folder can edit team.json, so they are not access control."""
        user = user.lower()
        if user == self.owner.lower():
            return "owner"
        return {k.lower(): v for k, v in self.members.items()}.get(user)

    def can(self, user: str, perm: str) -> bool:
        r = self.role(user)
        return bool(r) and perm in PERMS[r]


def load_team(root: Path | None = None) -> Team:
    root = root or team_root()
    if not root or not (root / "team.json").exists():
        raise StudioError("no team workspace — set LIONSTONE_STUDIO_DIR and run "
                          "`lionstone team init`")
    return Team(**json.loads((root / "team.json").read_text(encoding="utf-8")))


def save_team(team: Team, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "team.json").write_text(json.dumps(asdict(team), indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")


def init_team(root: Path, name: str, ent: Entitlement) -> Team:
    ent.require("studio", "Team workspaces")
    if (root / "team.json").exists():
        raise StudioError(f"a team already exists in {root}")
    team = Team(id=ent.team or slug(name), name=name, owner=ent.user)
    save_team(team, root)
    return team


def set_member(team: Team, root: Path, actor: Entitlement, email: str, role: str | None) -> Team:
    actor.require("studio", "Managing team members")
    if not team.can(actor.user, "manage_members"):
        raise StudioError(f"{actor.user} can't manage members of {team.name}")
    email = email.strip().lower()
    if email == team.owner.lower():
        raise StudioError("the owner's role can't be changed")
    if role is None:
        team.members.pop(email, None)
    else:
        if role not in ROLES[:3]:
            raise StudioError(f"role must be one of {ROLES[:3]}")
        if role == "admin" and team.role(actor.user) != "owner":
            raise StudioError("only the owner can appoint admins")
        team.members[email] = role
    save_team(team, root)
    return team


def require(team: Team, ent: Entitlement, perm: str, what: str) -> None:
    ent.require("studio", what)
    if not team.can(ent.user, perm):
        raise StudioError(f"{what}: {ent.user} ({team.role(ent.user) or 'not a member'}) "
                          f"lacks '{perm}' in team {team.name}")


# --- custom presets -------------------------------------------------------------------
def make_custom_preset(base, name: str, overrides: dict[str, Any], scope: str,
                       owner: str) -> dict:
    """A custom preset = a built-in renderer + validated default overrides."""
    from .params import resolve
    resolved = resolve(base.parameters, overrides)
    params = {k: {**spec, "default": resolved[k]} for k, spec in base.parameters.items()}
    prefix = "personal" if scope == "personal" else "team"
    tier = base.tier if base.tier != "free" else "pro"  # custom presets are a Pro feature
    if scope != "personal":
        tier = "studio"
    return {"id": f"{prefix}.{slug(name)}", "name": name, "kind": base.kind,
            "category": base.category, "tier": tier, "implementationStatus":
            base.implementationStatus, "version": 1, "parameters": params,
            "performanceCost": base.performanceCost, "license": base.license,
            "description": f"Custom preset based on {base.name}.", "tags": base.tags,
            "styles": base.styles, "pipeline": base.pipeline, "base": base.renderer_id,
            "graphicEffect": base.graphicEffect, "owner": owner, "source": scope,
            "limitations": base.limitations}


def save_personal_preset(catalog, base_id: str, name: str, overrides: dict, ent: Entitlement,
                         note: str = "") -> tuple[str, int]:
    ent.require("pro", "Saving personal presets")
    base = catalog.get(base_id)
    ent.require(base.tier, f"Customising {base.name}")
    d = make_custom_preset(base, name, overrides, "personal", ent.user)
    rev = Store(personal_root(), "personal").save("preset", d["id"], d, ent.user, note)
    return d["id"], rev


def save_team_preset(catalog, base_id: str, name: str, overrides: dict, ent: Entitlement,
                     locked: bool = False, note: str = "") -> tuple[str, int]:
    root = team_root()
    team = load_team(root)
    require(team, ent, "lock" if locked else "create_preset", "Saving team presets")
    base = catalog.get(base_id)
    d = make_custom_preset(base, name, overrides, f"team:{team.id}", ent.user)
    d["locked"] = locked
    store = Store(root, f"team:{team.id}")
    if store.versions("preset", d["id"]):
        prev = store.load("preset", d["id"])
        if prev.get("locked") and not team.can(ent.user, "lock"):
            raise StudioError(f"{d['id']} is a locked company preset — only admins can change it")
    return d["id"], store.save("preset", d["id"], d, ent.user, note)


def custom_presets(ent: Entitlement) -> list[dict]:
    """Personal + team presets the user may see (latest revisions)."""
    out = []
    pr = Store(personal_root(), "personal")
    for item in pr.items("preset"):
        try:
            out.append(pr.load("preset", item))
        except FileNotFoundError:
            pass
    root = team_root()
    if root and (root / "team.json").exists():
        team = load_team(root)
        if team.role(ent.user):
            st = Store(root, f"team:{team.id}")
            for item in st.items("preset"):
                out.append(st.load("preset", item))
    clean = []
    for d in out:
        d = {k: v for k, v in d.items() if k not in ("revision", "updated_by", "locked")}
        clean.append(d)
    return clean


# --- brand kits -----------------------------------------------------------------------
@dataclass
class BrandKit:
    name: str
    colors: dict[str, str] = field(default_factory=lambda: {
        "primary": "#111114", "accent": "#E8B04B", "text": "#FFFFFF", "background": "#0B0B0D"})
    fonts: dict[str, dict] = field(default_factory=dict)  # role → {"path": ..., "license": ...}
    logos: dict[str, str] = field(default_factory=dict)  # variant → path
    lower_third: str = "lionstone.name-role"
    cta: dict[str, str] = field(default_factory=dict)  # {"text": ..., "subtext": ...}
    end_card: dict[str, str] = field(default_factory=dict)  # {"title","subtitle","cta"}
    transition: str = "lionstone.hard-cut"
    motion: str | None = None
    look: dict[str, Any] = field(default_factory=lambda: {"preset": "lionstone.look-natural-neutral",
                                                          "intensity": 0.6})
    safe_area: float = 0.05
    logo_clearspace: float = 0.5
    locked: list[str] = field(default_factory=list)  # preset ids editors can't swap out

    def __post_init__(self) -> None:
        # docs/studio.md writes these as {"preset": "lionstone.…"}; store the id either way
        for name in ("lower_third", "transition", "motion"):
            value = getattr(self, name)
            if isinstance(value, dict):
                setattr(self, name, value.get("preset") or BrandKit.__dataclass_fields__[name].default)

    def validate(self) -> list[str]:
        problems = []
        for role, f in self.fonts.items():
            if not f.get("license"):
                problems.append(f"font '{role}': record its licence before shipping it")
            if f.get("path") and not Path(f["path"]).exists():
                problems.append(f"font '{role}': {f['path']} not found — fallback font will be used")
        for v, p in self.logos.items():
            if not Path(p).exists():
                problems.append(f"logo '{v}': {p} not found")
        for k, c in self.colors.items():
            if not re.match(r"^#[0-9A-Fa-f]{6}$", c):
                problems.append(f"colour {k}={c!r} is not #RRGGBB")
        return problems


def save_kit(kit: BrandKit, ent: Entitlement, scope: str = "personal", note: str = "") -> int:
    if scope == "personal":
        ent.require("pro", "Personal brand kit")
        return Store(personal_root(), "personal").save("kit", kit.name, asdict(kit), ent.user, note)
    root = team_root()
    team = load_team(root)
    require(team, ent, "edit_kit", "Editing team brand kits")
    return Store(root, f"team:{team.id}").save("kit", kit.name, asdict(kit), ent.user, note)


def load_kit(name: str, ent: Entitlement, scope: str = "auto") -> tuple[BrandKit, str]:
    root = team_root()
    if scope in ("auto", "team") and root and (root / "team.json").exists():
        team = load_team(root)
        st = Store(root, f"team:{team.id}")
        if st.versions("kit", name):
            require(team, ent, "use", "Using team brand kits")
            d = st.load("kit", name)
            return BrandKit(**{k: v for k, v in d.items() if k in BrandKit.__dataclass_fields__}), \
                f"team:{team.id}"
    if scope == "team":
        raise FileNotFoundError(f"team kit {name!r} not found")
    ent.require("pro", "Brand kits")
    d = Store(personal_root(), "personal").load("kit", name)
    return BrandKit(**{k: v for k, v in d.items() if k in BrandKit.__dataclass_fields__}), "personal"


def apply_kit(plan, kit: BrandKit, catalog, ent: Entitlement, *, scope: str) -> list[str]:
    """Brand kit → plan: accent/font, look, lower third, CTA, end card, default transition."""
    from . import timeline as tl
    notes = [f"kit problems: {p}" for p in kit.validate()]
    opts = plan.meta.setdefault("options", {})
    opts["accent"] = kit.colors.get("accent", opts.get("accent", "#E8B04B"))
    title_font = kit.fonts.get("title", {}).get("path")
    if title_font and Path(title_font).exists():
        opts["font"] = title_font
    items = [i for i in tl.instances(plan) if i.created_by != "brand-kit"]
    tl.save_instances(plan, items)

    def add(pid, anchor, params, reason):
        p = catalog.get(pid)
        if not ent.allows(p.tier):
            notes.append(f"{p.name} skipped — needs {p.tier.title()}")
            return
        tl.add(plan, tl.FxInstance(preset=p.id, version=p.version, anchor=anchor, params=params,
                                   created_by="brand-kit",
                                   reason=f"{reason} ({kit.name}{', locked' if pid in kit.locked else ''})"))

    if kit.look.get("preset"):
        add(kit.look["preset"], {"type": "global"}, {"intensity": kit.look.get("intensity", 0.6)},
            "brand look")
    total = sum(s.duration for s in plan.segments)
    cta_start = total * 0.82
    if kit.end_card.get("title"):  # finish the CTA before the end card (short videos lost it)
        cta_start = min(cta_start, total - 4.2 - 4 - 0.3)
    cta_start = max(0, cta_start)
    if kit.cta.get("text"):
        add("lionstone.cta", {"type": "output", "start": cta_start, "end": cta_start + 4},
            {"text": kit.cta["text"], "subtext": kit.cta.get("subtext", ""), "duration": 4},
            "brand CTA")
    if kit.end_card.get("title"):
        prm = {"text": kit.end_card["title"], "subtext": kit.end_card.get("subtitle", ""),
               "duration": 4}
        add("lionstone.end-card", {"type": "output", "start": max(0, total - 4.2), "end": total},
            prm, "brand end card")
    if kit.transition and kit.transition != "lionstone.hard-cut":
        for i in range(len(plan.segments) - 1):
            gap = plan.segments[i + 1].start - plan.segments[i].end
            if gap > 2.5:  # only at meaningful cuts (long removed passages)
                add(kit.transition, tl.join_anchor(plan, i), {}, "brand transition at topic change")
    plan.meta.setdefault("lionstone_fx", {})["brand_kit"] = {"name": kit.name, "scope": scope}
    return notes


# --- batch ------------------------------------------------------------------------------
def batch_apply(plan_paths: list[str], preset_id: str, catalog, ent: Entitlement, *,
                anchor: str = "global", params: dict | None = None, team_log: bool = False) -> list[str]:
    from lionstone.models import EditPlan

    from . import timeline as tl
    ent.require("pro", "Batch preset application")
    if team_log:
        team = load_team(team_root())
        require(team, ent, "batch", "Team batch")
    p = catalog.get(preset_id)
    ent.require(p.tier, p.name)
    out = []
    for path in plan_paths:
        plan = EditPlan.load(path)
        if anchor == "global":
            anchors = [{"type": "global"}]
        elif anchor == "all-joins":
            anchors = [tl.join_anchor(plan, i) for i in range(len(plan.segments) - 1)]
        else:
            raise ValueError("batch anchor must be global or all-joins")
        for a in anchors:
            tl.add(plan, tl.FxInstance(preset=p.id, version=p.version, anchor=a,
                                       params=params or {}, created_by="batch"))
        plan.save(path)
        out.append(f"{path}: +{len(anchors)} × {p.name}")
    if team_log:
        root = team_root()
        with (root / "batch-log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"by": ent.user, "preset": preset_id, "plans": plan_paths,
                                "at": dt.datetime.now(dt.timezone.utc).isoformat()}) + "\n")
    return out


__all__ = ["Store", "Team", "BrandKit", "StudioError", "EntitlementError"]
