"""Generate the Reel FX pack catalog (src/lionstone/pro/features/presets/reelfx.json).

Run after editing: python tools/gen_reel_presets.py

Twelve one-command social effects for vertical talking-head videos — 8 Pro,
4 Studio. Every name, look and parameter set is original to Lionstone; the
renderers are pure FFmpeg math in ``features/renderers/reel_fx.py``. No stock
overlays, LUTs, fonts or third-party assets are bundled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "lionstone" / "pro" / "features" / "presets" / "reelfx.json"
LIC = {"source": "lionstone-original", "verified": True}
CAT = "reel-fx"


def num(default, lo=0.0, hi=1.0, unit=""):
    return {"type": "number", "min": lo, "max": hi, "default": default, **({"unit": unit} if unit else {})}


def integer(default, lo, hi):
    return {"type": "int", "min": lo, "max": hi, "default": default}


def color(default):
    return {"type": "color", "default": default}


def enum(default, values):
    return {"type": "enum", "values": values, "default": default}


def reel(slug, name, tier, line, desc, params, cost="medium", tags=(), limitations=(),
         styles=("social",), duration=None):
    return {
        "id": f"lionstone.{slug}", "name": name, "kind": "effect", "category": CAT,
        "tier": tier, "implementationStatus": "ready", "version": 1,
        "parameters": params, "performanceCost": cost, "license": LIC,
        "description": f"{line} — {desc}", "tags": ["reel", "vertical", *tags],
        "styles": list(styles), "supportedRenderers": ["ffmpeg"],
        "compatibleMedia": ["video", "image"],
        "duration": duration or {"default": 4.0, "min": 1.0, "max": 60.0},
        "intensityRange": [0.0, 1.0], "fallbackEffectId": None,
        "limitations": list(limitations), "pipeline": "filter",
    }


ACCENT = "#E8A33D"   # Lionstone gold — brand kits override it
INK = "#14161C"      # Lionstone ink

REEL_FX = [
    # ------------------------------------------------------------------ Pro (8)
    reel("stage-light", "Stage Light", "pro", "the room goes dark, you stay lit",
         "Two eased vignette passes centred on the speaker plus a gentle exposure and "
         "saturation drop outside the pool of light. Ramps in and out with the window.",
         {"intensity": num(0.7), "x": num(0.5), "y": num(0.36), "size": num(0.5)},
         cost="low", tags=["light", "focus"], styles=("social", "cinematic")),
    reel("press-mono", "Press Mono", "pro", "you, printed in tomorrow's paper",
         "Documentary black-and-white with crushed blacks, paper-tinted whites, ink "
         "sharpening and print grain. Pair with a text preset for stamped headlines.",
         {"intensity": num(0.8), "grain": num(0.4), "paper": color("#F2EAD8")},
         cost="low", tags=["mono", "documentary"], styles=("social", "documentary")),
    reel("frost-panels", "Frost Panels", "pro", "glass cards float beside you",
         "Up to three frosted-glass cards (blurred, lifted, tinted, outlined) appear one "
         "after another beside the speaker, with placeholder lines for your own text.",
         {"panels": integer(2, 1, 3), "frost": num(0.6), "tint": color("#FFFFFF")},
         tags=["glass", "ui"],
         limitations=["Cards sit at fixed safe positions (left/right of a centred speaker)."]),
    reel("duotone-pop", "Duotone Pop", "pro", "two colours, zero noise",
         "Maps the shot onto two colours (shadows → highlights) for a bold poster look. "
         "Set both colours to your brand palette.",
         {"intensity": num(1.0), "shadow": color("#1A1238"), "highlight": color("#FF8A3D")},
         cost="low", tags=["color", "poster"]),
    reel("scan-line", "Scan Line", "pro", "a light beam reads the frame",
         "A crisp glowing line with a soft trailing band sweeps top to bottom on repeat — "
         "ideal for 'AI analysing' or before/after moments.",
         {"intensity": num(0.7), "speed": num(0.6, 0.2, 2.0, "sweeps/s"),
          "color": color("#7CF5FF")},
         tags=["tech", "ai"]),
    reel("afterimage", "Afterimage", "pro", "every move leaves a trail",
         "Bright parts of the image decay slowly, so gestures, head turns and products "
         "leave luminous trails.",
         {"intensity": num(0.8), "decay": num(0.92, 0.5, 0.99)},
         tags=["motion", "trail"],
         limitations=["Trails come from bright areas; works best on lit subjects."]),
    reel("halo-orbit", "Halo Orbit", "pro", "a ring of light circles your head",
         "Glowing dots on a tilted elliptical ring rotate around the speaker's head. "
         "Position, radius, dot count, speed and colour are adjustable.",
         {"color": color("#FFD27A"), "x": num(0.5), "y": num(0.2), "radius": num(0.3, 0.1, 0.45),
          "dots": integer(8, 3, 12), "speed": num(0.3, 0.05, 1.0, "rev/s")},
         tags=["orbit", "glow"],
         limitations=["Ring is drawn in front of the speaker (no depth sorting)."]),
    reel("neon-outline", "Neon Outline", "pro", "neon traces your silhouette",
         "Edge detection tinted to a neon colour and glowed, screened over the shot.",
         {"intensity": num(0.75), "detail": num(0.5), "color": color("#FF4FD8")},
         tags=["neon", "edges"]),
    # --------------------------------------------------------------- Studio (4)
    reel("insight-split", "Insight Split", "studio", "your numbers on top, you below",
         "Brand-coloured chart panel fills the top of the frame; bars rise one by one "
         "(your values or an automatic rising series) while the speaker moves to the "
         "lower part.",
         {"split": num(0.38, 0.25, 0.5), "bars": integer(5, 2, 7),
          "values": {"type": "list", "items": {"type": "number", "min": 0, "max": 1},
                     "default": []},
          "bg": color(INK), "accent": color(ACCENT)},
         tags=["chart", "data", "brand"],
         limitations=["Speaker crop keeps the upper-middle of the frame (centred faces)."]),
    reel("brand-frame", "Brand Frame", "studio", "your clip, framed in your brand",
         "The clip sits inside an accent-bordered card on your brand background with a "
         "small accent tab underneath — consistent series framing for a whole channel.",
         {"inset": num(0.84, 0.7, 0.95), "bg": color(INK), "accent": color(ACCENT)},
         cost="low", tags=["brand", "frame"]),
    reel("progress-rail", "Progress Rail", "studio", "a rail fills as you count the steps",
         "A brand rail fills across the window while step dots light up in sequence — "
         "for lists, tutorials and 'step 3 of 5' content.",
         {"steps": integer(5, 2, 8), "side": enum("left", ["left", "right", "top"]),
          "track": color("#FFFFFF"), "accent": color(ACCENT)},
         cost="low", tags=["steps", "list", "brand"]),
    reel("pixel-resolve", "Pixel Resolve", "studio", "your shot assembles out of pixels",
         "Signature reveal: the frame starts as a coarse two-tone dither in your brand "
         "colours and resolves through finer pixel stages into the clean shot.",
         {"duration": num(1.2, 0.4, 3.0, "s"), "tone_a": color(INK), "tone_b": color(ACCENT)},
         cost="high", tags=["reveal", "pixel", "brand"],
         limitations=["The reveal plays at the start of each window; the rest is clean."]),
]


def main() -> int:
    ids = [d["id"] for d in REEL_FX]
    assert len(ids) == len(set(ids)), "duplicate ids"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(REEL_FX, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(ids)} reel presets → {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
