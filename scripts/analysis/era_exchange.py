"""Are the era-3 replicate branches VALID, or silently degraded?

Crashes are one thing; a surviving branch whose outcome is wrong is worse. Under
common random numbers with identical configuration, branch seeds 101-104 are
exchangeable: for the same point and condition, the distribution of branch_gpr
should not depend on which seed it was.

101/102 ran in eras 1-2, 103/104 in era 3. If era 3 is contaminated, the
103/104 outcomes will differ systematically from 101/102 on the SAME points.

Paired test on points complete in all 8 cells, so composition cannot explain it.
"""

import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

SEEDS = [101, 102, 103, 104]


def run(name, path):
    rows = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    pts = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        k = r.get("key")
        if not isinstance(k, str):
            continue
        pk = "/".join(k.split("/")[:4])
        pts[pk][r.get("condition")][r.get("branch_seed")] = r.get("branch_gpr")

    old_t, new_t, old_u, new_u = [], [], [], []
    for pk, cd in pts.items():
        t, u = cd.get("treated", {}), cd.get("untreated", {})
        if any(t.get(s) is None for s in SEEDS) or any(u.get(s) is None for s in SEEDS):
            continue
        old_t.append(st.mean([t[101], t[102]]))
        new_t.append(st.mean([t[103], t[104]]))
        old_u.append(st.mean([u[101], u[102]]))
        new_u.append(st.mean([u[103], u[104]]))

    n = len(old_t)
    print(f"\n===== {name}: {n} points complete in all 8 cells =====")
    if n < 20:
        print("  too few points")
        return

    def paired(a, b, label):
        d = [x - y for x, y in zip(a, b)]
        m = st.mean(d)
        sd = st.pstdev(d)
        se = sd / math.sqrt(len(d)) if sd > 0 else 0.0
        t_ = m / se if se > 0 else 0.0
        print(f"  {label:<34} old={st.mean(a):.4f}  new={st.mean(b):.4f}  "
              f"diff={m:+.4f}  paired t={t_:+.2f}")
        return m, t_

    print("  (old = seeds 101/102, eras 1-2;  new = seeds 103/104, era 3)")
    paired(old_t, new_t, "treated branch_gpr")
    paired(old_u, new_u, "untreated branch_gpr")

    # the quantity that actually matters
    d_old = [a - b for a, b in zip(old_t, old_u)]
    d_new = [a - b for a, b in zip(new_t, new_u)]
    paired(d_old, d_new, "delta (treated - untreated)")

    # and the crash-free outcome distribution
    print(f"  fraction at ceiling 1.0:  old_untreated={sum(1 for x in old_u if x>=0.999)/n:.3f}  "
          f"new_untreated={sum(1 for x in new_u if x>=0.999)/n:.3f}")
    print(f"  fraction at floor 0.0:    old_untreated={sum(1 for x in old_u if x<=0.001)/n:.3f}  "
          f"new_untreated={sum(1 for x in new_u if x<=0.001)/n:.3f}")


def main():
    run("TRAIN", "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl")
    run("DEV", "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl")
    print("\nREADING: under CRN the seeds are exchangeable, so every diff above should")
    print("be near zero with |t| < 2. A systematic gap means era 3 is contaminated and")
    print("the four-seed labels are not simply the two-seed labels with less noise.")


if __name__ == "__main__":
    main()
