#!/usr/bin/env python3
"""A9b: J7 AUROC floor/ceiling analysis. Read-only on /scratch results.

Does not refit, does not write a verifier artifact, does not touch src/.
Run from repo root inside a PBS job:
  PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python \\
    campaign/workers/scratch_A9b/a9_ceiling.py
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
import traceback
from collections import defaultdict
from pathlib import Path

print("START a9_ceiling", flush=True)
print("executable", sys.executable, flush=True)
print("argv", sys.argv, flush=True)

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "setup"))
sys.path.insert(0, str(REPO))

from sidekick.agents.verifier import FeatureVerifier, feature_spec  # noqa: E402
from fit_feature_verifier import (  # noqa: E402
    auroc,
    build_xy,
    join_episode_features,
    prepare_dataset,
    read_rows,
    standardize_fit,
    apply_standardize,
)

TRAIN_BRANCHES = Path(
    "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branches.jsonl"
)
DEV_BRANCHES = Path(
    "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branches.jsonl"
)
TRAIN_CAMPAIGN = Path("/scratch/n12194778/sidekick/results/hj4_correction_train_20260917")
DEV_CAMPAIGN = Path("/scratch/n12194778/sidekick/results/hj4b_fixed_k_dev_20260917")
WEIGHTS = REPO / "artifacts/verifiers/feature_lr_20260918/weights.json"
METRICS = REPO / "artifacts/verifiers/feature_lr_20260918/metrics.json"
OUT_JSON = REPO / "campaign/workers/scratch_A9b/a9_ceiling_out.json"

SEEDS = (101, 102, 103, 104)
HALF_SPLITS = (
    ((0, 1), (2, 3)),  # {101,102} vs {103,104}
    ((0, 2), (1, 3)),  # {101,103} vs {102,104}
    ((0, 3), (1, 2)),  # {101,104} vs {102,103}
)
N_BOOT = 10_000
BOOT_SEED = 20260918
MC_SEED = 20260919
N_MC = 200_000
# Reliability figures from RUNS.md (recomputed below; these are the ledger values).
LEDGER_RHO_1 = 0.1697
LEDGER_RHO_2 = 0.2902
LEDGER_RHO_4 = 0.4504
LEDGER_AUROC = 0.5916711736073553

report: dict = {"ok": False, "stage": "init"}


def dump() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-15 or dy < 1e-15:
        return None
    return num / (dx * dy)


def percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    # NumPy default linear interpolation on [0, 100].
    n = len(sorted_vals)
    pos = (p / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    lo = min(max(lo, 0), n - 1)
    hi = min(max(hi, 0), n - 1)
    w = pos - lo
    return float(sorted_vals[lo] * (1.0 - w) + sorted_vals[hi] * w)


def bootstrap_auroc(
    y: list[int],
    scores: list[float],
    *,
    n_boot: int,
    seed: int,
    groups: list[str] | None = None,
) -> dict:
    rng = random.Random(seed)
    n = len(y)
    stats: list[float] = []
    skipped = 0
    if groups is None:
        for _ in range(n_boot):
            idx = [rng.randrange(n) for _ in range(n)]
            yy = [y[i] for i in idx]
            ss = [scores[i] for i in idx]
            if len(set(yy)) < 2:
                skipped += 1
                continue
            stats.append(auroc(yy, ss))
    else:
        buckets: dict[str, list[int]] = defaultdict(list)
        for i, g in enumerate(groups):
            buckets[str(g)].append(i)
        names = list(buckets)
        for _ in range(n_boot):
            draw = [rng.choice(names) for _ in names]
            yy: list[int] = []
            ss: list[float] = []
            for g in draw:
                for i in buckets[g]:
                    yy.append(y[i])
                    ss.append(scores[i])
            if len(set(yy)) < 2:
                skipped += 1
                continue
            stats.append(auroc(yy, ss))
    stats.sort()
    point = auroc(y, scores)
    return {
        "auroc": point,
        "ci_low": percentile(stats, 2.5),
        "ci_high": percentile(stats, 97.5),
        "boot_mean": (sum(stats) / len(stats)) if stats else None,
        "boot_sd": statistics.pstdev(stats) if len(stats) > 1 else None,
        "n_boot": n_boot,
        "n_valid": len(stats),
        "n_skipped_single_class": skipped,
        "seed": seed,
    }


def group_prior_auroc(
    train_rows: list[dict],
    dev_rows: list[dict],
    key_fn,
) -> dict:
    by: dict[object, list[int]] = defaultdict(list)
    for r in train_rows:
        by[key_fn(r)].append(1 if r["needed"] else 0)
    prior = {k: (sum(v) / len(v)) for k, v in by.items() if v}
    global_prior = sum(1 if r["needed"] else 0 for r in train_rows) / len(train_rows)
    scores = [prior.get(key_fn(r), global_prior) for r in dev_rows]
    labels = [1 if r["needed"] else 0 for r in dev_rows]
    return {
        "auroc": auroc(labels, scores) if len(set(labels)) >= 2 else None,
        "n_keys_train": len(prior),
        "global_prior": global_prior,
    }


def knn_auroc(
    Xtr: list[list[float]],
    ytr: list[int],
    tasks_tr: list[str],
    Xdev: list[list[float]],
    ydev: list[int],
    tasks_dev: list[str],
    k: int,
) -> dict:
    refs = [(Xtr[i], ytr[i], tasks_tr[i]) for i in range(len(Xtr)) if ytr[i] in (0, 1)]
    n_pos = sum(1 for _, t, _ in refs if t == 1)
    n_neg = len(refs) - n_pos
    scores: list[float] = []
    labels: list[int] = []
    n_short = 0
    for x, t, yv in zip(Xdev, tasks_dev, ydev):
        dists = []
        for xr, yr, tr in refs:
            if tr == t:
                continue
            d = sum((a - b) ** 2 for a, b in zip(x, xr))
            dists.append((d, yr))
        dists.sort(key=lambda p: p[0])
        top = dists[:k]
        if not top:
            n_short += 1
            continue
        if len(top) < k:
            n_short += 1
        scores.append(sum(tt for _, tt in top) / len(top))
        labels.append(yv)
    out = {
        "k": k,
        "n_refs": len(refs),
        "n_pos_ref": n_pos,
        "n_neg_ref": n_neg,
        "n_scored": len(scores),
        "n_short_neighbourhood": n_short,
        "auroc": None,
    }
    if scores and len(set(labels)) >= 2:
        out["auroc"] = auroc(labels, scores)
    return out


def gpr_ok(v: object) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def half_delta(row: dict, idxs: tuple[int, ...]) -> float | None:
    t = row.get("treated_gpr") or []
    u = row.get("untreated_gpr") or []
    diffs: list[float] = []
    for i in idxs:
        if i >= len(t) or i >= len(u):
            return None
        if not gpr_ok(t[i]) or not gpr_ok(u[i]):
            return None
        diffs.append(float(t[i]) - float(u[i]))
    if not diffs:
        return None
    return sum(diffs) / len(diffs)


def four_delta(row: dict) -> float | None:
    return half_delta(row, (0, 1, 2, 3))


def label_from_delta(delta: float, band: float) -> str:
    if delta > band:
        return "needed"
    if delta < -band:
        return "needless"
    return "ambiguous"


def complete_four(row: dict) -> bool:
    t = row.get("treated_gpr") or []
    u = row.get("untreated_gpr") or []
    if len(t) < 4 or len(u) < 4:
        return False
    return all(gpr_ok(t[i]) and gpr_ok(u[i]) for i in range(4))


def gaussian_ceiling(mu: float, sigma: float, rho: float, band: float, n: int, seed: int) -> dict:
    """AUROC of latent θ vs band-thresholded noisy Δ. corr(θ, Δ)=√ρ by construction."""
    if sigma <= 0 or not (0.0 < rho < 1.0):
        return {"error": f"bad sigma/rho sigma={sigma} rho={rho}"}
    rng = random.Random(seed)
    sd_theta = sigma * math.sqrt(rho)
    sd_eps = sigma * math.sqrt(1.0 - rho)
    scores: list[float] = []
    labels: list[int] = []
    all_t: list[float] = []
    all_d: list[float] = []
    kept_delta: list[float] = []
    n_needed = 0
    for _ in range(n):
        theta = rng.gauss(mu, sd_theta)
        eps = rng.gauss(0.0, sd_eps)
        delta = theta + eps
        all_t.append(theta)
        all_d.append(delta)
        if abs(delta) <= band:
            continue
        lab = 1 if delta > band else 0
        n_needed += lab
        scores.append(theta)
        labels.append(lab)
        kept_delta.append(delta)
    n_kept = len(scores)
    r_all = pearson(all_t, all_d)
    return_r_kept = pearson(scores, kept_delta)
    auc = auroc(labels, scores) if scores and len(set(labels)) >= 2 else None
    return {
        "rho": rho,
        "sqrt_rho": math.sqrt(rho),
        "rcn_misapplied_0_5_1_plus_sqrt_rho": 0.5 * (1.0 + math.sqrt(rho)),
        "mu": mu,
        "sigma": sigma,
        "band": band,
        "n_mc": n,
        "n_kept_tail": n_kept,
        "kept_positive_rate": (n_needed / n_kept) if n_kept else None,
        "corr_theta_delta_all": r_all,
        "corr_theta_delta_tail": return_r_kept,
        "auroc_theta_vs_tail_labels": auc,
        "seed": seed,
    }


def main() -> int:
    global report
    report = {"ok": False, "stage": "load"}
    dump()
    print("loading metrics/weights/branches", flush=True)
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    weights_raw = json.loads(WEIGHTS.read_text(encoding="utf-8"))
    verifier = FeatureVerifier(
        weights={c: float(v) for c, v in weights_raw["weights"].items()},
        intercept=float(weights_raw["intercept"]),
        temperature=float(weights_raw["temperature"]),
        spec=feature_spec(),
    )
    train_raw = read_rows(TRAIN_BRANCHES)
    dev_raw = read_rows(DEV_BRANCHES)
    report["n_rows"] = {"train": len(train_raw), "dev": len(dev_raw)}
    bands_raw = sorted({
        float(r["delta_band_delta"])
        for r in (train_raw + dev_raw)
        if r.get("delta_band_delta") is not None
    })
    bands = sorted({round(x, 6) for x in bands_raw})
    report["delta_band_values_raw"] = bands_raw
    report["delta_band_values_rounded_6dp"] = bands
    if len(bands) != 1:
        raise RuntimeError(
            f"expected one frozen delta band, got raw={bands_raw} rounded={bands}"
        )
    band = bands[0]
    report["delta_band"] = band
    dump()

    report["stage"] = "filter_join"
    train_kept, train_filt = prepare_dataset(train_raw)
    dev_kept, dev_filt = prepare_dataset(dev_raw)
    report["filter"] = {"train": train_filt, "dev": dev_filt}
    train_joined, train_join = join_episode_features(
        train_kept, TRAIN_CAMPAIGN, split="train"
    )
    dev_joined, dev_join = join_episode_features(dev_kept, DEV_CAMPAIGN, split="dev")
    report["join"] = {"train": train_join, "dev": dev_join}
    dump()
    print(
        "kept/joined",
        train_filt["n_kept_for_fit"],
        train_join["n_joined"],
        dev_filt["n_kept_for_fit"],
        dev_join["n_joined"],
        flush=True,
    )

    y_dev = [1 if r["needed"] else 0 for r in dev_joined]
    y_tr = [1 if r["needed"] else 0 for r in train_joined]
    scores_dev = [verifier.score(r) for r in dev_joined]
    scores_tr = [verifier.score(r) for r in train_joined]
    art_dev = float(metrics["dev"]["auroc_all_states"])
    art_tr = float(metrics["train"]["auroc_all_states"])
    got_dev = auroc(y_dev, scores_dev)
    got_tr = auroc(y_tr, scores_tr)
    report["artifact"] = {
        "dev_auroc": art_dev,
        "train_auroc": art_tr,
        "dev_n": metrics["dev"]["n"],
        "train_n": metrics["train"]["n"],
        "temperature": metrics["temperature"],
        "dev_brier": metrics["dev"]["brier"],
        "dev_ece": metrics["dev"]["ece"],
    }
    report["reproduced"] = {
        "dev_auroc": got_dev,
        "train_auroc": got_tr,
        "dev_n": len(dev_joined),
        "train_n": len(train_joined),
        "dev_n_pos": sum(y_dev),
        "train_n_pos": sum(y_tr),
        "dev_match_artifact": abs(got_dev - art_dev) < 1e-12,
        "abs_dev_diff": abs(got_dev - art_dev),
        "ledger_brief_0_59_abs_diff": abs(got_dev - 0.59),
    }
    print("reproduced dev AUROC", got_dev, "artifact", art_dev, "match",
          report["reproduced"]["dev_match_artifact"], flush=True)

    report["stage"] = "bootstrap"
    dump()
    tasks_dev = [str(r["task_id"]) for r in dev_joined]
    report["bootstrap_point"] = bootstrap_auroc(
        y_dev, scores_dev, n_boot=N_BOOT, seed=BOOT_SEED, groups=None
    )
    report["bootstrap_task"] = bootstrap_auroc(
        y_dev, scores_dev, n_boot=N_BOOT, seed=BOOT_SEED, groups=tasks_dev
    )
    report["n_dev_tasks"] = len(set(tasks_dev))
    print("bootstrap point", report["bootstrap_point"], flush=True)
    print("bootstrap task", report["bootstrap_task"], flush=True)

    report["stage"] = "floors"
    dump()
    Xtr_raw, _ = build_xy(train_joined)
    Xdev_raw, _ = build_xy(dev_joined)
    means, stds = standardize_fit(Xtr_raw)
    Xtr = apply_standardize(Xtr_raw, means, stds)
    Xdev = apply_standardize(Xdev_raw, means, stds)
    columns = feature_spec()["columns"]
    tasks_tr = [str(r["task_id"]) for r in train_joined]

    floors = {
        "constant_0_5": 0.5,
        "step_prior": group_prior_auroc(
            train_joined, dev_joined, lambda r: int(r["step"])
        ),
        "n_interventions_prior": group_prior_auroc(
            train_joined, dev_joined, lambda r: int(r.get("n_interventions") or 0)
        ),
        "univariate_step": auroc(y_dev, [float(r["step"]) for r in dev_joined]),
        "univariate_n_interventions": auroc(
            y_dev, [float(r.get("n_interventions") or 0) for r in dev_joined]
        ),
        "univariate_transcript_chars": auroc(
            y_dev, [float(len(str(r.get("transcript") or ""))) for r in dev_joined]
        ),
        "train_class_prior_constant_score": auroc(
            y_dev, [sum(y_tr) / len(y_tr)] * len(y_dev)
        ),
    }
    report["floors"] = floors
    print("floors", json.dumps(floors, default=str), flush=True)

    report["stage"] = "knn"
    dump()
    knn = {
        "k3": knn_auroc(Xtr, y_tr, tasks_tr, Xdev, y_dev, tasks_dev, k=3),
        "k5": knn_auroc(Xtr, y_tr, tasks_tr, Xdev, y_dev, tasks_dev, k=5),
        "k9": knn_auroc(Xtr, y_tr, tasks_tr, Xdev, y_dev, tasks_dev, k=9),
    }
    report["knn_train_to_dev"] = knn
    print("knn", json.dumps(knn, default=str), flush=True)

    # Pooled leave-one-task-out k-NN as a small-n sensitivity (proxy, not bound).
    Xall = Xtr + Xdev
    yall = y_tr + y_dev
    tall = tasks_tr + tasks_dev
    # Standardize on pooled rows for this sensitivity only; labelled as such.
    m_all, s_all = standardize_fit(Xtr_raw + Xdev_raw)
    Xp = apply_standardize(Xtr_raw + Xdev_raw, m_all, s_all)
    knn_loto = knn_auroc(Xp, yall, tall, Xp, yall, tall, k=5)
    report["knn_pooled_loto_k5"] = knn_loto
    print("knn loto", knn_loto, flush=True)

    report["stage"] = "label_noise"
    dump()
    # 4-complete rows (all points, not just J7 kept).
    def summarise_split(rows: list[dict], tag: str) -> dict:
        complete = [r for r in rows if complete_four(r)]
        deltas4 = []
        for r in complete:
            d = four_delta(r)
            if d is not None:
                deltas4.append(d)
        mu = sum(deltas4) / len(deltas4) if deltas4 else None
        sigma = statistics.pstdev(deltas4) if len(deltas4) > 1 else None
        sigma_s = statistics.stdev(deltas4) if len(deltas4) > 1 else None
        split_rows = []
        for a_idx, b_idx in HALF_SPLITS:
            xs, ys = [], []
            n_both_polar = 0
            n_agree_polar = 0
            n_flip = 0
            scores_b: list[float] = []
            labels_b: list[int] = []
            scores_b_j7: list[float] = []
            labels_b_j7: list[int] = []
            for r in complete:
                da = half_delta(r, a_idx)
                db = half_delta(r, b_idx)
                if da is None or db is None:
                    continue
                xs.append(da)
                ys.append(db)
                la = label_from_delta(da, band)
                lb = label_from_delta(db, band)
                if la != "ambiguous" and lb != "ambiguous":
                    n_both_polar += 1
                    if la == lb:
                        n_agree_polar += 1
                    else:
                        n_flip += 1
                if lb != "ambiguous":
                    scores_b.append(da)
                    labels_b.append(1 if lb == "needed" else 0)
                    # J7 kept = 4-rep non-ambiguous (the row itself is in prepare_dataset
                    # kept set if we mark it). Use the file's own needed/ambiguous flags
                    # which are 4-rep labels.
                    if r.get("ambiguous") is False and r.get("label_status") == "complete":
                        scores_b_j7.append(da)
                        labels_b_j7.append(1 if lb == "needed" else 0)
            r_half = pearson(xs, ys)
            sb4 = (2 * r_half / (1 + r_half)) if (r_half is not None and r_half != -1) else None
            split_rows.append({
                "a_seeds": [SEEDS[i] for i in a_idx],
                "b_seeds": [SEEDS[i] for i in b_idx],
                "n_complete_with_both_halves": len(xs),
                "r_half_means": r_half,
                "spearman_brown_4": sb4,
                "n_both_halves_polar": n_both_polar,
                "n_polar_agree": n_agree_polar,
                "n_polar_flip": n_flip,
                "polar_agreement": (n_agree_polar / n_both_polar) if n_both_polar else None,
                "auroc_deltaA_vs_labelsB_all_polar_B": (
                    auroc(labels_b, scores_b) if labels_b and len(set(labels_b)) >= 2 else None
                ),
                "n_polar_B": len(labels_b),
                "n_pos_B": sum(labels_b),
                "auroc_deltaA_vs_labelsB_on_j7_kept": (
                    auroc(labels_b_j7, scores_b_j7)
                    if labels_b_j7 and len(set(labels_b_j7)) >= 2 else None
                ),
                "n_j7_kept_scored": len(labels_b_j7),
                "n_pos_j7_kept_B": sum(labels_b_j7),
            })
        sb_vals = [s["spearman_brown_4"] for s in split_rows if s["spearman_brown_4"] is not None]
        auc_all = [
            s["auroc_deltaA_vs_labelsB_all_polar_B"]
            for s in split_rows
            if s["auroc_deltaA_vs_labelsB_all_polar_B"] is not None
        ]
        auc_j7 = [
            s["auroc_deltaA_vs_labelsB_on_j7_kept"]
            for s in split_rows
            if s["auroc_deltaA_vs_labelsB_on_j7_kept"] is not None
        ]
        # Tautology check: 4-rep Δ vs 4-rep binary on J7 kept (must be 1.0).
        taut_s, taut_y = [], []
        n_complete = len(complete)
        n_complete_j7 = 0
        for r in complete:
            if r.get("ambiguous") is True or r.get("label_status") != "complete":
                continue
            d = four_delta(r)
            if d is None:
                continue
            n_complete_j7 += 1
            taut_s.append(d)
            taut_y.append(1 if r["needed"] else 0)
        taut = auroc(taut_y, taut_s) if taut_y and len(set(taut_y)) >= 2 else None
        # 2-seed (101,102) vs file 4-rep labels on J7 kept: polarity movement.
        n_same = 0
        n_flip2 = 0
        n_to_amb = 0
        n_from_other = 0
        for r in complete:
            d2 = half_delta(r, (0, 1))
            if d2 is None:
                continue
            lab2 = label_from_delta(d2, band)
            lab4 = "ambiguous" if r.get("ambiguous") else (
                "needed" if r.get("needed") else "needless"
            )
            if lab2 == lab4:
                n_same += 1
            elif lab2 != "ambiguous" and lab4 != "ambiguous" and lab2 != lab4:
                n_flip2 += 1
            elif lab4 != "ambiguous" and lab2 == "ambiguous":
                n_from_other += 1
            elif lab2 != "ambiguous" and lab4 == "ambiguous":
                n_to_amb += 1
        return {
            "tag": tag,
            "n_rows": len(rows),
            "n_complete_four": n_complete,
            "delta4_mean": mu,
            "delta4_pstdev": sigma,
            "delta4_stdev": sigma_s,
            "splits": split_rows,
            "mean_spearman_brown_4": (sum(sb_vals) / len(sb_vals)) if sb_vals else None,
            "mean_split_half_auroc_polar_B": (sum(auc_all) / len(auc_all)) if auc_all else None,
            "min_split_half_auroc_polar_B": min(auc_all) if auc_all else None,
            "max_split_half_auroc_polar_B": max(auc_all) if auc_all else None,
            "mean_split_half_auroc_j7_kept": (sum(auc_j7) / len(auc_j7)) if auc_j7 else None,
            "min_split_half_auroc_j7_kept": min(auc_j7) if auc_j7 else None,
            "max_split_half_auroc_j7_kept": max(auc_j7) if auc_j7 else None,
            "tautological_auroc_delta4_vs_j7_labels": taut,
            "n_tautology": len(taut_y),
            "n_pos_tautology": sum(taut_y),
            "label_move_2_vs_4_all_complete": {
                "n_same": n_same,
                "n_needed_needless_flip": n_flip2,
                "n_2polar_to_4ambiguous": n_to_amb,
                "n_2ambiguous_to_4polar": n_from_other,
            },
        }

    report["label_noise_dev"] = summarise_split(dev_raw, "dev")
    report["label_noise_train"] = summarise_split(train_raw, "train")
    print("label_noise_dev mean SB", report["label_noise_dev"]["mean_spearman_brown_4"],
          "mean split-half AUROC polar", report["label_noise_dev"]["mean_split_half_auroc_polar_B"],
          "j7 kept", report["label_noise_dev"]["mean_split_half_auroc_j7_kept"],
          flush=True)

    report["stage"] = "gaussian_mc"
    dump()
    mu = report["label_noise_dev"]["delta4_mean"]
    sigma = report["label_noise_dev"]["delta4_stdev"]
    mc = {}
    for name, rho in {
        "single_rep_ledger": LEDGER_RHO_1,
        "two_rep_ledger": LEDGER_RHO_2,
        "four_rep_ledger": LEDGER_RHO_4,
        "four_rep_recomputed": report["label_noise_dev"]["mean_spearman_brown_4"],
    }.items():
        if rho is None:
            continue
        mc[name] = gaussian_ceiling(mu, sigma, float(rho), band, N_MC, MC_SEED)
        print("mc", name, mc[name]["auroc_theta_vs_tail_labels"],
              "sqrt_rho", mc[name]["sqrt_rho"], flush=True)
    report["gaussian_mc_dev_params"] = mc
    # Point-biserial translation of √ρ (the other mistaken scale map).
    def pb_to_auroc(r: float) -> float | None:
        # r = d' / sqrt(d'^2 + 4) at p=0.5 => d'^2 = 4 r^2 / (1-r^2)
        if abs(r) >= 1:
            return None
        d2 = 4.0 * r * r / (1.0 - r * r)
        d = math.sqrt(d2)
        return phi(d / math.sqrt(2.0))

    report["scale_translations_at_rho_0_4504"] = {
        "sqrt_rho": math.sqrt(LEDGER_RHO_4),
        "rcn_0_5_1_plus_sqrt_rho": 0.5 * (1.0 + math.sqrt(LEDGER_RHO_4)),
        "point_biserial_sqrt_rho_to_binormal_auroc": pb_to_auroc(math.sqrt(LEDGER_RHO_4)),
        "gaussian_mc_auroc_theta_vs_tail": mc.get("four_rep_ledger", {}).get(
            "auroc_theta_vs_tail_labels"
        ),
    }

    report["stage"] = "fractions"
    dump()
    ceil_label = report["label_noise_dev"]["mean_split_half_auroc_polar_B"]
    ceil_label_j7 = report["label_noise_dev"]["mean_split_half_auroc_j7_kept"]
    ceil_knn = knn["k5"]["auroc"]
    floor_step = floors["step_prior"]["auroc"]
    floor_const = 0.5

    def frac(au: float | None, floor: float | None, ceil: float | None) -> dict:
        if au is None or floor is None or ceil is None:
            return {"error": "missing"}
        gap = ceil - floor
        return {
            "auroc": au,
            "floor": floor,
            "ceiling": ceil,
            "auroc_minus_floor": au - floor,
            "ceiling_minus_floor": gap,
            "fraction_of_gap": ((au - floor) / gap) if abs(gap) > 1e-12 else None,
            "fraction_of_ceiling_from_0_5": (
                (au - 0.5) / (ceil - 0.5) if abs(ceil - 0.5) > 1e-12 else None
            ),
        }

    ci_lo = report["bootstrap_point"]["ci_low"]
    ci_hi = report["bootstrap_point"]["ci_high"]
    report["restatement"] = {
        "j7_dev_auroc": got_dev,
        "j7_dev_auroc_ci_point_bootstrap": [ci_lo, ci_hi],
        "j7_dev_auroc_ci_task_bootstrap": [
            report["bootstrap_task"]["ci_low"],
            report["bootstrap_task"]["ci_high"],
        ],
        "vs_constant_floor_and_split_half_ceiling": frac(got_dev, floor_const, ceil_label),
        "vs_step_prior_floor_and_knn_k5_ceiling": frac(got_dev, floor_step, ceil_knn),
        "vs_constant_floor_and_knn_k5_ceiling": frac(got_dev, floor_const, ceil_knn),
        "vs_constant_floor_and_j7kept_split_half_ceiling": frac(
            got_dev, floor_const, ceil_label_j7
        ),
        "vs_constant_floor_and_mc_theta_ceiling": frac(
            got_dev,
            floor_const,
            mc.get("four_rep_ledger", {}).get("auroc_theta_vs_tail_labels"),
        ),
        "thresholds_named_not_chosen": {"prereg_v1": 0.70, "a9_w16_brief": 0.65},
        "ci_includes_0_50": bool(ci_lo is not None and ci_hi is not None and ci_lo <= 0.5 <= ci_hi),
        "ci_includes_0_65": bool(ci_lo is not None and ci_hi is not None and ci_lo <= 0.65 <= ci_hi),
        "ci_includes_0_70": bool(ci_lo is not None and ci_hi is not None and ci_lo <= 0.70 <= ci_hi),
        "point_below_0_65": got_dev < 0.65,
        "point_below_0_70": got_dev < 0.70,
    }
    report["discrepancies"] = {
        "prereg_0_70_vs_brief_0_65": "docs/prereg_v1.md:147 says >= 0.70; A9/W16 briefs say 0.65",
        "w16_ci_quoted": [0.4677, 0.7113],
        "w16_ci_is_inferred_in_w16_report": True,
        "artifact_vs_w16_point": "agree at 0.5916711736073553",
        "ledger_rho4": LEDGER_RHO_4,
        "recomputed_rho4_dev": report["label_noise_dev"]["mean_spearman_brown_4"],
    }
    report["ok"] = True
    report["stage"] = "done"
    dump()
    print("DONE", json.dumps(report["restatement"], default=str), flush=True)
    print("wrote", OUT_JSON, flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        report["ok"] = False
        report["error"] = traceback.format_exc()
        dump()
        traceback.print_exc()
        raise
