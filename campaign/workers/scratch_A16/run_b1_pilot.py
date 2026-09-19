#!/usr/bin/env python3
"""Orchestrator entrypoint for the B1 clean-counterfactual pilot.

Monkey-patches ``collect_jobs`` so the frozen ``branch_counterfactual.py``
runs only the 200-point sample in ``b1_pilot_points.txt``. Then calls
``branch_counterfactual.main`` unchanged.

This unit (A16) must not execute this file. The orchestrator runs it after
the planner quota resets, from a PBS job, never from the login node.
"""
from __future__ import annotations

from pathlib import Path

import branch_counterfactual as bc

POINTS_PATH = Path(__file__).resolve().parent / "b1_pilot_points.txt"
_ORIG_COLLECT = bc.collect_jobs


def load_frozen_points(path: Path) -> set[tuple[int, str, int]]:
    out: set[tuple[int, str, int]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        seed_s, task_id, i_s = line.split("/")
        out.add((int(seed_s), task_id, int(i_s)))
    return out


FROZEN_POINTS = load_frozen_points(POINTS_PATH)
if len(FROZEN_POINTS) != 200:
    raise SystemExit(f"frozen point list must contain 200 keys, got {len(FROZEN_POINTS)}")


def collect_jobs_filtered(*args, **kwargs):
    jobs = _ORIG_COLLECT(*args, **kwargs)
    filtered = [
        j
        for j in jobs
        if (int(j["seed"]), str(j["task_id"]), int(j["i"])) in FROZEN_POINTS
    ]
    n_points = len({(int(j["seed"]), str(j["task_id"]), int(j["i"])) for j in filtered})
    if n_points > 200 or len(filtered) > 1600:
        raise RuntimeError(
            f"point filter overflow: {n_points} unique points / {len(filtered)} jobs; "
            "refusing to run an unplanned sample"
        )
    out_root = kwargs.get("out_root")
    runs = Path(out_root) / "branch_runs.jsonl" if out_root is not None else None
    fresh = runs is None or (not runs.is_file()) or runs.stat().st_size == 0
    if fresh and (n_points != 200 or len(filtered) != 1600):
        raise RuntimeError(
            f"fresh run must dispatch the frozen 200 points / 1600 branches; "
            f"got {n_points} points / {len(filtered)} jobs"
        )
    return filtered


bc.collect_jobs = collect_jobs_filtered


if __name__ == "__main__":
    raise SystemExit(bc.main())
