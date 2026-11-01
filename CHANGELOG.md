# Changelog

## 0.3.1 — 2026-11-01
- **Fix: audio/video stay in sync when the source audio ends before the video.** A kept segment that ran past the end of the audio produced a shorter audio piece, so the render drifted (QA reported it as `av_length`, and blocked delivery above 0.5 s). Each segment's audio is now padded with silence to the segment length.
- The many-features render test prints the QA report when it fails and now requires `av_length` to pass.

## 0.3.0 — 2026-11-01
- **Everything is free.** The commercial Lionstone Pro/Studio plugin (0.2.3) is merged into the open core as `lionstone.pro`: Creative Suite (133 looks, effects, transitions, motion and text presets, previews, keyframes, agent), multicam, style learning, Shorts/Reels clips, FCPXML/EDL export, vision QA, brand kits, roles, team presets and batch apply. License keys, activation, renewal and watermarks are gone; the old tier names stay as catalog labels.
- `lionstone pro whoami` is now `lionstone whoami`. Uninstall `lionstone-pro` if you had it.
- **Lionstone Styles**: `lionstone styles [--open] [--list] [--group O] [--cmd O4 W3 A3]`, original style recipes (Opening, Words, Aspect, Grade, Sound, Pace, Labels), a visual guide and a Claude skill in `integrations/lionstone-styles`. Source: `src/lionstone/data/styles/styles.json`; run `python tools/build_styles.py` after editing.
- New extras: `lionstone[extras]` (NumPy) and `lionstone[vision]` (NumPy + OpenCV).
