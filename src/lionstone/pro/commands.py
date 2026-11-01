"""CLI commands that used to be Lionstone Pro. Free and open."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _cfg_whoami(p: argparse.ArgumentParser) -> None:
    p.add_argument("email", nargs="?", help="your email; team roles follow it")
    p.add_argument("--clear", action="store_true", help="forget this computer's email")


def _run_whoami(a) -> int:
    """Show or set the email this computer works as (team roles follow it)."""
    from . import identity
    try:
        if a.clear:
            identity.set_member_email(None)
        elif a.email:
            identity.set_member_email(a.email)
    except identity.IdentityError as e:
        print(f"❌ {e}")
        return 1
    email = identity.member_email()
    if not email:
        print("No email set: lionstone whoami your@email.com")
        return 0
    src = "LIONSTONE_USER" if os.environ.get("LIONSTONE_USER") else "this computer"
    print(f"You work as {email} (from {src}).")
    return 0


# --- multicam ------------------------------------------------------------------------
def _pairs(values: list[str]) -> dict[str, str]:
    out = {}
    for v in values:
        k, _, path = v.partition("=")
        if not path:
            raise SystemExit(f"expected NAME=FILE, got {v!r}")
        out[k.strip()] = path.strip()
    return out


def _cfg_multicam(p: argparse.ArgumentParser) -> None:
    from lionstone.cli import _add_edit_options
    p.add_argument("--cam", action="append", required=True, metavar="SPEAKER=FILE",
                   help="close-up camera for a speaker (repeatable)")
    p.add_argument("--wide", metavar="NAME=FILE", help="wide / two-shot camera")
    p.add_argument("--mic", action="append", default=[], metavar="SPEAKER=FILE",
                   help="isolated mic per speaker (recommended)")
    p.add_argument("--min-shot", type=float, default=2.2)
    p.add_argument("-o", "--out", default="multicam_lionstone")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--plan-only", action="store_true")
    _add_edit_options(p)


def _run_multicam(a) -> int:
    from lionstone.cli import _catalog, _edit_options, _render_options
    from lionstone.ingest import probe
    from lionstone.pipeline import ASROptions, make_plan, render_and_verify

    from . import multicam as mc
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    cams = _pairs(a.cam)
    wide = _pairs([a.wide]) if a.wide else {}
    mics = _pairs(a.mic)
    master_src = next(iter(mics.values())) if mics else next(iter(cams.values()))
    print("🎥 Multicam — syncing sources to the master clock")
    syncs = []
    offsets: dict[str, float] = {}
    for name, path in {**cams, **wide}.items():
        r = mc.sync(master_src, path, name=name)
        syncs.append(r)
        offsets[name] = r.offset
        print(f"   {name:10} offset {r.offset:+.3f}s · confidence {r.confidence:.2f} · "
              f"drift {r.drift_ppm} ppm {('⚠️ ' + r.warning) if r.warning else ''}")
    mic_offsets: dict[str, float] = {}
    for name, path in mics.items():
        r = mc.sync(master_src, path, name=f"mic:{name}") if path != master_src else \
            mc.SyncResult(name, 0.0, 1.0)
        mic_offsets[name] = r.offset
        syncs.append(r)
    duration = probe(master_src).duration
    if mics:
        master = mc.mix_mics(mics, mic_offsets, outdir / "master_mix.wav", duration)
        act = mc.activity(mics, mic_offsets, duration)
    else:
        master = Path(master_src)
        act = mc.activity({k: v for k, v in cams.items()}, offsets, duration)
    print("🎙️ Speaker activity → camera timeline")
    shots = mc.camera_timeline(act, {k: k for k in cams}, next(iter(wide), None),
                               mc.SwitchRules(min_shot=a.min_shot))
    opts = _edit_options(a)
    plan = make_plan(Path(master), outdir, opts, ASROptions(
        mode="none" if a.no_asr else "auto", model=a.model, language=a.language,
        transcript=a.transcript), catalog=_catalog())
    plan.meta["sources"] = {k: {"path": str(Path(p).resolve()), "offset": offsets[k]}
                            for k, p in {**cams, **wide}.items()}
    all_cams = {**cams, **wide}
    mc.apply_timeline(plan, shots, mc.coverage(all_cams, offsets),
                      prefer=list(wide) + list(cams))
    plan.meta["multicam"] = mc.report(syncs, shots)
    plan.meta["camera_timeline"] = shots
    plan.save(outdir / "plan.json")
    mc.save_report(plan.meta["multicam"], outdir / "multicam.json")
    print(f"   {len(shots)} shots · screen time {plan.meta['multicam']['screen_time']}")
    if a.plan_only:
        return 0
    res, report = render_and_verify(plan, outdir, "multicam.edit.mp4", _render_options(a, opts),
                                    catalog=_catalog())
    return 0 if report.deliverable else 2


# --- style -----------------------------------------------------------------------------
def _cfg_style(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["learn", "show"])
    p.add_argument("files", nargs="+", help="reference videos (learn) or a profile (show)")
    p.add_argument("--name", default="my-style")
    p.add_argument("-o", "--output", default="style.json")


def _run_style(a) -> int:
    from . import style
    if a.action == "show":
        print(style.describe(style.StyleProfile.load(a.files[0])))
        return 0
    if len(a.files) > 3:
        print("Use 1–3 reference videos.")
        return 1
    prof = style.learn(a.files, a.name)
    prof.save(a.output)
    print(style.describe(prof))
    print(f"\nSaved → {a.output}\nUse:   lionstone edit input.mp4 --x style={a.output} "
          "[--x style_apply=tempo,color,audio]")
    return 0


# --- clips -------------------------------------------------------------------------------
def _cfg_clips(p: argparse.ArgumentParser) -> None:
    p.add_argument("plan", help="plan.json from `lionstone plan` / `lionstone edit`")
    p.add_argument("-n", "--count", type=int, default=5)
    p.add_argument("--min", type=float, default=18)
    p.add_argument("--max", type=float, default=60)
    p.add_argument("--aspect", default="9:16", choices=["9:16", "1:1", "4:5", "16:9"])
    p.add_argument("--reframe", default="face", choices=["face", "center"])
    p.add_argument("--hook-effect", default="P05")
    p.add_argument("--captions", default="highlight")
    p.add_argument("--llm", action="store_true", help="re-rank with Claude (ANTHROPIC_API_KEY)")
    p.add_argument("--list", action="store_true", help="only list candidates")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--renderer", choices=["auto", "ffmpeg", "remotion"], default="auto")


def _run_clips(a) -> int:
    from lionstone.cli import _catalog
    from lionstone.models import EditPlan
    from lionstone.pipeline import render_and_verify
    from lionstone.render import RenderOptions

    from . import clips
    plan = EditPlan.load(a.plan)
    if not plan.words:
        print("Clips need a transcript (run without --no-asr).")
        return 1
    cands = clips.candidates(plan, a.min, a.max)
    if a.llm:
        cands = clips.llm_rerank(cands, a.count, (plan.meta.get("options") or {}).get("language", ""))
    chosen = clips.pick(cands, a.count)
    for i, c in enumerate(chosen, 1):
        print(f"#{i}  {c.start:7.1f}s  {c.duration:5.1f}s  score {c.score:5.2f}  “{c.hook[:70]}”")
        print(f"     {' · '.join(c.reasons)}")
    if a.list or not chosen:
        return 0
    outdir = Path(a.plan).parent / "clips"
    outdir.mkdir(exist_ok=True)
    cat = _catalog()
    paths = []
    for i, c in enumerate(chosen, 1):
        sub = clips.subplan(plan, c, a.hook_effect, c.hook)
        sub.graphics[0].params["position"] = "upper"
        sub.save(outdir / f"clip_{i:02d}.plan.json")
        ro = RenderOptions(aspect=a.aspect, captions="burn", caption_style=a.captions,
                           reframe=a.reframe, preset="veryfast" if a.fast else "medium",
                           renderer=a.renderer)
        res, _ = render_and_verify(sub, outdir, f"clip_{i:02d}.mp4", ro, catalog=cat,
                                   log=lambda m: None)
        (outdir / "qa.md").rename(outdir / f"clip_{i:02d}.qa.md")
        paths.append(str(res.output))
        print(f"   → {res.output}")
    clips.write_manifest(chosen, paths, outdir / "clips.json")
    return 0


# --- export -------------------------------------------------------------------------------
def _cfg_export(p: argparse.ArgumentParser) -> None:
    p.add_argument("plan")
    p.add_argument("-o", "--out")


def _run_export(a) -> int:
    from lionstone.models import EditPlan

    from .export import export_all
    plan = EditPlan.load(a.plan)
    out = export_all(plan, Path(a.out or Path(a.plan).parent / "project"))
    for k, v in out.items():
        print(f"{k:7} → {v}")
    print("Open the .fcpxml in DaVinci Resolve / Final Cut Pro, or the .edl in Premiere Pro.")
    return 0


# --- variants -------------------------------------------------------------------------------
def _cfg_variants(p: argparse.ArgumentParser) -> None:
    from lionstone.cli import _add_edit_options
    p.add_argument("input")
    p.add_argument("-o", "--out")
    _add_edit_options(p)


VARIANTS = {
    "natural": {"intensity": "natural", "color": "natural", "title_effect": "F01"},
    "cinematic": {"intensity": "balanced", "color": "film", "title_effect": "P03",
                  "chapter_effect": "F04"},
    "dynamic": {"intensity": "dynamic", "color": "punchy", "title_effect": "P05",
                "caption_style": "highlight-landscape"},
}


def _run_variants(a) -> int:
    from dataclasses import replace

    from lionstone.cli import _catalog, _edit_options
    from lionstone.pipeline import ASROptions, make_plan
    src = Path(a.input)
    base = Path(a.out or f"{src.stem}_variants")
    base_opts = _edit_options(a)
    asr = ASROptions(mode="none" if a.no_asr else "auto", model=a.model, language=a.language,
                     transcript=a.transcript)
    rows = []
    for name, ov in VARIANTS.items():
        outdir = base / name
        outdir.mkdir(parents=True, exist_ok=True)
        # share the analysis cache between variants
        cache = base / ".lionstone"
        (outdir / ".lionstone").mkdir(exist_ok=True)
        if not (outdir / ".lionstone" / "cache").exists():
            cache.joinpath("cache").mkdir(parents=True, exist_ok=True)
            try:
                (outdir / ".lionstone" / "cache").symlink_to(cache.joinpath("cache").resolve(),
                                                             target_is_directory=True)
            except OSError:  # Windows without Developer Mode: no shared cache, just slower
                pass
        plan = make_plan(src, outdir, replace(base_opts, **ov), asr, catalog=_catalog(),
                         log=lambda m: None)
        rows.append((name, plan.output_duration, sum(1 for c in plan.cuts if c.enabled),
                     len(plan.graphics), outdir / "plan.json"))
    print(f"{'variant':10} {'length':>8} {'cuts':>5} {'graphics':>9}  plan")
    for n, d, c, g, p in rows:
        print(f"{n:10} {d:7.1f}s {c:5d} {g:9d}  {p}")
    print("\nRender the one you like: lionstone render <variant>/plan.json")
    return 0


def register_commands(reg) -> None:
    from . import styles_cmd
    reg.add_command("styles", "browse Lionstone Style codes and print the edit command",
                    styles_cmd.cfg, styles_cmd.run)
    reg.add_command("whoami", "show or set the email team roles follow",
                    _cfg_whoami, _run_whoami)
    reg.add_command("multicam", "sync cameras + mics and cut to the active speaker",
                    _cfg_multicam, _run_multicam)
    reg.add_command("style", "learn a reusable style profile from reference videos",
                    _cfg_style, _run_style)
    reg.add_command("clips", "long video → vertical Shorts/Reels with hooks",
                    _cfg_clips, _run_clips)
    reg.add_command("export", "export FCPXML + EDL for Resolve / FCP / Premiere",
                    _cfg_export, _run_export)
    reg.add_command("variants", "natural / cinematic / dynamic plans side by side",
                    _cfg_variants, _run_variants)
