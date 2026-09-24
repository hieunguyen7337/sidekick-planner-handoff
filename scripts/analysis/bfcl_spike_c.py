"""Spike (c): depth feasibility for prefix handoff on BFCL, from dev ground-truth trajectories only.

A prefix of depth m hands off when the source trajectory has more than m executed actions
(``prefix_source.HandoffPrefix.handoff_occurred``: effective_m < n_source_actions). The source
trajectory here is the ground truth as the harness would execute it: one CODE block per call and
one COMPLETE per user turn (``bfcl_env.ground_truth_script``), the proxy the scoping doc names
(docs/second_env_scoping_20260923.md:148-151). Two other readings are reported beside it: turn
counts (for turn-aligned depths) and a lower bound where every turn's calls are one block.

Grid rule: m_hi is the deepest m at which at least 70 % of dev entries still hand off; the grid
is {round(m_hi/3), round(2*m_hi/3), m_hi}. Gate: share(m_hi) >= 0.70.
Output: campaign/results/bfcl_spike_c_20260924.report.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from sidekick.environments.bfcl_env import ground_truth_script, load_entries, load_split  # noqa: E402

DEFAULT_OUT = REPO / "campaign" / "results" / "bfcl_spike_c_20260924.report.json"
GATE = 0.70


def share_above(lengths: list[int], m: int) -> float:
    """Share of trajectories longer than m (they still hand off at depth m)."""
    return sum(1 for n in lengths if n > m) / len(lengths)


def propose_grid(lengths: list[int], gate: float = GATE) -> tuple[int, list[int]]:
    """Deepest m with share_above >= gate, and the grid {round(m/3), round(2m/3), m}."""
    m_hi = max((m for m in range(max(lengths) + 1) if share_above(lengths, m) >= gate), default=0)
    grid = sorted({max(1, round(m_hi / 3)), max(1, round(2 * m_hi / 3)), m_hi})
    return m_hi, grid


def _stats(xs: list[int]) -> dict[str, Any]:
    return {"min": min(xs), "max": max(xs), "mean": round(statistics.fmean(xs), 3), "median": statistics.median(xs)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/analysis/bfcl_spike_c.py")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    entries = load_entries()
    dev = load_split()["dev"]
    per_call = [len(ground_truth_script(entries[i])) for i in dev]
    turns = [len(entries[i]["turns"]) for i in dev]
    # Lower bound on actions: one block per turn that has any call, plus the turn's COMPLETE.
    batched = [sum(1 for t in entries[i]["ground_truth"] if t) + len(entries[i]["turns"]) for i in dev]
    m_hi, grid = propose_grid(per_call)
    report = {
        "spike": "c",
        "unit": "bfcl-env",
        "split": "dev",
        "n_dev": len(dev),
        "trajectory": "ground truth, one CODE per call + one COMPLETE per turn",
        "length_stats_per_call": _stats(per_call),
        "length_stats_batched_lower_bound": _stats(batched),
        "turn_stats": _stats(turns),
        "share_handing_off_by_m": {str(m): round(share_above(per_call, m), 4) for m in range(max(per_call) + 1)},
        "share_handing_off_by_m_batched": {str(m): round(share_above(batched, m), 4) for m in range(max(batched) + 1)},
        "grid_rule": "m_hi = deepest m with share >= 0.70; grid = {round(m_hi/3), round(2*m_hi/3), m_hi}",
        "proposed_grid": grid,
        "share_at_grid": {str(m): round(share_above(per_call, m), 4) for m in grid},
        "share_at_grid_batched": {str(m): round(share_above(batched, m), 4) for m in grid},
        "doc_example_grid_steps": {str(m): round(share_above(per_call, m), 4) for m in (2, 4, 6)},
        "turn_aligned_share_more_turns_than": {str(t): round(share_above(turns, t), 4) for t in (1, 2, 3)},
        "gate": {"deepest_m": m_hi, "share": round(share_above(per_call, m_hi), 4), "threshold": GATE,
                 "pass": share_above(per_call, m_hi) >= GATE},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_dev", "proposed_grid", "share_at_grid", "share_at_grid_batched", "gate")}, sort_keys=True))
    return 0 if report["gate"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
