# Plugins

```toml
# your package's pyproject.toml
[project.entry-points."lionstone.plugins"]
myplugin = "my_package.plugin:register"
```

```python
def register(reg):
    reg.add_effect_dir("path/to/catalog")                 # JSON effect definitions
    reg.add_command("hello", "say hi", configure=lambda p: p.add_argument("name"),
                    run=lambda a: print(f"hi {a.name}") or 0)
    reg.add_exporter("otio", lambda plan, outdir: ...)
    reg.plan_hooks.append(lambda plan, ctx: ...)          # ctx: options, analysis, catalog, outdir
    reg.qa_hooks.append(lambda report, ctx: ...)          # add QACheck / QAIssue
    reg.autofix_hooks.append(lambda report, ctx: False)   # return True if you changed something
    reg.reframers["myframe"] = lambda *, plan, info, W, H, workdir: "crop=…"
```

Other extension points: `lionstone.effects.ffmpeg_fx.register_builder(id, fn)`,
`lionstone.captions.register_style(...)`, `lionstone.captions.register_dialogue(name, fn)`.

Plugin options on the CLI: `lionstone edit in.mp4 --x key=value` → `options.extras["key"]`.

A plugin that raises during `register` is reported by `lionstone doctor` and never breaks the core.
