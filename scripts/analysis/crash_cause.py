"""Full sweep of J6 error events: what actually killed the crashed branches?

One crashed branch showed exc_type=CodexExecError, "codex exec exited 1" -- a
failed hosted-planner call, not an AppWorld or concurrency failure. If that is
the cause, the escalating crash rate is the Codex quota draining over wall-clock
time, not anything about seeds, jobs or concurrency.

Sweeps every branch's events.jsonl, extracts error events, and cross-tabulates
exception type against seed and against wall-clock hour.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOTS = {
    "train": Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/fixed_k"),
    "dev": Path("/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/fixed_k"),
}


def main():
    for split, root in ROOTS.items():
        exc = Counter()
        detail = Counter()
        by_seed = defaultdict(Counter)
        by_hour = defaultdict(Counter)
        n_dirs = 0
        n_err = 0
        planner_calls_ok = []
        planner_calls_crash = []

        for ev in root.glob("*/*/events.jsonl"):
            n_dirs += 1
            name = ev.parent.name
            try:
                seed = int(name.rsplit("_s", 1)[1])
            except (ValueError, IndexError):
                continue
            # mtime of result.json is when the branch finished
            rj = ev.parent / "result.json"
            hour = None
            crashed = False
            if rj.exists():
                hour = datetime.fromtimestamp(rj.stat().st_mtime).strftime("%m-%d %H")
                try:
                    d = json.loads(rj.read_text())
                    crashed = d.get("error_type") == "crash"
                    npc = d.get("n_planner_calls")
                    if isinstance(npc, int):
                        (planner_calls_crash if crashed else planner_calls_ok).append(npc)
                except (OSError, json.JSONDecodeError):
                    pass
            if not crashed:
                continue
            # find the error event
            try:
                with ev.open() as fh:
                    for line in fh:
                        if '"event_type":"error"' not in line and '"event_type": "error"' not in line:
                            continue
                        r = json.loads(line)
                        if r.get("event_type") != "error":
                            continue
                        p = r.get("payload") or {}
                        et = p.get("exc_type") or "(none)"
                        exc[et] += 1
                        detail[str(p.get("detail"))[:60]] += 1
                        by_seed[seed][et] += 1
                        if hour:
                            by_hour[hour][et] += 1
                        n_err += 1
            except (OSError, json.JSONDecodeError):
                continue

        print(f"\n########## {split}: {n_dirs} branch dirs, {n_err} error events ##########")
        print("  exception types:")
        for k, v in exc.most_common(10):
            print(f"    {k:<28} {v:>6}")
        print("  error details:")
        for k, v in detail.most_common(6):
            print(f"    {k:<62} {v:>6}")
        print("  by seed:")
        for s in sorted(by_seed):
            tot = sum(by_seed[s].values())
            top = ", ".join(f"{k}={v}" for k, v in by_seed[s].most_common(3))
            print(f"    seed {s}: {tot:>5}  {top}")
        print("  by wall-clock hour the branch finished:")
        for h in sorted(by_hour):
            tot = sum(by_hour[h].values())
            top = ", ".join(f"{k}={v}" for k, v in by_hour[h].most_common(2))
            print(f"    {h}: {tot:>5}  {top}")
        if planner_calls_ok and planner_calls_crash:
            import statistics as st
            print(f"  mean n_planner_calls: ok={st.mean(planner_calls_ok):.2f} "
                  f"(n={len(planner_calls_ok)})  crashed={st.mean(planner_calls_crash):.2f} "
                  f"(n={len(planner_calls_crash)})")


if __name__ == "__main__":
    main()
