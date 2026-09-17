#!/usr/bin/env python
"""HJ-1's go/no-go gate: is the planner far enough above the bare executor?

The pilot only tells us anything if there is room between `planner_alone` and
`executor_alone`. With no gap there is nothing for a trained executor to close, and
every later milestone is measuring noise.

Everything here is **paired** on (task_id, seed). AppWorld tasks vary enormously in
difficulty, so an unpaired difference of means mostly measures which tasks each arm
happened to finish -- and tonight the arms did not finish the same ones, because they ran
in separate jobs and one of them died early. Pairing on the intersection is what makes the
comparison honest; the script reports how many pairs it found and how many runs it
discarded to get them, so a shrunken intersection cannot hide.

Runs that errored are kept at their recorded score (0.0), never dropped: an arm that
crashes on hard tasks is worse, not unmeasured.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Literal

BOOTSTRAP = 10_000
SEED = 20260915
ResampleUnit = Literal["task", "pair"]


def load_arm(root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    runs: dict[tuple[str, int], dict[str, Any]] = {}
    for path in sorted(root.rglob("result.json")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        r = json.loads(text)
        key = (str(r.get("task_id")), int(r.get("seed", 0)))
        runs[key] = r
    return runs


def scenario_of(task_id: str) -> str:
    """AppWorld task ids are `<scenario>_<n>`: 50e1ac9_1, _2 and _3 are one scenario."""
    return task_id.rsplit("_", 1)[0]


def scenario_goal_completion(runs: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    """SGC: the share of scenarios in which EVERY task succeeded.

    It cannot be a per-run field, which is why `AppWorldEnv.evaluate` leaves it None --
    one run is one task, and a scenario spans several. It has to be aggregated here.

    ⚠ Only scenarios whose tasks are *all* present are scored. A pilot runs a subset of
    the split, so a scenario represented by 1 of its 3 tasks would otherwise be counted as
    complete on the strength of a third of the evidence, which inflates SGC. The count of
    scenarios dropped for incompleteness is reported so the coverage is visible.
    """
    by_seed_scenario: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for (task_id, seed), r in runs.items():
        by_seed_scenario.setdefault((seed, scenario_of(task_id)), []).append(r)
    if not by_seed_scenario:
        return {"value": None, "note": "no runs"}
    # Expected size of each scenario, taken across the whole arm: the largest number of
    # distinct tasks seen for that scenario in any seed.
    expected: dict[str, int] = {}
    for (_seed, scen), group in by_seed_scenario.items():
        expected[scen] = max(expected.get(scen, 0), len(group))
    scored = 0
    complete = 0
    dropped = 0
    for (_seed, scen), group in by_seed_scenario.items():
        if len(group) < expected[scen]:
            dropped += 1
            continue
        scored += 1
        if all(r.get("success") for r in group):
            complete += 1
    if not scored:
        return {"value": None, "note": "no fully covered scenarios", "dropped_incomplete": dropped}
    return {
        "value": round(complete / scored, 4),
        "scenarios_scored": scored,
        "scenarios_complete": complete,
        "dropped_incomplete": dropped,
    }


def _draw_task_clusters(
    by_task: dict[str, list[Any]], rng: random.Random
) -> list[Any]:
    """Draw tasks with replacement and carry each selected task's whole cluster."""
    tasks = sorted(by_task)
    return [
        value
        for task in (tasks[rng.randrange(len(tasks))] for _ in range(len(tasks)))
        for value in by_task[task]
    ]


def describe(runs: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        return {"n": 0}
    tgc = [float(r.get("tgc") or 0.0) for r in runs.values()]
    steps = [int(r.get("steps") or 0) for r in runs.values()]
    calls = [int(r.get("n_planner_calls") or 0) for r in runs.values()]
    errors = Counter(str(r.get("error_type") or "none") for r in runs.values())
    # Never coerce a missing metric to 0.0. `sgc` is None on every run by construction,
    # and averaging that as zero reported "sgc_mean: 0.0" next to 41 solved tasks -- a
    # plausible-looking number for a metric that had simply never been computed.
    return {
        "n": len(runs),
        "solved": sum(1 for r in runs.values() if r.get("success")),
        "tgc_mean": round(statistics.fmean(tgc), 4),
        "sgc": scenario_goal_completion(runs),
        "steps_mean": round(statistics.fmean(steps), 2),
        "planner_calls_total": sum(calls),
        "errors": dict(sorted(errors.items())),
    }


def paired_diff(
    base: dict[tuple[str, int], dict[str, Any]],
    other: dict[tuple[str, int], dict[str, Any]],
    field: str,
    resample: ResampleUnit = "task",
) -> dict[str, Any]:
    if resample not in {"task", "pair"}:
        raise ValueError(f"unknown resampling unit: {resample!r}")
    keys = sorted(set(base) & set(other))
    dropped_from_base = len(base) - len(keys)
    dropped_from_other = len(other) - len(keys)
    dropped = {
        "base": dropped_from_base,
        "other": dropped_from_other,
        "total": dropped_from_base + dropped_from_other,
    }
    if not keys:
        return {
            "n_pairs": 0,
            "n_tasks": 0,
            "n_clusters": 0,
            "mean_cluster_size": None,
            "resample": resample,
            "resample_unit": resample,
            "dropped_from_base": dropped_from_base,
            "dropped_from_other": dropped_from_other,
            "dropped_unmatched_keys": dropped,
            "note": "no overlapping (task_id, seed) -- nothing to compare",
        }
    diffs = [
        float(base[k].get(field) or 0.0) - float(other[k].get(field) or 0.0) for k in keys
    ]
    point = statistics.fmean(diffs)
    by_task: dict[str, list[float]] = {}
    for key, diff in zip(keys, diffs):
        by_task.setdefault(key[0], []).append(diff)
    n_tasks = len(by_task)
    if resample == "task":
        n_clusters = n_tasks
        mean_cluster_size = len(diffs) / n_tasks
    else:
        n_clusters = len(diffs)
        mean_cluster_size = 1.0

    rng = random.Random(SEED)
    means = []
    for _ in range(BOOTSTRAP):
        if resample == "pair":
            sampled = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        else:
            sampled = _draw_task_clusters(by_task, rng)
        means.append(sum(sampled) / len(sampled))
    means.sort()
    lo = means[int(0.025 * BOOTSTRAP)]
    hi = means[int(0.975 * BOOTSTRAP)]
    return {
        "n_pairs": len(diffs),
        "n_tasks": n_tasks,
        "n_clusters": n_clusters,
        "mean_cluster_size": round(mean_cluster_size, 4),
        "resample": resample,
        "resample_unit": resample,
        "dropped_from_base": dropped_from_base,
        "dropped_from_other": dropped_from_other,
        "dropped_unmatched_keys": dropped,
        "diff_pp": round(point * 100, 2),
        "ci95_pp": [round(lo * 100, 2), round(hi * 100, 2)],
        "bootstrap": BOOTSTRAP,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--arm",
        action="append",
        required=True,
        metavar="LABEL=DIR",
        help="an arm's results directory, e.g. planner_alone=/scratch/.../planner_alone",
    )
    p.add_argument("--baseline", default="planner_alone")
    p.add_argument("--margin-pp", type=float, default=20.0)
    # tgc only: SGC is a scenario-level rate, so there is no per-run SGC to pair on. It
    # is reported per arm by scenario_goal_completion() instead.
    p.add_argument("--field", default="tgc", choices=["tgc"])
    p.add_argument(
        "--resample",
        choices=["task", "pair"],
        default="task",
        help="bootstrap unit: all matched seeds in a task, or individual pairs (default: task)",
    )
    p.add_argument("--out")
    args = p.parse_args()

    arms: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    for spec in args.arm:
        label, _, directory = spec.partition("=")
        arms[label] = load_arm(Path(directory))

    report: dict[str, Any] = {
        "margin_pp": args.margin_pp,
        "field": args.field,
        "baseline": args.baseline,
        "arms": {label: describe(runs) for label, runs in arms.items()},
        "comparisons": {},
    }

    base = arms.get(args.baseline) or {}
    for label, runs in arms.items():
        if label == args.baseline:
            continue
        cmp = paired_diff(base, runs, args.field, resample=args.resample)
        if cmp.get("n_pairs"):
            cmp["gap_at_least_margin"] = cmp["diff_pp"] >= args.margin_pp
            # Reported alongside, never instead of: the point estimate is the stated
            # rule, but a gap whose CI crosses the margin is not a settled gap.
            cmp["ci_lower_at_least_margin"] = cmp["ci95_pp"][0] >= args.margin_pp
        report["comparisons"][f"{args.baseline} - {label}"] = cmp

    incomplete = [lbl for lbl, d in report["arms"].items() if d.get("n", 0) == 0]
    if incomplete:
        report["warning"] = f"arms with no results: {', '.join(incomplete)}"

    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
