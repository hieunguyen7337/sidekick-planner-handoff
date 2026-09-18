"""Did four replicates actually lift label reliability?

Direct measurement, not extrapolation: split the four branch seeds into two
halves of two, correlate the half-means, and Spearman-Brown that correlation up
to the full four-replicate mean. Compare against the 0.440 predicted last night
from the two-seed data.
"""

import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

DEV = Path("/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917")
SEEDS = [101, 102, 103, 104]


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(rank(xs), rank(ys))


def sb(r, k):
    """Spearman-Brown: reliability of a k-fold mean given single-unit r."""
    return None if r is None else (k * r) / (1 + (k - 1) * r)


def main():
    rows = [json.loads(x) for x in (DEV / "branch_runs.jsonl").read_text().splitlines() if x.strip()]
    print(f"branch_runs rows = {len(rows)}")

    # point -> condition -> seed -> gpr
    pts = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        key = r.get("key")
        if isinstance(key, str):
            key = "/".join(key.split("/")[:4])
        cond = r.get("condition")
        bs = r.get("branch_seed")
        g = r.get("branch_gpr")
        if key is None or cond is None or bs not in SEEDS:
            continue
        pts[key][cond][bs] = g

    # keep points with all 8 cells present and non-null
    d = {}
    for key, cd in pts.items():
        t, u = cd.get("treated", {}), cd.get("untreated", {})
        if any(t.get(s) is None for s in SEEDS) or any(u.get(s) is None for s in SEEDS):
            continue
        d[key] = {s: t[s] - u[s] for s in SEEDS}
    print(f"points with all 4 seeds x 2 conditions complete = {len(d)}")
    if len(d) < 30:
        print("too few complete points; stopping")
        return

    keys = sorted(d)
    per = {s: [d[k][s] for k in keys] for s in SEEDS}

    # all six single-replicate pairwise correlations
    print("\n--- single-replicate pairwise correlations ---")
    rs = []
    for i in range(len(SEEDS)):
        for j in range(i + 1, len(SEEDS)):
            a, b = SEEDS[i], SEEDS[j]
            r = pearson(per[a], per[b])
            rs.append(r)
            print(f"  r({a},{b}) = {r:+.4f}")
    rbar = st.mean(rs)
    print(f"  mean single-replicate r = {rbar:+.4f}")
    print(f"  -> Spearman-Brown k=2 : {sb(rbar,2):.4f}   (last night, from 2 seeds: 0.282)")
    print(f"  -> Spearman-Brown k=4 : {sb(rbar,4):.4f}   (predicted last night: 0.440)")

    # DIRECT: correlate half-means, three distinct 2v2 splits
    print("\n--- DIRECT: 2-vs-2 half-mean correlation, then SB to k=4 ---")
    splits = [((101, 102), (103, 104)), ((101, 103), (102, 104)), ((101, 104), (102, 103))]
    rel4 = []
    for h1, h2 in splits:
        m1 = [st.mean([d[k][s] for s in h1]) for k in keys]
        m2 = [st.mean([d[k][s] for s in h2]) for k in keys]
        rh = pearson(m1, m2)
        r4 = sb(rh, 2)
        rel4.append(r4)
        print(f"  {h1} vs {h2}: r_halves={rh:+.4f}  -> reliability(4-mean)={r4:.4f}")
    print(f"  mean measured reliability of the 4-replicate mean = {st.mean(rel4):.4f}")
    print(f"  predicted last night                              = 0.4400")

    # Spearman version for robustness
    rho = st.mean([spearman(per[SEEDS[i]], per[SEEDS[j]])
                   for i in range(4) for j in range(i + 1, 4)])
    print(f"\n  mean single-replicate Spearman rho = {rho:+.4f}")

    # how much does the label set move between 2-seed and 4-seed means?
    band = 0.166
    lab2, lab4 = {}, {}
    for k in keys:
        d2 = st.mean([d[k][101], d[k][102]])
        d4 = st.mean([d[k][s] for s in SEEDS])
        lab2[k] = "needed" if d2 > band else ("needless" if d2 < -band else "ambiguous")
        lab4[k] = "needed" if d4 > band else ("needless" if d4 < -band else "ambiguous")
    from collections import Counter
    print(f"\n--- labels at band={band} on the SAME {len(keys)} points ---")
    print(f"  2-seed mean: {dict(Counter(lab2.values()))}")
    print(f"  4-seed mean: {dict(Counter(lab4.values()))}")
    agree = sum(1 for k in keys if lab2[k] == lab4[k])
    print(f"  label agreement 2-seed vs 4-seed = {agree}/{len(keys)} = {agree/len(keys):.4f}")
    flip = sum(1 for k in keys
               if {lab2[k], lab4[k]} == {"needed", "needless"})
    print(f"  outright needed<->needless flips = {flip}")


if __name__ == "__main__":
    main()
