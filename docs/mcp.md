# MCP server

```bash
pip install "lionstone[mcp,whisper] @ git+https://github.com/ismailarslantas/lionstone"
lionstone mcp   # stdio
```

**Claude Desktop** (`claude_desktop_config.json`) · **Claude Code** (`claude mcp add lionstone -- lionstone mcp`) · **Cursor** (`.cursor/mcp.json`):

```json
{ "mcpServers": { "lionstone": { "command": "lionstone", "args": ["mcp"] } } }
```

| Tool | Purpose |
|---|---|
| `inspect_media(path)` | metadata + validation warnings |
| `plan_edit(path, intensity, profile, title, speakers, chapters, language, no_asr)` | analyze → plan summary with every cut and reason |
| `get_transcript(plan_path)` | editable transcript |
| `edit_transcript(plan_path, transcript_markdown)` | cut / reorder by text |
| `restore_cuts(plan_path, cut_ids, restore)` | undo / redo cuts |
| `render_plan(plan_path, captions, aspect)` | render + QA → `deliverable` + QA markdown |
| `list_effects(category, style, tier)` | effect catalog with lock state |

Example prompt: *"Plan an edit of ~/Videos/ep12.mp4 in Turkish, natural intensity. Show me cuts under 0.7 confidence, restore the ones that remove meaning, then render for YouTube and summarise the QA."*
