"""Regenerate styles.md and guide/index.html from src/lionstone/data/styles/styles.json.

    python tools/build_styles.py
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "src" / "lionstone" / "data" / "styles"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lionstone Style Guide</title>
<style>
:root{--bg:#0f0f10;--card:#1a1a1c;--line:#2c2c30;--fg:#f4f2ec;--muted:#a09d94;--accent:#e8b04b;--accent-fg:#1a1306}
@media (prefers-color-scheme:light){:root{--bg:#faf8f3;--card:#fff;--line:#e4dfd3;--fg:#1c1a16;--muted:#6d6a60;--accent:#c98a14;--accent-fg:#fff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:0 16px}
header{padding:40px 0 16px}
h1{margin:0 0 6px;font-size:30px;letter-spacing:-.01em}
h1 span{color:var(--accent)}
p.lead{margin:0;color:var(--muted);max-width:62ch}
h2{margin:32px 0 2px;font-size:19px}
h2 small{color:var(--accent);font-size:13px;margin-left:8px;letter-spacing:.08em}
p.blurb{margin:0 0 12px;color:var(--muted);font-size:14px}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
button.card{all:unset;box-sizing:border-box;cursor:pointer;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
button.card:hover{border-color:var(--muted)}
button.card:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button.card[aria-pressed=true]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
.code{display:inline-block;min-width:2.2em;text-align:center;background:var(--accent);color:var(--accent-fg);font-weight:700;font-size:12px;border-radius:6px;padding:1px 6px;margin-right:8px}
.nm{font-weight:600}
.ds{display:block;margin-top:4px;color:var(--muted);font-size:13px}
.presets{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.chip{all:unset;cursor:pointer;border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:13px;background:var(--card)}
.chip:hover{border-color:var(--accent)}
.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.bar{position:sticky;bottom:0;background:var(--bg);border-top:1px solid var(--line);margin-top:32px;padding:14px 0}
.bar label{font-size:12px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.out{display:flex;gap:8px;margin:4px 0 10px}
.out code{flex:1;overflow-x:auto;white-space:nowrap;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:13px}
.btn{all:unset;cursor:pointer;background:var(--accent);color:var(--accent-fg);font-weight:600;border-radius:8px;padding:8px 14px;font-size:14px}
.btn:focus-visible{outline:2px solid var(--fg);outline-offset:2px}
.btn.alt{background:var(--card);color:var(--fg);border:1px solid var(--line)}
footer{padding:20px 0 40px;color:var(--muted);font-size:13px}
@media (prefers-reduced-motion:no-preference){button.card,.chip{transition:border-color .15s}}
</style>
</head>
<body>
<div class="wrap">
<header>
<h1><span>Lionstone</span> Style Guide</h1>
<p class="lead">__INTRO__</p>
<div class="presets" id="presets" aria-label="Starting points"></div>
</header>
<main id="groups"></main>
<div class="bar">
<label for="codes">Your codes</label>
<div class="out"><code id="codes">none selected</code><button class="btn alt" id="copyCodes">Copy codes</button></div>
<label for="cmd">Command</label>
<div class="out"><code id="cmd">lionstone edit video.mp4</code><button class="btn" id="copyCmd">Copy prompt</button></div>
</div>
<footer>Lionstone Styles are free and open source (Apache-2.0). <code>lionstone styles --cmd O4 W3 A3</code> prints the same command in your terminal.</footer>
</div>
<script>
const DATA = __DATA__;
const sel = {};
const $ = (id) => document.getElementById(id);
function render() {
  const root = $("groups"); root.textContent = "";
  for (const g of DATA.groups) {
    const h = document.createElement("h2"); h.textContent = g.name;
    const s = document.createElement("small"); s.textContent = g.id; h.appendChild(s);
    const b = document.createElement("p"); b.className = "blurb"; b.textContent = g.blurb;
    const grid = document.createElement("div"); grid.className = "grid";
    for (const st of g.styles) {
      const c = document.createElement("button"); c.className = "card"; c.type = "button";
      c.setAttribute("aria-pressed", sel[g.id] === st.code ? "true" : "false");
      const code = document.createElement("span"); code.className = "code"; code.textContent = st.code;
      const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = st.name;
      const ds = document.createElement("span"); ds.className = "ds"; ds.textContent = st.desc;
      c.append(code, nm, ds);
      c.addEventListener("click", () => { if (sel[g.id] === st.code) delete sel[g.id]; else sel[g.id] = st.code; update(); });
      grid.appendChild(c);
    }
    root.append(h, b, grid);
  }
}
function update() {
  render();
  const codes = DATA.groups.map((g) => sel[g.id]).filter(Boolean);
  const args = [];
  for (const g of DATA.groups) { const st = g.styles.find((x) => x.code === sel[g.id]); if (st) args.push(...st.args); }
  $("codes").textContent = codes.length ? codes.join(" ") : "none selected";
  $("cmd").textContent = ["lionstone edit video.mp4", ...args].join(" ");
}
function copy(text, btn) {
  const done = () => { const t = btn.textContent; btn.textContent = "Copied"; setTimeout(() => (btn.textContent = t), 1200); };
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => {}); else done();
}
$("copyCodes").addEventListener("click", (e) => copy($("codes").textContent, e.target));
$("copyCmd").addEventListener("click", (e) => copy("Edit my video with these Lionstone styles: " + $("codes").textContent + ". Command: " + $("cmd").textContent, e.target));
for (const p of DATA.presets) {
  const b = document.createElement("button"); b.className = "chip"; b.type = "button"; b.title = p.why; b.textContent = p.name + " - " + p.codes.join(" ");
  b.addEventListener("click", () => { for (const k of Object.keys(sel)) delete sel[k]; for (const c of p.codes) sel[c[0]] = c; update(); });
  $("presets").appendChild(b);
}
update();
</script>
</body>
</html>
"""


def build() -> None:
    data = json.loads((DATA / "styles.json").read_text(encoding="utf-8"))
    lines = ["# Lionstone Style Reference", "", data["intro"], ""]
    for g in data["groups"]:
        lines += [f"## {g['id']} - {g['name']}", "", g["blurb"], ""]
        for s in g["styles"]:
            args = " ".join(s["args"]) or "(no options)"
            lines.append(f"- **{s['code']} {s['name']}**: {s['desc']} `{args}`")
        lines.append("")
    lines += ["## Starting points", ""]
    for p in data["presets"]:
        lines.append(f"- **{p['name']}**: `{' '.join(p['codes'])}` - {p['why']}")
    (DATA / "styles.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    safe = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = PAGE.replace("__DATA__", safe).replace("__INTRO__", data["intro"].replace("`", ""))
    (DATA / "guide").mkdir(exist_ok=True)
    (DATA / "guide" / "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build()
