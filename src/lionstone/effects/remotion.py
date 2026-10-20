"""Remotion renderer for title effects (reference quality, alpha channel).

Each graphic event is rendered to a transparent ProRes 4444 clip by the
Remotion project in ``remotion/`` and overlaid by FFmpeg. If Node/Remotion is
missing or a render fails, the caller falls back to the native FFmpeg builder
— the failure is logged, never hidden.

Environment:
  LIONSTONE_REMOTION_DIR   path to the Remotion project (default: repo ./remotion)
  LIONSTONE_BROWSER        Chrome/Chromium executable for Remotion (optional)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from ..models import GraphicEvent
from .catalog import Effect


def project_dir() -> Path | None:
    env = os.environ.get("LIONSTONE_REMOTION_DIR")
    cands = [Path(env)] if env else []
    cands.append(Path(__file__).resolve().parents[3] / "remotion")
    for c in cands:
        if (c / "package.json").exists() and (c / "node_modules" / "remotion").exists():
            return c
    return None


def available() -> bool:
    return shutil.which("npx") is not None and project_dir() is not None


def project_for(fx: Effect) -> Path | None:
    """Effects from plugins can ship their own Remotion project."""
    if fx.remotionProject and fx.source:
        p = (Path(fx.source).parent / fx.remotionProject).resolve()
        if (p / "node_modules" / "remotion").exists():
            return p
    return project_dir()


def render_event(fx: Effect, ev: GraphicEvent, width: int, height: int, out: Path,
                 accent: str = "#E8B04B", timeout: int = 600) -> Path:
    proj = project_for(fx)
    if not proj or not fx.composition:
        raise RuntimeError("Remotion project not found (set LIONSTONE_REMOTION_DIR and npm install)")
    d = fx.duration
    total = max(ev.duration, d["enter"] + d["exit"] + 0.2)
    props = {
        "text": ev.text, "subtext": ev.subtext, "enter": d["enter"], "exit": d["exit"],
        "hold": round(total - d["enter"] - d["exit"], 3), "accent": accent,
        "textColor": "#FFFFFF", "backdrop": "transparent", "width": width, "height": height,
        "fontFamily": "Inter, 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif",
        **({"number": int(ev.params["number"])} if "number" in ev.params else {}),
        **{k: v for k, v in ev.params.items() if k not in ("number", "enter", "exit")},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    props_file = out.with_suffix(".props.json")
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    cmd = ["npx", "remotion", "render", "src/index.ts", fx.composition, str(out),
           f"--props={props_file}", "--codec=prores", "--prores-profile=4444",
           "--pixel-format=yuva444p10le", "--image-format=png", "--log=error"]
    browser = os.environ.get("LIONSTONE_BROWSER")
    if browser:
        cmd.append(f"--browser-executable={browser}")
    proc = subprocess.run(cmd, cwd=proj, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0 or not out.exists():
        log = (proc.stderr or proc.stdout or "remotion render failed").strip().splitlines()
        msg = next((l.strip() for l in log if "Error" in l), log[-1] if log else "failed")
        raise RuntimeError(msg[:200])
    return out
