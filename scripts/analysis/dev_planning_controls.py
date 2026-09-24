#!/usr/bin/env python
"""Plan-side counts for the two planning-control dev arms (brief 20260924_ctrl_planning_controls).

Neither arm's goal_pass means anything until two things are checked per episode, and this script
checks only those; scoring stays with the usual summaries.

* WTP (wrong-task plan): did every episode replay the planned source task? With --map, an
  episode counts as remapped only when its plan event's payload names `packet_task_source`
  == map[task] AND the replayed packet's task_id is that same task.
* SP (self-plan): how many first plans failed or came back empty? The harness scores a plan that
  does not parse as a step-0 `parse_error` (src/sidekick/systems/loop.py:406-423) and adds no
  retry; a packet with no plan_steps is accepted and the episode proceeds. Both are counted.

Asks and interventions are counted too: in either arm an executor ASK_PLANNER reaches the planner
live (hosted luna for WTP), which is the only way WTP can spend a hosted call.

Only the LAST attempt of each episode counts (events after its last `run_start`), as in the
replay layer. Output: one JSON object; nothing is written under /scratch.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sidekick.agents.packet_remap import PACKET_TASK_SOURCE_KEY


def last_attempt_events(path: Path) -> list[dict[str, Any]]:
    """Parsed events after the last `run_start` line; unparseable lines are skipped."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max((i for i, line in enumerate(lines) if '"run_start"' in line), default=-1)
    events = []
    for line in lines[start + 1:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def episode_counts(events: list[dict[str, Any]], task_id: str, task_map: dict[str, str] | None) -> Counter:
    c: Counter = Counter()
    plans = [e for e in events if e.get("event_type") == "plan" and isinstance((e.get("payload") or {}).get("packet"), dict)]
    c["n_ask_events"] = sum(1 for e in events if e.get("event_type") == "ask")
    c["n_intervention_events"] = sum(1 for e in events if e.get("event_type") == "intervention")
    if not plans:
        c["n_no_plan"] = 1
        errs = [e for e in events if e.get("actor") == "planner" and e.get("event_type") == "error" and e.get("step") == 0]
        if errs:
            c[f"n_plan_failed_{errs[0].get('error_type') or 'unknown'}"] = 1
        return c
    payload = plans[-1]["payload"]
    c["n_plan"] = 1
    if not payload["packet"].get("plan_steps"):
        c["n_plan_empty"] = 1
    if task_map is not None:
        want = task_map.get(task_id)
        got = payload.get(PACKET_TASK_SOURCE_KEY)
        if got is None:
            c["n_remap_unrecorded"] = 1
        elif want is not None and got == want and payload["packet"].get("task_id") == want:
            c["n_remap_ok"] = 1
        else:
            c["n_remap_wrong"] = 1
    return c


def campaign_counts(root: Path, task_map: dict[str, str] | None = None) -> dict[str, Any]:
    """Summed per-episode counts over <root>/<system>/<seed>/<task>/events.jsonl.

    The fixed keys are always present, at 0 when nothing was counted; `n_plan_failed_<error>`
    appears per error type seen.
    """
    fixed = ["n_episodes", "n_plan", "n_no_plan", "n_plan_empty", "n_ask_events", "n_intervention_events"]
    if task_map is not None:
        fixed += ["n_remap_ok", "n_remap_unrecorded", "n_remap_wrong"]
    total: Counter = Counter({k: 0 for k in fixed})
    for events_path in sorted(root.glob("*/*/*/events.jsonl")):
        total["n_episodes"] += 1
        total.update(episode_counts(last_attempt_events(events_path), events_path.parent.name, task_map))
    return {"root": str(root), **{k: total[k] for k in sorted(total)}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--campaign-root", required=True, help="<out>/<campaign_id>")
    p.add_argument("--map", help="configs/dev_wrongtask_plan_map.json, for the WTP arm")
    p.add_argument("--out", help="write the JSON here as well as to stdout")
    a = p.parse_args(argv)
    task_map = json.loads(Path(a.map).read_text(encoding="utf-8"))["map"] if a.map else None
    text = json.dumps(campaign_counts(Path(a.campaign_root), task_map), indent=1, sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
