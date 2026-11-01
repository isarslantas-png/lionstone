# Roadmap

Lionstone follows the spec's strategy: **first a trustworthy edit + QA engine, then style learning, advanced effects, short clips and pro workflows.**

## ✅ v0.1 — MVP (this release)
- Media validation (VFR, sample rate, A/V length, corrupt input)
- Word-timestamp ASR (faster-whisper) or bring-your-own transcript JSON
- Silence / filler / repeat / false-start cutting with three intensities, never inside a word
- Explainable `plan.json`, restore cuts, edit-by-transcript (delete / reorder / restore)
- Two-pass loudness, de-noise, click-free joins; exposure + looks + LUT
- SRT / VTT / ASS captions, RTL + Turkish casing, captions avoid lower thirds
- 6 free title effects (Remotion + FFmpeg), effect catalog + JSON schema
- Technical + editorial QA with auto-fix loop; honest `skipped` reporting
- MCP server, plugin API, `doctor`
- Former Pro plugin (now free, in the core): multicam, style learning, Shorts generator, FCPXML/EDL, P01-P06 effects, vision QA, Creative Suite

## 🔜 v0.2
- [ ] Speaker diarization in the free tier (pyannote / NeMo, optional)
- [ ] Segment-level re-render: change a title → re-encode only affected GOPs
- [ ] Browser review UI: player + transcript + timeline + cut reasons + before/after
- [ ] Breath detection and optional breath attenuation
- [ ] Filler lexicons: German, Spanish, French, Arabic, Portuguese (PRs welcome!)
- [ ] Evaluation set + KPI dashboard (cut error rate, QA catch rate, human-fix count)

## 🔭 v0.3 — Team tools
- [ ] Personal edit memory: learn from accepted / restored cuts, inspectable & resettable
- [ ] Batch queue, brand profiles, client approval links
- [ ] Shot-matching color across cameras, motion-graphics templates
- [ ] Premiere XML (xmeml) and OpenTimelineIO export

Targets for every KPI are set on a real evaluation set, not guessed. Scope follows user tests and cost measurements.
