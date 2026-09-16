#!/usr/bin/env python
"""Backfill normalized AppWorld goal-pass rates from event logs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _pass_percentage(event: dict[str, Any]) -> float | None:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None
    report = payload.get("report")
    values = [
        report.get("pass_percentage") if isinstance(report, dict) else None,
        payload.get("pass_percentage"),
    ]
    for value in values:
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _last_pass_percentage(events_path: Path) -> float | None:
    """Read the pass percentage from the final run segment in file order."""
    found_run_start = False
    pass_percentage: float | None = None
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event_type") == "run_start":
            found_run_start = True
            pass_percentage = None
            continue
        if found_run_start:
            candidate = _pass_percentage(event)
            if candidate is not None:
                pass_percentage = candidate
    return pass_percentage


def backfill_campaign(campaign_root: Path, *, dry_run: bool = False) -> dict[str, int]:
    """Backfill result files below one campaign root without overwriting values."""
    summary = {
        "n_dirs": 0,
        "n_backfilled": 0,
        "n_already_present": 0,
        "n_no_pass_percentage": 0,
    }
    for result_path in sorted(campaign_root.rglob("result.json")):
        summary["n_dirs"] += 1
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            summary["n_no_pass_percentage"] += 1
            continue
        if not isinstance(result, dict):
            summary["n_no_pass_percentage"] += 1
            continue
        if result.get("goal_pass_rate") is not None:
            summary["n_already_present"] += 1
            continue

        pass_percentage = _last_pass_percentage(result_path.parent / "events.jsonl")
        if pass_percentage is None:
            summary["n_no_pass_percentage"] += 1
            continue

        result["goal_pass_rate"] = pass_percentage / 100.0
        summary["n_backfilled"] += 1
        if not dry_run:
            result_path.write_text(
                json.dumps(result, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = backfill_campaign(args.campaign_root, dry_run=args.dry_run)
    print(" ".join(f"{key}={summary[key]}" for key in summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
