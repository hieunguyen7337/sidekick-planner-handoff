"""Is the crash rate driven by the SEED, or by WHEN the branch ran?

Seeds 103/104 crash ~10x more than 101/102, but they also all ran later. The
train resume job (25412609, 01:39-04:58) ran a MIX: it finished leftover 101/102
branches while starting 103/104. So within seeds 101/102 there are both early
and late branches, which separates the two explanations.

Uses result.json mtime as the run time.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/fixed_k")
# job boundaries, local time
BASE_END = datetime(2026, 9, 18, 1, 35).timestamp()    # 25410220 timed out
X4_START = datetime(2026, 9, 18, 4, 58).timestamp()    # 25413657 began


def era(ts):
    if ts < BASE_END:
        return "1_base(25410220)"
    if ts < X4_START:
        return "2_resume(25412609)"
    return "3_x4(25413657)"


def main():
    stats = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # era -> seed -> [n, crashes]
    for rj in ROOT.glob("*/*/result.json"):
        name = rj.parent.name
        if "_s" not in name:
            continue
        try:
            seed = int(name.rsplit("_s", 1)[1])
        except ValueError:
            continue
        try:
            st = rj.stat()
            d = json.loads(rj.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        e = era(st.st_mtime)
        cell = stats[e][seed]
        cell[0] += 1
        if d.get("error_type") == "crash":
            cell[1] += 1

    print(f"  {'era':<22} {'seed':>5} {'n':>6} {'crash':>6} {'rate':>8}")
    for e in sorted(stats):
        for seed in sorted(stats[e]):
            n, c = stats[e][seed]
            if n == 0:
                continue
            print(f"  {e:<22} {seed:>5} {n:>6} {c:>6} {100*c/n:>7.2f}%")
        print()

    print("READING:")
    print("  If 101/102 crash rates JUMP in era 2/3, the cause is time or job, not seed.")
    print("  If 101/102 stay low while 103/104 are high in the SAME era, the cause")
    print("  travels with the seed -- i.e. with the replicate branches themselves.")


if __name__ == "__main__":
    main()
