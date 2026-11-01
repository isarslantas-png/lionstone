"""Plugin system.

Plugins are regular Python packages exposing an entry point in the
``lionstone.plugins`` group::

    [project.entry-points."lionstone.plugins"]
    myplugin = "my_package.plugin:register"

``register(registry)`` receives a :class:`Registry` and can add effect packs,
CLI commands, exporters, plan/QA hooks, caption styles and reframers.
The creative features (formerly Pro) now ship built in: the open core has no paywalled code
paths, only extension points.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

log = logging.getLogger("lionstone.plugins")


@dataclass
class Command:
    name: str
    help: str
    configure: Callable[[Any], None]  # (argparse subparser) -> None
    run: Callable[[Any], int]  # (argparse namespace) -> exit code


@dataclass
class Registry:
    effect_dirs: list[Path] = field(default_factory=list)
    commands: dict[str, Command] = field(default_factory=dict)
    exporters: dict[str, Callable] = field(default_factory=dict)  # name -> fn(plan, outdir)
    plan_hooks: list[Callable] = field(default_factory=list)  # fn(plan, ctx) -> None
    qa_hooks: list[Callable] = field(default_factory=list)  # fn(report, ctx) -> None
    autofix_hooks: list[Callable] = field(default_factory=list)  # fn(report, ctx) -> bool
    reframers: dict[str, Callable] = field(default_factory=dict)  # mode -> fn(ctx) -> filter
    tiers: set[str] = field(default_factory=lambda: {"free"})
    loaded: list[dict] = field(default_factory=list)

    # convenience API for plugin authors ------------------------------------
    def add_effect_dir(self, path: str | Path) -> None:
        self.effect_dirs.append(Path(path))

    def add_command(self, name: str, help: str, configure, run) -> None:
        self.commands[name] = Command(name, help, configure, run)

    def add_exporter(self, name: str, fn: Callable) -> None:
        self.exporters[name] = fn

    def unlock_tier(self, tier: str) -> None:
        self.tiers.add(tier)


_REGISTRY: Registry | None = None


def registry(reload: bool = False) -> Registry:
    global _REGISTRY
    if _REGISTRY is not None and not reload:
        return _REGISTRY
    reg = Registry()
    try:  # the creative features (former Pro/Studio) ship in the core
        from .pro.plugin import register as _register_builtin
        _register_builtin(reg)
        reg.loaded.append({"name": "builtin", "module": "lionstone.pro", "status": "ok"})
    except Exception as e:  # e.g. numpy missing: the core must keep working
        log.warning("built-in creative features unavailable: %s", e)
        reg.loaded.append({"name": "builtin", "module": "lionstone.pro", "status": f"failed: {e}"})
    try:
        eps = entry_points(group="lionstone.plugins")
    except TypeError:  # pragma: no cover - py<3.10
        eps = entry_points().get("lionstone.plugins", [])
    for ep in eps:
        info = {"name": ep.name, "module": ep.value, "status": "ok"}
        try:
            ep.load()(reg)
        except Exception as e:  # a broken plugin must never break the core
            info["status"] = f"failed: {e}"
            log.warning("plugin %s failed to load: %s", ep.name, e)
        reg.loaded.append(info)
    _REGISTRY = reg
    return reg
