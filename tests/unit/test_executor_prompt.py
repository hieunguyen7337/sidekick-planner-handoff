"""Executor prompt is a multi-turn conversation; the planner transcript is unchanged."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.prompts import (
    EXECUTOR_SYSTEM_PROMPT,
    format_executor_action,
    render_executor_messages,
)
from sidekick.protocols.schemas import (
    DelegationPacket,
    ExecutorAction,
    parse_executor_action,
)
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog


def _packet(**kw) -> DelegationPacket:
    base = dict(
        packet_id="pkt-1",
        task_id="t1",
        goal="do the thing",
        created_at="2026-09-16T00:00:00+00:00",
    )
    base.update(kw)
    return DelegationPacket(**base)


def _code_turn(code: str) -> dict:
    return {"role": "assistant", "content": f"```python\n{code}\n```"}


def _obs_turn(text: str) -> dict:
    return {"role": "user", "content": f"OBS: {text}"}


def _two_action_history() -> list[dict]:
    return [
        _code_turn("print(apis.spotify.connect_account())"),
        _obs_turn("access_token=abc"),
        _code_turn("print(apis.spotify.fetch_saved_tracks())"),
        _obs_turn("songs=[]"),
    ]


def test_two_code_actions_appear_before_their_observations():
    # Would fail against the old single-message renderer: executed CODE never
    # entered the transcript, so the first login() call was invisible and the
    # model would log in again.
    history = _two_action_history()
    messages = render_executor_messages(instruction="login then list songs", history=history)
    blobs = [m["content"] for m in messages]
    # Use prompt-absent needles so ordering cannot collide with the system prompt's examples.
    joined_history = "\n".join(blobs[2:])
    i_login = joined_history.index("print(apis.spotify.connect_account())")
    i_token = joined_history.index("OBS: access_token=abc")
    i_lib = joined_history.index("print(apis.spotify.fetch_saved_tracks())")
    i_songs = joined_history.index("OBS: songs=[]")
    assert i_login < i_token < i_lib < i_songs
    framing = messages[1]["content"]
    assert "print(apis.spotify.connect_account())" not in framing
    assert "Transcript:" not in framing
    assert messages[2]["role"] == "assistant"
    assert "print(apis.spotify.connect_account())" in messages[2]["content"]
    assert messages[4]["role"] == "assistant"
    assert "print(apis.spotify.fetch_saved_tracks())" in messages[4]["content"]


def test_roles_alternate_and_system_is_first():
    messages = render_executor_messages(instruction="task", history=_two_action_history())
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == EXECUTOR_SYSTEM_PROMPT
    assert [m["role"] for m in messages] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]


def test_api_docs_empty_vs_present():
    empty = render_executor_messages(instruction="do x", history=[])
    assert empty[1]["content"] == "Task: do x\n"
    docs = "read(name: str) -> str\n"
    present = render_executor_messages(instruction="do x", api_docs=docs, history=[])
    assert present[1]["content"] == f"Task: do x\n{docs}\n"


def test_packet_none_vs_present():
    none = render_executor_messages(instruction="do x", history=[])
    assert "Plan:" not in none[1]["content"]
    packet = _packet()
    with_plan = render_executor_messages(instruction="do x", packet=packet, history=[])
    assert f"Plan: {packet.model_dump_json()}\n" in with_plan[1]["content"]
    assert with_plan[1]["content"].startswith("Task: do x\n")


def test_invalid_history_role_raises():
    with pytest.raises(ValueError, match="history\\[0\\]"):
        render_executor_messages(
            instruction="x",
            history=[{"role": "system", "content": "nope"}],
        )


def test_assistant_turns_round_trip_parse_executor_action():
    turns = [
        "```python\nprint(apis.spotify.login())\n```",
        "ASK_PLANNER: which playlist id?",
        "REPORT: got access_token",
        "COMPLETE",
        "COMPLETE: Placeholder Song A",
    ]
    history: list[dict] = []
    for text in turns:
        history.append({"role": "assistant", "content": text})
        history.append({"role": "user", "content": "OBS: ok"})
    messages = render_executor_messages(instruction="t", history=history)
    parsed = [parse_executor_action(m["content"]) for m in messages if m["role"] == "assistant"]
    assert [a.kind for a in parsed] == ["CODE", "ASK_PLANNER", "REPORT", "COMPLETE", "COMPLETE"]
    assert parsed[0].code == "print(apis.spotify.login())"
    assert parsed[1].ask_reason == "which playlist id?"
    assert parsed[2].message == "got access_token"
    assert parsed[3].message is None
    assert parsed[4].message == "Placeholder Song A"


def test_format_executor_action_matches_parser_fields():
    code = ExecutorAction(kind="CODE", code="print(1)", raw_output="<py>\nprint(1)\n</py>")
    assert format_executor_action(code) == "```python\nprint(1)\n```"
    assert parse_executor_action(format_executor_action(code)).code == "print(1)"
    ask = ExecutorAction(kind="ASK_PLANNER", ask_reason="need id", raw_output="ASK_PLANNER: need id")
    assert format_executor_action(ask) == "ASK_PLANNER: need id"
    report = ExecutorAction(kind="REPORT", message="found it", raw_output="REPORT: found it")
    assert format_executor_action(report) == "REPORT: found it"
    done = ExecutorAction(kind="COMPLETE", message=None, raw_output="COMPLETE")
    assert format_executor_action(done) == "COMPLETE"
    answered = ExecutorAction(kind="COMPLETE", message="ok", raw_output="COMPLETE: ok")
    assert format_executor_action(answered) == "COMPLETE: ok"


@dataclass
class _RecordingExecutor(MockExecutor):
    calls: list[list[dict]] = field(default_factory=list)

    def complete(self, messages: list[dict], **kw):
        self.calls.append(list(messages))
        return super().complete(messages, **kw)


@dataclass
class _RecordingPlanner(MockPlanner):
    act_transcripts: list[str] = field(default_factory=list)

    def act(self, task_id: str, transcript: str, timeout_s: float | None = None):
        self.act_transcripts.append(transcript)
        return super().act(task_id, transcript, timeout_s=timeout_s)


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


def test_loop_second_step_messages_contain_first_action(tmp_path):
    executor = _RecordingExecutor()
    log = EventLog(tmp_path, "ua1_exec_sees_self")
    system = get_system(
        "executor_alone",
        planner=MockPlanner(),
        executor=executor,
        limits=RunLimits(max_steps=8),
    )
    try:
        system.run(MockEnv(), "copy_hello", 1, log, _ledger())
    finally:
        log.close()

    assert len(executor.calls) >= 2
    first_prompt = executor.calls[0]
    second_prompt = executor.calls[1]
    assert first_prompt[0]["role"] == "system"
    assert all(m["role"] != "assistant" for m in first_prompt)
    first_code = 'print(read("inbox.txt"))'
    assistant = [m for m in second_prompt if m["role"] == "assistant"]
    assert assistant, "second executor call had no assistant history"
    assert any(first_code in m["content"] for m in assistant)
    ai = next(i for i, m in enumerate(second_prompt) if m["role"] == "assistant" and first_code in m["content"])
    oi = next(i for i, m in enumerate(second_prompt) if i > 1 and m["role"] == "user" and m["content"].startswith("OBS:"))
    assert ai < oi
    if len(executor.calls) >= 3:
        third = "\n".join(m["content"] for m in executor.calls[2] if m["role"] == "assistant")
        assert first_code in third
        assert 'write("outbox.txt", "hello world")' in third


def test_planner_act_still_receives_instruction_obs_transcript(tmp_path):
    planner = _RecordingPlanner()
    log = EventLog(tmp_path, "ua1_planner_prompt_guard")
    system = get_system(
        "planner_alone",
        planner=planner,
        executor=MockExecutor(),
        limits=RunLimits(max_steps=8),
    )
    try:
        system.run(MockEnv(), "copy_hello", 1, log, _ledger())
    finally:
        log.close()

    assert planner.act_transcripts, "planner.act was never called"
    first = planner.act_transcripts[0]
    assert first.startswith("INSTRUCTION: ")
    assert "\nPLAN: " in first
    assert "\nOBS: " not in first
    later = next(t for t in planner.act_transcripts if "\nOBS: " in t)
    assert later.startswith("INSTRUCTION: ")
    assert "```python" not in later
    assert "Transcript:" not in later
    assert "\nACTION: CODE" not in later
