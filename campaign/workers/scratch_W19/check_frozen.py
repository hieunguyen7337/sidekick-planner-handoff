import json, math
from collections import defaultdict
path = "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl"
d = defaultdict(dict)
for line in open(path):
    r = json.loads(line)
    d["/".join(r["key"].split("/")[:4])][(r["condition"], r["branch_seed"])] = r["branch_gpr"]
vals = []
for p, dd in d.items():
    t, u = dd.get(("treated",101)), dd.get(("treated",102))
    if t is not None and u is not None:
        vals.append(abs(t-u))
vals.sort()
n = len(vals); idx = 0.75*(n-1); lo=int(idx)
print("n =", n, "p75 =", vals[lo])
