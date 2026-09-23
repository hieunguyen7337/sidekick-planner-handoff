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

# These frozen-pilot configs produced archived results and are not to be edited.
# This allowlist is closed: adding a name to it is a deliberate act.
FROZEN_PILOT_ALLOWLIST = {
    "hj1r_exec8b.yaml",
    "pilot_exec_3b.yaml",
    "pilot_exec_8b.yaml",
    "pilot_fixed_k.yaml",
    "pilot_planner_alone.yaml",
    "pilot_prompt_only.yaml",
    "train_planner_alone.yaml",
}

# label -> (expected executor .name or None for mock, expected planner class name)
EXPECTED = {
    "configs/pilot_exec_8b.yaml": ("vllm-executor", {"enable_thinking": False}),
    "configs/pilot_exec_3b.yaml": ("vllm-executor", {"enable_thinking": False}),
    "configs/pilot_planner_alone.yaml": (None, None),
}


def _prompt_budget_paths(value: object, path: tuple[object, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (key,)
            if key == "max_prompt_tokens":
                yield child_path
            yield from _prompt_budget_paths(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _prompt_budget_paths(child, path + (index,))


def _format_key_path(path: tuple[object, ...]) -> str:
    rendered = ""
    for part in path:
        if isinstance(part, int):
            rendered += f"[{part}]"
        elif rendered:
            rendered += f".{part}"
        else:
            rendered = str(part)
    return rendered


def validate_prompt_budget(cfg: dict, rel: str) -> list[str]:
    """Return config errors for prompt budget placement and value."""
    errors: list[str] = []
    executor = cfg.get("executor")
    expected_path = ("executor", "max_prompt_tokens")

    if "executor" in cfg:
        if not isinstance(executor, dict) or "max_prompt_tokens" not in executor:
            if Path(rel).name not in FROZEN_PILOT_ALLOWLIST:
                errors.append(f"{rel}: missing required key executor.max_prompt_tokens")
        elif type(executor["max_prompt_tokens"]) is not int or executor["max_prompt_tokens"] <= 0:
            errors.append(f"{rel}: executor.max_prompt_tokens must be a positive integer")

    for path in _prompt_budget_paths(cfg):
        if path != expected_path:
            errors.append(
                f"{rel}: max_prompt_tokens is misplaced at {_format_key_path(path)}; "
                "it belongs at executor.max_prompt_tokens"
            )
    return errors

# Class C needs BOTH live at once, which is the combination nothing else checks: a mock on
# either side produces a plausible campaign. A mock planner makes the collaboration arm
# free and meaningless; a mock executor makes it need no GPU and measure nothing.
BOTH_LIVE = {
    "configs/pilot_prompt_only.yaml": ("vllm-executor", "CodexExecPlanner"),
    "configs/pilot_fixed_k.yaml": ("vllm-executor", "CodexExecPlanner"),
    # packet_source wraps CodexExecPlanner; make_planner returns the wrapper.
    "configs/hj4_correction.yaml": ("vllm-executor", "CachedPacketPlanner"),
}

def pending_packet_source(planner_cfg: dict) -> str | None:
    """Reason a config's packet_source may be absent today, or None if it must resolve now.

    A registered design can name, as its packet source, a campaign that a registered
    upstream arm has not produced yet (the J10 prefix arms replay arm 3). Such a config
    declares `planner.packet_source_pending: <reason>`. The exemption holds only while the
    path does not exist: once the upstream arm has written it, it must resolve like any
    other. The runner still aborts on a missing packet (`on_missing: fail`; J10's
    `call_if_planless` also aborts when the source episode is absent), so this can
    never let an episode run against nothing.
    """
    reason = str(planner_cfg.get("packet_source_pending") or "").strip()
    if not reason:
        return None
    if Path(str(planner_cfg.get("packet_source", ""))).exists():
        return None
    return reason


def main() -> int:
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
        failures.extend(validate_prompt_budget(cfg, rel))
        planner_cfg = cfg.get("planner") or {}
        if not planner_cfg.get("packet_source"):
            continue
        pending = pending_packet_source(planner_cfg)
        if pending is not None:
            print(f"\n{rel}")
            print(f"  packet subtree -> PENDING ({pending})")
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
        return 1
    print("\nall configs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
