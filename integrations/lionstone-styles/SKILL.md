---
name: lionstone-styles
description: Edit a spoken-word video with Lionstone using short style codes (for example O4 W3 A3 G5 S4 P3). Use when the user pastes Lionstone Style codes, says "edit my video in the X style", or asks to see the styles ("show me the styles", "open the style guide").
---

# Lionstone Styles

Each code is a recipe of real `lionstone edit` options. One code per group, any combination:

| Group | Decides | Example |
|---|---|---|
| O Opening | title effect | O4 Light Sweep |
| W Words | captions | W3 Word Highlight |
| A Aspect | shape and reframing | A3 Vertical Follow |
| G Grade | colour look | G5 Punchy |
| S Sound | loudness and de-noise | S4 Social -14 Tight |
| P Pace | how hard to cut | P3 Tight |
| L Labels | chapter cards and lower thirds | L1 Editorial Labels |

## Show the styles

When asked to show or list styles, run `lionstone styles --open` (visual guide in the browser) or `lionstone styles --list` (terminal). Tell the user: pick one card per group, press Copy prompt, paste it back here with the video path.

## Turning codes into an edit

1. Run `lionstone styles --cmd <codes> --video <file>`; it prints the full `lionstone edit` command and rejects two codes from one group.
2. Add what the codes do not cover: `--title`, `--subtitle`, `--speaker "Name|Role"`, `--chapter "00:05:10 Title"`, `--language`.
3. Reply with a short style card (max 6 lines): each code with its name, and one line on why the set fits this video.
4. Run it. Outputs go to `<name>_lionstone/`; never overwrite the source.
5. Read `qa.md`. Only call the video finished if it says **Deliverable: yes**, and report every skipped check.

## When the user gives no codes

Suggest one of the starting points from `lionstone styles` (podcast clip, talking-head Reel, cinematic talk, corporate explainer) or 4-6 codes that fit, show them, and wait for a yes.

## Rules

- Face-following crops (A3, A5) need OpenCV (`pip install "lionstone[vision]"`); say so and fall back to A4 if it is missing.
- Keep graphics out of the speaker's face; the QA step flags overlaps, so fix what it reports.
- Do not stack effects the codes did not ask for.
