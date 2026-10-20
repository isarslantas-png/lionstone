# Notes for AI coding agents

- Run `pytest -q` and `ruff check src tests` before proposing changes; E2E tests need `ffmpeg` on PATH.
- Core must stay standard-library only (+ FFmpeg). Put heavy dependencies behind `[project.optional-dependencies]`.
- Architecture: agents write `EditPlan` (models.py) → `render.py` executes → `qa.py` verifies. Do not put editorial logic in the renderer.
- `speech.py` is pure and fully unit-tested — add a test for each new rule.
- FFmpeg filtergraphs: quote expressions containing commas (`x='…'`), keep text in `textfile=` (never inline), run with `cwd=workdir`.
- QA: a check that doesn't run must be `skipped` with a reason. Never mark it `passed`.
- Effects: JSON in `effects/catalog/`, Remotion component in `remotion/src/effects/`, optional FFmpeg builder registered via `register_builder`.
