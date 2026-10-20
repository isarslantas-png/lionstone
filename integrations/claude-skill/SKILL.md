---
name: lionstone-video-editing
description: Edit spoken-word video (podcasts, interviews, talks, lectures) with the Lionstone CLI — remove fillers and dead air, add titles, lower thirds and captions, normalise loudness, and verify the result with QA before delivering.
---

# Editing video with Lionstone

Use when the user wants a recording cleaned up, cut tighter, captioned, titled, or checked.

1. `lionstone doctor` — confirm FFmpeg (and faster-whisper for transcripts).
2. `lionstone plan <file> [--language xx] [--intensity natural|balanced|dynamic]` — creates `<name>_lionstone/plan.json` and `transcript.md`.
3. Review: `lionstone cuts <plan>`. Look at cuts with confidence < 0.7 or kind `false_start`/`filler` near key sentences. Restore with `--restore ID`. Text edits: edit `transcript.md`, then `lionstone apply-transcript <plan> <transcript.md>`.
4. `lionstone render <plan>` — renders and runs QA.
5. Read `qa.md`. Only tell the user the video is ready if it says **Deliverable: yes**. List any medium/low issues and every skipped check honestly.

Defaults: YouTube → `--profile youtube`; podcast feeds → `--profile podcast`; Reels/Shorts → `--aspect 9:16 --intensity dynamic --profile social`.
Never overwrite the user's source files; outputs go to the `_lionstone` folder.
