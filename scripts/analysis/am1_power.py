#!/usr/bin/env python3
"""Power of the J10 predictions at the test design, from dev data only (A1 Amendment 1, §C).

Why this exists: the adversarial review (docs/review_paperA_adversarial_20260923.md) proposes a
content family CF1-CF3 on J10 arms 9-12, registered before any test_normal episode. A prediction
registered without its power invites the reading "it was bound to fail"; this script supplies it.

Method. Dev scenarios are resampled with replacement up to the test design (56 scenarios; each
brings its dev tasks; two seeds per task, drawn without replacement from the seeds dev has). The
same scenario draw and seed choice are applied to every contrast in a simulated read, because the
arms share episodes. Each simulated read is analysed as A1 registers it: a scenario-clustered
percentile bootstrap interval, and Holm within a family through the bootstrap p-value
(j10_report.bootstrap_pvalue's definition). Power is reported at the dev effect and at half of it
(every difference shifted by half the dev mean, spread kept): an effect chosen for registration
after being seen on dev is an optimistic guess of the test effect.

The dev values themselves are recomputed with j10_report.a1_contrast (10,000 draws, seed 20260924)
so that they can be checked against the values A1 and the ledger quote before any power number is
trusted.

Dev only: every path is refused if it names a held-out split (j16_robustness.refuse_heldout).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import numpy as np  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.analysis.j10_report import a1_contrast, holm_adjust  # noqa: E402
from scripts.setup.hj1_gate import scenario_of  # noqa: E402

RESULTS = Path("/scratch/n12194778/sidekick/results")
ALPHA = 0.05
TEST_SCENARIOS = 56
TEST_SEEDS_PER_TASK = 2
DEFAULT_R = 1000
DEFAULT_B = 2000
DEFAULT_SEED = 20260924

# Dev campaigns per J10 arm. Pooled arms list every campaign; seeds come from result.json.
ARMS: dict[str, list[str]] = {
    "takeover_k10": ["hj12_takeover_fixed_k_10_20260923", "b1_takeover_fixed_k_10_s3_20260923"],
    "advise_k10_fullctx": ["hj12_advise_fixed_k_10_fullctx_20260923",
                           "b1_advise_fixed_k_10_fullctx_s3_20260923"],
    "show_k10": ["b2_show_fixed_k_10_20260923", "b2_show_fixed_k_10_s3_20260923"],
    "advise_k10_neutral": ["b2_advise_neutral_fixed_k_10_fullctx_20260923",
                           "b2_advise_neutral_fixed_k_10_fullctx_s3_20260923"],
    "advise_k1_fullctx": ["hj13_advise_fixed_k_1_fullctx_20260923"],
    "prefix_m11": ["hj17_prefix_c81_bplus_m11_20260923", "hj18_prefix_c81s3_bplus_m11_20260924"],
    "planner_alone_cap81": ["hj13_planner_alone_cap81_20260923",
                            "hj13_planner_alone_cap81_seed3_20260924"],
    "prefix_zs_m11": ["hj17_prefix_c81_zs_m11_20260923", "hj18_prefix_c81s3_zs_m11_20260924"],
    "prefix_zs_m9": ["hj17_prefix_c81_zs_m9_20260923", "hj18_prefix_c81s3_zs_m9_20260924"],
}

# name: (left, right, direction, threshold, family, handoff_only)
CONTRASTS: dict[str, dict[str, Any]] = {
    "P1": dict(left="advise_k1_fullctx", right="prefix_m11", direction="less", threshold=0.0,
               family="A1"),
    "P3": dict(left="prefix_m11", right="planner_alone_cap81", direction="greater",
               threshold=-0.07, family="A1"),
    "P4": dict(left="prefix_zs_m11", right="prefix_zs_m9", direction="greater", threshold=0.0,
               family="A1"),
    "P6": dict(left="takeover_k10", right="advise_k10_fullctx", direction="greater",
               threshold=0.0, family="A1"),
    "CF1": dict(left="advise_k10_neutral", right="advise_k10_fullctx", direction="greater",
                threshold=0.0, family="CF"),
    # CF2 and CF3 are pre-specified secondaries, outside any Holm family. A first run with all
    # three in one Holm family (m = 3) gave CF1 a Holm power of 0.58 against 0.72 alone, and
    # CF2/CF3 at most 0.29, so Amendment 1 registers CF1 as the family's only decision-bearing
    # member (disclosed in Amendment 1 §C).
    "CF2": dict(left="show_k10", right="advise_k10_fullctx", direction="greater", threshold=0.0,
                family=None),
    "CF3": dict(left="takeover_k10", right="advise_k10_neutral", direction="two-sided",
                threshold=0.0, family=None),
    "P3_handoff_only": dict(left="prefix_m11", right="planner_alone_cap81", direction="greater",
                            threshold=-0.07, family=None, handoff_only=True),
}


# ---- loading (dev only) ------------------------------------------------------------------
def load_arm(campaigns: list[str], root: Path = RESULTS) -> dict[tuple[str, int], dict[str, Any]]:
    """Pooled scored episodes of one arm; crashes excluded as A1 excludes them."""
    pooled: dict[tuple[str, int], dict[str, Any]] = {}
    for name in campaigns:
        rows, _diag = j16.load_campaign_dir(root / name, allowed_seeds=(1, 2, 3))
        for key, row in rows.items():
            if key in pooled:
                raise ValueError(f"episode {key} appears in two campaigns of one arm ({name})")
            if row.get("error_type") == "crash":
                continue
            gp = row.get("goal_pass_rate")
            pooled[key] = {
                "goal_pass_rate": None if gp is None else float(gp),
                "tgc": None if row.get("tgc") is None else float(row["tgc"]),
                "handoff_occurred": row["_facts"].get("handoff_occurred"),
            }
    return pooled


def paired_rows(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    field: str = "goal_pass_rate",
) -> list[dict[str, Any]]:
    """(task, seed, scenario, d, h) for shared keys; h is the left (target) arm's handoff flag."""
    out = []
    for key in sorted(set(left) & set(right)):
        a, b = left[key].get(field), right[key].get(field)
        if a is None or b is None:
            continue
        h = left[key].get("handoff_occurred")
        out.append({"task": key[0], "seed": key[1], "scenario": scenario_of(key[0]),
                    "d": float(a) - float(b), "h": 1.0 if h else 0.0})
    return out


# ---- simulation (pure) --------------------------------------------------------------------
def index_by_scenario(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[int, tuple[float, float]]]]:
    """scenario -> task -> seed -> (d, h)."""
    out: dict[str, dict[str, dict[int, tuple[float, float]]]] = {}
    for r in rows:
        out.setdefault(r["scenario"], {}).setdefault(r["task"], {})[int(r["seed"])] = (r["d"], r["h"])
    return out


def draw_design(
    scenarios: list[str],
    tasks_by_scenario: dict[str, list[str]],
    rng: np.random.Generator,
    n_scenarios: int = TEST_SCENARIOS,
    seeds_available: tuple[int, ...] = (1, 2, 3),
    seeds_per_task: int = TEST_SEEDS_PER_TASK,
) -> list[list[tuple[str, tuple[int, ...]]]]:
    """One simulated read: n_scenarios draws; each is a list of (task, seeds chosen)."""
    design = []
    for i in rng.integers(0, len(scenarios), size=n_scenarios):
        scen = scenarios[int(i)]
        cluster = []
        for task in tasks_by_scenario[scen]:
            chosen = rng.choice(np.array(seeds_available), size=seeds_per_task, replace=False)
            cluster.append((task, tuple(sorted(int(s) for s in chosen))))
        design.append(cluster)
    return design


def cluster_sums(
    index: dict[str, dict[str, dict[int, tuple[float, float]]]],
    design: list[list[tuple[str, tuple[int, ...]]]],
    shift: float,
    handoff_only: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Per drawn cluster: numerator and denominator of the arm-level mean.

    Plain contrast: sum of (d - shift) and the pair count. Handoff-only: sum of (d - shift)*h and
    the sum of h (the Σd·h/Σh estimand of j10_report.a1_handoff_depth). A task whose drawn seeds
    are absent from this contrast (e.g. an arm run on seeds 1-2 only) falls back to the seeds it
    has, so a two-seed contrast keeps its full two seeds.
    """
    num = np.zeros(len(design))
    den = np.zeros(len(design))
    task_scen = {t: s for s, tasks in index.items() for t in tasks}
    for c, cluster in enumerate(design):
        for task, seeds in cluster:
            by_seed = index.get(task_scen.get(task, ""), {}).get(task)
            if not by_seed:
                continue
            use = [s for s in seeds if s in by_seed]
            if len(use) < len(seeds):
                use = sorted(by_seed)[: len(seeds)]
            for s in use:
                d, h = by_seed[s]
                if handoff_only:
                    num[c] += (d - shift) * h
                    den[c] += h
                else:
                    num[c] += d - shift
                    den[c] += 1.0
    return num, den


def bootstrap_means(num: np.ndarray, den: np.ndarray, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """Sorted cluster-bootstrap means of Σnum/Σden (clusters drawn with replacement)."""
    g = len(num)
    idx = rng.integers(0, g, size=(n_boot, g))
    d = den[idx].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        means = np.where(d > 0, num[idx].sum(axis=1) / np.where(d > 0, d, 1.0), np.nan)
    means = means[~np.isnan(means)]
    means.sort()
    return means


def percentile_ci(means: np.ndarray) -> tuple[float, float]:
    """Same order statistics as j10_report.percentile_ci."""
    n = len(means)
    return float(means[int(0.025 * n)]), float(means[int(0.975 * n)])


def pvalue(means: np.ndarray, threshold: float, direction: str) -> float:
    """j10_report.bootstrap_pvalue on a sorted numpy array."""
    n = len(means)
    share_le = np.searchsorted(means, threshold, side="right") / n
    share_ge = (n - np.searchsorted(means, threshold, side="left")) / n
    if direction == "greater":
        p = 2.0 * share_le
    elif direction == "less":
        p = 2.0 * share_ge
    elif direction == "two-sided":
        p = 2.0 * min(share_le, share_ge)
    else:
        raise ValueError(f"unknown direction {direction!r}")
    return float(min(1.0, p))


def interval_decision(lo: float, hi: float, threshold: float, direction: str) -> dict[str, bool]:
    return {
        "excludes_on_predicted_side": (lo > threshold) if direction == "greater"
        else (hi < threshold) if direction == "less" else (lo > threshold or hi < threshold),
        "lower_above": lo > threshold,
        "upper_below": hi < threshold,
    }


def simulate(
    indices: dict[str, dict[str, dict[str, dict[int, tuple[float, float]]]]],
    specs: dict[str, dict[str, Any]],
    shifts: dict[str, float],
    *,
    n_sims: int,
    n_boot: int,
    seed: int,
    n_scenarios: int = TEST_SCENARIOS,
) -> dict[str, Any]:
    """Joint simulated reads. Returns per-contrast rates and per-family Holm rates."""
    scenarios = sorted({s for idx in indices.values() for s in idx})
    tasks_by_scenario: dict[str, list[str]] = {}
    for idx in indices.values():
        for scen, tasks in idx.items():
            tasks_by_scenario.setdefault(scen, [])
            for t in tasks:
                if t not in tasks_by_scenario[scen]:
                    tasks_by_scenario[scen].append(t)
    for scen in tasks_by_scenario:
        tasks_by_scenario[scen].sort()
    rng = np.random.default_rng(seed)
    counts = {name: {"excludes_on_predicted_side": 0, "lower_above": 0, "upper_below": 0,
                     "holm_supported": 0} for name in specs}
    families = sorted({s["family"] for s in specs.values() if s.get("family")})
    fam_all = {f: 0 for f in families}
    cf_readings: dict[str, int] = {}
    for _ in range(n_sims):
        design = draw_design(scenarios, tasks_by_scenario, rng, n_scenarios=n_scenarios)
        pvals: dict[str, float] = {}
        verdicts: dict[str, dict[str, bool]] = {}
        for name, spec in specs.items():
            num, den = cluster_sums(indices[name], design, shifts[name], bool(spec.get("handoff_only")))
            means = bootstrap_means(num, den, n_boot, rng)
            lo, hi = percentile_ci(means)
            v = interval_decision(lo, hi, spec["threshold"], spec["direction"])
            verdicts[name] = v
            for k in ("excludes_on_predicted_side", "lower_above", "upper_below"):
                counts[name][k] += int(v[k])
            pvals[name] = pvalue(means, spec["threshold"], spec["direction"])
        for fam in families:
            members = [n for n, s in specs.items() if s.get("family") == fam]
            adj = holm_adjust([pvals[n] for n in members])
            ok_all = True
            for n, p in zip(members, adj):
                supported = p <= ALPHA and verdicts[n]["excludes_on_predicted_side"]
                counts[n]["holm_supported"] += int(supported)
                ok_all = ok_all and supported
            fam_all[fam] += int(ok_all)
        if {"CF1", "CF3"} <= set(specs):
            cf1 = verdicts["CF1"]["lower_above"]
            reading = ("CF1 not supported" if not cf1
                       else "CF1 supported, CF3 > 0" if verdicts["CF3"]["lower_above"]
                       else "CF1 supported, CF3 < 0" if verdicts["CF3"]["upper_below"]
                       else "CF1 supported, CF3 includes 0")
            cf_readings[reading] = cf_readings.get(reading, 0) + 1
    rates = {n: {k: round(v / n_sims, 4) for k, v in c.items()} for n, c in counts.items()}
    return {
        "per_contrast": rates,
        "families_all_supported": {f: round(v / n_sims, 4) for f, v in fam_all.items()},
        "cf_readings": {k: round(v / n_sims, 4) for k, v in sorted(cf_readings.items())},
    }


# ---- dev values ----------------------------------------------------------------------------
def handoff_ratio(rows: list[dict[str, Any]]) -> Optional[float]:
    den = sum(r["h"] for r in rows)
    return None if den == 0 else sum(r["d"] * r["h"] for r in rows) / den


def dev_block(name: str, spec: dict[str, Any], arms: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if spec.get("handoff_only"):
        num = np.array([r["d"] * r["h"] for r in rows])
        den = np.array([r["h"] for r in rows])
        clusters = sorted({r["scenario"] for r in rows})
        cnum = np.array([num[[r["scenario"] == c for r in rows]].sum() for c in clusters])
        cden = np.array([den[[r["scenario"] == c for r in rows]].sum() for c in clusters])
        means = bootstrap_means(cnum, cden, 10_000, np.random.default_rng(DEFAULT_SEED))
        lo, hi = percentile_ci(means)
        point = handoff_ratio(rows)
        return {"n_pairs": len(rows), "n_handoff": int(den.sum()),
                "diff_pp": round(point * 100, 2), "ci95_pp_scenario": [round(lo * 100, 2), round(hi * 100, 2)],
                "note": "ratio estimator Σd·h/Σh, numpy scenario bootstrap (10k, seed 20260924)"}
    cmp = a1_contrast(arms[spec["left"]], arms[spec["right"]], "goal_pass_rate")
    return {"n_pairs": cmp["n_pairs"], "diff_pp": cmp["scenario"]["diff_pp"],
            "ci95_pp_scenario": cmp["scenario"]["ci95_pp"], "ci95_pp_task": cmp["task"]["ci95_pp"]}


def build(root: Path, n_sims: int, n_boot: int, seed: int) -> dict[str, Any]:
    j16.refuse_heldout(root)
    arms = {label: load_arm(camps, root) for label, camps in ARMS.items()}
    rows = {name: paired_rows(arms[s["left"]], arms[s["right"]]) for name, s in CONTRASTS.items()}
    indices = {name: index_by_scenario(r) for name, r in rows.items()}
    dev = {name: dev_block(name, CONTRASTS[name], arms, rows[name]) for name in CONTRASTS}
    full_shift = {name: 0.0 for name in CONTRASTS}
    half_shift = {}
    for name, spec in CONTRASTS.items():
        point = handoff_ratio(rows[name]) if spec.get("handoff_only") else statistics.fmean(r["d"] for r in rows[name])
        # Half the effect relative to the null the prediction is judged against.
        half_shift[name] = (point - spec["threshold"]) / 2.0 if spec["direction"] != "two-sided" else point / 2.0
    at_dev = simulate(indices, CONTRASTS, full_shift, n_sims=n_sims, n_boot=n_boot, seed=seed)
    at_half = simulate(indices, CONTRASTS, half_shift, n_sims=n_sims, n_boot=n_boot, seed=seed + 1)
    return {
        "generated_by": "scripts/analysis/am1_power.py",
        "split": "dev",
        "purpose": "power of A1 P1/P3/P4/P6 and the proposed Amendment 1 content family at the test design",
        "design": {"n_scenarios": TEST_SCENARIOS, "tasks_per_scenario": "as on dev (3)",
                   "seeds_per_task": TEST_SEEDS_PER_TASK, "dev_seeds_available": [1, 2, 3]},
        "n_sims": n_sims, "n_boot_per_sim": n_boot, "seed": seed, "alpha": ALPHA,
        "arms": ARMS,
        "contrasts": {name: {k: v for k, v in spec.items()} for name, spec in CONTRASTS.items()},
        "dev": dev,
        "power_at_dev_effect": at_dev,
        "power_at_half_effect": at_half,
        "half_effect_shift_pp": {k: round(v * 100, 3) for k, v in half_shift.items()},
        "caveats": [
            "Resampling dev scenarios treats the dev effect as the truth; the half-effect rows are the guard against that optimism.",
            "B per simulated read is below the registered 10,000; interval endpoints carry Monte Carlo error of a few tenths of a pp.",
            "P1 uses dev seeds 1-2 only (its advice arm was not run at seed 3).",
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=RESULTS)
    ap.add_argument("--sims", type=int, default=DEFAULT_R)
    ap.add_argument("--boot", type=int, default=DEFAULT_B)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    j16.refuse_heldout(args.out)
    report = build(args.root, args.sims, args.boot, args.seed)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dev": report["dev"], "at_dev": report["power_at_dev_effect"],
                      "at_half": report["power_at_half_effect"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
