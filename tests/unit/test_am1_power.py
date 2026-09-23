"""Tests for scripts/analysis/am1_power.py (power of the J10 predictions at the test design).

Fixtures are synthetic with answers known by arithmetic: a constant positive difference must be
supported in every simulated read, a zero-mean difference almost never, and the handoff-only
estimand must equal Σd·h/Σh.
"""

from __future__ import annotations

import numpy as np
import pytest

from scripts.analysis import am1_power as ap


def rows_for(values_by_scenario: dict[str, list[float]], seeds=(1, 2, 3), h=1.0) -> list[dict]:
    """Each scenario has tasks <scen>_1.._n; each task gets every seed with the listed value."""
    out = []
    for scen, values in values_by_scenario.items():
        for t, v in enumerate(values, start=1):
            for s in seeds:
                out.append({"task": f"{scen}_{t}", "seed": s, "scenario": scen, "d": v, "h": h})
    return out


SPEC_GT = {"C": dict(left="a", right="b", direction="greater", threshold=0.0, family="F")}


def test_constant_positive_effect_is_always_supported():
    rows = rows_for({f"s{i}": [0.10, 0.10, 0.10] for i in range(6)})
    res = ap.simulate({"C": ap.index_by_scenario(rows)}, SPEC_GT, {"C": 0.0},
                      n_sims=40, n_boot=200, seed=1, n_scenarios=10)
    assert res["per_contrast"]["C"]["excludes_on_predicted_side"] == 1.0
    assert res["per_contrast"]["C"]["holm_supported"] == 1.0
    assert res["families_all_supported"]["F"] == 1.0


def test_zero_mean_effect_is_rarely_supported():
    # Scenario means alternate +0.2 / -0.2, so the true mean over scenarios is 0.
    rows = rows_for({f"s{i}": [0.2 if i % 2 else -0.2] * 3 for i in range(10)})
    res = ap.simulate({"C": ap.index_by_scenario(rows)}, SPEC_GT, {"C": 0.0},
                      n_sims=200, n_boot=400, seed=2, n_scenarios=20)
    assert res["per_contrast"]["C"]["excludes_on_predicted_side"] < 0.10


def test_shift_turns_a_supported_effect_into_a_null():
    rows = rows_for({f"s{i}": [0.10, 0.10, 0.10] for i in range(6)})
    res = ap.simulate({"C": ap.index_by_scenario(rows)}, SPEC_GT, {"C": 0.10},
                      n_sims=20, n_boot=200, seed=3, n_scenarios=10)
    # Every shifted difference is exactly 0: the interval is [0, 0] and never excludes 0.
    assert res["per_contrast"]["C"]["excludes_on_predicted_side"] == 0.0


def test_design_draws_two_distinct_seeds_per_task():
    rng = np.random.default_rng(0)
    design = ap.draw_design(["s1", "s2"], {"s1": ["s1_1", "s1_2"], "s2": ["s2_1"]}, rng, n_scenarios=50)
    assert len(design) == 50
    for cluster in design:
        for _task, seeds in cluster:
            assert len(seeds) == 2 and len(set(seeds)) == 2 and set(seeds) <= {1, 2, 3}


def test_two_seed_contrast_falls_back_to_its_own_seeds():
    rows = rows_for({"s1": [0.5]}, seeds=(1, 2))
    index = ap.index_by_scenario(rows)
    num, den = ap.cluster_sums(index, [[("s1_1", (1, 3))]], shift=0.0, handoff_only=False)
    assert den.tolist() == [2.0] and num.tolist() == [1.0]


def test_handoff_only_is_the_ratio_estimator():
    rows = [
        {"task": "s1_1", "seed": 1, "scenario": "s1", "d": 0.30, "h": 1.0},
        {"task": "s1_2", "seed": 1, "scenario": "s1", "d": -0.90, "h": 0.0},
        {"task": "s2_1", "seed": 1, "scenario": "s2", "d": 0.10, "h": 1.0},
    ]
    assert ap.handoff_ratio(rows) == pytest.approx(0.20)
    index = ap.index_by_scenario(rows)
    num, den = ap.cluster_sums(index, [[("s1_1", (1,)), ("s1_2", (1,))], [("s2_1", (1,))]],
                               shift=0.0, handoff_only=True)
    assert num.tolist() == pytest.approx([0.30, 0.10]) and den.tolist() == [1.0, 1.0]


def test_pvalue_matches_j10_report_definition():
    from scripts.analysis.j10_report import bootstrap_pvalue
    means = sorted([-0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05])
    arr = np.array(means)
    for direction in ("greater", "less", "two-sided"):
        for t in (-0.015, 0.0, 0.025):
            assert ap.pvalue(arr, t, direction) == pytest.approx(bootstrap_pvalue(means, t, direction))


def test_percentile_ci_uses_j10_order_statistics():
    from scripts.analysis.j10_report import percentile_ci
    means = [i / 1000 for i in range(1000)]
    assert ap.percentile_ci(np.array(means)) == pytest.approx(percentile_ci(means))


def test_refuses_heldout_paths(tmp_path):
    with pytest.raises(RuntimeError):
        ap.main(["--root", str(tmp_path), "--out", str(tmp_path / "test_normal_power.json")])
