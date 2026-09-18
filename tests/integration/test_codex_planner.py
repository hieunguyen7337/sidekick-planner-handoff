from __future__ import annotations

import json
import subprocess
import sys
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
    assert "hello" not in argv
    assert "--ephemeral" not in argv


def test_build_codex_resume_argv() -> None:
    argv = build_codex_argv(
        binary="codex",
        model="gpt-5.6-luna",
        reasoning_effort="medium",
        scratch="/tmp/scratch",
        thread_id="thr-1",
    )
    assert argv[:3] == ["codex", "exec", "resume"]
    assert "--disable" in argv and "shell_tool" in argv
    assert "-m" in argv and "gpt-5.6-luna" in argv
    assert "model_reasoning_effort=medium" in argv
    assert argv[-1] == "thr-1"
    assert "next" not in argv
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


def test_plan_uses_output_schema_and_stdin(tmp_path: Path) -> None:
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
    kwargs = recorded[0]["kwargs"]
    assert kwargs.get("encoding") == "utf-8"
    assert isinstance(kwargs.get("input"), str)
    assert "copy inbox to outbox" in kwargs["input"]
    assert "docs" in kwargs["input"]
    assert "copy inbox to outbox" not in argv
    assert kwargs.get("stdin") is not subprocess.DEVNULL
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
    assert recorded[1][-1] == "thr-1"
    assert "outbox empty" not in recorded[1]


def test_parse_packet_text_fenced() -> None:
    packet = parse_packet_text("noise\n```json\n" + _packet_json() + "\n```\n")
    assert packet.packet_id == "p1"


MAX_ARG_STRLEN = 128 * 1024
HUGE_PROMPT_BYTES = 300 * 1024


def _write_fake_codex(path: Path) -> Path:
    """Fake `codex` that echoes stdin as the last agent_message in JSONL."""
    body = '''
import json
import sys

prompt = sys.stdin.read()
sys.stdout.write(json.dumps({"type": "thread.started", "thread_id": "thr-stdin"}) + "\\n")
sys.stdout.write(
    json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": prompt}})
    + "\\n"
)
sys.stdout.write(
    json.dumps(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1,
                "cached_input_tokens": 0,
                "output_tokens": 1,
                "reasoning_output_tokens": 0,
            },
        }
    )
    + "\\n"
)
'''
    path.write_text("#!" + sys.executable + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_huge_prompt_round_trips_via_stdin(tmp_path: Path) -> None:
    """Regression: a 300 KiB prompt must not raise OSError E2BIG (MAX_ARG_STRLEN)."""
    fake = _write_fake_codex(tmp_path / "codex")
    planner = CodexExecPlanner(
        CodexExecConfig(binary=str(fake), scratch_parent=str(tmp_path)),
    )
    payload = "Ω" + ("x" * HUGE_PROMPT_BYTES)
    text, _usage, thread_id = planner._invoke(
        payload, schema_path=None, timeout_s=None
    )
    assert text == payload
    assert thread_id == "thr-stdin"


def test_build_codex_argv_no_element_exceeds_max_arg_strlen() -> None:
    huge = "x" * HUGE_PROMPT_BYTES
    fresh = build_codex_argv(
        binary="codex",
        model="gpt-5.6-luna",
        reasoning_effort="medium",
        scratch="/tmp/scratch",
        schema_path="/tmp/schema.json",
    )
    resume = build_codex_argv(
        binary="codex",
        model="gpt-5.6-luna",
        reasoning_effort="medium",
        scratch="/tmp/scratch",
        thread_id="thr-1",
    )
    for argv in (fresh, resume):
        assert all(len(part.encode("utf-8")) <= MAX_ARG_STRLEN for part in argv)
        assert huge not in argv
    assert resume[-1] == "thr-1"


def test_invoke_argv_omits_huge_prompt_fresh_and_resume(tmp_path: Path) -> None:
    huge = "x" * HUGE_PROMPT_BYTES
    recorded: list[dict] = []

    def runner(argv, **kwargs):
        recorded.append({"argv": argv, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            argv, 0, stdout=_jsonl("ok", thread="thr-1"), stderr=""
        )

    planner = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path)), runner=runner)
    planner._invoke(huge, schema_path=None, timeout_s=None)
    planner._invoke(huge, schema_path=None, timeout_s=None)
    assert len(recorded) == 2
    fresh, resume = recorded
    assert "resume" not in fresh["argv"]
    assert resume["argv"][:3] == ["codex", "exec", "resume"]
    assert resume["argv"][-1] == "thr-1"
    for rec in recorded:
        assert all(len(part.encode("utf-8")) <= MAX_ARG_STRLEN for part in rec["argv"])
        assert huge not in rec["argv"]
        assert rec["kwargs"].get("input") == huge
        assert rec["kwargs"].get("encoding") == "utf-8"
        assert rec["kwargs"].get("stdin") is not subprocess.DEVNULL


def test_fake_codex_receives_prompt_on_stdin(tmp_path: Path) -> None:
    fake = _write_fake_codex(tmp_path / "codex")
    planner = CodexExecPlanner(
        CodexExecConfig(binary=str(fake), scratch_parent=str(tmp_path)),
    )
    payload = "café — traceback\n  File \"app.py\", line 1\n    print('hi')"
    text, _usage, thread_id = planner._invoke(
        payload, schema_path=None, timeout_s=None
    )
    assert text == payload
    assert thread_id == "thr-stdin"
