# Recipes

```bash
# YouTube podcast, two speakers, chapters
lionstone edit ep12.mp4 --language tr --title "12. Bölüm" --subtitle "Yapay zekâ ile kurgu" \
  --speaker "Ayşe Yılmaz|Kurucu" --speaker "Mehmet Kaya|Editör" \
  --chapter "00:04:10 Başlangıç" --chapter "00:21:30 Araçlar" --outro "Abone olmayı unutmayın"

# Tight vertical cut for Reels (center crop; Pro: --reframe face)
lionstone edit clip.mp4 --intensity dynamic --aspect 9:16 --profile social --caption-style social

# Audio-only podcast → audiogram video
lionstone edit episode.wav --title "Episode 7" --profile podcast

# Course lecture: gentle edit, warm look, your LUT, captions as files only
lionstone edit lecture.mov --intensity natural --color warm --lut brand.cube --captions file

# Already have a transcript from another ASR (Whisper / WhisperX / Deepgram JSON)?
lionstone edit talk.mp4 --transcript talk.words.json

# Review loop
lionstone plan talk.mp4                      # analyze only
$EDITOR talk_lionstone/transcript.md         # delete / move lines
lionstone apply-transcript talk_lionstone/plan.json talk_lionstone/transcript.md
lionstone cuts talk_lionstone/plan.json --restore c0007
lionstone render talk_lionstone/plan.json
```

See [`claude_desktop_config.json`](claude_desktop_config.json) to use Lionstone from Claude.
