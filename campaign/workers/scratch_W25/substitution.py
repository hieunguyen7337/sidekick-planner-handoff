#!/usr/bin/env python3
"""
W-25 substitution test.

Read-only on /scratch. Reuses W-24 load/complete/SEEDS so the population
matches W-24/W-20 exactly. Counts later reviews from untreated branch
events.jsonl (ground truth). Paired sign-flip permutation null on the
n_later = 0 subset is the same procedure as W-24.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scratch_W24"))
import permnull as w24  # noqa: E402

TRAIN_PATH = w24.TRAIN_PATH
DEV_PATH = w24.DEV_PATH
SEEDS = w24.SEEDS
DELTAS = w24.DELTAS
N_PERM = w24.N_PERM
PERM_SEED = 20260918
SPEARMAN_PERM_SEED = 20260919
SPEARMAN_N_PERM = 10_000
REVIEW_EVERY_K = 5

BUCKET_ORDER = ("0", "0.5", "1", "1.5", "2", "2.5", "3+")


def load_rows(path):
    """Last row per (point, condition, seed) wins, matching W-24 load()."""
    pts = defaultdict(dict)
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
            pts[point][(r["condition"], r["branch_seed"])] = r
    return pts, n_rows, n_null


def complete_rows(pts, seeds=SEEDS):
    out = {}
    for p, d in pts.items():
        if all(
            d.get((c, s)) is not None and d[(c, s)].get("branch_gpr") is not None
            for c in ("treated", "untreated")
            for s in seeds
        ):
            out[p] = d
    return out


def gpr_maps(comp, seeds=SEEDS):
    """Match W-24 complete() shape: point -> (cond, seed) -> gpr."""
    out = {}
    for p, d in comp.items():
        out[p] = {(c, s): d[(c, s)]["branch_gpr"] for c in ("treated", "untreated") for s in seeds}
    return out


def events_path(results_root: Path, row: dict) -> Path:
    run_id = row.get("run_id")
    if not run_id:
        raise KeyError("run_id missing")
    return results_root / str(run_id) / "events.jsonl"


def count_later_from_events(path: Path, branch_step: int) -> dict:
    n_after = 0
    n_all = 0
    n_live = 0
    n_after_live = 0
    max_step = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            st = ev.get("step")
            if isinstance(st, (int, float)):
                max_step = st if max_step is None else max(max_step, st)
            if ev.get("event_type") != "intervention":
                continue
            n_all += 1
            payload = ev.get("payload") or {}
            is_live = payload.get("source") == "live_policy"
            if is_live:
                n_live += 1
            if st is None:
                continue
            if int(st) > int(branch_step):
                n_after += 1
                if is_live:
                    n_after_live += 1
    return {
        "n_later": n_after,
        "n_intervention_any": n_all,
        "n_live_policy": n_live,
        "n_later_live": n_after_live,
        "max_event_step": max_step,
    }


def proxy_n_later(branch_steps, s, k=REVIEW_EVERY_K):
    if branch_steps is None or s is None:
        return None
    return int(math.floor((int(branch_steps) - int(s)) / k))


def bucket_of(med: float) -> str:
    if med == 0.0:
        return "0"
    if med == 0.5:
        return "0.5"
    if med == 1.0:
        return "1"
    if med == 1.5:
        return "1.5"
    if med == 2.0:
        return "2"
    if med == 2.5:
        return "2.5"
    if med >= 3.0:
        return "3+"
    return f"{med:g}"


def rankdata_average(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    n = a.size
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and a[order[j + 1]] == a[order[i]]:
            j += 1
        avg = 0.5 * ((i + 1) + (j + 1))
        ranks[order[i : j + 1]] = avg
        i = j + 1
    return ranks


def spearman_rho(x, y) -> float:
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    if x.size < 2:
        return float("nan")
    rx = rankdata_average(x)
    ry = rankdata_average(y)
    if rx.std() == 0.0 or ry.std() == 0.0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def pearson_r(x, y) -> float:
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    if x.size < 2 or x.std() == 0.0 or y.std() == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def try_scipy_spearman(x, y):
    try:
        from scipy.stats import spearmanr
    except Exception as exc:
        return None, f"scipy_unavailable:{type(exc).__name__}"
    res = spearmanr(x, y, nan_policy="omit")
    return (float(res.statistic), float(res.pvalue)), "scipy.stats.spearmanr"


def perm_spearman_p(x, y, rng, n_perm) -> dict:
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    obs = spearman_rho(x, y)
    if math.isnan(obs):
        return {
            "rho": obs,
            "p_two_sided": float("nan"),
            "n_abs_ge": 0,
            "n_perm": n_perm,
        }
    count = 0
    abs_obs = abs(obs)
    for _ in range(n_perm):
        rho = spearman_rho(rng.permutation(x), y)
        if abs(rho) >= abs_obs:
            count += 1
    return {
        "rho": obs,
        "p_two_sided": count / n_perm,
        "n_abs_ge": count,
        "n_perm": n_perm,
    }


def scan_untreated_logs(name, results_root: Path, comp_rows):
    n_expected = 0
    n_opened = 0
    n_missing = 0
    n_unreadable = 0
    missing_examples = []
    unreadable_examples = []
    per_point = {}  # point -> list of per-seed records in SEEDS order

    t0 = time.time()
    for p in sorted(comp_rows.keys()):
        d = comp_rows[p]
        recs = []
        for s in SEEDS:
            row = d[("untreated", s)]
            n_expected += 1
            branch_step = row.get("step")
            bsteps = row.get("branch_steps")
            stored = row.get("n_later_reviews")
            proxy = proxy_n_later(bsteps, branch_step)
            rec = {
                "seed": s,
                "step": branch_step,
                "branch_steps": bsteps,
                "stored_n_later_reviews": stored,
                "proxy": proxy,
                "status": None,
                "n_later": None,
                "n_intervention_any": None,
                "n_live_policy": None,
                "n_later_live": None,
                "path": None,
            }
            try:
                path = events_path(results_root, row)
            except KeyError as exc:
                n_missing += 1
                rec["status"] = "missing_run_id"
                rec["error"] = str(exc)
                if len(missing_examples) < 8:
                    missing_examples.append(f"{p} seed={s} no run_id")
                recs.append(rec)
                continue
            rec["path"] = str(path)
            if not path.is_file():
                n_missing += 1
                rec["status"] = "missing"
                if len(missing_examples) < 8:
                    missing_examples.append(str(path))
                recs.append(rec)
                continue
            try:
                counts = count_later_from_events(path, int(branch_step))
            except Exception as exc:
                n_unreadable += 1
                rec["status"] = "unreadable"
                rec["error"] = f"{type(exc).__name__}: {exc}"
                if len(unreadable_examples) < 8:
                    unreadable_examples.append(f"{path} {type(exc).__name__}")
                recs.append(rec)
                continue
            n_opened += 1
            rec["status"] = "ok"
            rec.update(counts)
            recs.append(rec)
        per_point[p] = recs

    elapsed = time.time() - t0
    print(f"[EVENT LOG SCAN {name}]")
    print(f"  results_root={results_root}")
    print(f"  untreated_complete_expected={n_expected}  # n_complete * 4")
    print(f"  opened_readable={n_opened}")
    print(f"  missing={n_missing}")
    print(f"  unreadable={n_unreadable}")
    print(f"  wall_s={elapsed:.3f}")
    if missing_examples:
        print("  missing_examples:")
        for ex in missing_examples:
            print(f"    {ex}")
    if unreadable_examples:
        print("  unreadable_examples:")
        for ex in unreadable_examples:
            print(f"    {ex}")
    return {
        "n_expected": n_expected,
        "n_opened": n_opened,
        "n_missing": n_missing,
        "n_unreadable": n_unreadable,
        "per_point": per_point,
        "missing_examples": missing_examples,
        "unreadable_examples": unreadable_examples,
    }


def point_n_later(recs):
    """Median across the four untreated replicates. None if any seed not ok."""
    if len(recs) != len(SEEDS) or any(r["status"] != "ok" or r["n_later"] is None for r in recs):
        return None
    vals = [int(r["n_later"]) for r in recs]
    med = float(np.median(np.asarray(vals, dtype=np.float64)))
    return {
        "n_later": med,
        "vals": vals,
        "min": min(vals),
        "max": max(vals),
        "all_equal": len(set(vals)) == 1,
        "n_unique": len(set(vals)),
    }


def stats_row(delta, dth):
    n = int(delta.size)
    if n == 0:
        return {
            "n": 0,
            "needed": 0,
            "needless": 0,
            "ambiguous": 0,
            "f": float("nan"),
            "asymmetry": 0,
            "mean_delta": float("nan"),
            "mean_help": float("nan"),
            "mean_harm": float("nan"),
        }
    needed = int(np.sum(delta > dth))
    needless = int(np.sum(delta < -dth))
    help_v = np.maximum(delta, 0.0)
    harm_v = np.maximum(-delta, 0.0)
    return {
        "n": n,
        "needed": needed,
        "needless": needless,
        "ambiguous": n - needed - needless,
        "f": needed / n,
        "asymmetry": needed - needless,
        "mean_delta": float(delta.mean()),
        "mean_help": float(help_v.mean()),
        "mean_harm": float(harm_v.mean()),
    }


def print_dose_table(title, buckets, delta_by_bucket, dth):
    print(f"[DOSE-RESPONSE {title} δ={dth:.3f}]  f = needed / n_bucket")
    print(
        "  bucket  n_points  mean_Δ  mean_help  mean_harm  needed  needless  "
        "f=needed/n  asymmetry=needed-needless"
    )
    for b in buckets:
        d = delta_by_bucket.get(b)
        if d is None or d.size == 0:
            print(f"  {b:<6}  n=0  (empty)")
            continue
        st = stats_row(d, dth)
        print(
            f"  {b:<6}  n={st['n']}  mean_Δ={st['mean_delta']:+.10f}  "
            f"mean_help={st['mean_help']:.10f}  mean_harm={st['mean_harm']:.10f}  "
            f"needed={st['needed']}/{st['n']}  needless={st['needless']}/{st['n']}  "
            f"f={st['needed']}/{st['n']}={st['f']:.10f}  "
            f"asymmetry={st['asymmetry']}"
        )


def print_confound_table(title, buckets, meta_by_bucket):
    print(f"[CONFOUND {title}] per n_later bucket")
    print(
        "  bucket  n  mean_step  mean_untreated  ceiling_frac "
        "(mean_u=1.000 i.e. mean_u>=1)  floor_frac (mean_u<=0 and mean_t<=0)"
    )
    for b in buckets:
        m = meta_by_bucket.get(b)
        if m is None or m["n"] == 0:
            print(f"  {b:<6}  n=0  (empty)")
            continue
        print(
            f"  {b:<6}  n={m['n']}  mean_step={m['mean_step']:.10f}  "
            f"mean_untreated={m['mean_u']:.10f}  "
            f"ceiling={m['n_ceil']}/{m['n']}={m['ceil_frac']:.10f}  "
            f"floor={m['n_floor']}/{m['n']}={m['floor_frac']:.10f}"
        )


def run_perm_on_mask(label, diffs, mask, mean_t, mean_u, rng):
    n_sub = int(mask.sum())
    print()
    print(f"--- PERM {label} n={n_sub} PERM_SEED={PERM_SEED} N_PERM={N_PERM} ---")
    if n_sub == 0:
        print("  empty subset; permutation not run")
        return None
    d_obs = diffs.mean(axis=1)[mask]
    mt = mean_t[mask]
    mu = mean_u[mask]
    n_pts, n_seeds = diffs[mask].shape
    t0 = time.time()
    flips = rng.random((N_PERM, n_pts, n_seeds)) < 0.5
    signs = np.where(flips, -1.0, 1.0)
    perm_delta = (signs * diffs[mask][None, :, :]).mean(axis=2)
    elapsed = time.time() - t0
    print(f"  method=paired_sign_flip_per_(point,seed); NOT pooled reshuffle")
    print(f"  sign array shape={tuple(signs.shape)} perm_delta shape={tuple(perm_delta.shape)}")
    print(f"  wall_s={elapsed:.3f}")

    # precision / achieved resolution of this n
    null_mean_delta = perm_delta.mean(axis=1)
    lo_d, hi_d = np.percentile(null_mean_delta, [2.5, 97.5])
    print("[POWER / PRECISION of this n_later=0 subset]")
    print(f"  SUBSET_SIZE n={n_sub}")
    print(
        f"  under this sign-flip null, mean_Δ 2.5th={lo_d:+.10f} 97.5th={hi_d:+.10f} "
        f"interval_width={hi_d - lo_d:.10f}"
    )
    print(
        f"  a |mean_Δ| smaller than this interval's edge cannot fall outside the null "
        f"interval at this n; that is the resolution of the test, not evidence of absence"
    )

    results = {}
    for dth in DELTAS:
        obs = w24.stats_from_delta(d_obs, mt, mu, dth)
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
        nulls = w24.null_stats_from_perm_delta(perm_delta, dth)
        block = {"observed": obs, "null": {}}
        for key in ("needed", "f", "needless", "mean_delta", "mean_help", "mean_harm"):
            block["null"][key] = w24.summarize_null(obs[key], nulls[key], sided="greater")
        block["null"]["asymmetry"] = w24.summarize_null(
            obs["asymmetry"], nulls["asymmetry"], sided="two-sided"
        )
        print("    one-sided p = n(perm >= obs) / N_PERM")
        w24.print_row("needed", block["null"]["needed"])
        w24.print_row("f=needed/n", block["null"]["f"])
        w24.print_row("needless", block["null"]["needless"])
        w24.print_row("mean_Δ", block["null"]["mean_delta"])
        w24.print_row("mean_help", block["null"]["mean_help"])
        w24.print_row("mean_harm", block["null"]["mean_harm"])
        print("    two-sided p for asymmetry = n(|perm| >= |obs|) / N_PERM")
        w24.print_row("needed-needless", block["null"]["asymmetry"])
        for key, sided in (
            ("needed", "one-sided >= "),
            ("f", "one-sided >= "),
            ("needless", "one-sided >= "),
            ("mean_delta", "one-sided >= "),
            ("mean_help", "one-sided >= "),
            ("mean_harm", "one-sided >= "),
            ("asymmetry", "two-sided | | "),
        ):
            s = block["null"][key]
            loc = "INSIDE" if s["observed_inside_null_interval"] else "OUTSIDE"
            print(
                f"    INTERVAL {key}: observed {s['observed']:.10g} is {loc} "
                f"null [{s['null_p025']:.10g}, {s['null_p975']:.10g}] "
                f"({sided}p={s['p_reported']:.6f} {s['p_count']}/{s['n_perm']})"
            )
        # needed count that would exit the interval
        needed_hi = block["null"]["needed"]["null_p975"]
        print(
            f"    PRECISION needed@δ={dth:.3f}: null 97.5th={needed_hi:.10g}; "
            f"observed needed would have to exceed this to sit above the interval"
        )
        results[f"{dth:.3f}"] = block
    return {"n": n_sub, "results": results}


def run_split(name, path, rng_perm, rng_spear):
    print()
    print("=" * 78)
    print(f"DATASET: {name}")
    print(f"File: {path}")
    print("=" * 78)

    results_root = Path(path).resolve().parent
    seed_info = w24.inspect_seeds(path)
    print("[REPLICATE SEEDS ACTUALLY PRESENT IN FILE]")
    print(f"  n_rows={seed_info['n_rows']} n_null_gpr={seed_info['n_null']}")
    for cond in sorted(seed_info["seeds"]):
        seeds = seed_info["seeds"][cond]
        print(f"  condition={cond!r} unique_branch_seeds={seeds} count={len(seeds)}")

    # W-24 population check
    pts_w24, n_rows_w24, n_null_w24 = w24.load(path)
    comp_w24 = w24.complete(pts_w24)
    pts, n_rows, n_null = load_rows(path)
    comp = complete_rows(pts)
    print("[W-24 POPULATION CHECK]")
    print(f"  w24.load n_rows={n_rows_w24} n_null={n_null_w24} total_points={len(pts_w24)}")
    print(f"  w24.complete n={len(comp_w24)} using SEEDS={list(SEEDS)}")
    print(f"  load_rows n_rows={n_rows} n_null={n_null} total_points={len(pts)}")
    print(f"  complete_rows n={len(comp)}")
    print(f"  complete_keys_equal={set(comp) == set(comp_w24)}")
    print(f"  incomplete_points={len(pts) - len(comp)}")

    keys, treated, untreated = w24.matrices_from_complete(gpr_maps(comp))
    diffs = treated - untreated
    masks = w24.observed_masks(treated, untreated)
    delta_obs = diffs.mean(axis=1)
    mean_t = masks["mean_t"]
    mean_u = masks["mean_u"]
    key_index = {p: i for i, p in enumerate(keys)}

    print("[OBSERVED SUBSET COUNTS — W-20 DEFINITIONS]")
    print(f"  all_complete n={int(masks['all_complete'].sum())}")
    print(f"  ceiling (mean_u >= 1.0) n={int(masks['ceiling'].sum())}")
    print(f"  floor (mean_u <= 0 and mean_t <= 0) n={int(masks['floor'].sum())}")
    print(f"  contestable (non-ceiling & non-floor; POST-HOC) n={int(masks['contestable'].sum())}")

    scan = scan_untreated_logs(name, results_root, comp)

    # per-replicate event vs proxy
    later_ok = []
    proxy_ok = []
    event_for_proxy = []
    stored_ok = []
    live_ok = []
    n_proxy_undef = 0
    n_event_proxy_disagree = 0
    n_event_proxy_pairs = 0
    n_event_stored_disagree = 0
    n_event_live_disagree = 0
    n_event_live_after_disagree = 0
    proxy_neg = 0
    n_full_points = 0
    n_partial_points = 0
    medians = []
    n_later_by_point = {}
    disagree_points = 0
    median0_but_max_pos = 0

    for p in keys:
        recs = scan["per_point"][p]
        nl = point_n_later(recs)
        if nl is None:
            n_partial_points += 1
            continue
        n_full_points += 1
        n_later_by_point[p] = nl
        medians.append(nl["n_later"])
        if not nl["all_equal"]:
            disagree_points += 1
        if nl["n_later"] == 0.0 and nl["max"] > 0:
            median0_but_max_pos += 1
        for r in recs:
            later_ok.append(r["n_later"])
            live_ok.append(r["n_live_policy"])
            stored = r["stored_n_later_reviews"]
            if stored is not None:
                stored_ok.append(int(stored))
                if int(stored) != int(r["n_later"]):
                    n_event_stored_disagree += 1
            if r["n_later"] != r["n_live_policy"]:
                n_event_live_disagree += 1
            if r["n_later"] != r["n_later_live"]:
                n_event_live_after_disagree += 1
            if r["proxy"] is None:
                n_proxy_undef += 1
            else:
                proxy_ok.append(int(r["proxy"]))
                n_event_proxy_pairs += 1
                if int(r["proxy"]) != int(r["n_later"]):
                    n_event_proxy_disagree += 1
                if int(r["proxy"]) < 0:
                    proxy_neg += 1
                event_for_proxy.append(int(r["n_later"]))

    print("[POINT COVERAGE FOR n_later]")
    print(f"  complete_points={len(keys)}")
    print(f"  points_with_all_four_untreated_logs={n_full_points}")
    print(f"  points_missing_any_untreated_log={n_partial_points}")
    print(f"  these missing-any points are EXCLUDED from n_later tables (not silently dropped; counted here)")

    print("[REPLICATE DISAGREEMENT on event-log n_later]")
    print(f"  n_points_all_four_logs={n_full_points}")
    print(f"  n_points_four_replicates_not_all_equal={disagree_points}")
    if n_full_points:
        print(
            f"  disagreement_rate={disagree_points}/{n_full_points}="
            f"{disagree_points / n_full_points:.10f}"
        )
    print(f"  n_points_median_eq_0_but_max_gt_0={median0_but_max_pos}")
    med_hist = Counter(medians)
    print("  median_n_later histogram (exact, including half-integers):")
    for k in sorted(med_hist):
        print(f"    median={k:g}  n={med_hist[k]}")

    print("[EVENT-LOG vs PROXY floor((branch_steps-s)/5)]")
    print(f"  n_pairs_with_proxy={n_event_proxy_pairs} n_proxy_undef={n_proxy_undef}")
    print(f"  n_disagree={n_event_proxy_disagree}")
    if n_event_proxy_pairs:
        agree = n_event_proxy_pairs - n_event_proxy_disagree
        print(
            f"  agreement_rate={agree}/{n_event_proxy_pairs}="
            f"{agree / n_event_proxy_pairs:.10f}"
        )
        print(
            f"  disagreement_rate={n_event_proxy_disagree}/{n_event_proxy_pairs}="
            f"{n_event_proxy_disagree / n_event_proxy_pairs:.10f}"
        )
        r_pp = pearson_r(event_for_proxy, proxy_ok)
        rho_pp = spearman_rho(event_for_proxy, proxy_ok)
        print(f"  Pearson r(event n_later, proxy)={r_pp:.10f} n={len(event_for_proxy)}")
        print(f"  Spearman rho(event n_later, proxy)={rho_pp:.10f} n={len(event_for_proxy)}")
    print(f"  n_proxy_negative={proxy_neg}")
    print("  ground_truth=event_log n_later (intervention events with step > branch step s)")
    print(f"  event_after_s vs stored n_later_reviews disagree={n_event_stored_disagree} / {len(later_ok)}")
    print(f"  event_after_s vs all live_policy (no step filter) disagree={n_event_live_disagree} / {len(later_ok)}")
    print(f"  event_after_s vs live_policy AND step>s disagree={n_event_live_after_disagree} / {len(later_ok)}")

    # arrays aligned to keys, nan where incomplete logs
    n_later_arr = np.full(len(keys), np.nan, dtype=np.float64)
    step_arr = np.full(len(keys), np.nan, dtype=np.float64)
    full_mask = np.zeros(len(keys), dtype=bool)
    for p, nl in n_later_by_point.items():
        i = key_index[p]
        n_later_arr[i] = nl["n_later"]
        step_arr[i] = float(comp[p][("untreated", SEEDS[0])]["step"])
        full_mask[i] = True

    n0_mask = full_mask & (n_later_arr == 0.0)
    print()
    print("*" * 78)
    print(f"[{name} n_later=0 SUBSET SIZE] n={int(n0_mask.sum())} / complete={len(keys)} / with_logs={n_full_points}")
    print("*" * 78)

    # Spearman n_later vs Δ
    x = n_later_arr[full_mask]
    y = delta_obs[full_mask]
    rho = spearman_rho(x, y)
    scipy_pair, scipy_how = try_scipy_spearman(x, y)
    perm_s = perm_spearman_p(x, y, rng_spear, SPEARMAN_N_PERM)
    print(f"[SPEARMAN n_later vs Δ] {name} n={int(full_mask.sum())}")
    print(f"  rho_average_ranks={rho:.10f}")
    print(
        f"  perm_two_sided p=n(|rho_perm|>=|obs|)/{SPEARMAN_N_PERM} "
        f"seed={SPEARMAN_PERM_SEED} p={perm_s['p_two_sided']:.6f} "
        f"({perm_s['n_abs_ge']}/{perm_s['n_perm']})"
    )
    if scipy_pair is not None:
        print(f"  {scipy_how} rho={scipy_pair[0]:.10f} p={scipy_pair[1]:.10g}")
    else:
        print(f"  scipy not used ({scipy_how})")

    # dose-response
    bucket_ids = np.array([bucket_of(v) if not math.isnan(v) else "NA" for v in n_later_arr])
    present_buckets = [b for b in BUCKET_ORDER if np.any(full_mask & (bucket_ids == b))]
    extra = sorted(set(bucket_ids[full_mask]) - set(BUCKET_ORDER) - {"NA"})
    buckets = present_buckets + extra
    print(f"[BUCKETS PRESENT] {buckets}")

    delta_by_bucket = {}
    meta_by_bucket = {}
    for b in buckets:
        m = full_mask & (bucket_ids == b)
        delta_by_bucket[b] = delta_obs[m]
        n_b = int(m.sum())
        n_ceil = int((m & masks["ceiling"]).sum())
        n_floor = int((m & masks["floor"]).sum())
        meta_by_bucket[b] = {
            "n": n_b,
            "mean_step": float(step_arr[m].mean()) if n_b else float("nan"),
            "mean_u": float(mean_u[m].mean()) if n_b else float("nan"),
            "n_ceil": n_ceil,
            "n_floor": n_floor,
            "ceil_frac": (n_ceil / n_b) if n_b else float("nan"),
            "floor_frac": (n_floor / n_b) if n_b else float("nan"),
        }

    for dth in DELTAS:
        print_dose_table(f"{name} ALL-COMPLETE", buckets, delta_by_bucket, dth)

    print_confound_table(f"{name} ALL-COMPLETE", buckets, meta_by_bucket)

    # contestable post-hoc
    c_delta_by_bucket = {}
    c_meta_by_bucket = {}
    c_present = []
    for b in buckets:
        m = full_mask & masks["contestable"] & (bucket_ids == b)
        if int(m.sum()) == 0 and b not in c_present:
            c_delta_by_bucket[b] = delta_obs[m]
            c_meta_by_bucket[b] = {
                "n": 0,
                "mean_step": float("nan"),
                "mean_u": float("nan"),
                "n_ceil": 0,
                "n_floor": 0,
                "ceil_frac": float("nan"),
                "floor_frac": float("nan"),
            }
            continue
        c_present.append(b)
        c_delta_by_bucket[b] = delta_obs[m]
        n_b = int(m.sum())
        c_meta_by_bucket[b] = {
            "n": n_b,
            "mean_step": float(step_arr[m].mean()) if n_b else float("nan"),
            "mean_u": float(mean_u[m].mean()) if n_b else float("nan"),
            "n_ceil": 0,
            "n_floor": 0,
            "ceil_frac": 0.0,
            "floor_frac": 0.0,
        }
    print("[CONTESTABLE DOSE-RESPONSE IS POST-HOC — W-20 non-ceiling non-floor on observed means]")
    for dth in DELTAS:
        print_dose_table(f"{name} CONTESTABLE POST-HOC", buckets, c_delta_by_bucket, dth)
    print_confound_table(f"{name} CONTESTABLE POST-HOC", buckets, c_meta_by_bucket)

    perm = run_perm_on_mask(
        f"{name} n_later=0 ALL-COMPLETE",
        diffs,
        n0_mask,
        mean_t,
        mean_u,
        rng_perm,
    )
    n0_cont = n0_mask & masks["contestable"]
    print(f"[{name} n_later=0 CONTESTABLE SUBSET SIZE] n={int(n0_cont.sum())} (post-hoc)")
    perm_c = run_perm_on_mask(
        f"{name} n_later=0 CONTESTABLE POST-HOC",
        diffs,
        n0_cont,
        mean_t,
        mean_u,
        rng_perm,
    )

    return {
        "name": name,
        "n_complete": len(keys),
        "n_full_logs": n_full_points,
        "n_later0": int(n0_mask.sum()),
        "n_later0_contestable": int(n0_cont.sum()),
        "scan": {k: scan[k] for k in ("n_expected", "n_opened", "n_missing", "n_unreadable")},
        "perm": perm,
        "perm_contestable": perm_c,
    }


def main():
    print("=== W-25 SUBSTITUTION TEST ===")
    print(f"python={sys.version.replace(chr(10), ' ')}")
    print(f"numpy={np.__version__}")
    print(f"PBS_JOBID={os.environ.get('PBS_JOBID', '')}")
    print(f"hostname={os.environ.get('HOSTNAME', '')}")
    print(f"PERM_SEED={PERM_SEED} N_PERM={N_PERM}")
    print(f"SPEARMAN_PERM_SEED={SPEARMAN_PERM_SEED} SPEARMAN_N_PERM={SPEARMAN_N_PERM}")
    print(f"SEEDS={list(SEEDS)}")
    print(f"DELTAS={list(DELTAS)}")
    print("n_later_event=count of event_type==intervention with step > branch step s")
    print("  on each untreated complete-point replicate; point n_later = median of 4")
    print("proxy=floor((branch_steps-s)/5); event log is ground truth")
    print("completeness=W-24/W-20: seeds 101-104, non-null branch_gpr, both conditions")
    print("null=paired sign-flip per (point, seed) with p=0.5; 10000 perms")
    print("f=needed/n  (never the needless fraction)")
    print("contestable=POST-HOC W-20 mask on observed means")

    rng_perm = np.random.default_rng(PERM_SEED)
    rng_spear = np.random.default_rng(SPEARMAN_PERM_SEED)
    train = run_split("TRAIN", TRAIN_PATH, rng_perm, rng_spear)
    dev = run_split("DEV", DEV_PATH, rng_perm, rng_spear)

    print()
    print("=" * 78)
    print("DONE")
    print(f"PERM_SEED={PERM_SEED} N_PERM={N_PERM}")
    print(
        f"train_complete={train['n_complete']} train_full_logs={train['n_full_logs']} "
        f"train_n_later0={train['n_later0']} train_n_later0_contestable={train['n_later0_contestable']}"
    )
    print(
        f"dev_complete={dev['n_complete']} dev_full_logs={dev['n_full_logs']} "
        f"dev_n_later0={dev['n_later0']} dev_n_later0_contestable={dev['n_later0_contestable']}"
    )
    print(
        f"train_logs opened={train['scan']['n_opened']} missing={train['scan']['n_missing']} "
        f"unreadable={train['scan']['n_unreadable']} expected={train['scan']['n_expected']}"
    )
    print(
        f"dev_logs opened={dev['scan']['n_opened']} missing={dev['scan']['n_missing']} "
        f"unreadable={dev['scan']['n_unreadable']} expected={dev['scan']['n_expected']}"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
