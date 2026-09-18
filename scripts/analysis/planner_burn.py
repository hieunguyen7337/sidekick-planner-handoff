"""How many hosted-planner calls did J6 actually consume?

The plan's cost table lists J6 at 0 luna calls. But the branch definition was
amended on 2026-09-17 so that in BOTH arms "the reviewer stays live on its normal
5-step schedule afterwards, calling the planner on the branch's own state".
That amendment makes J6 planner-heavy; the cost table was never updated.

Sum n_planner_calls and planner token totals across every branch result.
"""

import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOTS = {
    "train": Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/fixed_k"),
    "dev": Path("/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/fixed_k"),
}

grand_calls = 0
grand_usd = 0.0
grand_tok = 0

for split, root in ROOTS.items():
    calls = 0
    usd = 0.0
    toks = 0
    n = 0
    per_branch = []
    by_status = Counter()
    for rj in root.glob("*/*/result.json"):
        try:
            d = json.loads(rj.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        n += 1
        c = d.get("n_planner_calls") or 0
        calls += c
        per_branch.append(c)
        by_status["crash" if d.get("error_type") == "crash" else "ok"] += 1
        tot = d.get("totals") or {}
        pa = (tot.get("per_actor") or {}).get("planner") or {}
        usd += float(pa.get("usd") or 0.0)
        toks += int(tot.get("planner_tokens_total") or 0)
    print(f"\n===== {split} =====")
    print(f"  branches with a result.json : {n}")
    print(f"  total planner calls         : {calls:,}")
    print(f"  mean per branch             : {st.mean(per_branch):.2f}" if per_branch else "")
    print(f"  planner tokens (sum)        : {toks:,}")
    print(f"  planner usd (reported)      : ${usd:,.2f}")
    print(f"  status                      : {dict(by_status)}")
    grand_calls += calls
    grand_usd += usd
    grand_tok += toks

print("\n########## J6 TOTAL ##########")
print(f"  hosted planner calls : {grand_calls:,}")
print(f"  planner tokens       : {grand_tok:,}")
print(f"  reported usd         : ${grand_usd:,.2f}")
print("  plan's budgeted luna calls for J6: 0")
print("\n  For scale, the plan budgets J8 at ~3,200 calls and J10 at ~11,500.")
