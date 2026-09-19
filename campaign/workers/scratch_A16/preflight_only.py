#!/usr/bin/env python3
"""PREFLIGHT only: collect jobs, filter to the frozen A16 200-point sample, print
the same PREFLIGHT JSON as branch_counterfactual.run_branches, then exit.

No planner. No GPU. No writes under /scratch/.../results/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "setup"))

import branch_counterfactual as bc  # noqa: E402
from sidekick.runner import load_config  # noqa: E402

POINTS_PATH = REPO / "campaign/workers/scratch_A16/b1_pilot_points.txt"
CAMPAIGN_ROOT = Path("/scratch/n12194778/sidekick/results/hj4_correction_train_20260917")
CFG_PATH = REPO / "configs/hj4_correction.yaml"
OUT_ROOT = REPO / "campaign/workers/scratch_A16/preflight_out_root_unused"
BRANCH_SEEDS = [101, 102, 103, 104]
CAP = 10000


def load_points(path: Path) -> set[tuple[int, str, int]]:
    out: set[tuple[int, str, int]] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        seed_s, task_id, i_s = line.split("/")
        out.add((int(seed_s), task_id, int(i_s)))
    return out


def main() -> None:
    print(f"python={sys.version.replace(chr(10), ' ')}")
    keys = load_points(POINTS_PATH)
    print(f"frozen_points={len(keys)}")
    cfg = load_config(str(CFG_PATH))
    jobs = bc.collect_jobs(
        campaign_root=CAMPAIGN_ROOT,
        out_root=OUT_ROOT,
        split="train",
        branch_seeds=BRANCH_SEEDS,
        resume=False,
        limit=None,
        env_kind="appworld",
        config=cfg,
        prices_path=str(cfg.get("prices") or ""),
        adapter_fallback=(cfg.get("executor") or {}).get("lora_name") or "sft_b",
        retry_errors=True,
        untreated_mode="suppress_next",
    )
    print(f"collect_jobs_unfiltered={len(jobs)}")
    filtered = [
        j
        for j in jobs
        if (int(j["seed"]), str(j["task_id"]), int(j["i"])) in keys
    ]
    print(f"collect_jobs_filtered={len(filtered)}")
    n_points = len({(j["seed"], j["task_id"], j["i"]) for j in filtered})
    print(f"filtered_unique_points={n_points}")
    missing = keys - {(int(j["seed"]), str(j["task_id"]), int(j["i"])) for j in filtered}
    print(f"frozen_keys_missing_from_collect={len(missing)}")
    extra_modes = {j.get("untreated_mode") for j in filtered}
    print(f"untreated_modes={sorted(extra_modes)}")
    planner_factor = int(
        ((cfg.get("limits") or {}).get("max_planner_calls")) or bc.DEFAULT_MAX_PLANNER_CALLS
    )
    preflight = {
        "branches_to_run": len(filtered),
        "per_branch_planner_call_factor": planner_factor,
        "projected_planner_calls": len(filtered) * planner_factor,
        "factor_source": "config limits.max_planner_calls (per-episode cap)",
        "max_planner_calls_total": CAP,
    }
    print("PREFLIGHT " + json.dumps(preflight, sort_keys=True))
    print("no_branches_executed=True")


if __name__ == "__main__":
    main()
