# Lionstone Pro & Studio

Pro is a plugin for the open-source core. Install it next to `lionstone`, activate your key once, and the extra commands and effects unlock. Everything still runs locally.

| Plan | For | Suggested price* |
|---|---|---|
| **Pro** | creators and editors who publish every week | $12 / month · $99 / year |
| **Studio** | agencies & teams (5 seats, multiple brands, batch) | $39 / month · $349 / year |

<sub>*Launch pricing. Students, non-profits and open-source maintainers: ask for a free key.</sub>

**→ [Buy a license](https://ismailarslantas.com)** <!-- TODO: replace with your Lemon Squeezy / Gumroad checkout URL -->

## What you get

| Command / feature | What it does |
|---|---|
| `lionstone multicam` | Syncs 2+ cameras and isolated mics on audio (coarse onset match + sample-accurate refine), re-checks sync mid-way and at the end to catch clock drift, gates mic bleed, then cuts to the active speaker with minimum shot length, hysteresis, crosstalk → wide shot and long-monologue cutaways. Never assigns footage a camera didn't record. |
| `lionstone style learn ref1.mp4 ref2.mp4` | Builds a reusable style profile: cut rhythm, pause behaviour → intensity, loudness profile, color (contrast / saturation / warmth). Apply with `--x style=style.json`, choose traits with `--x style_apply=tempo,color`. |
| `lionstone clips plan.json -n 5` | Finds self-contained moments (complete sentences, strong first line, good pace), renders 9:16 with face-tracked reframing, a kinetic hook title and word-highlight captions. `--llm` re-ranks with your own Claude API key. |
| `lionstone export plan.json` | FCPXML 1.10 (DaVinci Resolve, Final Cut Pro) + CMX3600 EDL (Premiere Pro). Clips point at your original media, multicam included. |
| `lionstone variants talk.mp4` | Natural / Cinematic / Dynamic plans from one analysis, compared side by side. |
| Pro effects P01–P06 | Light Sweep, Footage Mask Reveal, Depth Parallax, Film Grain, Staggered Kinetic, Signature Brand Reveal — Remotion quality, FFmpeg fallbacks for P03–P06. |
| Vision QA | Flags lower thirds, titles or captions that cover a face. |
| `--reframe face` | Face-following crop for 9:16 / 1:1 / 4:5. |

## Activate

```bash
pip install "lionstone-pro @ <private download link from your receipt>"
lionstone pro activate LSP1.xxxxx.yyyyy
lionstone pro status
lionstone pro setup-remotion   # optional, needs Node.js 18+: Remotion-quality P01–P06
```

Without `setup-remotion`, P03–P06 render with their FFmpeg versions and P01/P02 fall back to F01.
It installs into your user data folder (`%LOCALAPPDATA%\lionstone\pro-remotion` on Windows,
`~/.local/share/lionstone/pro-remotion` elsewhere). Before `pip uninstall lionstone-pro`, run
`lionstone pro remove-remotion` to delete it.

Servers / CI: set `LIONSTONE_LICENSE` instead of activating. Keys are verified offline (Ed25519 signatures) — no phone-home.
