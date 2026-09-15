from __future__ import annotations

from pathlib import Path

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.agents.verifier import ConstantVerifier
from sidekick.environments.mock_env import MockEnv
from sidekick.systems.loop import MAX_PARSE_RETRIES, RunLimits
from sidekick.trajectories.eventlog import EventLog


def test_max_steps_limit_is_a_counted_failure(run_system) -> None:
    result, events_file, *_ = run_system(
        "executor_alone",
        limits=RunLimits(max_steps=1),
        run_id="limit_steps",
    )
    assert result.success is False
    assert result.error_type == "limit"
    events = list(EventLog.read(events_file))
    assert any(e.error_type == "limit" for e in events)
    assert any(e.event_type == "run_end" for e in events)
    assert any(e.event_type == "evaluate" for e in events)


def test_max_planner_calls_limit(run_system) -> None:
    result, events_file, *_ = run_system(
        "prompt_only",
        limits=RunLimits(max_planner_calls=0),
        run_id="limit_planner",
    )
    assert result.success is False
    assert result.error_type == "limit"
    assert result.n_planner_calls == 0


def test_max_tokens_limit_after_plan(run_system) -> None:
    result, *_ = run_system(
        "prompt_only",
        limits=RunLimits(max_tokens_per_episode=10),
        run_id="limit_tokens",
    )
    assert result.success is False
    assert result.error_type == "limit"


def test_parse_error_is_retried_then_recovers(run_system) -> None:
    # Deliberate change of contract, 2026-09-15. This previously asserted that a parse
    # error ended the episode immediately. That made the score a measure of output-format
    # luck: granite-4.2 emitted five distinct wrappers in one evening, and one unreadable
    # step killed the whole run. Worse for HJ-1, a format-crippled executor scores LOW,
    # which makes the "is there a capability gap" gate easier to pass for the wrong
    # reason. The loop now asks again, bounded by MAX_PARSE_RETRIES.
    result, events_file, *_ = run_system(
        "executor_alone",
        executor=MockExecutor(script=["this is not an action"]),
        run_id="parse_retry_ok",
    )
    assert result.error_type is None
    events = list(EventLog.read(events_file))
    retries = [e for e in events if e.error_type == "parse_error_retry"]
    assert len(retries) == 1, "the one bad reply should be logged as a retry, not a failure"
    assert not [e for e in events if e.error_type == "parse_error"]


def test_parse_error_gives_up_after_the_retry_budget(run_system) -> None:
    result, events_file, *_ = run_system(
        "executor_alone",
        executor=MockExecutor(script=["not an action"] * 10),
        run_id="parse_err",
    )
    assert result.success is False
    assert result.error_type == "parse_error"
    events = list(EventLog.read(events_file))
    retries = [e for e in events if e.error_type == "parse_error_retry"]
    failures = [e for e in events if e.event_type == "error" and e.error_type == "parse_error"]
    # Every retry is logged, so the cost of format non-compliance stays measurable.
    assert len(retries) == MAX_PARSE_RETRIES
    assert len(failures) == 1
    assert events[-1].event_type == "run_end"
    assert events[-1].error_type == "parse_error"


def test_timeout_retry_then_success(run_system) -> None:
    planner = MockPlanner(fail_timeout_once=True)
    result, events_file, *_ = run_system(
        "prompt_only",
        planner=planner,
        run_id="timeout_retry",
    )
    assert result.success is True
    events = list(EventLog.read(events_file))
    timeouts = [e for e in events if e.error_type == "timeout"]
    assert len(timeouts) == 1
    assert timeouts[0].usage is not None
    assert timeouts[0].usage.n_calls == 1
    plan_events = [e for e in events if e.event_type == "plan"]
    assert plan_events
    assert plan_events[0].usage is not None
    assert plan_events[0].usage.n_calls == 2


def test_ask_then_recovery(run_system) -> None:
    executor = MockExecutor(
        script=[
            '```python\nwrite("outbox.txt", "wrong")\n```',
            "ASK_PLANNER: outbox does not match inbox",
            '```python\nwrite("outbox.txt", "hello world")\n```',
            "COMPLETE",
        ]
    )
    result, events_file, *_ = run_system(
        "prompt_only",
        executor=executor,
        run_id="ask_recover",
    )
    assert result.success is True
    assert result.n_asks == 1
    events = list(EventLog.read(events_file))
    assert any(e.event_type == "ask" and e.payload.get("n_asks") == 1 for e in events)


def test_sidekick_gates_ask_at_default_threshold(run_system) -> None:
    executor = MockExecutor(
        script=[
            "ASK_PLANNER: please help",
            '```python\nwrite("outbox.txt", "hello world")\n```',
            "COMPLETE",
        ]
    )
    result, *_ = run_system(
        "sidekick",
        executor=executor,
        verifier=ConstantVerifier(0.5),
        run_id="gate_default",
    )
    assert result.success is True
    assert result.n_asks == 0


def test_sidekick_honours_ask_when_score_exceeds_threshold(run_system) -> None:
    executor = MockExecutor(
        script=[
            "ASK_PLANNER: please help",
            '```python\nwrite("outbox.txt", "hello world")\n```',
            "COMPLETE",
        ]
    )
    result, *_ = run_system(
        "sidekick",
        executor=executor,
        verifier=ConstantVerifier(0.9),
        verifier_threshold=0.5,
        run_id="gate_open",
    )
    assert result.success is True
    assert result.n_asks == 1


def test_fixed_k_reviews_every_step(run_system) -> None:
    result, events_file, *_ = run_system("fixed_k", k=1, run_id="fixed_k1")
    assert result.success is True
    assert result.n_interventions >= 1
    events = list(EventLog.read(events_file))
    assert any(e.event_type == "intervention" and e.payload.get("forced") for e in events)


def test_delete_all_fails_even_if_outbox_rewritten(run_system) -> None:
    executor = MockExecutor(
        script=[
            "```python\ndelete_all()\n```",
            '```python\nwrite("outbox.txt", "hello world")\n```',
            "COMPLETE",
        ]
    )
    result, *_ = run_system("executor_alone", executor=executor, run_id="trap")
    assert result.success is False
    assert result.tgc == 0.0


def test_mock_env_delete_all_and_wrong_file(tmp_path: Path) -> None:
    from sidekick.protocols.schemas import ExecutorAction

    env = MockEnv()
    env.reset("copy_hello", 0)
    h0 = env.snapshot_hash()
    env.step(ExecutorAction(kind="CODE", code='write("notes.txt", "x")', raw_output="x"))
    assert env.evaluate()["success"] is False
    env.step(ExecutorAction(kind="CODE", code="delete_all()", raw_output="d"))
    assert env.evaluate()["success"] is False
    env.step(ExecutorAction(kind="CODE", code='write("outbox.txt", "hello world")', raw_output="w"))
    assert env.evaluate()["success"] is False
    assert env.snapshot_hash() != h0
