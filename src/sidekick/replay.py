"""Replay recorded CODE/COMPLETE actions and check env_state_hash sequences."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sidekick.environments.base import BaseEnv
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import Event, ExecutorAction
from sidekick.trajectories.eventlog import EventLog

APPWORLD_REPLAY_NOTE = (
    "AppWorldEnv replay can re-execute recorded CODE/COMPLETE actions on a fresh "
    "world with the same task_id. snapshot_hash is sha256 of environment_io (observation "
    "history), not a DB dump, so hidden state that never appears in execute() output "
    "will not be detected. Replay is reliable on MockEnv."
)


@dataclass
class ReplayReport:
    ok: bool
    n_compared: int
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    task_id: str = ""
    seed: int = 0
    system: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "n_compared": self.n_compared,
            "mismatches": self.mismatches,
            "notes": self.notes,
            "task_id": self.task_id,
            "seed": self.seed,
            "system": self.system,
        }


def _action_from_payload(payload: dict[str, Any]) -> ExecutorAction | None:
    kind = payload.get("kind")
    if kind not in ("CODE", "COMPLETE"):
        return None
    try:
        return ExecutorAction(
            kind=kind,
            code=payload.get("code"),
            message=payload.get("message"),
            ask_reason=payload.get("ask_reason"),
            confidence=payload.get("confidence"),
            raw_output=payload.get("raw_output") or "",
        )
    except Exception:
        return None


def replay_prefix(
    events_path: str | Path, k: int, env: BaseEnv
) -> tuple[BaseEnv, list[Event]]:
    """Replay the first ``k`` executed (CODE/COMPLETE) actions of a trajectory.

    Returns ``(world, remaining_events)`` where ``world`` is **still open** —
    the caller owns closing it — and ``remaining_events`` are the gold events
    after the last replayed observation (the gold action for step k+1 and what
    follows), in file order.

    Only events after the LAST ``run_start`` count: a retried run appends to the
    dead attempt's log, so a file can hold two attempts concatenated with
    nothing marking the boundary. Events are ordered by file position, never by
    ``ts`` (frozen by freezegun, identical across events). ``replay()`` does NOT
    do this — it takes the first ``run_start`` (replay.py:74) and steps every
    event in the file, so a two-attempt file double-steps; that is a real bug
    left in place here because ``replay()``'s behaviour must not change.

    ``k`` larger than the number of executed actions is clamped to the
    trajectory length (documented choice: the probe asks for one more step than
    exists sometimes and a clamp is the useful behaviour there; ``remaining`` is
    then empty or holds only trailing non-action events).
    """
    events = _events_of_last_attempt(events_path)
    world = env
    start = next(
        (e for e in reversed(events) if e.event_type == "run_start"), None
    )
    task_id = start.task_id if start is not None else ""
    seed = start.seed if start is not None else 0
    world.reset(task_id, seed)
    executed = 0
    last_obs_idx: int | None = None
    pending: ExecutorAction | None = None
    for idx, event in enumerate(events):
        if event.event_type == "action":
            pending = _action_from_payload(event.payload)
            continue
        if event.event_type == "observation" and pending is not None:
            if pending.kind in ("CODE", "COMPLETE") and executed < k:
                world.step(pending)
                executed += 1
                last_obs_idx = idx
            pending = None
    remaining = events[last_obs_idx + 1 :] if last_obs_idx is not None else []
    return world, remaining


def _events_of_last_attempt(events_path: str | Path) -> list[Event]:
    """All events after the LAST run_start, in file order (empty if none)."""
    events = list(EventLog.read(Path(events_path)))
    for i in range(len(events) - 1, -1, -1):
        if events[i].event_type == "run_start":
            return events[i:]
    return []


def replay(events_path: str | Path, env: BaseEnv | None = None) -> ReplayReport:
    """Re-run recorded env-mutating actions on a fresh env; compare hashes.

    Observation events that follow CODE/COMPLETE are the recorded hash sequence.
    ASK/REPORT/intervention do not mutate the mock world and are skipped.
    """
    path = Path(events_path)
    events = list(EventLog.read(path))
    if not events:
        return ReplayReport(ok=False, n_compared=0, notes=["empty event log"])

    start = next((e for e in events if e.event_type == "run_start"), events[0])
    task_id = start.task_id
    seed = start.seed
    system = start.system
    notes = [APPWORLD_REPLAY_NOTE]
    world = env or MockEnv()
    recorded_reset = start.env_state_hash
    obs = world.reset(task_id, seed)
    mismatches: list[dict[str, Any]] = []
    n_compared = 0
    if recorded_reset and obs.env_state_hash != recorded_reset:
        mismatches.append(
            {
                "where": "reset",
                "recorded": recorded_reset,
                "replayed": obs.env_state_hash,
            }
        )
        n_compared += 1
    elif recorded_reset:
        n_compared += 1

    pending_action: ExecutorAction | None = None
    for event in events:
        if event.event_type == "action":
            pending_action = _action_from_payload(event.payload)
            continue
        if event.event_type == "observation" and pending_action is not None:
            if pending_action.kind in ("CODE", "COMPLETE"):
                replayed = world.step(pending_action)
                n_compared += 1
                recorded_hash = event.env_state_hash
                if recorded_hash and replayed.env_state_hash != recorded_hash:
                    mismatches.append(
                        {
                            "where": f"step {event.step}",
                            "recorded": recorded_hash,
                            "replayed": replayed.env_state_hash,
                            "kind": pending_action.kind,
                        }
                    )
            pending_action = None
            continue
        if event.event_type == "observation" and event.step == 0:
            continue
    world.close()
    return ReplayReport(
        ok=not mismatches,
        n_compared=n_compared,
        mismatches=mismatches,
        notes=notes,
        task_id=task_id,
        seed=seed,
        system=system,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sidekick.replay")
    parser.add_argument("events", help="path to events.jsonl")
    parser.add_argument("--env", choices=["mock", "appworld"], default="mock")
    args = parser.parse_args(argv)
    env: BaseEnv
    if args.env == "appworld":
        from sidekick.environments.appworld_env import AppWorldEnv

        events = list(EventLog.read(args.events))
        start = events[0] if events else None
        experiment = "replay"
        if start is not None:
            experiment = f"{start.run_id}/replay"
        env = AppWorldEnv(experiment_name=experiment)
    else:
        env = MockEnv()
    report = replay(args.events, env)
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
