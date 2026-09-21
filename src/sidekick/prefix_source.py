"""Build a replayed planner prefix for the prefix_handoff system.

Hash check limitation, quoting replay.py:15-20:

    "AppWorldEnv replay can re-execute recorded CODE/COMPLETE actions on a fresh
    world with the same task_id. snapshot_hash is sha256 of environment_io (observation
    history), not a DB dump, so hidden state that never appears in execute() output
    will not be detected. Replay is reliable on MockEnv."

``snapshot_hash`` therefore detects **visible** divergence only. It is not proof
that the hidden world / database state matches the recording.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from sidekick.environments.base import BaseEnv
from sidekick.protocols.schemas import Event, Usage
from sidekick.replay import _action_from_payload, _events_of_last_attempt, replay_prefix

if TYPE_CHECKING:
    from sidekick.systems.loop import EpisodePrefix


@dataclass
class HandoffPrefix:
    prefix: EpisodePrefix | None
    env: BaseEnv  # still open, stepped to the handoff point
    effective_m: int  # actions actually replayed (clamped)
    n_source_actions: int  # executed actions in the source episode
    handoff_occurred: bool  # effective_m < n_source_actions
    hash_ok: bool
    replayed_planner_tokens: int
    broken_reason: str | None  # None, "missing_source", "replay_divergence", "replay_error"
    notes: list[str] = field(default_factory=list)


def _n_executed_actions(events: list[Event]) -> int:
    n = 0
    pending = None
    for event in events:
        if event.event_type == "action":
            pending = _action_from_payload(event.payload)
            continue
        if event.event_type == "observation" and pending is not None:
            if pending.kind in ("CODE", "COMPLETE"):
                n += 1
            pending = None
    return n


def _events_before_first_executed(events: list[Event]) -> list[Event]:
    """Prefix when m==0: everything before the first executed CODE/COMPLETE.

    ``replay_prefix`` returns ``remaining=[]`` when ``k=0`` because
    ``last_obs_idx`` stays None (replay.py:107), so "attempt minus remaining"
    would wrongly be the whole episode.
    """
    pending = None
    pending_idx: int | None = None
    for i, event in enumerate(events):
        if event.event_type == "action":
            pending = _action_from_payload(event.payload)
            pending_idx = i
            continue
        if event.event_type == "observation" and pending is not None:
            if pending.kind in ("CODE", "COMPLETE"):
                return events[: pending_idx]
            pending = None
            pending_idx = None
    return list(events)


def _prefix_slice(events: list[Event], remaining: list[Event], effective_m: int) -> list[Event]:
    if effective_m <= 0:
        return _events_before_first_executed(events)
    n_rem = len(remaining)
    if n_rem:
        return events[: len(events) - n_rem]
    return list(events)


def _usage_tokens(usage: Usage | None, notes: list[str], *, loc: str) -> int:
    """input + output + reasoning; never add cached_input_tokens; never guess."""
    if usage is None:
        notes.append(f"{loc}: usage missing; counted as 0")
        return 0
    for name in (
        "input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
        "cached_input_tokens",
    ):
        if name not in usage.model_fields_set:
            notes.append(f"{loc}: usage.{name} absent; treated as 0")
    return int(usage.input_tokens) + int(usage.output_tokens) + int(usage.reasoning_output_tokens)


def _replayed_planner_tokens(prefix_events: list[Event], notes: list[str]) -> int:
    total = 0
    for i, event in enumerate(prefix_events):
        if event.actor != "planner":
            continue
        total += _usage_tokens(event.usage, notes, loc=f"prefix[{i}] step={event.step} {event.event_type}")
    return total


def build_handoff_prefix(
    source_campaign: str | Path,
    source_system: str,
    task_id: str,
    seed: int,
    m: int,
    env: BaseEnv,
) -> HandoffPrefix:
    from sidekick.systems.loop import EpisodePrefix

    notes: list[str] = []
    events_path = (
        Path(source_campaign) / str(source_system) / str(seed) / str(task_id) / "events.jsonl"
    )
    if not events_path.is_file():
        return HandoffPrefix(
            prefix=None,
            env=env,
            effective_m=0,
            n_source_actions=0,
            handoff_occurred=False,
            hash_ok=False,
            replayed_planner_tokens=0,
            broken_reason="missing_source",
            notes=notes,
        )

    events = _events_of_last_attempt(events_path)
    n_source_actions = _n_executed_actions(events)
    effective_m = min(max(0, int(m)), n_source_actions)

    try:
        world, remaining = replay_prefix(events_path, m, env)
    except Exception as exc:
        notes.append(f"{type(exc).__name__}: {exc}")
        return HandoffPrefix(
            prefix=None,
            env=env,
            effective_m=effective_m,
            n_source_actions=n_source_actions,
            handoff_occurred=effective_m < n_source_actions,
            hash_ok=False,
            replayed_planner_tokens=0,
            broken_reason="replay_error",
            notes=notes,
        )

    prefix_events = _prefix_slice(events, remaining, effective_m)
    last_obs = next((e for e in reversed(prefix_events) if e.event_type == "observation"), None)
    live_hash = world.snapshot_hash()
    hash_ok = True
    broken_reason: str | None = None
    if last_obs is None:
        if effective_m > 0:
            hash_ok = False
            broken_reason = "replay_divergence"
            notes.append("no observation event in prefix to hash-check")
    else:
        recorded = last_obs.env_state_hash
        if recorded is None:
            notes.append("env_state_hash absent on last replayed observation; treated as missing")
            hash_ok = False
            broken_reason = "replay_divergence"
        elif recorded != live_hash:
            hash_ok = False
            broken_reason = "replay_divergence"

    tokens = _replayed_planner_tokens(prefix_events, notes)
    prefix = EpisodePrefix(events=prefix_events, start_step=effective_m + 1)
    return HandoffPrefix(
        prefix=prefix,
        env=world,
        effective_m=effective_m,
        n_source_actions=n_source_actions,
        handoff_occurred=effective_m < n_source_actions,
        hash_ok=hash_ok,
        replayed_planner_tokens=tokens,
        broken_reason=broken_reason,
        notes=notes,
    )
