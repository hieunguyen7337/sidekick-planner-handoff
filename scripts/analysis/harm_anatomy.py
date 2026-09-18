"""Why does a 5-step expert review hurt one call in six?

Splits the hypothesis: is harm predicted by TIMING (when the review fires, how
deep, how much remains) or by CONTENT (what the correction actually says)?

Point-level delta is recomputed here by the verified rule:
  delta = mean(treated[101,102]) - mean(untreated[101,102])
Band 0.166, frozen on train.
"""

import json
import math
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

TRAIN = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl")
BAND = 0.166
SEEDS = [101, 102]


def bucket_report(name, groups):
    """groups: label -> list of deltas."""
    print(f"\n--- {name} ---")
    print(f"  {'bucket':<22} {'n':>5} {'meanD':>9} {'harm%':>7} {'help%':>7}")
    for k in sorted(groups, key=lambda x: (isinstance(x, str), x)):
        v = groups[k]
        if len(v) < 8:
            continue
        harm = sum(1 for d in v if d < -BAND) / len(v)
        help_ = sum(1 for d in v if d > BAND) / len(v)
        print(f"  {str(k):<22} {len(v):>5} {st.mean(v):>+9.4f} {harm:>7.3f} {help_:>7.3f}")


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return None if dx == 0 or dy == 0 else num / (dx * dy)


def main():
    rows = [json.loads(x) for x in TRAIN.read_text().splitlines() if x.strip()]
    print(f"branch_runs rows = {len(rows)}")

    pts = defaultdict(lambda: {"t": {}, "u": {}, "meta": None})
    for r in rows:
        k = r.get("key")
        if not isinstance(k, str):
            continue
        pk = "/".join(k.split("/")[:4])
        bs = r.get("branch_seed")
        if bs not in SEEDS:
            continue
        side = "t" if r.get("condition") == "treated" else "u"
        pts[pk][side][bs] = r.get("branch_gpr")
        if pts[pk]["meta"] is None:
            pts[pk]["meta"] = r

    recs = []
    for pk, v in pts.items():
        if any(v["t"].get(s) is None for s in SEEDS) or any(v["u"].get(s) is None for s in SEEDS):
            continue
        delta = st.mean([v["t"][s] for s in SEEDS]) - st.mean([v["u"][s] for s in SEEDS])
        m = v["meta"]
        corr = m.get("correction") or ""
        recs.append({
            "delta": delta,
            "step": m.get("step"),
            "i": m.get("i"),
            "replay_k": m.get("replay_k"),
            "n_later": m.get("n_later_reviews"),
            "task_id": m.get("task_id"),
            "seed": m.get("seed"),
            "corr": corr,
            "corr_len": len(corr),
            "has_complete": int("complete_task" in corr),
            "has_code": int(bool(re.search(r"apis\.\w+\.\w+\(", corr))),
            "n_api_calls": len(re.findall(r"apis\.\w+\.\w+\(", corr)),
            "is_terse": int(len(corr) < 200),
        })
    print(f"points with complete 101/102 = {len(recs)}")
    ds = [r["delta"] for r in recs]
    print(f"mean delta = {st.mean(ds):+.4f}   "
          f"harm={sum(1 for d in ds if d<-BAND)/len(ds):.4f}  "
          f"help={sum(1 for d in ds if d>BAND)/len(ds):.4f}")

    # ---------- TIMING ----------
    g = defaultdict(list)
    for r in recs:
        s = r["step"]
        b = "01-05" if s <= 5 else "06-10" if s <= 10 else "11-20" if s <= 20 else "21+"
        g[b].append(r["delta"])
    bucket_report("TIMING: step at which the review fired", g)

    g = defaultdict(list)
    for r in recs:
        k = r["replay_k"] or 0
        b = "0-4" if k <= 4 else "5-9" if k <= 9 else "10-19" if k <= 19 else "20+"
        g[b].append(r["delta"])
    bucket_report("TIMING: replay depth (actions before the intervention)", g)

    g = defaultdict(list)
    for r in recs:
        g[f"i={r['i']}" if r["i"] is not None and r["i"] <= 4 else "i>=5"].append(r["delta"])
    bucket_report("TIMING: which intervention index", g)

    g = defaultdict(list)
    for r in recs:
        n = r["n_later"] or 0
        g["0 later" if n == 0 else "1 later" if n == 1 else "2+ later"].append(r["delta"])
    bucket_report("TIMING: reviews still to come after this one", g)

    # ---------- CONTENT ----------
    lens = sorted(r["corr_len"] for r in recs)
    q1, q2, q3 = (lens[len(lens)//4], lens[len(lens)//2], lens[3*len(lens)//4])
    g = defaultdict(list)
    for r in recs:
        L = r["corr_len"]
        b = f"Q1 <={q1}" if L <= q1 else f"Q2 <={q2}" if L <= q2 else f"Q3 <={q3}" if L <= q3 else f"Q4 >{q3}"
        g[b].append(r["delta"])
    bucket_report("CONTENT: correction length quartile (chars)", g)

    g = defaultdict(list)
    for r in recs:
        g["mentions complete_task" if r["has_complete"] else "no complete_task"].append(r["delta"])
    bucket_report("CONTENT: does the correction push to finish the task", g)

    g = defaultdict(list)
    for r in recs:
        g["contains apis.x.y(" if r["has_code"] else "prose only"].append(r["delta"])
    bucket_report("CONTENT: does the correction contain concrete API code", g)

    g = defaultdict(list)
    for r in recs:
        n = r["n_api_calls"]
        g["0 calls" if n == 0 else "1 call" if n == 1 else "2-3 calls" if n <= 3 else "4+ calls"].append(r["delta"])
    bucket_report("CONTENT: how many API calls the correction prescribes", g)

    # ---------- correlations ----------
    print("\n--- point-biserial / linear correlation with delta ---")
    for name, key in [("step", "step"), ("replay_k", "replay_k"), ("i", "i"),
                      ("n_later", "n_later"), ("corr_len", "corr_len"),
                      ("has_complete", "has_complete"), ("has_code", "has_code"),
                      ("n_api_calls", "n_api_calls")]:
        xs = [r[key] or 0 for r in recs]
        r_ = pearson(xs, ds)
        print(f"  r(delta, {name:<13}) = {r_:+.4f}" if r_ is not None else f"  r(delta, {name}) = n/a")

    # ---------- concentration ----------
    per_task = defaultdict(list)
    for r in recs:
        per_task[r["task_id"]].append(r["delta"])
    harm_tasks = [(t, st.mean(v), len(v)) for t, v in per_task.items() if len(v) >= 3]
    harm_tasks.sort(key=lambda x: x[1])
    print(f"\n--- harm concentration: {len(per_task)} tasks, {len(harm_tasks)} with >=3 points ---")
    print("  most harmful tasks (mean delta):")
    for t, m, n in harm_tasks[:8]:
        print(f"    {t:<16} n={n:<3} meanD={m:+.4f}")
    print("  most helpful tasks:")
    for t, m, n in harm_tasks[-5:]:
        print(f"    {t:<16} n={n:<3} meanD={m:+.4f}")
    tm = [m for _, m, _ in harm_tasks]
    print(f"  spread of per-task mean delta: sd={st.pstdev(tm):.4f} "
          f"min={min(tm):+.4f} max={max(tm):+.4f}")

    # dump the worst corrections for qualitative read
    recs.sort(key=lambda r: r["delta"])
    out = Path("/home/n12194778/.claude/jobs/91578989/tmp/harmful_corrections.jsonl")
    with out.open("w") as fh:
        for r in recs[:40]:
            fh.write(json.dumps({k: r[k] for k in
                                 ("delta", "step", "i", "replay_k", "n_later",
                                  "task_id", "seed", "corr")}) + "\n")
        fh.write("=== MOST HELPFUL BELOW ===\n")
        for r in recs[-40:]:
            fh.write(json.dumps({k: r[k] for k in
                                 ("delta", "step", "i", "replay_k", "n_later",
                                  "task_id", "seed", "corr")}) + "\n")
    print(f"\nwrote 40 most harmful + 40 most helpful corrections to {out}")


if __name__ == "__main__":
    main()
