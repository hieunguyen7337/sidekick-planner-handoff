#!/usr/bin/env python
"""Parse each pilot config and check the client it builds carries what we expect.

A YAML typo here does not raise: an unknown executor type silently becomes a Mock
client, and a mis-nested chat_template_kwargs silently becomes None and the model
thinks for its whole budget. Both produce plausible, wrong campaigns, so check the
built object rather than the file.
"""
from __future__ import annotations

import sys
from pathlib import Path

from sidekick.runner import load_config, make_executor, make_planner

EXPECTED = {
    "configs/pilot_exec_8b.yaml": ("vllm-executor", {"enable_thinking": False}),
    "configs/pilot_exec_3b.yaml": ("vllm-executor", {"enable_thinking": False}),
    "configs/pilot_planner_alone.yaml": (None, None),
}

failures: list[str] = []
for rel, (want_exec_name, want_ctk) in EXPECTED.items():
    path = Path(rel)
    cfg = load_config(str(path))
    ex = make_executor(cfg)
    pl = make_planner(cfg)
    name = getattr(ex, "name", type(ex).__name__)
    print(f"\n{rel}")
    print(f"  executor -> {name}")
    print(f"  planner  -> {type(pl).__name__}")

    if want_exec_name:
        if name != want_exec_name:
            failures.append(f"{rel}: executor is {name}, expected {want_exec_name}")
        ctk = getattr(ex, "chat_template_kwargs", None)
        print(f"  chat_template_kwargs -> {ctk}")
        if ctk != want_ctk:
            failures.append(f"{rel}: chat_template_kwargs is {ctk!r}, expected {want_ctk!r}")
        print(f"  max_tokens -> {getattr(ex, 'max_tokens', None)}")
        if type(pl).__name__ != "MockPlanner":
            failures.append(f"{rel}: planner is {type(pl).__name__}, expected MockPlanner (must cost nothing)")
    else:
        if type(pl).__name__ != "CodexExecPlanner":
            failures.append(f"{rel}: planner is {type(pl).__name__}, expected CodexExecPlanner")
        print(f"  planner model -> {getattr(getattr(pl, 'cfg', None), 'model', '?')}")

if failures:
    print("\nFAILURES:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("\nall configs OK")
