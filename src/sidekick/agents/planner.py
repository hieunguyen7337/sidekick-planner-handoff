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
from typing import Any, Callable, Iterable, Optional, Protocol

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

# Appended to the plan prompt when the structured-output plan call fails, by EVERY backend:
# CodexExecPlanner after its `--output-schema` call, VllmPlanner after its `response_format`
# call. One constant so the second attempt cannot differ in wording between the hosted and
# the local planner (see the prompt-sharing note below). The text is the hosted planner's
# own: editing it changes the prompts of every hosted arm.
STRUCTURED_OUTPUT_FALLBACK_SUFFIX = (
    "\nThe structured-output call failed. Reply with a single fenced "
    "```json block containing the DelegationPacket object."
)


class PlannerClient(Protocol):
    name: str

    def plan(self, task_id: str, goal: str, context: str) -> PlannerResponse: ...
    def correct(self, packet: DelegationPacket, transcript_delta: str) -> PlannerResponse: ...
    def act(
        self,
        task_id: str,
        transcript: str,
        timeout_s: float | None = None,
        allow_handoff: bool = False,
    ) -> PlannerResponse: ...
    def close(self) -> None: ...


# --- prompts, shared by every planner backend -------------------------------------------
#
# These are module-level and shared on purpose. The second-planner experiment asks whether
# the channel result depends on the *planner*, so the prompts the two backends issue must
# be identical; if each backend spelled its own, a difference in outcome would confound
# planner identity with prompt wording and the generality claim would be unfalsifiable.
# `test_vllm_planner` asserts the hosted and local planners produce the same prompt text
# for the same inputs.


def build_plan_prompt(task_id: str, goal: str, context: str) -> str:
    return (
        "Produce a DelegationPacket JSON object for this task.\n"
        f"task_id: {task_id}\n"
        f"goal: {goal}\n"
        f"context:\n{context}\n"
        "Fill every required field. plan_steps should be concrete and ordered."
    )


def build_correct_prompt(packet: DelegationPacket, transcript_delta: str) -> str:
    return (
        "The executor needs a correction. Reply with concise correction text only.\n"
        f"packet:\n{packet.model_dump_json()}\n"
        f"transcript_delta:\n{transcript_delta}\n"
    )


# Advice-prompt styles (plan 2026-09-23, experiment B2). "correction" is the wording every
# published advise arm used, and returns build_correct_prompt byte-for-byte. "neutral" removes
# the two features a reviewer called a handicap -- the presumption that the executor has erred
# ("needs a correction") and the cap ("concise correction text only") -- and keeps the packet
# and transcript lines identical, so the two styles differ in their first line only.
CORRECT_PROMPT_STYLES = ("correction", "neutral")


def build_advice_prompt(
    packet: DelegationPacket, transcript_delta: str, style: str = "correction"
) -> str:
    if style == "correction":
        return build_correct_prompt(packet, transcript_delta)
    if style == "neutral":
        return (
            "Advise the executor on how to proceed with this task: say what it should do next. "
            "You may include code.\n"
            f"packet:\n{packet.model_dump_json()}\n"
            f"transcript_delta:\n{transcript_delta}\n"
        )
    raise ValueError(
        f"unknown correct_prompt style {style!r}; expected one of {CORRECT_PROMPT_STYLES}"
    )


def build_act_prompt(task_id: str, transcript: str, allow_handoff: bool = False) -> str:
    prompt = (
        "You are solving the task yourself. Output the next action as either a "
        "```python fenced block, a line ASK_PLANNER: reason, REPORT: message, or COMPLETE.\n"
    )
    if allow_handoff:
        prompt += (
            "You may instead output a line HANDOFF meaning the remaining work is "
            "routine enough for a smaller local executor to finish.\n"
        )
    prompt += f"task_id: {task_id}\ntranscript:\n{transcript}\n"
    return prompt


class PacketParseError(ValueError):
    """Planner text could not be parsed into a DelegationPacket."""

    def __init__(self, raw_output: str, message: str = "could not parse DelegationPacket") -> None:
        super().__init__(message)
        self.raw_output = raw_output


class PlannerContextOverflow(RuntimeError):
    """The planner's episode conversation no longer fits its context window.

    Defined here rather than beside the vLLM backend so the loop can catch it without importing
    that module. A planner that cannot fit the episode has exhausted a budget, like the step or
    token caps, so the loop scores it as a ``limit`` rather than a ``crash``. Only the vLLM
    backend raises it; `CodexExecPlanner` never does, so hosted arms are unaffected.
    """

    def __init__(self, message: str, *, usage: Optional[Usage] = None) -> None:
        super().__init__(message)
        self.usage = usage


@dataclass
class CodexExecConfig:
    binary: str = "codex"
    model: str = DEFAULT_PLANNER_MODEL
    reasoning_effort: str = DEFAULT_REASONING_EFFORT
    sandbox: str = "read-only"
    timeout_s: float = DEFAULT_PLANNER_TIMEOUT_S
    scratch_parent: Optional[str] = None
    # Style of the advice prompt used by correct(); see build_advice_prompt.
    correct_prompt: str = "correction"


SubprocessRunner = Callable[..., subprocess.CompletedProcess]


def build_codex_argv(
    *,
    binary: str,
    model: str,
    reasoning_effort: str,
    scratch: str,
    thread_id: Optional[str] = None,
    schema_path: Optional[str] = None,
    sandbox: str = "read-only",
) -> list[str]:
    """Build a `codex exec` argv. Never includes `--ephemeral` (that blocks resume).

    The prompt is not an argv element (Linux MAX_ARG_STRLEN is 128 KiB). The
    caller must write it to the child's stdin and close the pipe. Do not also
    pass a positional PROMPT: `codex exec` would append stdin as a `<stdin>`
    block and the argv element would still hit E2BIG.
    """
    effort = f"model_reasoning_effort={reasoning_effort}"
    if thread_id:
        # `codex exec resume [OPTIONS] [SESSION_ID]` — prompt on stdin; no -s/-C.
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
        cmd.append(thread_id)
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
        prompt = build_plan_prompt(task_id, goal, context)
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
        prompt = build_advice_prompt(packet, transcript_delta, self.config.correct_prompt)
        text, usage, thread_id = self._invoke(prompt, schema_path=None, timeout_s=timeout_s)
        return PlannerResponse(
            kind="CORRECTION",
            packet=packet,
            correction=text,
            raw_output=text,
            usage=usage,
            thread_id=thread_id,
        )

    def act(
        self,
        task_id: str,
        transcript: str,
        timeout_s: float | None = None,
        allow_handoff: bool = False,
    ) -> PlannerResponse:
        prompt = build_act_prompt(task_id, transcript, allow_handoff)
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
                fallback_prompt = prompt + STRUCTURED_OUTPUT_FALLBACK_SUFFIX
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
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
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
        # Continuation turns are much smaller than a cold plan() call (15,378 input).
        usage = _mock_usage(input_tokens=2400, cached=1800, output_tokens=80)
        return PlannerResponse(
            kind="CORRECTION",
            packet=packet,
            correction=text,
            raw_output=text,
            usage=usage,
            thread_id=f"mock-thread-{packet.task_id}",
        )

    def act(
        self,
        task_id: str,
        transcript: str,
        timeout_s: float | None = None,
        allow_handoff: bool = False,
    ) -> PlannerResponse:
        self._maybe_timeout()
        canned = self._pop(task_id, "act")
        if canned is not None:
            return canned
        if "PROPOSED_ACTION:" in (transcript or ""):
            usage = _mock_usage(input_tokens=1800, cached=1200, output_tokens=60)
            return PlannerResponse(
                kind="ACTION",
                raw_output="looks fine",
                usage=usage,
                thread_id=f"mock-thread-{task_id}",
            )
        n = self._counts.get((task_id, "act-default"), 0)
        self._counts[(task_id, "act-default")] = n + 1
        usage = _mock_usage(input_tokens=1800, cached=1200, output_tokens=60)
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


class CachedPacketPlanner:
    """Replays archived planner packets instead of re-calling a live model.

    HJ-1 spent 936 hosted calls to produce 114 plans; every later arm that needs
    "the same plan for this task" replays the archived `plan` event instead of
    buying it again. Replay also removes plan-sampling noise: each arm sees a
    byte-identical plan per (task, seed).

    Replay is NOT a mock: `plan()` does no model I/O but returns the real
    packet HJ-1 bought, tagged `provider="cache"` with zero tokens and
    `n_calls=0` because nothing was bought. The campaign gate treats a
    zero-token "mock" record as a mistyped planner.type falling back to
    MockPlanner, so a replayed packet must never carry that tag.

    Because a replayed plan creates no codex thread, the inner planner's first
    live call starts from nothing where the original run resumed a session that
    already held the task context. We therefore store the `context` argument
    (the api-docs prompt) passed to `plan()` and prepend it, once, to the first
    live `correct()`/`act()` prompt. `CodexExecPlanner.correct` already embeds
    the full packet in its prompt, so the packet itself is not repeated.
    """

    name = "cached-packet"

    _DIGEST_BANNER = "=== api digest (plan was replayed; no prior session) ==="

    def __init__(
        self,
        inner: Any,
        packet_source: str | Path,
        system: str = "planner_alone",
        seed: int | None = None,
        on_missing: str = "fail",
        live_plan_keys: Iterable[str] | None = None,
    ) -> None:
        if on_missing not in ("fail", "call"):
            raise ValueError(f"on_missing must be 'fail' or 'call', got {on_missing!r}")
        self.inner = inner
        self.packet_source = Path(packet_source)
        self.system = system
        # The planner protocol's plan() carries no seed, but the archive is
        # keyed <system>/<seed>/<task_id>; the runner knows the seed of the
        # episode it is about to run, so it is fixed at construction time.
        self.seed = seed
        self.on_missing = on_missing
        # Registered exceptions to on_missing="fail", as "<seed>/<task_id>": keys whose source
        # episode ended before the planner wrote any plan (e.g. a step-0 parse_error), so there is
        # nothing to replay. Only these call the inner planner live; any other miss still raises.
        keys = [str(k) for k in (live_plan_keys or [])]
        for key in keys:
            seed_part, sep, task_part = key.partition("/")
            if not sep or not seed_part.isdigit() or not task_part:
                raise ValueError(f"live_plan_keys entries must be '<seed>/<task_id>', got {key!r}")
        self.live_plan_keys = frozenset(keys)
        self._context: str | None = None
        self._digest_prepended = False

    def _events_path(self, task_id: str) -> Path:
        if self.seed is None:
            # No seed supplied: glob the seed directories and fail loudly rather
            # than silently replaying an arbitrary attempt's plan.
            matches = sorted(self.packet_source.glob(f"{self.system}/*/{task_id}/events.jsonl"))
            if not matches:
                raise FileNotFoundError(
                    f"no cached planner packet under {self.packet_source}/{self.system}/*/ for task {task_id}"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"task {task_id} appears under {len(matches)} seeds without a configured seed: "
                    + ", ".join(str(m) for m in matches)
                )
            return matches[0]
        return self.packet_source / self.system / str(self.seed) / task_id / "events.jsonl"

    def _load_plan_event(self, task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Return (plan-event payload, plan-event usage) for this task.

        Reads the file FORWARDS and uses only events after the LAST
        `run_start`: a retried run appends to the dead attempt's log, so a file
        can hold two attempts concatenated with nothing marking the boundary
        (docs/FOLLOWUPS.md). Ordering comes from file order, never from `ts`:
        AppWorld freezes time with freezegun, so `ts` is identical across
        events and cannot order them.
        """
        path = self._events_path(task_id)
        if not path.is_file():
            raise FileNotFoundError(f"no cached planner packet for task {task_id} at {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        last_run_start = -1
        for i, line in enumerate(lines):
            if '"run_start"' in line:
                last_run_start = i
        plan_payload: dict[str, Any] | None = None
        plan_usage: dict[str, Any] = {}
        for line in lines[last_run_start + 1 :]:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue  # a truncated trailing line must not break replay
            if not isinstance(obj, dict):
                continue
            if obj.get("event_type") == "plan" and isinstance(obj.get("payload"), dict):
                if isinstance(obj["payload"].get("packet"), dict):
                    plan_payload = obj["payload"]
                    plan_usage = obj.get("usage") or {}
        if plan_payload is None:
            raise FileNotFoundError(f"no archived plan event found for task {task_id} at {path}")
        return plan_payload, plan_usage

    def plan(self, task_id: str, goal: str, context: str, timeout_s: float | None = None) -> PlannerResponse:
        # Remember what plan() was handed: on a replayed plan there is no prior
        # codex session, so the first live call needs the api digest prepended.
        self._context = context
        try:
            payload, event_usage = self._load_plan_event(task_id)
        except FileNotFoundError:
            if self.on_missing == "call" or f"{self.seed}/{task_id}" in self.live_plan_keys:
                return self.inner.plan(task_id, goal, context, timeout_s=timeout_s)
            raise
        packet = DelegationPacket.model_validate(payload["packet"])
        # Provenance must point at the ORIGINAL model even though nothing was
        # bought here: campaign_summarize._planner_models reads usage.model on
        # planner-attributed records, and the gate has to report the hosted
        # model id for a replayed arm too.
        model = payload.get("model") or (event_usage or {}).get("model") or ""
        if not model:
            raise ValueError(f"cached plan event for {task_id} records no model id at {self._events_path(task_id)}")
        raw: dict[str, Any] = {"cached_from": str(self._events_path(task_id))}
        thread_id = payload.get("thread_id")
        if thread_id is not None:
            raw["cached_thread_id"] = thread_id
        usage = Usage(
            model=model,
            provider="cache",
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_output_tokens=0,
            latency_s=0.0,
            gpu_seconds=0.0,
            n_calls=0,
            raw=raw,
        )
        return PlannerResponse(
            kind="PLAN",
            packet=packet,
            raw_output=json.dumps(payload["packet"], sort_keys=True),
            usage=usage,
            thread_id=thread_id if isinstance(thread_id, str) else None,
        )

    def _prepended_context(self) -> str:
        if self._digest_prepended or self._context is None:
            return ""
        self._digest_prepended = True
        return f"{self._DIGEST_BANNER}\n{self._context}\n"

    def correct(
        self,
        packet: DelegationPacket,
        transcript_delta: str,
        timeout_s: float | None = None,
    ) -> PlannerResponse:
        return self.inner.correct(packet, self._prepended_context() + transcript_delta, timeout_s=timeout_s)

    def act(
        self,
        task_id: str,
        transcript: str,
        timeout_s: float | None = None,
        allow_handoff: bool = False,
    ) -> PlannerResponse:
        text = self._prepended_context() + transcript
        return self.inner.act(
            task_id, text, timeout_s=timeout_s, allow_handoff=allow_handoff
        )

    def close(self) -> None:
        self.inner.close()
