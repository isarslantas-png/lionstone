# QA checks

| Check | Group | Severity if it fails | Auto-fix |
|---|---|---|---|
| `decode_full` — every packet decodes | technical | critical (blocks delivery) | — |
| `streams` — audio present | technical | critical | — |
| `av_length` — video/audio length match (≤ 2 frames) | technical | high / critical | — |
| `plan_duration` — output matches plan | technical | medium | — |
| `format` — resolution & frame rate on target | technical | medium | — |
| `black_frames` — unexpected black (intentional cards excluded) | technical | medium / high | — |
| `frozen_frames` — static picture > 5 s | technical | medium | — |
| `loudness` · `true_peak` — EBU R128 vs profile | technical | high | ✅ re-normalise (video stream copied) |
| `join_clicks` — every join inspected for discontinuities | technical | medium | — |
| `word_integrity` — no cut clips a kept word | editorial | high | ✅ widen cut boundaries, re-render |
| `low_confidence_cuts` — cuts a human should review | editorial | low | — |
| `choppiness` — many sub-0.45 s fragments | editorial | medium | — |
| `caption_timing` — cues in range, no overlaps | editorial | high | — |
| `graphics_rules` — overlap, readability, inside video | editorial | medium | — |
| `faces_covered` — graphics over faces | editorial | medium | Pro (OpenCV) |
| `camera_choice` — camera shows the speaker | editorial | — | Pro multicam |

Delivery is blocked only by `critical`. `high` issues trigger up to two fix → re-render → re-check rounds. Everything else is reported in `qa.md` for a human.

**A skipped check is never counted as passed.** The report lists why it was skipped (no transcript, single camera, missing model…).
