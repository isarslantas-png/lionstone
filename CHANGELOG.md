# Changelog

## 0.3.0 - Unreleased
- **Everything is free.** The commercial Lionstone Pro/Studio plugin (0.2.3) is merged into the open core as `lionstone.pro`: Creative Suite (133 looks, effects, transitions, motion and text presets, previews, keyframes, agent), multicam, style learning, Shorts/Reels clips, FCPXML/EDL export, vision QA, brand kits, roles, team presets and batch apply. License keys, activation, renewal and watermarks are gone; the old tier names stay as catalog labels.
- `lionstone pro whoami` is now `lionstone whoami`. Uninstall `lionstone-pro` if you had it.
- **Lionstone Styles**: `lionstone styles [--open] [--list] [--group O] [--cmd O4 W3 A3]`, original style recipes (Opening, Words, Aspect, Grade, Sound, Pace, Labels), a visual guide and a Claude skill in `integrations/lionstone-styles`. Source: `src/lionstone/data/styles/styles.json`; run `python tools/build_styles.py` after editing.
- New extras: `lionstone[extras]` (NumPy) and `lionstone[vision]` (NumPy + OpenCV).

## 0.1.0 — 2026-10-20
First public release. See [ROADMAP.md](ROADMAP.md#-v01--mvp-this-release) for the full feature list.
