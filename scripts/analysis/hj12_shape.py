#!/usr/bin/env python3
"""HJ-13 registered shape test (docs/prereg_hj13_shape_20260923.md §3).

Implements the frozen segmented-linear protocol. Does not choose a different
test. Results on hj12_prefix_*_20260922 and *_20260923 are exploratory.

Interface:
  python scripts/analysis/hj12_shape.py
      [--out-pre PATH] [--out-post PATH] [--n-boot 10000]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_J8_SPEC = importlib.util.spec_from_file_location(
    "j8_frontier", Path(__file__).resolve().parent / "j8_frontier.py"
)
j8 = importlib.util.module_from_spec(_J8_SPEC)
assert _J8_SPEC.loader is not None
_J8_SPEC.loader.exec_module(j8)

_J10_SPEC = importlib.util.spec_from_file_location(
    "j10_report", Path(__file__).resolve().parent / "j10_report.py"
)
j10 = importlib.util.module_from_spec(_J10_SPEC)
assert _J10_SPEC.loader is not None
_J10_SPEC.loader.exec_module(j10)

from scripts.setup.hj1_gate import (  # noqa: E402
    BOOTSTRAP,
    SEED,
    _draw_task_clusters,
    scenario_of,
)

M_GRID = (0, 2, 4, 6, 7, 8, 9, 10, 11)
PREFIX_M = (2, 4, 6, 7, 8, 9, 10, 11)
TAU_CANDIDATES = (4, 6, 7, 8, 9)
MIN_ROWS = 114
REPLICATE_FLOOR_PP = 3.31
ADVICE_CHANNEL_CONTRAST_PP = -0.48
ADVICE_CHANNEL_SOURCE = (
    "campaign/results/hj12_unified_frontier_20260922.report.json "
    "contrasts.goal_pass_rate_advise_fixed_k_10_minus_advise_fixed_k_3"
)
RESULTS_DIR = Path("/scratch/n12194778/sidekick/results")
SFT_PLAN_DIR = RESULTS_DIR / "hj8_sft_plan_bplus_20260921iaware"
PLANNER_ALONE_DIR = RESULTS_DIR / "hj1b_planner_20260915"
DEFAULT_OUT_PRE = (
    REPO_ROOT / "campaign" / "results" / "hj13_shape_pre_guard_20260923.report.json"
)
DEFAULT_OUT_POST = (
    REPO_ROOT / "campaign" / "results" / "hj13_shape_post_guard_20260923.report.json"
)
HELD_OUT_MARKERS = ("test_normal", "test_challenge")

REUSED_FROM_J8 = [
    "j8_frontier.summarise_arm",
    "j8_frontier.handoff_flag_keys",
    "j8_frontier.restrict_to_defining_handoff",
    "j8_frontier.resolve_handoff_keys_arm",
    "j8_frontier.coerce_crash_quality",
    "j8_frontier.is_crashed",
    "j8_frontier.ci_excludes_zero",
    "j8_frontier.mean_quality",
    "j8_frontier.paired_diff_scenario (scenario clustering has landed; "
    "curve bootstrap reuses the same _draw_task_clusters resampler grouped "
    "by scenario_of, rather than writing a second resampler)",
    "j10_report.load_arm_tree",
    "hj1_gate._draw_task_clusters",
    "hj1_gate.scenario_of",
    "hj1_gate.BOOTSTRAP",
    "hj1_gate.SEED",
]


def refuse_heldout(path: Path) -> None:
    text = str(path)
    for marker in HELD_OUT_MARKERS:
        if marker in text:
            raise RuntimeError(f"refusing held-out split path {path}")


def hinge(x: float, tau: float) -> float:
    return max(float(x) - float(tau), 0.0)


def design_row(x: float, tau: float) -> list[float]:
    return [1.0, float(x), hinge(x, tau)]


def solve_linear(a: list[list[float]], b: list[float]) -> Optional[list[float]]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            for j in range(col, n + 1):
                m[r][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def ols_segmented(
    xs: list[float], ys: list[float], tau: float
) -> tuple[Optional[list[float]], float]:
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    for x, y in zip(xs, ys):
        row = design_row(x, tau)
        for i in range(3):
            xty[i] += row[i] * float(y)
            for j in range(3):
                xtx[i][j] += row[i] * row[j]
    beta = solve_linear(xtx, xty)
    if beta is None:
        return None, float("inf")
    rss = 0.0
    for x, y in zip(xs, ys):
        pred = sum(b * r for b, r in zip(beta, design_row(x, tau)))
        err = float(y) - pred
        rss += err * err
    return beta, rss


def fit_segmented(
    ms: list[int] | list[float],
    qs: list[float],
    *,
    taus: Iterable[float] = TAU_CANDIDATES,
    x_of_m: dict[Any, float] | None = None,
) -> dict[str, Any]:
    """Profile RSS over tau candidates. Ties take the smallest tau."""
    if len(ms) != len(qs) or len(ms) < 3:
        return {
            "tau": None,
            "beta0": None,
            "beta1": None,
            "beta2": None,
            "rss": None,
            "n_points": len(ms),
            "note": "need at least 3 (m, q) points",
        }
    xs = [float(x_of_m[m]) if x_of_m is not None else float(m) for m in ms]
    ranked: list[tuple[float, float, list[float]]] = []
    for tau_m in taus:
        tau_x = float(x_of_m[tau_m]) if x_of_m is not None else float(tau_m)
        beta, rss = ols_segmented(xs, qs, tau_x)
        if beta is None:
            continue
        ranked.append((rss, float(tau_m), beta))
    if not ranked:
        return {
            "tau": None,
            "beta0": None,
            "beta1": None,
            "beta2": None,
            "rss": None,
            "n_points": len(ms),
            "note": "all tau candidates produced a singular design",
        }
    mean_q = sum(qs) / len(qs)
    tss = sum((float(q) - mean_q) ** 2 for q in qs)
    # 1e-12 * max(tss, 1.0) absorbs floating-point noise on a straight line
    # without bridging genuine RSS gaps, which are orders of magnitude larger.
    tol = 1e-12 * max(tss, 1.0)
    best_rss = min(t[0] for t in ranked)
    tied = [t for t in ranked if t[0] <= best_rss + tol]
    tied.sort(key=lambda t: (t[1], t[0]))
    rss, tau, beta = tied[0]
    return {
        "tau": int(tau) if float(tau).is_integer() else tau,
        "beta0": beta[0],
        "beta1": beta[1],
        "beta2": beta[2],
        "beta1_plus_beta2": beta[1] + beta[2],
        "rss": rss,
        "n_points": len(ms),
        "tie_break": "smallest_tau_on_equal_rss",
        "candidates": list(taus),
    }


def planner_percentile(m: float, step_counts: list[int] | list[float]) -> float:
    """Empirical CDF in percent: 100 * #{s_i <= m} / n. Monotone in m."""
    if not step_counts:
        raise ValueError("step_counts is empty")
    n = len(step_counts)
    le = sum(1 for s in step_counts if s <= m)
    return 100.0 * le / n


def percentile_map(
    ms: Iterable[float], step_counts: list[int] | list[float]
) -> dict[float, float]:
    return {float(m): planner_percentile(m, step_counts) for m in ms}


def isotonic_pava(ys: list[float]) -> list[float]:
    blocks: list[dict[str, float | int]] = []
    for i, yi in enumerate(ys):
        blocks.append({"sum": float(yi), "n": 1, "i0": i, "i1": i})
        while (
            len(blocks) >= 2
            and blocks[-2]["sum"] / blocks[-2]["n"]
            > blocks[-1]["sum"] / blocks[-1]["n"]
        ):
            b2 = blocks.pop()
            b1 = blocks[-1]
            b1["sum"] = float(b1["sum"]) + float(b2["sum"])
            b1["n"] = int(b1["n"]) + int(b2["n"])
            b1["i1"] = b2["i1"]
    out = [0.0] * len(ys)
    for b in blocks:
        mean = float(b["sum"]) / int(b["n"])
        for i in range(int(b["i0"]), int(b["i1"]) + 1):
            out[i] = mean
    return out


def isotonic_first_exceed(
    ms: list[int], qs: list[float], floor: float, pp: float = 5.0
) -> dict[str, Any]:
    fitted = isotonic_pava(qs)
    threshold = float(floor) + pp / 100.0
    first = None
    for m, yhat in zip(ms, fitted):
        if yhat > threshold:
            first = int(m)
            break
    return {
        "label": "descriptive_uncorrected",
        "method": "isotonic_pava",
        "floor": floor,
        "exceed_by_pp": pp,
        "first_m_exceeding_floor_plus_5pp": first,
        "fitted": [{"m": int(m), "q_hat": yhat} for m, yhat in zip(ms, fitted)],
        "observed": [{"m": int(m), "q": q} for m, q in zip(ms, qs)],
    }


def percentile_interval(samples: list[float]) -> Optional[list[float]]:
    if not samples:
        return None
    s = sorted(samples)
    n = len(s)
    lo = s[int(0.025 * n)]
    hi = s[int(0.975 * n)]
    return [lo, hi]


def onesided_lower(samples: list[float]) -> Optional[float]:
    if not samples:
        return None
    s = sorted(samples)
    return s[int(0.05 * len(s))]


def cluster_keys(
    keys: list[tuple[str, int]], cluster: str
) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, list[tuple[str, int]]] = {}
    for key in keys:
        cid = scenario_of(key[0]) if cluster == "scenario" else key[0]
        grouped.setdefault(cid, []).append(key)
    return grouped


def panel_means(
    panel: dict[int, dict[tuple[str, int], float]],
    keys: list[tuple[str, int]] | None = None,
) -> dict[int, float]:
    out: dict[int, float] = {}
    for m, scores in panel.items():
        use = keys if keys is not None else list(scores)
        vals = [scores[k] for k in use if k in scores]
        if vals:
            out[int(m)] = statistics.fmean(vals)
    return out


def holm_adjusted_intervals(
    contrasts: dict[str, list[float]], alpha: float = 0.05
) -> dict[str, Any]:
    """Holm-adjusted intervals and p-values for a family of bootstrap contrasts.

    Uniformly more powerful than Bonferroni at the same family-wise error rate.
    """
    if not contrasts:
        return {
            "method": "holm",
            "alpha": alpha,
            "family": [],
            "n_comparisons": 0,
            "adjusted": {},
        }

    K = len(contrasts)
    raw_info: dict[str, dict[str, Any]] = {}
    for name, samples in contrasts.items():
        if not samples:
            raw_info[name] = {
                "p_raw": 1.0,
                "ci_raw": None,
                "samples_sorted": [],
                "n": 0,
            }
            continue
        s = sorted(float(x) for x in samples)
        n = len(s)
        n_le_0 = sum(1 for x in s if x <= 0.0)
        n_ge_0 = sum(1 for x in s if x >= 0.0)
        p_raw = min(1.0, 2.0 * min(n_le_0 / n, n_ge_0 / n))
        lo_raw = s[max(0, min(n - 1, int((alpha / 2.0) * n)))]
        hi_raw = s[max(0, min(n - 1, int((1.0 - alpha / 2.0) * n)))]
        raw_info[name] = {
            "p_raw": p_raw,
            "ci_raw": [lo_raw, hi_raw],
            "samples_sorted": s,
            "n": n,
        }

    # Sort contrasts by raw p-value ascending
    sorted_names = sorted(contrasts.keys(), key=lambda k: (raw_info[k]["p_raw"], k))

    # Holm step-down loop
    adjusted: dict[str, Any] = {}
    running_max_p = 0.0

    for i, name in enumerate(sorted_names):
        multiplier = K - i
        info = raw_info[name]
        p_raw = info["p_raw"]
        p_unclamped = float(multiplier) * p_raw
        running_max_p = max(running_max_p, p_unclamped)
        p_adj = min(1.0, running_max_p)

        s = info["samples_sorted"]
        n = info["n"]
        if n > 0:
            alpha_adj = alpha / float(multiplier)
            lo_idx = max(0, min(n - 1, int((alpha_adj / 2.0) * n)))
            hi_idx = max(0, min(n - 1, int((1.0 - alpha_adj / 2.0) * n)))
            lo_adj = s[lo_idx]
            hi_adj = s[hi_idx]
            ci_adj = [round(lo_adj, 6), round(hi_adj, 6)]
        else:
            ci_adj = None

        adjusted[name] = {
            "ci95_pp_adjusted": ci_adj,
            "p_adjusted": round(p_adj, 6),
            "survives": bool(p_adj <= alpha),
            "ci95_pp_raw": [round(v, 6) for v in info["ci_raw"]] if info["ci_raw"] else None,
            "p_raw": round(p_raw, 6),
            "multiplier": multiplier,
        }

    return {
        "method": "holm",
        "alpha": alpha,
        "family": list(contrasts.keys()),
        "n_comparisons": K,
        "adjusted": adjusted,
    }


def bootstrap_segmented(
    panel: dict[int, dict[tuple[str, int], float]],
    *,
    cluster: str = "scenario",
    n_boot: int = BOOTSTRAP,
    seed: int = SEED,
    taus: Iterable[float] = TAU_CANDIDATES,
    x_of_m: dict[Any, float] | None = None,
) -> dict[str, Any]:
    """Refit the whole segmented model, including tau, inside every resample.

    Resampler is hj1_gate._draw_task_clusters, the same function j8_frontier
    uses for the task-clustered paired bootstrap. Scenario clustering groups
    keys by scenario_of before drawing, matching j8_frontier.paired_diff_scenario.
    """
    if cluster not in {"scenario", "task"}:
        raise ValueError(f"unknown cluster {cluster!r}")
    ms = sorted(panel)
    key_sets = [set(panel[m]) for m in ms]
    keys = sorted(set.intersection(*key_sets)) if key_sets else []
    point_means = panel_means(panel, keys)
    qs = [point_means[m] for m in ms]
    point = fit_segmented(ms, qs, taus=taus, x_of_m=x_of_m)
    grouped = cluster_keys(keys, cluster)
    rng = random.Random(seed)
    tau_s: list[float] = []
    b1_s: list[float] = []
    b12_s: list[float] = []
    contrasts_b: dict[str, list[float]] = {
        f"m{ms[i]}_to_m{ms[i+1]}": [] for i in range(len(ms) - 1)
    }
    skipped = 0
    for _ in range(n_boot):
        drawn = _draw_task_clusters(grouped, rng) if grouped else []
        qs_b: list[float] = []
        ok = True
        for m in ms:
            vals = [panel[m][k] for k in drawn if k in panel[m]]
            if not vals:
                ok = False
                break
            qs_b.append(sum(vals) / len(vals))
        if not ok:
            skipped += 1
            continue
        fit = fit_segmented(ms, qs_b, taus=taus, x_of_m=x_of_m)
        if fit["tau"] is None:
            skipped += 1
            continue
        tau_s.append(float(fit["tau"]))
        b1_s.append(float(fit["beta1"]))
        b12_s.append(float(fit["beta1_plus_beta2"]))
        for i in range(len(ms) - 1):
            pair_key = f"m{ms[i]}_to_m{ms[i+1]}"
            contrasts_b[pair_key].append((qs_b[i+1] - qs_b[i]) * 100.0)
    tau_ci = percentile_interval(tau_s)
    b1_ci = percentile_interval(b1_s)
    b12_ci = percentile_interval(b12_s)
    b12_lo_os = onesided_lower(b12_s)
    tau_counts = {int(k): int(v) for k, v in sorted(Counter(int(t) for t in tau_s).items())}
    uninformative = bool(
        tau_ci is not None and tau_ci[0] <= min(TAU_CANDIDATES) and tau_ci[1] >= max(TAU_CANDIDATES)
    )
    return {
        "point": point,
        "means": {str(m): point_means[m] for m in ms},
        "n_keys": len(keys),
        "n_clusters": len(grouped),
        "cluster": cluster,
        "n_boot": n_boot,
        "n_kept": len(tau_s),
        "n_skipped": skipped,
        "seed": seed,
        "tau": point["tau"],
        "tau_ci95": tau_ci,
        "tau_counts": tau_counts,
        "tau_interval_uninformative": uninformative,
        "tau_n_distinct_in_bootstrap": len(tau_counts),
        "beta0": point["beta0"],
        "beta1": point["beta1"],
        "beta1_ci95": b1_ci,
        "beta2": point["beta2"],
        "beta1_plus_beta2": point["beta1_plus_beta2"],
        "beta1_plus_beta2_ci95": b12_ci,
        "beta1_plus_beta2_onesided95_lower": b12_lo_os,
        "adjacent_contrasts": contrasts_b,
        "resampler": "hj1_gate._draw_task_clusters",
    }


def s1_s2_s3(boot: dict[str, Any]) -> dict[str, Any]:
    b1_ci = boot.get("beta1_ci95")
    b12_lo = boot.get("beta1_plus_beta2_onesided95_lower")
    tau_ci = boot.get("tau_ci95")
    s1_rejected = bool(j8.ci_excludes_zero(b1_ci))
    s1_holds = not s1_rejected and b1_ci is not None
    s2_holds = b12_lo is not None and float(b12_lo) > 0.0
    s3_holds = tau_ci is not None and float(tau_ci[0]) > 4.0
    supported = bool(s1_holds and s2_holds and s3_holds)
    return {
        "S1_pre_threshold_flatness": {
            "hypothesis": "beta1 = 0",
            "rejected": s1_rejected,
            "holds": s1_holds,
            "beta1": boot.get("beta1"),
            "beta1_ci95": b1_ci,
            "rule": "rejected only if the interval for beta1 excludes zero",
        },
        "S2_post_threshold_rise": {
            "hypothesis": "beta1 + beta2 > 0, one-sided 95%",
            "holds": s2_holds,
            "beta1_plus_beta2": boot.get("beta1_plus_beta2"),
            "beta1_plus_beta2_ci95": boot.get("beta1_plus_beta2_ci95"),
            "onesided95_lower": b12_lo,
            "rule": "holds iff the 5th percentile of bootstrap (beta1+beta2) is > 0",
        },
        "S3_threshold_is_real": {
            "hypothesis": "bootstrap interval for tau excludes m <= 4",
            "holds": s3_holds,
            "tau": boot.get("tau"),
            "tau_ci95": tau_ci,
            "tau_interval_uninformative": boot.get("tau_interval_uninformative"),
            "rule": "holds iff the 2.5th percentile of bootstrap tau is > 4",
        },
        "shape_claim_supported": supported,
        "verdict": (
            "shape claim supported" if supported else "no threshold established"
        ),
        "family": "S1-S3 one family; robustness descriptive and uncorrected",
        "analysis_status": "exploratory",
    }


def episode_quality(row: dict[str, Any], field: str, crash_as_zero: bool) -> Optional[float]:
    if crash_as_zero and j8.is_crashed(row):
        return 0.0
    raw = row.get(field)
    if raw is None:
        return None
    return float(raw)


def attach_executor_n_calls(
    cleaned: dict[tuple[str, int], dict[str, Any]],
    runs: dict[tuple[str, int], dict[str, Any]],
) -> None:
    for key, row in cleaned.items():
        raw = runs.get(key) or {}
        totals = raw.get("totals") if isinstance(raw.get("totals"), dict) else {}
        per_actor = (
            totals.get("per_actor") if isinstance(totals.get("per_actor"), dict) else {}
        )
        ex = per_actor.get("executor") if isinstance(per_actor.get("executor"), dict) else {}
        n = ex.get("n_calls")
        row["executor_n_calls"] = None if n is None else int(n)


def load_named_arm(label: str, root: Path, seeds: list[int]) -> dict[str, Any]:
    refuse_heldout(root)
    loaded = j10.load_arm_tree(root)
    arm = j8.summarise_arm(label, loaded, seeds, root=root)
    attach_executor_n_calls(arm["cleaned"], loaded["runs"])
    return arm


def shared_keys(arms: dict[str, dict[str, Any]]) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] | None = None
    for arm in arms.values():
        s = set(arm["cleaned"])
        keys = s if keys is None else keys & s
    return keys or set()


def survivor_keys(
    arms: dict[str, dict[str, Any]], keys: set[tuple[str, int]]
) -> set[tuple[str, int]]:
    kept = set()
    for key in keys:
        ok = True
        for arm in arms.values():
            row = arm["cleaned"].get(key)
            if row is None or j8.is_crashed(row):
                ok = False
                break
        if ok:
            kept.add(key)
    return kept


def pinned_keys(
    defining: dict[str, Any], others: list[dict[tuple[str, int], dict[str, Any]]]
) -> tuple[set[tuple[str, int]], int, int]:
    return j8.restrict_to_defining_handoff(defining["cleaned"], others, True)


def make_panel(
    m_to_arm: dict[int, dict[str, Any]],
    keys: set[tuple[str, int]],
    field: str,
    crash_as_zero: bool,
) -> dict[int, dict[tuple[str, int], float]]:
    panel: dict[int, dict[tuple[str, int], float]] = {}
    for m, arm in m_to_arm.items():
        scores: dict[tuple[str, int], float] = {}
        for key in keys:
            row = arm["cleaned"].get(key)
            if row is None:
                continue
            val = episode_quality(row, field, crash_as_zero)
            if val is None:
                continue
            scores[key] = val
        panel[int(m)] = scores
    return panel


def silenced_count(arm: dict[str, Any]) -> int:
    return sum(
        1
        for row in arm["cleaned"].values()
        if row.get("executor_n_calls") == 0
    )


def shape04_reconciliation(defining: dict[str, Any]) -> dict[str, Any]:
    cleaned = defining["cleaned"]
    flag_true = j8.handoff_flag_keys(cleaned, True)
    ncalls_pos = {
        key
        for key, row in cleaned.items()
        if row.get("executor_n_calls") is not None
        and int(row["executor_n_calls"]) > 0
    }
    only_flag = sorted(flag_true - ncalls_pos)
    only_calls = sorted(ncalls_pos - flag_true)

    def describe(key: tuple[str, int]) -> dict[str, Any]:
        row = cleaned[key]
        return {
            "task_id": key[0],
            "seed": key[1],
            "handoff_occurred": row.get("handoff_occurred"),
            "executor_n_calls": row.get("executor_n_calls"),
            "error_type": row.get("error_type"),
            "goal_pass_rate": row.get("goal_pass_rate"),
        }

    return {
        "item": "SHAPE-04",
        "definition_used": "handoff_occurred",
        "reused": [
            "j8_frontier.handoff_flag_keys",
            "j8_frontier.restrict_to_defining_handoff",
        ],
        "defining_arm": defining["label"],
        "handoff_occurred_n": len(flag_true),
        "executor_n_calls_gt0_n": len(ncalls_pos),
        "n_only_handoff_occurred": len(only_flag),
        "n_only_executor_n_calls": len(only_calls),
        "only_handoff_occurred": [describe(k) for k in only_flag],
        "only_executor_n_calls": [describe(k) for k in only_calls],
        "note": (
            "Registered pin uses the harness handoff_occurred flag, the same "
            "keys --handoff-keys-from feeds into j8_frontier non-inferiority "
            "goal_pass_handoff_only. executor.n_calls > 0 is reported beside "
            "it and is not substituted."
        ),
    }


def noise_floor_block(means: dict[int, float]) -> dict[str, Any]:
    q6 = means.get(6)
    q9 = means.get(9)
    rise_pp = None if q6 is None or q9 is None else (q9 - q6) * 100.0
    twice = 2.0 * REPLICATE_FLOOR_PP
    withdrawn = rise_pp is None or rise_pp < twice
    return {
        "replicate_floor_pp": REPLICATE_FLOOR_PP,
        "floor_definition": (
            "observed maximum single-arm |delta| on goal_pass_rate across the "
            "two available replicate pairs (m=2: 3.31 pp, m=4: 1.50 pp) where "
            "the terminal guard never fires. Not a standard error and not a CI."
        ),
        "m6": q6,
        "m9": q9,
        "m6_to_m9_rise_pp": rise_pp,
        "twice_floor_pp": twice,
        "rise_at_least_twice_floor": (
            rise_pp is not None and rise_pp >= twice
        ),
        "shape_claim_withdrawn_by_noise_floor": withdrawn,
        "advice_channel_contrast_pp": ADVICE_CHANNEL_CONTRAST_PP,
        "advice_channel_source": ADVICE_CHANNEL_SOURCE,
        "advice_channel_inside_floor": abs(ADVICE_CHANNEL_CONTRAST_PP)
        <= REPLICATE_FLOOR_PP,
        "rule": (
            "If the observed m6 -> m9 rise is not at least twice the larger "
            "replicate difference, the shape claim is withdrawn regardless of "
            "S1-S3 (prereg §3)."
        ),
    }


def round_public(obj: Any) -> Any:
    if isinstance(obj, float):
        if abs(obj) >= 1.0:
            return round(obj, 6)
        return round(obj, 8)
    if isinstance(obj, dict):
        return {str(k): round_public(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_public(v) for v in obj]
    if isinstance(obj, tuple):
        return [round_public(v) for v in obj]
    return obj


def fit_population(
    name: str,
    panel_gp: dict[int, dict[tuple[str, int], float]],
    panel_tgc: dict[int, dict[tuple[str, int], float]],
    *,
    n_boot: int,
    step_counts: list[int],
) -> dict[str, Any]:
    ms = sorted(panel_gp)
    means = panel_means(panel_gp)
    qs = [means[m] for m in ms]
    boot_scen = bootstrap_segmented(
        panel_gp, cluster="scenario", n_boot=n_boot, seed=SEED
    )
    boot_task = bootstrap_segmented(
        panel_gp, cluster="task", n_boot=n_boot, seed=SEED
    )
    verdict = s1_s2_s3(boot_scen)
    verdict_task = s1_s2_s3(boot_task)
    tgc_means = panel_means(panel_tgc)
    tgc_ms = sorted(tgc_means)
    tgc_qs = [tgc_means[m] for m in tgc_ms]
    tgc_boot = bootstrap_segmented(
        panel_tgc, cluster="scenario", n_boot=n_boot, seed=SEED
    )
    xmap = percentile_map(list(ms) + list(TAU_CANDIDATES), step_counts) if step_counts else None
    pct_boot = None
    if xmap is not None:
        pct_boot = bootstrap_segmented(
            panel_gp,
            cluster="scenario",
            n_boot=n_boot,
            seed=SEED,
            x_of_m=xmap,
        )
    floor = means.get(0)
    iso = isotonic_first_exceed(ms, qs, floor if floor is not None else qs[0])
    return {
        "population": name,
        "analysis_status": "exploratory",
        "n_keys": boot_scen["n_keys"],
        "n_clusters_scenario": boot_scen["n_clusters"],
        "n_clusters_task": boot_task["n_clusters"],
        "curve_goal_pass": [{"m": m, "goal_pass_rate": means[m]} for m in ms],
        "curve_tgc": [{"m": m, "tgc": tgc_means[m]} for m in tgc_ms],
        "primary_cluster": "scenario",
        "scenario": boot_scen,
        "task": boot_task,
        "verdict_scenario_primary": verdict,
        "verdict_task_alongside": verdict_task,
        "noise_floor": noise_floor_block(means),
        "robustness": {
            "label": "descriptive_uncorrected",
            "a_isotonic": iso,
            "b_segmented_on_tgc": {
                "label": "descriptive_uncorrected",
                "fit": tgc_boot,
                "verdict": s1_s2_s3(tgc_boot),
            },
            "d_percentile_remap": {
                "label": "descriptive_uncorrected",
                "mapping": (
                    "p(m) = 100 * #{source planner action counts s_i <= m} / n; "
                    "s_i is n_source_actions from the handoff payload "
                    "(HJ-12 §7.3 quantity). Hinge is (p(m)-p(tau))_+; tau "
                    "candidates remain {4,6,7,8,9}."
                ),
                "p_of_m": xmap,
                "fit": pct_boot,
                "verdict": s1_s2_s3(pct_boot) if pct_boot is not None else None,
                "monotone": (
                    xmap is not None
                    and all(
                        xmap[float(a)] <= xmap[float(b)]
                        for a, b in zip(ms, ms[1:])
                    )
                ),
            },
        },
    }


def prefix_dir(m: int, date: str) -> Path:
    return RESULTS_DIR / f"hj12_prefix_m{m}_{date}"


def load_series(date: str, seeds: list[int]) -> dict[str, Any]:
    arms: dict[str, dict[str, Any]] = {}
    arms["sft_plan"] = load_named_arm("sft_plan", SFT_PLAN_DIR, seeds)
    for m in PREFIX_M:
        label = f"prefix_m{m}"
        arms[label] = load_named_arm(label, prefix_dir(m, date), seeds)
    arms["planner_alone"] = load_named_arm("planner_alone", PLANNER_ALONE_DIR, seeds)
    m_to_arm = {0: arms["sft_plan"]}
    for m in PREFIX_M:
        m_to_arm[m] = arms[f"prefix_m{m}"]
    incomplete = []
    for label, arm in arms.items():
        if label == "planner_alone":
            continue
        n = int(arm.get("n") or 0)
        if n < MIN_ROWS:
            incomplete.append(
                {
                    "label": label,
                    "n": n,
                    "need": MIN_ROWS,
                    "root_missing": arm.get("root_missing"),
                }
            )
    complete_m = {
        m: arm
        for m, arm in m_to_arm.items()
        if int(arm.get("n") or 0) >= MIN_ROWS
    }
    curve_labels = ["sft_plan"] + [f"prefix_m{m}" for m in PREFIX_M if m in complete_m]
    if 0 not in complete_m:
        curve_labels = [lab for lab in curve_labels if lab != "sft_plan"]
    curve_arms = {lab: arms[lab] for lab in curve_labels}
    return {
        "date": date,
        "arms": arms,
        "m_to_arm": complete_m,
        "curve_arms": curve_arms,
        "incomplete": incomplete,
    }


def step_counts_from_series(series: dict[str, Any]) -> tuple[list[int], str]:
    for m in (11, 10, 9, 2):
        arm = series["arms"].get(f"prefix_m{m}")
        if arm is None:
            continue
        vals = [
            int(row["n_source_actions"])
            for row in arm["cleaned"].values()
            if row.get("n_source_actions") is not None
        ]
        if len(vals) >= 50:
            return vals, f"n_source_actions from {arm['label']} handoff payload"
    vals = [
        int(row["steps"])
        for row in series["arms"]["planner_alone"]["cleaned"].values()
        if not row.get("steps_missing")
    ]
    return vals, "planner_alone cleaned.steps fallback"


def arm_snapshot(arm: dict[str, Any], m: int | None) -> dict[str, Any]:
    cleaned_rows = list(arm["cleaned"].values())
    gp = j8.mean_quality(cleaned_rows, "goal_pass_rate", crash_as_zero=True)
    tgc = j8.mean_quality(cleaned_rows, "tgc", crash_as_zero=True)
    return {
        "label": arm["label"],
        "m": m,
        "n": arm.get("n"),
        "complete_n": arm.get("complete_n"),
        "goal_pass_all": gp,
        "tgc_all": tgc,
        "n_handoff_occurred": arm.get("n_handoff_occurred"),
        "n_silenced_executor_n_calls_eq_0": silenced_count(arm),
        "error_types": arm.get("error_types"),
    }


def registered_prediction_row(
    m: int,
    pre: dict[str, Any] | None,
    post: dict[str, Any] | None,
) -> dict[str, Any]:
    pre_gp = None if pre is None else pre.get("goal_pass_all")
    post_gp = None if post is None else post.get("goal_pass_all")
    delta_pp = None
    if pre_gp is not None and post_gp is not None:
        delta_pp = (float(post_gp) - float(pre_gp)) * 100.0
    silenced = None if post is None else post.get("n_silenced_executor_n_calls_eq_0")
    observed_fall = delta_pp is not None and delta_pp < 0.0
    return {
        "m": m,
        "pre_guard_goal_pass": pre_gp,
        "post_guard_goal_pass": post_gp,
        "delta_pp": delta_pp,
        "silenced_post": silenced,
        "replicate_floor_pp": REPLICATE_FLOOR_PP,
        "abs_delta_inside_floor": (
            delta_pp is not None and abs(delta_pp) <= REPLICATE_FLOOR_PP
        ),
        "registered_prediction_verbatim": (
            "the affected arms' scores are expected to fall, most at large m"
        ),
        "observed_fall": observed_fall,
        "prediction_met_at_this_m": observed_fall,
        "note": (
            "Reported per m; not summarised as a single pass/fail across the "
            "curve. At m=2 and m=4 the guard never fires (silenced=0), so a "
            "fall is a replicate movement of the same configuration."
        ),
    }


def build_series_report(
    series: dict[str, Any],
    other: dict[str, Any] | None,
    *,
    n_boot: int,
    role: str,
) -> dict[str, Any]:
    seeds_note = "1,2"
    curve_arms = series["curve_arms"]
    m_to_arm = series["m_to_arm"]
    keys_all = shared_keys(curve_arms)
    keys_surv = survivor_keys(curve_arms, keys_all)
    others_cleaned = [arm["cleaned"] for arm in curve_arms.values()]
    pin10 = pin11 = None
    keys10 = keys11 = set()
    if "prefix_m10" in series["arms"] and series["arms"]["prefix_m10"].get("n", 0) >= MIN_ROWS:
        keys10, n_shared10, n_drop10 = pinned_keys(
            series["arms"]["prefix_m10"], others_cleaned
        )
        pin10 = {
            "handoff_keys_from": "prefix_m10",
            "n_keys": len(keys10),
            "n_shared_before_flag": n_shared10,
            "n_dropped_handoff": n_drop10,
            "reused": "j8_frontier.restrict_to_defining_handoff",
        }
    if "prefix_m11" in series["arms"] and series["arms"]["prefix_m11"].get("n", 0) >= MIN_ROWS:
        keys11, n_shared11, n_drop11 = pinned_keys(
            series["arms"]["prefix_m11"], others_cleaned
        )
        pin11 = {
            "handoff_keys_from": "prefix_m11",
            "n_keys": len(keys11),
            "n_shared_before_flag": n_shared11,
            "n_dropped_handoff": n_drop11,
            "reused": "j8_frontier.restrict_to_defining_handoff",
        }
    steps, steps_src = step_counts_from_series(series)
    pops: dict[str, Any] = {}
    specs = [
        ("all_episodes", keys_all, True, "all-episodes; crash scores 0"),
        ("survivors_robustness_c", keys_surv, False, "HJ-12 §3.4 survivors; robustness (c)"),
    ]
    if pin10 is not None:
        specs.append(
            (
                "handoff_keys_m10",
                keys10,
                True,
                "pinned to prefix_m10 handoff_occurred keys",
            )
        )
    if pin11 is not None:
        specs.append(
            (
                "handoff_keys_m11",
                keys11,
                True,
                "pinned to prefix_m11 handoff_occurred keys",
            )
        )
    for name, keys, crash0, note in specs:
        panel_gp = make_panel(m_to_arm, keys, "goal_pass_rate", crash0)
        panel_tgc = make_panel(m_to_arm, keys, "tgc", crash0)
        block = fit_population(
            name, panel_gp, panel_tgc, n_boot=n_boot, step_counts=steps
        )
        block["note"] = note
        block["n_keys_requested"] = len(keys)
        pops[name] = block

    snapshots = {
        "sft_plan": arm_snapshot(series["arms"]["sft_plan"], 0),
        **{
            f"prefix_m{m}": arm_snapshot(series["arms"][f"prefix_m{m}"], m)
            for m in PREFIX_M
            if f"prefix_m{m}" in series["arms"]
        },
        "planner_alone": arm_snapshot(series["arms"]["planner_alone"], None),
    }
    other_snaps = {}
    if other is not None:
        other_snaps = {
            **{
                f"prefix_m{m}": arm_snapshot(other["arms"][f"prefix_m{m}"], m)
                for m in PREFIX_M
                if f"prefix_m{m}" in other["arms"]
            }
        }
    per_m = []
    for m in PREFIX_M:
        pre_s = (
            other_snaps.get(f"prefix_m{m}")
            if role == "post_guard"
            else snapshots.get(f"prefix_m{m}")
        )
        post_s = (
            snapshots.get(f"prefix_m{m}")
            if role == "post_guard"
            else other_snaps.get(f"prefix_m{m}")
        )
        if role == "pre_guard":
            pre_s = snapshots.get(f"prefix_m{m}")
            post_s = other_snaps.get(f"prefix_m{m}")
        per_m.append(registered_prediction_row(m, pre_s, post_s))

    m11_post = snapshots["prefix_m11"]["goal_pass_all"] if "prefix_m11" in snapshots else None
    planner_gp = snapshots["planner_alone"]["goal_pass_all"]
    m11_minus_planner = None
    if m11_post is not None and planner_gp is not None:
        m11_minus_planner = (float(m11_post) - float(planner_gp)) * 100.0
    m9_row = next((r for r in per_m if r["m"] == 9), None)
    m11_row = next((r for r in per_m if r["m"] == 11), None)
    m11_lost_more_than_m9 = None
    if (
        m9_row
        and m11_row
        and m9_row.get("delta_pp") is not None
        and m11_row.get("delta_pp") is not None
    ):
        # "lose more" = more negative delta
        m11_lost_more_than_m9 = float(m11_row["delta_pp"]) < float(m9_row["delta_pp"])

    shape04 = {}
    if "prefix_m10" in series["arms"]:
        shape04["m10"] = shape04_reconciliation(series["arms"]["prefix_m10"])
    if "prefix_m11" in series["arms"]:
        shape04["m11"] = shape04_reconciliation(series["arms"]["prefix_m11"])

    primary_pop = "all_episodes"
    primary_verdict = pops[primary_pop]["verdict_scenario_primary"]
    return {
        "analysis_status": "exploratory",
        "analysis_status_note": (
            "Shape test on existing hj12_prefix arms is exploratory "
            "(docs/prereg_hj13_shape_20260923.md §1.1). Confirmatory rows are "
            "not opened."
        ),
        "registered_spec": "docs/prereg_hj13_shape_20260923.md §3 plus amendment 2026-09-22 17:25",
        "series": role,
        "date": series["date"],
        "primary_series_is_post_guard": role == "post_guard",
        "seeds": seeds_note,
        "m_grid": list(M_GRID),
        "tau_candidates": list(TAU_CANDIDATES),
        "bootstrap": n_boot,
        "seed": SEED,
        "primary_cluster": "scenario",
        "reused_from_j8_frontier": REUSED_FROM_J8,
        "incomplete_arms": series["incomplete"],
        "arms": snapshots,
        "step_counts": {
            "n": len(steps),
            "min": min(steps) if steps else None,
            "median": statistics.median(steps) if steps else None,
            "max": max(steps) if steps else None,
            "source": steps_src,
        },
        "handoff_pin_m10": pin10,
        "handoff_pin_m11": pin11,
        "shape04_reconciliation": shape04,
        "populations": pops,
        "primary_population": primary_pop,
        "primary_verdict": primary_verdict,
        "per_m_pre_post_delta": per_m,
        "registered_prediction_m11_minus_planner_alone_pp": m11_minus_planner,
        "registered_prediction_m11_minus_planner_alone_positive": (
            None if m11_minus_planner is None else m11_minus_planner > 0.0
        ),
        "registered_prediction_m11_lost_more_than_m9": m11_lost_more_than_m9,
        "registered_prediction_verbatim": (
            "the affected arms' scores are expected to fall, most at large m. "
            "Specifically we predict prefix_m11 will lose more than prefix_m9, "
            "and that prefix_m11 − planner_alone will no longer be positive."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-pre", type=Path, default=DEFAULT_OUT_PRE)
    p.add_argument("--out-post", type=Path, default=DEFAULT_OUT_POST)
    p.add_argument("--n-boot", type=int, default=BOOTSTRAP)
    p.add_argument("--seeds", default="1,2")
    return p.parse_args(argv)


def write_report(path: Path, report: dict[str, Any]) -> None:
    refuse_heldout(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(round_public(report), indent=2, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"Wrote report to {path} ({path.stat().st_size} bytes)")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seeds = j8.parse_seeds(args.seeds)
    print(
        f"Loading pre-guard 20260922 and post-guard 20260923 series "
        f"(n_boot={args.n_boot}, seeds={seeds})",
        flush=True,
    )
    pre = load_series("20260922", seeds)
    post = load_series("20260923", seeds)
    pre_report = build_series_report(
        pre, post, n_boot=args.n_boot, role="pre_guard"
    )
    post_report = build_series_report(
        post, pre, n_boot=args.n_boot, role="post_guard"
    )
    write_report(args.out_pre, pre_report)
    write_report(args.out_post, post_report)
    for role, report in ("pre_guard", pre_report), ("post_guard", post_report):
        v = report["primary_verdict"]
        print(
            f"{role} all_episodes: tau={v['S3_threshold_is_real']['tau']} "
            f"ci={v['S3_threshold_is_real']['tau_ci95']} "
            f"verdict={v['verdict']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
