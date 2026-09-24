#!/usr/bin/env python
"""Build configs/dev_wrongtask_plan_map.json, the task permutation of the dev WTP control.

Brief: campaign/workers/briefs/20260924_ctrl_planning_controls.md. DEV ONLY: any other split is
refused before anything is read. The WTP arm replays, for episode (t, s), the HJ-1 packet of
(map[t], s) (src/sidekick/agents/packet_remap.py). The map is built as follows:

1. plan_chars[t] -- the characters of the plan text the executor is shown for t: the replayed
   packet rendered as `DelegationPacket.model_dump_json()`, which is what follows "Plan: " in the
   executor prompt (src/sidekick/protocols/prompts.py:226-227). The packet is the one
   CachedPacketPlanner replays: the plan event of the LAST attempt (`_last_attempt_plan_event`,
   src/sidekick/agents/planner.py:736-766, read at :893, validated at :918). Mean over the seeds.
2. cost[t][s] = |plan_chars[t] - plan_chars[s]|, FORBIDDEN when s == t or
   scenario_of(s) == scenario_of(t). scenario_of is scripts/setup/hj1_gate.py:45-47, the cluster
   label every scenario interval is computed on (scripts/analysis/j16_inference.py:152 hands it to
   cluster_inference.py, which defines none).
3. map = the perfect assignment of minimum total cost (rule "min_cost_length_assignment"). Ties go
   to the assignment whose sources, read in sorted task_id order, are lexicographically smallest
   by sorted task_id. Two-cycles (swaps) are allowed.

So the map is a permutation, a derangement, never inside one scenario, and as close in plan length
as those constraints allow. It replaced a cyclic shift over the length order (k = 16, median gap
573.5 chars, source/own length ratio 0.52-1.57), which did not support "matched length".

scipy is not installed in the project env, so the assignment is solved here: an integer Hungarian
algorithm (O(n^3)), exact because every cost is scaled to an integer.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hj1_gate import scenario_of  # noqa: E402

from sidekick.agents.planner import _last_attempt_plan_event  # noqa: E402
from sidekick.protocols.schemas import DelegationPacket  # noqa: E402

ALLOWED_SPLIT = "dev"
DEFAULT_SOURCE = "/scratch/n12194778/sidekick/results/hj1b_planner_20260915"
DEFAULT_OUT = "configs/dev_wrongtask_plan_map.json"
RULE = "min_cost_length_assignment"


def plan_text_chars(events_path: Path) -> int:
    """Length of the plan text the replay would show the executor for this archived episode."""
    payload, _usage = _last_attempt_plan_event(events_path)
    if payload is None:
        raise ValueError(f"no plan event in the last attempt of {events_path}")
    return len(DelegationPacket.model_validate(payload["packet"]).model_dump_json())


def plan_chars_by_task(
    packet_source: str | Path, system: str, task_ids: Sequence[str], seeds: Sequence[int]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for task_id in task_ids:
        lengths = []
        for seed in seeds:
            path = Path(packet_source) / system / str(seed) / task_id / "events.jsonl"
            if not path.is_file():
                raise FileNotFoundError(f"no archived episode for seed {seed}, task {task_id}: {path}")
            lengths.append(plan_text_chars(path))
        out[task_id] = sum(lengths) / len(lengths)
    return out


def min_cost_assignment(cost: Sequence[Sequence[int]]) -> list[int]:
    """Column of each row in a minimum-total-cost perfect assignment of a square integer matrix.

    The Hungarian algorithm with row/column potentials (the O(n^3) shortest-augmenting-path
    form). Integer costs keep every potential and reduced cost exact, so the optimum is exact.
    "Not reached yet" is None rather than a numeric infinity, so no sentinel has to be proven
    larger than every reduced cost.
    """
    n = len(cost)
    if any(len(row) != n for row in cost) or not all(type(c) is int for row in cost for c in row):
        raise ValueError("min_cost_assignment needs a square matrix of ints")
    u = [0] * (n + 1)  # row potentials, 1-based
    v = [0] * (n + 1)  # column potentials, 1-based
    match = [0] * (n + 1)  # match[j] = row assigned to column j (0 = none)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        match[0] = i
        j0 = 0
        minv: list[int | None] = [None] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = match[j0], None, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if minv[j] is None or cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if delta is None or minv[j] < delta:
                        delta, j1 = minv[j], j
            # Every unused column was scanned above, so delta and each unused minv are ints.
            for j in range(n + 1):
                if used[j]:
                    u[match[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if match[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            match[j0] = match[j1]
            j0 = j1
    cols = [0] * n
    for j in range(1, n + 1):
        cols[match[j] - 1] = j - 1
    return cols


def map_stats(task_map: Mapping[str, str], plan_chars: Mapping[str, float]) -> dict[str, Any]:
    """Length match of a map: |gap| and source/own length ratio over its tasks."""
    gaps = [abs(plan_chars[s] - plan_chars[t]) for t, s in task_map.items()]
    ratios = [plan_chars[s] / plan_chars[t] for t, s in task_map.items()]
    return {
        "n_tasks": len(gaps),
        "total_cost_chars": sum(gaps),
        "median_abs_gap_chars": statistics.median(gaps),
        "max_abs_gap_chars": max(gaps),
        "min_length_ratio": min(ratios),
        "max_length_ratio": max(ratios),
        "n_two_cycles": sum(1 for t, s in task_map.items() if t < s and task_map[s] == t),
    }


def build_wrongtask_map(plan_chars: Mapping[str, float]) -> dict[str, Any]:
    order = sorted(plan_chars)
    n = len(order)
    exact = [Fraction(plan_chars[t]) for t in order]
    scale = math.lcm(*(x.denominator for x in exact))  # 2 for means over two seeds
    gap = [[int(abs(a - b) * scale) for b in exact] for a in exact]
    # Lexicographic tie-break folded into one objective: column j in row i adds j * n**(n-1-i), so
    # the sum over rows is the base-n numeral of the source sequence, and it is below big = n**n.
    # big * gap + that term therefore minimises total gap first and the source sequence second.
    big = n**n
    worst = max((max(row) for row in gap), default=0)
    forbidden = big * (worst + 1) * n + big  # above every feasible total, and finite

    def allowed(i: int, j: int) -> bool:
        return i != j and scenario_of(order[i]) != scenario_of(order[j])

    cost = [
        [big * gap[i][j] + j * n ** (n - 1 - i) if allowed(i, j) else forbidden for j in range(n)]
        for i in range(n)
    ]
    cols = min_cost_assignment(cost)
    if not all(allowed(i, j) for i, j in enumerate(cols)):
        raise ValueError(f"no assignment of {n} tasks avoids every task's own plan and scenario")
    task_map = {order[i]: order[j] for i, j in enumerate(cols)}
    chars = {t: float(plan_chars[t]) for t in order}
    return {
        "map": task_map,
        "plan_chars": chars,
        "metadata": {
            "rule": RULE,
            "cost": "|plan_chars[t] - plan_chars[s]|; forbidden when s == t or scenario_of(s) == scenario_of(t)",
            "tie_break": "lexicographically smallest source sequence, tasks and sources in sorted task_id order",
            **map_stats(task_map, chars),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--split", required=True)
    p.add_argument("--tasks", type=int, default=57, help="the runner's --tasks (ids[:n] of the split)")
    p.add_argument("--seeds", default="1,2")
    p.add_argument("--packet-source", default=DEFAULT_SOURCE)
    p.add_argument("--packet-system", default="planner_alone")
    p.add_argument("--out", default=DEFAULT_OUT)
    a = p.parse_args(argv)
    if a.split != ALLOWED_SPLIT:
        print(f"refusing split {a.split!r}: the wrong-task map is a dev-only control", file=sys.stderr)
        return 2
    from sidekick.runner import appworld_task_ids, parse_seeds

    task_ids = appworld_task_ids(a.split, a.tasks)
    seeds = parse_seeds(a.seeds)
    doc = build_wrongtask_map(plan_chars_by_task(a.packet_source, a.packet_system, task_ids, seeds))
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": a.out, "n_tasks": len(task_ids), "seeds": seeds, **doc["metadata"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
