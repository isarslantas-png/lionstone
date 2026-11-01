# Architecture

Lionstone is a set of small agents around one data structure: the **EditPlan**.

```
media ─▶ ingest ─▶ speech (ASR) ─┐
              └──▶ signal ───────┴▶ decide ─▶ plan.json ─▶ render ─▶ QA ─▶ deliver
                                      ▲           │                  │
                     plugins / LLM ───┘   human: transcript.md,     auto-fix
                                          cuts --restore            (re-render)
```

| Agent | Module | Responsibility |
|---|---|---|
| Orchestrator | `pipeline.py` | Step order, fingerprint cache (ASR & silence never re-run for the same file), QA → fix loop |
| Media Ingestion | `ingest.py` | ffprobe metadata, VFR / sample-rate / length warnings, refuses corrupt input |
| Speech Editing | `speech.py` | Pure functions over (silences, words): silence, filler, repeat, false-start and discourse-marker cuts. A cut is always clamped between words. |
| Edit Decision | `planner.py` | Builds the plan; graphics placement rules (no overlap, readable duration, inside the video) |
| Audio | `render.py` | highpass · de-noise · two-pass loudnorm · 8 ms join fades |
| Color | `color.py` | exposure (measured luma → gamma) · look · LUT · plugin style filter |
| Graphics & Subtitles | `effects/`, `captions.py` | effect catalog, FFmpeg + Remotion renderers, SRT/VTT/ASS, RTL, Turkish casing |
| QA | `qa.py` | technical + editorial checks; `skipped` ≠ `passed` |
| Interfaces | `cli.py`, `mcp_server.py` | CLI and MCP tools over the same functions |
| Extensions | `plugins.py` | entry-point plugins (the creative features, formerly Pro, load as a built-in one) |

## Design rules

1. **Decide ≠ render.** Agents only write the plan; the renderer only reads it.
2. **Non-destructive.** Sources are read-only; everything is re-derivable from `plan.json`.
3. **Explainable.** Every cut and graphic has a `reason`.
4. **Honest QA.** A check that did not run is reported as `skipped`, with why.
5. **Safe fallbacks.** If an effect renderer fails, its declared `fallback` runs and the render log says so.
6. **Local-first.** No network access is needed after models are downloaded.

## Timelines

* **Source timeline** — seconds in the master media (`Cut`, `Segment`, `Word`).
* **Output timeline** — seconds in the rendered video (`GraphicEvent.at`, captions).
  `EditPlan.source_to_output(t)` maps between them.

Multi-source plans (multicam) add `meta.sources = {id: {path, offset}}`; a segment's
`source` picks the camera, audio always comes from the master. `camera_time = master_time + offset`.
