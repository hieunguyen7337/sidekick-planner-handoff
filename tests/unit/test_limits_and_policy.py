from types import SimpleNamespace

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import Usage
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits, _client_model_id, token_count
from sidekick.trajectories.eventlog import EventLog


def test_token_count_excludes_cached_input():
    # Guards the episode-budget defect where cached transcript input was counted again.
    usage = Usage(
        model="mock",
        provider="mock",
        input_tokens=100_000,
        cached_input_tokens=90_000,
        output_tokens=500,
    )
    assert token_count(usage) == 10_500


def test_token_count_clamps_uncached_input_at_zero():
    # Guards negative episode budgets when a provider reports more cached than input tokens.
    usage = Usage(
        model="mock",
        provider="mock",
        input_tokens=100,
        cached_input_tokens=200,
        output_tokens=500,
        reasoning_output_tokens=25,
    )
    assert token_count(usage) == 525


def test_token_count_preserves_uncached_executor_shape():
    # Guards the executor budget path when cached input is absent.
    usage = Usage(model="mock", provider="mock", input_tokens=120, output_tokens=40)
    assert token_count(usage) == 160


def test_client_model_id_prefers_configured_model():
    # Guards failed planner bookkeeping from recording the planner class name.
    client = SimpleNamespace(config=SimpleNamespace(model="gpt-5.6-luna"), name="codex-exec")
    assert _client_model_id(client, "planner") == "gpt-5.6-luna"


def test_client_model_id_uses_client_model():
    # Guards failed executor bookkeeping from recording the executor class name.
    client = SimpleNamespace(model="local-granite", name="vllm-executor")
    assert _client_model_id(client, "executor") == "local-granite"


def test_client_model_id_uses_fallback_without_metadata():
    # Guards mock failed-call bookkeeping when the client exposes no model metadata.
    class BareClient:
        pass

    assert _client_model_id(BareClient(), "executor") == "executor"


def test_max_steps_limit_event_names_the_cap(tmp_path):
    # Guards the limit-accounting defect where a max-steps failure lost its cap name.
    run_id = "max_steps_limit"
    log = EventLog(tmp_path, run_id)
    ledger = CostLedger(PriceSchedule({"models": {}, "local": {}}))
    system = get_system(
        "prompt_only",
        planner=MockPlanner(),
        executor=MockExecutor(),
        limits=RunLimits(max_steps=2),
    )
    try:
        system.run(MockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()

    events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    # run_end also carries error_type="limit", so target the cap-naming error event.
    limit_events = [
        event
        for event in events
        if event.event_type == "error" and event.error_type == "limit"
    ]
    assert limit_events
    assert limit_events[-1].payload["limit"] == "max_steps"


def test_plan_event_records_thread_id(tmp_path):
    # Guards cached-plan provenance losing the hosted planner thread id.
    run_id = "plan_thread_id"
    log = EventLog(tmp_path, run_id)
    ledger = CostLedger(PriceSchedule({"models": {}, "local": {}}))
    system = get_system(
        "prompt_only",
        planner=MockPlanner(),
        executor=MockExecutor(),
        limits=RunLimits(max_steps=1),
    )
    try:
        system.run(MockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()

    plan_events = [
        event
        for event in EventLog.read(tmp_path / run_id / "events.jsonl")
        if event.event_type == "plan"
    ]
    assert plan_events[0].payload["thread_id"] == "mock-thread-copy_hello"
