# Writing an effect

An effect = **definition** (JSON) + **Remotion component** (reference look) + optional **FFmpeg builder** (zero-dependency renderer).

## 1. Definition — `effects/catalog/free/F07-my-title.json`

```json
{
  "id": "F07", "name": "My Title", "category": "title", "tier": "free",
  "style": ["minimal"], "use": ["chapter"],
  "description": "One sentence a user understands.",
  "duration": {"enter": 0.8, "hold": 3.0, "exit": 0.5},
  "parameters": {"fontSize": 0.07},
  "constraints": {"minDuration": 2.0, "maxDuration": 8.0, "safeArea": true, "minFontPx": 28},
  "renderEngine": "remotion", "fallbackEngine": "ffmpeg", "composition": "MyTitle",
  "supportsPreview": true, "fallback": "simple_fade",
  "license": {"code": "Apache-2.0", "assets": "OFL fonts only"}
}
```

Validated by `schemas/effect.schema.json` and `lionstone.effects.catalog.validate`.

## 2. Remotion component — `remotion/src/effects/MyTitle.tsx`

Use `useEnvelope(enter, hold, exit)` from `lib/timing.ts`, render inside `<Frame p={p}>`, keep text in the title-safe area, and register it in `Root.tsx` with the same id as `"composition"`. Preview with `npm run studio`.

## 3. FFmpeg builder (optional)

```python
from lionstone.effects.ffmpeg_fx import register_builder, envelope, _drawtext, _timing

def f07_my_title(fx, ev, inp, ctx):
    t0, t_in, t1, t_out = _timing(fx, ev)
    out = ctx.label()
    size = int(ctx.height * fx.parameters["fontSize"])
    return [_drawtext(ctx, inp, out, ev.text, size, "(w-tw)/2", "(h-th)/2",
                      envelope(t0, t_in, t1, t_out))], out

register_builder("F07", f07_my_title)
```

## 4. Check it

```bash
lionstone effects show F07
lionstone effects preview F07 --text "Hello" --gif
pytest tests/test_effects.py
```

### Rules every effect must respect
* Never animate outside its own event window.
* Readable: minimum on-screen time ≥ reading time; minimum font size in `constraints.minFontPx`.
* Text stays in the safe area; captions are a separate layer.
* Declare a `fallback`. Only ship fonts/assets whose license allows redistribution.
