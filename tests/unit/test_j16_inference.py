"""Tests for scripts/analysis/j16_inference.py and the j8_frontier --bootstrap-seed flag.

The load-bearing claims are (1) the RNG-identical replications return exactly what the
published code paths return, before rounding, at any seed; (2) re-seeding j8_frontier moves
both the task and the scenario interval and is always undone; (3) the default leaves the
registered seed alone. Fixtures are synthetic; nothing under /scratch is read.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

import scripts.setup.hj1_gate as hj1
from scripts.analysis import j16_inference as j16


def _arm_pair(n_scen: int = 19, per_task_seeds: int = 2, seed: int = 0):
    """Two synthetic arms keyed (task_id, seed): 3 tasks per scenario."""
    rng = random.Random(seed)
    base: dict[tuple[str, int], dict] = {}
    other: dict[tuple[str, int], dict] = {}
    for s in range(n_scen):
        for t in range(1, 4):
            task = f"sc{s:02d}_{t}"
            for sd in range(1, per_task_seeds + 1):
                base[(task, sd)] = {"goal_pass_rate": rng.random(), "tgc": float(rng.random() < 0.6)}
                other[(task, sd)] = {"goal_pass_rate": rng.random(), "tgc": float(rng.random() < 0.5)}
    return base, other


def _diffs(base, other, field):
    return {k: float(base[k][field]) - float(other[k][field]) for k in sorted(set(base) & set(other))}


@pytest.fixture(scope="module")
def j8():
    return j16.load_j8()


def test_parse_definition():
    assert j16.parse_definition("zs_m11 - zs_m6") == ("zs_m11", "zs_m6")
    with pytest.raises(ValueError):
        j16.parse_definition("zs_m11 minus zs_m6")


def test_negate_ci_and_excludes_zero():
    assert j16.negate_ci([-13.48, -1.29]) == [1.29, 13.48]
    assert j16.excludes_zero([0.1, 2.0]) is True
    assert j16.excludes_zero([-0.1, 2.0]) is False
    assert j16.excludes_zero([-3.0, -0.01]) is True


def test_ni_rule_matches_source_conventions():
    # POOL-02: ceiling minus arm, NI iff upper < +7.00 (strict).
    assert j16.ni_rule("upper", -10.0, 6.99) is True
    assert j16.ni_rule("upper", -10.0, 7.0175) is False
    assert j16.ni_rule("upper", -10.0, 7.0) is False
    # COST-03: arm minus ceiling, NI iff lower >= -7.00 (j12 uses >=).
    assert j16.ni_rule("lower", -6.14, 13.16) is True
    assert j16.ni_rule("lower", -7.0, 13.16) is True
    assert j16.ni_rule("lower", -7.02, 13.16) is False


@pytest.mark.parametrize("seed", [hj1.SEED, 20260924, 1, 999])
def test_replicate_task_bounds_equals_hj1_paired_diff(seed, monkeypatch):
    base, other = _arm_pair(seed=3)
    monkeypatch.setattr(hj1, "SEED", seed)
    published = hj1.paired_diff(base, other, "goal_pass_rate", resample="task")
    lo, hi = j16.replicate_task_bounds(_diffs(base, other, "goal_pass_rate"), seed, hj1.BOOTSTRAP)
    assert [round(lo * 100, 2), round(hi * 100, 2)] == published["ci95_pp"]


@pytest.mark.parametrize("seed", [20260915, 20260924, 7])
def test_replicate_scenario_bounds_equals_j8_paired_diff_scenario(seed, j8):
    base, other = _arm_pair(seed=5)
    saved = (j8.SEED, hj1.SEED)
    try:
        j8.set_bootstrap_seed(seed)
        published = j8.paired_diff_scenario(base, other, "tgc")
    finally:
        j8.SEED, hj1.SEED = saved
    lo, hi = j16.replicate_scenario_bounds(_diffs(base, other, "tgc"), seed, hj1.BOOTSTRAP)
    assert [round(lo * 100, 2), round(hi * 100, 2)] == published["ci95_pp"]


def test_seed_override_moves_both_intervals_and_restores(j8):
    base, other = _arm_pair(seed=9)
    registered = (j8.SEED, hj1.SEED)
    arm_a = {"cleaned": base, "label": "a"}
    arm_b = {"cleaned": other, "label": "b"}
    ref = j8.paired_contrast(arm_a, arm_b, "goal_pass_rate", "all", cluster="scenario")
    with j16.SeedOverride(j8, 1):
        assert j8.SEED == 1 and hj1.SEED == 1
        moved = j8.paired_contrast(arm_a, arm_b, "goal_pass_rate", "all", cluster="scenario")
    assert (j8.SEED, hj1.SEED) == registered
    again = j8.paired_contrast(arm_a, arm_b, "goal_pass_rate", "all", cluster="scenario")
    assert again["ci95_pp"] == ref["ci95_pp"] and again["ci95_pp_task"] == ref["ci95_pp_task"]
    # A different seed moves the percentile bounds (continuous synthetic data).
    assert moved["ci95_pp"] != ref["ci95_pp"] or moved["ci95_pp_task"] != ref["ci95_pp_task"]
    # And the replication at seed 1 matches the moved code path.
    d = j16.j8_diffs(j8, arm_a, arm_b, "goal_pass_rate")
    lo, hi = j16.replicate_task_bounds(d, 1, hj1.BOOTSTRAP)
    assert [round(lo * 100, 2), round(hi * 100, 2)] == moved["ci95_pp_task"]


def test_seed_override_restores_after_exception(j8):
    registered = (j8.SEED, hj1.SEED)
    with pytest.raises(RuntimeError):
        with j16.SeedOverride(j8, 42):
            raise RuntimeError("boom")
    assert (j8.SEED, hj1.SEED) == registered


def test_j8_bootstrap_seed_flag_defaults_to_none(j8):
    args = j8.parse_args(["--arm", "a=/tmp/x", "--out", "/tmp/o.json"])
    assert args.bootstrap_seed is None
    args = j8.parse_args(["--arm", "a=/tmp/x", "--out", "/tmp/o.json", "--bootstrap-seed", "7"])
    assert args.bootstrap_seed == 7


def test_j8_diffs_scores_crash_as_zero_and_drops_missing(j8):
    a = {"cleaned": {("s_1", 1): {"tgc": 1.0, "error_type": "crash"},
                     ("s_1", 2): {"tgc": 1.0},
                     ("s_2", 1): {"tgc": None}}}
    b = {"cleaned": {("s_1", 1): {"tgc": 0.0},
                     ("s_1", 2): {"tgc": 0.0},
                     ("s_2", 1): {"tgc": 1.0}}}
    d = j16.j8_diffs(j8, a, b, "tgc")
    assert d == {("s_1", 1): 0.0, ("s_1", 2): 1.0}


def test_j14_contrast_and_did_diffs_follow_episode_value():
    arms = {
        "ap": {("s_1", 1): {"goal_pass_rate": 0.9}, ("s_2", 1): {"goal_pass_rate": 0.5}},
        "an": {("s_1", 1): {"goal_pass_rate": 0.4}, ("s_2", 1): {"goal_pass_rate": 0.5,
                                                                   "error_type": "crash"}},
        "bp": {("s_1", 1): {"goal_pass_rate": 0.2}, ("s_2", 1): {"goal_pass_rate": None}},
        "bn": {("s_1", 1): {"goal_pass_rate": 0.1}, ("s_2", 1): {"goal_pass_rate": 0.3}},
    }
    c = j16.j14_contrast_diffs(arms, "ap", "an", "goal_pass_rate")
    # crash scores 0 -> s_2: 0.5 - 0 = 0.5
    assert c == {("s_1", 1): pytest.approx(0.5), ("s_2", 1): pytest.approx(0.5)}
    did = j16.j14_did_diffs(arms, "ap", "an", "bp", "bn", "goal_pass_rate")
    # s_1: (0.9-0.4) - (0.2-0.1) = 0.4 ; s_2: (0.5-0) - (0-0.3) = 0.8 (None scores 0)
    assert did[("s_1", 1)] == pytest.approx(0.4)
    assert did[("s_2", 1)] == pytest.approx(0.8)


def test_alternative_inference_structure_and_determinism():
    base, other = _arm_pair(seed=11)
    d = _diffs(base, other, "goal_pass_rate")
    kw = dict(seed=5, n_boot=2000, n_perm_scenario=1 << 19, n_perm_task=5000)
    out = j16.alternative_inference(d, **kw)
    assert out == j16.alternative_inference(d, **kw)
    assert out["n_pairs"] == 114
    assert out["scenario"]["n_clusters"] == 19
    assert out["scenario"]["signflip_method"] == "exact"
    assert out["scenario"]["signflip_n_patterns"] == 1 << 19
    assert out["task"]["n_clusters"] == 57
    assert out["task"]["signflip_method"] == "monte_carlo"
    for unit in ("scenario", "task"):
        for w in ("rademacher", "webb"):
            lo, hi = out[unit][f"wild_{w}_ci95_pp"]
            assert lo <= out["point_pp"] <= hi


def test_alternative_inference_ni_blocks():
    # Ceiling-minus-arm differences centred at 0 with small noise: NI at +7 pp must hold.
    rng = random.Random(2)
    d = {(f"sc{s:02d}_{t}", sd): rng.gauss(0.0, 0.05)
         for s in range(19) for t in range(1, 4) for sd in (1, 2)}
    out = j16.alternative_inference(d, n_boot=2000, n_perm_task=5000,
                                    ni={"bound": "upper", "margin": 0.07})
    assert out["scenario"]["ni_holds_signflip"] is True
    assert out["scenario"]["ni_holds_wild_rademacher"] is True
    assert out["scenario"]["ni_signflip_p_one_sided"] < 0.025
    # Centred at +10 pp: NI at +7 pp must fail everywhere.
    d2 = {k: v + 0.10 for k, v in d.items()}
    out2 = j16.alternative_inference(d2, n_boot=2000, n_perm_task=5000,
                                     ni={"bound": "upper", "margin": 0.07})
    assert out2["scenario"]["ni_holds_signflip"] is False
    assert out2["scenario"]["ni_holds_wild_webb"] is False
    # Arm-minus-ceiling orientation: centred at 0, lower-bound NI at -7 pp holds.
    out3 = j16.alternative_inference(d, n_boot=2000, n_perm_task=5000,
                                     ni={"bound": "lower", "margin": 0.07})
    assert out3["scenario"]["ni_holds_signflip"] is True


def _fake(pct_scen, pct_task, p_scen, p_task, wild_scen, wild_task):
    check = {"percentile_scenario_pp": pct_scen, "percentile_task_pp": pct_task}
    alt = {
        "scenario": {"signflip_rejects_zero_at_05": p_scen < 0.05,
                     "wild_rademacher_excludes_zero": j16.excludes_zero(wild_scen),
                     "wild_webb_excludes_zero": j16.excludes_zero(wild_scen)},
        "task": {"signflip_rejects_zero_at_05": p_task < 0.05,
                 "wild_rademacher_excludes_zero": j16.excludes_zero(wild_task),
                 "wild_webb_excludes_zero": j16.excludes_zero(wild_task)},
    }
    return check, alt


def test_verdicts_flags_disagreement_and_respects_presented_sign():
    spec = {"test": "zero", "presented_sign": -1}
    # Report orientation [-13.48, -1.29]: negated for presentation -> [1.29, 13.48].
    check, alt = _fake([-13.48, -1.29], [-12.35, -1.47], 0.01, 0.2, [1.0, 12.0], [0.5, 11.0])
    v = j16.verdicts(spec, check, alt)
    assert v["scenario"]["percentile_ci95_pp"] == [1.29, 13.48]
    assert v["scenario"]["all_methods_agree"] is True
    assert v["conclusion_changes_on_primary"] is False
    # task: percentile excludes zero, sign-flip p = 0.2 does not -> disagreement.
    assert v["conclusion_changes_on_task"] is True


def test_validate_output_path_refuses_results_and_heldout(tmp_path):
    with pytest.raises(SystemExit):
        j16.validate_output_path(Path("/scratch/n12194778/sidekick/results/x.json"))
    with pytest.raises(SystemExit):
        j16.validate_output_path(tmp_path / "test_normal" / "x.json")
    j16.validate_output_path(tmp_path / "ok.json")


def test_headline_specs_cover_the_brief():
    rows = j16.headline_specs()
    ids = {r["ledger_id"] for r in rows}
    assert {"CHAN-C1-02", "CHAN-PRICE-01", "POOL-01", "POOL-02", "DID-01"} <= ids
    pool02 = [r for r in rows if r["ledger_id"] == "POOL-02"]
    assert len(pool02) == 8 and all(r["ni"]["bound"] == "upper" for r in pool02)
    c1 = [r for r in rows if r["ledger_id"] == "CHAN-C1-02"]
    assert all(r["presented_sign"] == -1 for r in c1)
    # Every row names a report key that exists in its committed report.
    for r in rows:
        assert j16.dig(j16.load_json(r["report"]), r["report_key"]) is not None
