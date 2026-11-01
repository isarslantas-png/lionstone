"""`lionstone styles` — browse Lionstone Style codes and turn them into an edit command."""

from __future__ import annotations

import argparse
import json
import shlex
import webbrowser
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "styles"


def load() -> dict:
    return json.loads((DATA / "styles.json").read_text(encoding="utf-8"))


def resolve(codes: list[str], data: dict | None = None) -> list[dict]:
    """Codes -> style dicts, at most one per group. Raises ValueError on bad input."""
    data = data or load()
    by_code = {s["code"]: (g["id"], s) for g in data["groups"] for s in g["styles"]}
    chosen: dict[str, dict] = {}
    for raw in codes:
        code = raw.strip().upper()
        if code not in by_code:
            raise ValueError(f"unknown style code {raw!r} (see `lionstone styles`)")
        gid, style = by_code[code]
        if gid in chosen:
            raise ValueError(f"{chosen[gid]['code']} and {code} are both group {gid}; pick one")
        chosen[gid] = style
    return [chosen[g["id"]] for g in data["groups"] if g["id"] in chosen]


def command_for(codes: list[str], video: str = "video.mp4") -> list[str]:
    args = ["lionstone", "edit", video]
    for style in resolve(codes):
        args += style["args"]
    return args


def cfg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--open", action="store_true", help="open the visual style guide in your browser")
    p.add_argument("--list", action="store_true", help="include a short description for every style")
    p.add_argument("--group", help="only one group letter, e.g. O, W, A")
    p.add_argument("--cmd", nargs="+", metavar="CODE", help="print the edit command for these codes")
    p.add_argument("--video", default="video.mp4", help="input file used with --cmd")


def run(a) -> int:
    if not (DATA / "styles.json").exists():
        print("styles.json not found; reinstall lionstone")
        return 1
    if a.open:
        guide = DATA / "guide" / "index.html"
        print(f"Opening {guide}")
        webbrowser.open(guide.as_uri())
        return 0
    if a.cmd:
        try:
            print(shlex.join(command_for(a.cmd, a.video)))
        except ValueError as e:
            print(f"lionstone styles: {e}")
            return 2
        return 0
    data = load()
    for g in data["groups"]:
        if a.group and g["id"] != a.group.upper():
            continue
        print(f"\n{g['id']} - {g['name']}")
        for s in g["styles"]:
            print(f"  {s['code']:3} {s['name']}" + (f"  - {s['desc'][:68]}" if a.list else ""))
    print("\nTry: lionstone styles --cmd O4 W3 A3   |   guide: lionstone styles --open")
    return 0
