#!/usr/bin/env python
"""Dev-only plumbing dry-run for the J10 analysis script. Not a result."""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from scripts.analysis.j10_report import main as j10_main

SCRATCH = Path("/scratch/n12194778/sidekick/results")
OUT = REPO / "campaign" / "workers" / "a12_dryrun"
OUT.mkdir(parents=True, exist_ok=True)

# Stand-in mapping: there is no sidekick archive yet. Labels are plumbing, not science.
ARMS = {
    "planner_alone": SCRATCH / "hj1b_planner_20260915",
    "executor_alone": SCRATCH / "hj1r_exec8b_20260916",
    "prompt_only": SCRATCH / "hj1r_prompt_only_20260916",
    "fixed_k": SCRATCH / "hj4b_fixed_k_dev_20260917",
    "sft_plan": SCRATCH / "hj3_sft_plan_20260917",
    "sidekick": SCRATCH / "hj3_sft_plan_20260917",  # STAND-IN
}

COMMON = [
    "--split", "dev",
    "--seeds", "1,2",
    "--expected-n-tasks", "57",
    "--k-matched", "5",
    "--plumbing-check",
]


def arm_args(mapping: dict[str, Path]) -> list[str]:
    out: list[str] = []
    for label, path in mapping.items():
        out.extend(["--arm", f"{label}={path}"])
    return out


def copy_result_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    for path in src.rglob("result.json"):
        dest = dst / path.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def mutate(path: Path, **fields) -> None:
    row = json.loads(path.read_text(encoding="utf-8"))
    row.update(fields)
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")


def run(tag: str, argv: list[str]) -> dict:
    out = OUT / f"{tag}.json"
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = j10_main(argv + ["--out", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    summary = {
        "tag": tag,
        "exit_code": rc,
        "headline": report.get("headline"),
        "incomplete": report.get("incomplete"),
        "hypothesis_decisions_refused": report.get("hypothesis_decisions_refused"),
        "incomplete_reasons": report.get("incomplete_reasons"),
        "missing_and_crashed": report.get("missing_and_crashed"),
        "arms_tgc_mean": {
            k: v.get("tgc_mean") for k, v in (report.get("arms") or {}).items()
        },
        "arms_calls_mean": {
            k: v.get("planner_calls_mean") for k, v in (report.get("arms") or {}).items()
        },
        "H2": (report.get("hypotheses") or {}).get("H2"),
        "H1_status": (report.get("hypotheses") or {}).get("H1", {}).get("status"),
        "H1_holds": (report.get("hypotheses") or {}).get("H1", {}).get("holds"),
        "contrasts": {
            name: {
                "diff_pp": c.get("diff_pp"),
                "ci95_pp": c.get("ci95_pp"),
                "diff": c.get("diff"),
                "ci95": c.get("ci95"),
                "n_pairs": c.get("n_pairs"),
                "n_tasks": c.get("n_tasks"),
                "resample": c.get("resample"),
            }
            for name, c in (report.get("contrasts") or {}).items()
        },
    }
    (OUT / f"{tag}.summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"tag": tag, "exit_code": rc, "headline": summary["headline"]}, indent=2))
    return summary


def main() -> int:
    print("PLUMBING CHECK, NOT A RESULT — writing under", OUT)

    run("A_complete_standin", COMMON + arm_args(ARMS))
    run("B_missing_arm", COMMON + arm_args({k: v for k, v in ARMS.items() if k != "sidekick"}))

    stage_metric = OUT / "stage_missing_metric"
    copy_result_tree(ARMS["sidekick"], stage_metric)
    target = next(stage_metric.rglob("result.json"))
    mutate(target, tgc=None, error_type=None, success=False)
    (OUT / "stage_missing_metric_path.txt").write_text(str(target) + "\n", encoding="utf-8")
    mapping = dict(ARMS)
    mapping["sidekick"] = stage_metric
    run("C_missing_metric", COMMON + arm_args(mapping))

    stage_crash = OUT / "stage_crash"
    copy_result_tree(ARMS["sidekick"], stage_crash)
    target = sorted(stage_crash.rglob("result.json"))[1]
    mutate(target, tgc=None, error_type="crash", success=False)
    (OUT / "stage_crash_path.txt").write_text(str(target) + "\n", encoding="utf-8")
    mapping = dict(ARMS)
    mapping["sidekick"] = stage_crash
    run("D_crashed_episode", COMMON + arm_args(mapping))

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
