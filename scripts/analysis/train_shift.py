"""Train: does f drop because of better labels, or because of fewer points?

The 2-seed set gives needed 83 / 734 = 0.113. The 4-seed set gives 25 / 397 =
0.063. Two things changed at once -- replicate count AND point set -- so compare
both label rules on the SAME 397 points.
"""

import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

P = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl")
BAND = 0.166
ALL = [101, 102, 103, 104]

rows = [json.loads(x) for x in P.read_text().splitlines() if x.strip()]
pts = defaultdict(lambda: defaultdict(dict))
for r in rows:
    k = r.get("key")
    if not isinstance(k, str):
        continue
    pts["/".join(k.split("/")[:4])][r.get("condition")][r.get("branch_seed")] = r.get("branch_gpr")

four, two_only = {}, {}
for pk, cd in pts.items():
    t, u = cd.get("treated", {}), cd.get("untreated", {})
    has2 = all(t.get(s) is not None for s in (101, 102)) and all(u.get(s) is not None for s in (101, 102))
    has4 = all(t.get(s) is not None for s in ALL) and all(u.get(s) is not None for s in ALL)
    if not has2:
        continue
    d2 = st.mean([t[101], t[102]]) - st.mean([u[101], u[102]])
    if has4:
        four[pk] = (d2, st.mean([t[s] for s in ALL]) - st.mean([u[s] for s in ALL]))
    else:
        two_only[pk] = d2


def lab(d):
    return "needed" if d > BAND else ("needless" if d < -BAND else "ambiguous")


def tab(name, ds):
    c = Counter(lab(d) for d in ds)
    n = len(ds)
    print(f"  {name:<44} n={n:>4}  needed={c['needed']:>3} ({c['needed']/n:.4f})  "
          f"needless={c['needless']:>3}  ambiguous={c['ambiguous']:>3}  meanD={st.mean(ds):+.4f}")


print(f"points with a 2-seed delta        : {len(four)+len(two_only)}")
print(f"  of which complete on four seeds : {len(four)}")
print(f"  of which lost 103/104           : {len(two_only)}\n")

tab("ALL points, 2-seed rule (reported f=0.113)", [d2 for d2, _ in four.values()] + list(two_only.values()))
tab("SAME 397 points, 2-seed rule", [d2 for d2, _ in four.values()])
tab("SAME 397 points, 4-seed rule", [d4 for _, d4 in four.values()])
tab("the 337 dropped points, 2-seed rule", list(two_only.values()))

n4 = sum(1 for _, d4 in four.values() if lab(d4) == "needed")
n2same = sum(1 for d2, _ in four.values() if lab(d2) == "needed")
print(f"\n  on the same 397 points: needed goes {n2same} -> {n4} "
      f"({n2same/len(four):.4f} -> {n4/len(four):.4f}) purely from adding replicates")
flip = sum(1 for d2, d4 in four.values() if {lab(d2), lab(d4)} == {"needed", "needless"})
agree = sum(1 for d2, d4 in four.values() if lab(d2) == lab(d4))
print(f"  label agreement 2-seed vs 4-seed = {agree}/{len(four)} = {agree/len(four):.4f}; "
      f"needed<->needless flips = {flip}")
print(f"\n  extrapolating the 4-seed rate to all 777 points: "
      f"{n4/len(four)*777:.0f} needed (Gate B threshold is 75 positives)")
