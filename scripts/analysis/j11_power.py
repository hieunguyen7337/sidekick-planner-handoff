#!/usr/bin/env python3
"""Power of the J11 registration at the test design, from LP-2 dev pairs only (J11 prereg §5).

Why this exists: J11 re-runs LP's registered family (the informativeness gate, L1-L5 with Holm) for
the LP-2 planner P27 on test_normal. A prediction registered without its power invites the reading
"it was bound to fail"; this script supplies it before the prereg freezes.

Method (scripts/analysis/am1_power.py's, whose pure functions are imported). LP-2 dev scenarios are
resampled with replacement up to the test design, 56 scenarios; each brings its dev tasks, at seeds
1 and 2 (the only seeds LP-2 ran). The same scenario draw applies to every contrast in a simulated
read, because the arms share episodes. Each read is analysed as J11 registers it:
  - the gate: the point estimate of C - E > 0;
  - L1-L5: a scenario-clustered percentile interval (B draws), the bootstrap p on each contrast's
    own side and threshold, Holm across the five, and lp_report.rule_reading's registered reading;
  - a reading is drawn only when the gate passes.
Power is reported at the dev effect and at half of it (every difference shifted by half the dev
effect relative to the contrast's threshold; for the gate and two-sided L1, half the dev mean).
POOL-04's boundary rule and the planless-key sensitivity are not simulated (they can only withhold
a reading, so the rates are upper bounds on "resolved" and exact on "not supported").

LP Amendment 4/5 (docs/prereg_lp_planner_strength_20260923.md:276): P27's data are read only through
lp_report.py. Every P27 (and E) episode here comes from lp_report.resolve_campaigns and
lp_report.load_campaign, shaped by j10_report.a1_arm_episodes exactly as lp_report._planner_block
shapes them; the dev reference values are lp_report.evaluate_gate / evaluate_contrast. This file
opens no result file itself.

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

from scripts.analysis import am1_power as ap  # noqa: E402
from scripts.analysis import j10_report as j10  # noqa: E402
from scripts.analysis import lp_report as lp  # noqa: E402

PLANNER = "P27"
TEST_SCENARIOS = 56  # J11 prereg §2: 168 test_normal tasks, 56 scenario clusters
SEEDS: tuple[int, ...] = (1, 2)
DEFAULT_R = 1000
DEFAULT_B = 2000
DEFAULT_SEED = 20260924
OUT_DEFAULT = REPO_ROOT / "campaign" / "results" / "j11_power_dev_20260924.report.json"
ARM_CODES: tuple[str, ...] = ("C", "T", "A", "A1", "M_bplus_6", "M_bplus_11", "M_zs_6", "M_zs_11")
POSITIVE = ("replicates", "supported")

# The gate and L1-L5 as lp_report registers them (lp.GATE, lp.CONTRASTS).
SPECS: dict[str, dict[str, Any]] = {
    "gate": {"left": lp.GATE["left"], "right": lp.GATE["right"], "direction": "greater", "threshold": 0.0},
    **{c["id"]: {"left": c["left"], "right": c["right"], "direction": c["p_direction"],
                 "threshold": c["threshold_pp"] / 100.0} for c in lp.CONTRASTS},
}
L_IDS = lp.L_IDS


# ---- loading: through lp_report only -----------------------------------------------------------
def load_dev_arms(results_root: Path = lp.RESULTS_ROOT) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """P27's LP arms and E, each loaded by lp_report.load_campaign from the campaign lp_report resolves.

    Returns ({code: j10.a1_arm_episodes block}, {code: campaign}), shaped as lp_report._planner_block
    shapes them (tasks discovered over every arm, seeds 1-2).
    """
    campaigns = {code: blk["campaign"] for code, blk in lp.resolve_campaigns((PLANNER,))[PLANNER].items()
                 if code in ARM_CODES}
    campaigns["E"] = lp.REFERENCE_CAMPAIGNS["E"]
    for name in campaigns.values():
        ap.j16.refuse_heldout(results_root / name)
    loaded = {code: lp.load_campaign(code, results_root / name) for code, name in campaigns.items()}
    tasks = j10.discover_tasks(loaded, list(SEEDS))
    arms = {code: j10.a1_arm_episodes(code, loaded[code], tasks, list(SEEDS)) for code in loaded}
    # lp_report._planner_block's rule: a matrix of the wrong size or split is complete at no count.
    wrong_split = any(k not in {"dev", "unrecorded"} for blob in loaded.values()
                      for k in blob["campaign"]["split_provenance"])
    for arm in arms.values():
        arm["complete"] = bool(arm["complete"] and not wrong_split and len(tasks) == lp.N_TASKS
                               and arm["n_expected"] == lp.EXPECTED_PAIRS)
    return arms, campaigns


def contrast_rows(arms: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """(task, seed, scenario, d, h) per shared key with goal_pass on both sides, per gate / L contrast."""
    return {name: ap.paired_rows(arms[s["left"]]["episodes"], arms[s["right"]]["episodes"])
            for name, s in SPECS.items()}


def dev_reference(arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The dev values the simulation starts from, as lp_report computes them.

    lp.evaluate_gate / lp.evaluate_contrast at LP's registered settings (10,000 draws, seed 20260924).
    A contrast lp_report reads INCOMPLETE (an arm below 114 non-crashed) gets its provisional interval
    from j10.a1_contrast, the call evaluate_contrast makes once complete, on the pairs that exist.
    """
    out: dict[str, Any] = {}
    gate = lp.evaluate_gate(arms, n_boot=lp.N_BOOT, seed=lp.BOOTSTRAP_SEED)
    blocks = {"gate": ("planners.P27.gate", gate)}
    for spec in lp.CONTRASTS:
        blk, _rec = lp.evaluate_contrast(spec, arms, n_boot=lp.N_BOOT, seed=lp.BOOTSTRAP_SEED)
        blocks[spec["id"]] = (f"planners.P27.contrasts.{spec['id']}", blk)
    for name, (key, blk) in blocks.items():
        row: dict[str, Any] = {"lp_report_key": key, "lp_report_status": blk["status"],
                               "n_pairs": blk["n_pairs"], "counts": blk["counts"]}
        if blk["status"] == "COMPLETE":
            row.update(point_pp=blk["point_pp"], ci95_pp_scenario=blk["scenario"]["ci95_pp"],
                       ci95_pp_task=blk["task"]["ci95_pp"], p_raw=blk.get("p_raw"),
                       source="lp_report.evaluate_" + ("gate" if name == "gate" else "contrast"))
        else:
            s = SPECS[name]
            cmp = j10.a1_contrast(arms[s["left"]]["episodes"], arms[s["right"]]["episodes"], lp.FIELD,
                                  n_boot=lp.N_BOOT, seed=lp.BOOTSTRAP_SEED)
            row.update(point_pp=cmp["scenario"]["diff_pp"], ci95_pp_scenario=cmp["scenario"]["ci95_pp"],
                       ci95_pp_task=cmp["task"]["ci95_pp"],
                       p_raw=(None if name == "gate" else j10.bootstrap_pvalue(
                           cmp["scenario"]["_means"], s["threshold"], s["direction"])),
                       source="PROVISIONAL: j10.a1_contrast on the pairs lp_report's loader returned; "
                              "lp_report reads this contrast INCOMPLETE")
        out[name] = row
    return out


# ---- the registered analysis of one simulated read (pure) -------------------------------------------
def analyse_read(stats: dict[str, dict[str, Any]], alpha: float = lp.ALPHA) -> dict[str, Any]:
    """J11's reading of one read. stats[name] = {point, lo, hi, p}; the gate needs only point."""
    gate_passes = bool(stats["gate"]["point"] > lp.GATE_ZERO_TOL)
    adjusted = j10.holm_adjust([float(stats[c]["p"]) for c in L_IDS])
    readings = {}
    for c, p_holm in zip(L_IDS, adjusted):
        rec = {"point": stats[c]["point"], "lo": stats[c]["lo"], "hi": stats[c]["hi"], "boundary": False}
        readings[c] = lp.rule_reading(c, rec, p_holm, alpha)[0]
    return {"gate_passes": gate_passes, "p_holm": dict(zip(L_IDS, adjusted)), "readings": readings}


def simulate(
    indices: dict[str, dict[str, dict[str, dict[int, tuple[float, float]]]]],
    shifts: dict[str, float],
    *,
    n_sims: int,
    n_boot: int,
    seed: int,
    n_scenarios: int = TEST_SCENARIOS,
) -> dict[str, Any]:
    """Joint simulated reads of the gate and L1-L5; rates over n_sims."""
    scenarios = sorted({s for idx in indices.values() for s in idx})
    tasks_by_scenario: dict[str, list[str]] = {}
    for idx in indices.values():
        for scen, tasks in idx.items():
            known = tasks_by_scenario.setdefault(scen, [])
            for t in tasks:
                if t not in known:
                    known.append(t)
    for scen in tasks_by_scenario:
        tasks_by_scenario[scen].sort()
    rng = np.random.default_rng(seed)
    n = {"gate_passes": 0, "gate_and_L1_replicates": 0, "gate_and_all_five": 0}
    per_l = {c: {"positive_under_holm": 0, "registered": 0} for c in L_IDS}
    l1 = {r: 0 for r in lp.L1_READINGS}
    for _ in range(n_sims):
        design = ap.draw_design(scenarios, tasks_by_scenario, rng, n_scenarios=n_scenarios,
                                seeds_available=SEEDS, seeds_per_task=len(SEEDS))
        stats: dict[str, dict[str, Any]] = {}
        for name in SPECS:
            num, den = ap.cluster_sums(indices[name], design, shifts[name], False)
            point = float(num.sum() / den.sum())
            if name == "gate":
                stats[name] = {"point": point}
                continue
            means = ap.bootstrap_means(num, den, n_boot, rng)
            lo, hi = ap.percentile_ci(means)
            stats[name] = {"point": point, "lo": lo, "hi": hi,
                           "p": ap.pvalue(means, SPECS[name]["threshold"], SPECS[name]["direction"])}
        read = analyse_read(stats)
        gate = read["gate_passes"]
        n["gate_passes"] += int(gate)
        for c in L_IDS:
            positive = read["readings"][c] in POSITIVE
            per_l[c]["positive_under_holm"] += int(positive)
            per_l[c]["registered"] += int(gate and positive)
        l1[read["readings"]["L1"]] = l1.get(read["readings"]["L1"], 0) + 1
        n["gate_and_L1_replicates"] += int(gate and read["readings"]["L1"] == "replicates")
        n["gate_and_all_five"] += int(gate and all(read["readings"][c] in POSITIVE for c in L_IDS))
    rate = lambda k: round(k / n_sims, 4)  # noqa: E731
    return {
        "gate_passes": rate(n["gate_passes"]),
        "L": {c: {k: rate(v) for k, v in d.items()} for c, d in per_l.items()},
        "L1_readings_ignoring_gate": {k: rate(v) for k, v in l1.items()},
        "joint": {"gate_and_L1_replicates": rate(n["gate_and_L1_replicates"]),
                  "gate_and_all_five_positive": rate(n["gate_and_all_five"])},
    }


def half_shifts(points: dict[str, float]) -> dict[str, float]:
    """Half the dev effect: each difference shifted by half its distance from the contrast's null
    (the gate and two-sided L1: half the dev mean; one-sided L2-L5: half of point - threshold)."""
    out = {}
    for name, point in points.items():
        s = SPECS[name]
        out[name] = point / 2.0 if name == "gate" or s["direction"] == "two-sided" else (point - s["threshold"]) / 2.0
    return out


def build(root: Path, n_sims: int, n_boot: int, seed: int) -> dict[str, Any]:
    ap.j16.refuse_heldout(root)
    arms, campaigns = load_dev_arms(root)
    rows = contrast_rows(arms)
    indices = {name: ap.index_by_scenario(r) for name, r in rows.items()}
    points = {name: statistics.fmean(r["d"] for r in rows[name]) for name in SPECS}
    dev = dev_reference(arms)
    at_dev = simulate(indices, {name: 0.0 for name in SPECS}, n_sims=n_sims, n_boot=n_boot, seed=seed)
    half = half_shifts(points)
    at_half = simulate(indices, half, n_sims=n_sims, n_boot=n_boot, seed=seed + 1)
    table = {
        "gate_passes": {"at_dev_effect": at_dev["gate_passes"], "at_half_effect": at_half["gate_passes"]},
        **{c: {"at_dev_effect": at_dev["L"][c]["registered"], "at_half_effect": at_half["L"][c]["registered"],
               "reading": "L1 replicates" if c == "L1" else "supported",
               "note": "gate passes AND the registered reading (Holm m = 5)"} for c in L_IDS},
        "gate_and_L1_replicates": {"at_dev_effect": at_dev["joint"]["gate_and_L1_replicates"],
                                   "at_half_effect": at_half["joint"]["gate_and_L1_replicates"]},
        "gate_and_all_five_positive": {"at_dev_effect": at_dev["joint"]["gate_and_all_five_positive"],
                                       "at_half_effect": at_half["joint"]["gate_and_all_five_positive"]},
    }
    return {
        "generated_by": "scripts/analysis/j11_power.py",
        "split": "dev",
        "purpose": "power of the J11 registration (LP's gate and L1-L5 for P27) at the test_normal design",
        "prereg": "docs/prereg_j11_lp2_test_20260924.md §5",
        "loaded_through": {"campaigns": "lp_report.resolve_campaigns(('P27',)) + lp_report.REFERENCE_CAMPAIGNS['E']",
                           "episodes": "lp_report.load_campaign -> j10_report.a1_arm_episodes (as lp_report._planner_block)",
                           "dev_values": "lp_report.evaluate_gate / lp_report.evaluate_contrast"},
        "campaigns": campaigns,
        "arm_counts": {code: {k: arms[code][k] for k in ("n_scored", "n_expected", "n_crash", "n_missing", "complete")}
                       for code in arms},
        "pairs_per_contrast": {name: len(r) for name, r in rows.items()},
        "design": {"n_scenarios": TEST_SCENARIOS, "tasks_per_scenario": "as on dev (3)", "seeds": list(SEEDS),
                   "dev_scenarios": len({r["scenario"] for r in rows["gate"]})},
        "n_sims": n_sims, "n_boot_per_sim": n_boot, "seed": seed, "alpha": lp.ALPHA,
        "dev": dev,
        "dev_points_pp_from_pairs": {k: round(v * 100, 2) for k, v in points.items()},
        "half_effect_shift_pp": {k: round(v * 100, 3) for k, v in half.items()},
        "power_table": table,
        "power_at_dev_effect": at_dev,
        "power_at_half_effect": at_half,
        "caveats": [
            "Resampling dev scenarios treats the dev effect as the truth; the half-effect rows are the guard against that optimism.",
            "B per simulated read (2,000) is below the registered 10,000; interval endpoints carry Monte Carlo error of a few tenths of a pp.",
            "POOL-04's boundary rule and the planless-key sensitivity are not simulated; each can only withhold a reading.",
            "Contrasts on an arm below 114 non-crashed dev pairs use the pairs that exist (see arm_counts, pairs_per_contrast); "
            "their dev values are PROVISIONAL, and lp_report reads them INCOMPLETE until the refill lands.",
        ],
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", type=Path, default=lp.RESULTS_ROOT)
    parser.add_argument("--sims", type=int, default=DEFAULT_R)
    parser.add_argument("--boot", type=int, default=DEFAULT_B)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args(argv)
    ap.j16.refuse_heldout(args.out)
    report = build(args.root, args.sims, args.boot, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"dev": report["dev"], "pairs": report["pairs_per_contrast"],
                      "power_table": report["power_table"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
