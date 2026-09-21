"""Takeover channel and planner HANDOFF (X2). MockEnv only; stub planners; no network."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import CodexExecConfig, CodexExecPlanner, MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.prompts import format_executor_action
from sidekick.protocols.schemas import ExecutorAction, PlannerResponse, Usage
from sidekick.runner import system_kwargs
from sidekick.systems import SYSTEM_NAMES, get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

WRITE_CODE = 'write("outbox.txt", "hello world")'
WRITE = f"```python\n{WRITE_CODE}\n```"
READ = '```python\nprint(read("inbox.txt"))\n```'
COMPLETE = "COMPLETE"
UNPARSEABLE = "I am not an action, just commentary."


def _usage(**kw) -> Usage:
    base = dict(model="mock-planner", provider="mock", input_tokens=10, output_tokens=8)
    base.update(kw)
    return Usage(**base)


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


class _RecordingEnv(MockEnv):
    def __init__(self) -> None:
        super().__init__()
        self.stepped: list = []

    def step(self, action: ExecutorAction):
        self.stepped.append(action)
        return super().step(action)


@dataclass
class _RecordingExecutor(MockExecutor):
    calls: list = field(default_factory=list)

    def complete(self, messages: list[dict], **kw):
        self.calls.append(list(messages))
        return super().complete(messages, **kw)


def _run(
    tmp_path: Path,
    *,
    name: str,
    planner,
    executor,
    run_id: str,
    env=None,
    **system_kw,
):
    log = EventLog(tmp_path, run_id)
    ledger = _ledger()
    system = get_system(
        name,
        planner=planner,
        executor=executor,
        limits=RunLimits(),
        **system_kw,
    )
    env = env or MockEnv()
    try:
        result = system.run(env, "copy_hello", 1, log, ledger)
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    return result, events, ledger, env


def _act_write() -> PlannerResponse:
    return PlannerResponse(
        kind="ACTION",
        code=WRITE_CODE,
        raw_output=WRITE,
        usage=_usage(),
    )


def test_takeover_executes_planner_code_and_records_exec_turns(tmp_path: Path):
    env = _RecordingEnv()
    executor = _RecordingExecutor(script=[READ, COMPLETE])
    planner = MockPlanner(scripts={("copy_hello", "act"): [_act_write()]})
    result, events, _ledger, env = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=executor,
        run_id="to_exec",
        env=env,
        k=2,
        takeover=True,
    )
    codes = [a.code for a in env.stepped if a.kind == "CODE"]
    assert WRITE_CODE in codes
    assert any(
        e.actor == "planner" and e.event_type == "action" and e.payload.get("code") == WRITE_CODE
        for e in events
    )
    assert executor.calls, "executor must run after takeover so exec_turns is observable"
    history = executor.calls[-1]
    assert any(
        t.get("role") == "assistant" and WRITE_CODE in str(t.get("content") or "")
        for t in history
    )
    assert any(
        t.get("role") == "user" and str(t.get("content") or "").startswith("OBS:")
        for t in history
    )
    assert result.error_type is None


def test_takeover_appends_no_intervention_turn(tmp_path: Path):
    planner = MockPlanner(scripts={("copy_hello", "act"): [_act_write()]})
    result, events, _ledger, _env = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=MockExecutor(script=[READ, COMPLETE]),
        run_id="to_no_iv",
        k=2,
        takeover=True,
    )
    assert result.n_interventions == 0
    assert not any(e.event_type == "intervention" for e in events)
    assert not any("INTERVENTION:" in str(e.payload) for e in events)
    end = next(e for e in events if e.event_type == "run_end")
    assert end.payload["n_planner_actions"] == 1
    start = next(e for e in events if e.event_type == "run_start")
    assert start.payload["policy"]["takeover"] is True


def test_advise_channel_still_injects_intervention(tmp_path: Path):
    planner = MockPlanner(scripts={("copy_hello", "act"): [_act_write()]})
    result, events, _ledger, _env = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=MockExecutor(script=[READ, COMPLETE]),
        run_id="to_advise",
        k=2,
        takeover=False,
    )
    assert any(e.event_type == "intervention" for e in events)
    assert not any(e.actor == "planner" and e.event_type == "action" for e in events)
    end = next(e for e in events if e.event_type == "run_end")
    assert end.payload["n_planner_actions"] == 0
    start = next(e for e in events if e.event_type == "run_start")
    assert "takeover" not in start.payload["policy"]
    assert result.n_interventions >= 1


def test_unparseable_takeover_falls_through_to_executor(tmp_path: Path):
    planner = MockPlanner(
        scripts={
            ("copy_hello", "act"): [
                PlannerResponse(kind="ACTION", code=None, raw_output=UNPARSEABLE, usage=_usage())
            ]
        }
    )
    result, events, _ledger, _env = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=MockExecutor(script=[READ, WRITE, COMPLETE]),
        run_id="to_parse_miss",
        k=2,
        takeover=True,
    )
    assert result.error_type is None
    assert result.success is True
    end = next(e for e in events if e.event_type == "run_end")
    assert end.payload["n_planner_actions"] == 0
    assert any(e.actor == "executor" and e.event_type == "action" for e in events)


def test_handoff_flips_driver(tmp_path: Path):
    planner = MockPlanner(
        scripts={
            ("copy_hello", "act"): [
                PlannerResponse(
                    kind="ACTION",
                    code='print(read("inbox.txt"))',
                    raw_output=READ,
                    usage=_usage(),
                ),
                PlannerResponse(kind="ACTION", code=None, raw_output="HANDOFF", usage=_usage()),
            ]
        }
    )
    result, events, _ledger, _env = _run(
        tmp_path,
        name="planner_handoff",
        planner=planner,
        executor=MockExecutor(script=[WRITE, COMPLETE]),
        run_id="ho_flip",
    )
    actions = [e for e in events if e.event_type in ("action", "handoff")]
    kinds_actors = [(e.event_type, e.actor) for e in actions]
    assert ("action", "planner") in kinds_actors
    assert ("handoff", "planner") in kinds_actors
    handoff_i = next(i for i, e in enumerate(actions) if e.event_type == "handoff")
    after = actions[handoff_i + 1 :]
    assert after
    assert all(e.actor == "executor" and e.event_type == "action" for e in after)
    end = next(e for e in events if e.event_type == "run_end")
    assert end.payload["handoff_step"] == actions[handoff_i].step
    start = next(e for e in events if e.event_type == "run_start")
    assert start.payload["policy"]["handoff_allowed"] is True
    assert result.error_type is None
    assert result.success is True


def test_handoff_disallowed_not_in_prompt_and_does_not_flip(tmp_path: Path):
    captured: dict[str, str] = {}

    def fake_invoke(prompt, schema_path=None, timeout_s=None, scratch=None):
        captured["prompt"] = prompt
        return "COMPLETE", _usage(), None

    planner = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path)))
    planner._invoke = fake_invoke  # type: ignore[method-assign]
    planner.act("copy_hello", "transcript", allow_handoff=False)
    assert "HANDOFF" not in captured["prompt"]
    planner.act("copy_hello", "transcript", allow_handoff=True)
    assert "HANDOFF" in captured["prompt"]

    stub = MockPlanner(
        scripts={
            ("copy_hello", "act"): [
                PlannerResponse(kind="ACTION", code=None, raw_output="HANDOFF", usage=_usage()),
            ]
        }
    )
    result, events, _ledger, _env = _run(
        tmp_path,
        name="planner_alone",
        planner=stub,
        executor=MockExecutor(script=[WRITE, COMPLETE]),
        run_id="ho_denied",
        handoff_allowed=False,
    )
    assert not any(e.event_type == "handoff" for e in events)
    end = next(e for e in events if e.event_type == "run_end")
    assert end.payload["handoff_step"] is None
    start = next(e for e in events if e.event_type == "run_start")
    assert "handoff_allowed" not in start.payload["policy"]
    assert result.error_type == "parse_error"


def test_ledger_charges_act_like_correct(tmp_path: Path):
    usage = _usage(input_tokens=100, output_tokens=20, cached_input_tokens=0)
    act_resp = PlannerResponse(kind="ACTION", code=WRITE_CODE, raw_output=WRITE, usage=usage)
    corr_resp = PlannerResponse(
        kind="CORRECTION",
        correction="write outbox",
        raw_output="write outbox",
        usage=usage,
    )
    _, _, ledger_act, _ = _run(
        tmp_path,
        name="fixed_k",
        planner=MockPlanner(scripts={("copy_hello", "act"): [act_resp]}),
        executor=MockExecutor(script=[READ, COMPLETE]),
        run_id="chg_act",
        k=2,
        takeover=True,
    )
    _, _, ledger_corr, _ = _run(
        tmp_path,
        name="fixed_k",
        planner=MockPlanner(scripts={("copy_hello", "correct"): [corr_resp]}),
        executor=MockExecutor(script=[READ, COMPLETE]),
        run_id="chg_corr",
        k=2,
        takeover=False,
    )
    tot_act = ledger_act.totals()
    tot_corr = ledger_corr.totals()
    assert tot_act["planner_calls_total"] == tot_corr["planner_calls_total"]
    assert tot_act["planner_tokens_total"] == tot_corr["planner_tokens_total"]


def test_prefix_handoff_m_without_source_campaign_raises(tmp_path: Path):
    system = get_system("prefix_handoff", planner=MockPlanner(), executor=MockExecutor(), m=4)
    log = EventLog(tmp_path, "prefix_raise")
    with pytest.raises(RuntimeError, match="source_campaign"):
        system.run(MockEnv(), "copy_hello", 1, log, _ledger())
    log.close()
    events_path = tmp_path / "prefix_raise" / "events.jsonl"
    assert not events_path.exists() or events_path.read_text(encoding="utf-8").strip() == ""


def test_system_kwargs_forwards_takeover_and_planner_handoff_adapter():
    kw = system_kwargs("fixed_k", {"takeover": True, "fixed_k": 10}, "t")
    assert kw["takeover"] is True
    assert kw["k"] == 10
    kw_h = system_kwargs(
        "planner_handoff",
        {"handoff_allowed": True, "executor": {"lora_name": "sft_b_plus"}},
        "t",
    )
    assert kw_h["handoff_allowed"] is True
    assert kw_h["adapter_name"] == "sft_b_plus"
    assert SYSTEM_NAMES[:8] == (
        "planner_alone",
        "executor_alone",
        "prompt_only",
        "fixed_k",
        "sft_plan",
        "router_seq",
        "sidekick",
        "oracle_escalation",
    )
    assert SYSTEM_NAMES[-1] == "planner_handoff"


def test_format_handoff_kind_roundtrip():
    action = ExecutorAction(kind="HANDOFF", raw_output="HANDOFF")
    assert action.kind == "HANDOFF"
    assert format_executor_action(action) == "HANDOFF"
