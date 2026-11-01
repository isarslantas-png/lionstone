import json

import pytest

from lionstone.models import EditPlan
from lionstone.pro.features import agent, studio
from lionstone.pro.features import timeline as tl
from lionstone.pro.features.catalog import Catalog
from lionstone.pro.features.entitlements import EntitlementError, for_tier

CAT = Catalog()
OWNER = for_tier("studio", "owner@acme.com", "acme")
EDITOR = for_tier("studio", "ed@acme.com", "acme")
VIEWER = for_tier("studio", "vi@acme.com", "acme")


def test_personal_presets_need_pro_and_are_versioned():
    with pytest.raises(EntitlementError):
        studio.save_personal_preset(CAT, "film-grain", "My Grain", {"intensity": 0.2},
                                    for_tier("free"))
    pro = for_tier("pro", "me@x.com")
    pid, r1 = studio.save_personal_preset(CAT, "film-grain", "My Grain", {"intensity": 0.2}, pro)
    pid, r2 = studio.save_personal_preset(CAT, "film-grain", "My Grain", {"intensity": 0.4}, pro,
                                          note="stronger")
    assert pid == "personal.my-grain" and (r1, r2) == (1, 2)
    st = studio.Store(studio.personal_root(), "personal")
    assert [h["note"] for h in st.history("preset", pid)] == ["", "stronger"]
    cat = Catalog(extra=studio.custom_presets(pro))
    p = cat.get(pid)
    assert p.renderer_id == "lionstone.film-grain" and p.defaults["intensity"] == 0.4
    assert p.tier == "pro"  # customising a free preset is a Pro feature


def test_team_roles_and_locked_presets(tmp_path, monkeypatch):
    monkeypatch.setenv("LIONSTONE_STUDIO_DIR", str(tmp_path / "team"))
    root = studio.team_root()
    team = studio.init_team(root, "ACME Media", OWNER)
    with pytest.raises(EntitlementError):
        studio.init_team(tmp_path / "other", "x", for_tier("pro"))
    studio.set_member(team, root, OWNER, "ed@acme.com", "editor")
    studio.set_member(team, root, OWNER, "vi@acme.com", "viewer")
    with pytest.raises(studio.StudioError):
        studio.set_member(studio.load_team(root), root, EDITOR, "x@acme.com", "admin")
    pid, _ = studio.save_team_preset(CAT, "look-warm-cinema", "ACME Warm", {"intensity": 0.5},
                                     OWNER, locked=True)
    with pytest.raises(studio.StudioError):  # editors can't change locked company presets
        studio.save_team_preset(CAT, "look-warm-cinema", "ACME Warm", {"intensity": 0.9}, EDITOR)
    studio.save_team_preset(CAT, "film-grain", "ACME Grain", {"intensity": 0.2}, EDITOR)
    with pytest.raises(studio.StudioError):
        studio.save_team_preset(CAT, "film-grain", "Viewer Grain", {}, VIEWER)
    ids = {d["id"] for d in studio.custom_presets(VIEWER)}
    assert {"team.acme-warm", "team.acme-grain"} <= ids
    assert studio.custom_presets(for_tier("studio", "stranger@x.com")) == []


def test_store_refuses_secrets():
    st = studio.Store(studio.personal_root(), "personal")
    with pytest.raises(studio.StudioError):
        st.save("profile", "bad", {"api_key": "sk-123"}, "me")


def test_brand_kit_apply(plan_copy, tmp_path, monkeypatch):
    monkeypatch.setenv("LIONSTONE_STUDIO_DIR", str(tmp_path / "team"))
    root = studio.team_root()
    studio.init_team(root, "ACME", OWNER)
    kit = studio.BrandKit(name="ACME", colors={"primary": "#101010", "accent": "#FF3366",
                                               "text": "#FFFFFF", "background": "#000000"},
                          cta={"text": "Abone ol", "subtext": "Yeni bölüm her salı"},
                          end_card={"title": "ACME Media", "subtitle": "acme.com"},
                          look={"preset": "lionstone.look-cool-cinema", "intensity": 0.5},
                          fonts={"title": {"path": "/nope.ttf"}},
                          locked=["lionstone.look-cool-cinema"])
    assert any("licence" in p for p in kit.validate())
    with pytest.raises(studio.StudioError):
        studio.save_kit(kit, EDITOR, "team")  # not a member yet
    studio.save_kit(kit, OWNER, "team")
    plan = EditPlan.load(plan_copy)
    k, scope = studio.load_kit("ACME", OWNER)
    notes = studio.apply_kit(plan, k, CAT, OWNER, scope=scope)
    presets = [i.preset for i in tl.instances(plan)]
    assert "lionstone.look-cool-cinema" in presets and "lionstone.cta" in presets
    assert plan.meta["options"]["accent"] == "#FF3366"
    assert any("not found" in n for n in notes)


def test_brand_kit_in_the_documented_json_format(plan_copy, tmp_path, monkeypatch):
    """docs/studio.md writes transition / lower_third as {"preset": ...}: that must apply,
    including the transition at long removed passages (it used to crash: unhashable dict)."""
    monkeypatch.setenv("LIONSTONE_STUDIO_DIR", str(tmp_path / "team"))
    root = studio.team_root()
    studio.init_team(root, "ACME", OWNER)
    kit = studio.BrandKit(name="ACME", transition={"preset": "lionstone.dip-to-black"},
                          lower_third={"preset": "lionstone.speaker-label"})
    assert (kit.transition, kit.lower_third) == ("lionstone.dip-to-black", "lionstone.speaker-label")
    studio.save_kit(kit, OWNER, "team")
    plan = EditPlan.load(plan_copy)
    k, scope = studio.load_kit("ACME", OWNER)
    studio.apply_kit(plan, k, CAT, OWNER, scope=scope)
    gaps = [b.start - a.end for a, b in zip(plan.segments, plan.segments[1:])]
    assert any(g > 2.5 for g in gaps)  # the fixture has long removed passages
    assert "lionstone.dip-to-black" in [i.preset for i in tl.instances(plan)]


def test_brand_cta_and_end_card_never_overlap(plan_copy, tmp_path, monkeypatch):
    """On a short video the CTA (at 82%) used to run into the end card, which then got dropped."""
    monkeypatch.setenv("LIONSTONE_STUDIO_DIR", str(tmp_path / "team"))
    studio.init_team(studio.team_root(), "ACME", OWNER)
    kit = studio.BrandKit(name="ACME", cta={"text": "Subscribe"}, end_card={"title": "ACME"})
    studio.save_kit(kit, OWNER, "team")
    plan = EditPlan.load(plan_copy)
    k, scope = studio.load_kit("ACME", OWNER)
    studio.apply_kit(plan, k, CAT, OWNER, scope=scope)
    spans = {i.preset: (i.anchor["start"], i.anchor["end"]) for i in tl.instances(plan)
             if i.preset in ("lionstone.cta", "lionstone.end-card")}
    assert set(spans) == {"lionstone.cta", "lionstone.end-card"}
    assert spans["lionstone.cta"][1] <= spans["lionstone.end-card"][0]


def test_batch_apply(media, tmp_path):
    paths = []
    for i in range(2):
        p = tmp_path / f"p{i}.json"
        EditPlan.load(media["plan"]).save(p)
        paths.append(str(p))
    with pytest.raises(EntitlementError):
        studio.batch_apply(paths, "film-grain", CAT, for_tier("free"))
    out = studio.batch_apply(paths, "dip-to-black", CAT, for_tier("pro"), anchor="all-joins")
    assert len(out) == 2
    assert all(tl.instances(EditPlan.load(p)) for p in paths)


def _segments_plan(media, words=False):
    return EditPlan.load(media["plan"])


def test_agent_subtle_is_restrained(media):
    plan = _segments_plan(media)
    pr = agent.propose(plan, CAT, for_tier("studio"), content="podcast", style="minimal",
                       intensity="subtle")
    kinds = [CAT.get(d.preset).kind for d in pr.decisions]
    assert kinds.count("look") == 1 and "transition" not in kinds and "effect" not in kinds


def test_agent_bold_social_transitions_rotate(media):
    plan = _segments_plan(media)
    pr = agent.propose(plan, CAT, for_tier("pro"), content="vlog", style="social",
                       intensity="bold")
    tr = [d.preset for d in pr.decisions if CAT.get(d.preset).kind == "transition"]
    assert tr, pr.notes
    assert all(a != b for a, b in zip(tr, tr[1:]))  # never the same transition twice in a row


def test_agent_respects_free_tier_and_real_estate_motion(media):
    plan = _segments_plan(media)
    pr = agent.propose(plan, CAT, for_tier("free"), content="real-estate", style="minimal",
                       intensity="balanced")
    assert all(CAT.get(d.preset).tier == "free" for d in pr.decisions)
    moves = [d.preset for d in pr.decisions if CAT.get(d.preset).kind == "motion"]
    assert moves and all(a != b for a, b in zip(moves, moves[1:]))
    n = agent.apply(plan, pr, CAT)
    assert n == len(pr.decisions)
    agent.apply(plan, pr, CAT)  # re-running replaces, doesn't duplicate
    assert len([i for i in tl.instances(plan) if i.created_by == "agent"]) == n
    json.dumps(plan.to_dict())
