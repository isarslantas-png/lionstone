# Contributing to Lionstone

Thanks for helping! The most valuable contributions right now:

1. **Filler lexicons** for your language (`src/lionstone/speech.py` → `_FILLER_RE`, `_DISCOURSE`) with tests.
2. **New free effects** — see [docs/effects.md](docs/effects.md).
3. **QA checks** that catch real mistakes — see [docs/qa.md](docs/qa.md).
4. **Bug reports with a short sample file** (or the `plan.json` + `qa.json`).

## Dev setup

```bash
git clone https://github.com/isarslantas-png/lionstone && cd lionstone
pip install -e ".[dev,whisper,mcp]"
pytest                    # unit + end-to-end (needs ffmpeg)
ruff check src tests
cd remotion && npm install && npm run typecheck && npm run studio
```

## Rules of the road
- Decisions go into the plan; the renderer never decides.
- Every cut / graphic needs a human-readable `reason`.
- Never report a check as passed if it did not run.
- Keep the core dependency-free (stdlib + FFmpeg); heavy deps are optional extras.
- Add a test for every behaviour change. E2E tests synthesize media with FFmpeg — no binary fixtures.
- Only add fonts, LUTs or footage whose license allows redistribution.

By contributing you agree your work is licensed under Apache-2.0.
