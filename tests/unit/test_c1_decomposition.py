"""B2, the C1 decomposition (plan 2026-09-23): neutral advice and show-don't-execute.

The matched-trigger channel contrast C1 compares a takeover arm, which calls planner.act and
executes the result, with an advice arm, which calls planner.correct under a prompt that
presumes an error and caps length. Two new arms separate those differences:

* ``advice_from_act`` ("show"): the planner is called exactly as in takeover, and its parsed
  action is shown to the executor as an INTERVENTION turn instead of being executed.
* ``planner.correct_prompt: neutral``: the advice prompt without the presumption or the cap.

These tests pin the two properties the experiment's validity rests on: the show arm's
planner input is identical to takeover's, and nothing it shows reaches the environment.
MockEnv only; stub planners; no network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

import sidekick.agents.planner as planner_mod
from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import (
    CORRECT_PROMPT_STYLES,
    CodexExecConfig,
    CodexExecPlanner,
    MockPlanner,
    build_advice_prompt,
    build_correct_prompt,
)
from sidekick.agents.vllm_planner import VllmPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.prompts import format_executor_action
from sidekick.protocols.schemas import ExecutorAction, PlannerResponse, Usage
from sidekick.runner import make_planner, system_kwargs
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

WRITE_CODE = 'write("outbox.txt", "hello world")'
WRITE = f"```python\n{WRITE_CODE}\n```"
READ = '```python\nprint(read("inbox.txt"))\n```'
COMPLETE = "COMPLETE"
UNPARSEABLE = "I am not an action, just commentary."

PACKET = planner_mod._default_packet("copy_hello", "copy the file", "ctx")


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


@dataclass
class _RecordingPlanner(MockPlanner):
    act_calls: list = field(default_factory=list)

    def act(self, task_id, transcript, timeout_s=None, allow_handoff=False):
        self.act_calls.append((task_id, transcript, allow_handoff))
        return super().act(task_id, transcript, timeout_s=timeout_s, allow_handoff=allow_handoff)


def _act(raw: str, code: str | None = None) -> PlannerResponse:
    return PlannerResponse(kind="ACTION", code=code, raw_output=raw, usage=_usage())


def _run(tmp_path: Path, *, planner, executor, run_id: str, env=None, **system_kw):
    log = EventLog(tmp_path, run_id)
    system = get_system("fixed_k", planner=planner, executor=executor, limits=RunLimits(), **system_kw)
    env = env or MockEnv()
    try:
        result = system.run(env, "copy_hello", 1, log, _ledger())
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    return result, events, env


# --- advice prompt styles ---------------------------------------------------------------


def test_correction_style_is_byte_identical_to_the_registered_prompt():
    # Every published advise arm used build_correct_prompt; the default style must not move it.
    assert build_advice_prompt(PACKET, "delta") == build_correct_prompt(PACKET, "delta")
    assert build_advice_prompt(PACKET, "delta", "correction") == build_correct_prompt(PACKET, "delta")


def test_neutral_style_differs_from_the_registered_prompt_in_its_first_line_only():
    registered = build_correct_prompt(PACKET, "line a\nline b").splitlines()
    neutral = build_advice_prompt(PACKET, "line a\nline b", "neutral").splitlines()
    assert registered[1:] == neutral[1:]
    assert registered[0] != neutral[0]
    # The two features removed on purpose: the presumption of error and the length cap.
    assert "correction" not in neutral[0].lower()
    assert "concise" not in neutral[0].lower()


def test_unknown_style_raises_everywhere_it_can_enter():
    assert CORRECT_PROMPT_STYLES == ("correction", "neutral", "structured")  # D2 added the third
    with pytest.raises(ValueError):
        build_advice_prompt(PACKET, "d", "friendly")
    with pytest.raises(ValueError):
        VllmPlanner(model="m", base_url="http://127.0.0.1:1/v1", correct_prompt="friendly")
    with pytest.raises(ValueError):
        make_planner({"planner": {"type": "mock", "correct_prompt": "friendly"}})


def test_codex_planner_correct_uses_the_configured_style(tmp_path: Path):
    captured: list[str] = []

    def fake_invoke(prompt, schema_path=None, timeout_s=None, scratch=None):
        captured.append(prompt)
        return "advice", _usage(), None

    default = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path)))
    default._invoke = fake_invoke  # type: ignore[method-assign]
    default.correct(PACKET, "delta")
    neutral = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path), correct_prompt="neutral"))
    neutral._invoke = fake_invoke  # type: ignore[method-assign]
    neutral.correct(PACKET, "delta")
    assert captured[0] == build_correct_prompt(PACKET, "delta")
    assert captured[1] == build_advice_prompt(PACKET, "delta", "neutral")


def test_make_planner_threads_the_style_into_both_backends():
    codex = make_planner({"planner": {"type": "codex", "correct_prompt": "neutral"}})
    assert codex.config.correct_prompt == "neutral"
    local = make_planner(
        {"planner": {"type": "vllm", "model": "m", "correct_prompt": "neutral"}}
    )
    assert local.correct_prompt == "neutral"
    assert make_planner({"planner": {"type": "codex"}}).config.correct_prompt == "correction"


# --- show, don't execute ----------------------------------------------------------------


def test_show_calls_the_planner_exactly_as_takeover_does(tmp_path: Path):
    """The first forced review must reach planner.act with identical arguments in both arms."""
    # Both arms replay ONE cached plan in production (packet_source), so pin one here too;
    # MockPlanner.plan otherwise mints a fresh random packet_id per run.
    plan = PlannerResponse(
        kind="PLAN", packet=PACKET, raw_output=PACKET.model_dump_json(), usage=_usage()
    )
    first_calls = []
    for run_id, channel in (("take", {"takeover": True}), ("show", {"advice_from_act": True})):
        planner = _RecordingPlanner(
            scripts={
                ("copy_hello", "plan"): [plan],
                ("copy_hello", "act"): [_act(WRITE, WRITE_CODE)],
            }
        )
        _run(
            tmp_path,
            planner=planner,
            executor=_RecordingExecutor(script=[READ, COMPLETE]),
            run_id=run_id,
            k=2,
            **channel,
        )
        assert planner.act_calls, f"{run_id}: the planner was never asked to act"
        first_calls.append(planner.act_calls[0])
    assert first_calls[0] == first_calls[1]


def test_show_delivers_the_action_as_text_and_never_executes_it(tmp_path: Path):
    env = _RecordingEnv()
    executor = _RecordingExecutor(script=[READ, COMPLETE])
    planner = MockPlanner(scripts={("copy_hello", "act"): [_act(WRITE, WRITE_CODE)]})
    _result, events, env = _run(
        tmp_path, planner=planner, executor=executor, run_id="show_text", env=env, k=2,
        advice_from_act=True,
    )
    # Nothing the planner produced reached the environment: only the executor's own actions.
    assert WRITE_CODE not in [a.code for a in env.stepped if a.kind == "CODE"]
    assert not any(e.actor == "planner" and e.event_type == "action" for e in events)
    shown = [
        e for e in events
        if e.event_type == "intervention" and e.payload.get("source") == "shown_action"
    ]
    assert shown, "the shown action must be logged as an intervention"
    expected = format_executor_action(ExecutorAction(kind="CODE", code=WRITE_CODE, raw_output=WRITE))
    assert shown[0].payload["correction"] == expected
    assert shown[0].payload["shown_kind"] == "CODE"
    assert shown[0].usage is not None, "the act call's cost must be charged to the intervention"
    # The executor saw it as the same INTERVENTION turn the advice channel uses.
    assert any(
        t.get("role") == "user" and t.get("content") == f"INTERVENTION: {expected}"
        for t in executor.calls[-1]
    )
    run_start = next(e for e in events if e.event_type == "run_start")
    assert run_start.payload["policy"].get("advice_from_act") is True
    assert "takeover" not in run_start.payload["policy"]


def test_an_unparseable_act_reply_shows_nothing(tmp_path: Path):
    # Takeover executes nothing on an unparseable reply; show must likewise show nothing,
    # rather than forwarding raw commentary that takeover would never have acted on.
    planner = MockPlanner(scripts={("copy_hello", "act"): [_act(UNPARSEABLE)]})
    _result, events, _env = _run(
        tmp_path, planner=planner, executor=_RecordingExecutor(script=[READ, COMPLETE]),
        run_id="show_bad", k=2, advice_from_act=True,
    )
    assert not any(e.payload.get("source") == "shown_action" for e in events if e.event_type == "intervention")
    assert any(e.event_type == "error" and e.error_type == "parse_error" for e in events)


def test_takeover_and_show_are_mutually_exclusive():
    with pytest.raises(ValueError):
        get_system(
            "fixed_k", planner=MockPlanner(), executor=MockExecutor(), limits=RunLimits(),
            k=2, takeover=True, advice_from_act=True,
        )


def test_system_kwargs_forwards_advice_from_act():
    kw = system_kwargs("fixed_k", {"fixed_k": 10, "advice_from_act": True}, "copy_hello")
    assert kw["advice_from_act"] is True
    assert "advice_from_act" not in system_kwargs("fixed_k", {"fixed_k": 10}, "copy_hello")
