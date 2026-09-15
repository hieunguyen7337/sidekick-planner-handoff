#!/usr/bin/env python
"""Print the supervisor.complete_task API doc and the task's answer expectation.

The loop maps a COMPLETE action to `apis.supervisor.complete_task()` with no
arguments. AppWorld scores answer-returning tasks on a submitted answer, so this
checks whether complete_task takes one and what it is called.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("APPWORLD_ROOT", "/scratch/n12194778/sidekick/appworld")

from appworld import AppWorld, load_task_ids  # noqa: E402

tid = load_task_ids("dev")[1]
world = AppWorld(task_id=tid, experiment_name="probe_complete")
print(f"task: {tid}")
print(f"instruction: {world.task.instruction[:160]}")

docs = world.task.api_docs
entry = docs["supervisor"]["complete_task"]
print("\n=== supervisor.complete_task ===")
print(json.dumps(entry, indent=2, default=str)[:1800])

print("\n=== does the task expect an answer? ===")
for attr in ("answer", "expected_answer", "ground_truth_answer"):
    try:
        print(f"{attr}: {str(getattr(world.task, attr))[:200]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{attr}: <{type(exc).__name__}>")

world.close()
print("\nDONE")
