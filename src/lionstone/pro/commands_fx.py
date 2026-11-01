"""CLI for the creative feature engine: `lionstone fx …`, `preset …`, `brand …`, `team …`."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .features import agent as agent_mod
from .features import catalog as cat_mod
from .features import studio
from .features import timeline as tl
from .features.compile import compile_plan, is_stale
from .features.entitlements import EntitlementError, current
from .features.params import ParamError, parse_cli


def load_catalog(ent=None):
    ent = ent or current()
    try:
        extra = studio.custom_presets(ent)
    except Exception:
        extra = []
    return cat_mod.Catalog(extra=extra)


def _plan(path):
    from lionstone.models import EditPlan
    return EditPlan.load(path)


def _anchor(a, plan) -> list[dict]:
    if a.globally:
        return [{"type": "global"}]
    if a.segment is not None:
        return [tl.segment_anchor(plan, a.segment)]
    if a.join is not None:
        return [tl.join_anchor(plan, a.join)]
    if a.all_joins:
        return [tl.join_anchor(plan, i) for i in range(len(plan.segments) - 1)]
    if a.source:
        s, e = (float(x) for x in a.source.split("-"))
        return [{"type": "source", "start": s, "end": e}]
    if a.output:
        s, e = (float(x) for x in a.output.split("-"))
        return [{"type": "output", "start": s, "end": e}]
    return [{"type": "global"}]


def _add_anchor_args(p):
    g = p.add_argument_group("where")
    g.add_argument("--global", dest="globally", action="store_true", help="whole video")
    g.add_argument("--segment", type=int, help="kept segment index (see `fx segments`)")
    g.add_argument("--join", type=int, help="cut between segment N and N+1 (transitions)")
    g.add_argument("--all-joins", action="store_true", help="every cut (transitions)")
    g.add_argument("--source", metavar="START-END", help="source-time range in seconds")
    g.add_argument("--output", metavar="START-END", help="output-time range (text, CTA)")


# ======================================================================= fx
def _cfg_fx(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="fx_cmd", required=True)
    s = sub.add_parser("list", help="browse the catalog")
    for k in ("kind", "category", "tier", "style", "cost", "status", "search"):
        s.add_argument(f"--{k}")
    s.add_argument("--favorites", action="store_true")
    s.add_argument("--recent", action="store_true")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("show", help="preset card with parameters and limitations")
    s.add_argument("id")
    s = sub.add_parser("fav", help="toggle favourite")
    s.add_argument("id")
    s = sub.add_parser("preview", help="real low-res preview (same renderer as export)")
    s.add_argument("id")
    s.add_argument("--input", help="your clip (default: test pattern)")
    s.add_argument("--start", type=float, default=0.0)
    s.add_argument("--seconds", type=float, default=4.0)
    s.add_argument("--param", action="append", default=[], metavar="K=V")
    s.add_argument("--before-after", action="store_true")
    s.add_argument("--gif", action="store_true")
    s.add_argument("--width", type=int, default=640)
    s.add_argument("-o", "--output")
    s = sub.add_parser("segments", help="list kept segments and cuts (indices for --segment/--join)")
    s.add_argument("plan")
    s = sub.add_parser("apply", help="add a preset to a plan")
    s.add_argument("plan")
    s.add_argument("id")
    s.add_argument("--param", action="append", default=[], metavar="K=V")
    s.add_argument("--keyframes", metavar="JSON", help='{"zoom":[{"t":0,"v":1},{"t":2,"v":1.2}]}')
    _add_anchor_args(s)
    s = sub.add_parser("text", help="add a text / CTA / lower third preset")
    s.add_argument("plan")
    s.add_argument("id")
    s.add_argument("--text", required=True)
    s.add_argument("--subtext", default="")
    s.add_argument("--at", type=float, required=True, help="output seconds")
    s.add_argument("--duration", type=float, default=4.0)
    s.add_argument("--param", action="append", default=[], metavar="K=V")
    s = sub.add_parser("applied", help="list instances on a plan")
    s.add_argument("plan")
    s = sub.add_parser("remove", help="remove an instance")
    s.add_argument("plan")
    s.add_argument("fx_id")
    s = sub.add_parser("set", help="change parameters / enable / disable an instance")
    s.add_argument("plan")
    s.add_argument("fx_id")
    s.add_argument("--param", action="append", default=[], metavar="K=V")
    s.add_argument("--enable", action="store_true")
    s.add_argument("--disable", action="store_true")
    s = sub.add_parser("auto", help="agent: propose (and apply) looks, effects, transitions")
    s.add_argument("plan")
    s.add_argument("--content", default="podcast", choices=agent_mod.CONTENT)
    s.add_argument("--style", default="minimal", choices=agent_mod.STYLES)
    s.add_argument("--intensity", default="balanced", choices=list(agent_mod.INTENSITY))
    s.add_argument("--platform", default="youtube")
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("compile", help="compile instances into the render plan")
    s.add_argument("plan")
    s = sub.add_parser("render", help="compile + render + QA (use after any edit)")
    s.add_argument("plan")
    s.add_argument("-o", "--output")
    s.add_argument("--fast", action="store_true")
    s.add_argument("--renderer", default="auto", choices=["auto", "ffmpeg", "remotion"])
    s.add_argument("--profile", help="shared QA/export profile (Studio)")
    s = sub.add_parser("batch", help="apply one preset to many plans")
    s.add_argument("id")
    s.add_argument("plans", nargs="+")
    s.add_argument("--anchor", default="global", choices=["global", "all-joins"])
    s.add_argument("--param", action="append", default=[], metavar="K=V")
    s.add_argument("--team", action="store_true", help="log as a team batch (Studio)")
    s = sub.add_parser("catalog-doc", help="write the catalog as Markdown")
    s.add_argument("-o", "--output", default="docs/fx-catalog.md")
    s = sub.add_parser("showcase", help="6.4 s vertical one-command reel for an effect "
                                        "(Reel FX, see docs/reel-fx.md)")
    s.add_argument("id")
    s.add_argument("clip", help="talking-head clip (any aspect; cropped to 9:16)")
    s.add_argument("-o", "--output")
    s.add_argument("--start", type=float, default=0.0, help="start time in the clip (s)")
    s.add_argument("--param", action="append", default=[], metavar="K=V")


def _list(a, cat, ent):
    ids = None
    if a.favorites:
        ids = cat_mod.favorites()
    if a.recent:
        ids = set(cat_mod.recents())
    items = cat.search(kind=a.kind, category=a.category, tier=a.tier, style=a.style,
                       cost=a.cost, status=a.status, text=a.search, ids=ids)
    if a.json:
        print(json.dumps([p.card() for p in items], indent=1, ensure_ascii=False))
        return 0
    fav = cat_mod.favorites()
    for p in items:
        lock = "" if ent.allows(p.tier) else " 🔒"
        star = "★" if p.id in fav else " "
        st = {"ready": "", "partial": " (partial)", "planned": " (planned)"}[p.implementationStatus]
        print(f"{star} {p.kind:10} {p.category:15} {p.tier:6} {p.performanceCost:6} "
              f"{p.id.replace('lionstone.', ''):26} {p.name}{st}{lock}")
    print(f"\n{len(items)} presets · plan: {ent.level} · 🔒 = needs a higher plan "
          "(previews still work)")
    return 0


def _show(a, cat, ent):
    p = cat.get(a.id)
    d = p.card() | {"version": p.version, "parameters": p.parameters, "license": p.license,
                    "styles": p.styles, "renderers": p.supportedRenderers,
                    "unlocked": ent.allows(p.tier)}
    print(json.dumps(d, indent=2, ensure_ascii=False))
    return 0


def _apply(a, cat, ent):
    plan = _plan(a.plan)
    p = cat.get(a.id)
    if not p.usable:
        print(f"{p.name} is {p.implementationStatus}: {'; '.join(p.limitations)}")
        return 1
    ent.require(p.tier, p.name)
    params = parse_cli(a.param)
    if a.keyframes:
        params.update(json.loads(a.keyframes))
    from .features.params import resolve
    resolve(p.parameters, params)  # validate now, fail early
    anchors = _anchor(a, plan)
    if p.kind == "transition" and anchors[0]["type"] != "join":
        print("transitions need --join N or --all-joins")
        return 1
    for anc in anchors:
        inst = tl.add(plan, tl.FxInstance(preset=p.id, version=p.version, anchor=anc,
                                          params=params))
        print(f"+ {inst.id}  {p.name}  {anc}")
    plan.save(a.plan)
    cat_mod.touch_recent(p.id)
    print("Render with: lionstone fx render", a.plan)
    return 0


def _text(a, cat, ent):
    plan = _plan(a.plan)
    p = cat.get(a.id)
    if p.kind != "text":
        print(f"{p.name} is not a text preset")
        return 1
    ent.require(p.tier, p.name)
    params = {"text": a.text, "subtext": a.subtext, "duration": a.duration, **parse_cli(a.param)}
    from .features.params import resolve
    resolve(p.parameters, params)
    inst = tl.add(plan, tl.FxInstance(preset=p.id, version=p.version,
                                      anchor={"type": "output", "start": a.at,
                                              "end": a.at + a.duration}, params=params))
    plan.save(a.plan)
    print(f"+ {inst.id}  {p.name} at {a.at:.1f}s")
    return 0


def _applied(a, cat, ent):
    plan = _plan(a.plan)
    comp = (plan.meta.get("lionstone_fx") or {}).get("compiled") or {}
    for i in tl.instances(plan):
        print(f"{i.id:12} {'on ' if i.enabled else 'off'} {i.status:9} {i.created_by:9} "
              f"{i.preset.replace('lionstone.', ''):24} {i.anchor.get('type'):7} {i.reason}")
    print(f"\ncompiled: {comp.get('fingerprint', '—')} · stale: {is_stale(plan)}")
    return 0


def _set(a, cat, ent):
    plan = _plan(a.plan)
    items = tl.instances(plan)
    inst = next((i for i in items if i.id == a.fx_id), None)
    if not inst:
        print("no such instance")
        return 1
    if inst.created_by == "brand-kit" and "locked" in inst.reason:
        team = studio.load_team(studio.team_root())
        studio.require(team, ent, "lock", "Changing a locked brand-kit instance")
    p = cat.get(inst.preset)
    if a.param:
        from .features.params import resolve
        new = {**inst.params, **parse_cli(a.param)}
        resolve(p.parameters, new)
        inst.params = new
    if a.enable:
        inst.enabled = True
    if a.disable:
        inst.enabled = False
    tl.save_instances(plan, items)
    plan.save(a.plan)
    print(f"updated {inst.id}")
    return 0


def _remove(a, cat, ent):
    plan = _plan(a.plan)
    inst = next((i for i in tl.instances(plan) if i.id == a.fx_id), None)
    if inst and inst.created_by == "brand-kit" and "locked" in inst.reason:
        team = studio.load_team(studio.team_root())
        studio.require(team, ent, "lock", "Removing a locked brand-kit instance")
    ok = tl.remove(plan, a.fx_id)
    plan.save(a.plan)
    print("removed" if ok else "no such instance")
    return 0 if ok else 1


def _segments(a, cat, ent):
    plan = _plan(a.plan)
    acc = 0.0
    for i, s in enumerate(plan.segments):
        print(f"segment {i:3}  out {acc:7.2f}s  src {s.start:8.2f}–{s.end:<8.2f} {s.source:6} "
              f"{s.text[:50]}")
        acc += s.duration
        if i < len(plan.segments) - 1:
            gap = plan.segments[i + 1].start - s.end
            print(f"   join {i:3} at {acc:7.2f}s  (removed {gap:.2f}s)")
    return 0


def _auto(a, cat, ent):
    plan = _plan(a.plan)
    pr = agent_mod.propose(plan, cat, ent, content=a.content, style=a.style,
                           intensity=a.intensity, platform=a.platform)
    for name, where, why in pr.table():
        print(f"  {name:24} {where:8} {why}")
    for n in pr.notes:
        print(f"  note: {n}")
    if a.dry_run:
        print("\n(dry run — nothing changed)")
        return 0
    n = agent_mod.apply(plan, pr, cat)
    plan.save(a.plan)
    print(f"\n{n} decisions applied (replacing previous agent decisions). "
          f"Undo any with `lionstone fx remove`. Render: lionstone fx render {a.plan}")
    return 0


def _compile(a, cat, ent):
    plan = _plan(a.plan)
    rep = compile_plan(plan, cat, ent)
    plan.save(a.plan)
    for x in rep.applied:
        print(f"  ✓ {x['preset'].replace('lionstone.', '')}  {x.get('windows') or x.get('at', '')}")
    for x in rep.skipped:
        print(f"  ✗ {x['preset'].replace('lionstone.', '')}: {x['reason']}")
    for n in rep.notes:
        print(f"  note: {n}")
    print(f"compiled {rep.fingerprint} · {rep.filter_chars} chars of filtergraph")
    return 0 if rep.ok else 2


def _render(a, cat, ent):
    from lionstone.cli import _catalog as core_catalog
    from lionstone.pipeline import options_from_meta, render_and_verify
    from lionstone.render import RenderOptions
    plan = _plan(a.plan)
    rep = compile_plan(plan, cat, ent)
    if a.profile:
        prof = _load_profile(a.profile, ent)
        plan.audio_profile = prof.get("loudness", plan.audio_profile)
        plan.meta.setdefault("options", {}).update(
            {k: v for k, v in prof.items() if k in ("caption_style", "aspect")})
    plan.save(a.plan)
    for x in rep.skipped:
        print(f"  ✗ {x['preset']}: {x['reason']}")
    opts = options_from_meta(plan)
    ro = RenderOptions(aspect=opts.aspect, captions=opts.captions, caption_style=opts.caption_style,
                       denoise=opts.denoise, accent=opts.accent, font=opts.font,
                       preset="veryfast" if a.fast else "medium", renderer=a.renderer)
    outdir = Path(a.output).parent if a.output else Path(a.plan).parent
    name = Path(a.output).name if a.output else Path(plan.source).stem + ".edit.mp4"
    res, report = render_and_verify(plan, outdir, name, ro, catalog=core_catalog())
    return 0 if report.deliverable else 2


def _load_profile(name, ent):
    root = studio.team_root()
    team = studio.load_team(root)
    studio.require(team, ent, "use", "Shared QA/export profiles")
    return studio.Store(root, f"team:{team.id}").load("profile", name)


def _preview(a, cat, ent):
    from .features.preview import render_preview
    out = Path(a.output or f"preview-{a.id.replace('lionstone.', '')}.mp4")
    r = render_preview(a.id, out, cat, ent, input_path=a.input, start=a.start, seconds=a.seconds,
                       params=parse_cli(a.param), width=a.width, before_after=a.before_after,
                       gif=a.gif)
    cat_mod.touch_recent(cat.get(a.id).id)
    print(f"Preview ({r['width']}px, low-res) → {r['video']}" + (f"\n          {r['gif']}"
                                                                   if r.get("gif") else ""))
    for n in r["notes"]:
        print(f"  note: {n}")
    return 0


def _batch(a, cat, ent):
    for line in studio.batch_apply(a.plans, a.id, cat, ent, anchor=a.anchor,
                                   params=parse_cli(a.param), team_log=a.team):
        print(line)
    return 0


def _showcase(a, cat, ent):
    from .features.showcase import make_showcase
    out = make_showcase(a.id, a.clip, a.output or f"{a.id.replace('lionstone.', '')}-reel.mp4",
                        start=a.start, params=parse_cli(a.param), check_entitlement=False)
    print(f"Showcase reel (1080x1920, 6.4 s) → {out}")
    return 0


def _catalog_doc(a, cat, ent):
    lines = ["# Lionstone Pro / Studio — creative catalog", "",
             "Generated by `lionstone fx catalog-doc`. **ready** = preview + final render "
             "implemented and tested · **partial** = renders with documented limits · "
             "**planned** = roadmap only (can't be applied).", ""]
    for kind in cat_mod.KINDS:
        items = cat.search(kind=kind)
        if not items:
            continue
        lines += [f"## {kind.title()}s ({len(items)})", "",
                  "| Id | Name | Category | Tier | Status | Cost | Notes |", "|---|---|---|---|---|---|---|"]
        for p in items:
            note = "; ".join(p.limitations) or p.description
            lines.append(f"| `{p.id.replace('lionstone.', '')}` | {p.name} | {p.category} | "
                         f"{p.tier} | {p.implementationStatus} | {p.performanceCost} | "
                         f"{note.replace('|', '/')} |")
        lines.append("")
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    Path(a.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"→ {a.output}")
    return 0


FX = {"list": _list, "show": _show, "apply": _apply, "text": _text, "applied": _applied,
      "set": _set, "remove": _remove, "segments": _segments, "auto": _auto,
      "compile": _compile, "render": _render, "preview": _preview, "batch": _batch,
      "catalog-doc": _catalog_doc, "showcase": _showcase,
      "fav": lambda a, c, e: print("★ added" if cat_mod.toggle_favorite(c.get(a.id).id)
                                   else "removed") or 0}


def _run_fx(a) -> int:
    ent = current()
    try:
        return FX[a.fx_cmd](a, load_catalog(ent), ent) or 0
    except (EntitlementError, studio.StudioError) as e:
        print(f"🔒 {e}", file=sys.stderr)
        return 3
    except (ParamError, cat_mod.CatalogError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# ======================================================================= preset
def _cfg_preset(p):
    sub = p.add_subparsers(dest="preset_cmd", required=True)
    s = sub.add_parser("save", help="save a custom preset (Pro: personal · Studio: --team)")
    s.add_argument("name")
    s.add_argument("--from", dest="base", required=True)
    s.add_argument("--param", action="append", default=[], metavar="K=V")
    s.add_argument("--team", action="store_true")
    s.add_argument("--locked", action="store_true", help="company preset (admins only)")
    s.add_argument("--note", default="")
    s = sub.add_parser("history", help="revision history")
    s.add_argument("id")
    s.add_argument("--team", action="store_true")
    s = sub.add_parser("revert", help="restore an older revision as a new one")
    s.add_argument("id")
    s.add_argument("revision", type=int)
    s.add_argument("--team", action="store_true")
    sub.add_parser("list", help="your personal and team presets")


def _run_preset(a) -> int:
    ent = current()
    cat = load_catalog(ent)
    try:
        if a.preset_cmd == "save":
            fn = studio.save_team_preset if a.team else studio.save_personal_preset
            kw = {"locked": a.locked} if a.team else {}
            pid, rev = fn(cat, a.base, a.name, parse_cli(a.param), ent, note=a.note, **kw)
            print(f"saved {pid} (revision {rev})")
        elif a.preset_cmd == "list":
            for d in studio.custom_presets(ent):
                print(f"{d['id']:32} based on {d['base']:32} tier {d['tier']}")
        else:
            store = (studio.Store(studio.team_root(), "team") if a.team
                     else studio.Store(studio.personal_root(), "personal"))
            if a.team:
                studio.require(studio.load_team(studio.team_root()), ent, "use", "Team history")
            if a.preset_cmd == "history":
                for h in store.history("preset", a.id):
                    print(f"r{h['revision']:<3} {h['at']}  {h['author']:28} {h['note']}  {h['sha']}")
            else:
                d = store.load("preset", a.id, a.revision)
                if a.team:
                    team = studio.load_team(studio.team_root())
                    studio.require(team, ent, "lock" if d.get("locked") else "create_preset",
                                   "Reverting team presets")
                else:
                    ent.require("pro", "Personal preset history")
                rev = store.save("preset", a.id, d, ent.user, f"revert to r{a.revision}")
                print(f"restored r{a.revision} as r{rev}")
        return 0
    except (EntitlementError, studio.StudioError) as e:
        print(f"🔒 {e}", file=sys.stderr)
        return 3
    except (ParamError, cat_mod.CatalogError, FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# ======================================================================= brand
def _cfg_brand(p):
    sub = p.add_subparsers(dest="brand_cmd", required=True)
    s = sub.add_parser("create", help="create / update a brand kit from a JSON file")
    s.add_argument("file", help="kit JSON (see docs/studio.md)")
    s.add_argument("--team", action="store_true")
    s.add_argument("--note", default="")
    s = sub.add_parser("show")
    s.add_argument("name")
    s = sub.add_parser("apply", help="apply a brand kit to a plan")
    s.add_argument("plan")
    s.add_argument("name")
    s = sub.add_parser("history")
    s.add_argument("name")
    s.add_argument("--team", action="store_true")


def _run_brand(a) -> int:
    ent = current()
    try:
        if a.brand_cmd == "create":
            d = json.loads(Path(a.file).read_text(encoding="utf-8"))
            kit = studio.BrandKit(**{k: v for k, v in d.items()
                                     if k in studio.BrandKit.__dataclass_fields__})
            for p in kit.validate():
                print(f"  ! {p}")
            rev = studio.save_kit(kit, ent, "team" if a.team else "personal", a.note)
            print(f"saved kit {kit.name!r} revision {rev}")
        elif a.brand_cmd == "show":
            kit, scope = studio.load_kit(a.name, ent)
            print(json.dumps({"scope": scope, **asdict(kit)}, indent=2, ensure_ascii=False))
        elif a.brand_cmd == "apply":
            plan = _plan(a.plan)
            kit, scope = studio.load_kit(a.name, ent)
            for n in studio.apply_kit(plan, kit, load_catalog(ent), ent, scope=scope):
                print(f"  note: {n}")
            plan.save(a.plan)
            print(f"applied {kit.name!r} ({scope}). Render: lionstone fx render {a.plan}")
        else:
            root = studio.team_root() if a.team else studio.personal_root()
            for h in studio.Store(root, "x").history("kit", a.name):
                print(f"r{h['revision']:<3} {h['at']}  {h['author']:28} {h['note']}")
        return 0
    except (EntitlementError, studio.StudioError) as e:
        print(f"🔒 {e}", file=sys.stderr)
        return 3
    except (FileNotFoundError, ValueError, TypeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


# ======================================================================= team
def _cfg_team(p):
    sub = p.add_subparsers(dest="team_cmd", required=True)
    s = sub.add_parser("init", help="create a team workspace in $LIONSTONE_STUDIO_DIR")
    s.add_argument("name")
    s = sub.add_parser("member", help="add / change / remove a member")
    s.add_argument("email")
    s.add_argument("role", choices=["viewer", "editor", "admin", "remove"])
    sub.add_parser("show")
    s = sub.add_parser("profile", help="save a shared QA/export profile")
    s.add_argument("name")
    s.add_argument("--loudness", default="youtube")
    s.add_argument("--caption-style", default="clean")
    s.add_argument("--aspect")


def _run_team(a) -> int:
    ent = current()
    root = studio.team_root()
    try:
        if not root:
            raise studio.StudioError("set LIONSTONE_STUDIO_DIR to the shared team folder")
        if a.team_cmd == "init":
            t = studio.init_team(root, a.name, ent)
            print(f"team {t.name!r} ({t.id}) created in {root}; owner {t.owner}")
        elif a.team_cmd == "member":
            t = studio.set_member(studio.load_team(root), root, ent, a.email,
                                  None if a.role == "remove" else a.role)
            print(json.dumps(t.members, indent=2))
        elif a.team_cmd == "profile":
            team = studio.load_team(root)
            studio.require(team, ent, "publish", "Shared export profiles")
            rev = studio.Store(root, f"team:{team.id}").save(
                "profile", a.name, {"loudness": a.loudness, "caption_style": a.caption_style,
                                    **({"aspect": a.aspect} if a.aspect else {})}, ent.user)
            print(f"profile {a.name!r} r{rev}")
        else:
            t = studio.load_team(root)
            print(json.dumps({"id": t.id, "name": t.name, "owner": t.owner,
                              "members": t.members, "you": t.role(ent.user), "as": ent.user},
                             indent=2))
        return 0
    except (EntitlementError, studio.StudioError) as e:
        print(f"🔒 {e}", file=sys.stderr)
        return 3


def register(reg) -> None:
    reg.add_command("fx", "[Pro/Studio] effects, transitions, looks, motion, text — catalog, "
                    "preview, apply, auto, render", _cfg_fx, _run_fx)
    reg.add_command("preset", "[Pro/Studio] custom presets with version history",
                    _cfg_preset, _run_preset)
    reg.add_command("brand", "[Pro/Studio] brand kits", _cfg_brand, _run_brand)
    reg.add_command("team", "[Studio] team workspace, roles, shared profiles",
                    _cfg_team, _run_team)
