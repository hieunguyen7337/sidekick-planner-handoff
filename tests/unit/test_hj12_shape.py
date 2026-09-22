"""Registered HJ-13 shape test: breakpoint recovery, S3 can fail, tau reselection, percentile map."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_SPEC = importlib.util.spec_from_file_location(
    "hj12_shape", REPO / "scripts" / "analysis" / "hj12_shape.py"
)
shape = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(shape)


M = [0, 2, 4, 6, 7, 8, 9, 10, 11]


def synthetic_keys():
    keys = []
    for i in range(19):
        scen = f"{i:07x}"
        for v in (1, 2, 3):
            for seed in (1, 2):
                keys.append((f"{scen}_{v}", seed))
    return keys


def panel_from_fn(fn):
    keys = synthetic_keys()
    panel = {}
    for m in M:
        panel[m] = {k: float(fn(m, k)) for k in keys}
    return panel


def test_known_breakpoint_at_7_recovers_tau():
    qs = [0.50 if m <= 7 else 0.50 + 0.05 * (m - 7) for m in M]
    fit = shape.fit_segmented(M, qs)
    assert fit["tau"] == 7
    assert abs(fit["beta1"]) < 1e-8
    assert fit["beta1_plus_beta2"] > 0.0


def test_straight_line_s3_does_not_exclude_m_le_4():
    panel = panel_from_fn(lambda m, _k: 0.50 + 0.02 * m)
    boot = shape.bootstrap_segmented(
        panel, cluster="scenario", n_boot=200, seed=shape.SEED
    )
    verdict = shape.s1_s2_s3(boot)
    assert boot["tau"] == 4
    assert boot["tau_ci95"][0] <= 4
    assert verdict["S3_threshold_is_real"]["holds"] is False
    assert verdict["verdict"] == "no threshold established"


def test_bootstrap_reselects_tau_across_resamples():
    def q(m, key):
        scen = int(key[0].split("_")[0], 16)
        tau = 6 if scen < 9 else 9
        return 0.50 + 0.08 * max(m - tau, 0)

    panel = panel_from_fn(q)
    boot = shape.bootstrap_segmented(
        panel, cluster="scenario", n_boot=400, seed=shape.SEED
    )
    assert boot["tau_n_distinct_in_bootstrap"] >= 2
    assert len(boot["tau_counts"]) >= 2


def test_percentile_remap_is_monotone_and_matches_hand_computed():
    steps = [5, 5, 10, 20]
    assert shape.planner_percentile(4, steps) == 0.0
    assert shape.planner_percentile(5, steps) == 50.0
    assert shape.planner_percentile(10, steps) == 75.0
    assert shape.planner_percentile(20, steps) == 100.0
    ps = [shape.planner_percentile(m, steps) for m in range(0, 21)]
    assert all(ps[i] <= ps[i + 1] for i in range(len(ps) - 1))
    mapped = shape.percentile_map(M, steps)
    ms = sorted(mapped)
    assert all(mapped[ms[i]] <= mapped[ms[i + 1]] for i in range(len(ms) - 1))


def test_tie_break_takes_smallest_tau_on_a_line():
    qs = [0.50 + 0.02 * m for m in M]
    fit = shape.fit_segmented(M, qs)
    assert fit["tau"] == 4


def test_resampler_is_hj1_gate_draw_task_clusters():
    from scripts.setup.hj1_gate import _draw_task_clusters

    assert shape._draw_task_clusters is _draw_task_clusters


def test_holm_is_monotone_and_at_least_as_wide_as_raw():
    """Every adjusted interval contains the raw interval and is at least as wide."""
    import random

    rng = random.Random(42)
    contrasts = {
        "c1": [rng.gauss(1.0, 1.0) for _ in range(2000)],
        "c2": [rng.gauss(0.2, 1.0) for _ in range(2000)],
        "c3": [rng.gauss(-0.5, 1.0) for _ in range(2000)],
        "c4": [rng.gauss(2.0, 0.5) for _ in range(2000)],
    }
    res = shape.holm_adjusted_intervals(contrasts, alpha=0.05)
    assert res["method"] == "holm"
    assert res["n_comparisons"] == 4
    assert set(res["family"]) == set(contrasts.keys())

    for name, adj in res["adjusted"].items():
        ci_adj = adj["ci95_pp_adjusted"]
        ci_raw = adj["ci95_pp_raw"]
        assert ci_adj is not None and ci_raw is not None
        # Adjusted interval contains raw interval
        assert ci_adj[0] <= ci_raw[0] + 1e-9
        assert ci_adj[1] >= ci_raw[1] - 1e-9
        # Adjusted width is at least as wide as raw width
        assert (ci_adj[1] - ci_adj[0]) >= (ci_raw[1] - ci_raw[0]) - 1e-9
        # Adjusted p-value >= raw p-value
        assert adj["p_adjusted"] >= adj["p_raw"] - 1e-9


def test_holm_matches_a_hand_worked_example():
    """Four p-values with a known Holm result match step-down calculation."""
    # Construct 4 sample vectors of length 10000 with known fractions <= 0
    # c_p005: 25/10000 <= 0 -> p = 2 * 25/10000 = 0.005
    # c_p010: 50/10000 <= 0 -> p = 2 * 50/10000 = 0.010
    # c_p030: 150/10000 <= 0 -> p = 2 * 150/10000 = 0.030
    # c_p040: 200/10000 <= 0 -> p = 2 * 200/10000 = 0.040
    def make_samples(n_neg: int, total: int = 10000) -> list[float]:
        return [-1.0] * n_neg + [1.0] * (total - n_neg)

    contrasts = {
        "c_p010": make_samples(50),
        "c_p040": make_samples(200),
        "c_p005": make_samples(25),
        "c_p030": make_samples(150),
    }

    res = shape.holm_adjusted_intervals(contrasts, alpha=0.05)
    adj = res["adjusted"]

    # c_p005 (rank 1, multiplier 4): 4 * 0.005 = 0.020 <= 0.05 -> survives True
    assert abs(adj["c_p005"]["p_raw"] - 0.005) < 1e-6
    assert abs(adj["c_p005"]["p_adjusted"] - 0.020) < 1e-6
    assert adj["c_p005"]["survives"] is True

    # c_p010 (rank 2, multiplier 3): max(0.020, 3 * 0.010) = 0.030 <= 0.05 -> survives True
    assert abs(adj["c_p010"]["p_raw"] - 0.010) < 1e-6
    assert abs(adj["c_p010"]["p_adjusted"] - 0.030) < 1e-6
    assert adj["c_p010"]["survives"] is True

    # c_p030 (rank 3, multiplier 2): max(0.030, 2 * 0.030) = 0.060 > 0.05 -> survives False
    assert abs(adj["c_p030"]["p_raw"] - 0.030) < 1e-6
    assert abs(adj["c_p030"]["p_adjusted"] - 0.060) < 1e-6
    assert adj["c_p030"]["survives"] is False

    # c_p040 (rank 4, multiplier 1): max(0.060, 1 * 0.040) = 0.060 > 0.05 -> survives False
    assert abs(adj["c_p040"]["p_raw"] - 0.040) < 1e-6
    assert abs(adj["c_p040"]["p_adjusted"] - 0.060) < 1e-6
    assert adj["c_p040"]["survives"] is False


def _make_dummy_arm(n_scenarios: int = 10, base_gp: float = 0.70, base_tgc: float = 0.50) -> dict:
    cleaned = {}
    for i in range(n_scenarios):
        scen = f"{i:07x}"
        for v in (1, 2):
            for seed in (1, 2):
                key = (f"{scen}_{v}", seed)
                # Vary slightly around base
                offset = 0.02 * ((i + v + seed) % 5 - 2)
                gp = max(0.0, min(1.0, base_gp + offset))
                tgc = max(0.0, min(1.0, base_tgc + offset))
                cleaned[key] = {
                    "task_id": key[0],
                    "seed": seed,
                    "goal_pass_rate": gp,
                    "tgc": tgc,
                    "error_type": None,
                    "executor_n_calls": 5,
                }
    return {
        "label": "prefix_m6",
        "n": len(cleaned),
        "complete_n": True,
        "n_handoff_occurred": len(cleaned),
        "error_types": {"none": len(cleaned)},
        "cleaned": cleaned,
    }


def test_arm_snapshot_contains_all_four_ci_keys():
    arm = _make_dummy_arm(n_scenarios=8)
    snap = shape.arm_snapshot(arm, m=6, n_boot=200, seed=shape.SEED)
    for k in ("goal_pass_all_ci95", "goal_pass_all_ci95_pp", "tgc_all_ci95", "tgc_all_ci95_pp"):
        assert k in snap
        assert snap[k] is not None
        assert isinstance(snap[k], list)
        assert len(snap[k]) == 2
        assert snap[k][0] <= snap[k][1]


def test_arm_ci_brackets_point_estimate():
    arm = _make_dummy_arm(n_scenarios=12, base_gp=0.75, base_tgc=0.60)
    snap = shape.arm_snapshot(arm, m=8, n_boot=1000, seed=shape.SEED)
    gp = snap["goal_pass_all"]
    gp_ci = snap["goal_pass_all_ci95"]
    gp_ci_pp = snap["goal_pass_all_ci95_pp"]
    assert gp_ci[0] <= gp <= gp_ci[1]
    assert gp_ci_pp[0] <= gp * 100.0 <= gp_ci_pp[1]

    tgc = snap["tgc_all"]
    tgc_ci = snap["tgc_all_ci95"]
    tgc_ci_pp = snap["tgc_all_ci95_pp"]
    assert tgc_ci[0] <= tgc <= tgc_ci[1]
    assert tgc_ci_pp[0] <= tgc * 100.0 <= tgc_ci_pp[1]


def test_arm_bootstrap_seed_reproducible():
    arm = _make_dummy_arm(n_scenarios=6)
    ci1, ci_pp1 = shape.bootstrap_arm_quality(
        arm, "goal_pass_rate", n_boot=300, seed=shape.SEED
    )
    ci2, ci_pp2 = shape.bootstrap_arm_quality(
        arm, "goal_pass_rate", n_boot=300, seed=shape.SEED
    )
    assert ci1 == ci2
    assert ci_pp1 == ci_pp2


def test_arm_bootstrap_single_cluster_does_not_crash():
    # Only a single scenario cluster
    arm = _make_dummy_arm(n_scenarios=1)
    ci, ci_pp = shape.bootstrap_arm_quality(
        arm, "goal_pass_rate", n_boot=100, seed=shape.SEED
    )
    assert ci is not None
    assert len(ci) == 2
    assert ci[0] <= ci[1]
    snap = shape.arm_snapshot(arm, m=2, n_boot=100, seed=shape.SEED)
    assert snap["goal_pass_all_ci95"] is not None
    assert len(snap["goal_pass_all_ci95"]) == 2


