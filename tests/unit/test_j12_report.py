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
              live_asks: dict | None = None, other_provider_asks: dict | None = None) -> Path:
    """One arm in runner layout. goal_pass: a value or {(task, seed): value}. handoff: the system
    `report` event's handoff_occurred per key. live_asks: codex-answered asks per key."""
    arm_root = root / label
    for task_id, seed in KEYS:
        key = (task_id, seed)
        dest = arm_root / "prefix_handoff" / str(seed) / task_id
        dest.mkdir(parents=True, exist_ok=True)
        events = [{"event_type": "run_start", "payload": {}}]
        if handoff is not None and key in handoff:
            events.append({"event_type": "report", "actor": "system",
                           "payload": {"handoff_occurred": handoff[key], "effective_m": 6}})
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
    data = json.loads((REPO / j12.J12_DEV_REPORT).read_text(encoding="utf-8"))
    for p in j12.J12_PREDICTIONS:
        ref = p["dev_reference"]
        node = data
        for part in ref["key"].split("."):
            node = node[part]
        assert ref["diff_pp"] == round(node["diff_pp"], 2), p["id"]
        assert ref["ci95_pp_scenario"] == [round(v, 2) for v in node["ci95_pp_scenario"]], p["id"]
        pairing = data["handoff_only_contrasts"][p["receiver"]]["m6_to_m11"]["goal_pass"]["pairing"]
        assert ref["n_pairs"] == pairing["n_pairs"]
        if p["kind"] == "handoff_only":
            assert ref["n_handoff"] == node["n_pairs"] == pairing["n_handoff"]


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


def test_confirmed_test_normal_read_writes_the_json_and_the_md(tmp_path: Path, capsys):
    kw = {a: {"manifest_split": "test_normal"} for a in j12.J12_ARMS}
    kw["prefix_m11"]["handoff"] = ALL_H
    kw["prefix_zs_m11"]["handoff"] = ALL_H
    dirs = write_family(tmp_path / "t", CONSTANT, **kw)
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
