"""A planner served locally by vLLM, for the second-planner generality check (U11).

Every result in this project so far replays or drives one hosted planner family
(`gpt-5.6-luna` through `codex exec`). That leaves the obvious objection open: the channel
result may be a fact about *that* planner rather than about spending budget as actions.
This backend answers it at zero hosted cost by serving an open-weight planner on the
cluster's own GPUs, so the whole `planner_alone` -> prefix replay -> channel pair sequence
can be re-run against a second planner family.

Five things are deliberate:

* **The prompts are not written here.** They come from `planner.build_*_prompt`, the same
  functions `CodexExecPlanner` calls. If each backend spelled its own prompt, a difference
  in outcome would confound planner identity with prompt wording and the generality claim
  would be unfalsifiable. A test asserts both backends emit identical prompt text.
* **Packet parsing is not reimplemented** either: `parse_packet_text` already handles the
  fenced-JSON and bare-JSON shapes, and a second parser would be a second set of bugs.
* **Usage is reported with `provider="vllm"` and `gpu_seconds`, and no dollars.** A local
  planner has no provider price; pretending otherwise would put a fabricated number into
  the cost frontier, which is the one place this project cannot afford one.
* **The planner keeps one conversation per episode, as the hosted one does.**
  `CodexExecPlanner` resumes a single codex thread per instance and the runner builds one
  planner per episode, so the hosted planner sees, in context, its plan prompt (the only
  prompt that carries the API docs), its packet, and every earlier act/correct prompt with
  its own reply. The loop's planner transcript records a CODE action only as
  ``OBS: <text>`` -- the code itself is never in it -- so a stateless local planner would
  read observations without knowing what it ran, and would lose the API docs after
  `plan()`. The two arms would then differ in what the planner is told, not only in which
  planner it is. Each request is therefore ``[system] + thread + [new prompt]``, and a reply
  is appended to the thread only once the call has succeeded.

  The thread is compacted only when the server refuses it. On a 400 whose body names the
  maximum context length, the OLDEST exchange that is not the anchor is dropped for good and
  the request is resent, until it fits. The anchor -- the exchange made inside `plan()`, or
  the first exchange when the plan was replayed -- is never dropped: it carries the API docs
  (directly, or as `CachedPacketPlanner`'s prepended digest). When nothing droppable is
  left, `PlannerContextOverflow` is raised and the loop scores the episode as a ``limit``.

* **The plan call is structured, as the hosted one is.** `CodexExecPlanner` asks for the
  packet with ``--output-schema`` (DELEGATION_PACKET_SCHEMA) and only falls back to a
  fenced-JSON reply when that fails. The first LP-1 ceiling (job 25724309) made the plan call
  as free text instead: Qwen3-8B added a ``context`` key, copied the API docs into it, ran out
  of ``max_tokens`` before the JSON closed, and every episode ended ``parse_error`` at step 0
  -- an arm that measured nothing, from a request the hosted planner never makes. So `plan()`
  sends the same schema as ``response_format`` first (vLLM enforces it while decoding) and
  falls back exactly as codex does, with the same appended sentence
  (`STRUCTURED_OUTPUT_FALLBACK_SUFFIX`). `act`/`correct` stay free text on both backends.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from sidekick.agents.planner import (
    DELEGATION_PACKET_SCHEMA,
    STRUCTURED_OUTPUT_FALLBACK_SUFFIX,
    PacketParseError,
    PlannerContextOverflow,
    build_act_prompt,
    CORRECT_PROMPT_STYLES,
    build_advice_prompt,
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

# vLLM's wording when a request exceeds max_model_len ("This model's maximum context length
# is N tokens. However, you requested ..." -- vllm 0.29 renderers/params.py). Matched in one
# place, `is_context_overflow`, so a wording change is a one-line fix.
CONTEXT_OVERFLOW_TEXT = "maximum context length"

# The plan call's structured-output request: the OpenAI chat-completions `response_format`
# carrying the very schema object codex writes to its --output-schema file, so the two
# backends constrain the packet identically. vLLM 0.29 accepts this shape for chat
# completions: ChatCompletionRequest.response_format (entrypoints/openai/chat_completion/
# protocol.py:229) is a ResponseFormat whose `json_schema` is JsonSchemaResponseFormat{name,
# schema (alias), strict} (entrypoints/generate/base/protocol.py:70-76,103-106), and it
# becomes the guided-decoding `json` constraint (same file, :125-128).
PLAN_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "delegation_packet",
        "schema": DELEGATION_PACKET_SCHEMA,
        "strict": True,
    },
}

# A 4xx (other than a context overflow) whose body names one of these was a refusal of the
# structured-output request itself -- the request validator names `response_format` /
# `json_schema` (chat_completion/protocol.py:767-777), the grammar backend "JSON schema"
# (v1/structured_output/backend_xgrammar.py:352,359). That is the local counterpart of codex's
# `--output-schema` call exiting non-zero, and falls back the same way. Any other 4xx is a
# real error and still raises.
RESPONSE_FORMAT_REJECTION_TEXTS = ("response_format", "json_schema", "json schema", "structured_output")


class VllmPlannerError(RuntimeError):
    """The planner server could not be reached or returned an unusable response."""

    def __init__(self, message: str, *, usage: Usage, body: str = "") -> None:
        super().__init__(message)
        self.usage = usage
        self.body = body


class VllmPlannerContextOverflow(PlannerContextOverflow, VllmPlannerError):
    """The episode's thread does not fit the served context even with every droppable exchange gone.

    Both bases on purpose: the loop catches the backend-neutral `PlannerContextOverflow` and
    scores a ``limit``; anything that already catches `VllmPlannerError` still sees it.
    """

    def __init__(self, message: str, *, usage: Usage, body: str = "") -> None:
        RuntimeError.__init__(self, message)
        self.usage = usage
        self.body = body


class _ContextRejected(Exception):
    """One request refused for length. Internal: `_converse` compacts and resends on it."""

    def __init__(self, latency_s: float, body: str) -> None:
        super().__init__("request exceeds the planner's context window")
        self.latency_s = latency_s
        self.body = body


class _ResponseFormatRejected(Exception):
    """The server refused the structured-output request. Internal: `plan` falls back on it."""

    def __init__(self, usage: Usage, body: str) -> None:
        super().__init__("planner server refused the response_format request")
        self.usage = usage
        self.body = body


def is_response_format_rejection(status_code: Any, body: str) -> bool:
    """True for a non-overflow 4xx whose body names the structured-output request."""
    if not isinstance(status_code, int) or not 400 <= status_code < 500:
        return False
    if is_context_overflow(status_code, body):
        return False
    text = (body or "").lower()
    return any(needle in text for needle in RESPONSE_FORMAT_REJECTION_TEXTS)


def is_context_overflow(status_code: Any, body: str) -> bool:
    """True when the server refused a request for exceeding the model's context window.

    Any other 400 is a real error and must surface as `VllmPlannerError`, not be "fixed" by
    silently deleting the planner's memory.
    """
    return status_code == 400 and CONTEXT_OVERFLOW_TEXT in (body or "").lower()


@dataclass
class _Exchange:
    """One prior prompt and the planner's reply to it, as they are resent."""

    prompt: str
    reply: str
    anchor: bool


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
        correct_prompt: str = "correction",
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
        if correct_prompt not in CORRECT_PROMPT_STYLES:
            raise ValueError(f"unknown correct_prompt style {correct_prompt!r}")
        self.correct_prompt = correct_prompt
        # The episode's conversation, oldest first: the local counterpart of the codex thread
        # CodexExecPlanner resumes (one planner instance per episode, runner.run_single).
        self._thread: list[_Exchange] = []
        self._n_context_drops_total = 0

    # --- PlannerClient ------------------------------------------------------------------

    def plan(self, task_id: str, goal: str, context: str, timeout_s: float | None = None) -> PlannerResponse:
        # The same two attempts as CodexExecPlanner._invoke_for_packet: the plan prompt under
        # the packet schema (parse_path "output_schema"), then -- only if that reply does not
        # parse or the server refuses the schema -- the plan prompt plus the shared fallback
        # sentence, as free text (parse_path "fenced_json"). A planner that cannot produce a
        # packet twice is a real failure and must surface, not be papered over with a default
        # packet that would silently measure nothing.
        prompt = build_plan_prompt(task_id, goal, context)
        packet: DelegationPacket | None = None
        try:
            text, usage = self._converse(prompt, timeout_s, response_format=PLAN_RESPONSE_FORMAT)
        except _ResponseFormatRejected as rejected:
            usage = rejected.usage
        else:
            try:
                packet = parse_packet_text(text)
            except PacketParseError:
                packet = None

        if packet is not None:
            parse_path = "output_schema"
        else:
            # The failed exchange is NOT kept in the thread, and only the successful one
            # becomes the anchor: the failed reply carries nothing the loop uses, and both
            # prompts embed the API docs, so keeping it would park a second copy of them in
            # every later request -- a large share of a 32k window.
            prompt = prompt + STRUCTURED_OUTPUT_FALLBACK_SUFFIX
            text, retry_usage = self._converse(prompt, timeout_s)
            usage = _merge_usage(usage, retry_usage)
            packet = parse_packet_text(text)
            parse_path = "fenced_json"

        self._record(prompt, text, anchor=True)
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
        prompt = build_advice_prompt(packet, transcript_delta, self.correct_prompt)
        text, usage = self._converse(prompt, timeout_s)
        self._record(prompt, text)
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
        prompt = build_act_prompt(task_id, transcript, allow_handoff)
        text, usage = self._converse(prompt, timeout_s)
        self._record(prompt, text)
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

    # --- the episode thread --------------------------------------------------------------

    def _record(self, prompt: str, reply: str, *, anchor: bool = False) -> None:
        # With no plan() on this instance (a replayed plan), the first exchange is the anchor:
        # it is where CachedPacketPlanner prepends the API digest.
        anchor = anchor or not any(ex.anchor for ex in self._thread)
        self._thread.append(_Exchange(prompt=prompt, reply=reply, anchor=anchor))

    def _drop_oldest_exchange(self) -> bool:
        for i, ex in enumerate(self._thread):
            if not ex.anchor:
                del self._thread[i]
                return True
        return False

    def _converse(
        self,
        prompt: str,
        timeout_s: float | None = None,
        *,
        response_format: Optional[dict[str, Any]] = None,
    ) -> tuple[str, Usage]:
        """Send thread + prompt, compacting on a context overflow. Does not record the exchange."""
        drops = 0
        # Refused attempts still held the GPU while the server tokenised them.
        refused_latency_s = 0.0
        while True:
            try:
                text, usage = self._chat(self._messages(prompt), timeout_s, response_format=response_format)
            except _ResponseFormatRejected as rejected:
                # Nothing was generated; bill the time only, and say why the plan fell back.
                total = rejected.usage.latency_s + refused_latency_s
                usage = rejected.usage.model_copy(
                    update={
                        "latency_s": total,
                        "gpu_seconds": total * float(self.gpu_fraction),
                        "n_calls": 0,
                    }
                )
                usage.raw.update(self._thread_stats(drops))
                usage.raw["response_format_rejected"] = True
                raise _ResponseFormatRejected(usage, rejected.body) from None
            except _ContextRejected as rejected:
                refused_latency_s += rejected.latency_s
                if not self._drop_oldest_exchange():
                    usage = self._usage({}, refused_latency_s)
                    usage.raw.update(self._thread_stats(drops))
                    usage.raw["error_type"] = "context_overflow"
                    raise VllmPlannerContextOverflow(
                        "planner context overflow: the request does not fit the served context "
                        f"with {len(self._thread)} anchor exchange(s) and no droppable exchange "
                        f"left ({drops} dropped in this call)",
                        usage=usage,
                        body=rejected.body,
                    ) from None
                drops += 1
                self._n_context_drops_total += 1
                continue
            if refused_latency_s:
                total = usage.latency_s + refused_latency_s
                usage = usage.model_copy(
                    update={"latency_s": total, "gpu_seconds": total * float(self.gpu_fraction)}
                )
            usage.raw.update(self._thread_stats(drops))
            return text, usage

    def _thread_stats(self, drops: int) -> dict[str, int]:
        return {
            "n_context_drops": drops,
            "n_context_drops_total": self._n_context_drops_total,
            # Prior exchanges actually sent with this request, i.e. after any drops.
            "thread_exchanges": len(self._thread),
        }

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
        for ex in self._thread:
            messages.append({"role": "user", "content": ex.prompt})
            messages.append({"role": "assistant", "content": ex.reply})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _chat(
        self,
        messages: list[dict[str, str]],
        timeout_s: float | None = None,
        *,
        response_format: Optional[dict[str, Any]] = None,
    ) -> tuple[str, Usage]:
        client = self._ensure_client()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.chat_template_kwargs:
            payload["chat_template_kwargs"] = self.chat_template_kwargs
        # Only plan() passes one; act/correct are free text on both backends, as codex runs
        # them without --output-schema.
        if response_format is not None:
            payload["response_format"] = response_format

        t0 = time.perf_counter()
        response = client.post(self._chat_url(), json=payload)
        latency_s = time.perf_counter() - t0

        try:
            response.raise_for_status()
        except Exception as exc:
            status_code = getattr(response, "status_code", "?")
            body = _safe_text(response)
            if is_context_overflow(status_code, body):
                raise _ContextRejected(latency_s, body) from exc
            if response_format is not None and is_response_format_rejection(status_code, body):
                raise _ResponseFormatRejected(self._usage({}, latency_s), body) from exc
            raise VllmPlannerError(
                f"planner server returned {status_code}",
                usage=self._usage({}, latency_s),
                body=body,
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
    # The later call's thread state is the current one; the per-call drop counts are summed.
    raw = {**first.raw, **second.raw}
    raw["n_context_drops"] = int(first.raw.get("n_context_drops", 0)) + int(second.raw.get("n_context_drops", 0))
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
        raw=raw,
    )


def _safe_text(response: Any) -> str:
    try:
        return str(response.text)[:2000]
    except Exception:
        return ""
