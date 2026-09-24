"""Small-cluster inference for paired per-episode differences.

Why this exists
---------------
Every headline interval in this project is a percentile cluster bootstrap over 19 scenario
clusters (57 task clusters on the secondary clustering). A reviewer's standing objection is
that 19 clusters is few for a percentile interval: resampling clusters with replacement
gives a variance estimate close to the CR0 sandwich, which is known to under-cover when G is
small. This module supplies two alternatives that operate on exactly the same input -- one
paired difference per episode plus that episode's cluster label -- so any headline can be
re-read under them without touching the loaders that produced the differences.

``cluster_signflip_pvalue``
    A randomization test. Under H0 each cluster's summed difference is symmetric about
    zero, so flipping the sign of *all* of a cluster's differences jointly leaves the
    distribution unchanged. The statistic is the mean of the per-episode differences.
    When 2**G <= n_perm every one of the 2**G sign patterns is enumerated and the p-value
    is exact (no Monte Carlo error at all); otherwise n_perm random patterns are drawn and
    p = (1 + #{as or more extreme}) / (1 + n_perm). The test's validity does not depend on
    G being large, which is the point.

``wild_cluster_bootstrap_ci``
    The mean plus cluster-level perturbations of the centred residuals: each bootstrap
    draw is ``mean + sum_g w_g * E_g / N`` with ``E_g`` the cluster sum of
    ``diff - mean`` and ``w_g`` i.i.d. Rademacher (+/-1) or Webb six-point weights. The
    interval is the percentile interval of the resampled mean, using the same index rule
    as every percentile interval in this repo (``sorted[int(a/2 * B)]``,
    ``sorted[int((1 - a/2) * B)]``; ``scripts/setup/hj1_gate.py`` ``paired_diff``).

⚠ What the wild interval is and is not. It is NOT studentized and it uses UNRESTRICTED
residuals, so its variance is the CR0 cluster variance ``sum_g E_g**2 / N**2`` -- the same
quantity the pairs cluster bootstrap approximates. It is symmetric about the point estimate
by construction (Rademacher and Webb weights are symmetric), so it differs from the
percentile interval mainly by removing resampling asymmetry and the discreteness of which
clusters get drawn. It is a sensitivity reading, not a small-G correction; the sign-flip
test is the component whose size does not rely on G being large.

Pure numpy; no scipy. Deterministic given ``seed``.
"""

from __future__ import annotations

from typing import Any, Hashable, Sequence

import numpy as np

DEFAULT_SEED = 20260924
ALTERNATIVES = ("two-sided", "greater", "less")
WEIGHT_SCHEMES = ("rademacher", "webb")

# Webb (2014) six-point distribution: +/- sqrt(1/2), +/- 1, +/- sqrt(3/2), each w.p. 1/6.
# Mean 0, variance 1, and -- unlike Rademacher -- 6**G distinct patterns, which matters
# when G is small enough that 2**G patterns leave the bootstrap distribution lumpy.
WEBB_POINTS = np.array(
    [
        -np.sqrt(1.5),
        -1.0,
        -np.sqrt(0.5),
        np.sqrt(0.5),
        1.0,
        np.sqrt(1.5),
    ]
)

# Relative tolerance for "as or more extreme". Paired differences on this project's
# metrics are discrete (TGC is 0/1 per episode), so the permuted statistic ties the
# observed one exactly, and floating-point summation order must not break a real tie.
_TIE_RTOL = 1e-9
_ENUM_CHUNK = 1 << 16


def _cluster_sums(
    diffs: Sequence[float], clusters: Sequence[Hashable]
) -> tuple[np.ndarray, np.ndarray, int]:
    """Validate inputs; return (per-cluster sums, per-cluster sizes, N).

    Clusters are indexed in a deterministic sorted-label order, so a result never depends
    on the order in which episodes were supplied.
    """
    d = np.asarray(list(diffs), dtype=float)
    labels = list(clusters)
    if d.ndim != 1:
        raise ValueError("diffs must be one-dimensional")
    if len(labels) != d.shape[0]:
        raise ValueError(
            f"diffs and clusters differ in length ({d.shape[0]} vs {len(labels)})"
        )
    if d.shape[0] == 0:
        raise ValueError("no differences supplied")
    if not np.all(np.isfinite(d)):
        raise ValueError("diffs contain a non-finite value; drop missing pairs first")
    order: dict[Hashable, int] = {}
    for lab in sorted(set(labels), key=lambda x: (str(type(x)), str(x))):
        order[lab] = len(order)
    idx = np.fromiter((order[lab] for lab in labels), dtype=np.int64, count=len(labels))
    sums = np.bincount(idx, weights=d, minlength=len(order))
    sizes = np.bincount(idx, minlength=len(order)).astype(float)
    return sums, sizes, int(d.shape[0])


def _check_alternative(alternative: str) -> None:
    if alternative not in ALTERNATIVES:
        raise ValueError(f"alternative must be one of {ALTERNATIVES}, got {alternative!r}")


def _count_extreme(
    stats: np.ndarray, observed: float, alternative: str, tol: float
) -> int:
    if alternative == "two-sided":
        return int(np.count_nonzero(np.abs(stats) >= abs(observed) - tol))
    if alternative == "greater":
        return int(np.count_nonzero(stats >= observed - tol))
    return int(np.count_nonzero(stats <= observed + tol))


def signflip_details(
    diffs: Sequence[float],
    clusters: Sequence[Hashable],
    *,
    n_perm: int = 10_000,
    seed: int = DEFAULT_SEED,
    alternative: str = "two-sided",
) -> dict[str, Any]:
    """``cluster_signflip_pvalue`` plus the bookkeeping a report needs.

    Returns ``p``, ``method`` ('exact' or 'monte_carlo'), ``n_patterns``, ``n_clusters``,
    ``n_obs``, ``statistic`` (the observed mean) and ``n_as_extreme``.
    """
    _check_alternative(alternative)
    if n_perm < 1:
        raise ValueError("n_perm must be >= 1")
    sums, _sizes, n_obs = _cluster_sums(diffs, clusters)
    n_clusters = int(sums.shape[0])
    observed = float(sums.sum() / n_obs)
    tol = _TIE_RTOL * max(1.0, float(np.abs(sums).sum()) / n_obs)

    exact = n_clusters < 63 and (1 << n_clusters) <= n_perm
    if exact:
        total = 1 << n_clusters
        bits = np.arange(n_clusters, dtype=np.int64)
        count = 0
        for start in range(0, total, _ENUM_CHUNK):
            codes = np.arange(start, min(start + _ENUM_CHUNK, total), dtype=np.int64)
            signs = 1.0 - 2.0 * ((codes[:, None] >> bits[None, :]) & 1)
            stats = signs @ sums / n_obs
            count += _count_extreme(stats, observed, alternative, tol)
        p = count / total
        return {
            "p": float(p),
            "method": "exact",
            "n_patterns": int(total),
            "n_clusters": n_clusters,
            "n_obs": n_obs,
            "statistic": observed,
            "n_as_extreme": int(count),
            "alternative": alternative,
        }

    rng = np.random.default_rng(seed)
    count = 0
    done = 0
    while done < n_perm:
        m = min(_ENUM_CHUNK, n_perm - done)
        signs = rng.choice(np.array([-1.0, 1.0]), size=(m, n_clusters))
        stats = signs @ sums / n_obs
        count += _count_extreme(stats, observed, alternative, tol)
        done += m
    p = (1 + count) / (1 + n_perm)
    return {
        "p": float(min(1.0, p)),
        "method": "monte_carlo",
        "n_patterns": int(n_perm),
        "n_clusters": n_clusters,
        "n_obs": n_obs,
        "statistic": observed,
        "n_as_extreme": int(count),
        "alternative": alternative,
        "seed": seed,
    }


def cluster_signflip_pvalue(
    diffs: Sequence[float],
    clusters: Sequence[Hashable],
    *,
    n_perm: int = 10_000,
    seed: int = DEFAULT_SEED,
    alternative: str = "two-sided",
) -> float:
    """Cluster sign-flip randomization p-value for H0: mean paired difference = 0.

    The statistic is the mean of the per-episode ``diffs``. A permutation multiplies every
    difference in a cluster by the same sign. All 2**G patterns are enumerated when
    2**G <= n_perm (exact p, identity pattern included); otherwise ``n_perm`` random
    patterns are drawn with ``seed`` and p = (1 + count) / (1 + n_perm).

    alternative: 'two-sided' (|T*| >= |T|), 'greater' (T* >= T), 'less' (T* <= T).
    To test a non-zero null value d0, pass ``[d - d0 for d in diffs]``.
    """
    return signflip_details(
        diffs, clusters, n_perm=n_perm, seed=seed, alternative=alternative
    )["p"]


# The registered sign-flip of Amendment A1 r2 §5.5 (docs/prereg_j10_amendment_20260924.md:310-318):
# exact when the cluster count gives <= 2**20 sign patterns, otherwise Monte Carlo over 100,000
# patterns at seed 20260924. j10_report (every A1 prediction) and b2_decomposition (every B2
# contrast) call this one routine, so the J10 read and the B2 decomposition cannot disagree on it.
REGISTERED_EXACT_MAX_PATTERNS = 1 << 20
REGISTERED_MC_PATTERNS = 100_000


def registered_signflip(
    diffs: Sequence[float],
    clusters: Sequence[Hashable],
    *,
    threshold: float = 0.0,
    alternative: str = "two-sided",
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """A1 r2 §5.5 cluster sign-flip p at ``threshold``, with its bookkeeping.

    Exactly what is computed. Let d_i be episode i's paired difference, t the threshold,
    S_g = sum over episodes i in cluster g of (d_i - t), N the number of episodes and, for a
    sign vector s in {-1, +1}^G, T(s) = sum_g s_g S_g / N; T_obs = T(1, ..., 1), the observed
    shifted mean. With tol = 1e-9 * max(1, sum_g |S_g| / N) (ties on discrete metrics count):

        extreme(s):  'greater'   T(s) >= T_obs - tol
                     'less'      T(s) <= T_obs + tol
                     'two-sided' |T(s)| >= |T_obs| - tol

        exact (2**G <= 2**20):  p = #{s in {-1,+1}^G : extreme(s)} / 2**G   (identity included)
        otherwise:              p = (1 + #{b <= 100,000 : extreme(s_b)}) / (1 + 100,000),
                                s_b drawn i.i.d. uniform from numpy default_rng(seed).

    A non-inferiority prediction at margin -m (A1 P3: prefix_m11 - planner_alone_cap81 above
    -7.00 pp) is threshold = -0.07, alternative = 'greater': H0 is a mean at the margin, and
    evidence against it is a shifted mean that few flipped patterns reach. The enumeration is
    signflip_details' chunked numpy product (65,536 patterns x G per chunk).
    """
    shifted = [float(d) - float(threshold) for d in diffs]
    sums, _sizes, _n = _cluster_sums(shifted, clusters)
    n_clusters = int(sums.shape[0])
    exact = n_clusters < 63 and (1 << n_clusters) <= REGISTERED_EXACT_MAX_PATTERNS
    n_perm = (1 << n_clusters) if exact else REGISTERED_MC_PATTERNS
    out = signflip_details(shifted, clusters, n_perm=n_perm, seed=seed, alternative=alternative)
    out.update(
        threshold=float(threshold),
        rule="A1 r2 §5.5: exact if 2^G <= 2^20, else Monte Carlo over 100,000 patterns",
    )
    return out


def _weights(scheme: str, rng: np.random.Generator, size: tuple[int, int]) -> np.ndarray:
    if scheme == "rademacher":
        return rng.choice(np.array([-1.0, 1.0]), size=size)
    if scheme == "webb":
        return rng.choice(WEBB_POINTS, size=size)
    raise ValueError(f"weights must be one of {WEIGHT_SCHEMES}, got {scheme!r}")


def wild_cluster_draws(
    diffs: Sequence[float],
    clusters: Sequence[Hashable],
    *,
    n_boot: int = 10_000,
    seed: int = DEFAULT_SEED,
    weights: str = "rademacher",
) -> tuple[float, np.ndarray]:
    """Return (point estimate, sorted array of the n_boot resampled means)."""
    if weights not in WEIGHT_SCHEMES:
        raise ValueError(f"weights must be one of {WEIGHT_SCHEMES}, got {weights!r}")
    if n_boot < 1:
        raise ValueError("n_boot must be >= 1")
    sums, n_g, n_obs = _cluster_sums(diffs, clusters)
    point = float(sums.sum() / n_obs)
    # Cluster sums of the centred residuals: E_g = S_g - n_g * mean.
    resid = sums - n_g * point
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot, dtype=float)
    done = 0
    while done < n_boot:
        m = min(_ENUM_CHUNK, n_boot - done)
        w = _weights(weights, rng, (m, resid.shape[0]))
        draws[done : done + m] = point + (w @ resid) / n_obs
        done += m
    draws.sort()
    return point, draws


def wild_cluster_bootstrap_ci(
    diffs: Sequence[float],
    clusters: Sequence[Hashable],
    *,
    n_boot: int = 10_000,
    seed: int = DEFAULT_SEED,
    level: float = 0.95,
    weights: str = "rademacher",
) -> tuple[float, float]:
    """Wild cluster bootstrap percentile interval for the mean paired difference.

    Residuals ``diff - mean`` are summed within cluster; each draw multiplies every
    cluster's residual sum by one weight (Rademacher +/-1, or Webb six-point) and adds the
    result, divided by N, to the mean. The interval is the percentile interval of the
    draws with the repo's index rule. Returned in the units of ``diffs``.
    """
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0, 1)")
    _point, draws = wild_cluster_draws(
        diffs, clusters, n_boot=n_boot, seed=seed, weights=weights
    )
    alpha = 1.0 - level
    lo_idx = int((alpha / 2.0) * n_boot)
    hi_idx = min(n_boot - 1, int((1.0 - alpha / 2.0) * n_boot))
    return float(draws[lo_idx]), float(draws[hi_idx])


def by_fdr(pvalues: Sequence[float]) -> list[float]:
    """Benjamini-Yekutieli step-up adjusted p-values, returned in input order.

    ``p_(i) * m * c(m) / i`` with ``c(m) = sum_{j=1..m} 1/j``, made monotone from the
    largest rank down (the minimum over ranks >= i) and capped at 1. Valid under arbitrary
    dependence between the tests, which is why it -- not Benjamini-Hochberg -- is the
    paper-wide sensitivity: the contrasts share arms and so are correlated by construction.
    A sensitivity reading only; no registered verdict is decided by it.
    """
    m = len(pvalues)
    if m == 0:
        return []
    for p in pvalues:
        if not 0.0 <= float(p) <= 1.0:
            raise ValueError(f"p-value out of [0, 1]: {p!r}")
    c_m = sum(1.0 / j for j in range(1, m + 1))
    order = sorted(range(m), key=lambda i: (float(pvalues[i]), i))
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        running = min(running, min(1.0, float(pvalues[idx]) * m * c_m / rank))
        adjusted[idx] = running
    return adjusted


__all__ = [
    "by_fdr",
    "cluster_signflip_pvalue",
    "registered_signflip",
    "REGISTERED_EXACT_MAX_PATTERNS",
    "REGISTERED_MC_PATTERNS",
    "wild_cluster_bootstrap_ci",
    "signflip_details",
    "wild_cluster_draws",
    "WEBB_POINTS",
]
