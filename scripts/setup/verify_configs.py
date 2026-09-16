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

WANT_STOP = ["</py>", "</python>", "</tool_call>"]

# label -> (expected executor .name or None for mock, expected planner class name)
EXPECTED = {
    "configs/pilot_exec_8b.yaml": ("vllm-executor", {"enable_thinking": False}),
    "configs/pilot_exec_3b.yaml": ("vllm-executor", {"enable_thinking": False}),
    "configs/pilot_planner_alone.yaml": (None, None),
}

# Class C needs BOTH live at once, which is the combination nothing else checks: a mock on
# either side produces a plausible campaign. A mock planner makes the collaboration arm
# free and meaningless; a mock executor makes it need no GPU and measure nothing.
BOTH_LIVE = {
    "configs/pilot_prompt_only.yaml": ("vllm-executor", "CodexExecPlanner"),
    "configs/pilot_fixed_k.yaml": ("vllm-executor", "CodexExecPlanner"),
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
        stop = getattr(ex, "stop", None)
        print(f"  stop -> {stop}")
        if stop != WANT_STOP:
            failures.append(f"{rel}: stop is {stop!r}, expected {WANT_STOP!r}")
        print(f"  max_tokens -> {getattr(ex, 'max_tokens', None)}")
        if type(pl).__name__ != "MockPlanner":
            failures.append(f"{rel}: planner is {type(pl).__name__}, expected MockPlanner (must cost nothing)")
    else:
        if type(pl).__name__ != "CodexExecPlanner":
            failures.append(f"{rel}: planner is {type(pl).__name__}, expected CodexExecPlanner")
        print(f"  planner model -> {getattr(getattr(pl, 'cfg', None), 'model', '?')}")

for rel, (want_exec_name, want_planner) in BOTH_LIVE.items():
    cfg = load_config(rel)
    ex = make_executor(cfg)
    pl = make_planner(cfg)
    name = getattr(ex, "name", type(ex).__name__)
    print(f"\n{rel}")
    print(f"  executor -> {name}")
    print(f"  planner  -> {type(pl).__name__}")
    print(f"  stop -> {getattr(ex, 'stop', None)}")
    print(f"  chat_template_kwargs -> {getattr(ex, 'chat_template_kwargs', None)}")
    if name != want_exec_name:
        failures.append(f"{rel}: executor is {name}, expected {want_exec_name}")
    if type(pl).__name__ != want_planner:
        failures.append(f"{rel}: planner is {type(pl).__name__}, expected {want_planner}")
    if getattr(ex, "stop", None) != WANT_STOP:
        failures.append(f"{rel}: stop is {getattr(ex, 'stop', None)!r}, expected {WANT_STOP!r}")
    if getattr(ex, "chat_template_kwargs", None) != {"enable_thinking": False}:
        failures.append(f"{rel}: thinking is not disabled")

# Cached packet configs are resolved at planner construction. Keep an ambiguous
# or missing producer subtree visible as a config failure instead of letting a
# later episode discover it after spending executor time.
for path in sorted(Path("configs").glob("*.yaml")):
    rel = str(path)
    cfg = load_config(rel)
    planner_cfg = cfg.get("planner") or {}
    if not planner_cfg.get("packet_source"):
        continue
    try:
        pl = make_planner(cfg)
    except (FileNotFoundError, ValueError) as exc:
        failures.append(f"{rel}: cached packet system is not resolvable: {exc}")
        continue
    print(f"\n{rel}")
    print(f"  packet subtree -> {getattr(pl, 'system', None)}")
    closer = getattr(pl, "close", None)
    if callable(closer):
        closer()

if failures:
    print("\nFAILURES:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("\nall configs OK")
