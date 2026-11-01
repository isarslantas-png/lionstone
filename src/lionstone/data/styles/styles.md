# Lionstone Style Reference

Pick one style per group and combine the codes, for example O4 W3 A3 G5 S4 P3. Every style is a recipe of real Lionstone options, so `lionstone styles --cmd O4 W3 A3` prints the exact edit command.

## O - Opening

The first seconds: how the title enters.

- **O1 Quiet Fade**: Title fades in and out with a slow, calm ease. Safe for interviews and lectures. `--title-effect F01`
- **O2 Slow Rise**: Title drifts upward while it fades in. Documentary feel. `--title-effect F02`
- **O3 Hairline Reveal**: A thin line draws out, then the title appears under it. Clean and corporate. `--title-effect F03`
- **O4 Light Sweep**: A band of light glides across the letters as they appear. Premium and cinematic. `--title-effect P01`
- **O5 Film Grain Open**: Title sits in animated film grain with a soft vignette. Story-driven pieces. `--title-effect P04`
- **O6 Kinetic Hook**: Words land one after another with a stagger. Built for Shorts and Reels hooks. `--title-effect P05`
- **O7 Signature Stamp**: Your brand name reveals with a short, confident flourish. Channel intros. `--title-effect P06`

## W - Words

How speech shows up on screen.

- **W1 Clean Lines**: Readable burned-in captions, sentence case, bottom third. `--captions burn --caption-style clean`
- **W2 Bold Punch**: Large, heavy captions that carry the energy of the delivery. `--captions burn --caption-style bold`
- **W3 Word Highlight**: Social-style captions with the spoken word highlighted as it is said. `--captions burn --caption-style social`
- **W4 Silent Frame**: No captions on the picture. Calm, premium, or when the footage already has text. `--captions none`
- **W5 Sidecar Only**: Captions exported as .srt/.vtt files, nothing burned in. For YouTube and podcasts. `--captions file`

## A - Aspect

Shape of the frame and how it follows the speaker.

- **A1 Native**: Keep the source shape untouched. `(no options)`
- **A2 Wide Stage**: 16:9 for YouTube and presentations. `--aspect 16:9`
- **A3 Vertical Follow**: 9:16 with a face-following crop. Needs OpenCV (pip install lionstone[vision]). `--aspect 9:16 --reframe face`
- **A4 Vertical Centre**: 9:16 with a fixed centre crop. No extra dependencies. `--aspect 9:16 --reframe center`
- **A5 Square Follow**: 1:1 with a face-following crop for feeds. Needs OpenCV. `--aspect 1:1 --reframe face`
- **A6 Portrait Feed**: 4:5 centre crop, the tallest shape most feeds show uncropped. `--aspect 4:5 --reframe center`

## G - Grade

The colour look applied after exposure correction.

- **G1 Untouched**: No colour work at all. `--color none`
- **G2 Natural**: Light contrast and saturation lift. The default, safe everywhere. `--color natural`
- **G3 Warm Room**: Gently warmer shadows and skin. Friendly, conversational. `--color warm`
- **G4 Cool Studio**: Cooler balance for tech, science and corporate topics. `--color cool`
- **G5 Punchy**: More contrast, saturation and local sharpness. Reads well on phones. `--color punchy`
- **G6 Film**: Softer saturation with a medium-contrast curve. Cinematic. `--color film`

## S - Sound

Loudness target and noise handling.

- **S1 YouTube -14**: -14 LUFS with a -1 dB true-peak ceiling, light de-noise. `--profile youtube --denoise light`
- **S2 Podcast -16**: -16 LUFS for Apple and Spotify spoken word, light de-noise. `--profile podcast --denoise light`
- **S3 Broadcast -23**: EBU R128 at -23 LUFS for TV and festivals. `--profile broadcast --denoise light`
- **S4 Social -14 Tight**: -14 LUFS with a narrower loudness range so it survives phone speakers. `--profile social --denoise light`
- **S5 Rescue**: YouTube loudness with strong de-noise for noisy rooms. `--profile youtube --denoise strong`

## P - Pace

How aggressively silences and fillers are cut.

- **P1 Breathing Room**: Keeps natural pauses and filler words, removes only long dead air and exact repeats. `--intensity natural`
- **P2 Tidy**: Removes fillers, repeats and false starts but keeps sentence beats. `--intensity balanced`
- **P3 Tight**: Shortest pauses and discourse markers removed. Fast, social pacing. `--intensity dynamic`

## L - Labels

Chapter cards and speaker lower thirds.

- **L1 Editorial Labels**: Chapter cards and an editorial lower third for each new speaker. `--chapter-effect F04 --lower-third-effect F05`
- **L2 Spaced Chapters**: Wide-tracked chapter titles with the editorial lower third. `--chapter-effect F06 --lower-third-effect F05`
- **L3 Line Chapters**: Hairline chapter reveals, same lower third. Minimal and corporate. `--chapter-effect F03 --lower-third-effect F05`

## Starting points

- **Podcast clip**: `O1 W1 A2 G2 S2 P2 L1` - Calm, readable, loudness for audio apps.
- **Talking-head Reel**: `O6 W3 A3 G5 S4 P3` - Fast hook, highlighted words, phone-friendly sound.
- **Cinematic talk**: `O4 W4 A2 G6 S1 P1 L2` - Slow, premium, no captions on the picture.
- **Corporate explainer**: `O3 W1 A2 G4 S1 P2 L3` - Clean, cool and tidy.
