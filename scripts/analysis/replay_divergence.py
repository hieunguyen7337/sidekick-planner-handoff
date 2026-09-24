#!/usr/bin/env python
"""A prefix replay that cannot pass its own check: the one definition of a divergent key.

J10 A1 Amendment 5 §B, J11 Amendment 2 §B and J12 Amendment 2 (2026-09-25) register one completeness rule
for one crash class, and j10_report.py, j11_report.py and j12_report.py all read it from here.

A prefix replay arm rebuilds the world by re-executing the source episode's first m actions and checks the
last replayed observation's recorded env_state_hash against the live one
(src/sidekick/prefix_source.py:157-175). On a mismatch the episode is a crash whose `error` event carries
``payload.reason == "replay_divergence"`` (src/sidekick/systems/prefix_handoff.py:100-143) and the executor
never acts.

* **Divergent key** -- a ``(task_id, seed)`` under a replay arm whose ``result.json`` has
  ``error_type == "crash"`` and whose ``events.jsonl``, restricted to the LAST attempt (every event from the
  last ``run_start`` on, in file order; none if there is no ``run_start`` -- the rule of
  ``sidekick.replay._events_of_last_attempt``, applied here to raw JSON lines), holds an event with
  ``event_type == "error"`` and ``payload.reason == "replay_divergence"``. No other crash qualifies. The
  first ``result.json`` per key wins, as in ``j10_report.load_arm_tree``.
* **Exclusion** -- a divergent key leaves BOTH arms of every contrast that uses its arm; a contrast between two
  replay arms removes the union of their divergent keys.
* **Cap** -- a contrast that removes at most ``DIVERGENCE_CAP`` = 16 keys (5 % of 336) is read on its
  remaining pairs (``"ok"``); above that it is incomplete (``"over_cap"``).

Pure: json and pathlib only, no pydantic at import.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

Key = tuple[str, int]

REASON = "replay_divergence"
CRASH = "crash"
DIVERGENCE_CAP = 16  # 5 % of the 336-pair matrix: A1 §4.2's cap, J11 §6's, J12 §3's
VERDICT_OK = "ok"
VERDICT_OVER_CAP = "over_cap"
DEFINITION = (
    "a (task_id, seed) of a prefix replay arm whose result.json has error_type == 'crash' and whose "
    "events.jsonl, from the last run_start on, holds an 'error' event with payload.reason == "
    "'replay_divergence'; first result.json per key wins"
)


def events_of_last_attempt(events_path: Path) -> list[dict[str, Any]]:
    """Every JSON-object event from the LAST ``run_start`` on, in file order; [] if there is none.

    sidekick.replay._events_of_last_attempt's rule on raw lines (a retried run appends to the dead
    attempt's log). An unreadable file or line is skipped, never fatal."""
    try:
        text = Path(events_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    for i in range(len(events) - 1, -1, -1):
        if events[i].get("event_type") == "run_start":
            return events[i:]
    return []


def is_divergence_event(ev: Mapping[str, Any]) -> bool:
    payload = ev.get("payload")
    return ev.get("event_type") == "error" and isinstance(payload, dict) and payload.get("reason") == REASON


def last_attempt_diverged(events_path: Path) -> bool:
    """True iff the last attempt's events hold an error event with payload.reason 'replay_divergence'."""
    return any(is_divergence_event(ev) for ev in events_of_last_attempt(events_path))


def _read_row(path: Path) -> Optional[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8").strip()
        row = json.loads(text) if text else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return row if isinstance(row, dict) else None


def divergent_keys(arm_dir: Path) -> list[Key]:
    """Every divergent (task_id, seed) under ``arm_dir``, sorted. A missing directory has none."""
    root = Path(arm_dir)
    if not root.exists():
        return []
    seen: set[Key] = set()
    out: list[Key] = []
    for path in sorted(root.rglob("result.json")):
        row = _read_row(path)
        if row is None or row.get("task_id") is None or row.get("seed") is None:
            continue
        try:
            key = (str(row["task_id"]), int(row["seed"]))
        except (TypeError, ValueError):
            continue
        if key in seen:
            continue  # the first result.json per key wins (load_arm_tree)
        seen.add(key)
        if row.get("error_type") == CRASH and last_attempt_diverged(path.parent / "events.jsonl"):
            out.append(key)
    return sorted(out)


def contrast_exclusion(
    divergent: Mapping[str, Iterable[Key]],
    left: str,
    right: str,
    cap: int = DIVERGENCE_CAP,
) -> tuple[list[Key], str]:
    """(keys removed from both arms of ``left - right``, ``"ok"`` or ``"over_cap"``).

    ``divergent`` maps a REPLAY arm to its divergent keys; an arm it does not name contributes nothing, so a
    contrast of two replay arms removes the union and a contrast with no replay arm removes none (``"ok"``)."""
    excluded = sorted({tuple(k) for arm in (left, right) for k in (divergent.get(arm) or ())})
    return [(str(t), int(s)) for t, s in excluded], (VERDICT_OK if len(excluded) <= cap else VERDICT_OVER_CAP)


def key_label(key: Key) -> str:
    """'seed/task_id', the form the reports already use for key lists (A1 §4.2's planless keys)."""
    return f"{key[1]}/{key[0]}"
