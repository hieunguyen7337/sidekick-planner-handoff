#!/usr/bin/env python
"""W-19 delta analysis. Read-only on /scratch. All numbers below are INFERRED
from this script unless tagged OBSERVED to a data path."""
import json, itertools, math, statistics as st
from collections import defaultdict

TRAIN = "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl"
DEV   = "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl"
FROZEN_DELTA = 0.166

def load(path):
    pts = defaultdict(dict)  # point -> (cond, seed) -> gpr
    n_null = 0
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            point = "/".join(r["key"].split("/")[:4])
            g = r["branch_gpr"]
            if g is None:
                n_null += 1
            pts[point][(r["condition"], r["branch_seed"])] = g
    return pts, n_null

def complete(pts, seeds=(101,102,103,104)):
    out = {}
    for p, d in pts.items():
        if all(d.get((c,s)) is not None for c in ("treated","untreated") for s in seeds):
            out[p] = d
    return out

def sd(vals):
    if len(vals) < 2: return 0.0
    m = sum(vals)/len(vals)
    return math.sqrt(sum((v-m)**2 for v in vals)/(len(vals)-1))

def pct(sorted_vals, q):
    n = len(sorted_vals)
    idx = q*(n-1)
    lo = int(math.floor(idx)); hi = min(lo+1, n-1)
    frac = idx - lo
    return sorted_vals[lo]*(1-frac) + sorted_vals[hi]*frac

def pearson(t, u):
    mt, mu = sum(t)/len(t), sum(u)/len(u)
    num = sum((a-mt)*(b-mu) for a,b in zip(t,u))
    return num / math.sqrt(sum((a-mt)**2 for a in t)*sum((b-mu)**2 for b in u))

def labels(vals, delta):
    D = sum(vals[0])/len(vals[0]) - sum(vals[1])/len(vals[1])
    if D > delta: return "needed", D
    if D < -delta: return "needless", D
    return "ambiguous", D

def label_grid(comp):
    print("[label grid]")
    grid = [0.02,0.04,0.06,0.08,0.083,0.10,0.117,0.12,0.14,0.166,0.18,0.20,0.22,0.25]
    for delta in grid:
        counts = {"needed":0,"needless":0,"ambiguous":0}
        for p, d in comp.items():
            t = [d[("treated",s)] for s in (101,102,103,104)]
            u = [d[("untreated",s)] for s in (101,102,103,104)]
            lab, _ = labels([t,u], delta)
            counts[lab] += 1
        n = sum(counts.values())
        f = counts["needless"]/n
        print(f"  delta={delta:.4f}: needed={counts['needed']} needless={counts['needless']} "
              f"ambiguous={counts['ambiguous']} f={f:.4f} 1-f={1-f:.4f}")

def stability(comp, deltas):
    for delta in deltas:
        agree = 0; n = 0
        for p, d in comp.items():
            labs = []
            for reps in [(101,102),(103,104)]:
                t = [d[("treated",s)] for s in reps]
                u = [d[("untreated",s)] for s in reps]
                labs.append(labels([t,u], delta)[0])
            n += 1
            agree += (labs[0] == labs[1])
        print(f"[stability delta={delta:.4f}] half-agreement={agree/n:.4f} (n={n})")


def report(path, name):
    pts, n_null = load(path)
    comp = complete(pts)
    print(f"\n===== {name} =====")
    print(f"[coverage] points={len(pts)} complete4={len(comp)} null_gpr_rows={n_null}")

    # 1. within-condition SD at each complete point
    sds = {"treated": [], "untreated": []}
    for p, d in comp.items():
        for c in sds:
            v = [d[(c,s)] for s in (101,102,103,104)]
            sds[c].append(sd(v))
    for c in sds:
        v = sorted(sds[c])
        print(f"[within-SD {c}] n={len(v)} median={st.median(v):.4f} "
              f"IQR=({pct(v,0.25):.4f},{pct(v,0.75):.4f}) p90={pct(v,0.9):.4f}")

    # 2. CRN correlation: per branch seed, corr(treated, untreated) across points
    rs = []
    for s in (101,102,103,104):
        t = [comp[p][("treated",s)] for p in comp]
        u = [comp[p][("untreated",s)] for p in comp]
        r = pearson(t, u)
        rs.append(r)
        print(f"[CRN corr seed {s}] r={r:.4f}")
    print(f"[CRN corr mean across seeds] {st.mean(rs):.4f}")

    # 3. null distribution: split 4 treated reps into two disjoint pairs
    null = []
    for pairing in [(0,1),(2,3)], [(0,2),(1,3)], [(0,3),(1,2)]:
        for p, d in comp.items():
            for c in ("treated","untreated"):
                v = [d[(c,s)] for s in (101,102,103,104)]
                a = (v[pairing[0][0]]+v[pairing[0][1]])/2
                b = (v[pairing[1][0]]+v[pairing[1][1]])/2
                null.append(abs(a-b))
    null.sort()
    d75 = pct(null, 0.75)
    print(f"[null |mean(pairA)-mean(pairB)|] n={len(null)} "
          f"p50={pct(null,0.5):.4f} p75={d75:.4f} p90={pct(null,0.9):.4f}")
    print(f"[derivation] null is diff of two 2-rep means: Var = s^2/2 + s^2/2 = s^2/2 -> SD = s/sqrt(2).")
    print(f"             4-rep Delta: Var = s^2/4 + s^2/4 = s^2/2 -> SD = s/sqrt(2). SAME scale -> no further adjustment.")

    # observed SD of Delta across replicate subsets (measure, not theory)
    for reps in [(101,102),(103,104),(101,102,103,104)]:
        Ds = []
        for p, d in comp.items():
            t = [d[("treated",s)] for s in reps]
            u = [d[("untreated",s)] for s in reps]
            Ds.append(sum(t)/len(t) - sum(u)/len(u))
        Ds_abs = sorted(abs(x) for x in Ds)
        print(f"[observed |Delta| reps={reps}] n={len(Ds)} mean_abs={st.mean(Ds_abs):.4f} "
              f"SD(D)={sd(Ds):.4f} p75_abs={pct(Ds_abs,0.75):.4f}")
    return comp, d75

tr, d75_tr = report(TRAIN, "TRAIN")
tr, d75_tr = report(TRAIN, "TRAIN")
dv, d75_dv = report(DEV, "DEV")

print("\n===== LABEL GRIDS =====")
print("-- TRAIN --"); label_grid(tr)
print("-- DEV --");   label_grid(dv)

print("\n===== STABILITY (half vs half) =====")
for name, comp, d75 in (("TRAIN", tr, d75_tr), ("DEV", dv, d75_dv)):
    print(f"-- {name} (derived delta={d75:.4f} vs frozen 0.166) --")
    stability(comp, sorted(set([d75, 0.166, 0.083])))
