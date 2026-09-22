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
