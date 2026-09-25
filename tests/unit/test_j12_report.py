"""scripts/analysis/j12_report.py on synthetic campaigns whose answers are known by arithmetic.

Dyadic goal_pass values make every per-pair difference exact, so a constant difference gives every
bootstrap mean equal to it, a degenerate interval and a p of 0 or 1, all writable by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j10_report as j10
from scripts.analysis import j12_report as j12

REPO = Path(__file__).resolve().parents[2]
TASKS = [f"sc{i}_{j}" for i in range(4) for j in (1, 2, 3)]  # 4 scenarios x 3 tasks
SEEDS = (1, 2)
KEYS = [(t, s) for t in TASKS for s in SEEDS]  # 24 pairs
N_BOOT = 2000  # non-registered: dev only; test_normal cases use the registered 10,000


def write_arm(root: Path, label: str, goal_pass, *, handoff: dict | None = None,
              error_types: dict | None = None, manifest_split: str = "dev",
              live_asks: dict | None = None, other_provider_asks: dict | None = None,
              live: set | None = None) -> Path:
    """One arm in runner layout. goal_pass: a value or {(task, seed): value}. handoff: the system
    `report` event's handoff_occurred per key (effective_m 6). live: the keys whose executor took
    control -- an executor action at step 7 = effective_m + 1, so h* = 1 -- by default the keys whose
    flag is true. live_asks: codex-answered asks per key."""
    arm_root = root / label
    if live is None:
        live = {k for k, v in (handoff or {}).items() if v}
    for task_id, seed in KEYS:
        key = (task_id, seed)
        dest = arm_root / "prefix_handoff" / str(seed) / task_id
        dest.mkdir(parents=True, exist_ok=True)
        events = [{"event_type": "run_start", "payload": {}}]
        if handoff is not None and key in handoff:
            events.append({"event_type": "report", "actor": "system", "step": 6,
                           "payload": {"handoff_occurred": handoff[key], "effective_m": 6}})
            if key in live:
                events.append({"event_type": "action", "actor": "executor", "step": 7,
                               "payload": {"kind": "CODE", "code": "x"}})
        n_live = (live_asks or {}).get(key, 0)
        for provider, n in (("codex", n_live), ("mock", (other_provider_asks or {}).get(key, 0))):
            for _ in range(n):
                events.append({"event_type": "ask", "actor": "executor", "payload": {"gated": False}})
                events.append({"event_type": "intervention", "actor": "planner", "payload": {"forced": False},
                               "usage": {"provider": provider, "model": "gpt-5.6-luna", "n_calls": 1}})
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        gp = goal_pass[key] if isinstance(goal_pass, dict) else goal_pass
        row = {"run_id": f"synth/{label}/{seed}/{task_id}", "task_id": task_id, "system": "prefix_handoff",
               "seed": seed, "success": False, "tgc": 0.0, "goal_pass_rate": gp, "steps": 5,
               "n_planner_calls": 0, "error_type": (error_types or {}).get(key),
               "totals": {"planner_calls_total": n_live}}
        (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
        (dest / "manifest.json").write_text(json.dumps({"provenance": {"split": manifest_split}}), encoding="utf-8")
    return arm_root


def write_family(root: Path, gp: dict, **kw) -> dict[str, Path]:
    """gp: label -> value or map; kw per label: {label: {write_arm kwargs}}."""
    return {label: write_arm(root, label, gp[label], **kw.get(label, {})) for label in j12.J12_ARMS}


CONSTANT = {"prefix_m11": 0.75, "prefix_m6": 0.625, "prefix_zs_m11": 0.625, "prefix_zs_m6": 0.5}
ALL_H = {k: True for k in KEYS}
PLAN = j12.J12_PLAN_SOURCE_ARM
REG = j12.j12_registered_campaigns()  # label -> the campaign id its config declares


def write_plan_source(root: Path, name: str, *, planless=(), crash=(), manifest_split: str = "dev") -> Path:
    """J10 arm 3 in runner layout (system planner_alone): a scored episode per key whose last attempt wrote a
    plan, except `planless` keys (no plan event) and `crash` keys (error_type crash)."""
    arm_root = root / name
    for task_id, seed in KEYS:
        key = (task_id, seed)
        dest = arm_root / "planner_alone" / str(seed) / task_id
        dest.mkdir(parents=True, exist_ok=True)
        events = [{"event_type": "run_start", "payload": {}}]
        if key not in planless:
            events.append({"event_type": "plan", "actor": "planner", "payload": {"packet": {"steps": ["x"]}}})
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        row = {"run_id": f"synth/{name}/{seed}/{task_id}", "task_id": task_id, "system": "planner_alone",
               "seed": seed, "success": False, "tgc": 0.0, "goal_pass_rate": 0.5, "steps": 5,
               "error_type": "crash" if key in crash else None}
        (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
        (dest / "manifest.json").write_text(json.dumps({"provenance": {"split": manifest_split}}), encoding="utf-8")
    return arm_root


def registered_family(root: Path, gp: dict = CONSTANT, *, arm3: bool = True, arm3_kw: dict | None = None,
                      **kw) -> dict[str, Path]:
    """The four contrast arms and arm 3 under their registered campaign ids, test_normal manifests; the m = 11
    arms hand off everywhere unless kw says otherwise."""
    per = {"prefix_m11": {"handoff": ALL_H}, "prefix_zs_m11": {"handoff": ALL_H}}
    dirs = {label: write_arm(root, REG[label], gp[label], manifest_split="test_normal",
                             **(per.get(label, {}) | kw.get(label, {}))) for label in j12.J12_ARMS}
    if arm3:
        dirs[PLAN] = write_plan_source(root, REG[PLAN], manifest_split="test_normal", **(arm3_kw or {}))
    return dirs


def registered_read(dirs: dict[str, Path], **kw):
    return report_for(dirs, split="test_normal", confirm_heldout_test_split=True, n_boot=j10.A1_BOOTSTRAP_N, **kw)


def report_for(dirs: dict[str, Path], **kw):
    kw.setdefault("split", "dev")
    kw.setdefault("seeds", list(SEEDS))
    kw.setdefault("expected_n_tasks", len(TASKS))
    kw.setdefault("n_boot", N_BOOT)
    return j12.build_report_j12(arm_dirs=dirs, **kw)


def by_id(report: dict) -> dict:
    return {p["id"]: p for p in report["predictions"]}


# ---- the registry ------------------------------------------------------------------------------

def test_registry_is_one_holm_family_of_four_all_greater_than_zero():
    preds = j12.J12_PREDICTIONS
    assert [p["id"] for p in preds] == ["D1", "D2", "D3", "D4"]
    assert all(p["holm_family"] and p["threshold_pp"] == 0.0 and p["metric"] == "goal_pass" for p in preds)
    assert {p["rule"] for p in preds} == {"lower_bound_above_threshold"}
    assert j10.A1_RULES["lower_bound_above_threshold"]["direction"] == "greater"
    assert [(p["left"], p["right"], p["kind"]) for p in preds] == [
        ("prefix_m11", "prefix_m6", "paired_contrast"), ("prefix_zs_m11", "prefix_zs_m6", "paired_contrast"),
        ("prefix_m11", "prefix_m6", "handoff_only"), ("prefix_zs_m11", "prefix_zs_m6", "handoff_only")]
    # h comes from the m = 11 arm (j17_depth_fixes.paired_components: the target arm).
    assert [p.get("flags_from") for p in preds[2:]] == ["prefix_m11", "prefix_zs_m11"]
    assert j12.J12_ARMS["prefix_m6"] == "configs/j12_prefix_m6.yaml"
    assert j12.J12_ARMS["prefix_m11"] == "configs/j10_prefix_m11.yaml"


def test_dev_references_are_the_j17_report_values_rounded():
    # D1 / D2 from j17_depth_fixes; D3 / D4 from j17_hstar (h*), with the flag-based value kept beside.
    assert [p["dev_reference"]["source"] for p in j12.J12_PREDICTIONS] == [
        j12.J12_DEV_REPORT, j12.J12_DEV_REPORT, j12.J12_DEV_REPORT_HSTAR, j12.J12_DEV_REPORT_HSTAR]
    refs = [(p, p["dev_reference"]) for p in j12.J12_PREDICTIONS]
    refs += [(p, p["dev_reference_flag"]) for p in j12.J12_PREDICTIONS if "dev_reference_flag" in p]
    assert [r["source"] for p, r in refs[4:]] == [j12.J12_DEV_REPORT, j12.J12_DEV_REPORT]
    for p, ref in refs:
        data = json.loads((REPO / ref["source"]).read_text(encoding="utf-8"))
        node = data
        for part in ref["key"].split("."):
            node = node[part]
        assert ref["diff_pp"] == round(node["diff_pp"], 2), p["id"]
        assert ref["ci95_pp_scenario"] == [round(v, 2) for v in node["ci95_pp_scenario"]], p["id"]
        pairing = data["handoff_only_contrasts"][p["receiver"]]["m6_to_m11"]["goal_pass"]["pairing"]
        assert ref["n_pairs"] == pairing["n_pairs"]
        if p["kind"] == "handoff_only":
            assert ref["n_handoff"] == node["n_pairs"] == pairing["n_handoff"]
    # The h* report's all-episode values are j17_depth_fixes' exactly (they do not depend on h).
    hstar = json.loads((REPO / j12.J12_DEV_REPORT_HSTAR).read_text(encoding="utf-8"))
    assert hstar["changes_vs_flag"]["all_episode_values_unchanged"] is True
    assert hstar["validation"]["all_hold"] is True


# ---- one all-episode contrast, by hand ------------------------------------------------------------

def test_all_episode_contrast_by_hand(tmp_path: Path):
    dirs = write_family(tmp_path, CONSTANT, prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H})
    report, code = report_for(dirs)
    d1, d2 = by_id(report)["D1"], by_id(report)["D2"]
    # 0.75 − 0.625 = 0.125 on every pair: every resample mean is 0.125.
    assert d1["contrast"]["n_pairs"] == 24
    assert d1["contrast"]["scenario"]["diff_pp"] == 12.5
    assert d1["contrast"]["scenario"]["ci95_pp"] == [12.5, 12.5]
    assert d1["contrast"]["task"]["ci95_pp"] == [12.5, 12.5]
    assert (d1["contrast"]["scenario"]["n_clusters"], d1["contrast"]["task"]["n_clusters"]) == (4, 12)
    # greater at 0: 2 x share(means <= 0) = 0; Holm over four zeros is 0.
    assert d1["p_value"] == 0.0 and d1["holm"]["p_adjusted"] == 0.0 and d1["holm"]["m"] == 4
    assert d1["verdict"] == "supported"
    assert d2["contrast"]["scenario"]["diff_pp"] == 12.5 and d2["verdict"] == "supported"
    assert d1["tgc_secondary"]["scenario"]["diff_pp"] == 0.0  # TGC beside it
    assert d1["pool04"]["fired"] is False
    assert d1["permutation_sensitivity"]["decision_bearing"] is False
    assert report["multiplicity"]["family"] == ["D1", "D2", "D3", "D4"]
    assert code == 0 and report["headline"].startswith("COMPLETE")
    assert report["label"] == "J12 DRY RUN ON DEV, NOT THE J12 RESULT (NON-REGISTERED bootstrap settings)"


def test_all_episode_point_with_varying_scenarios(tmp_path: Path):
    # d = 0.375 on sc0's 6 pairs and 0.125 on the other 18: (6 x 0.375 + 18 x 0.125) / 24 = 0.1875.
    m11 = {k: (1.0 if k[0].startswith("sc0") else 0.75) for k in KEYS}
    dirs = write_family(tmp_path, dict(CONSTANT, prefix_m11=m11), prefix_m11={"handoff": ALL_H},
                        prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    scen = by_id(report)["D1"]["contrast"]["scenario"]
    assert scen["diff_pp"] == 18.75
    assert 12.5 <= scen["ci95_pp"][0] <= scen["ci95_pp"][1] <= 37.5


# ---- one handoff-only contrast, by hand -----------------------------------------------------------

def test_handoff_only_by_hand_h_from_m11_and_h0_pairs_never_enter(tmp_path: Path):
    # m11 hands off on sc0 and sc1 (12 pairs) and not on sc2, sc3 (12 pairs). The m6 arm says every
    # episode handed off: if h were read from m6, D3 would equal D1.
    h11 = {k: k[0].startswith(("sc0", "sc1")) for k in KEYS}
    m11 = {k: (0.875 if h11[k] else 0.25) for k in KEYS}
    dirs = write_family(tmp_path, dict(CONSTANT, prefix_m11=m11),
                        prefix_m11={"handoff": h11}, prefix_m6={"handoff": ALL_H},
                        prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    d1, d3 = by_id(report)["D1"], by_id(report)["D3"]
    # d = 0.875 − 0.625 = +0.25 on the 12 handoff pairs, 0.25 − 0.625 = −0.375 on the 12 others.
    # D3 = Σ d·h / Σ h = (12 x 0.25) / 12 = +25 pp; the h = 0 pairs are not in it.
    assert (d3["contrast"]["n_pairs"], d3["contrast"]["n_handoff"], d3["contrast"]["n_silenced"]) == (24, 12, 12)
    assert d3["contrast"]["scenario"]["diff_pp"] == 25.0
    assert d3["contrast"]["scenario"]["ci95_pp"] == [25.0, 25.0]
    assert d3["contrast"]["task"]["ci95_pp"] == [25.0, 25.0]
    # Resamples that draw only sc2 / sc3 have Σ h = 0: undefined, left out and counted.
    assert d3["contrast"]["scenario"]["n_resamples_undefined"] > 0
    assert d3["p_value"] == 0.0 and d3["verdict"] == "supported"
    # D1 over all pairs: (12 x 0.25 − 12 x 0.375) / 24 = −6.25 pp, not supported.
    assert d1["contrast"]["scenario"]["diff_pp"] == -6.25 and d1["verdict"] == "not_supported"
    # Reading J12 §4: D1 not supported -> the dev span does not replicate for the tailored executor.
    assert report["readings"]["bplus"]["reading_key"] == "all_not"
    assert "tailored executor" in report["readings"]["bplus"]["reading"]
    # Beside: the decomposition's two contributions sum to the all-episode rise; silenced counts.
    dec = report["beside"]["decomposition"]["bplus"]["goal_pass"]
    assert dec["contribution_handoff"]["diff_pp"] == 12.5 and dec["contribution_silenced"]["diff_pp"] == -18.75
    assert dec["delta_total"]["diff_pp"] == -6.25
    counts = report["beside"]["silenced_counts"]
    assert (counts["prefix_m11"]["n_handoff"], counts["prefix_m11"]["n_no_handoff"]) == (12, 12)
    assert (counts["prefix_m11"]["m"], counts["prefix_m6"]["m"]) == (11, 6)
    # The sign-flip runs over the 12 handoff pairs' d only.
    assert report["beside"]["sign_flip_p"]["D3"] is not None


def test_handoff_only_evaluator_directly_matches_the_estimand():
    arms = {"prefix_m11": {"episodes": {("a_1", 1): {"goal_pass_rate": 1.0}, ("a_2", 1): {"goal_pass_rate": 0.0},
                                        ("b_1", 1): {"goal_pass_rate": 0.5}},
                           "complete": True},
            "prefix_m6": {"episodes": {("a_1", 1): {"goal_pass_rate": 0.5}, ("a_2", 1): {"goal_pass_rate": 1.0},
                                       ("b_1", 1): {"goal_pass_rate": 0.25}},
                          "complete": True}}
    flags = {"prefix_m11": {("a_1", 1): True, ("a_2", 1): False, ("b_1", 1): None}}
    # d = +0.5 (h = 1), −1.0 (h = 0), +0.25 (flag missing: h = 0). Σ d·h / Σ h = 0.5 / 1.
    r = j12.j12_evaluate_handoff_only(dict(j12.J12_PREDICTIONS[2]), arms, flags, n_boot=200, seed=1,
                                      stability=False)
    assert r["contrast"]["scenario"]["diff_pp"] == 50.0
    assert (r["contrast"]["n_handoff"], r["contrast"]["n_silenced"], r["contrast"]["n_flag_missing"]) == (1, 2, 1)


def test_d3_reads_h_star_and_d3_flag_keeps_the_flag(tmp_path: Path):
    # m11's flag is true on sc0, sc1 (12 keys); the executor also took control on sc2 although its
    # flag is false (the source made <= m executed actions without ending); sc3's prefix was terminal.
    flag = {k: k[0].startswith(("sc0", "sc1")) for k in KEYS}
    live = {k for k in KEYS if not k[0].startswith("sc3")}
    m11 = {k: (0.875 if flag[k] else 0.75 if k in live else 0.25) for k in KEYS}
    dirs = write_family(tmp_path, dict(CONSTANT, prefix_m11=m11),
                        prefix_m11={"handoff": flag, "live": live}, prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    d3 = by_id(report)["D3"]
    # d vs m6 0.625: +0.25 on 12 flagged keys, +0.125 on 6 live-unflagged, −0.375 on 6 terminal.
    # h*: (12 x 0.25 + 6 x 0.125) / 18 = 0.2083 -> 20.83 pp; the flag: 12 x 0.25 / 12 = 25 pp.
    assert (d3["contrast"]["n_handoff"], d3["contrast"]["n_silenced"], d3["contrast"]["h"]) == (18, 6, "h_star")
    assert d3["contrast"]["scenario"]["diff_pp"] == 20.83
    assert "h*" in d3["contrast"]["estimand"]
    sens = report["sensitivity_h_flag"]
    assert sens["decision_bearing"] is False
    f3 = sens["D3_flag"]
    assert (f3["contrast"]["n_handoff"], f3["contrast"]["h"], f3["sensitivity_of"]) == (12, "h_flag", "D3")
    assert f3["contrast"]["scenario"]["diff_pp"] == 25.0
    assert f3["holm"]["m"] == 4 and f3["verdict_holm_with_hstar"] == d3["verdict_holm"]
    assert sens["D4_flag"]["contrast"]["n_handoff"] == 24
    counts = report["beside"]["handoff_control_counts"]["prefix_m11"]
    assert (counts["n_h_flag_true"], counts["n_live_but_unflagged"], counts["n_terminal"]) == (12, 6, 6)
    # The flag-based silenced count is unchanged; the decomposition reads h*, with the flag beside it.
    assert report["beside"]["silenced_counts"]["prefix_m11"]["n_handoff"] == 12
    assert report["beside"]["decomposition"]["bplus"]["goal_pass"]["n_handoff"] == 18
    assert report["beside"]["decomposition_h_flag"]["bplus"]["goal_pass"]["n_handoff"] == 12
    md = j12.render_markdown(report, "x.json")
    assert "D3_flag: 25.0 pp" in md and "live but unflagged 6" in md


# ---- the Holm step --------------------------------------------------------------------------------

def _synthetic(pid: str, p: float) -> dict:
    return {"id": pid, "kind": "paired_contrast", "rule": j12.J12_RULE, "threshold_pp": 0.0,
            "holm_family": True, "decidable": True, "p_value": p, "_point": 0.05, "_lo": 0.01, "_hi": 0.09,
            "events_unadjusted": {"lo_above_threshold": True, "hi_below_threshold": False},
            "pool04": {"fired": False, "stable": True}}


def test_holm_step_by_hand():
    # Sorted p 0.01, 0.02, 0.03, 0.04 at m = 4: 4 x 0.01 = 0.04; 3 x 0.02 = 0.06; 2 x 0.03 = 0.06;
    # 1 x 0.04 = 0.04 -> running max 0.06. Every CI lower bound is above 0, but only D1 survives Holm.
    results = [_synthetic(f"D{i}", p) for i, p in enumerate((0.01, 0.02, 0.03, 0.04), start=1)]
    fam = j12.j12_decide_family(results)
    assert fam["m"] == 4 and fam["family"] == ["D1", "D2", "D3", "D4"]
    assert [r["holm"]["p_adjusted"] for r in results] == pytest.approx([0.04, 0.06, 0.06, 0.06])
    assert [r["verdict"] for r in results] == ["supported", "not_supported", "not_supported", "not_supported"]
    assert all(r["reversal_unadjusted"] is False for r in results)


def test_holm_counts_an_undecidable_member_at_p_1():
    results = [_synthetic("D1", 0.01), _synthetic("D2", 0.01), _synthetic("D3", 0.01),
               dict(_synthetic("D4", 0.0), decidable=False, verdict="refused_incomplete")]
    j12.j12_decide_family(results)
    # p_raw 0.01, 0.01, 0.01, 1.0: 4 x 0.01, 3 x 0.01, 2 x 0.01 -> all 0.04; D4 1.0.
    assert [r["holm"]["p_adjusted"] for r in results] == pytest.approx([0.04, 0.04, 0.04, 1.0])
    assert [r["verdict"] for r in results] == ["supported"] * 3 + ["refused_incomplete"]


# ---- the incomplete rule --------------------------------------------------------------------------

def test_a_crash_leaves_its_contrasts_incomplete_and_a_limit_is_scored(tmp_path: Path):
    dirs = write_family(
        tmp_path, CONSTANT,
        prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H},
        prefix_m6={"error_types": {("sc1_2", 2): "crash"}},
        prefix_zs_m6={"error_types": {("sc2_1", 1): "limit"}})
    report, code = report_for(dirs)
    d = by_id(report)
    for pid in ("D1", "D3"):
        assert d[pid]["decidable"] is False and d[pid]["verdict"] == "refused_incomplete"
    assert d["D1"]["n_noncrashed_pairs"] == 23 and d["D1"]["expected_pairs"] == 24
    # The limit episode is a scored outcome: D2 / D4 keep all 24 pairs and are decided.
    for pid in ("D2", "D4"):
        assert d[pid]["decidable"] is True and d[pid]["n_noncrashed_pairs"] == 24
    assert d["D2"]["contrast"]["n_pairs"] == 24
    assert report["arms"]["prefix_m6"]["n_crash"] == 1 and report["arms"]["prefix_m6"]["complete"] is False
    assert report["beside"]["limit_rates"]["prefix_zs_m6"] == {"n_scored": 24, "n_limit": 1,
                                                               "limit_rate": round(1 / 24, 6)}
    assert code == 1 and report["headline"].startswith("INCOMPLETE")
    assert report["readings"]["bplus"]["reading"] is None


def test_pair_rule_refuses_a_decidable_contrast_below_the_registered_pairs():
    arms = {"prefix_m11": {"episodes": {("a", 1): {}, ("b", 1): {}}},
            "prefix_m6": {"episodes": {("a", 1): {}, ("c", 1): {}}}}
    r = {"id": "D1", "left": "prefix_m11", "right": "prefix_m6", "decidable": True}
    j12.j12_apply_pair_rule(r, arms, expected_pairs=2)
    assert (r["n_noncrashed_pairs"], r["decidable"], r["verdict"]) == (1, False, "refused_incomplete")


def test_key_exclusion_drops_keys_from_every_arm_and_flags_a_changed_verdict(tmp_path: Path):
    # d = +0.25 on sc0-sc2 and 0 on sc3. All pairs: a resample mean is 0 only if all four draws are
    # sc3 (p = 1/256), so the scenario lower bound is +6.25 pp and D1 / D3 are supported. Without
    # sc0-sc2's keys only sc3 is left, d is 0 everywhere and both are not supported.
    m11 = {k: (0.875 if not k[0].startswith("sc3") else 0.625) for k in KEYS}
    dirs = write_family(tmp_path, dict(CONSTANT, prefix_m11=m11), prefix_m11={"handoff": ALL_H},
                        prefix_zs_m11={"handoff": ALL_H})
    loaded = {a: j10.load_arm_tree(p) for a, p in dirs.items()}
    arms = {a: j10.a1_arm_episodes(a, blob, TASKS, list(SEEDS)) for a, blob in loaded.items()}
    flags = {a: j10.a1_handoff_flags(p) for a, p in dirs.items()}
    results = [j12.j12_evaluate(dict(p), arms, flags, n_boot=N_BOOT, seed=7, stability=False)
               for p in j12.J12_PREDICTIONS]
    j12.j12_decide_family(results)
    keys = [k for k in KEYS if not k[0].startswith("sc3")]
    sens = j12.j12_key_exclusion_sensitivity(results, arms, flags, keys, n_boot=N_BOOT, seed=7)
    rows = {r["id"]: r for r in sens["rows"]}
    assert rows["D1"]["verdict_holm_all_pairs"] == rows["D3"]["verdict_holm_all_pairs"] == "supported"
    assert rows["D1"]["contrast_without_keys"]["scenario"]["diff_pp"] == 0.0
    assert rows["D3"]["contrast_without_keys"]["scenario"]["diff_pp"] == 0.0
    assert rows["D1"]["verdict_holm_without_keys"] == rows["D3"]["verdict_holm_without_keys"] == "not_supported"
    assert sens["differs"] == ["D1", "D3"]
    j10.a1_apply_key_exclusion(results, sens["differs"])
    assert [r["verdict"] for r in results] == ["on_boundary", "supported", "on_boundary", "supported"]


# ---- A1 Amendment 1 §I -------------------------------------------------------------------------

def test_live_asks_are_counted_and_bounded_beside_every_contrast(tmp_path: Path):
    dirs = write_family(tmp_path, CONSTANT, prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H},
                        prefix_m6={"live_asks": {("sc0_1", 1): 2}, "other_provider_asks": {("sc0_2", 1): 1}})
    report, _ = report_for(dirs)
    live = report["beside"]["live_asks"]["prefix_m6"]
    # One episode got two codex answers; the mock-provider answer is not a hosted call.
    assert (live["n_episodes_live_answer"], live["n_live_answer_calls"]) == (1, 2)
    assert live["n_ledger_live_planner_calls"] == 2 and live["n_episodes_events_and_ledger_disagree"] == 0
    assert live["episodes"] == ["1/sc0_1"]
    # Bound = 1 / 24 pairs = 4.17 pp >= 1.00 pp: printed with the verdict of D1 and D3.
    assert live["bound_pp"] == round(100 / 24, 2) and live["reaches_1pp"] is True
    assert report["beside"]["live_asks"]["prefix_m11"]["n_episodes_live_answer"] == 0
    d = by_id(report)
    for pid in ("D1", "D3"):
        sentence = d[pid]["live_ask_bound"]["sentence"]
        assert sentence.startswith(f"{pid} supported; prefix_m6: 1 episode(s)") and "4.17 pp" in sentence
        assert sentence in report["headline"]
    for pid in ("D2", "D4"):
        assert d[pid]["live_ask_bound"]["sentence"] is None
        assert d[pid]["live_ask_bound"]["arms"]["prefix_zs_m6"]["bound_pp"] == 0.0


# ---- refusals -----------------------------------------------------------------------------------

def _argv(dirs: dict[str, Path], *extra: str) -> list[str]:
    out = []
    for label, path in dirs.items():
        out += ["--arm", f"{label}={path}"]
    return out + ["--seeds", "1,2", "--expected-n-tasks", str(len(TASKS)), *extra]


def test_test_normal_is_refused_without_the_confirmation_flag_and_writes_nothing(tmp_path: Path, capsys):
    dirs = write_family(tmp_path / "t", CONSTANT, prefix_m11={"handoff": ALL_H, "manifest_split": "test_normal"})
    out = tmp_path / "r.report.json"
    code = j12.main(["--split", "test_normal", *_argv(dirs), "--out", str(out)])
    assert code == 2 and not out.exists()
    assert "--confirm-heldout-test-split" in capsys.readouterr().out


def test_test_challenge_is_always_refused(tmp_path: Path, capsys):
    dirs = {a: tmp_path / a for a in j12.J12_ARMS}
    for extra in ((), ("--confirm-heldout-test-split",)):
        code = j12.main(["--split", "test_challenge", *_argv(dirs), *extra, "--out", str(tmp_path / "x.json")])
        assert code == 2
        assert "test_challenge" in capsys.readouterr().out
    assert not (tmp_path / "x.json").exists()


def test_plumbing_check_reads_only_dryrun_campaigns_on_dev(tmp_path: Path):
    plain = write_family(tmp_path / "plain", CONSTANT, prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H})
    report, code = report_for(plain, plumbing_check=True)
    assert code == 2 and "plumbing checks read only *_dryrun campaigns" in report["reason"]
    dry = {a: write_arm(tmp_path / "dry", f"{Path(j12.J12_ARMS[a]).stem}_20260924_dryrun", CONSTANT[a],
                        handoff=ALL_H) for a in j12.J12_ARMS}
    report, code = report_for(dry, plumbing_check=True)
    assert code == 0 and report["label"].startswith("PLUMBING CHECK, NOT A RESULT")
    report, code = report_for(dry, plumbing_check=True, split="test_normal", confirm_heldout_test_split=True,
                              n_boot=j10.A1_BOOTSTRAP_N)
    assert code == 2 and "plumbing" in report["reason"]


def test_a_registered_test_campaign_is_read_only_on_test_normal_and_a_dryrun_never_there(tmp_path: Path):
    reg = {a: tmp_path / f"{Path(j12.J12_ARMS[a]).stem}_20260924" for a in j12.J12_ARMS}
    report, code = report_for(reg)  # dev
    assert code == 2 and "registered J10/J12 test campaign" in report["reason"]
    dry = {a: tmp_path / f"{Path(j12.J12_ARMS[a]).stem}_20260924_dryrun" for a in j12.J12_ARMS}
    report, code = report_for(dry, split="test_normal", confirm_heldout_test_split=True, n_boot=j10.A1_BOOTSTRAP_N)
    assert code == 2 and "*_dryrun campaign is dev data" in report["reason"]


def test_other_a1_refusals_hold(tmp_path: Path):
    dirs = {a: tmp_path / a for a in j12.J12_ARMS}
    # test_normal at non-registered bootstrap settings; a held-out marker read on dev; --out under results.
    assert report_for(dirs, split="test_normal", confirm_heldout_test_split=True, n_boot=500)[1] == 2
    marked = dict(dirs, prefix_m6=tmp_path / "test_normal" / "prefix_m6")
    assert report_for(marked)[1] == 2
    rep, code = report_for(dirs, out_path=Path("/scratch/n12194778/sidekick/results/j12.json"))
    assert code == 2 and "raw results are read-only" in rep["reason"]
    assert j12.main(["--split", "dev", "--arm", f"prefix_m9={tmp_path}"]) == 2  # unknown label


def test_confirmed_test_normal_read_writes_the_json_and_the_md(tmp_path: Path, capsys, monkeypatch):
    # R1 (2026-09-25): the registered read now needs arm 3 and each arm under its registered campaign id, at the
    # registered 168 tasks; the fixture's 12 tasks stand in for 168 (the guard itself: test_n4_*).
    monkeypatch.setattr(j12, "J12_TEST_N_TASKS", len(TASKS))
    dirs = registered_family(tmp_path / "t")
    out = tmp_path / "j12_depth_test_normal.report.json"
    code = j12.main(["--split", "test_normal", "--confirm-heldout-test-split", *_argv(dirs), "--out", str(out)])
    capsys.readouterr()
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["label"] == "J12 registered analysis" and report["not_the_j12_result"] is False
    assert report["verdicts"] == {"D1": "supported", "D2": "supported", "D3": "supported", "D4": "supported"}
    assert report["bootstrap"]["n"] == 10_000 and report["bootstrap"]["seed"] == 20260924
    md = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "| D1 | prefix_m11 − prefix_m6 | all | 12.5 | [12.5, 12.5] | [12.5, 12.5] |" in md
    assert "a later handoff raises the tailored executor's quality" in md
    assert "_samples" not in out.read_text(encoding="utf-8")  # internal resamples stripped


def test_default_out_is_the_registered_path_and_j17_is_not_imported():
    assert j12.J12_DEFAULT_OUT == "campaign/results/j12_depth_test_normal.report.json"
    src = (REPO / "scripts" / "analysis" / "j12_report.py").read_text(encoding="utf-8")
    imports = [line for line in src.splitlines() if line.startswith(("import ", "from "))]
    assert imports and not any("j17" in line for line in imports)  # j17 refuses held-out paths by design


# ---- J12 Amendment 2: a replay that cannot pass its own check (unit DIVRULE, 2026-09-25) -------------------
AM2_KEY = ("sc0_1", 1)


def _am2_crash(arm_root: Path, keys, reason: str = "replay_divergence") -> None:
    """These episodes become crashes whose last attempt's error event carries `reason`."""
    for task_id, seed in keys:
        dest = arm_root / "prefix_handoff" / str(seed) / task_id
        row = json.loads((dest / "result.json").read_text(encoding="utf-8"))
        row["error_type"] = "crash"
        (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
        events = [{"event_type": "run_start", "payload": {}},
                  {"event_type": "error", "actor": "system", "step": 6, "error_type": "crash",
                   "payload": {"reason": reason}}]
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _am2_family(root: Path, **gp) -> dict[str, Path]:
    return write_family(root, dict(CONSTANT, **gp), prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H})


def test_am2_no_divergent_key_changes_nothing_but_adds_the_block(tmp_path: Path, monkeypatch):
    """(a) and an ordinary crash (still incomplete): the report equals the pre-amendment one but for the block."""
    clean = _am2_family(tmp_path / "clean")
    crashed = _am2_family(tmp_path / "crashed")
    _am2_crash(crashed["prefix_m6"], [("sc1_2", 2)], reason="replay_error")
    new = [report_for(d) for d in (clean, crashed)]
    monkeypatch.setattr(j10, "a1_am5_arms", lambda arms, *_a, **_k: arms)
    monkeypatch.setattr(j10, "a1_am5_pair", lambda arms, left, right: (arms[left], arms[right]))
    monkeypatch.setattr(j10, "a1_am5_exclusion", lambda *_a: ([], "ok"))
    old = [report_for(d) for d in (clean, crashed)]
    blocks = []
    for (rep, code), (base, code0) in zip(new, old):
        blocks.append(rep.pop("j12_am2_divergence"))
        base.pop("j12_am2_divergence")
        assert code == code0
        assert json.dumps(rep, sort_keys=True, default=str) == json.dumps(base, sort_keys=True, default=str)
        assert {a: (v["n_divergent"], v["keys"]) for a, v in blocks[-1]["per_arm"].items()} == {
            a: (0, []) for a in j12.J12_ARMS}
        assert blocks[-1]["contrasts"] == {} and blocks[-1]["companions"] == {}
    assert new[0][1] == 0 and new[1][1] == 1 and by_id(new[1][0])["D1"]["verdict"] == "refused_incomplete"
    assert blocks[1]["per_arm"]["prefix_m6"]["n_crash_other"] == 1


def test_am2_one_divergent_key_in_a_j10_arm_reads_d1_d3_on_23_pairs(tmp_path: Path):
    """(b) J10's prefix_m11 diverges on AM2_KEY, where prefix_m6 scores 0.0: D1 and D3 lose the key on both
    sides and are decided on 23 pairs against 23; D2 / D4 keep 24."""
    dirs = _am2_family(tmp_path, prefix_m6={k: 0.0 if k == AM2_KEY else 0.625 for k in KEYS})
    _am2_crash(dirs["prefix_m11"], [AM2_KEY])
    report, code = report_for(dirs)
    assert code == 0 and report["incomplete_reasons"] == [], report["headline"]
    d = by_id(report)
    for pid in ("D1", "D3"):
        assert d[pid]["decidable"] is True and d[pid]["verdict"] == "supported", pid
        assert (d[pid]["n_noncrashed_pairs"], d[pid]["expected_pairs"], d[pid]["contrast"]["n_pairs"]) == (23, 23, 23)
        assert d[pid]["contrast"]["scenario"]["ci95_pp"] == [12.5, 12.5]  # m6's 0.0 on the key is gone
    for pid in ("D2", "D4"):
        assert (d[pid]["n_noncrashed_pairs"], d[pid]["expected_pairs"], d[pid]["contrast"]["n_pairs"]) == (24, 24, 24)
    assert report["arms"]["prefix_m11"]["complete"] is True and report["arms"]["prefix_m11"]["n_crash"] == 1
    assert report["sensitivity_h_flag"]["D3_flag"]["decidable"] is True
    assert report["beside"]["decomposition"]["bplus"]["goal_pass"]["n_pairs"] == 23
    blk = report["j12_am2_divergence"]
    assert blk["per_arm"]["prefix_m11"] == {"n_divergent": 1, "keys": ["1/sc0_1"], "n_crash_other": 0,
                                            "arm_complete": True}
    assert {a: v["n_divergent"] for a, v in blk["per_arm"].items()} == {
        "prefix_m6": 0, "prefix_zs_m6": 0, "prefix_m11": 1, "prefix_zs_m11": 0}
    assert set(blk["contrasts"]) == {"D1", "D3"}
    assert blk["contrasts"]["D1"]["excluded_keys"] == ["1/sc0_1"] and blk["contrasts"]["D3"]["n_pairs"] == 23
    assert blk["contrasts"]["D3"]["n_pairs_h_flag"] == 23
    assert blk["companions"] == {"decomposition.bplus": {"n_excluded": 1, "n_pairs": 23}}


def test_am2_two_arms_of_a_d_remove_the_union(tmp_path: Path):
    """(c) D2 / D4: {sc0_1/1} from prefix_zs_m11 and {sc0_1/1, sc1_1/2} from prefix_zs_m6: 2 keys, 22 pairs."""
    dirs = _am2_family(tmp_path)
    _am2_crash(dirs["prefix_zs_m11"], [AM2_KEY])
    _am2_crash(dirs["prefix_zs_m6"], [AM2_KEY, ("sc1_1", 2)])
    report, code = report_for(dirs)
    assert code == 0, report["headline"]
    d = by_id(report)
    for pid in ("D2", "D4"):
        assert (d[pid]["n_noncrashed_pairs"], d[pid]["expected_pairs"], d[pid]["decidable"]) == (22, 22, True)
    assert report["j12_am2_divergence"]["contrasts"]["D2"]["excluded_keys"] == ["1/sc0_1", "2/sc1_1"]


def test_am2_more_than_16_divergent_keys_leave_the_d_incomplete(tmp_path: Path):
    """(d) 17 keys: D1 and D3 draw no reading, although the arm is complete; D2 and D4 are decided."""
    dirs = _am2_family(tmp_path)
    _am2_crash(dirs["prefix_m6"], KEYS[:17])
    report, code = report_for(dirs)
    assert code == 1 and report["arms"]["prefix_m6"]["complete"] is True
    d = by_id(report)
    for pid in ("D1", "D3"):
        assert d[pid]["decidable"] is False and d[pid]["verdict"] == "refused_incomplete", pid
        assert "cap 16" in d[pid]["reason"]
    assert d["D2"]["decidable"] is True and d["D4"]["decidable"] is True
    assert "replay_divergence_above_cap:D1=17>16" in report["incomplete_reasons"]
    assert report["j12_am2_divergence"]["contrasts"]["D1"]["verdict"] == "over_cap"


def test_am2_a_divergent_key_plus_an_ordinary_crash_is_incomplete(tmp_path: Path):
    """(e) §B.3: any other residual crash keeps the arm, and so D1 / D3, incomplete."""
    dirs = _am2_family(tmp_path)
    _am2_crash(dirs["prefix_m6"], [AM2_KEY])
    _am2_crash(dirs["prefix_m6"], [("sc2_1", 2)], reason="replay_error")
    report, code = report_for(dirs)
    assert code == 1 and report["arms"]["prefix_m6"]["complete"] is False
    assert "incomplete_arm:prefix_m6 scored=22/24 crash=2 missing=0" in report["incomplete_reasons"]
    d = by_id(report)
    assert d["D1"]["verdict"] == d["D3"]["verdict"] == "refused_incomplete"
    assert report["j12_am2_divergence"]["per_arm"]["prefix_m6"]["n_crash_other"] == 1


# ---- R1 (2026-09-25): the J12 pre-read audit's findings ------------------------------------------------------
# REVERSED: d = +0.125 on sc0 and -0.5 on sc1-sc3. A scenario resample has a mean >= 0 only if all four draws are
# sc0 (1 / 256), so the 97.5th percentile is negative: the upper bound is below 0, a reversal, p (less) ~ 0.008.
REVERSED = dict(CONSTANT, prefix_m11={k: (0.75 if k[0].startswith("sc0") else 0.125) for k in KEYS})


def test_n1_a_reversal_carries_its_one_sided_less_p_unadjusted(tmp_path: Path):
    dirs = write_family(tmp_path, REVERSED, prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    d1, d3 = by_id(report)["D1"], by_id(report)["D3"]
    assert d1["decidable"] and d1["reversal_unadjusted"] is True and d1["contrast"]["scenario"]["ci95_pp"][1] < 0
    # Computed as j10_report.bootstrap_pvalue(..., direction="less") at 0 on the D's own scenario resamples.
    arms = {a: j10.a1_arm_episodes(a, j10.load_arm_tree(p), TASKS, list(SEEDS)) for a, p in dirs.items()}
    means = j10.a1_contrast(arms["prefix_m11"]["episodes"], arms["prefix_m6"]["episodes"], "goal_pass_rate",
                            n_boot=N_BOOT, seed=j10.A1_BOOTSTRAP_SEED)["scenario"]["_means"]
    assert d1["p_value_less_unadjusted"] == j10.bootstrap_pvalue(means, 0.0, "less")
    assert 0.0 < d1["p_value_less_unadjusted"] < 0.05
    assert d3["reversal_unadjusted"] is True and 0.0 < d3["p_value_less_unadjusted"] < 0.05
    assert "one-sided p (less)" in d1["verdict_sentence"] and d1["verdict_sentence"] in report["headline"]
    md = j12.render_markdown(report, "x.json")
    assert f"one-sided p (less), unadjusted: D1 {d1['p_value_less_unadjusted']}" in md
    assert "reported as a primary finding" in md
    # No reversal, no p (less): D2 is supported.
    assert "p_value_less_unadjusted" not in by_id(report)["D2"]


def test_n2_an_incomplete_d_draws_no_reversal_and_no_primary_finding(tmp_path: Path):
    dirs = write_family(tmp_path, REVERSED, prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H},
                        prefix_m6={"error_types": {("sc1_2", 2): "crash"}})
    report, code = report_for(dirs)
    d1 = by_id(report)["D1"]
    assert code == 1 and d1["verdict"] == "refused_incomplete"
    assert d1["contrast"]["scenario"]["ci95_pp"][1] < 0  # the interval would read a reversal ...
    assert d1["reversal_unadjusted"] is None and "p_value_less_unadjusted" not in d1  # ... but none is drawn
    assert report["readings"]["bplus"]["reversals_unadjusted"] == []
    assert "primary finding" not in j12.render_markdown(report, "x.json")


def test_n6_not_supported_is_printed_as_not_replicated(tmp_path: Path):
    # d = 0 everywhere on the tailored receiver: D1 and D3 are not supported (and no reversal).
    dirs = write_family(tmp_path, dict(CONSTANT, prefix_m11=0.625), prefix_m11={"handoff": ALL_H},
                        prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    assert report["verdicts"]["D1"] == "not_supported"  # the JSON value is unchanged
    assert "D1 not replicated" in report["headline"] and "not_supported" not in report["headline"]
    md = j12.render_markdown(report, "x.json")
    d1_row = next(x for x in md.splitlines() if x.startswith("| D1 |"))
    assert d1_row.endswith("| not replicated |") and "not_supported" not in md.split("## Readings")[0]


def test_n8_both_silenced_counts_are_printed_and_labelled(tmp_path: Path):
    # As test_d3_reads_h_star_*: m11's flag is true on 12 keys, h* on 18 (sc3's prefix was terminal).
    flag = {k: k[0].startswith(("sc0", "sc1")) for k in KEYS}
    live = {k for k in KEYS if not k[0].startswith("sc3")}
    dirs = write_family(tmp_path, CONSTANT, prefix_m11={"handoff": flag, "live": live},
                        prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    hs = report["beside"]["silenced_counts_h_star"]["prefix_m11"]
    assert (hs["n_handoff"], hs["n_no_handoff"], hs["h"]) == (18, 6, "h_star")
    assert report["beside"]["silenced_counts"]["prefix_m11"]["n_no_handoff"] == 12  # h_flag, as before
    md = j12.render_markdown(report, "x.json")
    assert ("- silenced count prefix_m11 (m = 11), by handoff_occurred: handoff 12, no handoff 12, flag missing 0; "
            "by h*: handoff 18, no handoff 6, h* undefined 0") in md


def test_n9_a_d3_on_the_boundary_prints_one_explicit_line():
    results = [{"id": "D1", "verdict": "supported"}, {"id": "D2", "verdict": "refused_incomplete"},
               {"id": "D3", "verdict": "on_boundary"}, {"id": "D4", "verdict": "supported"}]
    rd = j12.j12_readings(results)
    assert rd["bplus"]["reading"] is None
    assert rd["bplus"]["no_reading_reason"] == (
        "D1 supported, but the D1 / D3 pattern reading cannot apply: D3 is on_boundary, and J12 §4 fixes readings "
        "only for D3 supported or not replicated")
    assert rd["zs"]["no_reading_reason"].startswith("no fixed reading: D2 is refused_incomplete")
    results[2]["verdict"] = "refused_incomplete"
    assert "D3 is refused_incomplete" in j12.j12_readings(results)["bplus"]["no_reading_reason"]


def test_n10_a_disagreeing_sign_flip_is_in_the_verdicts_sentence_and_tgc_atoms_are_noted(tmp_path: Path):
    dirs = write_family(tmp_path, CONSTANT, prefix_m11={"handoff": ALL_H}, prefix_zs_m11={"handoff": ALL_H})
    report, _ = report_for(dirs)
    d1 = by_id(report)["D1"]
    # Four equal positive scenario sums: the exact two-sided sign-flip p is 2 / 16 = 0.125 > 0.05, while the
    # bootstrap interval [12.5, 12.5] excludes 0: they disagree, and the sentence says so beside "supported".
    assert d1["permutation_sensitivity"]["p_value"] == 0.125 and d1["verdict"] == "supported"
    sf = d1["signflip_disagreement"]
    assert (sf["agrees"], sf["bootstrap_side"], sf["signflip_side"], sf["level"]) == (False, "above", None, 0.05)
    assert d1["verdict_sentence"] == (
        "D1 supported; the scenario sign-flip p = 0.125 (two-sided) does not reject at 0.05 while the bootstrap "
        "interval excludes +0.00 pp (A1 §5.5; not decision-bearing)")
    assert d1["verdict_sentence"] in report["headline"]
    assert f"- {d1['verdict_sentence']}" in j12.render_markdown(report, "x.json")
    # An agreeing pair adds nothing; a rejecting sign-flip against an interval that includes 0 is a disagreement.
    agree = {"id": "D2", "decidable": True, "threshold_pp": 0.0, "verdict": "supported",
             "events_unadjusted": {"lo_above_threshold": True, "hi_below_threshold": False},
             "permutation_sensitivity": {"p_value": 0.01, "alternative": "two-sided"},
             "contrast": {"scenario": {"diff_pp": 3.0}}}
    assert j12.j12_signflip_disagreement(agree)["sentence"] is None
    assert j12.j12_verdict_sentence(dict(agree, signflip_disagreement=j12.j12_signflip_disagreement(agree))) == \
        "D2 supported"
    wide = dict(agree, events_unadjusted={"lo_above_threshold": False, "hi_below_threshold": False})
    assert "rejects at 0.05 while the bootstrap interval includes" in j12.j12_signflip_disagreement(wide)["sentence"]
    # TGC is 0.0 in every fixture episode: every TGC bound is 0.00 pp, the atom at the threshold. One note per D's
    # TGC row, naming every bound on the atom.
    notes = report["beside"]["tgc_atom_notes"]
    assert notes["D1"] == ("D1 TGC: the scenario lower and upper and the task lower and upper bounds sit on the atom "
                           "at the threshold 0 (A1 §5.2)")
    assert notes["D3"] == ("D3 TGC: the handoff-only scenario lower and upper, the handoff-only task lower and upper, "
                           "the all-episode scenario lower and upper and the all-episode task lower and upper bounds "
                           "sit on the atom at the threshold 0 (A1 §5.2)")
    md = j12.render_markdown(report, "x.json")
    assert all(md.count(notes[d]) == 1 for d in ("D1", "D2", "D3", "D4")) and md.count("(A1 §5.2)") == 4
    # Only the bounds on the atom are named; none on it, no note; a threshold other than 0 is not checked here.
    tgc = lambda s, t: {"scenario": {"ci95_pp": s}, "task": {"ci95_pp": t}}  # noqa: E731
    one = {"id": "D2", "threshold_pp": 0.0}
    assert j12.j12_tgc_atom_notes(one | {"tgc_secondary": tgc([0.004, 12.5], [-3.0, 5.0])}) == \
        "D2 TGC: the scenario lower bound sits on the atom at the threshold 0 (A1 §5.2)"
    assert j12.j12_tgc_atom_notes(one | {"tgc_secondary": tgc([-6.25, 0.0], [-0.001, 0.0])}) == \
        "D2 TGC: the scenario upper and the task lower and upper bounds sit on the atom at the threshold 0 (A1 §5.2)"
    assert j12.j12_tgc_atom_notes(one | {"tgc_secondary": tgc([0.01, 12.5], [-3.0, 5.0])}) is None
    assert j12.j12_tgc_atom_notes(one | {"threshold_pp": 7.0, "tgc_secondary": tgc([0.0, 0.0], [0.0, 0.0])}) is None


def test_n13_citations_name_the_committed_amendment_and_the_pin():
    assert not any("pending" in p["citation"] for p in j12.J12_PREDICTIONS)
    assert [p["citation"] for p in j12.J12_PREDICTIONS[2:]] == [f"{j12.J12_PREREG} §3-§4; h* per J12 Amendment 1"] * 2
    doc = j12.__doc__
    assert "pending" not in doc and "loop.py:743-756 at the arms' pin 6f40fec" in doc
    assert "j17_depth_fixes.py:329-346" in doc and "their own Holm" in doc


def test_n3_a_registered_read_without_arm3_is_refused_with_the_full_read_command(tmp_path: Path, capsys,
                                                                               monkeypatch):
    monkeypatch.setattr(j12, "J12_TEST_N_TASKS", len(TASKS))
    dirs = registered_family(tmp_path / "r", arm3=False)
    out = tmp_path / "r.report.json"
    code = j12.main(["--split", "test_normal", "--confirm-heldout-test-split", *_argv(dirs), "--out", str(out)])
    text = capsys.readouterr().out
    assert code == 2 and not out.exists()
    command = j12.j12_read_command(REG)
    assert command in json.loads(text)["reason"]
    assert command.startswith("python scripts/analysis/j12_report.py --split test_normal --confirm-heldout-test-split")
    for label in (*j12.J12_ARMS, PLAN):
        assert f"--arm {label}={j10.RAW_RESULTS_ROOT / REG[label]}" in command


def test_n3_n7_arm3_incomplete_or_planless_above_the_cap_is_not_run(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(j12, "J12_TEST_N_TASKS", len(TASKS))
    for case, arm3_kw, why in (
            ("crash", {"crash": {("sc2_2", 1)}}, "J10 arm 3 (planner_alone_cap81) is incomplete: 23/24 non-crashed"),
            ("planless", {"planless": {("sc0_1", 1), ("sc1_1", 2)}}, "2 planless arm-3 keys > cap 1")):
        report, code = registered_read(registered_family(tmp_path / case, arm3_kw=arm3_kw))
        assert code == 1 and report["status"] == "NOT_RUN", case
        assert report["headline"].startswith(f"J12 not run: {why}") and "Verdicts" not in report["headline"]
        assert report["verdicts"] == {d: "not_run" for d in ("D1", "D2", "D3", "D4")}
        assert report["label"].startswith("J12 NOT RUN") and report["not_the_j12_result"] is True
        assert by_id(report)["D1"]["computed_not_registered"]["verdict"] == "supported"  # kept, for diagnosis
        assert all(r["reading"] is None for r in report["readings"].values())
        md = j12.render_markdown(report, "x.json")
        assert "| supported |" not in md and "(h*: supported)" not in md
    assert report["planless_contingency"]["plan_source_arm"]["complete"] is True


def test_n4_a_registered_read_needs_seeds_1_2_and_168_tasks(tmp_path: Path):
    dirs = {label: tmp_path / REG[label] for label in (*j12.J12_ARMS, PLAN)}
    report, code = registered_read(dirs, seeds=[1], expected_n_tasks=168)
    assert code == 2 and "seeds [1]" in report["reason"]
    report, code = registered_read(dirs, seeds=[1, 2, 3], expected_n_tasks=168)
    assert code == 2 and "seeds [1, 2, 3]" in report["reason"]
    report, code = registered_read(dirs, expected_n_tasks=57)
    assert code == 2 and "--expected-n-tasks 57" in report["reason"] and "all 168 test_normal tasks" in report["reason"]


def test_n5_each_arm_is_read_only_from_its_registered_campaign(tmp_path: Path):
    # The ids are §2's table, read from the configs; arm 3's is J10's.
    assert REG == {"prefix_m6": "j12_prefix_m6_20260924", "prefix_zs_m6": "j12_prefix_zs_m6_20260924",
                   "prefix_m11": "j10_prefix_m11_20260924", "prefix_zs_m11": "j10_prefix_zs_m11_20260924",
                   PLAN: "j10_planner_alone_cap81_20260924"}
    good = {label: tmp_path / REG[label] for label in (*j12.J12_ARMS, PLAN)}
    for label, bad in (("prefix_m6", tmp_path / "prefix_m6"), ("prefix_m11", tmp_path / REG["prefix_zs_m11"]),
                       (PLAN, tmp_path / "j10_planner_alone_cap81_20260924_copy")):
        report, code = registered_read(dict(good, **{label: bad}), expected_n_tasks=168)
        assert code == 2 and f"on test_normal {label} is the registered campaign {REG[label]}" in report["reason"]


def test_refill_confirmation_gates_a_divergent_key_on_the_registered_read(tmp_path: Path, monkeypatch):
    """J12 Amendment 2 / A1 Amendment 5 §B.1: a divergent key counts only after a crash-only resumption run."""
    monkeypatch.setattr(j12, "J12_TEST_N_TASKS", len(TASKS))
    dirs = registered_family(tmp_path)
    _am2_crash(dirs["prefix_m11"], [AM2_KEY])
    report, code = registered_read(dirs)
    blk = report["j12_am2_divergence"]
    assert code == 1 and report["status"] == "INCOMPLETE"
    assert "divergent_keys_need_refill_confirmation:1" in report["incomplete_reasons"]
    assert blk["refill_confirmed_by_operator"] is False and blk["resumption_condition"]["required"] is True
    md = j12.render_markdown(report, "x.json")
    assert "INCOMPLETE until confirmed" in md and "--divergent-refill-confirmed" in md
    report, code = registered_read(dirs, divergent_refill_confirmed=True)
    assert code == 0 and report["status"] == "COMPLETE", report["headline"]
    assert report["j12_am2_divergence"]["refill_confirmed_by_operator"] is True
    assert by_id(report)["D1"]["n_noncrashed_pairs"] == 23
    # No divergent key: the flag is irrelevant.
    report, code = registered_read(registered_family(tmp_path / "clean"))
    assert code == 0 and report["j12_am2_divergence"]["refill_confirmed_by_operator"] is None
