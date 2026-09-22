"""Prefix terminal guard (X18). MockEnv + scripted MockExecutor; no AppWorld, no network."""
from __future__ import annotations

from pathlib import Path

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction
from sidekick.systems.loop import EpisodePrefix, RunLimits, SystemPolicy, run_episode
from sidekick.trajectories.eventlog import EventLog

TASK_ID = "copy_hello"
SEED = 1
TS = "2023-05-18T12:00:00+00:00"
SYSTEM = "prefix_handoff"

PACKET = DelegationPacket(
    packet_id="pkt-x18-1",
    task_id=TASK_ID,
    goal="Copy inbox.txt contents into outbox.txt without calling delete_all().",
    created_at=TS,
)

CODE_LIST = ExecutorAction(kind="CODE", code="print(list_files())", raw_output="print(list_files())")
CODE_READ = ExecutorAction(
    kind="CODE",
    code='print(read("inbox.txt"))',
    raw_output='print(read("inbox.txt"))',
)
CODE_WRITE = ExecutorAction(
    kind="CODE",
    code='write("outbox.txt", "hello world")',
    raw_output='write("outbox.txt", "hello world")',
)
COMPLETE = ExecutorAction(kind="COMPLETE", message="done", raw_output="COMPLETE: done")
DELETE_SCRIPT = '```python\ndelete_all()\n```'


def _ev(
    *,
    step: int,
    event_type: str,
    actor: str,
    payload: dict | None = None,
    env_state_hash: str | None = None,
) -> Event:
    return Event(
        run_id=f"src/{SYSTEM}/{SEED}/{TASK_ID}",
        task_id=TASK_ID,
        system=SYSTEM,
        seed=SEED,
        step=step,
        ts=TS,
        actor=actor,  # type: ignore[arg-type]
        event_type=event_type,  # type: ignore[arg-type]
        payload=payload or {},
        env_state_hash=env_state_hash,
    )


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


def _policy(**over) -> SystemPolicy:
    kw: dict = {
        "plan_first": False,
        "planner_drives": False,
        "allow_executor_ask": False,
        "review_every_k": None,
    }
    kw.update(over)
    return SystemPolicy(**kw)


def _replay(actions: list[ExecutorAction]) -> tuple[MockEnv, list[Event], dict]:
    """Reset, execute `actions` on the live env, and record prefix events."""
    env = MockEnv()
    reset = env.reset(TASK_ID, SEED)
    events = [
        _ev(step=0, event_type="run_start", actor="system", payload={"limits": {}}),
        _ev(
            step=0,
            event_type="observation",
            actor="environment",
            payload={"text": reset.text, "done": False},
            env_state_hash=reset.env_state_hash,
        ),
        _ev(
            step=0,
            event_type="plan",
            actor="planner",
            payload={"packet": PACKET.model_dump()},
        ),
    ]
    for i, action in enumerate(actions, start=1):
        obs = env.step(action)
        events.append(_ev(step=i, event_type="action", actor="planner", payload=action.model_dump()))
        events.append(
            _ev(
                step=i,
                event_type="observation",
                actor="environment",
                payload={"text": obs.text, "done": obs.done},
                env_state_hash=obs.env_state_hash,
            )
        )
    return env, events, env.evaluate()


def _run(
    tmp_path: Path,
    env: MockEnv,
    *,
    run_id: str,
    prefix: EpisodePrefix | None,
    policy: SystemPolicy,
    executor: MockExecutor,
) -> tuple[object, list[Event], MockExecutor]:
    log = EventLog(tmp_path, run_id)
    ledger = _ledger()
    try:
        result = run_episode(
            name=SYSTEM,
            env=env,
            planner=MockPlanner(),
            executor=executor,
            verifier=None,
            policy=policy,
            limits=RunLimits(max_steps=40),
            task_id=TASK_ID,
            seed=SEED,
            log=log,
            ledger=ledger,
            prefix=prefix,
        )
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    return result, events, executor


def _terminal_prefix() -> tuple[MockEnv, EpisodePrefix, dict]:
    env, events, expected = _replay([CODE_LIST, CODE_READ, CODE_WRITE, COMPLETE])
    prefix = EpisodePrefix(events=events, start_step=5)
    return env, prefix, expected


def _live_executor_actions(events: list[Event]) -> list[Event]:
    return [e for e in events if e.event_type == "action" and e.actor == "executor"]


def test_terminal_prefix_stop_asks_zero_executor_actions(tmp_path: Path):
    env, prefix, expected = _terminal_prefix()
    executor = MockExecutor(script=[DELETE_SCRIPT, "COMPLETE"])
    result, events, executor = _run(
        tmp_path,
        env,
        run_id="x18_stop",
        prefix=prefix,
        policy=_policy(),
        executor=executor,
    )
    end = next(e for e in events if e.event_type == "run_end")
    assert executor.complete_calls == []
    assert executor.last_messages is None
    assert _live_executor_actions(events) == []
    assert end.payload["n_post_terminal_actions"] == 0
    assert result.error_type is None
    assert result.success is bool(expected["success"])
    assert result.tgc == expected["tgc"]
    assert result.success is True


def test_terminal_prefix_continue_matches_legacy_and_counts_extra_actions(tmp_path: Path):
    env, prefix, expected = _terminal_prefix()
    executor = MockExecutor(script=[DELETE_SCRIPT, "COMPLETE"])
    result, events, executor = _run(
        tmp_path,
        env,
        run_id="x18_continue",
        prefix=prefix,
        policy=_policy(post_prefix_terminal="continue"),
        executor=executor,
    )
    live = _live_executor_actions(events)
    end = next(e for e in events if e.event_type == "run_end")
    assert len(executor.complete_calls) == 2
    assert [e.payload.get("kind") for e in live] == ["CODE", "COMPLETE"]
    assert end.payload["n_post_terminal_actions"] == 2
    assert end.payload["n_post_terminal_actions"] == len(live)
    assert result.success is False
    assert bool(expected["success"]) is True
    assert result.tgc == 0.0


def test_mid_episode_prefix_executor_runs_normally(tmp_path: Path):
    env, events, _expected = _replay([CODE_LIST])
    last_obs_done = events[-1].payload.get("done")
    assert last_obs_done is False
    executor = MockExecutor()
    result, log_events, executor = _run(
        tmp_path,
        env,
        run_id="x18_mid",
        prefix=EpisodePrefix(events=events, start_step=2),
        policy=_policy(),
        executor=executor,
    )
    live = _live_executor_actions(log_events)
    end = next(e for e in log_events if e.event_type == "run_end")
    assert last_obs_done is False
    assert len(executor.complete_calls) >= 1
    assert live
    assert live[0].step == 2
    assert end.payload["n_post_terminal_actions"] == 0
    assert result.error_type is None
    assert result.success is True


def test_no_prefix_guard_is_noop(tmp_path: Path):
    executor = MockExecutor()
    result, events, executor = _run(
        tmp_path,
        MockEnv(),
        run_id="x18_none",
        prefix=None,
        policy=SystemPolicy(plan_first=True, review_every_k=None),
        executor=executor,
    )
    start = next(e for e in events if e.event_type == "run_start")
    end = next(e for e in events if e.event_type == "run_end")
    action_steps = [e.step for e in events if e.event_type == "action"]
    assert "prefix" not in (start.payload or {})
    assert "post_prefix_terminal" not in (start.payload.get("policy") or {})
    assert "n_post_terminal_actions" not in end.payload
    assert action_steps[0] == 1
    assert len(executor.complete_calls) >= 1
    assert result.error_type is None


def test_run_start_records_post_prefix_terminal_policy(tmp_path: Path):
    assert SystemPolicy().post_prefix_terminal == "stop"
    env_stop, prefix_stop, _ = _terminal_prefix()
    _, events_stop, _ = _run(
        tmp_path,
        env_stop,
        run_id="x18_record_stop",
        prefix=prefix_stop,
        policy=_policy(),
        executor=MockExecutor(script=[DELETE_SCRIPT, "COMPLETE"]),
    )
    env_cont, prefix_cont, _ = _terminal_prefix()
    _, events_cont, _ = _run(
        tmp_path,
        env_cont,
        run_id="x18_record_continue",
        prefix=prefix_cont,
        policy=_policy(post_prefix_terminal="continue"),
        executor=MockExecutor(script=[DELETE_SCRIPT, "COMPLETE"]),
    )
    start_stop = next(e for e in events_stop if e.event_type == "run_start")
    start_cont = next(e for e in events_cont if e.event_type == "run_start")
    assert "prefix" in start_stop.payload
    assert start_stop.payload["policy"]["post_prefix_terminal"] == "stop"
    assert start_cont.payload["policy"]["post_prefix_terminal"] == "continue"
