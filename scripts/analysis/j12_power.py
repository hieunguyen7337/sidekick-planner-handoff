#!/usr/bin/env python3
"""Power of J12's registered analysis (D1-D4, one Holm family of m = 4) at the test design, from dev only.

Why this exists: J12 (docs/prereg_j12_depth_test_20260924.md §5) registers its power before any
test_normal episode, so that a prediction that fails cannot be read as "it was bound to fail".

Method, modelled on scripts/analysis/am1_power.py, whose resampling and simulation pieces are imported
(index_by_scenario, draw_design, cluster_sums, bootstrap_means, percentile_ci, pvalue,
interval_decision, paired_rows, handoff_ratio, dev_block; holm_adjust is j10_report's). Dev scenarios
are resampled with replacement to 56 scenarios, two seeds per task drawn from dev's 1-3, the same draw
applied to all four contrasts of a read. Each read is analysed as J12 §3 registers it: the scenario
cluster percentile interval, the bootstrap p in the "greater" direction at 0, Holm across D1-D4, and
"supported" = Holm-adjusted p <= 0.05 and the interval's lower bound above 0. The handoff-only reads
(D3, D4) use Σ d·h / Σ h. Power is reported at the dev effect and at half of it (am1_power's shift:
every difference moved by half the dev point, spread kept).

am1_power.simulate returns per-contrast and per-family rates only, and J12 also registers the joint
"D1 and D2 both supported". j12_simulate therefore repeats simulate's loop draw for draw -- the same
RNG calls in the same order, so its rates equal simulate's (tests/unit/test_j12_power.py) -- and
counts that joint event as well.

Dev input: the pooled cap-81 prefix family, seeds 1-3 (hj17 + hj18), loaded exactly as
j17_depth_fixes loads it (family_sources / load_depth_rows / drop_crashed, imported). Pairs are
A1's population: crash dropped, every other outcome scored, keyed (task_id, seed); d = m11 − m6 and
h = the m11 episode's handoff_occurred (j17_depth_fixes.paired_components' estimand). The dev point
values are checked against j17's report before any power number is trusted.

Dev only: every path is refused if it names a held-out split or a J10 campaign.
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

from scripts.analysis import am1_power as am1  # noqa: E402
from scripts.analysis import j12_report  # noqa: E402
from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.analysis.j10_report import A1_RULES, holm_adjust  # noqa: E402

RESULTS = Path("/scratch/n12194778/sidekick/results")
ALPHA = j12_report.j10.A1_ALPHA
DEFAULT_R = am1.DEFAULT_R  # 1,000 simulated reads
DEFAULT_B = am1.DEFAULT_B  # 2,000 bootstrap draws per read
DEFAULT_SEED = am1.DEFAULT_SEED  # 20260924
DEV_REPORT = REPO_ROOT / j12_report.J12_DEV_REPORT
# j12_report arm label -> j17_depth_fixes.family_sources label (pooled cap-81 dev campaigns).
DEV_LABEL = {"prefix_m6": "bplus_m6", "prefix_m11": "bplus_m11",
             "prefix_zs_m6": "zs_m6", "prefix_zs_m11": "zs_m11"}
FAMILY = "J12"
JOINT = ("D1", "D2")  # J12 §5: "D1 and D2 both supported"


def power_specs() -> dict[str, dict[str, Any]]:
    """J12's registered D1-D4 in am1_power's spec shape, read from j12_report's registry."""
    specs = {}
    for p in j12_report.J12_PREDICTIONS:
        specs[p["id"]] = dict(
            left=DEV_LABEL[p["left"]], right=DEV_LABEL[p["right"]],
            direction=A1_RULES[p["rule"]]["direction"], threshold=float(p["threshold_pp"]) / 100.0,
            family=FAMILY if p["holm_family"] else None, handoff_only=p["kind"] == "handoff_only")
    return specs


# ---- dev input -------------------------------------------------------------------------------------
def load_dev(root: Path = RESULTS) -> tuple[dict[str, dict], dict[str, Any]]:
    """The four pooled dev arms in am1_power's row shape, crashes dropped, with their inputs."""
    from scripts.analysis import j17_depth_fixes as j17  # dev paths; j17 refuses held-out and J10 ones

    j17.refuse_path(root)
    sources = j17.family_sources(root)
    arms: dict[str, dict] = {}
    inputs: dict[str, Any] = {}
    for label in sorted(set(DEV_LABEL.values())):
        rows, entries = j17.load_depth_rows(sources[label])
        kept = j17.drop_crashed(rows)
        arms[label] = {
            key: {"goal_pass_rate": None if row.get("goal_pass_rate") is None else float(row["goal_pass_rate"]),
                  "tgc": None if row.get("tgc") is None else float(row["tgc"]),
                  "handoff_occurred": j16.handoff_flag(row)}
            for key, row in kept.items()}
        inputs[label] = {"campaign_dirs": [e["campaign_dir"] for e in entries],
                         "seeds": sorted({s for e in entries for s in e["seeds"]}),
                         "n_episodes": sum(e["n_episodes"] for e in entries),
                         "n_crash_excluded": sum(e["n_crash"] for e in entries),
                         "n_scored": len(kept)}
    return arms, inputs


# ---- simulation ------------------------------------------------------------------------------------
def j12_simulate(
    indices: dict[str, dict[str, dict[str, dict[int, tuple[float, float]]]]],
    specs: dict[str, dict[str, Any]],
    shifts: dict[str, float],
    *,
    n_sims: int,
    n_boot: int,
    seed: int,
    n_scenarios: int = am1.TEST_SCENARIOS,
    joint: tuple[str, ...] = JOINT,
) -> dict[str, Any]:
    """am1_power.simulate's loop, draw for draw, plus the joint rate of `joint` all Holm-supported."""
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
    joint_all = 0
    for _ in range(n_sims):
        design = am1.draw_design(scenarios, tasks_by_scenario, rng, n_scenarios=n_scenarios)
        pvals: dict[str, float] = {}
        verdicts: dict[str, dict[str, bool]] = {}
        for name, spec in specs.items():
            num, den = am1.cluster_sums(indices[name], design, shifts[name], bool(spec.get("handoff_only")))
            means = am1.bootstrap_means(num, den, n_boot, rng)
            lo, hi = am1.percentile_ci(means)
            v = am1.interval_decision(lo, hi, spec["threshold"], spec["direction"])
            verdicts[name] = v
            for k in ("excludes_on_predicted_side", "lower_above", "upper_below"):
                counts[name][k] += int(v[k])
            pvals[name] = am1.pvalue(means, spec["threshold"], spec["direction"])
        supported: dict[str, bool] = {}
        for fam in families:
            members = [n for n, s in specs.items() if s.get("family") == fam]
            adj = holm_adjust([pvals[n] for n in members])
            ok_all = True
            for n, p in zip(members, adj):
                supported[n] = p <= ALPHA and verdicts[n]["excludes_on_predicted_side"]
                counts[n]["holm_supported"] += int(supported[n])
                ok_all = ok_all and supported[n]
            fam_all[fam] += int(ok_all)
        joint_all += int(all(supported.get(n, False) for n in joint))
    rates = {n: {k: round(v / n_sims, 4) for k, v in c.items()} for n, c in counts.items()}
    return {
        "per_contrast": rates,
        "families_all_supported": {f: round(v / n_sims, 4) for f, v in fam_all.items()},
        "joint_supported": {" and ".join(joint): round(joint_all / n_sims, 4)},
    }


def half_shifts(rows: dict[str, list[dict[str, Any]]], specs: dict[str, dict[str, Any]]) -> dict[str, float]:
    """am1_power.build's half-effect shift (am1_power.py:337-340): half the effect relative to the
    null the prediction is judged against."""
    out = {}
    for name, spec in specs.items():
        point = am1.handoff_ratio(rows[name]) if spec.get("handoff_only") else statistics.fmean(r["d"] for r in rows[name])
        out[name] = (point - spec["threshold"]) / 2.0 if spec["direction"] != "two-sided" else point / 2.0
    return out


def j17_check(dev: dict[str, Any], report_path: Path = DEV_REPORT) -> dict[str, Any]:
    """The dev points this script saw against j17_depth_fixes' report, per D (2 dp)."""
    if not report_path.is_file():
        return {"status": "absent", "path": str(report_path)}
    data = json.loads(report_path.read_text(encoding="utf-8"))
    rows = {}
    for p in j12_report.J12_PREDICTIONS:
        node: Any = data
        for part in p["dev_reference"]["key"].split("."):
            node = node[part]
        rows[p["id"]] = {"key": p["dev_reference"]["key"], "j17_diff_pp": round(node["diff_pp"], 2),
                         "j17_n_pairs": node["n_pairs"], "seen_diff_pp": dev[p["id"]]["diff_pp"],
                         "matches": round(node["diff_pp"], 2) == dev[p["id"]]["diff_pp"]}
    return {"status": "ok", "path": str(report_path.relative_to(REPO_ROOT)) if report_path.is_relative_to(REPO_ROOT)
            else str(report_path), "rows": rows, "all_match": all(r["matches"] for r in rows.values())}


def build_from_arms(
    arms: dict[str, dict],
    *,
    n_sims: int,
    n_boot: int,
    seed: int,
    inputs: Optional[dict[str, Any]] = None,
    n_scenarios: int = am1.TEST_SCENARIOS,
    report_path: Path = DEV_REPORT,
) -> dict[str, Any]:
    specs = power_specs()
    rows = {name: am1.paired_rows(arms[s["left"]], arms[s["right"]]) for name, s in specs.items()}
    indices = {name: am1.index_by_scenario(r) for name, r in rows.items()}
    dev = {}
    for name, spec in specs.items():
        blk = am1.dev_block(name, spec, arms, rows[name])
        blk["n_handoff"] = int(sum(r["h"] for r in rows[name]))
        blk["n_scenarios"] = len({r["scenario"] for r in rows[name]})
        dev[name] = blk
    zero = {name: 0.0 for name in specs}
    half = half_shifts(rows, specs)
    at_dev = j12_simulate(indices, specs, zero, n_sims=n_sims, n_boot=n_boot, seed=seed, n_scenarios=n_scenarios)
    at_half = j12_simulate(indices, specs, half, n_sims=n_sims, n_boot=n_boot, seed=seed + 1, n_scenarios=n_scenarios)

    def table(res: dict[str, Any]) -> dict[str, Any]:
        return {**{n: res["per_contrast"][n]["holm_supported"] for n in specs},
                "all_four_supported": res["families_all_supported"][FAMILY],
                "D1_and_D2_supported": res["joint_supported"]["D1 and D2"]}

    return {
        "generated_by": "scripts/analysis/j12_power.py",
        "split": "dev",
        "prereg": j12_report.J12_PREREG,
        "purpose": "power of J12's D1-D4 (one Holm family of m = 4) at the test design, from the dev depth family",
        "design": {"n_scenarios": n_scenarios, "tasks_per_scenario": "as on dev (3)",
                   "seeds_per_task": am1.TEST_SEEDS_PER_TASK, "dev_seeds_available": [1, 2, 3]},
        "analysis": {"interval": "scenario-cluster percentile, 95%", "p": "bootstrap, 'greater' at 0",
                     "multiplicity": "Holm across D1-D4", "alpha": ALPHA,
                     "supported": "Holm-adjusted p <= alpha and CI lower bound > 0",
                     "handoff_only": "Σ d·h / Σ h, h from the m11 arm"},
        "n_sims": n_sims, "n_boot_per_sim": n_boot, "seed": seed, "seed_half_effect": seed + 1,
        "specs": specs,
        "dev": dev,
        "dev_check_against_j17": j17_check(dev, report_path),
        "power_table": {"at_dev_effect": table(at_dev), "at_half_effect": table(at_half),
                        "value": "rate of Holm-supported per D; the family; D1 and D2 jointly"},
        "power_at_dev_effect": at_dev,
        "power_at_half_effect": at_half,
        "half_effect_shift_pp": {k: round(v * 100, 3) for k, v in half.items()},
        "inputs": inputs,
        "caveats": [
            "Resampling dev scenarios treats the dev effect as the truth; the half-effect rows are the guard against that optimism.",
            "B per simulated read is 2,000, below the registered 10,000; interval endpoints carry Monte Carlo error of a few tenths of a pp.",
            "Dev pairs pool seeds 1-3 (hj17 seeds 1-2 + hj18 seed 3); the test design draws two of them per task.",
        ],
    }


def build(root: Path, n_sims: int, n_boot: int, seed: int) -> dict[str, Any]:
    arms, inputs = load_dev(root)
    return build_from_arms(arms, n_sims=n_sims, n_boot=n_boot, seed=seed, inputs=inputs)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=RESULTS)
    ap.add_argument("--sims", type=int, default=DEFAULT_R)
    ap.add_argument("--boot", type=int, default=DEFAULT_B)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    j16.refuse_heldout(args.out)
    j16.refuse_heldout(args.root)
    report = build(args.root, args.sims, args.boot, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dev": report["dev"], "dev_check_against_j17": report["dev_check_against_j17"],
                      "power_table": report["power_table"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
