<p align="center">
  <a href="https://github.com/ismailarslantas/lionstone/releases/latest"><img src="assets/pro-studio/01-hero.jpg" alt="Lionstone Pro & Studio are now free — open source, Apache-2.0, local-first, no license keys, no watermark" width="100%"></a>
</p>

<p align="center">
  <a href="https://github.com/ismailarslantas/lionstone/actions"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/ismailarslantas/lionstone/ci.yml?branch=main&label=tests&style=flat-square"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-E8B04B?style=flat-square"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square">
  <img alt="FFmpeg" src="https://img.shields.io/badge/FFmpeg-powered-007808?style=flat-square">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-server-8A63D2?style=flat-square">
  <a href="https://github.com/ismailarslantas/lionstone/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/ismailarslantas/lionstone?style=flat-square&color=E8B04B"></a>
</p>

<p align="center">
  <b>Lionstone Pro & Studio are now free.</b> The complete AI video editor — multicam, Creative Suite, Shorts generator, NLE export, team tools and Lionstone Styles — in one open-source package.<br>
  Local-first · no upload · no license key · no watermark · works offline · <a href="https://github.com/ismailarslantas/lionstone/releases/latest">Latest release</a>
</p>

```bash
pip install "lionstone[all] @ git+https://github.com/ismailarslantas/lionstone"
lionstone doctor
```

---

## 🦁 Lionstone Pro & Studio — now free

Lionstone Pro ($12/month) and Lionstone Studio ($39/month) used to be a separate, paid plugin. Since **v0.3** every one of their features ships in this repository under Apache-2.0. There is nothing to buy, activate or renew, and nothing leaves your computer.

<img src="assets/pro-studio/02-what-changed.jpg" alt="What changed: paid Pro and Studio plans are now completely free and built into the core" width="100%">

| Before | Now |
|---|---|
| Lionstone Pro — $12/month | **Free**, built into the core |
| Lionstone Studio — $39/month (5 seats) | **Free**, for any team size |
| License keys, activation, renewal | **None** |
| Locked premium presets and watermarked previews | **Every preset unlocked** |
| Separate `lionstone-pro` package | **One package**: `lionstone` |

Coming from the paid plugin? Run `pip uninstall lionstone-pro`, then install as above. `lionstone pro whoami` is now `lionstone whoami`; `activate`, `status` and `renew` are gone.

### ✂️ Edits that understand speech

<img src="assets/pro-studio/03-smart-editing.jpg" alt="Smart editing: speech-aware cuts, explainable plan.json, edit via transcript, one-command restore" width="100%">

Most "AI editors" either chop every silence (and your sentences with it) or send your footage to a cloud you don't control. **Lionstone edits like a careful human editor.** It transcribes your video locally with word timestamps, removes fillers (`um`, `uh`, `ııı`, `eee`), stutters, repeated phrases and false starts, keeps the pauses that carry meaning, and **never cuts inside a word**. Every decision is written to `plan.json` with its reason, so you can read the edit, change it by editing `transcript.md`, or undo any cut with `lionstone cuts plan.json --restore c0004`. Your original files are never touched.

### 🎨 Creative Suite — 133 presets, 25 animated text styles

<img src="assets/pro-studio/04-creative-suite.jpg" alt="Creative Suite: 133 original presets, before/after previews, 25 animated text styles, karaoke captions, Lionstone Agent" width="100%">

- **133 original presets** — looks, effects, transitions and motion. Browse with `lionstone fx list`, inspect with `lionstone fx show soft-bloom`.
- **Real previews before you commit** — `lionstone fx preview soft-bloom --before-after --gif` renders a low-res before/after with the same code the final export uses.
- **25 animated text presets** — Word Pop, Counter Up, Price Reveal, Stat Emphasis, Location and Speaker labels, Call to Action, Type-on, Signature End Card — plus karaoke captions that highlight each word as it is spoken.
- **Lionstone Agent** — `lionstone fx auto plan.json --content vlog --style social` picks one consistent look, emphasis zooms and transitions on real topic changes, stays within budgets, and gives a reason for every choice.
- **Safe by design** — `lionstone fx render` checks flash rate (≤ 3 per second), exposure, saturation and stale edits before it delivers.

### 🎬 Pro workflow — multicam, style learning, Shorts, NLE export

<img src="assets/pro-studio/05-pro-workflow.jpg" alt="Pro workflow: multicam, style learn, clips for Shorts and Reels, export to DaVinci Resolve, Final Cut and Premiere" width="100%">

- **Multicam** — `lionstone multicam` syncs two or more cameras and isolated mics on their audio, re-checks sync to catch clock drift, gates mic bleed and cuts to the active speaker with sensible shot lengths and wide shots for crosstalk.
- **Style learning** — `lionstone style learn ref1.mp4 ref2.mp4` learns cut rhythm, pause behaviour, loudness and colour from videos you like, then applies them to new edits.
- **Shorts & Reels** — `lionstone clips plan.json -n 5` finds self-contained moments with a strong first line and renders them 9:16 with face-tracked reframing, a kinetic hook title and word-highlight captions.
- **Hand off to your editor** — `lionstone export plan.json` writes FCPXML for DaVinci Resolve and Final Cut Pro, and EDL for Premiere Pro, pointing at your original media.

### ✅ QA, team tools and agents

<img src="assets/pro-studio/06-qa-teams-get-it.jpg" alt="Quality assurance, team workflows, Lionstone Styles and Claude/MCP integration" width="100%">

- **QA before delivery** — every render is decoded end to end and checked for A/V sync, black and frozen frames, EBU R128 loudness and true peak, clicks at every join, caption timing and, with `lionstone[vision]`, titles or captions covering a face. Skipped checks are reported as skipped, never as passed.
- **Team tools (formerly Studio)** — roles per person (`lionstone team`), brand kits with colours, fonts, logo, lower third and end card (`lionstone brand`), versioned and locked team presets with history, and `lionstone fx batch` to apply one look to a whole season.
- **Agent-ready** — the built-in MCP server lets Claude, Cursor or any MCP client plan, review and render edits for you.

### 🧭 New: Lionstone Styles

Original style recipes you combine like a code: one pick per group, e.g. `O6 W3 A3 G5 S4 P3`. Every code maps to real Lionstone options, so `lionstone styles --cmd O6 W3 A3 G5 S4 P3` prints the exact edit command and `lionstone styles --open` shows the visual guide.

| Group | Controls | Codes |
|---|---|---|
| **O** Opening | how the title enters | O1 Quiet Fade · O2 Slow Rise · O3 Hairline Reveal · O4 Light Sweep · O5 Film Grain Open · O6 Kinetic Hook · O7 Signature Stamp |
| **W** Words | how speech shows on screen | W1 Clean Lines · W2 Bold Punch · W3 Word Highlight · W4 Silent Frame · W5 Sidecar Only |
| **A** Aspect | frame shape and speaker follow | A1 Native · A2 Wide Stage · A3 Vertical Follow · A4 Vertical Centre · A5 Square Follow · A6 Portrait Feed |
| **G** Grade | colour look | G1 Untouched · G2 Natural · G3 Warm Room · G4 Cool Studio · G5 Punchy · G6 Film |
| **S** Sound | loudness and de-noise | S1 YouTube −14 · S2 Podcast −16 · S3 Broadcast −23 · S4 Social −14 Tight · S5 Rescue |
| **P** Pace | how tightly pauses are cut | P1 Breathing Room · P2 Tidy · P3 Tight |
| **L** Labels | chapter cards and lower thirds | L1 Editorial Labels · L2 Spaced Chapters · L3 Line Chapters |

Starting points: **Podcast clip** `O1 W1 A2 G2 S2 P2 L1` · **Talking-head Reel** `O6 W3 A3 G5 S4 P3` · **Cinematic talk** `O4 W4 A2 G6 S1 P1 L2` · **Corporate explainer** `O3 W1 A2 G4 S1 P2 L3`. A Claude skill in [`integrations/lionstone-styles`](integrations/lionstone-styles) edits with these codes.

---

<p align="center">
  <img src="assets/demo-terminal.svg" alt="lionstone edit run" width="88%">
</p>

## ✨ What it does

| | |
|---|---|
| ✂️ **Speech-aware cutting** | Removes fillers (`um`, `uh`, `ııı`, `eee`…), stutters (`the the`), repeated phrases and false starts — keeps breaths and dramatic beats. Three intensities: `natural` · `balanced` · `dynamic`. |
| 🧾 **Explainable, reversible plan** | Every decision lands in `plan.json` with a reason (`filler "um,"`, `pause 2.59s → 0.55s (sentence beat kept)`). Restore any cut with one command. Originals are never touched. |
| 📝 **Edit video by editing text** | Delete a line in `transcript.md` → that sentence is cut. Move lines → scenes reorder. Uncomment → it's back. |
| 🔊 **Broadcast-grade audio** | Two-pass EBU R128 loudness (YouTube −14, podcast −16, broadcast −23 LUFS), true-peak ceiling, de-noise, 8 ms micro-fades at every join (no clicks). |
| 🎨 **Color & look** | Auto-exposure, tasteful looks (`natural`, `warm`, `film`, `punchy`…), your own `.cube` LUT. |
| 🔤 **Titles, lower thirds, captions** | 12 title effects, SRT/VTT/ASS captions, burned-in captions that move out of the way of lower thirds. Turkish casing (`i → İ`) and right-to-left scripts handled. |
| ✅ **QA before delivery** | Full decode, A/V length, black/frozen frames, loudness + true peak, clicks at every join, word-clipping, caption timing, graphics overlap/readability. **Skipped checks are reported as skipped — never as passed.** Auto-fixes what it can, then re-checks. |
| 🤖 **Agent-ready** | Built-in **MCP server**: let Claude, Cursor or any MCP client plan, review and render edits for you. |
| 🧩 **Plugin system** | Effects, commands, exporters, QA hooks, caption styles and reframers are all plugins. |

## 🚀 Quick start

```bash
# 1. FFmpeg (5+) — any build works; titles/burned captions need libfreetype + libass
sudo apt install ffmpeg                  # Ubuntu / Debian (full build)
winget install ffmpeg                    # Windows (full build)
conda install -c conda-forge ffmpeg      # macOS / anywhere (full build)
# brew install ffmpeg also works; if `lionstone doctor` reports drawtext/subtitles
# missing, Lionstone still edits but skips titles & burn-in (and says so in qa.md)

# 2. Lionstone (+ local Whisper transcription)
pip install "lionstone[whisper] @ git+https://github.com/ismailarslantas/lionstone"

# 3. Edit
lionstone edit podcast.mp4 --title "Episode 12" --speaker "Ayşe Yılmaz|Founder"
```

You get, in `podcast_lionstone/`:

```
podcast.edit.mp4    ← the edited video
podcast.edit.srt    ← captions (also .vtt)
plan.json           ← every cut / title / setting, with reasons
transcript.md       ← edit-by-text file
qa.md · qa.json     ← what was checked, what passed, what needs a human
```

Check your setup any time with `lionstone doctor`.

### 📚 Step-by-step guides (with real screenshots)

| | Guide | You'll learn |
|---|---|---|
| ![](docs/guides/img/free-timeline.png) | **[Your first video](docs/guides/free.md)** | install, one-command edit, captions, reading the QA report, editing by text, restoring cuts |
| ![](docs/guides/img/pro-shorts.png) | **[Creative features](docs/guides/pro.md)** | the agent, looks / transitions / animated text, previews, Shorts & Reels, Resolve / Final Cut / Premiere export |
| ![](docs/guides/img/studio-result.jpg) | **[Team tools](docs/guides/studio.md)** | roles per person, brand kits, locked presets with history, batch apply for a season |

## 🧭 How it works

```mermaid
flowchart LR
  A[🎬 Media] --> B[Ingest<br/>validate · VFR · timecode]
  B --> C[Speech<br/>Whisper word timestamps]
  B --> D[Signal<br/>silence · loudness]
  C & D --> E{{Decide<br/>plan.json}}
  E -->|you review / edit text / restore| E
  E --> F[Render<br/>FFmpeg · Remotion]
  F --> G[QA<br/>technical + editorial]
  G -->|auto-fix| F
  G --> H[✅ Deliver<br/>video · captions · report]
```

**Deciding is separate from rendering.** Agents write structured decisions into a plain-JSON plan; the renderer only executes it. That's what makes edits explainable, diffable and undoable — and lets an LLM agent work on the plan instead of on pixels.

## 🎛️ Everyday commands

```bash
lionstone plan  talk.mp4 --intensity dynamic      # analyze only → plan.json + transcript.md
lionstone cuts  talk_lionstone/plan.json          # list every cut with its reason
lionstone cuts  talk_lionstone/plan.json --restore c0004 c0011   # undo specific cuts
lionstone apply-transcript talk_lionstone/plan.json talk_lionstone/transcript.md
lionstone render talk_lionstone/plan.json         # render + QA
lionstone qa    any_video.mp4                     # QA any file
lionstone effects list --style cinematic          # browse effects 
lionstone effects preview F03 --text "Chapter 2" --gif
```

<details>
<summary><b>All edit options</b></summary>

```
--intensity natural|balanced|dynamic   --profile youtube|podcast|social|broadcast
--aspect 16:9|9:16|1:1|4:5             --reframe center|face (needs OpenCV)
--title / --subtitle / --outro         --speaker "Name|Title[|SPEAKER_00]" (repeatable)
--chapter "00:12:30 Pricing"           --title-effect F01 … --lower-third-effect F05
--captions burn|file|none              --caption-style clean|bold|social
--color natural|warm|cool|punchy|film  --lut my.cube    --denoise off|light|strong
--model small|medium|large-v3          --language tr    --transcript words.json   --no-asr
--renderer auto|ffmpeg|remotion        --fast           --x key=value (plugins)
```
</details>

## 🎞️ Effect library

Every effect is a JSON definition (timing, parameters, constraints, license tier, fallback) + a **Remotion** component (reference look, alpha channel) + a native **FFmpeg** renderer (zero-dependency fallback). If an effect can't render, its declared fallback runs and the report says so.

| Classic | | | Premium | | |
|:-:|:-:|:-:|:-:|:-:|:-:|
| <img src="assets/effects/F01.gif" width="200"><br>**F01** Cinematic Fade | <img src="assets/effects/F02.gif" width="200"><br>**F02** Slow Rise | <img src="assets/effects/F03.gif" width="200"><br>**F03** Line Reveal | <img src="assets/effects/P01.gif" width="200"><br>**P01** Light Sweep | <img src="assets/effects/P02.gif" width="200"><br>**P02** Footage Mask | <img src="assets/effects/P03.gif" width="200"><br>**P03** Depth Parallax |
| <img src="assets/effects/F04.gif" width="200"><br>**F04** Chapter Card | <img src="assets/effects/F05.gif" width="200"><br>**F05** Lower Third | <img src="assets/effects/F06.gif" width="200"><br>**F06** Letter Spacing | <img src="assets/effects/P04.gif" width="200"><br>**P04** Film Grain | <img src="assets/effects/P05.gif" width="200"><br>**P05** Kinetic Words | <img src="assets/effects/P06.gif" width="200"><br>**P06** Brand Reveal |

Default placement rules (all overridable): opening → Cinematic Fade · new chapter → Chapter Card · first time a speaker talks → Lower Third · normal speech → **no effect** (choosing no effect is a valid edit) · closing → fade. Never two animated titles at once; captions move up while a lower third is on screen; always long enough to read; Pro effects are never auto-applied. (Pro's vision QA also checks that graphics don't cover faces.)

Remotion titles: `cd remotion && npm install` once — Lionstone picks it up automatically (`--renderer auto`).

## 🤖 Use it from Claude / Cursor (MCP)

```bash
pip install "lionstone[mcp,whisper] @ git+https://github.com/ismailarslantas/lionstone"
```

```json
{ "mcpServers": { "lionstone": { "command": "lionstone", "args": ["mcp"] } } }
```

Then just ask: *"Edit ~/Videos/ep12.mp4 for YouTube, keep it natural, introduce Ayşe as Founder, and show me any cut you're unsure about."* The agent gets tools to `plan_edit`, read/`edit_transcript`, `restore_cuts`, `render_plan` and read the QA verdict — it can't claim success unless QA says `deliverable: true`.

## 💎 Feature reference — everything is free

Every feature is free and open source (Apache-2.0): no license key, no account, no watermark, no upload, no telemetry. The former Pro and Studio features are part of the core.

| Feature | Command |
|---|---|
| Speech-aware cutting, edit by text, restore cuts, plan.json | `lionstone edit` · `plan` · `apply-transcript` |
| Loudness, de-noise, color, LUTs, captions, RTL, Turkish | `lionstone edit` |
| 12 title effects (F01-F06 + P01-P06) and 12 animated text presets | `lionstone effects list` |
| **Creative Suite**: 133 looks, effects, transitions, motion and text presets with previews, keyframes and an agent that picks them | `lionstone fx list` · `fx preview` · `fx auto` |
| **Multicam**: audio sync with drift check, active-speaker switching | `lionstone multicam` |
| **Style learning** from 1-3 reference videos | `lionstone style learn` |
| **Shorts/Reels generator**: best moments → 9:16, face-tracked reframe, hook titles | `lionstone clips` |
| **Project export**: FCPXML (Resolve / Final Cut) + EDL (Premiere) | `lionstone export` |
| **Team tools**: brand kits, roles, versioned and locked presets, batch apply | `lionstone team` · `brand` · `preset` · `fx batch` |
| **Vision QA**: graphics/captions covering faces | `pip install "lionstone[vision]"` |
| **Lionstone Styles**: codes like `O4 W3 A3 G5 S4 P3` that map to real edit options | `lionstone styles --open` · `--cmd O4 W3 A3` |

Install everything with `pip install "lionstone[all] @ git+https://github.com/ismailarslantas/lionstone"`. Details: [docs/PRO.md](docs/PRO.md) and the [guides](docs/guides/pro.md).

## 🗺️ Roadmap

See [ROADMAP.md](ROADMAP.md). Next up: built-in speaker diarization, segment-level re-render, browser review UI (player + transcript + timeline), filler detection without ASR, more languages for filler lexicons.

## 🤝 Contributing

PRs welcome — especially filler lexicons for your language, new free effects, and QA checks. Start with [CONTRIBUTING.md](CONTRIBUTING.md); AI coding agents should read [AGENTS.md](AGENTS.md).

```bash
git clone https://github.com/ismailarslantas/lionstone && cd lionstone
pip install -e ".[dev,whisper]" && pytest
```

## 📄 License

Everything: [Apache-2.0](LICENSE). Effect assets ship with OFL/system fonts only — check the license of any font, LUT or footage you add.

<p align="center"><sub>Built in İzmir by <a href="https://www.linkedin.com/in/ismailarslantas/">İsmail Arslantaş</a> · If Lionstone saved you an evening of editing, a ⭐ helps others find it.</sub></p>
