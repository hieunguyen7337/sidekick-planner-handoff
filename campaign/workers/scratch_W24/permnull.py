#!/usr/bin/env python3
"""
W-24 paired sign-flip permutation null.

Read-only on /scratch. Reuses W-20 load/complete/SEEDS so the population
matches W-20 exactly. Contestable mask is the observed W-20 subset (post-hoc);
it is not re-derived after each permutation.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict

import numpy as np

TRAIN_PATH = "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl"
DEV_PATH = "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl"

# Copied from campaign/workers/scratch_W20/analyze_ceiling.py
SEEDS = (101, 102, 103, 104)
DELTAS = (0.166, 0.100)

PERM_SEED = 20260918
N_PERM = 10_000
PERCENTILES = (2.5, 97.5)


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


def inspect_seeds(path):
    """Report unique branch_seed values actually present per condition."""
    seeds_by_cond = defaultdict(set)
    n_rows = 0
    n_null = 0
    with open(path) as f:
        for line in f:
            n_rows += 1
            r = json.loads(line)
            seeds_by_cond[r["condition"]].add(r["branch_seed"])
            if r["branch_gpr"] is None:
                n_null += 1
    return {
        "n_rows": n_rows,
        "n_null": n_null,
        "seeds": {c: sorted(s) for c, s in seeds_by_cond.items()},
    }


def matrices_from_complete(comp, seeds=SEEDS):
    """Return treated, untreated arrays shape (n_points, n_seeds), plus labels."""
    keys = sorted(comp.keys())
    n = len(keys)
    k = len(seeds)
    treated = np.empty((n, k), dtype=np.float64)
    untreated = np.empty((n, k), dtype=np.float64)
    for i, p in enumerate(keys):
        d = comp[p]
        for j, s in enumerate(seeds):
            treated[i, j] = d[("treated", s)]
            untreated[i, j] = d[("untreated", s)]
    return keys, treated, untreated


def observed_masks(treated, untreated):
    """W-20 ceiling/floor/contestable on observed means. Masks are fixed."""
    mean_t = treated.mean(axis=1)
    mean_u = untreated.mean(axis=1)
    is_ceil = mean_u >= 1.0
    is_flr = (mean_u <= 0.0) & (mean_t <= 0.0)
    is_contestable = (~is_ceil) & (~is_flr)
    return {
        "all_complete": np.ones(treated.shape[0], dtype=bool),
        "contestable": is_contestable,
        "ceiling": is_ceil,
        "floor": is_flr,
        "mean_t": mean_t,
        "mean_u": mean_u,
    }


def pearson_r(a, b):
    a = a.ravel()
    b = b.ravel()
    if a.size < 2:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def stats_from_delta(delta, mean_t, mean_u, delta_thresh):
    """All headline statistics for one 1-d delta vector (one subset)."""
    n = int(delta.size)
    needed = int(np.sum(delta > delta_thresh))
    needless = int(np.sum(delta < -delta_thresh))
    ambiguous = n - needed - needless
    help_v = np.maximum(delta, 0.0)
    harm_v = np.maximum(-delta, 0.0)
    mean_delta = float(delta.mean()) if n else float("nan")
    mean_help = float(help_v.mean()) if n else float("nan")
    mean_harm = float(harm_v.mean()) if n else float("nan")
    mean_t_bar = float(mean_t.mean()) if n else float("nan")
    mean_u_bar = float(mean_u.mean()) if n else float("nan")
    lhs = mean_t_bar + mean_harm
    rhs = mean_u_bar + mean_help
    return {
        "n": n,
        "needed": needed,
        "needless": needless,
        "ambiguous": ambiguous,
        "f": (needed / n) if n else float("nan"),
        "asymmetry": needed - needless,
        "mean_delta": mean_delta,
        "mean_help": mean_help,
        "mean_harm": mean_harm,
        "mean_t": mean_t_bar,
        "mean_u": mean_u_bar,
        "identity_lhs": lhs,
        "identity_rhs": rhs,
        "identity_abs_diff": abs(lhs - rhs),
    }


def null_stats_from_perm_delta(perm_delta, delta_thresh):
    """
    perm_delta: (n_perm, n_subset)
    Returns arrays of length n_perm for each statistic.
    mean_t / mean_u are not needed for null of Δ-derived stats.
    """
    needed = (perm_delta > delta_thresh).sum(axis=1)
    needless = (perm_delta < -delta_thresh).sum(axis=1)
    mean_delta = perm_delta.mean(axis=1)
    help_v = np.maximum(perm_delta, 0.0).mean(axis=1)
    harm_v = np.maximum(-perm_delta, 0.0).mean(axis=1)
    n = perm_delta.shape[1]
    f = needed / n
    asymmetry = needed - needless
    return {
        "needed": needed.astype(np.int64),
        "f": f,
        "needless": needless.astype(np.int64),
        "mean_delta": mean_delta,
        "mean_help": help_v,
        "mean_harm": harm_v,
        "asymmetry": asymmetry.astype(np.int64),
    }


def summarize_null(obs_value, null_arr, sided="greater"):
    null_arr = np.asarray(null_arr, dtype=np.float64)
    lo, hi = np.percentile(null_arr, list(PERCENTILES))
    ge = int(np.sum(null_arr >= obs_value))
    le = int(np.sum(null_arr <= obs_value))
    two = int(np.sum(np.abs(null_arr) >= abs(obs_value)))
    n = int(null_arr.size)
    inside = (lo <= obs_value <= hi)
    out = {
        "observed": float(obs_value),
        "null_mean": float(null_arr.mean()),
        "null_p025": float(lo),
        "null_p975": float(hi),
        "n_perm": n,
        "n_ge": ge,
        "n_le": le,
        "n_abs_ge": two,
        "p_one_sided_ge": ge / n,
        "p_one_sided_le": le / n,
        "p_two_sided_abs": two / n,
        "observed_inside_null_interval": bool(inside),
    }
    if sided == "greater":
        out["p_reported"] = out["p_one_sided_ge"]
        out["p_count"] = ge
    elif sided == "two-sided":
        out["p_reported"] = out["p_two_sided_abs"]
        out["p_count"] = two
    else:
        raise ValueError(sided)
    return out


def fmt_p(s):
    return (
        f"{s['p_reported']:.6f} ({s['p_count']}/{s['n_perm']}); "
        f"inside_null_95pct={s['observed_inside_null_interval']}"
    )


def print_row(name, s, extra=""):
    print(
        f"    {name:22s}  obs={s['observed']:.10g}  "
        f"null_mean={s['null_mean']:.10g}  "
        f"null_2.5={s['null_p025']:.10g}  "
        f"null_97.5={s['null_p975']:.10g}  "
        f"p={fmt_p(s)}{extra}"
    )


def run_split(name, path, rng):
    print()
    print("=" * 78)
    print(f"DATASET: {name}")
    print(f"File: {path}")
    print("=" * 78)

    seed_info = inspect_seeds(path)
    print("[REPLICATE SEEDS ACTUALLY PRESENT IN FILE]")
    print(f"  n_rows={seed_info['n_rows']} n_null_gpr={seed_info['n_null']}")
    for cond in sorted(seed_info["seeds"]):
        seeds = seed_info["seeds"][cond]
        print(f"  condition={cond!r} unique_branch_seeds={seeds} count={len(seeds)}")

    pts, n_rows, n_null = load(path)
    comp = complete(pts)
    print("[W-20 POPULATION]")
    print(f"  load() n_rows={n_rows} n_null={n_null} total_points={len(pts)}")
    print(f"  complete() n={len(comp)} using SEEDS={list(SEEDS)}")
    print(f"  incomplete_points={len(pts) - len(comp)}")

    keys, treated, untreated = matrices_from_complete(comp)
    diffs = treated - untreated  # (n, k); sign-flip of pair s negates diffs[:, s]
    masks = observed_masks(treated, untreated)
    delta_obs = diffs.mean(axis=1)
    mean_t = masks["mean_t"]
    mean_u = masks["mean_u"]

    r_pair = pearson_r(treated, untreated)
    print("[CRN PAIRING]")
    print(f"  Pearson r(treated, untreated) over (point, seed) pairs on complete points = {r_pair:.10f}")
    print(f"  n_pairs = {treated.size}")

    print("[OBSERVED SUBSET COUNTS — W-20 DEFINITIONS, FIXED MASKS]")
    print(f"  all_complete n={int(masks['all_complete'].sum())}")
    print(f"  ceiling (mean_u >= 1.0) n={int(masks['ceiling'].sum())}")
    print(f"  floor (mean_u <= 0 and mean_t <= 0) n={int(masks['floor'].sum())}")
    print(f"  contestable (non-ceiling & non-floor; POST-HOC subset) n={int(masks['contestable'].sum())}")

    # Identity on observed all-complete
    help_all = np.maximum(delta_obs, 0.0)
    harm_all = np.maximum(-delta_obs, 0.0)
    lhs = float(mean_t.mean() + harm_all.mean())
    rhs = float(mean_u.mean() + help_all.mean())
    print("[IDENTITY all-complete observed]")
    print(f"  mean(treated) + mean(harm) = {lhs:.16f}")
    print(f"  mean(untreated) + mean(help) = {rhs:.16f}")
    print(f"  abs_diff = {abs(lhs - rhs):.3e}")
    print(f"  holds (abs_diff < 1e-12) = {abs(lhs - rhs) < 1e-12}")

    n_pts, n_seeds = diffs.shape
    t0 = time.time()
    # Independent swap of treated[s] <-> untreated[s] with p=0.5
    # equivalent to multiplying per-seed difference by ±1.
    flips = rng.random((N_PERM, n_pts, n_seeds)) < 0.5
    signs = np.where(flips, -1.0, 1.0)
    perm_delta = (signs * diffs[None, :, :]).mean(axis=2)  # (N_PERM, n_pts)
    elapsed = time.time() - t0
    print("[PERMUTATIONS]")
    print(f"  N_PERM={N_PERM} PERM_SEED={PERM_SEED} (Generator consumed from shared rng)")
    print(f"  sign array shape={tuple(signs.shape)} perm_delta shape={tuple(perm_delta.shape)}")
    print(f"  wall_s={elapsed:.3f}")
    print(f"  method=paired_sign_flip_per_(point,seed); NOT pooled reshuffle")

    subset_names = ("all_complete", "contestable")
    results = {}
    for subset in subset_names:
        mask = masks[subset]
        n_sub = int(mask.sum())
        d_obs = delta_obs[mask]
        mt = mean_t[mask]
        mu = mean_u[mask]
        pd = perm_delta[:, mask]
        posthoc = "yes" if subset == "contestable" else "no"
        print()
        print(f"--- SUBSET {subset} n={n_sub} post_hoc={posthoc} ---")
        results[subset] = {}
        for dth in DELTAS:
            obs = stats_from_delta(d_obs, mt, mu, dth)
            print(
                f"  δ={dth:.3f} observed: "
                f"needed={obs['needed']}/{obs['n']} f={obs['f']:.10f} "
                f"needless={obs['needless']}/{obs['n']} "
                f"ambiguous={obs['ambiguous']}/{obs['n']} "
                f"asymmetry(needed-needless)={obs['asymmetry']} "
                f"mean_Δ={obs['mean_delta']:+.10f} "
                f"mean_help={obs['mean_help']:.10f} "
                f"mean_harm={obs['mean_harm']:.10f}"
            )
            print(
                f"    identity: mean(t)+mean(harm)={obs['identity_lhs']:.16f} "
                f"mean(u)+mean(help)={obs['identity_rhs']:.16f} "
                f"abs_diff={obs['identity_abs_diff']:.3e} "
                f"holds={obs['identity_abs_diff'] < 1e-12}"
            )
            nulls = null_stats_from_perm_delta(pd, dth)
            block = {"observed": obs, "null": {}}
            # Brief: one-sided p = fraction of permutations with statistic >= observed
            for key in ("needed", "f", "needless", "mean_delta", "mean_help", "mean_harm"):
                block["null"][key] = summarize_null(obs[key], nulls[key], sided="greater")
            block["null"]["asymmetry"] = summarize_null(
                obs["asymmetry"], nulls["asymmetry"], sided="two-sided"
            )

            print("    one-sided p = n(perm >= obs) / N_PERM")
            print_row("needed", block["null"]["needed"])
            print_row("f=needed/n", block["null"]["f"])
            print_row("needless", block["null"]["needless"])
            print_row("mean_Δ", block["null"]["mean_delta"])
            print_row("mean_help", block["null"]["mean_help"])
            print_row("mean_harm", block["null"]["mean_harm"])
            print("    two-sided p for asymmetry = n(|perm| >= |obs|) / N_PERM")
            print_row("needed-needless", block["null"]["asymmetry"])
            results[subset][f"{dth:.3f}"] = block

    return {
        "name": name,
        "path": path,
        "n_complete": len(comp),
        "seeds_in_file": seed_info["seeds"],
        "pairing_r": r_pair,
        "n_ceiling": int(masks["ceiling"].sum()),
        "n_floor": int(masks["floor"].sum()),
        "n_contestable": int(masks["contestable"].sum()),
        "identity_all_abs_diff": abs(lhs - rhs),
        "results": results,
    }


def main():
    print("=== W-24 PAIRED SIGN-FLIP PERMUTATION NULL ===")
    print(f"python={sys.version.replace(chr(10), ' ')}")
    print(f"numpy={np.__version__}")
    print(f"PERM_SEED={PERM_SEED}")
    print(f"N_PERM={N_PERM}")
    print(f"SEEDS={list(SEEDS)}  # W-20 completeness definition")
    print(f"DELTAS={list(DELTAS)}")
    print(f"percentile_method=numpy.percentile default (linear) at {PERCENTILES}")
    print("null=for each point, independently for each branch seed s,")
    print("     swap treated[s] with untreated[s] with probability 0.5")
    print("contestable_mask=FIXED from observed W-20 definition (post-hoc subset)")
    print("p_one_sided=fraction of perms with statistic >= observed")
    print("p_two_sided_asymmetry=fraction of perms with |stat| >= |observed|")

    rng = np.random.default_rng(PERM_SEED)
    train = run_split("TRAIN", TRAIN_PATH, rng)
    dev = run_split("DEV", DEV_PATH, rng)

    print()
    print("=" * 78)
    print("DONE")
    print(f"PERM_SEED={PERM_SEED} N_PERM={N_PERM}")
    print(f"train_complete={train['n_complete']} train_contestable={train['n_contestable']} "
          f"train_r={train['pairing_r']:.6f}")
    print(f"dev_complete={dev['n_complete']} dev_contestable={dev['n_contestable']} "
          f"dev_r={dev['pairing_r']:.6f}")
    print("=" * 78)


if __name__ == "__main__":
    main()
