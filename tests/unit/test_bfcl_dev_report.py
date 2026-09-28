"""Tests for scripts/analysis/bfcl_dev_report.py (the BFCL dev read, dev prereg §6).

Every fixture is a synthetic campaign laid out as a real BFCL episode is
(<results>/<campaign>/<system>/<seed>/<entry>/{result.json, events.jsonl, manifest.json}, as spike b's
bfcl_executor_alone_zs_dev_20260924 holds them), and every asserted number is computed by hand in the
comment beside it.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Optional

import pytest

from scripts.analysis import bfcl_dev_report as dr
from scripts.analysis.j10_report import _load_j12, cluster_bootstrap_means
from scripts.setup.hj1_gate import scenario_of

N_BOOT = 1000


# ---- fixture writers -----------------------------------------------------------------------------
def _ev(run_id: str, entry: str, system: str, seed: int, step: int, actor: str, etype: str,
        payload: Optional[dict[str, Any]] = None, usage: Optional[dict[str, Any]] = None,
        error: Optional[str] = None) -> dict[str, Any]:
    return {"run_id": run_id, "task_id": entry, "system": system, "seed": seed, "step": step,
            "ts": "2026-09-24T11:56:08.067047+00:00", "actor": actor, "event_type": etype,
            "payload": payload or {}, "usage": usage, "env_state_hash": "0" * 64, "error_type": error}


def write_episode(
    root: Path,
    arm: str,
    entry: str,
    seed: int,
    gp: Optional[float],
    *,
    success: Optional[bool] = None,
    error_type: Optional[str] = None,
    system: str = "executor_alone",
    n_planner_calls: int = 0,
    ledger_calls: int = 0,
    cache_events: int = 0,
    prefix: Optional[dict[str, Any]] = None,
) -> Path:
    """One episode directory. prefix: {"eff": m, "n_src": n, "flag": bool|None, "live": bool,
    "record": bool} writes the prefix system's handoff record and, if live, a live executor step."""
    cid = f"bfcl_{arm}_dev_20260924"
    ep = root / cid / system / str(seed) / entry
    ep.mkdir(parents=True, exist_ok=True)
    run_id = f"{cid}/{system}/{seed}/{entry}"
    if success is None:
        success = gp == 1.0
    result = {
        "error_type": error_type, "goal_pass_rate": gp, "n_asks": 0, "n_interventions": 0,
        "n_planner_calls": n_planner_calls, "run_id": run_id, "seed": seed, "sgc": None, "steps": 12,
        "success": success, "system": system, "task_id": entry, "tgc": 1.0 if success else 0.0,
        "totals": {"executor_tokens_total": 1000, "gpu_seconds_total": 1.0,
                   "per_actor": {"executor": {"n_calls": 12}}, "planner_calls_total": ledger_calls,
                   "planner_tokens_total": 0, "usd_total": 0.0},
    }
    events = [_ev(run_id, entry, system, seed, 0, "system", "run_start", {"limits": {"max_steps": 40}}),
              _ev(run_id, entry, system, seed, 0, "environment", "observation", {"text": "hi", "done": False})]
    for _ in range(cache_events):
        events.append(_ev(run_id, entry, system, seed, 0, "planner", "plan", {"plan": "cached"},
                          usage={"model": "gpt-5.6-luna", "provider": "cache", "input_tokens": 0,
                                 "output_tokens": 0, "n_calls": 1}))
    last = 1
    if prefix is not None:
        eff = prefix["eff"]
        for s in range(1, eff + 1):
            events.append(_ev(run_id, entry, system, seed, s, "planner", "action", {"kind": "CODE", "code": "ls()"},
                              usage={"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 10,
                                     "output_tokens": 1, "n_calls": 1}))
        if prefix.get("record", True):
            events.append(_ev(run_id, entry, system, seed, eff, "system", "report",
                              {"effective_m": eff, "n_source_actions": prefix["n_src"],
                               "handoff_occurred": prefix["flag"], "source_campaign": "src"}))
        last = eff
        if prefix["live"]:
            last = eff + 1
            events.append(_ev(run_id, entry, system, seed, last, "executor", "action", {"kind": "CODE", "code": "pwd()"},
                              usage={"model": "ibm-granite/granite-4.2-8b", "provider": "vllm", "n_calls": 1}))
    else:
        events.append(_ev(run_id, entry, system, seed, 1, "executor", "action", {"kind": "CODE", "code": "pwd()"},
                          usage={"model": "ibm-granite/granite-4.2-8b", "provider": "vllm", "n_calls": 1}))
    events.append(_ev(run_id, entry, system, seed, last, "environment", "evaluate",
                      {"success": success, "goal_pass_rate": gp}))
    events.append(_ev(run_id, entry, system, seed, last, "system", "run_end", {}, error=error_type))
    (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (ep / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (ep / "manifest.json").write_text(json.dumps({"campaign_id": cid, "run_id": run_id, "seed": seed,
                                                  "task_id": entry, "system": system}), encoding="utf-8")
    return ep


def write_configs(configs: Path, arms=dr.EXPECTED_ARMS) -> Path:
    configs.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        (configs / f"bfcl_{arm}.yaml").write_text(f"env: bfcl\ncampaign_id: bfcl_{arm}_dev_20260924\n",
                                                  encoding="utf-8")
    return configs


def prefix_spec(live: bool, flag: Optional[bool], record: bool = True) -> dict[str, Any]:
    return {"eff": 6, "n_src": 8, "flag": flag, "live": live, "record": record}


@pytest.fixture(scope="module")
def report(tmp_path_factory) -> dict[str, Any]:
    """One synthetic dev tree for the P6 / B1 / did cases; every other arm is absent."""
    base = tmp_path_factory.mktemp("bfclroot")
    root, configs = base / "results", write_configs(base / "configs")
    # P6 = takeover_k5 - advise_k5_fullctx (seed 1). Calls: 3 published, ledger 3, one cached plan.
    kw = dict(system="fixed_k", n_planner_calls=3, ledger_calls=3, cache_events=1)
    for entry, t_gp, t_err in (("multi_turn_base_1", 0.5, None), ("multi_turn_base_2", 1.0, None),
                               ("multi_turn_base_3", 0.0, None), ("multi_turn_base_4", 0.5, None),
                               ("multi_turn_base_5", 0.0, "limit")):
        write_episode(root, "takeover_k5", entry, 1, t_gp, error_type=t_err, **kw)
    for entry, a_gp, a_err in (("multi_turn_base_1", 0.25, None), ("multi_turn_base_2", 0.5, None),
                               ("multi_turn_base_3", None, "crash"), ("multi_turn_base_5", 0.5, None)):
        write_episode(root, "advise_k5_fullctx", entry, 1, a_gp, error_type=a_err, **kw)
    # P6_qzs: constant +0.10 on the same entries 1, 2, 5.
    for entry in ("multi_turn_base_1", "multi_turn_base_2", "multi_turn_base_5"):
        write_episode(root, "takeover_k5_qzs", entry, 1, 0.6, system="fixed_k")
        write_episode(root, "advise_k5_fullctx_qzs", entry, 1, 0.5, system="fixed_k")
    # B1: prefix_zs_m6 - planner_alone_cap81, d = 0.2, -0.4, 0.6, 1.0;
    # h* = 1, 1, 0 (terminal), missing (no handoff record); h_flag = True, False, True, None.
    for entry, p_gp, c_gp, pre in (("multi_turn_base_1", 0.7, 0.5, prefix_spec(True, True)),
                                   ("multi_turn_base_2", 0.1, 0.5, prefix_spec(True, False)),
                                   ("multi_turn_base_3", 0.8, 0.2, prefix_spec(False, True)),
                                   ("multi_turn_base_4", 1.0, 0.0, prefix_spec(False, None, record=False))):
        write_episode(root, "prefix_zs_m6", entry, 1, p_gp, system="prefix_handoff", prefix=pre)
        write_episode(root, "planner_alone_cap81", entry, 1, c_gp, system="planner_alone", n_planner_calls=12,
                      ledger_calls=12)
    # Entry clustering: plan_zs - executor_alone_zs, two entries x two seeds, d = +1 on entry 1, 0 on entry 2.
    for seed in (1, 2):
        write_episode(root, "plan_zs", "multi_turn_base_1", seed, 1.0, system="prompt_only")
        write_episode(root, "executor_alone_zs", "multi_turn_base_1", seed, 0.0)
        write_episode(root, "plan_zs", "multi_turn_base_2", seed, 0.5, system="prompt_only")
        write_episode(root, "executor_alone_zs", "multi_turn_base_2", seed, 0.5)
    return dr.build_report(root, configs, n_boot=N_BOOT, seed=dr.SEED)


# ---- pairing, crash drops, error types as outcomes ------------------------------------------------
def test_paired_difference_drops_the_crash_and_the_missing_side(report):
    p6 = report["contrasts"]["P6"]["goal_pass"]
    assert (p6["left"], p6["right"]) == ("takeover_k5", "advise_k5_fullctx")
    # pairs: e1 0.5-0.25 = 0.25, e2 1.0-0.5 = 0.5, e5 (limit, stays) 0.0-0.5 = -0.5; e3 crash, e4 no right.
    assert p6["n_pairs"] == 3
    assert p6["n_dropped"] == 2
    assert p6["dropped"] == {"left_missing": 0, "right_missing": 1, "crash": 1, "metric_missing": 0}
    assert p6["diff_pp"] == 8.33  # (0.25 + 0.5 - 0.5) / 3 = 0.08333
    assert p6["sd_pp"] == pytest.approx(52.042, abs=1e-3)  # sqrt(((1/6)^2 + (5/12)^2 + (7/12)^2) / 2)
    assert p6["n_clusters"] == 3
    assert p6["left_mean"] == pytest.approx(0.5)  # (0.5 + 1.0 + 0.0) / 3
    assert p6["exploratory"] is True
    lo, hi = p6["ci95_entry"]
    assert lo <= p6["diff_pp"] <= hi


def test_arm_block_counts(report):
    t = report["arms"]["takeover_k5"]
    assert t["n"] == 5 and t["n_crash"] == 0 and t["seeds"] == [1]
    assert t["limit_rate"] == pytest.approx(0.2)  # 1 limit of 5 non-crash
    assert t["error_types"] == {"limit": 1, "none": 4}
    assert t["goal_pass_mean"] == pytest.approx(0.4)  # (0.5 + 1 + 0 + 0.5 + 0) / 5
    a = report["arms"]["advise_k5_fullctx"]
    assert a["n"] == 4 and a["n_crash"] == 1
    assert a["goal_pass_mean"] == pytest.approx((0.25 + 0.5 + 0.5) / 3)
    assert a["error_types"] == {"crash": 1, "none": 3}
    # Neither is complete: 5 and 3 non-crash episodes against 150 expected, and advise has a crash.
    assert t["n_expected"] == 150 and t["complete"] is False
    assert a["complete"] is False and "1 crashed" in a["complete_reason"]


def test_calls_live_subtracts_the_cached_plan_and_attributed_is_published(report):
    t = report["arms"]["takeover_k5"]
    assert t["calls_ledger_mean"] == 3.0
    assert t["calls_live_mean"] == 2.0  # ledger 3 - one cached plan record charged 1
    assert t["calls_live_reason"] is None
    assert t["calls_attributed_mean"] == 3.0  # result.json n_planner_calls
    assert t["n_cached_plan_events"] == 5
    c = report["arms"]["planner_alone_cap81"]
    assert c["calls_live_mean"] == 12.0 and c["calls_attributed_mean"] == 12.0


def test_negative_live_count_nulls_the_mean_instead_of_clamping(tmp_path):
    kw = dict(system="fixed_k", cache_events=1)
    write_episode(tmp_path, "takeover_k5", "multi_turn_base_1", 1, 0.5, n_planner_calls=3, ledger_calls=3, **kw)
    # Ledger 0 but one cached record charged 1: live would be -1.
    write_episode(tmp_path, "takeover_k5", "multi_turn_base_2", 1, 0.5, n_planner_calls=1, ledger_calls=0, **kw)
    block = dr.arm_block(dr.load_arm(tmp_path, "takeover_k5"))
    assert block["calls_live_mean"] is None
    assert block["calls_live_reason"].startswith("1 non-crash episodes")
    assert block["calls_ledger_mean"] == 1.5  # (3 + 0) / 2, reported as is
    assert block["calls_attributed_mean"] == 2.0  # (3 + 1) / 2


def test_completeness_gate_labels_but_never_refuses(tmp_path):
    root, configs = tmp_path / "results", write_configs(tmp_path / "configs")
    for i in range(1, 51):
        entry = f"multi_turn_base_{i}"
        for s in (1, 2, 3):
            write_episode(root, "executor_alone_zs", entry, s, 0.5)
            write_episode(root, "plan_zs", entry, s, 0.75, system="prompt_only")
        for s in (1, 2):  # executor_alone_bplus ran seeds 1-2 only
            write_episode(root, "executor_alone_bplus", entry, s, 0.25)
    rep = dr.build_report(root, configs, n_boot=50, seed=1)
    zs, bplus = rep["arms"]["executor_alone_zs"], rep["arms"]["executor_alone_bplus"]
    assert (zs["n"], zs["n_expected"], zs["complete"], zs["complete_reason"]) == (150, 150, True, None)
    assert (bplus["n"], bplus["n_expected"], bplus["complete"]) == (100, 150, False)
    assert "100 non-crash episodes < 150" in bplus["complete_reason"] and "seed 3: 0/50" in bplus["complete_reason"]
    plan, tailor = rep["contrasts"]["plan_zs"], rep["contrasts"]["tailor_bplus_zs"]
    assert plan["complete"] is True and plan["complete_reason"] is None
    assert tailor["complete"] is False and "executor_alone_bplus" in tailor["complete_reason"]
    # The incomplete contrast is still read: seeds 1-2 pair, seed 3 is dropped as left-missing.
    assert tailor["goal_pass"]["n_pairs"] == 100 and tailor["goal_pass"]["dropped"]["left_missing"] == 50
    assert tailor["goal_pass"]["diff_pp"] == -25.0
    assert rep["contrasts"]["did_plan"]["complete"] is False  # plan_qzs and executor_alone_qzs absent
    meta = rep["meta"]
    assert meta["seeds"] == [1, 2, 3] and meta["n_expected_per_arm"] == 150
    assert meta["all_arms_complete"] is False and "executor_alone_bplus" in meta["arms_incomplete"]
    assert "executor_alone_zs" not in meta["arms_incomplete"]
    lines = dr.summary_lines(rep)
    assert "INCOMPLETE" in next(x for x in lines if x.startswith("executor_alone_bplus"))
    assert "INCOMPLETE" not in next(x for x in lines if x.startswith("executor_alone_zs "))
    assert all("INCOMPLETE" in x for x in lines if x.startswith("tailor_bplus_zs"))
    assert not any("INCOMPLETE" in x for x in lines if x.startswith("plan_zs "))
    # Requested seeds 1-2 only: 100 expected, and bplus is complete.
    rep12 = dr.build_report(root, configs, n_boot=50, seed=1, seeds=(1, 2))
    assert rep12["meta"]["seeds"] == [1, 2] and rep12["arms"]["executor_alone_bplus"]["n_expected"] == 100
    assert rep12["arms"]["executor_alone_bplus"]["complete"] is True
    assert rep12["arms"]["executor_alone_zs"]["n"] == 100
    assert rep12["contrasts"]["tailor_bplus_zs"]["complete"] is True


def test_cached_record_rule_matches_j12(tmp_path):
    ep = write_episode(tmp_path, "takeover_k5", "multi_turn_base_9", 1, 0.5, system="fixed_k",
                       n_planner_calls=4, ledger_calls=4, cache_events=2)
    events = [json.loads(line) for line in (ep / "events.jsonl").read_text().splitlines()]
    n_rec, calls = dr.cache_plan_calls(events)
    j12_usages = _load_j12().cached_plan_usages(ep / "events.jsonl")
    assert n_rec == len(j12_usages) == 2
    assert calls == sum(int(u.get("n_calls") or 1) for u in j12_usages) == 2


# ---- entry clustering ------------------------------------------------------------------------------
def test_two_seeds_of_one_entry_move_together(report):
    plan = report["contrasts"]["plan_zs"]["goal_pass"]
    assert plan["n_pairs"] == 4
    assert plan["n_clusters"] == 2  # entries, not 1 (scenario_of) and not 4 (entry x seed)
    assert plan["diff_pp"] == 50.0
    # scenario_of would put every BFCL id in one cluster.
    assert scenario_of("multi_turn_base_1") == scenario_of("multi_turn_base_2") == "multi_turn_base"
    keys = [("multi_turn_base_1", 1), ("multi_turn_base_1", 2), ("multi_turn_base_2", 1), ("multi_turn_base_2", 2)]
    means = cluster_bootstrap_means([1.0, 1.0, 0.0, 0.0], dr.entry_labels(keys), n_boot=2000, seed=dr.SEED)
    # Both seeds of an entry are drawn together: a replicate mean is 0, 1/2 or 1, never 1/4 or 3/4.
    assert set(means) <= {0.0, 0.5, 1.0}
    assert len(set(means)) == 3


def test_generic_bootstrap_draws_like_j10():
    keys = [(f"multi_turn_base_{i}", s) for i in range(1, 8) for s in (1, 2)]
    diffs = [((i * 7 + s * 3) % 5) / 10.0 for i in range(1, 8) for s in (1, 2)]
    ref = cluster_bootstrap_means(diffs, dr.entry_labels(keys), n_boot=500, seed=7)
    groups: dict[str, list[float]] = {}
    for k, d in zip(keys, diffs):
        g = groups.setdefault(k[0], [0.0, 0.0])
        g[0] += d
        g[1] += 1

    def mean(drawn):
        return sum(groups[x][0] for x in drawn) / sum(groups[x][1] for x in drawn)

    mine = dr.cluster_bootstrap_stat(groups, mean, n_boot=500, seed=7)
    assert mine == pytest.approx(ref, abs=1e-12)


# ---- B1 handoff-only ----------------------------------------------------------------------------
def test_b1_ratio_with_a_missing_hstar(report):
    b1 = report["contrasts"]["B1_zs_m6_hstar"]["goal_pass"]
    # h* = 1, 1, 0, missing(->0): (0.2 - 0.4) / 2 = -0.1
    assert b1["diff_pp"] == -10.0
    assert b1["n_handoff"] == 2
    assert b1["n_h_missing"] == 1
    assert b1["n_pairs"] == 4 and b1["n_clusters"] == 4
    assert b1["margin_pp"] == -7.0 and "p_ni" in b1 and "lower_above_margin" in b1
    flag = report["contrasts"]["B1_zs_m6_flag"]["goal_pass"]
    # h_flag = True, False, True, None(->0): (0.2 + 0.6) / 2 = 0.4
    assert flag["diff_pp"] == 40.0
    assert flag["n_handoff"] == 2 and flag["n_h_missing"] == 1
    arm = report["arms"]["prefix_zs_m6"]
    assert (arm["hstar_true"], arm["hstar_false"], arm["hstar_missing"]) == (2, 1, 1)
    assert (arm["h_flag_true"], arm["h_flag_false"], arm["h_flag_missing"]) == (2, 1, 1)


def test_b1_bootstrap_resamples_entries_and_recomputes_the_ratio():
    keys = [("multi_turn_base_1", 1), ("multi_turn_base_2", 1)]
    series = {"keys": keys, "diffs": [0.3, -0.1], "n_dropped": 0, "dropped": {}}
    block, why = dr.handoff_metric(series, {keys[0]: True, keys[1]: True}, n_boot=4000, seed=1)
    assert why is None
    assert block["diff_pp"] == 10.0  # (0.3 - 0.1) / 2
    assert block["ci95_entry"] == [-10.0, 30.0]  # replicates are -0.1, 0.1 or 0.3
    none, why = dr.handoff_metric(series, {keys[0]: False}, n_boot=10, seed=1)
    assert none is None and "sum of h = 0" in why


# ---- depth, handoff-only (E-prereg family D: D3, D4 and their flag sensitivity) --------------------
def _depth_tree(base: Path) -> tuple[Path, Path]:
    """prefix_bplus_m6 − prefix_bplus_m2 at seed 1, d = 0.5, -0.2, 1.0, 0.4.

    Left (m6) h* = 1, 1, 0 (terminal), missing (no handoff record); left h_flag = True, False, True, None.
    The right (m2) arm has h* = 1 on every entry, so a row that took h from the right would count all four.
    """
    root, configs = base / "results", write_configs(base / "configs")
    for entry, m6_gp, m2_gp, pre in (("multi_turn_base_1", 0.9, 0.4, prefix_spec(True, True)),
                                     ("multi_turn_base_2", 0.3, 0.5, prefix_spec(True, False)),
                                     ("multi_turn_base_3", 1.0, 0.0, prefix_spec(False, True)),
                                     ("multi_turn_base_4", 0.6, 0.2, prefix_spec(False, None, record=False))):
        write_episode(root, "prefix_bplus_m6", entry, 1, m6_gp, system="prefix_handoff", prefix=pre)
        write_episode(root, "prefix_bplus_m2", entry, 1, m2_gp, system="prefix_handoff",
                      prefix={"eff": 2, "n_src": 8, "flag": True, "live": True, "record": True})
    return root, configs


def test_depth_hstar_takes_h_from_the_left_m6_arm(tmp_path):
    rep = dr.build_report(*_depth_tree(tmp_path), n_boot=N_BOOT, seed=dr.SEED)
    row = rep["contrasts"]["depth_bplus_hstar"]
    assert (row["left"], row["right"], row["kind"], row["h_arm"]) == (
        "prefix_bplus_m6", "prefix_bplus_m2", "hstar", "prefix_bplus_m6")
    gp = row["goal_pass"]
    # Left h* = 1, 1, 0, missing(->0): (0.5 - 0.2) / 2 = 0.15. The terminal e3 (left h* = 0, right h* = 1)
    # does not count; with h from the right arm it would be (0.5 - 0.2 + 1.0 + 0.4) / 4 = 0.425.
    assert gp["diff_pp"] == 15.0
    assert gp["n_handoff"] == 2 and gp["n_h_missing"] == 1
    assert gp["n_pairs"] == 4 and gp["n_clusters"] == 4 and gp["n_dropped"] == 0
    assert gp["sd_pp"] == pytest.approx(49.497, abs=1e-3)  # stdev(0.5, -0.2) = 0.7 / sqrt(2)
    # Judged at 0: no NI fields (B1 keeps them).
    assert "margin_pp" not in gp and "p_ni" not in gp and "lower_above_margin" not in gp
    assert gp["p_two_sided"] is not None
    flag = rep["contrasts"]["depth_bplus_flag"]
    assert flag["kind"] == "flag" and flag["h_arm"] == "prefix_bplus_m6"
    # Left h_flag = True, False, True, None(->0): (0.5 + 1.0) / 2 = 0.75.
    assert flag["goal_pass"]["diff_pp"] == 75.0
    assert flag["goal_pass"]["n_handoff"] == 2 and flag["goal_pass"]["n_h_missing"] == 1
    # D1's dev value is the plain depth row over every pair: (0.5 - 0.2 + 1.0 + 0.4) / 4 = 0.425.
    assert rep["contrasts"]["depth_bplus"]["goal_pass"]["diff_pp"] == 42.5
    # The zs pair is absent here: its rows are null with a reason naming the arm.
    for cid in ("depth_zs_hstar", "depth_zs_flag"):
        assert rep["contrasts"][cid]["goal_pass"] is None and "prefix_zs_m2" in rep["contrasts"][cid]["reason"]


def test_depth_handoff_interval_by_hand():
    keys = [("multi_turn_base_1", 1), ("multi_turn_base_2", 1), ("multi_turn_base_3", 1)]
    series = {"keys": keys, "diffs": [0.3, -0.1, 0.9], "n_dropped": 0, "dropped": {}}
    # The third pair has h = 0, so its entry holds no weight. A replicate without entry 1 is -0.1 and one
    # without entry 2 is 0.3, each (2/3)^3 - (1/3)^3 = 7/27 of the draws, so the 2.5 % and 97.5 % order
    # statistics sit on them; drawing entry 3 three times (1/27) gives Σh = 0 and the replicate is dropped.
    block, why = dr.handoff_metric(series, {keys[0]: True, keys[1]: True, keys[2]: False}, n_boot=4000, seed=1,
                                   ni=False)
    assert why is None
    assert block["diff_pp"] == 10.0  # (0.3 - 0.1) / 2
    assert block["ci95_entry"] == [-10.0, 30.0]
    assert block["n_handoff"] == 2 and block["n_pairs"] == 3
    assert "margin_pp" not in block
    assert 0 < 4000 - block["n_boot_valid"] < 400  # about 4000 / 27 = 148 dropped


def test_depth_rows_are_appended_and_leave_every_earlier_row_unchanged(tmp_path, monkeypatch):
    new = ["depth_bplus_hstar", "depth_zs_hstar", "depth_bplus_flag", "depth_zs_flag"]
    assert list(dr.CONTRASTS)[-4:] == new
    assert dr.CONTRASTS["depth_bplus"] == dict(left="prefix_bplus_m6", right="prefix_bplus_m2", kind="depth",
                                               m4="prefix_bplus_m4")
    root, configs = _depth_tree(tmp_path)
    for i, c_gp in ((1, 0.5), (2, 0.25), (3, 0.75), (4, 0.0)):  # so B1_bplus_* and P3_bplus_m6 are computed
        write_episode(root, "planner_alone_cap81", f"multi_turn_base_{i}", 1, c_gp, system="planner_alone")
    with_d = dr.build_report(root, configs, n_boot=300, seed=dr.SEED)
    assert with_d["contrasts"]["B1_bplus_m6_hstar"]["goal_pass"] is not None
    monkeypatch.setattr(dr, "CONTRASTS", {k: v for k, v in dr.CONTRASTS.items() if k not in new})
    without = dr.build_report(root, configs, n_boot=300, seed=dr.SEED)
    assert set(with_d["contrasts"]) - set(without["contrasts"]) == set(new)
    for cid, block in without["contrasts"].items():
        assert with_d["contrasts"][cid] == block, cid
    assert with_d["arms"] == without["arms"]


# ---- non-inferiority fields ------------------------------------------------------------------------
def _series(diffs: list[float]) -> dict[str, Any]:
    keys = [(f"multi_turn_base_{i}", 1) for i in range(len(diffs))]
    return {"keys": keys, "diffs": diffs, "left": diffs, "right": [0.0] * len(diffs), "n_dropped": 0,
            "dropped": {}}


def test_ni_fields_at_minus_seven():
    inside = dr.plain_metric(_series([-0.05] * 5), n_boot=500, seed=1, ni=True)
    assert inside["margin_pp"] == -7.0
    assert inside["ci95_entry"] == [-5.0, -5.0]
    assert inside["lower_above_margin"] is True
    assert inside["p_ni"] == 0.0  # 2 x share of replicates <= -0.07 = 0
    outside = dr.plain_metric(_series([-0.10] * 5), n_boot=500, seed=1, ni=True)
    assert outside["lower_above_margin"] is False
    assert outside["p_ni"] == 1.0  # 2 x 1, capped at 1
    plain = dr.plain_metric(_series([-0.05] * 5), n_boot=100, seed=1)
    assert "margin_pp" not in plain


def test_p3_row_carries_the_ni_fields(report):
    p3 = report["contrasts"]["P3_zs_m6"]
    assert p3["kind"] == "ni" and p3["goal_pass"]["margin_pp"] == -7.0
    assert p3["goal_pass"]["diff_pp"] == 35.0  # (0.2 - 0.4 + 0.6 + 1.0) / 4, every pair


# ---- difference-in-differences ----------------------------------------------------------------------
def test_did_is_the_zs_contrast_minus_its_qzs_repeat(report):
    did = report["contrasts"]["did_P6"]["goal_pass"]
    # P6 = 8.33 pp over e1, e2, e5; P6_qzs = +10 pp on the same entries.
    assert did["zs_diff_pp"] == 8.33 and did["qzs_diff_pp"] == 10.0
    assert did["diff_pp"] == -1.67
    assert did["n_clusters"] == 3 and did["n_clusters_common"] == 3


def test_did_interval_by_hand():
    zs = _series([0.4, 0.2])
    q = _series([0.1, 0.1])
    block, why = dr.did_metric(zs, q, n_boot=4000, seed=3)
    assert why is None
    assert block["diff_pp"] == 20.0
    # Two entries: replicates are 0.3 (e0 twice), 0.2 (one of each) or 0.1 (e1 twice).
    assert block["ci95_entry"] == [10.0, 30.0]


# ---- absence ---------------------------------------------------------------------------------------
def test_absent_arms_and_contrasts_are_null_with_a_reason(report):
    cf3 = report["contrasts"]["CF3"]  # advise_k5_neutral absent
    assert cf3["goal_pass"] is None and cf3["success"] is None
    assert "advise_k5_neutral" in cf3["reason"]
    arm = report["arms"]["advise_k5_neutral"]
    assert arm["present"] is False and arm["n"] is None and "absent" in arm["reason"]
    depth = report["contrasts"]["depth_zs"]  # prefix_zs_m2 absent
    assert depth["goal_pass"] is None and "prefix_zs_m2" in depth["reason"]
    assert depth["arm_means"]["m6"]["goal_pass_mean"] == pytest.approx(0.65)  # (0.7 + 0.1 + 0.8 + 1.0) / 4
    assert depth["arm_means"]["m4"]["goal_pass_mean"] is None and depth["m4_reason"]
    did = report["contrasts"]["did_depth"]
    assert did["goal_pass"] is None and did["reason"]
    assert "bfcl_advise_k5_neutral_dev_20260924" in report["meta"]["campaigns_absent"]
    assert report["meta"]["cluster_unit"] == "entry"
    assert report["meta"]["n_boot"] == N_BOOT and report["meta"]["seed"] == dr.SEED


def test_only_executor_alone_present(tmp_path):
    root, configs = tmp_path / "results", write_configs(tmp_path / "configs")
    for i in (1, 2):
        for s in (1, 2):
            write_episode(root, "executor_alone_zs", f"multi_turn_base_{i}", s, 0.5)
    rep = dr.build_report(root, configs, n_boot=50, seed=1)
    assert rep["arms"]["executor_alone_zs"]["n"] == 4
    for arm, block in rep["arms"].items():
        if arm != "executor_alone_zs":
            assert block["n"] is None and block["reason"], arm
    for cid, block in rep["contrasts"].items():
        assert block["goal_pass"] is None and block["reason"], cid
    assert rep["meta"]["campaigns_found"] == ["bfcl_executor_alone_zs_dev_20260924"]


def test_real_configs_name_their_campaigns():
    configured = dr.configured_arms(dr.CONFIGS_DIR)
    assert set(configured) == set(dr.EXPECTED_ARMS)
    assert all(cid == f"bfcl_{arm}_dev_20260924" for arm, cid in configured.items())


# ---- refusals --------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["/r/bfcl_x/test_normal/1", "/r/test_challenge/x", "/r/bfcl_takeover_k5_test_20260925"])
def test_refuse_heldout_markers(path):
    with pytest.raises(RuntimeError):
        dr.refuse_path(path)


def test_refuse_campaign_without_dev():
    with pytest.raises(RuntimeError):
        dr.refuse_campaign("bfcl_takeover_k5_20260924")
    with pytest.raises(RuntimeError):
        dr.refuse_campaign("bfcl_takeover_k5_test_20260925")
    dr.refuse_campaign("bfcl_takeover_k5_dev_20260924")


def test_config_with_a_wrong_campaign_id_is_refused(tmp_path):
    (tmp_path / "bfcl_takeover_k5.yaml").write_text("campaign_id: bfcl_takeover_k5_test_20260925\n")
    with pytest.raises(ValueError):
        dr.configured_arms(tmp_path)


def test_heldout_result_path_is_refused(tmp_path):
    ep = tmp_path / "bfcl_takeover_k5_dev_20260924" / "fixed_k" / "test_normal" / "multi_turn_base_1"
    ep.mkdir(parents=True)
    (ep / "result.json").write_text(json.dumps({"task_id": "multi_turn_base_1", "seed": 1}))
    with pytest.raises(RuntimeError):
        dr.load_arm(tmp_path, "takeover_k5")


def test_heldout_root_and_out_are_refused(tmp_path):
    configs = write_configs(tmp_path / "configs")
    with pytest.raises(RuntimeError):
        dr.build_report(tmp_path / "bfcl_x_test_y", configs, n_boot=10, seed=1)
    with pytest.raises(RuntimeError):
        dr.main(["--root", str(tmp_path), "--configs", str(configs), "--out", str(tmp_path / "a_test_b.json")])
