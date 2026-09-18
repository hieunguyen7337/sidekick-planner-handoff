#!/usr/bin/env python3
"""
W-20 ceiling analysis.
Read-only on /scratch.
Re-cuts the estimand excluding ceiling points (and floor points).
"""
import json
import math
import statistics as st
from collections import defaultdict

TRAIN_PATH = "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl"
DEV_PATH   = "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl"

SEEDS = (101, 102, 103, 104)
DELTAS = [0.166, 0.100, 0.083, 0.200]

def load(path):
    pts = defaultdict(dict)  # point -> (cond, seed) -> gpr
    n_rows = 0
    n_null = 0
    with open(path) as f:
        for line in f:
            n_rows += 1
            r = json.loads(line)
            point = "/".join(r["key"].split("/")[:4])
            g = r["branch_gpr"]
            if g is None:
                n_null += 1
            pts[point][(r["condition"], r["branch_seed"])] = g
    return pts, n_rows, n_null

def complete(pts, seeds=SEEDS):
    out = {}
    for p, d in pts.items():
        if all(d.get((c, s)) is not None for c in ("treated", "untreated") for s in seeds):
            out[p] = d
    return out

def classify_points(comp):
    """
    Returns classified point dicts:
    all, ceiling, ceiling_0999, floor, floor_0001, contestable, non_ceiling
    """
    metrics = {}
    for p, d in comp.items():
        t_vals = [d[("treated", s)] for s in SEEDS]
        u_vals = [d[("untreated", s)] for s in SEEDS]
        mean_t = sum(t_vals) / len(t_vals)
        mean_u = sum(u_vals) / len(u_vals)
        delta = mean_t - mean_u
        help_val = max(delta, 0.0)
        harm_val = max(-delta, 0.0)

        is_ceil = (mean_u >= 1.0)
        is_ceil_0999 = (mean_u >= 0.999)
        is_flr = (mean_u <= 0.0 and mean_t <= 0.0)
        is_flr_0001 = (mean_u <= 0.001 and mean_t <= 0.001)

        metrics[p] = {
            "mean_t": mean_t,
            "mean_u": mean_u,
            "delta": delta,
            "help": help_val,
            "harm": harm_val,
            "is_ceiling": is_ceil,
            "is_ceiling_0999": is_ceil_0999,
            "is_floor": is_flr,
            "is_floor_0001": is_flr_0001,
            "is_contestable": (not is_ceil) and (not is_flr),
            "is_non_ceiling": (not is_ceil),
        }
    return metrics

def labels_for_delta(delta_val, delta_thresh):
    if delta_val > delta_thresh:
        return "needed"
    elif delta_val < -delta_thresh:
        return "needless"
    else:
        return "ambiguous"

def analyze_subset(subset_name, pts_metrics, total_n):
    n = len(pts_metrics)
    frac = n / total_n if total_n > 0 else 0.0

    deltas = [m["delta"] for m in pts_metrics.values()]
    helps = [m["help"] for m in pts_metrics.values()]
    harms = [m["harm"] for m in pts_metrics.values()]
    mean_ts = [m["mean_t"] for m in pts_metrics.values()]
    mean_us = [m["mean_u"] for m in pts_metrics.values()]

    mean_d = sum(deltas) / n if n > 0 else 0.0
    mean_h = sum(helps) / n if n > 0 else 0.0
    mean_harm = sum(harms) / n if n > 0 else 0.0
    mean_t_bar = sum(mean_ts) / n if n > 0 else 0.0
    mean_u_bar = sum(mean_us) / n if n > 0 else 0.0
    sd_d = st.stdev(deltas) if n > 1 else 0.0

    print(f"\n--- Subset: {subset_name} ---")
    print(f"Count: n = {n} ({frac:.4f} of total {total_n})")
    print(f"mean(treated)   = {mean_t_bar:.6f}")
    print(f"mean(untreated) = {mean_u_bar:.6f}")
    print(f"mean(Δ)         = {mean_d:+.6f} (SD = {sd_d:.6f})")
    print(f"mean(help)      = {mean_h:.6f}")
    print(f"mean(harm)      = {mean_harm:.6f}")

    label_results = {}
    for d_thresh in DELTAS:
        counts = {"needed": 0, "needless": 0, "ambiguous": 0}
        for m in pts_metrics.values():
            lab = labels_for_delta(m["delta"], d_thresh)
            counts[lab] += 1
        needed = counts["needed"]
        needless = counts["needless"]
        ambiguous = counts["ambiguous"]
        f = needed / n if n > 0 else 0.0
        one_minus_f = 1.0 - f
        label_results[d_thresh] = {
            "needed": needed,
            "needless": needless,
            "ambiguous": ambiguous,
            "f": f,
            "1-f": one_minus_f,
        }
        print(f"  δ = {d_thresh:.3f}: needed = {needed} ({needed}/{n} = {f:.4f}), "
              f"needless = {needless} ({needless}/{n} = {needless/n if n>0 else 0:.4f}), "
              f"ambiguous = {ambiguous} ({ambiguous}/{n} = {ambiguous/n if n>0 else 0:.4f}) | "
              f"f = {f:.4f}, 1-f = {one_minus_f:.4f}")

    return {
        "n": n,
        "frac": frac,
        "mean_t": mean_t_bar,
        "mean_u": mean_u_bar,
        "mean_d": mean_d,
        "mean_h": mean_h,
        "mean_harm": mean_harm,
        "sd_d": sd_d,
        "labels": label_results,
    }

def run_analysis(path, name):
    pts, n_rows, n_null = load(path)
    comp = complete(pts)
    total_pts = len(pts)
    n_comp = len(comp)

    print(f"\n=======================================================")
    print(f"DATASET: {name}")
    print(f"File: {path}")
    print(f"Total rows: {n_rows}, Null gpr rows: {n_null}")
    print(f"Total points: {total_pts}, Complete 4-rep points: {n_comp}")
    print(f"Incomplete points: {total_pts - n_comp}")
    print(f"=======================================================")

    metrics = classify_points(comp)

    all_pts         = {p: m for p, m in metrics.items()}
    ceiling_pts     = {p: m for p, m in metrics.items() if m["is_ceiling"]}
    ceiling_0999    = {p: m for p, m in metrics.items() if m["is_ceiling_0999"]}
    floor_pts       = {p: m for p, m in metrics.items() if m["is_floor"]}
    floor_0001      = {p: m for p, m in metrics.items() if m["is_floor_0001"]}
    contestable_pts = {p: m for p, m in metrics.items() if m["is_contestable"]}
    non_ceiling_pts = {p: m for p, m in metrics.items() if m["is_non_ceiling"]}

    print("\n[FLOAT NOISE / THRESHOLD SENSITIVITY CHECK]")
    print(f"Ceiling (mean_u >= 1.0):   {len(ceiling_pts)}")
    print(f"Ceiling (mean_u >= 0.999): {len(ceiling_0999)} (diff = {len(ceiling_0999) - len(ceiling_pts)})")
    print(f"Floor (mean_u <= 0.0 & mean_t <= 0.0):     {len(floor_pts)}")
    print(f"Floor (mean_u <= 0.001 & mean_t <= 0.001): {len(floor_0001)} (diff = {len(floor_0001) - len(floor_pts)})")

    # Check ceiling Δ max
    ceil_deltas = [m["delta"] for m in ceiling_pts.values()]
    if ceil_deltas:
        print(f"Ceiling points: max Δ = {max(ceil_deltas):+.6f}, min Δ = {min(ceil_deltas):+.6f}, mean Δ = {st.mean(ceil_deltas):+.6f}")
        print(f"Ceiling points with Δ > 0: {sum(1 for d in ceil_deltas if d > 0)}")
        print(f"Ceiling points with Δ == 0: {sum(1 for d in ceil_deltas if d == 0)}")
        print(f"Ceiling points with Δ < 0: {sum(1 for d in ceil_deltas if d < 0)}")

    flr_deltas = [m["delta"] for m in floor_pts.values()]
    if flr_deltas:
        print(f"Floor points: max Δ = {max(flr_deltas):+.6f}, min Δ = {min(flr_deltas):+.6f}, mean Δ = {st.mean(flr_deltas):+.6f}")
        print(f"Floor points with Δ != 0: {sum(1 for d in flr_deltas if d != 0)}")

    res_all         = analyze_subset("ALL COMPLETE POINTS", all_pts, n_comp)
    res_ceil        = analyze_subset("CEILING POINTS (mean_u >= 1.0)", ceiling_pts, n_comp)
    res_floor       = analyze_subset("FLOOR POINTS (mean_u <= 0 and mean_t <= 0)", floor_pts, n_comp)
    res_contestable = analyze_subset("CONTESTABLE POINTS (non-ceiling & non-floor)", contestable_pts, n_comp)
    res_non_ceil    = analyze_subset("NON-CEILING POINTS (all minus ceiling)", non_ceiling_pts, n_comp)

    # Invariant verification: needed counts
    print("\n[INVARIANT CHECK: NEEDED COUNTS]")
    for d_thresh in DELTAS:
        n_needed_all = res_all["labels"][d_thresh]["needed"]
        n_needed_non_ceil = res_non_ceil["labels"][d_thresh]["needed"]
        n_needed_contestable = res_contestable["labels"][d_thresh]["needed"]
        n_needed_ceil = res_ceil["labels"][d_thresh]["needed"]
        n_needed_floor = res_floor["labels"][d_thresh]["needed"]
        match_str = "MATCH (UNCHANGED)" if (n_needed_all == n_needed_non_ceil == n_needed_contestable) else "MISMATCH!"
        print(f"  δ = {d_thresh:.3f}: ALL={n_needed_all}, NON_CEILING={n_needed_non_ceil}, CONTESTABLE={n_needed_contestable} | "
              f"CEIL={n_needed_ceil}, FLOOR={n_needed_floor} => {match_str}")

    # Contribution of ceiling points to overall mean Δ
    print("\n[DECOMPOSITION OF MEAN Δ]")
    n_c = len(ceiling_pts)
    n_fl = len(floor_pts)
    n_ct = len(contestable_pts)
    n_nc = len(non_ceiling_pts)

    mean_d_all = res_all["mean_d"]
    mean_d_ceil = res_ceil["mean_d"] if n_c > 0 else 0.0
    mean_d_fl = res_floor["mean_d"] if n_fl > 0 else 0.0
    mean_d_ct = res_contestable["mean_d"] if n_ct > 0 else 0.0
    mean_d_nc = res_non_ceil["mean_d"] if n_nc > 0 else 0.0

    ceil_contrib = (n_c / n_comp) * mean_d_ceil
    non_ceil_contrib = (n_nc / n_comp) * mean_d_nc
    reconstructed_d = ceil_contrib + non_ceil_contrib

    print(f"  Overall mean Δ (all):             {mean_d_all:+.6f}")
    print(f"  Ceiling point mean Δ:             {mean_d_ceil:+.6f} (weight = {n_c}/{n_comp} = {n_c/n_comp:.4f})")
    print(f"  Non-ceiling point mean Δ:         {mean_d_nc:+.6f} (weight = {n_nc}/{n_comp} = {n_nc/n_comp:.4f})")
    print(f"  Contestable point mean Δ:         {mean_d_ct:+.6f} (weight = {n_ct}/{n_comp} = {n_ct/n_comp:.4f})")
    print(f"  Floor point mean Δ:               {mean_d_fl:+.6f} (weight = {n_fl}/{n_comp} = {n_fl/n_comp:.4f})")
    print(f"  Ceiling point drag on overall Δ:  {ceil_contrib:+.6f}")
    print(f"  Reconstructed overall mean Δ:     {reconstructed_d:+.6f} (diff = {mean_d_all - reconstructed_d:+.6e})")
    print(f"  Mean Δ change (All -> Non-Ceil):   {mean_d_nc - mean_d_all:+.6f}")
    print(f"  Mean Δ change (All -> Contestable):{mean_d_ct - mean_d_all:+.6f}")

    return {
        "metrics": metrics,
        "res_all": res_all,
        "res_ceil": res_ceil,
        "res_floor": res_floor,
        "res_contestable": res_contestable,
        "res_non_ceil": res_non_ceil,
    }

if __name__ == "__main__":
    print("=== W-20 CEILING ANALYSIS ===")
    tr_res = run_analysis(TRAIN_PATH, "TRAIN")
    dv_res = run_analysis(DEV_PATH, "DEV")
