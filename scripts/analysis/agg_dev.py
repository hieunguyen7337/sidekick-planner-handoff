"""Aggregate J6 dev branches with the repo's OWN rebuild_derived.

Runs entirely off branch_runs.jsonl in a STAGING copy, so the live campaign
tree is never touched while a job may still resume into it.

Two passes:
  A. delta_band=None  -> confirms labels come out label_status=incomplete
  B. delta_band computed from train's partial branch_runs by the repo's own
     compute_delta_band -> the preliminary Gate B read
"""

import json
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
sys.path.insert(0, str(REPO / "scripts" / "setup"))
sys.path.insert(0, str(REPO / "src"))

import branch_counterfactual as bc  # noqa: E402

DEV = Path("/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917")
TRAIN = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917")
STAGE = Path("/home/n12194778/.claude/jobs/91578989/tmp/agg_dev")
SEEDS = [101, 102]


def stage(src: Path, name: str) -> Path:
    d = STAGE / name
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "branch_runs.jsonl", d / "branch_runs.jsonl")
    return d


def summarise(tag: str, out: Path, band):
    rows = [json.loads(x) for x in (out / "branches.jsonl").read_text().splitlines() if x.strip()]
    st = Counter(r.get("label_status") for r in rows)
    lab = Counter()
    for r in rows:
        if r.get("label_status") != "complete":
            continue
        if r.get("needed"):
            lab["needed"] += 1
        elif r.get("needless"):
            lab["needless"] += 1
        elif r.get("ambiguous"):
            lab["ambiguous"] += 1
    n_complete = sum(lab.values())
    print(f"\n===== {tag} =====")
    print(f"delta_band          : {band}")
    print(f"points in branches  : {len(rows)}")
    print(f"label_status        : {dict(st)}")
    if n_complete:
        for k in ("needed", "needless", "ambiguous"):
            print(f"  {k:<10}: {lab[k]:>4}  f={lab[k]/n_complete:.4f}")
        print(f"  n_complete: {n_complete}   1-f(needed) = {1 - lab['needed']/n_complete:.4f}")
    man = json.loads((out / "manifest.json").read_text())
    for k in ("n_points", "n_complete", "n_needed", "n_needless", "n_ambiguous",
              "n_incomplete", "delta_band", "delta_band_delta",
              "fraction_factual_outside_treated_range"):
        if k in man:
            print(f"manifest.{k} = {man[k]}")
    return rows


def main():
    dev = stage(DEV, "dev")
    tr = stage(TRAIN, "train")

    n_dev = sum(1 for _ in (dev / "branch_runs.jsonl").open())
    n_tr = sum(1 for _ in (tr / "branch_runs.jsonl").open())
    print(f"staged dev branch_runs = {n_dev}   train branch_runs = {n_tr}")

    # --- delta band from train, by the repo's own rule, on partial train data
    tr_rows = bc.load_jsonl(tr / "branch_runs.jsonl")
    _, tr_samples = bc.group_branch_samples(tr_rows)
    band = bc.compute_delta_band(bc.treated_pairs_from_samples(tr_samples, SEEDS))
    print(f"\ncompute_delta_band(train partial, seeds={SEEDS}) = {band}")

    # --- pass A: no band (what the job itself would have written)
    b = bc.rebuild_derived(dev, SEEDS, DEV, "dev", "sft_b", delta_band=None)
    summarise("A. dev, delta_band=None (job's own behaviour)", dev, b)

    # --- pass B: train band applied to dev == the pre-registered rule
    dev2 = stage(DEV, "dev_banded")
    b2 = bc.rebuild_derived(dev2, SEEDS, DEV, "dev", "sft_b", delta_band=band)
    rows = summarise("B. dev, delta_band from train (PRELIMINARY Gate B)", dev2, b2)

    # --- extra: mean delta by label, and the factual-in-range validation
    import statistics as st
    buckets = {"needed": [], "needless": [], "ambiguous": []}
    deltas = []
    outside = 0
    scored = 0
    for r in rows:
        if r.get("label_status") != "complete":
            continue
        d = r.get("delta")
        if d is None:
            continue
        deltas.append(d)
        if r.get("needed"):
            buckets["needed"].append(d)
        elif r.get("needless"):
            buckets["needless"].append(d)
        else:
            buckets["ambiguous"].append(d)
        tg = r.get("treated_gpr") or []
        a = r.get("actual_gpr")
        if tg and a is not None:
            scored += 1
            if a < min(tg) or a > max(tg):
                outside += 1
    print(f"\nmean delta (all complete) = {st.mean(deltas):+.4f}  n={len(deltas)}")
    for k, v in buckets.items():
        if v:
            print(f"  mean delta [{k:<9}] = {st.mean(v):+.4f}  n={len(v)}")
    if scored:
        print(f"factual outside treated range = {outside}/{scored} = {outside/scored:.4f}")

    # oracle allocation: fire only where needed
    oracle = st.mean([max(d, 0.0) if r.get("needed") else 0.0
                      for r, d in zip([x for x in rows if x.get("label_status") == "complete"], deltas)])
    print(f"oracle allocation mean gain/point = {oracle:+.4f} "
          f"(vs always-on {st.mean(deltas):+.4f}); calls saved = "
          f"{1 - len(buckets['needed'])/len(deltas):.4f}")


if __name__ == "__main__":
    main()
