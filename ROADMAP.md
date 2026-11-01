# Roadmap

Lionstone Pro & Studio follows one strategy: **a trustworthy edit + QA engine first, then the creative, pro and team workflows built on it.**

## ✅ v0.3.1 — A/V sync fix (latest)
- Audio and video stay in sync when a recording's audio ends before its video

## ✅ v0.3.0 — Lionstone Pro & Studio, free and open source
- Speech-aware editing: word-timestamp ASR (faster-whisper) or your own transcript; silence / filler / repeat / false-start cutting with three intensities, never inside a word
- Explainable `plan.json`, restore cuts, edit-by-transcript (delete / reorder / restore)
- Two-pass loudness, de-noise, click-free joins; exposure, looks and LUTs
- SRT / VTT / ASS captions, RTL + Turkish casing, captions avoid lower thirds
- 12 title effects (F01-F06, P01-P06) with Remotion and FFmpeg renderers
- Creative Suite: 133 looks, effects, transitions, motion and text presets with previews, keyframes and an agent
- Multicam, style learning, Shorts/Reels generator, FCPXML/EDL export
- Technical + editorial QA with auto-fix loop and vision QA; honest `skipped` reporting
- Team tools: roles, brand kits, versioned and locked presets, batch apply
- Lionstone Styles, MCP server, plugin API, `doctor`
- No license keys, no activation, no watermark: every feature is free (Apache-2.0)

## 🔜 Next
- [ ] Built-in speaker diarization (pyannote / NeMo, optional)
- [ ] Segment-level re-render: change a title → re-encode only affected GOPs
- [ ] Browser review UI: player + transcript + timeline + cut reasons + before/after
- [ ] Breath detection and optional breath attenuation
- [ ] Filler lexicons: German, Spanish, French, Arabic, Portuguese (PRs welcome!)
- [ ] Personal edit memory: learn from accepted / restored cuts, inspectable & resettable
- [ ] Client approval links, shot-matching color across cameras
- [ ] Premiere XML (xmeml) and OpenTimelineIO export
- [ ] Evaluation set + KPI dashboard (cut error rate, QA catch rate, human-fix count)

Targets for every KPI are set on a real evaluation set, not guessed. Scope follows user tests and cost measurements.
