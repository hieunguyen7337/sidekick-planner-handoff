#!/usr/bin/env python3
"""A17: residual later ticks under symmetric suppress_next, from frozen inputs.

Read-only on /scratch/.../results/. Does not call the planner.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from sidekick.systems.loop import next_scheduled_review_step  # noqa: E402

J6_TRAIN = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl")
POINTS = REPO / "campaign/workers/scratch_A16/b1_pilot_points.txt"
MAX_STEPS = 40


def last_rows(path: Path) -> dict[tuple, dict]:
    last: dict[tuple, dict] = {}
    n_lines = 0
    with path.open() as fh:
        for line in fh:
            n_lines += 1
            r = json.loads(line)
            key = (
                int(r["seed"]),
                str(r["task_id"]),
                int(r["i"]),
                str(r["condition"]),
                int(r["branch_seed"]),
            )
            last[key] = r
    print(f"j6_jsonl_lines={n_lines} last_row_keys={len(last)}")
    return last


def load_frozen_points(path: Path) -> list[tuple[int, str, int]]:
    out: list[tuple[int, str, int]] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            seed_s, task_id, i_s = line.split("/", 2)
            out.append((int(seed_s), task_id, int(i_s)))
    return out


def ticks_after_t(s: int, k: int, horizon: int) -> tuple[int | None, int]:
    t = next_scheduled_review_step(s, k)
    if t is None or k <= 0 or horizon < t:
        return t, 0
    n = 0
    step = t + k
    while step <= horizon:
        n += 1
        step += k
    return t, n


def median(xs: list[float]) -> float | None:
    if not xs:
        return None
    return float(statistics.median(xs))


def summarize(name: str, vals: list[float]) -> None:
    if not vals:
        print(f"{name}: n=0")
        return
    buckets = Counter()
    for v in vals:
        if v <= 0:
            buckets["0"] += 1
        elif v < 1:
            buckets["(0,1)"] += 1
        elif v == 1:
            buckets["1"] += 1
        elif v == 2:
            buckets["2"] += 1
        else:
            buckets["3+"] += 1
    print(
        f"{name}: n={len(vals)} mean={sum(vals)/len(vals):.6f} "
        f"median={median(vals)} min={min(vals)} max={max(vals)} "
        f"buckets={dict(sorted(buckets.items()))}"
    )


def point_values(by_point: dict, pids: list[tuple[int, str, int]]) -> dict[str, list[float]]:
    sched_max: list[float] = []
    sched_obs_horizon: list[float] = []
    proxy_from_n_later: list[float] = []
    j6_n_later: list[float] = []
    n_missing = 0
    n_used = 0
    for pid in pids:
        d = by_point.get(pid) or {}
        untreated = [d[k] for k in d if k[0] == "untreated"]
        if not untreated:
            n_missing += 1
            continue
        n_used += 1
        n_laters = []
        residuals_obs = []
        residuals_max = []
        for r in untreated:
            s = int(r["step"])
            k = int(r.get("review_every_k") or 5)
            n_later = r.get("n_later_reviews")
            if n_later is None:
                continue
            n_later = int(n_later)
            n_laters.append(n_later)
            proxy_from_n_later.append(max(0, n_later - 1))
            j6_n_later.append(n_later)
            _t, n_max = ticks_after_t(s, k, MAX_STEPS)
            residuals_max.append(n_max)
            bs = r.get("branch_steps")
            if bs is not None:
                _t2, n_obs = ticks_after_t(s, k, int(bs))
                residuals_obs.append(n_obs)
                sched_obs_horizon.append(n_obs)
            sched_max.append(n_max)
        if n_laters:
            # keep lists as replicate-level above; point-level medians added below
            pass
    print(f"points_requested={len(pids)} points_with_untreated={n_used} points_missing={n_missing}")
    return {
        "sched_max_steps40_replicate": sched_max,
        "sched_observed_branch_steps_replicate": sched_obs_horizon,
        "proxy_max0_n_later_minus_1_replicate": proxy_from_n_later,
        "j6_n_later_replicate": j6_n_later,
    }


def point_medians(by_point: dict, pids: list[tuple[int, str, int]]) -> dict[str, list[float]]:
    out = {
        "j6_n_later_point_median": [],
        "proxy_n_later_minus_1_point_median": [],
        "sched_max40_point_median": [],
        "sched_branch_steps_point_median": [],
    }
    for pid in pids:
        d = by_point.get(pid) or {}
        untreated = [d[k] for k in d if k[0] == "untreated"]
        if not untreated:
            continue
        n_laters = []
        max40 = []
        obs_h = []
        for r in untreated:
            s = int(r["step"])
            k = int(r.get("review_every_k") or 5)
            raw = r.get("n_later_reviews")
            if raw is not None:
                n_laters.append(int(raw))
            _t, n_max = ticks_after_t(s, k, MAX_STEPS)
            max40.append(n_max)
            if r.get("branch_steps") is not None:
                _t2, n_obs = ticks_after_t(s, k, int(r["branch_steps"]))
                obs_h.append(n_obs)
        if n_laters:
            med = float(statistics.median(n_laters))
            out["j6_n_later_point_median"].append(med)
            out["proxy_n_later_minus_1_point_median"].append(max(0.0, med - 1.0))
        if max40:
            out["sched_max40_point_median"].append(float(statistics.median(max40)))
        if obs_h:
            out["sched_branch_steps_point_median"].append(float(statistics.median(obs_h)))
    return out


def main() -> None:
    print("=== A17 residual n_later under symmetric suppress_next ===")
    print(f"j6_train={J6_TRAIN}")
    print(f"frozen_points={POINTS}")
    print(f"max_steps_assumed={MAX_STEPS}")
    last = last_rows(J6_TRAIN)
    by_point: dict[tuple[int, str, int], dict] = defaultdict(dict)
    for (seed, task_id, i, cond, bseed), r in last.items():
        by_point[(seed, task_id, i)][(cond, bseed)] = r
    all_pids = sorted(by_point.keys())
    frozen = load_frozen_points(POINTS)
    print(f"unique_j6_points={len(all_pids)} frozen_n={len(frozen)}")
    frozen_in_j6 = sum(1 for p in frozen if p in by_point)
    print(f"frozen_in_j6={frozen_in_j6}")

    print("--- frozen 200, replicate-level untreated ---")
    for name, vals in point_values(by_point, frozen).items():
        summarize(name, vals)
    print("--- frozen 200, point-level median untreated ---")
    for name, vals in point_medians(by_point, frozen).items():
        summarize(name, vals)
    print("--- all J6 train points, point-level median untreated ---")
    for name, vals in point_medians(by_point, all_pids).items():
        summarize(name, vals)


if __name__ == "__main__":
    main()
