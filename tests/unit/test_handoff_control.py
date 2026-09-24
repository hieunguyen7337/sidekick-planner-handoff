"""scripts/analysis/handoff_control.py: h*, the executor took control after a replayed prefix.

Every fixture is an event sequence shaped as src/sidekick/systems/loop.py writes it for a prefix arm:
run_start (step 0), the prefix system's handoff record (a system `report` at step effective_m), the
step-0 observation, then the live loop's events from step effective_m + 1, then evaluate / run_end
at steps_taken. The answer of each is known from the loop's code.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import handoff_control as hc


def ev(step, actor, etype, payload=None, error=None):
    return {"step": step, "actor": actor, "event_type": etype, "payload": payload or {}, "error_type": error}


def head(eff, n_src, flag=None):
    flag = eff < n_src if flag is None else flag
    return [ev(0, "system", "run_start"),
            ev(eff, "system", "report", {"effective_m": eff, "n_source_actions": n_src, "handoff_occurred": flag,
                                         "source_campaign": "/r/hj13_planner_alone_cap81_20260923"}),
            ev(0, "environment", "observation", {"text": "", "done": False})]


def tail(step, error=None):
    return [ev(step, "environment", "evaluate", {"success": False}), ev(step, "system", "run_end", {}, error)]


# ---- validation cases 3 and 4, and the first-live-step failures -----------------------------------------

def test_planless_key_is_live_although_the_flag_is_false():
    # No plan: effective_m = n_source_actions = 0, flag false; the executor runs the episode from step 1.
    events = [*head(0, 0), ev(1, "executor", "action", {"kind": "CODE"}),
              ev(1, "environment", "observation", {"done": False}), *tail(1)]
    assert hc.executor_took_control(events, 0) is True
    c = hc.control_from_events(events)
    assert (c["h_star"], c["h_flag"], c["effective_m"], c["n_source_actions"]) == (True, False, 0, 0)
    assert c["first_live_event"] == {"step": 1, "actor": "executor", "event_type": "action", "error_type": None}


def test_terminal_prefix_is_not_live_even_when_evaluate_sits_past_effective_m():
    # skip_live_loop: steps_taken = the last replayed observation's step (loop.py:750-751), which is 10
    # when the source's prefix held a REPORT step; evaluate and run_end at 10 are not live events.
    events = [*head(9, 9), *tail(10)]
    assert hc.executor_took_control(events, 9) is False
    assert hc.control_from_events(events)["h_star"] is False


def test_a_first_live_step_that_fails_to_parse_is_live():
    events = [*head(11, 11), ev(12, "executor", "error", {"attempt": 1}, "parse_error_retry"),
              ev(12, "executor", "error", {"attempts": 3}, "parse_error"), *tail(12, "parse_error")]
    assert hc.executor_took_control(events, 11) is True


def test_a_first_live_step_that_hits_a_limit_or_times_out_is_live():
    limit = [*head(6, 8), ev(7, "system", "error", {"limit": "max_planner_calls"}, "limit"), *tail(7, "limit")]
    assert hc.executor_took_control(limit, 6) is True
    timeout = [*head(6, 8), ev(7, "executor", "error", {"detail": "t"}, "timeout"), *tail(7, "timeout")]
    assert hc.executor_took_control(timeout, 6) is True


def test_the_post_loop_crash_handler_is_not_a_live_event():
    # loop.py:1206-1212: written at steps_taken whatever skip_live_loop was; its payload carries exc_type.
    events = [*head(9, 9), ev(10, "system", "error", {"detail": "boom", "exc_type": "RuntimeError"}, "crash"),
              ev(10, "system", "run_end", {}, "crash")]
    assert hc.executor_took_control(events, 9) is False


def test_live_events_below_the_threshold_do_not_count():
    events = [*head(9, 12), ev(9, "executor", "action", {"kind": "CODE"}), *tail(9)]
    assert hc.executor_took_control(events, 9) is False
    assert hc.executor_took_control(events, 8) is True


def test_only_the_last_attempt_is_read():
    first = [*head(6, 8), ev(7, "executor", "action", {"kind": "CODE"})]
    second = [*head(6, 6), *tail(6)]
    assert hc.executor_took_control(first + second, 6) is False
    assert hc.executor_took_control(second + first, 6) is True


def test_the_synthetic_cases_all_hold():
    out = hc.check_synthetic_cases()
    assert out["all_hold"] is True
    assert {n: r["h_star"] for n, r in out["cases"].items()} == {
        "planless": True, "terminal": False, "parse_error_first": True, "limit_first": True}


# ---- the flag, the record and the edges ----------------------------------------------------------------

def test_h_flag_is_the_last_report_event_as_j10_reads_it():
    # An executor REPORT after the handoff record: the flag (last `report` event) reads None, exactly
    # as j10_report._last_report_handoff does, while h* still reads effective_m from the record.
    events = [*head(6, 8), ev(7, "executor", "report", {"message": "done?"}), *tail(7)]
    c = hc.control_from_events(events)
    assert c["h_flag"] is None and c["record_handoff_occurred"] is True
    assert c["h_star"] is True and c["effective_m"] == 6


def test_no_handoff_record_gives_an_undefined_h_star():
    events = [ev(0, "system", "run_start"), ev(1, "executor", "action", {"kind": "CODE"}), *tail(1)]
    c = hc.control_from_events(events)
    assert c["h_star"] is None and c["status"] == "no_handoff_record"


def test_a_pre_loop_token_limit_is_reported_and_is_not_control():
    # loop.py:733-740: the limit is written at step 0 and the loop stops before the executor acts.
    events = [*head(6, 8), ev(0, "system", "error", {"limit": "max_tokens_per_episode"}, "limit"), *tail(0, "limit")]
    c = hc.control_from_events(events)
    assert c["h_star"] is False and c["pre_loop_limit"] is True


def test_event_objects_are_read_like_dicts():
    from sidekick.protocols.schemas import Event

    base = {"run_id": "r", "task_id": "t_1", "system": "prefix_handoff", "seed": 1, "ts": "2026-01-01T00:00:00Z"}
    objs = [Event(**base, **e) for e in [*head(6, 8), ev(7, "executor", "action", {"kind": "CODE"}), *tail(7)]]
    assert hc.executor_took_control(objs, 6) is True
    assert hc.executor_took_control(objs[:3] + objs[-2:], 6) is False


# ---- loaders and the count table ------------------------------------------------------------------------

def write(root: Path, task: str, seed: int, events, *, result=True):
    d = root / str(seed) / task
    d.mkdir(parents=True, exist_ok=True)
    if result:
        (d / "result.json").write_text(json.dumps({"task_id": task, "seed": seed}), encoding="utf-8")
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events) + "{truncated", encoding="utf-8")


def test_arm_control_counts_and_flags(tmp_path: Path):
    root = tmp_path / "arm" / "prefix_handoff"
    live = [*head(11, 13), ev(12, "executor", "action", {"kind": "CODE"}), *tail(12)]
    live_unflagged = [*head(11, 11), ev(12, "executor", "action", {"kind": "CODE"}), *tail(12)]
    terminal = [*head(11, 11), *tail(11)]
    write(root, "s1_1", 1, live)
    write(root, "s1_2", 1, live_unflagged)
    write(root, "s1_3", 1, terminal)
    write(root, "s2_1", 2, terminal)
    write(root, "s2_2", 3, live)  # seed 3: filtered when seeds = (1, 2)
    ctl = hc.arm_control(root, seeds=(1, 2))
    assert sorted(ctl) == [("s1_1", 1), ("s1_2", 1), ("s1_3", 1), ("s2_1", 2)]
    assert hc.hstar_flags(root, seeds=(1, 2)) == {("s1_1", 1): True, ("s1_2", 1): True,
                                                  ("s1_3", 1): False, ("s2_1", 2): False}
    counts = hc.control_counts(ctl)
    assert (counts["n"], counts["n_h_flag_true"], counts["n_live_but_unflagged"], counts["n_terminal"]) == (4, 1, 1, 2)
    assert counts["n_h_flag_true_but_terminal"] == 0 and counts["n_hstar_undefined"] == 0
    assert counts["live_but_unflagged_keys"] == [["s1_2", 1]]
    # A key the table is asked for but the arm lacks counts as undefined, not as silently dropped.
    assert hc.control_counts(ctl, keys=[("s1_1", 1), ("zz_9", 1)])["n_hstar_undefined"] == 1
    assert hc.arm_control(tmp_path / "absent") == {}


def test_episode_without_events_is_undefined(tmp_path: Path):
    d = tmp_path / "ep"
    d.mkdir()
    c = hc.episode_control(d)
    assert c["h_star"] is None and c["status"] == "no_events"


@pytest.mark.parametrize("etype", ["evaluate", "run_end", "run_start"])
def test_post_and_pre_loop_bookkeeping_is_never_live(etype: str):
    actor = {"evaluate": "environment", "run_end": "system", "run_start": "system"}[etype]
    assert hc.is_live_event(ev(20, actor, etype)) is False
    assert hc.is_live_event(ev(20, "environment", "evaluate", {"horizon": "local"})) is True
