"""Are the points that survived on all four seeds a biased subset?

Seeds 103/104 crashed at ~40% on train and ~9% on dev. Crashes are recorded as
null and correctly dropped, so no number is fabricated -- but if crashing
correlates with episode character, then every four-seed statistic (the 0.4504
reliability, the 4-seed label counts) is computed on a non-random, probably
easier, subset.

Decisive test: compare the SAME 2-seed quantities between points that survived
on four seeds and points that did not. Two-seed delta is available for both, so
the comparison is apples to apples.
"""

import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

BAND = 0.166


def load(p):
    rows = [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
    pts = defaultdict(lambda: {"t": {}, "u": {}, "meta": None})
    for r in rows:
        k = r.get("key")
        if not isinstance(k, str):
            continue
        pk = "/".join(k.split("/")[:4])
        pts[pk]["t" if r.get("condition") == "treated" else "u"][r.get("branch_seed")] = r.get("branch_gpr")
        if pts[pk]["meta"] is None:
            pts[pk]["meta"] = r
    return pts


def describe(name, recs):
    if not recs:
        print(f"  {name:<28} n=0")
        return
    d = [r["d2"] for r in recs]
    harm = sum(1 for x in d if x < -BAND) / len(d)
    help_ = sum(1 for x in d if x > BAND) / len(d)
    steps = [r["step"] for r in recs if r["step"] is not None]
    untr = [r["u2"] for r in recs]
    ceil = sum(1 for u in untr if u >= 0.999) / len(untr)
    print(f"  {name:<28} n={len(recs):>4}  meanD={st.mean(d):+.4f}  "
          f"harm={harm:.3f} help={help_:.3f}  meanStep={st.mean(steps):5.1f}  "
          f"untreated={st.mean(untr):.3f}  ceiling={ceil:.3f}")


def main():
    for name, p in (
        ("TRAIN", "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl"),
        ("DEV", "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl"),
    ):
        pts = load(p)
        surv, lost = [], []
        for pk, v in pts.items():
            t, u = v["t"], v["u"]
            if any(t.get(s) is None for s in (101, 102)) or any(u.get(s) is None for s in (101, 102)):
                continue  # no 2-seed delta, cannot compare
            rec = {
                "d2": st.mean([t[101], t[102]]) - st.mean([u[101], u[102]]),
                "u2": st.mean([u[101], u[102]]),
                "step": (v["meta"] or {}).get("step"),
            }
            four = all(t.get(s) is not None for s in (101, 102, 103, 104)) and \
                   all(u.get(s) is not None for s in (101, 102, 103, 104))
            (surv if four else lost).append(rec)

        print(f"\n===== {name}: points with a 2-seed delta = {len(surv)+len(lost)} =====")
        describe("survived all four seeds", surv)
        describe("lost 103 and/or 104", lost)

        if surv and lost:
            a = [r["d2"] for r in surv]
            b = [r["d2"] for r in lost]
            # Welch t on the 2-seed delta
            va, vb = st.pvariance(a), st.pvariance(b)
            se = math.sqrt(va / len(a) + vb / len(b))
            t_ = (st.mean(a) - st.mean(b)) / se if se > 0 else 0.0
            print(f"  difference in 2-seed meanD = {st.mean(a)-st.mean(b):+.4f}  (Welch t = {t_:+.2f})")
            ca = sum(1 for r in surv if r["u2"] >= 0.999) / len(surv)
            cb = sum(1 for r in lost if r["u2"] >= 0.999) / len(lost)
            print(f"  ceiling-point share: survived {ca:.3f} vs lost {cb:.3f}  (diff {ca-cb:+.3f})")
            sa = st.mean([r["step"] for r in surv if r["step"] is not None])
            sb = st.mean([r["step"] for r in lost if r["step"] is not None])
            print(f"  mean step:           survived {sa:.1f} vs lost {sb:.1f}  (diff {sa-sb:+.1f})")


if __name__ == "__main__":
    main()
