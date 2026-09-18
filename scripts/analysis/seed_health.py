"""Why do only 397 of 777 train points have all four seeds, when 734 have two?

All 6216 branch rows exist (777 x 4 seeds x 2 conditions), so nothing is
missing. The gap must be null branch_gpr. Check whether the replicate seeds
103/104 failed more often than the base pair, and why.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

for name, p in (
    ("train", "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl"),
    ("dev", "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl"),
):
    rows = [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
    print(f"\n===== {name}: {len(rows)} rows =====")
    tot = Counter()
    nullg = Counter()
    errs = defaultdict(Counter)
    for r in rows:
        s = r.get("branch_seed")
        tot[s] += 1
        if r.get("branch_gpr") is None:
            nullg[s] += 1
            errs[s][r.get("branch_error_type") or "(none recorded)"] += 1
    print(f"  {'seed':>6} {'rows':>6} {'null gpr':>9} {'null %':>8}")
    for s in sorted(tot):
        print(f"  {s:>6} {tot[s]:>6} {nullg[s]:>9} {100*nullg[s]/tot[s]:>7.2f}%")
    for s in sorted(errs):
        if errs[s]:
            top = ", ".join(f"{k}={v}" for k, v in errs[s].most_common(4))
            print(f"    seed {s} error types: {top}")
