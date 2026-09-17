#!/usr/bin/env python
"""Recompute the requested published comparisons under pair and task bootstrap."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.setup.hj1_gate import BOOTSTRAP, SEED, load_arm, paired_diff


def _comparison(label: str, base_dir: str, other_dir: str, threshold: float) -> dict:
    base = load_arm(Path(base_dir))
    other = load_arm(Path(other_dir))
    pair = paired_diff(base, other, "tgc", resample="pair")
    task = paired_diff(base, other, "tgc", resample="task")
    base_label, other_label = label.split(" vs ", 1)
    pair_verdict = pair.get("ci95_pp", [None])[0] >= threshold
    task_verdict = task.get("ci95_pp", [None])[0] >= threshold
    return {
        "base": base_label,
        "other": other_label,
        "base_path": base_dir,
        "other_path": other_dir,
        "point_estimate_pp": task.get("diff_pp"),
        "pair_level": pair,
        "task_level": task,
        "gate_rule": f"lower endpoint >= {threshold:g} pp",
        "pair_verdict": pair_verdict,
        "task_verdict": task_verdict,
        "verdict_changed": pair_verdict != task_verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comparison",
        action="append",
        required=True,
        help="comparison label in the form 'base vs other' (repeat three times)",
    )
    parser.add_argument("--base", action="append", required=True)
    parser.add_argument("--other", action="append", required=True)
    parser.add_argument("--threshold", action="append", required=True, type=float)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not (
        len(args.comparison)
        == len(args.base)
        == len(args.other)
        == len(args.threshold)
    ):
        parser.error("each comparison requires a base, other, and threshold")

    comparisons = {
        label: _comparison(label, base_dir, other_dir, threshold)
        for label, base_dir, other_dir, threshold in zip(
            args.comparison, args.base, args.other, args.threshold
        )
    }
    report = {
        "field": "tgc",
        "bootstrap": BOOTSTRAP,
        "seed": SEED,
        "resampling_units": ["pair", "task"],
        "comparisons": comparisons,
        "summary": (
            "[OBSERVED] Each comparison reports the unchanged paired point estimate and both "
            "bootstrap intervals. [OBSERVED] Task-level resampling carries all matched seeds "
            "within a task together."
        ),
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
