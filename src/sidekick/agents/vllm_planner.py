"""A planner served locally by vLLM, for the second-planner generality check (U11).

Every result in this project so far replays or drives one hosted planner family
(`gpt-5.6-luna` through `codex exec`). That leaves the obvious objection open: the channel
result may be a fact about *that* planner rather than about spending budget as actions.
This backend answers it at zero hosted cost by serving an open-weight planner on the
cluster's own GPUs, so the whole `planner_alone` -> prefix replay -> channel pair sequence
can be re-run against a second planner family.

Three things are deliberate:

* **The prompts are not written here.** They come from `planner.build_*_prompt`, the same
  functions `CodexExecPlanner` calls. If each backend spelled its own prompt, a difference
  in outcome would confound planner identity with prompt wording and the generality claim
  would be unfalsifiable. A test asserts both backends emit identical prompt text.
* **Packet parsing is not reimplemented** either: `parse_packet_text` already handles the
  fenced-JSON and bare-JSON shapes, and a second parser would be a second set of bugs.
* **Usage is reported with `provider="vllm"` and `gpu_seconds`, and no dollars.** A local
  planner has no provider price; pretending otherwise would put a fabricated number into
  the cost frontier, which is the one place this project cannot afford one.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from sidekick.agents.planner import (
    PacketParseError,
    build_act_prompt,
    build_correct_prompt,
    build_plan_prompt,
    parse_packet_text,
    _maybe_python_fence,
)
from sidekick.protocols.schemas import DelegationPacket, PlannerResponse, Usage

DEFAULT_TIMEOUT_S = 300.0
DEFAULT_MAX_TOKENS = 2048
# A planner that deliberates forever emits no action and the episode dies on the step cap
# rather than on anything informative - the exact failure mode measured on the tailored
# Qwen executor. Keep the knob explicit at the call site.
DEFAULT_TEMPERATURE = 0.7


class VllmPlannerError(RuntimeError):
    """The planner server could not be reached or returned an unusable response."""

    def __init__(self, message: str, *, usage: Usage, body: str = "") -> None:
        super().__init__(message)
        self.usage = usage
        self.body = body


class VllmPlanner:
    """OpenAI-compatible chat client driving an open-weight planner served by vLLM."""

    name = "vllm-planner"

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        gpu_fraction: float = 1.0,
        http_client: Any | None = None,
        chat_template_kwargs: Optional[dict] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.gpu_fraction = gpu_fraction
        self._http = http_client
        # Mirrors VLLMExecutor: a thinking template left on its default spends the whole
        # budget reasoning and returns no content.
        self.chat_template_kwargs = chat_template_kwargs or None
        self.system_prompt = system_prompt

    # --- PlannerClient ------------------------------------------------------------------

    def plan(self, task_id: str, goal: str, context: str, timeout_s: float | None = None) -> PlannerResponse:
        text, usage = self._chat(build_plan_prompt(task_id, goal, context), timeout_s)
        try:
            packet = parse_packet_text(text)
            parse_path = "fenced_json"
        except PacketParseError:
            # One retry with an explicit instruction, mirroring the hosted backend's
            # structured-output -> fenced-JSON fallback. A planner that cannot produce a
            # packet twice is a real failure and must surface, not be papered over with a
            # default packet that would silently measure nothing.
            retry_prompt = (
                build_plan_prompt(task_id, goal, context)
                + "\nYour previous reply could not be parsed. Reply with a single fenced "
                "```json block containing only the DelegationPacket object."
            )
            text, retry_usage = self._chat(retry_prompt, timeout_s)
            usage = _merge_usage(usage, retry_usage)
            packet = parse_packet_text(text)
            parse_path = "fenced_json_retry"

        if not packet.task_id:
            packet = packet.model_copy(update={"task_id": task_id})
        usage.raw["packet_parse_path"] = parse_path
        return PlannerResponse(kind="PLAN", packet=packet, raw_output=text, usage=usage)

    def correct(
        self,
        packet: DelegationPacket,
        transcript_delta: str,
        timeout_s: float | None = None,
    ) -> PlannerResponse:
        text, usage = self._chat(build_correct_prompt(packet, transcript_delta), timeout_s)
        return PlannerResponse(
            kind="CORRECTION",
            packet=packet,
            correction=text,
            raw_output=text,
            usage=usage,
        )

    def act(
        self,
        task_id: str,
        transcript: str,
        timeout_s: float | None = None,
        allow_handoff: bool = False,
    ) -> PlannerResponse:
        text, usage = self._chat(build_act_prompt(task_id, transcript, allow_handoff), timeout_s)
        return PlannerResponse(
            kind="ACTION",
            code=_maybe_python_fence(text),
            raw_output=text,
            usage=usage,
        )

    def close(self) -> None:
        if self._http is not None and hasattr(self._http, "close"):
            try:
                self._http.close()
            except Exception:
                pass
        self._http = None

    # --- transport ----------------------------------------------------------------------

    def _ensure_client(self) -> Any:
        if self._http is None:
            import httpx

            self._http = httpx.Client(timeout=self.timeout_s)
        return self._http

    def _chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _messages(self, prompt: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _chat(self, prompt: str, timeout_s: float | None = None) -> tuple[str, Usage]:
        client = self._ensure_client()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(prompt),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.chat_template_kwargs:
            payload["chat_template_kwargs"] = self.chat_template_kwargs

        t0 = time.perf_counter()
        response = client.post(self._chat_url(), json=payload)
        latency_s = time.perf_counter() - t0

        try:
            response.raise_for_status()
        except Exception as exc:
            raise VllmPlannerError(
                f"planner server returned {getattr(response, 'status_code', '?')}",
                usage=self._usage({}, latency_s),
                body=_safe_text(response),
            ) from exc

        body = response.json()
        choices = body.get("choices") or []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get("message") or {}
        text = message.get("content") or ""
        if not text:
            # With a reasoning parser enabled the whole generation can land in
            # reasoning_content, leaving content empty; that reaches the loop as an
            # unparseable "" with no hint of why.
            text = message.get("reasoning_content") or ""

        return text, self._usage(body.get("usage") or {}, latency_s)

    def _usage(self, usage_raw: dict[str, Any], latency_s: float) -> Usage:
        details = usage_raw.get("prompt_tokens_details") or {}
        cached = int(details.get("cached_tokens") or 0) if isinstance(details, dict) else 0
        return Usage(
            model=str(self.model),
            # Not "openai": this planner costs GPU time, not provider dollars, and the
            # cost frontier must not be handed a fabricated price.
            provider="vllm",
            input_tokens=int(usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens") or 0),
            cached_input_tokens=cached,
            output_tokens=int(usage_raw.get("completion_tokens") or usage_raw.get("output_tokens") or 0),
            reasoning_output_tokens=int(usage_raw.get("reasoning_tokens") or 0),
            latency_s=latency_s,
            gpu_seconds=latency_s * float(self.gpu_fraction),
            n_calls=1,
        )


def _merge_usage(first: Usage, second: Usage) -> Usage:
    """Sum two calls so a retry is billed as the two calls it really was."""
    return Usage(
        model=second.model,
        provider=second.provider,
        input_tokens=first.input_tokens + second.input_tokens,
        cached_input_tokens=first.cached_input_tokens + second.cached_input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        reasoning_output_tokens=first.reasoning_output_tokens + second.reasoning_output_tokens,
        latency_s=first.latency_s + second.latency_s,
        gpu_seconds=first.gpu_seconds + second.gpu_seconds,
        n_calls=first.n_calls + second.n_calls,
    )


def _safe_text(response: Any) -> str:
    try:
        return str(response.text)[:2000]
    except Exception:
        return ""
