"""Recover train's 2-seed aggregation into a STAGING dir.

The live tree's branches.jsonl was overwritten with an empty file by the x4
job's startup resume-rebuild, which requires all four seeds. branch_runs.jsonl
retains everything, so the 2-seed view rebuilds on CPU. The live tree is never
touched.
"""

import json
import shutil
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
sys.path.insert(0, str(REPO / "scripts" / "setup"))
sys.path.insert(0, str(REPO / "src"))

import branch_counterfactual as bc  # noqa: E402

TRAIN = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917")
STAGE = Path("/home/n12194778/.claude/jobs/91578989/tmp/agg_train")
SEEDS = [101, 102]


def coverage(rows):
    """How many train points have each seed-set complete, both conditions?"""
    pts = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        k = r.get("key")
        if not isinstance(k, str):
            continue
        pk = "/".join(k.split("/")[:4])
        pts[pk][r.get("condition")][r.get("branch_seed")] = r.get("branch_gpr")
    n2 = n4 = 0
    for pk, cd in pts.items():
        t, u = cd.get("treated", {}), cd.get("untreated", {})
        if all(t.get(s) is not None for s in (101, 102)) and all(u.get(s) is not None for s in (101, 102)):
            n2 += 1
        if all(t.get(s) is not None for s in (101, 102, 103, 104)) and all(u.get(s) is not None for s in (101, 102, 103, 104)):
            n4 += 1
    return len(pts), n2, n4


def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TRAIN / "branch_runs.jsonl", STAGE / "branch_runs.jsonl")

    rows = bc.load_jsonl(STAGE / "branch_runs.jsonl")
    n_pts, n2, n4 = coverage(rows)
    print(f"train branch_runs rows = {len(rows)}")
    print(f"train points seen      = {n_pts}")
    print(f"  complete on 101/102  = {n2}")
    print(f"  complete on all four = {n4}")

    band = bc.rebuild_derived(STAGE, SEEDS, TRAIN, "train", "sft_b",
                              delta_band=None, freeze_from_train=True)
    print(f"\nFROZEN delta band (train, seeds 101/102) = {band}")

    pr = [json.loads(x) for x in (STAGE / "branches.jsonl").read_text().splitlines() if x.strip()]
    stt = Counter(r.get("label_status") for r in pr)
    print(f"branches.jsonl rows = {len(pr)}   label_status = {dict(stt)}")

    lab = Counter()
    deltas = []
    for r in pr:
        if r.get("label_status") != "complete":
            continue
        d = r.get("delta")
        if d is not None:
            deltas.append(d)
        if r.get("needed"):
            lab["needed"] += 1
        elif r.get("needless"):
            lab["needless"] += 1
        elif r.get("ambiguous"):
            lab["ambiguous"] += 1
    n = sum(lab.values())
    print(f"\n--- GATE B (train), n_complete = {n} ---")
    for k in ("needed", "needless", "ambiguous"):
        print(f"  {k:<10}: {lab[k]:>4}  f={lab[k]/n:.4f}")
    print(f"  mean delta = {st.mean(deltas):+.4f}")
    print(f"\nGate B thresholds:")
    f = lab["needed"] / n
    print(f"  f_train < 0.10 (would need a 4th seed)?  f_train={f:.4f} -> {'FIRES' if f < 0.10 else 'does not fire'}")
    print(f"  n_needed = {lab['needed']} (threshold was <75 positives)")
    h = lab["needless"] / n
    print(f"  harmful > 0.15 (flag review format)?     harmful={h:.4f} -> {'FIRES' if h > 0.15 else 'does not fire'}")

    man = json.loads((STAGE / "manifest.json").read_text())
    for k in ("n_points", "n_complete", "n_needed", "n_needless", "n_ambiguous",
              "n_incomplete", "delta_band_delta"):
        if k in man:
            print(f"manifest.{k} = {man[k]}")
    fv = man.get("factual_vs_treated") or {}
    print(f"factual_vs_treated = {fv}")


if __name__ == "__main__":
    main()
