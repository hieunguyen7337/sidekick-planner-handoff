"""Planner clients: Codex CLI subprocess and a deterministic mock."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from sidekick.protocols.schemas import (
    DelegationPacket,
    PlanStep,
    PlannerResponse,
    Usage,
    utc_now_iso,
)

DEFAULT_PLANNER_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "medium"
DEFAULT_PLANNER_TIMEOUT_S = 300.0

# Strict JSON Schema for DelegationPacket (OpenAI/Codex structured output).
DELEGATION_PACKET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "packet_id",
        "task_id",
        "goal",
        "plan_steps",
        "constraints",
        "success_criteria",
        "forbidden_actions",
        "context_digest",
        "created_at",
    ],
    "properties": {
        "packet_id": {"type": "string"},
        "task_id": {"type": "string"},
        "goal": {"type": "string"},
        "plan_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "description", "expected_outcome", "apps"],
                "properties": {
                    "index": {"type": "integer"},
                    "description": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "apps": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "constraints": {"type": "array", "items": {"type": "string"}},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "forbidden_actions": {"type": "array", "items": {"type": "string"}},
        "context_digest": {"type": "string"},
        "created_at": {"type": "string"},
    },
}

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


class PlannerClient(Protocol):
    name: str

    def plan(self, task_id: str, goal: str, context: str) -> PlannerResponse: ...
    def correct(self, packet: DelegationPacket, transcript_delta: str) -> PlannerResponse: ...
    def act(self, task_id: str, transcript: str) -> PlannerResponse: ...
    def close(self) -> None: ...


class PacketParseError(ValueError):
    """Planner text could not be parsed into a DelegationPacket."""

    def __init__(self, raw_output: str, message: str = "could not parse DelegationPacket") -> None:
        super().__init__(message)
        self.raw_output = raw_output


@dataclass
class CodexExecConfig:
    binary: str = "codex"
    model: str = DEFAULT_PLANNER_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    sandbox: str = "read-only"
    timeout_s: float = DEFAULT_PLANNER_TIMEOUT_S
    scratch_parent: Optional[str] = None


SubprocessRunner = Callable[..., subprocess.CompletedProcess]


def build_codex_argv(
    *,
    binary: str,
    model: str,
    reasoning_effort: str,
    scratch: str,
    prompt: str,
    thread_id: Optional[str] = None,
    schema_path: Optional[str] = None,
    sandbox: str = "read-only",
) -> list[str]:
    """Build a `codex exec` argv. Never includes `--ephemeral` (that blocks resume)."""
    effort = f"model_reasoning_effort={reasoning_effort}"
    if thread_id:
        # `codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]` — no -s/-C on resume.
        cmd = [
            binary,
            "exec",
            "resume",
            "--json",
            "--skip-git-repo-check",
            "--disable",
            "shell_tool",
            "-m",
            model,
            "-c",
            effort,
        ]
        if schema_path:
            cmd.extend(["--output-schema", schema_path])
        cmd.extend([thread_id, prompt])
        return cmd
    cmd = [
        binary,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "-s",
        sandbox,
        "--disable",
        "shell_tool",
        "-m",
        model,
        "-c",
        effort,
        "-C",
        scratch,
    ]
    if schema_path:
        cmd.extend(["--output-schema", schema_path])
    cmd.append(prompt)
    return cmd


def _extract_item_text(obj: dict[str, Any]) -> str:
    item = obj.get("item") if isinstance(obj.get("item"), dict) else obj
    if not isinstance(item, dict):
        return ""
    if isinstance(item.get("text"), str) and item["text"]:
        return item["text"]
    content = item.get("content")
    if isinstance(content, str) and content:
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, dict) and isinstance(chunk.get("text"), str):
                parts.append(chunk["text"])
            elif isinstance(chunk, str):
                parts.append(chunk)
        return "".join(parts)
    if isinstance(obj.get("text"), str):
        return obj["text"]
    return ""


def parse_codex_jsonl(stdout: str) -> tuple[Optional[str], str, dict[str, Any]]:
    """Return (thread_id, last assistant text, usage dict) from Codex JSONL stdout."""
    thread_id: Optional[str] = None
    texts: list[str] = []
    usage: dict[str, Any] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = obj.get("type") or obj.get("event_type")
        if typ == "thread.started":
            tid = obj.get("thread_id") or obj.get("threadId")
            if isinstance(tid, str):
                thread_id = tid
        elif typ == "turn.completed":
            u = obj.get("usage")
            if isinstance(u, dict):
                usage = u
        elif typ in ("agent_message", "item.completed", "agent.completed"):
            item = obj.get("item") if isinstance(obj.get("item"), dict) else obj
            item_type = ""
            if isinstance(item, dict):
                item_type = str(item.get("type") or item.get("item_type") or "")
            if typ == "item.completed" and item_type and item_type not in (
                "agent_message",
                "message",
                "agent_message_item",
            ):
                # Keep non-message items only if they still have text.
                text = _extract_item_text(obj)
                if text:
                    texts.append(text)
                continue
            text = _extract_item_text(obj)
            if text:
                texts.append(text)
    return thread_id, (texts[-1] if texts else ""), usage


def parse_packet_text(text: str) -> DelegationPacket:
    """Parse a DelegationPacket from raw JSON or a fenced JSON block."""
    candidates: list[str] = []
    stripped = text.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)
    for match in _FENCED_JSON_RE.finditer(text):
        candidates.append(match.group(1))
    last_err: Exception | None = None
    for blob in candidates:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError as exc:
            last_err = exc
            continue
        if not isinstance(data, dict):
            continue
        try:
            return DelegationPacket.model_validate(data)
        except Exception as exc:  # pydantic ValidationError
            last_err = exc
            continue
    raise PacketParseError(text, f"could not parse DelegationPacket: {last_err}")


def _usage_from_codex(
    *,
    model: str,
    effort: str,
    usage_raw: dict[str, Any],
    latency_s: float,
    n_calls: int,
    extra: dict[str, Any] | None = None,
) -> Usage:
    raw = {
        "cache_write_input_tokens": int(usage_raw.get("cache_write_input_tokens") or 0),
        "model": model,
        "model_reasoning_effort": effort,
    }
    if extra:
        raw.update(extra)
    return Usage(
        model=model,
        provider="codex",
        input_tokens=int(usage_raw.get("input_tokens") or 0),
        cached_input_tokens=int(usage_raw.get("cached_input_tokens") or 0),
        output_tokens=int(usage_raw.get("output_tokens") or 0),
        reasoning_output_tokens=int(usage_raw.get("reasoning_output_tokens") or 0),
        latency_s=float(latency_s),
        gpu_seconds=0.0,
        n_calls=n_calls,
        raw=raw,
    )


class CodexExecPlanner:
    """Frozen planner driven by `codex exec --json` (hosted gpt-5.6-luna)."""

    name = "codex-exec"

    def __init__(
        self,
        config: CodexExecConfig | None = None,
        runner: SubprocessRunner | None = None,
    ) -> None:
        self.config = config or CodexExecConfig()
        self._runner = runner or subprocess.run
        self._thread_id: Optional[str] = None

    def plan(self, task_id: str, goal: str, context: str, timeout_s: float | None = None) -> PlannerResponse:
        prompt = (
            "Produce a DelegationPacket JSON object for this task.\n"
            f"task_id: {task_id}\n"
            f"goal: {goal}\n"
            f"context:\n{context}\n"
            "Fill every required field. plan_steps should be concrete and ordered."
        )
        text, usage, thread_id, parse_path = self._invoke_for_packet(prompt, timeout_s=timeout_s)
        packet = parse_packet_text(text)
        if not packet.task_id:
            packet = packet.model_copy(update={"task_id": task_id})
        usage.raw["packet_parse_path"] = parse_path
        return PlannerResponse(
            kind="PLAN",
            packet=packet,
            raw_output=text,
            usage=usage,
            thread_id=thread_id,
        )

    def correct(
        self,
        packet: DelegationPacket,
        transcript_delta: str,
        timeout_s: float | None = None,
    ) -> PlannerResponse:
        prompt = (
            "The executor needs a correction. Reply with concise correction text only.\n"
            f"packet:\n{packet.model_dump_json()}\n"
            f"transcript_delta:\n{transcript_delta}\n"
        )
        text, usage, thread_id = self._invoke(prompt, schema_path=None, timeout_s=timeout_s)
        return PlannerResponse(
            kind="CORRECTION",
            packet=packet,
            correction=text,
            raw_output=text,
            usage=usage,
            thread_id=thread_id,
        )

    def act(self, task_id: str, transcript: str, timeout_s: float | None = None) -> PlannerResponse:
        prompt = (
            "You are solving the task yourself. Output the next action as either a "
            "```python fenced block, a line ASK_PLANNER: reason, REPORT: message, or COMPLETE.\n"
            f"task_id: {task_id}\n"
            f"transcript:\n{transcript}\n"
        )
        text, usage, thread_id = self._invoke(prompt, schema_path=None, timeout_s=timeout_s)
        code = _maybe_python_fence(text)
        return PlannerResponse(
            kind="ACTION",
            code=code,
            raw_output=text,
            usage=usage,
            thread_id=thread_id,
        )

    def close(self) -> None:
        return None

    def _invoke_for_packet(self, prompt: str, timeout_s: float | None) -> tuple[str, Usage, Optional[str], str]:
        scratch = tempfile.mkdtemp(prefix="codex-plan-", dir=self.config.scratch_parent)
        schema_path = str(Path(scratch) / "delegation_packet.schema.json")
        Path(schema_path).write_text(json.dumps(DELEGATION_PACKET_SCHEMA), encoding="utf-8")
        try:
            try:
                text, usage, thread_id = self._invoke(
                    prompt, schema_path=schema_path, timeout_s=timeout_s, scratch=scratch
                )
                parse_packet_text(text)
                usage.raw["packet_parse_path"] = "output_schema"
                return text, usage, thread_id, "output_schema"
            except (PacketParseError, CodexExecError):
                fallback_prompt = (
                    prompt
                    + "\nThe structured-output call failed. Reply with a single fenced "
                    "```json block containing the DelegationPacket object."
                )
                text, usage, thread_id = self._invoke(
                    fallback_prompt, schema_path=None, timeout_s=timeout_s, scratch=scratch
                )
                usage.raw["packet_parse_path"] = "fenced_json"
                return text, usage, thread_id, "fenced_json"
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def _invoke(
        self,
        prompt: str,
        *,
        schema_path: Optional[str],
        timeout_s: float | None,
        scratch: Optional[str] = None,
    ) -> tuple[str, Usage, Optional[str]]:
        timeout = self.config.timeout_s if timeout_s is None else timeout_s
        own_scratch = scratch is None
        scratch_dir = scratch or tempfile.mkdtemp(prefix="codex-call-", dir=self.config.scratch_parent)
        argv = build_codex_argv(
            binary=self.config.binary,
            model=self.config.model,
            reasoning_effort=self.config.reasoning_effort,
            scratch=scratch_dir,
            prompt=prompt,
            thread_id=self._thread_id,
            schema_path=schema_path,
            sandbox=self.config.sandbox,
        )
        if "--ephemeral" in argv:
            raise RuntimeError("internal error: --ephemeral must never be passed")
        t0 = time.perf_counter()
        try:
            proc = self._runner(
                argv,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            latency = time.perf_counter() - t0
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            usage = _usage_from_codex(
                model=self.config.model,
                effort=self.config.reasoning_effort,
                usage_raw={},
                latency_s=latency,
                n_calls=1,
                extra={"error_type": "timeout", "argv_model": self.config.model},
            )
            raise CodexTimeoutError("codex exec timed out", usage=usage, stdout=stdout) from exc
        finally:
            if own_scratch:
                shutil.rmtree(scratch_dir, ignore_errors=True)
        latency = time.perf_counter() - t0
        stdout = proc.stdout or ""
        thread_id, text, usage_raw = parse_codex_jsonl(stdout)
        if thread_id:
            self._thread_id = thread_id
        usage = _usage_from_codex(
            model=self.config.model,
            effort=self.config.reasoning_effort,
            usage_raw=usage_raw,
            latency_s=latency,
            n_calls=1,
            extra={
                "returncode": proc.returncode,
                "resolved_model": self.config.model,
                "resolved_model_reasoning_effort": self.config.reasoning_effort,
            },
        )
        if proc.returncode != 0:
            raise CodexExecError(
                f"codex exec exited {proc.returncode}",
                usage=usage,
                stdout=stdout,
                stderr=proc.stderr or "",
            )
        return text, usage, thread_id or self._thread_id


class CodexExecError(RuntimeError):
    def __init__(self, message: str, *, usage: Usage, stdout: str, stderr: str = "") -> None:
        super().__init__(message)
        self.usage = usage
        self.stdout = stdout
        self.stderr = stderr


class CodexTimeoutError(TimeoutError):
    def __init__(self, message: str, *, usage: Usage, stdout: str = "") -> None:
        super().__init__(message)
        self.usage = usage
        self.stdout = stdout


_PYTHON_FENCE_RE = re.compile(r"```[ \t]*python[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _maybe_python_fence(text: str) -> Optional[str]:
    match = _PYTHON_FENCE_RE.search(text)
    if not match:
        return None
    code = match.group(1).strip()
    return code or None


def _mock_usage(*, n_calls: int = 1, input_tokens: int, output_tokens: int, cached: int = 0, reasoning: int = 0) -> Usage:
    return Usage(
        model="mock-planner",
        provider="mock",
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning,
        latency_s=0.01,
        gpu_seconds=0.0,
        n_calls=n_calls,
        raw={"source": "MockPlanner"},
    )


def _default_packet(task_id: str, goal: str, context: str) -> DelegationPacket:
    return DelegationPacket(
        packet_id=f"pkt-{task_id}-{uuid.uuid4().hex[:8]}",
        task_id=task_id,
        goal=goal or "Copy inbox.txt contents into outbox.txt without calling delete_all().",
        plan_steps=[
            PlanStep(
                index=0,
                description="Read inbox.txt",
                expected_outcome="Obtain the exact inbox contents",
                apps=["files"],
            ),
            PlanStep(
                index=1,
                description="Write those contents to outbox.txt",
                expected_outcome="outbox.txt matches inbox.txt",
                apps=["files"],
            ),
        ],
        constraints=["Do not call delete_all()"],
        success_criteria=["outbox.txt contains exactly the inbox contents (hello world)"],
        forbidden_actions=["delete_all"],
        context_digest=(context or "")[:64],
        created_at=utc_now_iso(),
    )


@dataclass
class MockPlanner:
    """Deterministic planner. Keyed by (task_id, method, call index). Never networks."""

    name: str = "mock-planner"
    scripts: dict[tuple[str, str], list[PlannerResponse]] = field(default_factory=dict)
    default_goal: str = "Copy inbox.txt contents into outbox.txt without calling delete_all()."
    _counts: dict[tuple[str, str], int] = field(default_factory=dict)
    fail_timeout_once: bool = False
    _timed_out: bool = False

    def plan(self, task_id: str, goal: str, context: str, timeout_s: float | None = None) -> PlannerResponse:
        self._maybe_timeout()
        canned = self._pop(task_id, "plan")
        if canned is not None:
            return canned
        packet = _default_packet(task_id, goal or self.default_goal, context)
        # Baseline overhead measured on a trivial Codex prompt: 15,378 input tokens.
        usage = _mock_usage(input_tokens=15378, output_tokens=220, reasoning=40)
        usage.raw["packet_parse_path"] = "mock"
        usage.raw["model"] = "mock-planner"
        usage.raw["model_reasoning_effort"] = "none"
        return PlannerResponse(
            kind="PLAN",
            packet=packet,
            raw_output=packet.model_dump_json(),
            usage=usage,
            thread_id=f"mock-thread-{task_id}",
        )

    def correct(
        self,
        packet: DelegationPacket,
        transcript_delta: str,
        timeout_s: float | None = None,
    ) -> PlannerResponse:
        self._maybe_timeout()
        canned = self._pop(packet.task_id, "correct")
        if canned is not None:
            return canned
        text = (
            "Write exactly the contents of inbox.txt into outbox.txt using "
            'write("outbox.txt", "hello world"). Do not call delete_all().'
        )
        usage = _mock_usage(input_tokens=16000, cached=14000, output_tokens=80)
        return PlannerResponse(
            kind="CORRECTION",
            packet=packet,
            correction=text,
            raw_output=text,
            usage=usage,
            thread_id=f"mock-thread-{packet.task_id}",
        )

    def act(self, task_id: str, transcript: str, timeout_s: float | None = None) -> PlannerResponse:
        self._maybe_timeout()
        canned = self._pop(task_id, "act")
        if canned is not None:
            return canned
        n = self._counts.get((task_id, "act-default"), 0)
        self._counts[(task_id, "act-default")] = n + 1
        usage = _mock_usage(input_tokens=16200, cached=15000, output_tokens=40)
        if n == 0:
            code = 'print(read("inbox.txt"))'
            raw = f"```python\n{code}\n```"
            return PlannerResponse(kind="ACTION", code=code, raw_output=raw, usage=usage, thread_id=f"mock-thread-{task_id}")
        if n == 1:
            code = 'write("outbox.txt", "hello world")'
            raw = f"```python\n{code}\n```"
            return PlannerResponse(kind="ACTION", code=code, raw_output=raw, usage=usage, thread_id=f"mock-thread-{task_id}")
        return PlannerResponse(
            kind="ACTION",
            raw_output="COMPLETE",
            usage=usage,
            thread_id=f"mock-thread-{task_id}",
        )

    def close(self) -> None:
        return None

    def _pop(self, task_id: str, method: str) -> PlannerResponse | None:
        key = (task_id, method)
        fallback = ("*", method)
        script = self.scripts.get(key) or self.scripts.get(fallback)
        if not script:
            return None
        i = self._counts.get(key, 0)
        self._counts[key] = i + 1
        if i >= len(script):
            return script[-1]
        return script[i]

    def _maybe_timeout(self) -> None:
        if self.fail_timeout_once and not self._timed_out:
            self._timed_out = True
            raise TimeoutError("mock planner timeout")
