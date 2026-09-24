"""Tests for the J17 depth fixes (scripts/analysis/j17_depth_fixes.py).

Fixtures are synthetic and scripted so the right answer is known by arithmetic. Where every
scenario has the same composition, every scenario resample gives the same statistic, so the
scenario interval collapses onto the hand-computed point as well.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j17_depth_fixes as j17

# Two scenarios x three tasks x two seeds = 12 episodes; scenario_of splits on the last "_".
KEYS = [(f"s{s}_{t}", seed) for s in (1, 2) for t in (1, 2, 3) for seed in (1, 2)]
CONTRACT_KEYS = {"diff_pp", "ci95_pp_scenario", "ci95_pp_task", "p_two_sided", "threshold_pp",
                 "n_pairs", "metric"}


def row(value: float, *, handoff=None, error_type=None, tgc=None) -> dict:
    """A j16-loader row (result.json fields plus `_facts`)."""
    return {
        "goal_pass_rate": value,
        "tgc": value if tgc is None else tgc,
        "error_type": error_type,
        "success": value == 1.0,
        "n_planner_calls": 1,
        "_facts": {"handoff_occurred": handoff, "executor_n_calls": 2 if handoff else 0,
                   "effective_m": None, "n_source_actions": None},
    }


def _depth_fixture() -> tuple[dict, dict]:
    """Base 0.5 everywhere (hands off). At the target, task _1 hands off and scores 0.8
    (+0.3); task _2 has NO flag and task _3 a false flag, both 0.6 (+0.1, silenced)."""
    base, target = {}, {}
    for k in KEYS:
        base[k] = row(0.5, handoff=True)
        if k[0].endswith("_1"):
            target[k] = row(0.8, handoff=True)
        elif k[0].endswith("_2"):
            target[k] = row(0.6, handoff=None)
        else:
            target[k] = row(0.6, handoff=False)
    return base, target


# --------------------------------------------------------------------------------------
# R1.1  handoff-only means and the decomposition
# --------------------------------------------------------------------------------------


def test_handoff_arm_block_counts_missing_flag_as_silenced() -> None:
    _, target = _depth_fixture()
    b = j17.handoff_arm_block(target, n_boot=100)
    assert b["n"] == 12 and b["n_handoff"] == 4 and b["n_silenced"] == 8
    assert b["n_handoff_flag_missing"] == 4
    gp = b["goal_pass"]
    assert gp["mean_all"] == pytest.approx((4 * 0.8 + 8 * 0.6) / 12)
    assert gp["mean_handoff"] == pytest.approx(0.8)
    assert gp["mean_silenced"] == pytest.approx(0.6)
    assert gp["ci95_scenario"]["handoff"] == [pytest.approx(0.8), pytest.approx(0.8)]


def test_depth_contrast_handoff_only_and_decomposition_sum_to_total() -> None:
    base, target = _depth_fixture()
    c = j17.depth_contrast(base, target, "goal_pass_rate", "goal_pass", n_boot=200, seed=7)
    total_pp = 100 * (4 * 0.3 + 8 * 0.1) / 12  # 16.667
    assert c["all"]["diff_pp"] == pytest.approx(total_pp)
    assert c["handoff_only"]["diff_pp"] == pytest.approx(30.0)
    assert c["silenced"]["diff_pp"] == pytest.approx(10.0)
    assert c["all"]["n_pairs"] == 12 and c["handoff_only"]["n_pairs"] == 4 and c["silenced"]["n_pairs"] == 8
    for name in ("all", "handoff_only", "silenced"):
        assert CONTRACT_KEYS <= set(c[name])
        assert c[name]["threshold_pp"] == 0.0 and c[name]["metric"] == "goal_pass"
        # Every scenario has the same composition: the scenario interval is the point, and
        # no resample reaches 0, so the two-sided bootstrap p is 0.
        lo, hi = c[name]["ci95_pp_scenario"]
        assert lo == pytest.approx(c[name]["diff_pp"]) and hi == pytest.approx(c[name]["diff_pp"])
        assert c[name]["p_two_sided"] == 0.0
    d = c["decomposition"]
    assert d["contribution_handoff"]["point_pp"] == pytest.approx(100 * 1.2 / 12)
    assert d["contribution_silenced"]["point_pp"] == pytest.approx(100 * 0.8 / 12)
    assert d["contribution_handoff"]["point_pp"] + d["contribution_silenced"]["point_pp"] == pytest.approx(total_pp)
    assert d["contributions_sum_to_all"] is True
    assert d["share_handoff"]["point"] == pytest.approx(1.2 / 2.0)
    assert d["share_handoff"]["ci95_scenario"] == [pytest.approx(0.6), pytest.approx(0.6)]
    assert d["handoff_count"] == 4 and d["silenced_count"] == 8
    assert c["pairing"]["n_silenced_flag_missing"] == 4


def test_crashed_episode_is_excluded_from_the_pair_not_scored_zero() -> None:
    base, target = _depth_fixture()
    target[("s1_3", 1)] = row(0.6, handoff=False, error_type="crash")
    c = j17.depth_contrast(base, j17.drop_crashed(target), "goal_pass_rate", "goal_pass", n_boot=50, seed=7)
    assert c["all"]["n_pairs"] == 11
    assert c["all"]["diff_pp"] == pytest.approx(100 * (4 * 0.3 + 7 * 0.1) / 11)


# --------------------------------------------------------------------------------------
# NI reading
# --------------------------------------------------------------------------------------


def test_ni_reading_all_holds_while_handoff_only_fails() -> None:
    """Ceiling 0.9. Prefix: tasks _1/_2 hand off at 0.8 (d = -0.10), task _3 is silenced at
    0.9 (d = 0). All episodes: -0.8/12 = -6.67 pp, holds at -7; handoff-only: -10 pp, fails."""
    ceiling = {k: row(0.9, handoff=None) for k in KEYS}
    prefix = {k: (row(0.9, handoff=False) if k[0].endswith("_3") else row(0.8, handoff=True)) for k in KEYS}
    ni = j17.ni_block(prefix, ceiling, "goal_pass_rate", "goal_pass", n_boot=200, seed=3)
    a, h = ni["all"], ni["handoff_only"]
    assert a["diff_pp"] == pytest.approx(-100 * 0.8 / 12)
    assert h["diff_pp"] == pytest.approx(-10.0)
    assert a["threshold_pp"] == -7.0 and h["threshold_pp"] == -7.0
    assert a["n_pairs"] == 12 and h["n_pairs"] == 8
    assert a["ci95_pp_scenario"][0] == pytest.approx(-100 * 0.8 / 12)
    assert a["reading"] == "holds"
    assert h["reading"] == "fails"
    # Every resample sits on one side of -7 pp, so both bootstrap p values are 0.
    assert a["p_two_sided"] == 0.0 and h["p_two_sided"] == 0.0
    assert CONTRACT_KEYS <= set(a) and CONTRACT_KEYS <= set(h)


# --------------------------------------------------------------------------------------
# R1.2  chord
# --------------------------------------------------------------------------------------


def cost_row(q: float, cost: float, *, error_type=None) -> dict:
    """A j8_frontier cleaned row: quality plus the non-cached planner-token fields."""
    return {"goal_pass_rate": q, "tgc": q, "error_type": error_type,
            "planner_tokens_noncached_live": cost, "replayed_planner_tokens": None,
            "sft_plan_replayed_plan_tokens": None}


def test_chord_residual_with_known_f() -> None:
    """floor (q 0.4, cost 100), reference (q 0.9, cost 1100), arm (q 0.75, cost 600):
    f = 500 / 1000 = 0.5, chord = 0.4 + 0.5 * 0.5 = 0.65, residual = +0.10 = +10 pp."""
    floor = {"label": "sft_plan", "cleaned": {k: cost_row(0.4, 100.0) for k in KEYS}}
    ref = {"label": "planner_alone_cap81", "cleaned": {k: cost_row(0.9, 1100.0) for k in KEYS}}
    arm_rows = {k: cost_row(0.75, 600.0) for k in KEYS}
    arm_rows[("s1_1", 1)] = cost_row(0.0, 600.0, error_type="crash")  # excluded, not scored 0
    arm = {"label": "prefix", "cleaned": arm_rows}
    with j17.bootstrap_settings(200, 11):
        c = j17.chord_object(arm, floor, ref, "goal_pass_rate", "goal_pass", n_boot=200, seed=11)
    assert c["f"] == pytest.approx(0.5)
    assert c["residual_mean_pp"] == pytest.approx(10.0)
    assert c["n_pairs"] == 11 and c["n_pairs_dropped_crash"] == 1
    assert c["ci95_pp_scenario"] == [pytest.approx(10.0), pytest.approx(10.0)]
    assert c["ci95_pp_task"] == [pytest.approx(10.0), pytest.approx(10.0)]
    assert c["p_two_sided"] == 0.0
    assert c["p_recomputation"]["matches_j8"] is True
    assert c["floor_arm"].startswith("sft_plan") and "prereg_hj12_dev_20260922.md:40" in c["floor_arm"]


def test_bootstrap_settings_restore_the_reused_modules() -> None:
    before = (j17.j16.SEED, j17.j8.SEED, j17.j8.BOOTSTRAP, j17.hj1.SEED, j17.hj1.BOOTSTRAP)
    with j17.bootstrap_settings(123, 456):
        assert (j17.j16.SEED, j17.j8.BOOTSTRAP, j17.hj1.SEED, j17.hj1.BOOTSTRAP) == (456, 123, 456, 123)
    assert (j17.j16.SEED, j17.j8.SEED, j17.j8.BOOTSTRAP, j17.hj1.SEED, j17.hj1.BOOTSTRAP) == before


# --------------------------------------------------------------------------------------
# R1.3 / R1.4  Ganz metrics and cost share
# --------------------------------------------------------------------------------------


def ganz_row(q: float, calls: float, usd: float) -> dict:
    return {"goal_pass_rate": q, "hosted_calls_per_episode": calls, "usd_per_episode": usd}


def test_qrec_and_savings_retained_by_hand() -> None:
    """floor (0.4, 1 call, $0.004), ceiling (0.9, 20, $0.04), arm (0.8, 15, $0.03):
    QRec = 0.4 / 0.5 = 0.8; savings retained = 5 / 19 on calls and 0.01 / 0.036 on dollars.
    The floor covers seed 1 only, so only seed-1 triples are formed."""
    arm = {k: ganz_row(0.8, 15.0, 0.03) for k in KEYS}
    ceiling = {k: ganz_row(0.9, 20.0, 0.04) for k in KEYS}
    floor = {k: ganz_row(0.4, 1.0, 0.004) for k in KEYS if k[1] == 1}
    g = j17.ganz_metrics(arm, floor, ceiling, n_boot=200, seed=5)
    assert g["n_triples"] == 6 and g["seeds"] == [1]
    assert g["qrec"]["point"] == pytest.approx(0.8)
    assert g["qrec"]["ci95_scenario"] == [pytest.approx(0.8), pytest.approx(0.8)]
    assert g["savings_retained"]["hosted_calls"]["point"] == pytest.approx(5 / 19)
    assert g["savings_retained"]["usd"]["point"] == pytest.approx(0.01 / 0.036)
    assert g["savings_retained"]["usd"]["ci95_task"] == [pytest.approx(0.01 / 0.036), pytest.approx(0.01 / 0.036)]


def test_cost_share_calls_fraction_and_dollar_saving_retained() -> None:
    arm = {k: ganz_row(0.8, 15.0, 0.03) for k in KEYS}
    ceiling = {k: ganz_row(0.9, 20.0, 0.04) for k in KEYS}
    with j17.bootstrap_settings(200, 5):
        s = j17.cost_share(arm, ceiling, n_boot=200, seed=5)
    assert s["calls_fraction"]["point"] == pytest.approx(0.75)
    assert s["calls_fraction"]["ci95_scenario"] == [pytest.approx(0.75), pytest.approx(0.75)]
    assert s["dollar_saving_retained"]["point"] == pytest.approx(0.25)
    assert s["dollar_saving_retained"]["ci95_task"] == [pytest.approx(0.25), pytest.approx(0.25)]
    assert s["calls_fraction"]["n_pairs"] == 12


# --------------------------------------------------------------------------------------
# Path refusal and loading
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("marker", ["test_normal", "test_challenge", "j10_prefix_zs_m9_20260924"])
def test_refuse_path_names_each_marker(marker: str) -> None:
    with pytest.raises(j17.RefusedPath):
        j17.refuse_path(f"/scratch/results/{marker}/prefix_handoff")
    j17.refuse_path("/scratch/results/hj17_prefix_c81_bplus_m9_20260923/prefix_handoff")


@pytest.mark.parametrize("bad", ["results_j10_x", "test_normal_results", "test_challenge"])
def test_main_exits_2_on_a_refused_results_root(tmp_path: Path, bad: str) -> None:
    out = tmp_path / "out.json"
    assert j17.main(["--out", str(out), "--results-root", str(tmp_path / bad), "--n-boot", "10"]) == 2
    assert not out.exists()


def test_main_refuses_to_write_under_the_results_root(tmp_path: Path) -> None:
    root = tmp_path / "results"
    assert j17.main(["--out", str(root / "x.json"), "--results-root", str(root), "--n-boot", "10"]) == 2


def write_episode(system_dir: Path, task_id: str, seed: int, result: dict, events: list[dict]) -> None:
    d = system_dir / str(seed) / task_id
    d.mkdir(parents=True, exist_ok=True)
    payload = {"task_id": task_id, "seed": seed}
    payload.update(result)
    (d / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    evs = [{"event_type": "run_start", "ts": "2026-01-01T00:00:00+00:00"}, *events,
           {"event_type": "run_end", "ts": "2026-01-01T00:00:10+00:00"}]
    # Every real event carries its task_id and seed; j8's handoff loader keys on them.
    evs = [{"task_id": task_id, "seed": seed, **e} for e in evs]
    (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in evs) + "\n", encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")


def test_load_depth_rows_pools_seeds_and_counts_crashes(tmp_path: Path) -> None:
    root = tmp_path / "results"
    ceiling = j17.family_sources(root)["ceiling"]
    for k in KEYS:
        write_episode(ceiling[0]["root"], k[0], k[1], {"goal_pass_rate": 0.9, "tgc": 1.0, "n_planner_calls": 12}, [])
    # A stray seed-3 episode in the seeds 1-2 campaign is filtered, not pooled.
    write_episode(ceiling[0]["root"], "s1_1", 3, {"goal_pass_rate": 0.1, "tgc": 0.0, "n_planner_calls": 12}, [])
    for t in ("s1_1", "s1_2", "s1_3"):
        err = "crash" if t == "s1_2" else None
        write_episode(ceiling[1]["root"], t, 3, {"goal_pass_rate": 0.9, "tgc": 0.0 if err else 1.0,
                                                 "n_planner_calls": 12, "error_type": err}, [])
    rows, entries = j17.load_depth_rows(ceiling)
    assert len(rows) == 15
    assert [e["n_episodes"] for e in entries] == [12, 3]
    assert [e["n_crash"] for e in entries] == [0, 1]
    assert entries[0]["load_diagnostics"]["seed_filtered"] == 1
    assert len(j17.drop_crashed(rows)) == 14


# --------------------------------------------------------------------------------------
# End to end on a synthetic results tree: the key contract and a few hand values
# --------------------------------------------------------------------------------------

TASKS = [f"s{s}_{t}" for s in (1, 2) for t in (1, 2, 3)]
USAGE = {"model": "gpt-5.6-luna", "provider": "openai", "input_tokens": 1000,
         "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}


def _plan_event(tokens: int) -> dict:
    return {"event_type": "plan", "actor": "planner", "payload": {"packet": {"steps": []}},
            "usage": {**USAGE, "input_tokens": tokens}}


def _prefix_result(q: float, handoff) -> tuple[dict, list[dict]]:
    report = {"effective_m": 6, "n_source_actions": 12, "replayed_planner_tokens": 500}
    if handoff is not None:
        report["handoff_occurred"] = handoff
    result = {"system": "prefix_handoff", "goal_pass_rate": q, "tgc": 0.0, "success": False,
              "n_planner_calls": 6, "steps": 10,
              "totals": {"planner_calls_total": 0, "per_actor": {"executor": {"n_calls": 3}}}}
    return result, [{"event_type": "report", "actor": "system", "payload": report}]


def build_synthetic_results(root: Path) -> None:
    """Ceiling q 0.9, 12 calls, 1000 live non-cached tokens. Floor sft_plan q 0.4, 1 call,
    charged its hj1b plan event (100 tokens). Prefix arms (both receivers): m6 all hand off
    at 0.7; m9 tasks _1/_2 hand off at 0.8, _3 silenced at 0.9; m11 task _1 hands off at
    0.8, _2 silenced at 0.9, _3 has no flag at 0.9. Every prefix arm replays 500 tokens."""
    src = j17.family_sources(root)
    ceiling_result = {"system": "planner_alone", "goal_pass_rate": 0.9, "tgc": 1.0, "success": True,
                      "n_planner_calls": 12, "steps": 12,
                      "totals": {"planner_calls_total": 12, "planner_tokens_total": 1000,
                                 "per_actor": {"planner": {"input_tokens": 1000, "cached_input_tokens": 0,
                                                           "output_tokens": 0, "reasoning_output_tokens": 0},
                                               "executor": {"n_calls": 0}}}}
    for s in src["ceiling"]:
        for seed in s["seeds"]:
            for t in TASKS:
                write_episode(s["root"], t, seed, ceiling_result, [_plan_event(1000)])
    floor = src["floor"][0]
    for seed in floor["seeds"]:
        for t in TASKS:
            write_episode(floor["root"], t, seed,
                          {"system": "sft_plan", "goal_pass_rate": 0.4, "tgc": 0.0, "success": False,
                           "n_planner_calls": 1, "steps": 20,
                           "totals": {"planner_calls_total": 0, "per_actor": {"executor": {"n_calls": 20}}}}, [])
            write_episode(floor["packet_source"] / "planner_alone", t, seed, ceiling_result, [_plan_event(100)])
    spec = {6: {"_1": (0.7, True), "_2": (0.7, True), "_3": (0.7, True)},
            9: {"_1": (0.8, True), "_2": (0.8, True), "_3": (0.9, False)},
            11: {"_1": (0.8, True), "_2": (0.9, False), "_3": (0.9, None)}}
    for rx in j17.RECEIVERS:
        for m in j17.DEPTHS:
            for s in src[f"{rx}_m{m}"]:
                for seed in s["seeds"]:
                    for t in TASKS:
                        q, h = spec[m][t[-2:]]
                        result, events = _prefix_result(q, h)
                        write_episode(s["root"], t, seed, result, events)


def test_end_to_end_key_contract_and_hand_values(tmp_path: Path) -> None:
    root = tmp_path / "results"
    build_synthetic_results(root)
    out = tmp_path / "report.json"
    assert j17.main(["--out", str(out), "--results-root", str(root), "--n-boot", "30", "--seed", "9"]) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["settings"]["n_boot"] == 30 and rep["settings"]["seed"] == 9

    for rx in j17.RECEIVERS:
        for pair in ("m6_to_m11", "m9_to_m11"):
            for metric in ("goal_pass", "tgc"):
                blk = rep["handoff_only_contrasts"][rx][pair][metric]
                for name in ("all", "handoff_only", "silenced"):
                    assert CONTRACT_KEYS <= set(blk[name])
                for key in ("contribution_handoff", "contribution_silenced", "share_handoff"):
                    assert key in blk["decomposition"]
        for m in ("m9", "m11"):
            for metric in ("goal_pass", "tgc"):
                for name in ("all", "handoff_only"):
                    assert CONTRACT_KEYS <= set(rep["ni"][rx][m][metric][name])
                    assert rep["ni"][rx][m][metric][name]["reading"] in ("holds", "fails")
            for key in ("residual_mean_pp", "ci95_pp_scenario", "ci95_pp_task", "f", "floor_arm",
                        "reference_arm", "n_pairs"):
                assert key in rep["chord"][rx][m]

    h11 = rep["handoff_only"]["bplus"]["m11"]
    assert (h11["n"], h11["n_handoff"], h11["n_silenced"], h11["n_handoff_flag_missing"]) == (18, 6, 12, 6)
    c = rep["handoff_only_contrasts"]["bplus"]["m9_to_m11"]["goal_pass"]
    # Only task _2 moves (0.8 -> 0.9), and it is silenced at m11: 6 of 18 pairs gain 0.1.
    assert c["all"]["diff_pp"] == pytest.approx(100 * 0.6 / 18)
    assert c["handoff_only"]["diff_pp"] == pytest.approx(0.0)
    assert c["silenced"]["diff_pp"] == pytest.approx(100 * 0.6 / 12)
    assert c["decomposition"]["share_handoff"]["point_raw"] == pytest.approx(0.0)
    ni = rep["ni"]["bplus"]["m11"]["goal_pass"]
    assert ni["all"]["diff_pp"] == pytest.approx(-100 * 0.6 / 18) and ni["all"]["reading"] == "holds"
    assert ni["handoff_only"]["diff_pp"] == pytest.approx(-10.0) and ni["handoff_only"]["reading"] == "fails"
    ch = rep["chord"]["bplus"]["m9"]
    # f = (500 - 100) / (1000 - 100); chord = 0.4 + f * 0.5; the floor has seeds 1-2 only.
    f = 400 / 900
    assert ch["f"] == pytest.approx(f, abs=1e-6)
    assert ch["n_pairs"] == 12 and ch["seeds_paired"] == [1, 2]
    assert ch["residual_mean_pp"] == pytest.approx(round(100 * ((0.8 + 0.8 + 0.9) / 3 - (0.4 + f * 0.5)), 2))
    assert ch["p_recomputation"]["matches_j8"] is True
    assert rep["cost_share"]["bplus"]["m9"]["calls_fraction"]["point"] == pytest.approx(0.5)
    g = rep["ganz"]["bplus"]["m9"]
    assert g["qrec"]["point"] == pytest.approx(((0.8 + 0.8 + 0.9) / 3 - 0.4) / 0.5, abs=1e-6)
    assert g["savings_retained"]["hosted_calls"]["point"] == pytest.approx(6 / 11, abs=1e-6)
    assert g["n_triples"] == 12
    inputs = rep["inputs"]
    assert inputs["n_campaign_dirs"] == 15  # 2 ceiling + 1 floor + 2 receivers x 3 depths x 2
    assert inputs["n_episodes_total"] == 18 + 12 + 6 * 18  # ceiling, floor (seeds 1-2), six prefix arms
    assert inputs["n_crash_total"] == 0
    for agree in inputs["loader_agreement"].values():
        assert agree["n_goal_pass_mismatch"] == 0 and agree["n_handoff_flag_mismatch"] == 0
        assert agree["n_keys_only_in_depth_rows"] == 0 and agree["n_keys_only_in_cost_rows"] == 0
