#!/usr/bin/env python3
"""h*: did the executor take control after a replayed planner prefix?

Why this exists
---------------
The prefix arms record ``handoff_occurred = effective_m < n_source_actions``
(src/sidekick/prefix_source.py:184), where ``n_source_actions`` counts only the source episode's
*executed* CODE / COMPLETE actions (:40-51) and ``effective_m = min(m, n_source_actions)`` (:139).
The loop, however, skips its live phase only when the replayed prefix is *terminal*
(src/sidekick/systems/loop.py:743-756): the last replayed observation is ``done`` or the last
replayed action is COMPLETE (``prefix_is_terminal``, :172-180). A source episode that made at most
m executed actions and did not end with done / COMPLETE (it hit a limit, repeated REPORT, or wrote
no plan at all) therefore gives ``handoff_occurred = false`` while the executor still takes control
and acts. That flag is kept everywhere, renamed ``h_flag`` in new outputs; h* is the indicator of
what actually happened.

Definition
----------
h* = 1 iff the loop ran live after the replayed prefix (``skip_live_loop`` false, loop.py:747-749).
It is not recorded, so it is derived from the prefix-arm episode's own ``events.jsonl``, last
attempt only (events from the last ``run_start`` on): h* = 1 iff at least one event that only the
live loop writes exists at step >= effective_m + 1. ``effective_m`` is read from the handoff
record, the system ``report`` event the prefix system writes right after ``run_start``
(src/sidekick/systems/prefix_handoff.py:179-196, payload ``effective_m``).

Which events mark a live step, from the loop's ``emit`` calls:

* The live loop runs ``for step in range(start_step, max_steps + 1)`` with
  ``start_step = max(1, prefix.start_step)`` (loop.py:621, :753) and
  ``prefix.start_step = effective_m + 1`` (prefix_source.py:178). Every event it writes carries
  ``step=step`` (loop.py:758-1182), so a live event sits at step >= effective_m + 1.
* executor: every executor LLM call ends in an executor ``action`` (loop.py:598-605) or an executor
  ``error`` -- timeout (:546-553), parse error after the retries (:563-570), parse-error retry
  (:573-580); asks (``ask``, :1053-1062, :1087-1096, :1112-1121) and REPORT (``report``,
  :1130-1136) are executor events of the live loop too. No executor event is written anywhere else.
  So a first live step that fails to parse still gives h* = 1.
* system ``error``: the step / token / planner-call limits (:354-360, :760-766, :1176-1182 --
  the max_steps error is written only when ``not skip_live_loop``), a planner-call failure
  (:453-459) and "no executor" (:504). The one system error written after the loop regardless of
  ``skip_live_loop`` is the crash handler (:1206-1212), whose payload alone carries ``exc_type``;
  it is excluded. So a first live step that hits a limit still gives h* = 1.
* environment ``observation`` / ``error`` from a live env.step (:1146-1160), and a ``local``-horizon
  ``evaluate`` (:786-792); planner ``intervention`` / ``action`` / ``handoff`` / ``error`` from live
  planner calls (:373-441, :823-1004, :1074-1081, :476-481) and the action review
  (src/sidekick/systems/action_review_gate.py:77-88). Each is preceded by, or is itself, a
  live step; they are listed so that no live-loop event is missed.

Excluded: ``run_start`` and the step-0 observation (:682-695), the handoff record (step
effective_m), the final ``evaluate`` (:1196-1202) and ``run_end`` (:1238-1245). The last two carry
``step=steps_taken``, which on a skipped live phase is the last replayed observation's step
(:750-751) and can exceed effective_m when the source's prefix held REPORT / ASK steps -- which is
why the test is on (actor, event_type) and not on the step alone.

One edge the event rule reads differently from ``skip_live_loop``: a token limit reached by the
replayed prefix itself is written at step 0 before the loop (:733-740), and the loop then stops at
its first iteration without acting. The executor never takes control there, so h* = 0; the loader
reports such an episode as ``pre_loop_limit`` so that it is counted rather than hidden.

Everything here is pure file reading; no model is called and nothing under ``src/`` is imported.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable, Optional

Key = tuple  # (task_id, seed)

HSTAR_NAME = "h_star"
HFLAG_NAME = "h_flag"
DEFINITION = ("h* = 1 iff the prefix arm's last attempt holds an event only the live loop writes at step "
              ">= effective_m + 1 (scripts/analysis/handoff_control.py); effective_m from the handoff "
              "record's payload")
FLAG_DEFINITION = ("h_flag = handoff_occurred of the last `report` event of the last attempt "
                   "(effective_m < n_source_actions, src/sidekick/prefix_source.py:184)")

# (actor -> event types) that only the live loop writes. Conditions beyond the pair are in is_live_event.
LIVE_EVENT_TYPES: dict[str, frozenset[str]] = {
    "executor": frozenset({"action", "error", "ask", "report"}),
    "system": frozenset({"error"}),
    "environment": frozenset({"observation", "error", "evaluate"}),
    "planner": frozenset({"intervention", "action", "handoff", "error", "action_review"}),
}


def _get(ev: Any, name: str) -> Any:
    if isinstance(ev, Mapping):
        return ev.get(name)
    return getattr(ev, name, None)


def _payload(ev: Any) -> dict[str, Any]:
    payload = _get(ev, "payload")
    return payload if isinstance(payload, Mapping) else {}


def _step(ev: Any) -> Optional[int]:
    step = _get(ev, "step")
    if isinstance(step, bool) or not isinstance(step, int):
        return None
    return step


def last_attempt(events: Iterable[Any]) -> list[Any]:
    """Events from the last ``run_start`` on (all of them if there is none), in file order.

    Idempotent: a list that already starts at its only run_start is returned unchanged."""
    evs = list(events)
    start = 0
    for i, ev in enumerate(evs):
        if _get(ev, "event_type") == "run_start":
            start = i
    return evs[start:]


def is_live_event(ev: Any) -> bool:
    """True for an (actor, event_type) only the live loop writes (see the module docstring)."""
    actor, etype = _get(ev, "actor"), _get(ev, "event_type")
    if etype not in LIVE_EVENT_TYPES.get(actor, frozenset()):
        return False
    payload = _payload(ev)
    if actor == "system":
        return "exc_type" not in payload  # the post-loop crash handler, loop.py:1206-1212
    if actor == "environment" and etype == "evaluate":
        return payload.get("horizon") == "local"  # the in-loop local evaluate, loop.py:786-792
    return True


def executor_took_control(events: Iterable[Any], effective_m: int) -> bool:
    """h*: True iff the last attempt holds a live-loop event at step >= effective_m + 1.

    ``events`` are an episode's events (dicts as read from events.jsonl, or objects with the same
    attributes); only the last attempt is read. ``effective_m`` is the handoff record's."""
    threshold = int(effective_m) + 1
    for ev in last_attempt(events):
        step = _step(ev)
        if step is not None and step >= threshold and is_live_event(ev):
            return True
    return False


def first_live_event(events: Iterable[Any], effective_m: int) -> Optional[dict[str, Any]]:
    threshold = int(effective_m) + 1
    for ev in last_attempt(events):
        step = _step(ev)
        if step is not None and step >= threshold and is_live_event(ev):
            return {"step": step, "actor": _get(ev, "actor"), "event_type": _get(ev, "event_type"),
                    "error_type": _get(ev, "error_type")}
    return None


def handoff_record(events: Iterable[Any]) -> Optional[dict[str, Any]]:
    """Payload of the last ``report`` event of the last attempt that carries ``effective_m``."""
    record = None
    for ev in last_attempt(events):
        payload = _payload(ev)
        if _get(ev, "event_type") == "report" and payload.get("effective_m") is not None:
            record = dict(payload)
    return record


def last_report_flag(events: Iterable[Any]) -> Optional[bool]:
    """h_flag: handoff_occurred of the last ``report`` event of the last attempt, or None --
    exactly j10_report._last_report_handoff and j16_robustness.episode_facts."""
    flag: Optional[bool] = None
    for ev in last_attempt(events):
        payload = _get(ev, "payload")
        if _get(ev, "event_type") == "report" and isinstance(payload, Mapping):
            value = payload.get("handoff_occurred")
            flag = None if value is None else bool(value)
    return flag


def pre_loop_limit(events: Iterable[Any]) -> bool:
    """A system ``limit`` error at step 0 of the last attempt (loop.py:733-740)."""
    for ev in last_attempt(events):
        if (_get(ev, "actor") == "system" and _get(ev, "event_type") == "error"
                and _get(ev, "error_type") == "limit" and _step(ev) == 0):
            return True
    return False


def read_events(path: Path) -> list[dict[str, Any]]:
    """Every JSON object line of an events.jsonl; unreadable lines are skipped (as j16 reads them)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
    return out


def control_from_events(events: Iterable[Any]) -> dict[str, Any]:
    """h*, h_flag and the facts behind them for one episode's events."""
    evs = last_attempt(events)
    record = handoff_record(evs)
    flag = last_report_flag(evs)
    out: dict[str, Any] = {
        HSTAR_NAME: None,
        HFLAG_NAME: flag,
        "effective_m": None,
        "n_source_actions": None,
        "record_handoff_occurred": None,
        "source_campaign": None,
        "first_live_event": None,
        "pre_loop_limit": pre_loop_limit(evs),
        "status": "no_handoff_record",
    }
    if record is None:
        return out
    eff = int(record["effective_m"])
    first = first_live_event(evs, eff)
    out.update({
        HSTAR_NAME: first is not None,
        "effective_m": eff,
        "n_source_actions": None if record.get("n_source_actions") is None else int(record["n_source_actions"]),
        "record_handoff_occurred": None if record.get("handoff_occurred") is None
        else bool(record["handoff_occurred"]),
        "source_campaign": record.get("source_campaign"),
        "first_live_event": first,
        "status": "ok",
    })
    return out


def episode_control(ep_dir: Path) -> dict[str, Any]:
    """control_from_events for ``<ep_dir>/events.jsonl``."""
    path = Path(ep_dir) / "events.jsonl"
    if not path.is_file():
        out = control_from_events([])
        out["status"] = "no_events"
        return out
    return control_from_events(read_events(path))


def _result_key(path: Path) -> Optional[tuple[str, int]]:
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(row, dict) or row.get("task_id") is None or row.get("seed") is None:
        return None
    try:
        return (str(row["task_id"]), int(row["seed"]))
    except (TypeError, ValueError):
        return None


def arm_control(root: Path, seeds: Optional[Iterable[int]] = None) -> dict[tuple[str, int], dict[str, Any]]:
    """(task_id, seed) -> episode_control for every result.json under a prefix arm.

    The first result.json per key wins (sorted paths), as j10_report.a1_handoff_flags reads them."""
    allowed = None if seeds is None else {int(s) for s in seeds}
    out: dict[tuple[str, int], dict[str, Any]] = {}
    root = Path(root)
    if not root.exists():
        return out
    for path in sorted(root.rglob("result.json")):
        key = _result_key(path)
        if key is None or key in out or (allowed is not None and key[1] not in allowed):
            continue
        out[key] = episode_control(path.parent)
    return out


def hstar_flags(root: Path, seeds: Optional[Iterable[int]] = None) -> dict[tuple[str, int], Optional[bool]]:
    """(task_id, seed) -> h* (None when the episode has no handoff record): the shape of
    j10_report.a1_handoff_flags, so every flag-taking helper takes it unchanged."""
    return {k: v[HSTAR_NAME] for k, v in arm_control(root, seeds).items()}


def control_counts(controls: Mapping[Any, Mapping[str, Any]], keys: Optional[Iterable[Any]] = None) -> dict[str, Any]:
    """The per-arm count table: n h_flag true, n live-but-unflagged, n terminal (h* = 0), plus the
    cells that should be empty (h_flag true yet terminal; h* undefined)."""
    ks = sorted(controls) if keys is None else sorted(keys)
    n = n_flag_true = n_live_unflagged = n_terminal = n_missing = n_flag_true_terminal = 0
    n_flag_missing = n_pre_loop_limit = n_hstar = 0
    live_unflagged_keys: list[list[Any]] = []
    for k in ks:
        c = controls.get(k)
        n += 1
        if c is None:
            n_missing += 1
            continue
        hs, hf = c.get(HSTAR_NAME), c.get(HFLAG_NAME)
        n_flag_true += int(hf is True)
        n_flag_missing += int(hf is None)
        n_pre_loop_limit += int(bool(c.get("pre_loop_limit")))
        if hs is None:
            n_missing += 1
        elif hs:
            n_hstar += 1
            if hf is not True:
                n_live_unflagged += 1
                live_unflagged_keys.append([k[0], k[1]] if isinstance(k, tuple) else k)
        else:
            n_terminal += 1
            n_flag_true_terminal += int(hf is True)
    return {
        "n": n,
        "n_h_flag_true": n_flag_true,
        "n_live_but_unflagged": n_live_unflagged,
        "n_terminal": n_terminal,
        "n_hstar_true": n_hstar,
        "n_hstar_undefined": n_missing,
        "n_h_flag_true_but_terminal": n_flag_true_terminal,
        "n_h_flag_missing": n_flag_missing,
        "n_pre_loop_limit": n_pre_loop_limit,
        "live_but_unflagged_keys": live_unflagged_keys,
        "definition": DEFINITION,
        "h_flag": FLAG_DEFINITION,
    }


def synthetic_cases() -> dict[str, dict[str, Any]]:
    """Event sequences whose h* is known from the loop's code, shaped as the loop writes them.

    * planless: no plan, so effective_m = n_source_actions = 0 and the flag is false, yet the
      executor runs the whole episode (validation case 3: h* = 1).
    * terminal: the replayed prefix ended the source episode (validation case 4: h* = 0). The
      final evaluate / run_end sit at step 10 > effective_m = 9, as they do when the source's prefix
      held a REPORT step (loop.py:750-751), so a rule on the step alone would call it live.
    * parse_error_first: the first live step fails to parse after its retries (h* = 1).
    * limit_first: the first live step hits the planner-call limit after an ask (h* = 1).
    """
    def ev(step: int, actor: str, etype: str, payload: Optional[dict[str, Any]] = None,
           error: Optional[str] = None) -> dict[str, Any]:
        return {"step": step, "actor": actor, "event_type": etype, "payload": payload or {},
                "error_type": error}

    def head(eff: int, n_src: int) -> list[dict[str, Any]]:
        return [ev(0, "system", "run_start", {"prefix": {"start_step": eff + 1}}),
                ev(eff, "system", "report", {"effective_m": eff, "n_source_actions": n_src,
                                             "handoff_occurred": eff < n_src}),
                ev(0, "environment", "observation", {"text": "", "done": False})]

    def tail(step: int, error: Optional[str] = None) -> list[dict[str, Any]]:
        return [ev(step, "environment", "evaluate", {"success": False}),
                ev(step, "system", "run_end", {}, error)]

    return {
        "planless": {"effective_m": 0, "expected_h_star": True, "expected_h_flag": False, "events": [
            *head(0, 0),
            ev(1, "executor", "action", {"kind": "CODE", "code": "print(1)"}),
            ev(1, "environment", "observation", {"text": "1", "done": False, "kind": "CODE"}),
            ev(2, "executor", "action", {"kind": "COMPLETE"}),
            ev(2, "environment", "observation", {"text": "", "done": True, "kind": "COMPLETE"}),
            *tail(2)]},
        "terminal": {"effective_m": 9, "expected_h_star": False, "expected_h_flag": False, "events": [
            *head(9, 9), *tail(10)]},
        "parse_error_first": {"effective_m": 11, "expected_h_star": True, "expected_h_flag": False, "events": [
            *head(11, 11),
            ev(12, "executor", "error", {"raw_output": "?", "attempt": 1}, "parse_error_retry"),
            ev(12, "executor", "error", {"raw_output": "?", "attempts": 3}, "parse_error"),
            *tail(12, "parse_error")]},
        "limit_first": {"effective_m": 6, "expected_h_star": True, "expected_h_flag": True, "events": [
            *head(6, 8),
            ev(7, "executor", "ask", {"n_asks": 1, "ask_reason": "?", "gated": False}),
            ev(7, "system", "error", {"limit": "max_planner_calls", "n_planner_calls": 81}, "limit"),
            *tail(7, "limit")]},
    }


def check_synthetic_cases() -> dict[str, Any]:
    """Each synthetic case's h* and h_flag against its expected value (validation cases 3-4)."""
    rows = {}
    for name, case in synthetic_cases().items():
        c = control_from_events(case["events"])
        rows[name] = {"effective_m": c["effective_m"], HSTAR_NAME: c[HSTAR_NAME], HFLAG_NAME: c[HFLAG_NAME],
                      "direct": executor_took_control(case["events"], case["effective_m"]),
                      "expected_h_star": case["expected_h_star"],
                      "holds": (c[HSTAR_NAME] is case["expected_h_star"]
                                and executor_took_control(case["events"], case["effective_m"]) is case["expected_h_star"]
                                and c[HFLAG_NAME] is case["expected_h_flag"])}
    return {"cases": rows, "all_hold": all(r["holds"] for r in rows.values())}
