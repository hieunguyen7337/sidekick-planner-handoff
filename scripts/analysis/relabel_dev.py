"""Relabel the dev campaign against the band frozen on train.

The dev x4 job ran before train's delta band was frozen, so it aggregated with
delta_band=None and every one of its 382 rows came back label_status=incomplete.
That is the pre-registered behaviour -- a label is never invented when the band
is unknown -- but it leaves J7 with no dev set to temperature-scale on.

This re-runs the repo's own rebuild_derived over the same branch_runs.jsonl with
the frozen band supplied. GPU-free: it reads branch_runs.jsonl and rewrites the
derived files only.

Run only when no J6 job is active against the dev tree.
"""

import argparse
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
sys.path.insert(0, str(REPO / "scripts" / "setup"))
sys.path.insert(0, str(REPO / "src"))

import branch_counterfactual as bc  # noqa: E402

DEV_OUT = Path("/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917")
DEV_CAMPAIGN = Path("/scratch/n12194778/sidekick/results/hj4b_fixed_k_dev_20260917")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta-band", type=float, required=True,
                    help="band frozen on train; the pre-registered rule, not a tuned value")
    ap.add_argument("--branch-seeds", type=int, nargs="+", default=[101, 102, 103, 104])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = bc.load_jsonl(DEV_OUT / "branch_runs.jsonl")
    print(f"branch_runs rows = {len(rows)}")
    print(f"branch seeds     = {args.branch_seeds}")
    print(f"delta band       = {args.delta_band}")

    if args.dry_run:
        print("dry run; nothing written")
        return

    band = bc.rebuild_derived(
        DEV_OUT, list(args.branch_seeds), DEV_CAMPAIGN, "dev", "sft_b",
        delta_band=args.delta_band,
    )
    print(f"rebuild_derived returned band = {band}")

    pr = [json.loads(x) for x in (DEV_OUT / "branches.jsonl").read_text().splitlines() if x.strip()]
    status = Counter(r.get("label_status") for r in pr)
    print(f"\nbranches.jsonl rows = {len(pr)}  label_status = {dict(status)}")

    lab = Counter()
    deltas = []
    for r in pr:
        if r.get("label_status") != "complete":
            continue
        if r.get("delta") is not None:
            deltas.append(r["delta"])
        if r.get("needed"):
            lab["needed"] += 1
        elif r.get("needless"):
            lab["needless"] += 1
        elif r.get("ambiguous"):
            lab["ambiguous"] += 1
    n = sum(lab.values())
    if not n:
        print("no complete points; nothing to report")
        return
    print(f"\n--- dev labels, {n} complete points ---")
    for k in ("needed", "needless", "ambiguous"):
        print(f"  {k:<10}: {lab[k]:>4}  f={lab[k]/n:.4f}")
    print(f"  1 - f(needed) = {1 - lab['needed']/n:.4f}")
    print(f"  mean delta    = {st.mean(deltas):+.4f}")

    oracle = json.loads((DEV_OUT / "oracle_labels.json").read_text())
    n_ep = len(oracle)
    n_steps = sum(len(v) for v in oracle.values()) if isinstance(oracle, dict) else 0
    print(f"\noracle_labels.json: {n_ep} episodes, {n_steps} needed steps")


if __name__ == "__main__":
    main()
