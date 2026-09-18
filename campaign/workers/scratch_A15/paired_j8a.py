#!/usr/bin/env python
"""A15 helper: paired J8a contrast the J10 script does not emit.

Uses j10_report.load_arm_tree / inventory_arm and hj1_gate.paired_diff
unmodified. Does not write under /scratch/.../results/. Dev archives only.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from scripts.analysis.j10_report import (  # noqa: E402
    RESAMPLE_UNIT,
    discover_tasks,
    inventory_arm,
    load_arm_tree,
    native_from_paired_diff,
)
from scripts.setup.campaign_summarize import BROKEN  # noqa: E402
from scripts.setup.hj1_gate import paired_diff  # noqa: E402

SCRATCH = Path("/scratch/n12194778/sidekick/results")
EXEC_ROOT = SCRATCH / "hj8_executor_alone_bplus_20260919"
SFT_ROOT = SCRATCH / "hj8_sft_plan_bplus_20260919"
OUT = REPO / "campaign" / "workers" / "scratch_A15" / "paired_contrast.json"
SEEDS = [1, 2]
MAX_STEPS = 40
HOSTED_PROVIDERS = {"codex"}


def _public_inv(inv: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in inv.items()
        if k
        not in {
            "cleaned",
            "disagreements",
            "empty_files",
            "unreadable",
            "duplicates",
            "extra_runs_ignored",
            "_extra_keys",
            "n_cells_shown_in_detail",
        }
    }


def _task_sets(loaded: dict[str, Any], seeds: list[int]) -> set[str]:
    seed_set = set(seeds)
    return {task_id for task_id, seed in loaded["runs"] if seed in seed_set}


def _episode_files(root: Path) -> dict[str, Any]:
    result_dirs = {p.parent for p in root.rglob("result.json")}
    event_dirs = {p.parent for p in root.rglob("events.jsonl")}
    empty_results = []
    for path in sorted(root.rglob("result.json")):
        if not path.read_text(encoding="utf-8").strip():
            empty_results.append(str(path))
    return {
        "n_result_json": len(result_dirs),
        "n_events_jsonl": len(event_dirs),
        "events_without_result": sorted(str(p) for p in event_dirs - result_dirs),
        "result_without_events": sorted(str(p) for p in result_dirs - event_dirs),
        "empty_result_json": empty_results,
    }


def _scan_planner_events(root: Path) -> dict[str, Any]:
    n_planner_events = 0
    providers: Counter[str] = Counter()
    models: Counter[str] = Counter()
    hosted = 0
    token_sum = 0
    nonzero_token_events = 0
    for path in sorted(root.rglob("events.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or '"actor"' not in line:
                continue
            ev = json.loads(line)
            if ev.get("actor") != "planner":
                continue
            n_planner_events += 1
            usage = ev.get("usage") or {}
            provider = str(usage.get("provider") or "missing")
            model = str(usage.get("model") or "missing")
            providers[provider] += 1
            models[model] += 1
            tokens = (
                int(usage.get("input_tokens") or 0)
                + int(usage.get("cached_input_tokens") or 0)
                + int(usage.get("output_tokens") or 0)
                + int(usage.get("reasoning_output_tokens") or 0)
            )
            token_sum += tokens
            if tokens:
                nonzero_token_events += 1
            if provider in HOSTED_PROVIDERS:
                hosted += 1
    return {
        "n_planner_events": n_planner_events,
        "providers": dict(sorted(providers.items())),
        "models": dict(sorted(models.items())),
        "hosted_provider_events": hosted,
        "planner_event_token_sum": token_sum,
        "n_planner_events_with_nonzero_tokens": nonzero_token_events,
    }


def _arm_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = Counter(str(r.get("error_type") or "none") for r in rows)
    broken_rows = [
        {
            "task_id": r.get("task_id"),
            "seed": r.get("seed"),
            "error_type": r.get("error_type"),
        }
        for r in rows
        if r.get("error_type") in BROKEN
    ]
    calls = [int(r["n_planner_calls"]) for r in rows if r.get("n_planner_calls") is not None]
    calls_missing = sum(1 for r in rows if r.get("n_planner_calls") is None)
    steps = [int(r["steps"]) for r in rows if r.get("steps") is not None]
    steps_missing = sum(1 for r in rows if r.get("steps") is None)
    gpr = [float(r["goal_pass_rate"]) for r in rows if r.get("goal_pass_rate") is not None]
    gpr_missing = sum(1 for r in rows if r.get("goal_pass_rate") is None)
    tgc = [float(r["tgc"]) for r in rows if r.get("tgc") is not None]
    tgc_missing = sum(1 for r in rows if r.get("tgc") is None)
    usd = [float((r.get("totals") or {}).get("usd_total") or 0.0) for r in rows]
    planner_tokens = [
        int((r.get("totals") or {}).get("planner_tokens_total") or 0) for r in rows
    ]
    max_step_hits = [
        {
            "task_id": r.get("task_id"),
            "seed": r.get("seed"),
            "steps": r.get("steps"),
            "error_type": r.get("error_type"),
            "tgc": r.get("tgc"),
        }
        for r in rows
        if r.get("steps") is not None and int(r["steps"]) >= MAX_STEPS
    ]
    limit_below_cap = [
        {
            "task_id": r.get("task_id"),
            "seed": r.get("seed"),
            "steps": r.get("steps"),
            "error_type": r.get("error_type"),
        }
        for r in rows
        if r.get("error_type") == "limit"
        and r.get("steps") is not None
        and int(r["steps"]) < MAX_STEPS
    ]
    by_seed: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_seed.setdefault(str(r.get("seed")), []).append(r)

    def _seed_mean(seed_rows: list[dict[str, Any]], field: str) -> Optional[float]:
        vals = [float(r[field]) for r in seed_rows if r.get(field) is not None]
        return round(statistics.fmean(vals), 6) if vals else None

    return {
        "n_rows": len(rows),
        "n_success": sum(1 for r in rows if r.get("success")),
        "errors": dict(sorted(errors.items())),
        "n_broken": len(broken_rows),
        "broken": broken_rows,
        "n_planner_calls_total": sum(calls) if calls_missing == 0 else None,
        "n_planner_calls_mean": round(statistics.fmean(calls), 6) if calls else None,
        "n_planner_calls_missing": calls_missing,
        "n_planner_calls_nonzero": sum(1 for c in calls if c != 0),
        "n_planner_calls_values": dict(sorted(Counter(calls).items())),
        "steps_mean": round(statistics.fmean(steps), 6) if steps else None,
        "steps_missing": steps_missing,
        "goal_pass_rate_mean": round(statistics.fmean(gpr), 6) if gpr else None,
        "goal_pass_rate_missing": gpr_missing,
        "tgc_mean_unpaired": round(statistics.fmean(tgc), 6) if tgc else None,
        "tgc_missing": tgc_missing,
        "usd_total_sum": round(sum(usd), 6),
        "planner_tokens_total_sum": sum(planner_tokens),
        "n_max_steps": len(max_step_hits),
        "max_steps_episodes": max_step_hits,
        "n_limit": errors.get("limit", 0),
        "limit_below_max_steps": limit_below_cap,
        "unpaired_by_seed": {
            seed: {
                "n": len(seed_rows),
                "tgc_mean": _seed_mean(seed_rows, "tgc"),
                "goal_pass_rate_mean": _seed_mean(seed_rows, "goal_pass_rate"),
            }
            for seed, seed_rows in sorted(by_seed.items())
        },
    }


def _gpr_maps(
    loaded: dict[str, Any], seeds: list[int]
) -> dict[tuple[str, int], dict[str, Any]]:
    seed_set = set(seeds)
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for (task_id, seed), row in loaded["runs"].items():
        if seed not in seed_set:
            continue
        out[(task_id, seed)] = {
            "task_id": task_id,
            "seed": seed,
            "goal_pass_rate": row.get("goal_pass_rate"),
            "tgc": row.get("tgc"),
            "n_planner_calls": row.get("n_planner_calls"),
            "steps": row.get("steps"),
        }
    return out


def _contrast(base: dict, other: dict, field: str) -> dict[str, Any]:
    task = paired_diff(base, other, field, resample="task")
    pair = paired_diff(base, other, field, resample="pair")
    out = native_from_paired_diff(task)
    out["diagnostic_pair_resample"] = native_from_paired_diff(pair)
    out["resample_unit_for_decision"] = RESAMPLE_UNIT
    out["field"] = field
    return out


def main() -> int:
    exec_loaded = load_arm_tree(EXEC_ROOT)
    sft_loaded = load_arm_tree(SFT_ROOT)
    loaded = {"executor_alone": exec_loaded, "sft_plan": sft_loaded}
    exec_tasks = _task_sets(exec_loaded, SEEDS)
    sft_tasks = _task_sets(sft_loaded, SEEDS)
    union_tasks = discover_tasks(loaded, SEEDS)
    only_exec = sorted(exec_tasks - sft_tasks)
    only_sft = sorted(sft_tasks - exec_tasks)
    shared_tasks = sorted(exec_tasks & sft_tasks)

    inventories = {
        label: inventory_arm(label, blob, union_tasks, SEEDS)
        for label, blob in loaded.items()
    }

    exec_rows = list(exec_loaded["runs"].values())
    sft_rows = list(sft_loaded["runs"].values())
    exec_raw = _arm_from_rows(exec_rows)
    sft_raw = _arm_from_rows(sft_rows)

    exec_calls_all_zero = (
        exec_raw["n_planner_calls_missing"] == 0
        and exec_raw["n_planner_calls_nonzero"] == 0
        and exec_raw["n_planner_calls_total"] == 0
        and exec_raw["planner_tokens_total_sum"] == 0
    )

    exec_events = _scan_planner_events(EXEC_ROOT)
    sft_events = _scan_planner_events(SFT_ROOT)

    tgc_contrast = _contrast(
        inventories["sft_plan"]["cleaned"],
        inventories["executor_alone"]["cleaned"],
        "tgc",
    )
    calls_contrast = _contrast(
        inventories["sft_plan"]["cleaned"],
        inventories["executor_alone"]["cleaned"],
        "n_planner_calls",
    )
    steps_contrast = _contrast(
        inventories["sft_plan"]["cleaned"],
        inventories["executor_alone"]["cleaned"],
        "steps",
    )
    gpr_contrast = _contrast(
        _gpr_maps(sft_loaded, SEEDS),
        _gpr_maps(exec_loaded, SEEDS),
        "goal_pass_rate",
    )

    report = {
        "note": (
            "Paired contrast sft_plan − executor_alone. "
            "j10_report.py does not emit this contrast: it only contrasts "
            "sidekick minus other arms, and it requires the full J10 arm set. "
            "Resampling is paired_diff(resample='task'), same as j10_report."
        ),
        "split": "dev",
        "seeds": SEEDS,
        "campaigns": {
            "executor_alone": str(EXEC_ROOT),
            "sft_plan": str(SFT_ROOT),
        },
        "pairing": {
            "n_tasks_executor_alone": len(exec_tasks),
            "n_tasks_sft_plan": len(sft_tasks),
            "n_tasks_shared": len(shared_tasks),
            "n_tasks_union": len(union_tasks),
            "only_in_executor_alone": only_exec,
            "only_in_sft_plan": only_sft,
        },
        "j10_inventory_public": {
            label: _public_inv(inv) for label, inv in inventories.items()
        },
        "files": {
            "executor_alone": _episode_files(EXEC_ROOT),
            "sft_plan": _episode_files(SFT_ROOT),
        },
        "raw_arm_stats": {
            "executor_alone": exec_raw,
            "sft_plan": sft_raw,
        },
        "zero_planner_executor_alone": {
            "all_result_n_planner_calls_zero": exec_calls_all_zero,
            "planner_tokens_total_sum": exec_raw["planner_tokens_total_sum"],
            "usd_total_sum": exec_raw["usd_total_sum"],
            "planner_events": exec_events,
        },
        "sft_plan_planner": {
            "planner_tokens_total_sum": sft_raw["planner_tokens_total_sum"],
            "usd_total_sum": sft_raw["usd_total_sum"],
            "planner_events": sft_events,
        },
        "n_broken_independent": {
            "broken_error_types": sorted(BROKEN),
            "executor_alone": exec_raw["n_broken"],
            "sft_plan": sft_raw["n_broken"],
        },
        "contrasts_sft_plan_minus_executor_alone": {
            "tgc": tgc_contrast,
            "goal_pass_rate": gpr_contrast,
            "n_planner_calls": calls_contrast,
            "steps": steps_contrast,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, default=str) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text, end="")
    if not exec_calls_all_zero:
        print("STOP: executor_alone is not exactly zero planner calls", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
