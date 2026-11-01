"""Built-in registration of the creative features. No license, no keys, no gating."""

from __future__ import annotations

import sys
from pathlib import Path


def safe_console(streams=None) -> None:
    """Keep emoji output from crashing on streams that can't encode it (Windows pipes)."""
    for s in streams or (sys.stdout, sys.stderr):
        enc = (getattr(s, "encoding", None) or "").lower().replace("-", "").replace("_", "")
        if enc and enc not in ("utf8", "utf8sig") and getattr(s, "errors", "") in (
                "strict", "surrogateescape"):
            try:
                s.reconfigure(errors="replace")
            except (AttributeError, ValueError, OSError):
                pass


def register(reg) -> None:
    safe_console()
    from lionstone.effects.ffmpeg_fx import register_builder

    from . import captions_pro, commands, commands_fx, style, vision
    from .export import export_all
    from .features.qa_fx import fx_qa
    from .fx.builders import BUILDERS
    from .fx.text_builders import BUILDERS as TEXT_BUILDERS

    for tier in ("pro", "studio"):  # effect metadata still carries the old tier names
        reg.unlock_tier(tier)
    commands.register_commands(reg)
    commands_fx.register(reg)
    reg.qa_hooks.append(fx_qa)
    for fid, fn in {**BUILDERS, **TEXT_BUILDERS}.items():
        register_builder(fid, fn)
    captions_pro.register()
    captions_pro.register_karaoke()
    reg.reframers["face"] = vision.face_reframer
    reg.qa_hooks.append(vision.faces_qa)
    reg.plan_hooks.append(style.plan_hook)
    reg.add_exporter("nle", lambda plan, outdir: export_all(plan, Path(outdir)))
