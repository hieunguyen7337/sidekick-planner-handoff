"""Tests for the J16 robustness analyses (scripts/analysis/j16_robustness.py).

Fixtures are synthetic and scripted so the right answer is known by arithmetic. The
bootstrap is also checked against j14_did's independent implementation, because a
resampler that is subtly wrong still returns a confident-looking interval.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from scripts.analysis import j16_robustness as j16

# Two scenarios x three tasks x two seeds = 12 episodes; scenario_of splits on the last "_".
KEYS = [(f"s{s}_{t}", seed) for s in (1, 2) for t in (1, 2, 3) for seed in (1, 2)]


def row(value: float, *, error_type=None, tgc=None, handoff=None, exec_calls=0, success=None,
        n_planner_calls=1) -> dict:
    return {
        "goal_pass_rate": value,
        "tgc": value if tgc is None else tgc,
        "error_type": error_type,
        "success": (value == 1.0) if success is None else success,
        "n_planner_calls": n_planner_calls,
        "_facts": {"handoff_occurred": handoff, "executor_n_calls": exec_calls,
                   "effective_m": None, "n_source_actions": None},
    }


# --------------------------------------------------------------------------------------
# Scoring conventions
# --------------------------------------------------------------------------------------


def test_quality_crash_is_zero_but_limit_is_scored() -> None:
    assert j16.quality(row(0.7, error_type="crash"), "goal_pass_rate") == 0.0
    assert j16.quality(row(0.7, error_type="limit"), "goal_pass_rate") == 0.7
    # A scored failure with no recorded tgc scores 0 (j10 score_tgc); a clean row without
    # a recorded value is missing, not zero.
    r = row(0.5, error_type="limit")
    r["tgc"] = None
    assert j16.quality(r, "tgc") == 0.0
    r2 = row(0.5)
    r2["tgc"] = None
    assert j16.quality(r2, "tgc") is None


def test_j10_clean_matches_inventory_rules() -> None:
    assert j16.j10_clean(row(0.5, error_type="limit", tgc=0.0))
    assert not j16.j10_clean(row(1.0, error_type="limit", tgc=1.0))  # writings disagree
    no_tgc = row(0.5)
    no_tgc["tgc"] = None
    assert not j16.j10_clean(no_tgc)
    assert not j16.j10_clean(row(0.5, n_planner_calls=None))


def test_ni_rule_rounds_lower_bound_to_two_decimals() -> None:
    assert j16.ni_holds([-7.004, 1.0]) is True
    assert j16.ni_holds([-7.006, 1.0]) is False
    assert j16.ni_holds(None) is None


def test_refuses_held_out_paths(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        j16.refuse_heldout(tmp_path / "test_normal" / "x")


# --------------------------------------------------------------------------------------
# Bootstrap
# --------------------------------------------------------------------------------------


def test_bootstrap_constant_values_give_degenerate_interval() -> None:
    b = j16.boot_mean({k: 0.25 for k in KEYS}, "scenario", seed=1, n_boot=200)
    assert b["point"] == pytest.approx(0.25)
    assert b["ci95"] == [pytest.approx(0.25), pytest.approx(0.25)]
    assert b["n_clusters"] == 2


def test_bootstrap_matches_j14_independent_implementation() -> None:
    """Same draw sequence as j14_did._cluster_bootstrap (and hj1_gate / j8_frontier)."""
    from scripts.analysis.j14_did import _cluster_bootstrap

    rng = random.Random(7)
    keys = [(f"sc{s}_{t}", seed) for s in range(6) for t in (1, 2, 3) for seed in (1, 2)]
    values = {k: rng.random() - 0.4 for k in keys}
    for unit in ("scenario", "task"):
        ref = _cluster_bootstrap(values, unit, 500, 20260924)
        mine = j16.boot_mean(values, unit, seed=20260924, n_boot=500)
        assert round(100 * mine["point"], 4) == ref["point_pp"]
        assert [round(100 * x, 4) for x in mine["ci95"]] == ref["ci95_pp"]
        assert mine["n_clusters"] == ref["n_clusters"]


def test_ratio_statistic_skips_undefined_resamples() -> None:
    comps = {("a_1", 1): (1.0, 0.0), ("b_1", 1): (1.0, 1.0)}
    b = j16.bootstrap_multi(comps, {"r": j16.ratio(0, 1)}, "scenario", seed=3, n_boot=400)
    st = b["stats"]["r"]
    assert st["point"] == pytest.approx(2.0)
    assert st["n_undefined"] > 0  # resamples that drew only scenario "a" have 0 denominator
    assert st["ci95"][0] >= 1.0


# --------------------------------------------------------------------------------------
# F-d  hinge vs linear
# --------------------------------------------------------------------------------------

MS = [0, 2, 4, 6, 7, 8, 9, 10, 11]


def test_fit_shape_on_a_straight_line_has_no_hinge_advantage() -> None:
    qs = [0.6 + 0.02 * m for m in MS]
    fit = j16.fit_shape(MS, qs, j16.TAU_REGISTERED)
    assert fit["linear"]["sse"] == pytest.approx(0.0, abs=1e-20)
    assert fit["delta_sse"] == pytest.approx(0.0, abs=1e-15)
    assert fit["hinge"]["tau"] == 4  # every tau fits exactly; ties take the smallest
    assert fit["hinge_preferred_bic"] is False


def test_fit_shape_recovers_a_true_kink() -> None:
    qs = [0.5 + 0.05 * max(m - 7, 0) for m in MS]
    fit = j16.fit_shape(MS, qs, j16.TAU_REGISTERED)
    assert fit["hinge"]["tau"] == 7
    assert fit["hinge"]["sse"] == pytest.approx(0.0, abs=1e-18)
    assert fit["hinge"]["b1"] == pytest.approx(0.0, abs=1e-9)
    assert fit["hinge"]["b1_plus_b2"] == pytest.approx(0.05, abs=1e-9)
    assert fit["delta_sse"] > 0
    assert fit["hinge_preferred_bic"] is True
    # The profile is minimised at the true tau.
    prof = fit["sse_profile_by_tau"]
    assert min(prof, key=prof.get) == "7"


def _panel(shape, noise: float, seed: int = 11) -> dict[int, dict[tuple, float]]:
    """Scenario-clustered noise: each scenario shares an offset, plus episode noise."""
    rng = random.Random(seed)
    keys = [(f"sc{s}_{t}", sd) for s in range(19) for t in (1, 2, 3) for sd in (1, 2)]
    scen_off = {f"sc{s}": rng.gauss(0, noise) for s in range(19)}
    panel: dict[int, dict[tuple, float]] = {}
    for m in MS:
        panel[m] = {k: shape(m) + scen_off[k[0].rsplit("_", 1)[0]] + rng.gauss(0, noise) for k in keys}
    return panel


def test_null_calibrated_bootstrap_rejects_a_strong_kink_and_localizes_it() -> None:
    panel = _panel(lambda m: 0.5 + 0.06 * max(m - 7, 0), noise=0.02)
    b = j16.bootstrap_shape(panel, j16.TAU_REGISTERED, "scenario", seed=5, n_boot=300)
    assert b["tau"] == 7
    assert b["null_linear"]["p_value"] < 0.05
    assert b["share_hinge_preferred_bic"] > 0.9
    assert b["tau_modal"] == 7


def test_null_calibrated_bootstrap_does_not_reject_a_line() -> None:
    panel = _panel(lambda m: 0.5 + 0.02 * m, noise=0.05)
    b = j16.bootstrap_shape(panel, j16.TAU_REGISTERED, "scenario", seed=5, n_boot=300)
    assert b["null_linear"]["p_value"] > 0.05
    assert b["share_hinge_sse_below_linear"] > 0.99  # nested model: trivially ~1
    assert b["breakpoint_localized"] is False


# --------------------------------------------------------------------------------------
# F-c  handoff shares and counts
# --------------------------------------------------------------------------------------


def _decomp_fixture() -> tuple[dict, dict]:
    """Each scenario: tasks 1,2 hand off at the target (both seeds), task 3 does not.
    Base 0.5 everywhere; target 0.8 on handoff episodes (+0.3), 0.6 on silenced (+0.1).
    Every scenario has the same composition, so every resample gives the same statistic."""
    base, target = {}, {}
    for k in KEYS:
        h = not k[0].endswith("_3")
        base[k] = row(0.5, handoff=True, exec_calls=2)
        target[k] = row(0.8 if h else 0.6, handoff=h, exec_calls=2 if h else 0)
    return base, target


def test_decomposition_arithmetic_and_identity() -> None:
    base, target = _decomp_fixture()
    d = j16.decomposition(base, target, "goal_pass_rate", n_boot=200)
    assert d["handoff_count"] == 8 and d["silenced_count"] == 4
    total = (8 * 0.3 + 4 * 0.1) / 12
    assert d["delta_total"]["point"] == pytest.approx(total)
    assert d["contribution_handoff"]["point"] == pytest.approx(2.4 / 12)
    assert d["contribution_handoff"]["point"] + d["contribution_silenced"]["point"] == pytest.approx(total)
    assert d["share_of_rise_from_handoff"]["point_raw"] == pytest.approx(2.4 / 2.8)
    assert d["gain_on_handoff_subset"]["point"] == pytest.approx(0.3)
    assert d["gain_on_silenced_subset"]["point"] == pytest.approx(0.1)
    assert d["y_base_handoff_subset"]["point"] == pytest.approx(0.5)
    assert d["y_target_handoff_subset"]["point"] == pytest.approx(0.8)
    lo, hi = d["share_of_rise_from_handoff"]["ci95_scenario"]
    assert lo == pytest.approx(2.4 / 2.8) and hi == pytest.approx(2.4 / 2.8)


def test_decomposition_share_undefined_when_rise_is_not_positive() -> None:
    base, target = _decomp_fixture()
    for k in target:
        target[k]["goal_pass_rate"] = 0.5  # no rise anywhere
    d = j16.decomposition(base, target, "goal_pass_rate", n_boot=100)
    assert d["delta_total"]["point"] == pytest.approx(0.0)
    assert d["share_of_rise_from_handoff"]["point"] is None
    assert d["share_of_rise_from_handoff"]["n_resamples_rise_not_positive_scenario"] == 100


def test_depth_counts_separates_the_two_silenced_definitions() -> None:
    rows = {
        ("a_1", 1): row(0.5, handoff=True, exec_calls=3),
        ("a_2", 1): row(0.5, handoff=False, exec_calls=0),
        ("a_3", 1): row(0.5, handoff=False, exec_calls=2),  # exhausted source, executor acted
        ("b_1", 1): row(0.5, handoff=None, exec_calls=0),
    }
    c = j16.depth_counts(rows)
    assert c["n_handoff_occurred_true"] == 1
    assert c["n_handoff_occurred_false"] == 2
    assert c["n_handoff_flag_missing"] == 1
    assert c["n_executor_never_acted"] == 2
    assert c["n_handoff_false_but_executor_acted"] == 1
    assert c["handoff_false_but_executor_acted_keys"] == [["a_3", 1]]


def test_handoff_only_block_means() -> None:
    _, target = _decomp_fixture()
    b = j16.handoff_only_block(target, "goal_pass_rate", n_boot=100)
    assert b["handoff_only"]["point"] == pytest.approx(0.8)
    assert b["silenced"]["point"] == pytest.approx(0.6)
    assert b["all"]["point"] == pytest.approx((8 * 0.8 + 4 * 0.6) / 12)
    assert b["n_handoff"] == 8 and b["n_silenced"] == 4


def test_receiver_gap_did_is_formed_per_episode() -> None:
    t_b, t_t, u_b, u_t = {}, {}, {}, {}
    for k in KEYS:
        t_b[k] = row(0.6, handoff=True)
        u_b[k] = row(0.5, handoff=True)
        t_t[k] = row(0.8, handoff=True)
        u_t[k] = row(0.8, handoff=True)
    g = j16.receiver_gap(t_b, t_t, u_b, u_t, "goal_pass_rate", n_boot=100)
    h = g["handoff_at_target"]
    assert h["gap_at_base"]["point"] == pytest.approx(0.1)
    assert h["gap_at_target"]["point"] == pytest.approx(0.0)
    assert h["did_gap_change"]["point"] == pytest.approx(-0.1)
    assert g["handoff_flag_mismatch_between_receivers"] == 0


def test_pinned_curve_uses_deepest_handoff_set() -> None:
    arms = {}
    for m, val in ((6, 0.5), (9, 0.7)):
        arms[m] = {k: row(val, handoff=(True if m == 6 else not k[0].endswith("_3"))) for k in KEYS}
    pc = j16.pinned_curve(arms, "goal_pass_rate", n_boot=100)
    assert pc["n_keys"] == 8
    assert pc["curve"]["m6"]["mean"] == pytest.approx(0.5)
    assert pc["contrasts"]["m9_minus_m6"]["diff_pp"] == pytest.approx(20.0)
    assert pc["keys_not_handing_off_at_shallower_depth"] == {"m6": 0, "m9": 0}


# --------------------------------------------------------------------------------------
# F-b  SGC
# --------------------------------------------------------------------------------------


def test_sgc_units_require_every_task_and_treat_crash_as_failure() -> None:
    rows = {k: row(1.0, success=True) for k in KEYS}
    rows[("s2_3", 2)] = row(1.0, success=True, error_type="crash")
    u = j16.sgc_units(rows)
    assert u[("s1", 1)] == 1.0 and u[("s2", 1)] == 1.0
    assert u[("s2", 2)] == 0.0
    del rows[("s1_2", 1)]  # incomplete scenario-seed unit is not scored
    assert ("s1", 1) not in j16.sgc_units(rows)


def test_sgc_contrast_counts_units_and_discordance() -> None:
    a = {k: row(1.0, success=True) for k in KEYS}
    b = dict(a)
    b[("s1_1", 1)] = row(0.0, success=False)
    c = j16.sgc_contrast(a, b, seed=1, n_boot=100)
    assert c["n_units_scenario_seed"] == 4
    assert c["n_discordant_units"] == 1
    assert c["diff_pp"] == pytest.approx(25.0)


# --------------------------------------------------------------------------------------
# Loader, ArmStore, contrasts, selection
# --------------------------------------------------------------------------------------


def write_campaign(root: Path, name: str, rows: dict, *, handoff: dict | None = None,
                   two_attempts: bool = False) -> Path:
    camp = root / name / "sys"
    for (task_id, seed), r in rows.items():
        d = camp / str(seed) / task_id
        d.mkdir(parents=True, exist_ok=True)
        payload = {"task_id": task_id, "seed": seed, "n_planner_calls": 1,
                   "totals": {"per_actor": {"executor": {"n_calls": 2}}, "executor_tokens_total": 100}}
        payload.update(r)
        (d / "result.json").write_text(json.dumps(payload), encoding="utf-8")
        events = []
        if two_attempts:
            events.append({"event_type": "run_start", "ts": "2026-01-01T00:00:00+00:00"})
            events.append({"event_type": "report", "payload": {"handoff_occurred": True}})
        events.append({"event_type": "run_start", "ts": "2026-01-01T00:00:00+00:00"})
        if handoff is not None:
            events.append({"event_type": "report", "payload": {"handoff_occurred": handoff[(task_id, seed)],
                                                              "effective_m": 6, "n_source_actions": 9}})
        events.append({"actor": "executor", "event_type": "action",
                       "usage": {"latency_s": 0.0, "gpu_seconds": 0.0}})
        events.append({"event_type": "run_end", "ts": "2026-01-01T00:00:10+00:00"})
        (d / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        (d / "manifest.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:04+00:00"}), encoding="utf-8")
    return camp


def test_loader_reads_last_attempt_report_and_usage(tmp_path: Path) -> None:
    rows = {k: {"goal_pass_rate": 0.5, "tgc": 0.0} for k in KEYS}
    flags = {k: False for k in KEYS}
    camp = write_campaign(tmp_path, "c", rows, handoff=flags, two_attempts=True)
    loaded, diag = j16.load_campaign_dir(camp, {1, 2})
    assert len(loaded) == 12 and diag["loaded"] == 12
    f = loaded[KEYS[0]]["_facts"]
    assert f["handoff_occurred"] is False  # the earlier attempt's True is ignored
    assert f["effective_m"] == 6 and f["executor_n_calls"] == 2
    assert f["executor_usage_records"] == 1 and f["executor_latency_positive"] == 0
    assert f["wall_clock_s"] == pytest.approx(6.0)
    only_seed1, _ = j16.load_campaign_dir(camp, {1})
    assert len(only_seed1) == 6


def test_armstore_contrast_and_pooling_refuses_collisions(tmp_path: Path) -> None:
    a = write_campaign(tmp_path, "a", {k: {"goal_pass_rate": 0.8, "tgc": 1.0} for k in KEYS})
    b = write_campaign(tmp_path, "b", {k: {"goal_pass_rate": 0.6, "tgc": 0.0} for k in KEYS})
    store = j16.ArmStore({"a": [a], "b": [b], "ab": [a, b]})
    c = j16.contrast(store, "a", "b", "goal_pass_rate", n_boot=100)
    assert c["n_pairs"] == 12
    assert c["diff_pp"] == pytest.approx(20.0)
    assert c["scenario"]["ci95_pp"] == [pytest.approx(20.0), pytest.approx(20.0)]
    with pytest.raises(ValueError):
        store("ab")


def test_selection_block_splits_reference_limit_episodes(tmp_path: Path) -> None:
    ref_rows = {k: {"goal_pass_rate": 0.9, "tgc": 1.0} for k in KEYS}
    limit_keys = [("s1_1", 1), ("s2_1", 2)]
    for k in limit_keys:
        ref_rows[k] = {"goal_pass_rate": 0.2, "tgc": 0.0, "error_type": "limit"}
    arm_rows = {k: {"goal_pass_rate": 0.7, "tgc": 0.0} for k in KEYS}
    for k in limit_keys:
        arm_rows[k] = {"goal_pass_rate": 0.8, "tgc": 0.0}
    ref = write_campaign(tmp_path, "ref", ref_rows)
    arm = write_campaign(tmp_path, "arm", arm_rows)
    store = j16.ArmStore({"ref": [ref], "arm": [arm]})
    sel = j16.selection_block(store, "ref", ["arm"], n_boot=100)
    assert sel["n_dropped"] == 2 and sel["n_kept"] == 10
    r = sel["per_arm"]["ref"]
    assert r["goal_pass_kept"] == pytest.approx(0.9) and r["goal_pass_dropped"] == pytest.approx(0.2)
    e = sel["per_arm"]["arm"]
    assert e["arm_minus_ref_dropped_pp"] == pytest.approx(60.0)
    assert e["arm_minus_ref_kept_pp"] == pytest.approx(-20.0)
    # The full contrast is the weighted mix of the two subsets.
    assert e["arm_minus_ref_all_pp"] == pytest.approx((10 * -20.0 + 2 * 60.0) / 12)


def test_repro_check_uses_stored_precision() -> None:
    r = j16.Repro()
    assert r.check("x", "s", "k", 0.800719, 0.80071949, 6)
    assert not r.check("x", "s", "k", 0.800719, 0.8007196, 6)
    assert r.check("x", "s", "k", [-6.69, 1.2], [-6.694, 1.204], 2)
    assert not r.all_ok
    assert len(r.failures()) == 1
