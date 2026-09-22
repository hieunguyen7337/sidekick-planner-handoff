"""Tests for scripts/analysis/cluster_inference.py.

Every expected value is derived by hand in the comment next to it: a permutation test that
is subtly wrong still returns a plausible-looking p-value, so blessing printed output would
test nothing.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from scripts.analysis.cluster_inference import (
    WEBB_POINTS,
    cluster_signflip_pvalue,
    signflip_details,
    wild_cluster_bootstrap_ci,
    wild_cluster_draws,
)

# Three clusters: A = [1, 1] (sum 2), B = [2] (sum 2), C = [-1] (sum -1). N = 4.
# Observed mean = (2 + 2 - 1) / 4 = 0.75, i.e. signed total 3.
# The 8 sign patterns (sA, sB, sC) give totals:
#   (+,+,+)  3   (+,+,-)  5   (+,-,+) -1   (+,-,-)  1
#   (-,+,+) -1   (-,+,-)  1   (-,-,+) -5   (-,-,-) -3
# two-sided: |total| >= 3 -> {3, 5, -5, -3}            -> 4/8 = 0.5
# greater:    total  >= 3 -> {3, 5}                    -> 2/8 = 0.25
# less:       total  <= 3 -> all but the 5             -> 7/8 = 0.875
HAND_DIFFS = [1.0, 1.0, 2.0, -1.0]
HAND_CLUSTERS = ["A", "A", "B", "C"]


def test_exact_enumeration_hand_computed_three_clusters():
    assert cluster_signflip_pvalue(HAND_DIFFS, HAND_CLUSTERS) == pytest.approx(0.5)
    assert cluster_signflip_pvalue(
        HAND_DIFFS, HAND_CLUSTERS, alternative="greater"
    ) == pytest.approx(0.25)
    assert cluster_signflip_pvalue(
        HAND_DIFFS, HAND_CLUSTERS, alternative="less"
    ) == pytest.approx(0.875)


def test_exact_details_report_enumeration():
    d = signflip_details(HAND_DIFFS, HAND_CLUSTERS)
    assert d["method"] == "exact"
    assert d["n_patterns"] == 8
    assert d["n_clusters"] == 3
    assert d["n_obs"] == 4
    assert d["n_as_extreme"] == 4
    assert d["statistic"] == pytest.approx(0.75)


def test_exact_is_order_invariant():
    # Shuffling the episodes (keeping labels attached) cannot change an exact p.
    pairs = list(zip(HAND_DIFFS, HAND_CLUSTERS))
    pairs = [pairs[i] for i in (3, 1, 0, 2)]
    diffs, clusters = zip(*pairs)
    assert cluster_signflip_pvalue(list(diffs), list(clusters)) == pytest.approx(0.5)


def test_exact_threshold_uses_two_pow_g_le_n_perm():
    # G = 3 -> 8 patterns. n_perm = 8 enumerates; n_perm = 7 must fall back to Monte Carlo.
    assert signflip_details(HAND_DIFFS, HAND_CLUSTERS, n_perm=8)["method"] == "exact"
    mc = signflip_details(HAND_DIFFS, HAND_CLUSTERS, n_perm=7)
    assert mc["method"] == "monte_carlo"
    # Monte Carlo p carries the +1 correction, so it can never be 0.
    assert mc["p"] == pytest.approx((1 + mc["n_as_extreme"]) / 8)


def test_ties_are_counted_as_extreme():
    # Cluster sums X = 0.1 + 0.2 (0.30000000000000004 in floats), Y = 0.3, Z = -0.3, N = 4.
    # Mathematically the totals (sX, sY, sZ) are:
    #   (+,+,+) 0.3  (+,+,-) 0.9  (+,-,+) -0.3  (+,-,-) 0.3
    #   (-,+,+) -0.3 (-,+,-) 0.3  (-,-,+) -0.9  (-,-,-) -0.3
    # greater: total >= 0.3 -> 4 of 8 = 0.5. Three of those ties are only ties up to
    # floating-point rounding, so a strict float comparison would return less than 0.5.
    diffs = [0.1, 0.2, 0.3, -0.3]
    clusters = ["X", "X", "Y", "Z"]
    assert cluster_signflip_pvalue(diffs, clusters, alternative="greater") == pytest.approx(
        0.5
    )
    # two-sided: every |total| >= 0.3 -> 8 of 8.
    assert cluster_signflip_pvalue(diffs, clusters) == pytest.approx(1.0)


def test_symmetry_under_negation():
    rng = random.Random(5)
    clusters = [f"s{i // 3}" for i in range(30)]
    diffs = [rng.gauss(0.2, 1.0) for _ in clusters]
    neg = [-d for d in diffs]
    # G = 10 -> 1024 patterns <= 10,000, so both are exact and must agree exactly.
    assert cluster_signflip_pvalue(diffs, clusters) == pytest.approx(
        cluster_signflip_pvalue(neg, clusters)
    )
    assert cluster_signflip_pvalue(diffs, clusters, alternative="greater") == pytest.approx(
        cluster_signflip_pvalue(neg, clusters, alternative="less")
    )


def test_two_sided_relates_to_one_sided_exact():
    # Under exact enumeration the null distribution is symmetric, so
    # two-sided p = 2 * min(one-sided) whenever the observed total is non-zero and untied.
    rng = random.Random(11)
    clusters = [f"c{i // 2}" for i in range(24)]
    diffs = [rng.gauss(0.1, 1.0) for _ in clusters]
    g = cluster_signflip_pvalue(diffs, clusters, alternative="greater")
    l = cluster_signflip_pvalue(diffs, clusters, alternative="less")
    two = cluster_signflip_pvalue(diffs, clusters)
    assert two == pytest.approx(2 * min(g, l))


def test_strong_effect_gives_small_p():
    # Ten clusters, every one positive. Exact: only the all-plus and all-minus patterns
    # reach |total| >= observed, so p = 2 / 2**10.
    clusters = [f"s{i // 3}" for i in range(30)]
    diffs = [1.0 + 0.01 * i for i in range(30)]
    assert cluster_signflip_pvalue(diffs, clusters) == pytest.approx(2 / 1024)
    # Nineteen clusters, Monte Carlo at the default n_perm: p near the 1 / 10,001 floor.
    clusters19 = [f"s{i // 6}" for i in range(114)]
    diffs19 = [0.5 + 0.001 * i for i in range(114)]
    p = cluster_signflip_pvalue(diffs19, clusters19)
    assert p < 0.002


def test_null_effect_gives_large_p():
    clusters = [f"s{i // 2}" for i in range(20)]
    diffs = [1.0, -1.0] * 10  # every cluster sums to exactly 0 -> every pattern ties
    assert cluster_signflip_pvalue(diffs, clusters) == pytest.approx(1.0)


def test_monte_carlo_is_deterministic_under_seed():
    clusters = [f"s{i // 6}" for i in range(114)]
    rng = random.Random(3)
    diffs = [rng.gauss(0.03, 0.4) for _ in clusters]
    a = cluster_signflip_pvalue(diffs, clusters, n_perm=5000, seed=7)
    b = cluster_signflip_pvalue(diffs, clusters, n_perm=5000, seed=7)
    assert a == b
    assert signflip_details(diffs, clusters, n_perm=5000, seed=7)["method"] == "monte_carlo"


def test_monte_carlo_close_to_exact():
    # G = 12 -> 4096 patterns. Exact with n_perm = 4096; Monte Carlo with 4095 draws must
    # land within a few binomial standard errors of it.
    rng = random.Random(21)
    clusters = [f"s{i // 3}" for i in range(36)]
    diffs = [rng.gauss(0.15, 1.0) for _ in clusters]
    exact = cluster_signflip_pvalue(diffs, clusters, n_perm=4096)
    mc = cluster_signflip_pvalue(diffs, clusters, n_perm=4095, seed=1)
    se = max(1e-3, (exact * (1 - exact) / 4095) ** 0.5)
    assert abs(mc - exact) < 5 * se


def test_bad_arguments_raise():
    with pytest.raises(ValueError):
        cluster_signflip_pvalue([1.0], ["a"], alternative="bigger")
    with pytest.raises(ValueError):
        cluster_signflip_pvalue([1.0, 2.0], ["a"])
    with pytest.raises(ValueError):
        cluster_signflip_pvalue([], [])
    with pytest.raises(ValueError):
        cluster_signflip_pvalue([float("nan")], ["a"])
    with pytest.raises(ValueError):
        wild_cluster_bootstrap_ci([1.0, 2.0], ["a", "b"], weights="mammen")
    with pytest.raises(ValueError):
        wild_cluster_bootstrap_ci([1.0, 2.0], ["a", "b"], level=1.5)


def test_webb_points_are_mean_zero_variance_one():
    assert WEBB_POINTS.mean() == pytest.approx(0.0, abs=1e-12)
    assert (WEBB_POINTS**2).mean() == pytest.approx(1.0)
    assert len(WEBB_POINTS) == 6


@pytest.mark.parametrize("weights", ["rademacher", "webb"])
def test_wild_ci_contains_mean_and_is_deterministic(weights):
    rng = random.Random(9)
    clusters = [f"s{i // 6}" for i in range(114)]
    diffs = [rng.gauss(0.05, 0.3) for _ in clusters]
    mean = sum(diffs) / len(diffs)
    lo, hi = wild_cluster_bootstrap_ci(diffs, clusters, weights=weights, seed=4)
    assert lo < mean < hi
    assert (lo, hi) == wild_cluster_bootstrap_ci(diffs, clusters, weights=weights, seed=4)


@pytest.mark.parametrize("weights", ["rademacher", "webb"])
def test_wild_ci_shrinks_with_n(weights):
    # Same data-generating process; 10x the clusters should cut the width by ~sqrt(10).
    rng = random.Random(13)
    small_c = [f"s{i // 3}" for i in range(60)]  # 20 clusters
    small_d = [rng.gauss(0.1, 1.0) for _ in small_c]
    big_c = [f"s{i // 3}" for i in range(600)]  # 200 clusters
    big_d = [rng.gauss(0.1, 1.0) for _ in big_c]
    lo_s, hi_s = wild_cluster_bootstrap_ci(small_d, small_c, weights=weights)
    lo_b, hi_b = wild_cluster_bootstrap_ci(big_d, big_c, weights=weights)
    assert (hi_b - lo_b) < 0.6 * (hi_s - lo_s)


def test_wild_draws_are_symmetric_about_point_rademacher_variance():
    # With Rademacher weights, Var(draw) = sum_g E_g**2 / N**2 exactly in expectation.
    clusters = ["a", "a", "b", "b", "c", "c", "d", "d"]
    diffs = [1.0, 0.0, 0.5, 0.5, -1.0, 0.0, 2.0, 1.0]
    point, draws = wild_cluster_draws(diffs, clusters, n_boot=40_000, seed=2)
    mean = sum(diffs) / len(diffs)
    assert point == pytest.approx(mean)
    sums = {"a": 1.0, "b": 1.0, "c": -1.0, "d": 3.0}
    size = 2
    resid = [s - size * mean for s in sums.values()]
    expected_var = sum(r * r for r in resid) / len(diffs) ** 2
    assert np.var(draws) == pytest.approx(expected_var, rel=0.05)
    assert np.mean(draws) == pytest.approx(mean, abs=0.01)


def test_wild_ci_index_rule_matches_repo_percentile_convention():
    clusters = [f"s{i // 2}" for i in range(40)]
    rng = random.Random(17)
    diffs = [rng.gauss(0.0, 1.0) for _ in clusters]
    _p, draws = wild_cluster_draws(diffs, clusters, n_boot=10_000, seed=3)
    lo, hi = wild_cluster_bootstrap_ci(diffs, clusters, n_boot=10_000, seed=3)
    assert lo == draws[int(0.025 * 10_000)]
    assert hi == draws[int(0.975 * 10_000)]


# ---- registered_signflip: A1 r2 §5.5 ------------------------------------------------------


def _brute_force_p(diffs, clusters, threshold, alternative):
    """Every sign pattern, one at a time, in plain Python: the definition, not the numpy path."""
    import itertools

    labels = sorted(set(clusters))
    sums = {g: sum(d - threshold for d, c in zip(diffs, clusters) if c == g) for g in labels}
    n = len(diffs)
    t_obs = sum(sums.values()) / n
    hits = 0
    total = 0
    for signs in itertools.product((1.0, -1.0), repeat=len(labels)):
        t = sum(s * sums[g] for s, g in zip(signs, labels)) / n
        total += 1
        if alternative == "greater":
            hits += t >= t_obs - 1e-12
        elif alternative == "less":
            hits += t <= t_obs + 1e-12
        else:
            hits += abs(t) >= abs(t_obs) - 1e-12
    return hits / total


@pytest.mark.parametrize("alternative", ["two-sided", "greater", "less"])
@pytest.mark.parametrize("threshold", [0.0, -0.07])
def test_registered_exact_agrees_with_a_brute_force_loop(alternative, threshold):
    from scripts.analysis.cluster_inference import registered_signflip

    rng = random.Random(11)
    clusters = [f"sc{g}" for g in range(9) for _ in range(rng.randint(1, 4))]
    diffs = [rng.choice([-1.0, -0.5, 0.0, 0.25, 0.5, 1.0]) for _ in clusters]
    got = registered_signflip(diffs, clusters, threshold=threshold, alternative=alternative)
    assert got["method"] == "exact" and got["n_patterns"] == 2 ** 9
    assert got["p"] == pytest.approx(_brute_force_p(diffs, clusters, threshold, alternative), abs=1e-12)
    assert got["threshold"] == threshold and got["alternative"] == alternative


def test_registered_is_exact_up_to_two_pow_20_and_monte_carlo_above():
    from scripts.analysis.cluster_inference import (
        REGISTERED_EXACT_MAX_PATTERNS, REGISTERED_MC_PATTERNS, registered_signflip)

    assert (REGISTERED_EXACT_MAX_PATTERNS, REGISTERED_MC_PATTERNS) == (2 ** 20, 100_000)
    rng = random.Random(5)
    at_limit = [f"c{g}" for g in range(20) for _ in range(2)]
    d20 = [rng.gauss(0.1, 1.0) for _ in at_limit]
    exact = registered_signflip(d20, at_limit)
    assert (exact["method"], exact["n_patterns"], exact["n_clusters"]) == ("exact", 2 ** 20, 20)
    above = [f"c{g}" for g in range(21) for _ in range(2)]
    d21 = [rng.gauss(0.1, 1.0) for _ in above]
    mc = registered_signflip(d21, above)
    assert (mc["method"], mc["n_patterns"], mc["n_clusters"]) == ("monte_carlo", 100_000, 21)
    assert mc["seed"] == 20260924
    assert mc == registered_signflip(d21, above)  # deterministic at the registered seed
    # p = (1 + count) / (1 + 100,000)
    assert mc["p"] == pytest.approx((1 + mc["n_as_extreme"]) / (1 + 100_000))


def test_registered_one_sided_non_inferiority_direction():
    # An arm 5 pp BELOW its ceiling is still well above a -7 pp margin: the shifted mean is
    # +2 pp in every cluster, so only the identity pattern reaches it -> p = 1 / 2**G.
    from scripts.analysis.cluster_inference import registered_signflip

    clusters = [f"s{g}" for g in range(6) for _ in range(3)]
    diffs = [-0.05] * len(clusters)
    got = registered_signflip(diffs, clusters, threshold=-0.07, alternative="greater")
    assert got["p"] == pytest.approx(1 / 2 ** 6)
    # The same data tested at the margin in the other direction is no evidence at all.
    assert registered_signflip(diffs, clusters, threshold=-0.07, alternative="less")["p"] == 1.0
