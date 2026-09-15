from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sidekick.agents.planner import (
    CodexExecConfig,
    CodexExecPlanner,
    DELEGATION_PACKET_SCHEMA,
    build_codex_argv,
    parse_codex_jsonl,
    parse_packet_text,
)


def _jsonl(text: str, thread: str = "thr-1") -> str:
    usage = {
        "input_tokens": 15378,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 4,
        "output_tokens": 80,
        "reasoning_output_tokens": 12,
    }
    return (
        json.dumps({"type": "thread.started", "thread_id": thread})
        + "\n"
        + json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}})
        + "\n"
        + json.dumps({"type": "turn.completed", "usage": usage})
        + "\n"
    )


def _packet_json() -> str:
    return json.dumps(
        {
            "packet_id": "p1",
            "task_id": "copy_hello",
            "goal": "copy",
            "plan_steps": [
                {
                    "index": 0,
                    "description": "read inbox",
                    "expected_outcome": "text",
                    "apps": ["files"],
                }
            ],
            "constraints": [],
            "success_criteria": ["outbox matches"],
            "forbidden_actions": ["delete_all"],
            "context_digest": "x",
            "created_at": "2026-09-15T00:00:00+00:00",
        }
    )


def test_build_codex_argv_flags() -> None:
    argv = build_codex_argv(
        binary="codex",
        model="gpt-5.6-luna",
        reasoning_effort="medium",
        scratch="/tmp/scratch",
        prompt="hello",
        schema_path="/tmp/schema.json",
    )
    assert argv[:3] == ["codex", "exec", "--json"]
    assert "--skip-git-repo-check" in argv
    assert argv[argv.index("-s") + 1] == "read-only"
    assert argv[argv.index("--disable") + 1] == "shell_tool"
    assert argv[argv.index("-m") + 1] == "gpt-5.6-luna"
    assert argv[argv.index("-c") + 1] == "model_reasoning_effort=medium"
    assert argv[argv.index("-C") + 1] == "/tmp/scratch"
    assert argv[argv.index("--output-schema") + 1] == "/tmp/schema.json"
    assert argv[-1] == "hello"
    assert "--ephemeral" not in argv


def test_build_codex_resume_argv() -> None:
    argv = build_codex_argv(
        binary="codex",
        model="gpt-5.6-luna",
        reasoning_effort="medium",
        scratch="/tmp/scratch",
        prompt="next",
        thread_id="thr-1",
    )
    assert argv[:3] == ["codex", "exec", "resume"]
    assert "--disable" in argv and "shell_tool" in argv
    assert "-m" in argv and "gpt-5.6-luna" in argv
    assert "model_reasoning_effort=medium" in argv
    assert "thr-1" in argv
    assert "--ephemeral" not in argv
    assert "-C" not in argv  # resume CLI has no -C


def test_schema_is_strict() -> None:
    assert DELEGATION_PACKET_SCHEMA["additionalProperties"] is False
    required = set(DELEGATION_PACKET_SCHEMA["required"])
    assert required == set(DELEGATION_PACKET_SCHEMA["properties"])
    step = DELEGATION_PACKET_SCHEMA["properties"]["plan_steps"]["items"]
    assert step["additionalProperties"] is False
    assert set(step["required"]) == set(step["properties"])


def test_parse_codex_jsonl_usage_and_last_message() -> None:
    stdout = _jsonl("first") + json.dumps(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "second"}}
    )
    thread, text, usage = parse_codex_jsonl(stdout)
    assert thread == "thr-1"
    assert text == "second"
    assert usage["input_tokens"] == 15378
    assert usage["reasoning_output_tokens"] == 12


def test_plan_uses_output_schema_and_devnull(tmp_path: Path) -> None:
    recorded: list[dict] = []
    packet = _packet_json()

    def runner(argv, **kwargs):
        recorded.append({"argv": argv, "kwargs": kwargs})
        return subprocess.CompletedProcess(argv, 0, stdout=_jsonl(packet), stderr="")

    planner = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path)), runner=runner)
    resp = planner.plan("copy_hello", "copy inbox to outbox", "docs")
    assert resp.kind == "PLAN"
    assert resp.packet is not None
    assert resp.packet.task_id == "copy_hello"
    assert resp.usage.provider == "codex"
    assert resp.usage.model == "gpt-5.6-luna"
    assert resp.usage.input_tokens == 15378
    assert resp.usage.raw["model_reasoning_effort"] == "medium"
    assert resp.usage.raw["packet_parse_path"] == "output_schema"
    assert resp.thread_id == "thr-1"
    assert recorded
    argv = recorded[0]["argv"]
    assert "--output-schema" in argv
    assert recorded[0]["kwargs"]["stdin"] is subprocess.DEVNULL
    assert "--ephemeral" not in argv


def test_plan_falls_back_to_fenced_json(tmp_path: Path) -> None:
    calls = {"n": 0}

    def runner(argv, **kwargs):
        calls["n"] += 1
        if "--output-schema" in argv:
            return subprocess.CompletedProcess(argv, 1, stdout="nope", stderr="schema fail")
        fenced = "```json\n" + _packet_json() + "\n```"
        return subprocess.CompletedProcess(argv, 0, stdout=_jsonl(fenced), stderr="")

    planner = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path)), runner=runner)
    resp = planner.plan("copy_hello", "copy", "")
    assert resp.packet is not None
    assert resp.usage.raw["packet_parse_path"] == "fenced_json"
    assert calls["n"] == 2


def test_correct_resumes_thread(tmp_path: Path) -> None:
    recorded: list[list[str]] = []

    def runner(argv, **kwargs):
        recorded.append(argv)
        if "resume" not in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=_jsonl(_packet_json()), stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout=_jsonl("do not delete_all"), stderr="")

    planner = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path)), runner=runner)
    planned = planner.plan("copy_hello", "copy", "")
    assert planned.packet is not None
    corrected = planner.correct(planned.packet, "outbox empty")
    assert corrected.kind == "CORRECTION"
    assert corrected.correction == "do not delete_all"
    assert recorded[1][:3] == ["codex", "exec", "resume"]
    assert "thr-1" in recorded[1]


def test_parse_packet_text_fenced() -> None:
    packet = parse_packet_text("noise\n```json\n" + _packet_json() + "\n```\n")
    assert packet.packet_id == "p1"
