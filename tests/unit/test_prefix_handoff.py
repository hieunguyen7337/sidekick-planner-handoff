"""Offline tests for prefix_handoff (X1). MockEnv only: no AppWorld, no vLLM, no network."""
from __future__ import annotations

from pathlib import Path

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.prefix_source import build_handoff_prefix
from sidekick.protocols.prompts import format_executor_action
from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction, Usage
from sidekick.runner import system_kwargs
from sidekick.systems import SYSTEM_NAMES, get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

TASK_ID = "copy_hello"
SEED = 1
SOURCE_SYSTEM = "planner_alone"
TS = "2023-05-18T12:00:00+00:00"

CODE_1 = 'print(list_files())'
CODE_2 = 'print(read("inbox.txt"))'
CODE_3 = 'write("outbox.txt", "hello world")'
CODE_4 = 'print(read("outbox.txt"))'
CODES = [CODE_1, CODE_2, CODE_3, CODE_4]

PACKET = DelegationPacket(
    packet_id="pkt-prefix-1",
    task_id=TASK_ID,
    goal="Copy inbox.txt contents into outbox.txt without calling delete_all().",
    created_at=TS,
)

# Plan + two replayed planner actions. cached_input_tokens set but excluded.
# expected = (10+2+1) + (100+10+5) + (50+8+2) = 188
PLAN_USAGE = Usage(
    model="mock-planner",
    provider="mock",
    input_tokens=10,
    cached_input_tokens=3,
    output_tokens=2,
    reasoning_output_tokens=1,
)
ACT1_USAGE = Usage(
    model="mock-planner",
    provider="mock",
    input_tokens=100,
    cached_input_tokens=40,
    output_tokens=10,
    reasoning_output_tokens=5,
)
ACT2_USAGE = Usage(
    model="mock-planner",
    provider="mock",
    input_tokens=50,
    cached_input_tokens=20,
    output_tokens=8,
    reasoning_output_tokens=2,
)
# Must not be included when m=2.
ACT3_USAGE = Usage(
    model="mock-planner",
    provider="mock",
    input_tokens=999,
    cached_input_tokens=1,
    output_tokens=1,
    reasoning_output_tokens=1,
)
EXPECTED_REPLAYED_PLANNER_TOKENS = 188

ORIGINAL_EIGHT = (
    "planner_alone",
    "executor_alone",
    "prompt_only",
    "fixed_k",
    "sft_plan",
    "router_seq",
    "sidekick",
    "oracle_escalation",
)


def _ev(*, step: int, event_type: str, actor: str, payload: dict | None = None, usage=None, env_state_hash=None) -> Event:
    return Event(
        run_id=f"src/{SOURCE_SYSTEM}/{SEED}/{TASK_ID}",
        task_id=TASK_ID,
        system=SOURCE_SYSTEM,
        seed=SEED,
        step=step,
        ts=TS,
        actor=actor,  # type: ignore[arg-type]
        event_type=event_type,  # type: ignore[arg-type]
        payload=payload or {},
        usage=usage,
        env_state_hash=env_state_hash,
    )


def _write_source(tmp_path: Path, *, corrupt_hash: bool = False) -> Path:
    """Five executed actions (4 CODE + COMPLETE) with MockEnv hashes and planner actor."""
    camp = tmp_path / "camp"
    dest = camp / SOURCE_SYSTEM / str(SEED) / TASK_ID
    dest.mkdir(parents=True)
    world = MockEnv()
    reset_obs = world.reset(TASK_ID, SEED)
    events: list[Event] = [
        _ev(step=0, event_type="run_start", actor="system", payload={"limits": {}}, env_state_hash=reset_obs.env_state_hash),
        _ev(
            step=0,
            event_type="observation",
            actor="environment",
            payload={"text": reset_obs.text, "done": False},
            env_state_hash=reset_obs.env_state_hash,
        ),
        _ev(
            step=0,
            event_type="plan",
            actor="planner",
            payload={"packet": PACKET.model_dump()},
            usage=PLAN_USAGE,
        ),
    ]
    usages = [ACT1_USAGE, ACT2_USAGE, ACT3_USAGE, None]
    for i, code in enumerate(CODES, start=1):
        action = ExecutorAction(kind="CODE", code=code, raw_output=code)
        obs = world.step(action)
        events.append(
            _ev(
                step=i,
                event_type="action",
                actor="planner",
                payload=action.model_dump(),
                usage=usages[i - 1],
            )
        )
        events.append(
            _ev(
                step=i,
                event_type="observation",
                actor="environment",
                payload={"text": obs.text, "done": obs.done},
                env_state_hash=obs.env_state_hash,
            )
        )
    complete = ExecutorAction(kind="COMPLETE", message="done", raw_output="COMPLETE: done")
    obs = world.step(complete)
    events.append(_ev(step=5, event_type="action", actor="planner", payload=complete.model_dump()))
    events.append(
        _ev(
            step=5,
            event_type="observation",
            actor="environment",
            payload={"text": obs.text, "done": True},
            env_state_hash=obs.env_state_hash,
        )
    )
    world.close()
    if corrupt_hash:
        # Last replayed observation for m=2 is the observation at step 2.
        for e in events:
            if e.event_type == "observation" and e.step == 2:
                e.env_state_hash = "0" * 64
                break
    path = dest / "events.jsonl"
    path.write_text("".join(e.model_dump_json() + "\n" for e in events))
    return camp


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


def _run_handoff(tmp_path: Path, camp: Path, *, m: int, run_id: str, executor: MockExecutor | None = None):
    log = EventLog(tmp_path, run_id)
    ledger = _ledger()
    executor = executor or MockExecutor()
    planner = MockPlanner()
    system = get_system(
        "prefix_handoff",
        planner=planner,
        executor=executor,
        limits=RunLimits(),
        source_campaign=str(camp),
        source_system=SOURCE_SYSTEM,
        m=m,
    )
    try:
        result = system.run(MockEnv(), TASK_ID, SEED, log, ledger)
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    return result, events, ledger, executor, planner


def test_m2_of_five_handoff_and_history(tmp_path: Path):
    camp = _write_source(tmp_path)
    built = build_handoff_prefix(camp, SOURCE_SYSTEM, TASK_ID, SEED, 2, MockEnv())
    try:
        assert built.broken_reason is None
        assert built.effective_m == 2
        assert built.n_source_actions == 5
        assert built.handoff_occurred is True
        assert built.hash_ok is True
        assert built.prefix is not None
        assert built.prefix.start_step == 3
    finally:
        built.env.close()

    result, events, ledger, executor, planner = _run_handoff(tmp_path, camp, m=2, run_id="h_m2")
    assert result.error_type is None
    reports = [e for e in events if e.event_type == "report" and e.actor == "system"]
    assert reports and reports[0].payload["effective_m"] == 2
    assert reports[0].payload["handoff_occurred"] is True
    types = [e.event_type for e in events]
    assert types[0] == "run_start"
    assert types.index("run_start") < types.index("report")
    messages = executor.last_messages or []
    # render_executor_messages: system, opening user (Task + Plan), then exec_turns.
    opening = next(m for m in messages if m.get("role") == "user" and "Plan:" in str(m.get("content")))
    assert PACKET.packet_id in str(opening["content"])
    hist = messages[2:]
    assert hist[0]["role"] == "assistant"
    assert hist[0]["content"] == format_executor_action(ExecutorAction(kind="CODE", code=CODE_1))
    assert hist[1]["role"] == "user"
    assert str(hist[1]["content"]).startswith("OBS:")
    assert hist[2]["role"] == "assistant"
    assert hist[2]["content"] == format_executor_action(ExecutorAction(kind="CODE", code=CODE_2))
    assert hist[3]["role"] == "user"
    assert str(hist[3]["content"]).startswith("OBS:")
    assert ledger.totals()["planner_calls_total"] == 0


def test_m_beyond_episode_no_handoff(tmp_path: Path):
    camp = _write_source(tmp_path)
    built = build_handoff_prefix(camp, SOURCE_SYSTEM, TASK_ID, SEED, 99, MockEnv())
    try:
        assert built.effective_m == built.n_source_actions == 5
        assert built.handoff_occurred is False
        assert built.hash_ok is True
        assert built.broken_reason is None
    finally:
        built.env.close()


def test_corrupt_hash_broken_not_scored(tmp_path: Path):
    camp = _write_source(tmp_path, corrupt_hash=True)
    built = build_handoff_prefix(camp, SOURCE_SYSTEM, TASK_ID, SEED, 2, MockEnv())
    try:
        assert built.hash_ok is False
        assert built.broken_reason == "replay_divergence"
    finally:
        built.env.close()

    result, events, _ledger, _ex, _pl = _run_handoff(tmp_path, camp, m=2, run_id="h_div")
    assert result.success is False
    assert result.error_type == "crash"
    assert result.tgc is None
    assert any(e.event_type == "error" and e.payload.get("reason") == "replay_divergence" for e in events)
    assert not any(e.event_type == "evaluate" for e in events)


def test_missing_source(tmp_path: Path):
    built = build_handoff_prefix(tmp_path / "no_such_camp", SOURCE_SYSTEM, TASK_ID, SEED, 2, MockEnv())
    try:
        assert built.prefix is None
        assert built.broken_reason == "missing_source"
    finally:
        built.env.close()

    result, events, _ledger, _ex, _pl = _run_handoff(
        tmp_path, tmp_path / "no_such_camp", m=2, run_id="h_miss"
    )
    assert result.success is False
    assert result.error_type == "crash"
    assert any(e.event_type == "error" and e.payload.get("reason") == "missing_source" for e in events)


def test_replayed_planner_tokens_exclude_cached(tmp_path: Path):
    camp = _write_source(tmp_path)
    built = build_handoff_prefix(camp, SOURCE_SYSTEM, TASK_ID, SEED, 2, MockEnv())
    try:
        assert built.replayed_planner_tokens == EXPECTED_REPLAYED_PLANNER_TOKENS
        # Sanity: including cached or the unreplayed action-3 usage would not match.
        assert built.replayed_planner_tokens != EXPECTED_REPLAYED_PLANNER_TOKENS + 3 + 40 + 20
        assert built.replayed_planner_tokens != 999 + 1 + 1
    finally:
        built.env.close()


def test_live_suffix_zero_planner_calls(tmp_path: Path):
    camp = _write_source(tmp_path)
    result, events, ledger, _ex, _planner = _run_handoff(tmp_path, camp, m=2, run_id="h_zero")
    assert result.error_type is None
    assert ledger.totals()["planner_calls_total"] == 0
    assert not any(e.actor == "planner" for e in events)
    assert not any(e.event_type == "plan" for e in events)


def test_get_system_and_names_prefix():
    system = get_system("prefix_handoff", planner=MockPlanner(), executor=MockExecutor())
    assert system.name == "prefix_handoff"
    assert SYSTEM_NAMES[:8] == ORIGINAL_EIGHT
    assert SYSTEM_NAMES[8] == "action_review"
    assert "prefix_handoff" in SYSTEM_NAMES
    kw = system_kwargs(
        "prefix_handoff",
        {
            "handoff": {
                "source_campaign": "/scratch/n12194778/sidekick/results/hj1b_planner_20260915",
                "source_system": "planner_alone",
                "m": 4,
            },
            "executor": {"lora_name": "sft_b_plus"},
        },
        TASK_ID,
        SEED,
    )
    assert kw["source_campaign"].endswith("hj1b_planner_20260915")
    assert kw["source_system"] == "planner_alone"
    assert kw["m"] == 4
    assert kw["adapter_name"] == "sft_b_plus"
    # Not added to the adapter-forwarding tuple; dedicated block sets adapter_name.
    assert "prefix_handoff" not in (
        "sft_plan",
        "router_seq",
        "sidekick",
        "oracle_escalation",
        "action_review",
    )
