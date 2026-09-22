"""A planner whose episode no longer fits its context ends the episode as a `limit`, not a `crash`.

The local planner (LP arms) keeps the whole episode in its conversation and raises
`PlannerContextOverflow` when even the compacted thread does not fit. That is an exhausted
budget, like the step or token caps. Scored as `crash` it would be dropped from the analysis and
resubmitted forever -- hiding the failure and never terminating -- so the loop must evaluate and
score the episode exactly as it does a `max_steps` limit.
"""
from __future__ import annotations

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner, PlannerContextOverflow
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import Usage
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

OVERFLOW_USAGE = Usage(model="Qwen/Qwen3-8B", provider="vllm", latency_s=0.5, gpu_seconds=0.5, n_calls=1)


class ScoredMockEnv(MockEnv):
    """MockEnv reports no goal_pass_rate; a number makes "the episode was scored" checkable."""

    def evaluate(self) -> dict:
        return {**super().evaluate(), "goal_pass_rate": 0.25}


class OverflowOnSecondAct(MockPlanner):
    """Runs one real action, then cannot fit the episode any more."""

    n_act = 0

    def act(self, task_id, transcript, timeout_s=None, allow_handoff=False):
        self.n_act += 1
        if self.n_act >= 2:
            raise PlannerContextOverflow("planner context overflow: test", usage=OVERFLOW_USAGE)
        return super().act(task_id, transcript, timeout_s=timeout_s, allow_handoff=allow_handoff)


class OverflowInPlan(MockPlanner):
    """Overflows before any action, and carries no usage (the loop must charge a zero record)."""

    def plan(self, task_id, goal, context, timeout_s=None):
        raise PlannerContextOverflow("planner context overflow: plan")


def _run(tmp_path, planner, run_id: str):
    log = EventLog(tmp_path, run_id)
    ledger = CostLedger(PriceSchedule({"models": {}, "local": {}}))
    system = get_system(
        "planner_alone",
        planner=planner,
        executor=MockExecutor(),
        limits=RunLimits(max_steps=10),
    )
    try:
        result = system.run(ScoredMockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()
    return result, list(EventLog.read(tmp_path / run_id / "events.jsonl"))


def test_an_act_overflow_is_a_limit_and_the_episode_is_still_scored(tmp_path) -> None:
    planner = OverflowOnSecondAct()

    result, events = _run(tmp_path, planner, "ctx_overflow_act")

    assert planner.n_act == 2  # no retry after the overflow
    assert result.error_type == "limit"
    assert result.success is False
    assert result.goal_pass_rate == 0.25
    evaluate = [e for e in events if e.event_type == "evaluate"]
    assert len(evaluate) == 1
    assert evaluate[0].payload["goal_pass_rate"] == 0.25
    assert not [e for e in events if e.error_type == "crash"]

    limit = [e for e in events if e.event_type == "error" and e.actor == "planner"]
    assert len(limit) == 1
    assert limit[0].error_type == "limit"
    assert limit[0].payload == {
        "method": "act",
        "limit": "planner_context",
        "detail": "planner context overflow: test",
    }
    # The overflow's own usage is what gets charged, so its GPU time stays on the books.
    assert limit[0].usage.provider == "vllm"
    assert limit[0].usage.gpu_seconds == 0.5
    run_end = [e for e in events if e.event_type == "run_end"]
    assert run_end[-1].error_type == "limit"


def test_a_plan_overflow_without_usage_is_a_limit_charged_a_zero_record(tmp_path) -> None:
    result, events = _run(tmp_path, OverflowInPlan(), "ctx_overflow_plan")

    assert result.error_type == "limit"
    assert result.goal_pass_rate == 0.25
    assert [e for e in events if e.event_type == "evaluate"]
    assert not [e for e in events if e.error_type == "crash"]
    limit = [e for e in events if e.event_type == "error" and e.actor == "planner"]
    assert len(limit) == 1
    assert limit[0].payload["method"] == "plan"
    assert limit[0].payload["limit"] == "planner_context"
    assert limit[0].usage.input_tokens == 0
    assert limit[0].usage.output_tokens == 0
    assert limit[0].usage.n_calls == 1
