# `plan.json` reference

```jsonc
{
  "version": "1.0",
  "source": "/abs/path/podcast.mp4",
  "duration": 5412.3,               // source seconds
  "intensity": "balanced",
  "segments": [                     // KEPT material, in output order
    {"id": "s0000", "start": 1.02, "end": 14.88, "source": "main", "text": "Welcome back…"}
  ],
  "cuts": [                         // REMOVED material (source timeline)
    {"id": "c0003", "start": 21.40, "end": 21.71, "kind": "filler",
     "reason": "filler \"um,\"", "confidence": 0.95, "enabled": true}
  ],
  "graphics": [                     // output timeline
    {"id": "g000", "effect": "F01", "at": 0.2, "duration": 4.8, "text": "Episode 12",
     "subtext": "", "params": {}, "layer": "titles", "reason": "video opening"}
  ],
  "words": [{"text": "Welcome", "start": 1.10, "end": 1.42, "confidence": 0.98, "speaker": null}],
  "audio_profile": "youtube",
  "color": {"preset": "natural", "lut": null},
  "meta": {"options": {…}, "sentences": […], "asr_note": "…"}
}
```

* `kind`: `silence` · `filler` · `repeat` · `false_start` · `transcript` · `manual` · `mixed`
* Set `"enabled": false` (or `lionstone cuts plan.json --restore ID`) to bring material back.
* Segments are derived from cuts: `segments = timeline − enabled cuts` (unless reordered by `transcript.md`).
* You can hand-edit the file and run `lionstone render plan.json`.

JSON Schema for effects: [`schemas/effect.schema.json`](../schemas/effect.schema.json).
