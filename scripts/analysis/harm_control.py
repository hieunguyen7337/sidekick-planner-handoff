"""Is the n_later_reviews effect real, or is it a proxy for a struggling episode?

n_later is measured on the FACTUAL episode: an episode that finished quickly has
few later reviews, one that floundered has many. So "2+ reviews still to come"
may simply mean "this episode was going badly", and a main effect of difficulty
would be expected to cancel in a treated-minus-untreated difference -- unless the
intervention interacts with difficulty.

Stratify and see whether n_later survives.
"""

import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

TRAIN = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl")
BAND = 0.166
SEEDS = [101, 102]


def cell(v):
    if len(v) < 8:
        return f"{len(v):>4}      --        --"
    harm = sum(1 for d in v if d < -BAND) / len(v)
    return f"{len(v):>4} {st.mean(v):>+9.4f} {harm:>8.3f}"


def main():
    rows = [json.loads(x) for x in TRAIN.read_text().splitlines() if x.strip()]
    pts = defaultdict(lambda: {"t": {}, "u": {}, "meta": None})
    for r in rows:
        k = r.get("key")
        if not isinstance(k, str):
            continue
        pk = "/".join(k.split("/")[:4])
        bs = r.get("branch_seed")
        if bs not in SEEDS:
            continue
        pts[pk]["t" if r.get("condition") == "treated" else "u"][bs] = r.get("branch_gpr")
        if pts[pk]["meta"] is None:
            pts[pk]["meta"] = r

    recs = []
    for pk, v in pts.items():
        if any(v["t"].get(s) is None for s in SEEDS) or any(v["u"].get(s) is None for s in SEEDS):
            continue
        m = v["meta"]
        recs.append({
            "delta": st.mean([v["t"][s] for s in SEEDS]) - st.mean([v["u"][s] for s in SEEDS]),
            "step": m.get("step") or 0,
            "n_later": m.get("n_later") if m.get("n_later") is not None else (m.get("n_later_reviews") or 0),
            "solved": bool(m.get("actual_solved")),
            "actual": m.get("actual_gpr"),
            "untr": st.mean([v["u"][s] for s in SEEDS]),
        })
    print(f"points = {len(recs)}")

    def nl(r):
        n = r["n_later"] or 0
        return "0" if n == 0 else "1" if n == 1 else "2+"

    # 1. factual solved / not solved
    print("\n=== stratified by whether the FACTUAL episode solved the task ===")
    print(f"  {'stratum':<26} {'n':>4} {'meanD':>9} {'harm%':>8}")
    for sv in (True, False):
        sub = [r for r in recs if r["solved"] == sv]
        print(f"  solved={str(sv):<19} {cell([r['delta'] for r in sub])}")
        for b in ("0", "1", "2+"):
            v = [r["delta"] for r in sub if nl(r) == b]
            print(f"    n_later={b:<20} {cell(v)}")

    # 2. control for how well the UNTREATED branch did (the counterfactual baseline)
    print("\n=== stratified by untreated-branch outcome (the counterfactual baseline) ===")
    us = sorted(r["untr"] for r in recs)
    lo, hi = us[len(us) // 3], us[2 * len(us) // 3]
    print(f"  tertile cuts at untreated_gpr {lo:.3f} / {hi:.3f}")
    print(f"  {'stratum':<26} {'n':>4} {'meanD':>9} {'harm%':>8}")
    for name, pred in (("low", lambda r: r["untr"] <= lo),
                       ("mid", lambda r: lo < r["untr"] <= hi),
                       ("high", lambda r: r["untr"] > hi)):
        sub = [r for r in recs if pred(r)]
        print(f"  untreated={name:<17} {cell([r['delta'] for r in sub])}")
        for b in ("0", "1", "2+"):
            v = [r["delta"] for r in sub if nl(r) == b]
            print(f"    n_later={b:<20} {cell(v)}")

    # 3. within a narrow step band, does n_later still bite?
    print("\n=== stratified by step bucket (position held roughly fixed) ===")
    print(f"  {'stratum':<26} {'n':>4} {'meanD':>9} {'harm%':>8}")
    for name, pred in (("step<=5", lambda r: r["step"] <= 5),
                       ("step 6-10", lambda r: 5 < r["step"] <= 10),
                       ("step 11+", lambda r: r["step"] > 10)):
        sub = [r for r in recs if pred(r)]
        print(f"  {name:<24} {cell([r['delta'] for r in sub])}")
        for b in ("0", "1", "2+"):
            v = [r["delta"] for r in sub if nl(r) == b]
            print(f"    n_later={b:<20} {cell(v)}")

    # 4. ceiling check: can a correction even help when untreated already succeeds?
    print("\n=== ceiling/floor asymmetry ===")
    top = [r for r in recs if r["untr"] >= 0.999]
    bot = [r for r in recs if r["untr"] <= 0.001]
    mid = [r for r in recs if 0.001 < r["untr"] < 0.999]
    for nm, sub in (("untreated already 1.0", top), ("untreated already 0.0", bot), ("untreated in between", mid)):
        v = [r["delta"] for r in sub]
        if v:
            harm = sum(1 for d in v if d < -BAND) / len(v)
            help_ = sum(1 for d in v if d > BAND) / len(v)
            print(f"  {nm:<24} n={len(v):>4} meanD={st.mean(v):+.4f} harm={harm:.3f} help={help_:.3f}")


if __name__ == "__main__":
    main()
