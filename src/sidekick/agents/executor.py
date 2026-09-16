"""Executor clients: vLLM OpenAI-compatible HTTP and a scripted mock."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from sidekick.protocols.prompts import fit_messages_to_budget
from sidekick.protocols.schemas import Usage

logger = logging.getLogger(__name__)

DEFAULT_READ_SCRIPT = '```python\nprint(read("inbox.txt"))\n```'
DEFAULT_WRITE_SCRIPT = '```python\nwrite("outbox.txt", "hello world")\n```'
DEFAULT_EXECUTOR_SCRIPT = [DEFAULT_READ_SCRIPT, DEFAULT_WRITE_SCRIPT, "COMPLETE"]


class LLMClient(Protocol):
    def complete(self, messages: list[dict], **kw) -> tuple[str, Usage]: ...


class VLLMExecutor:
    """OpenAI-compatible chat client for a vLLM server.

    ``gpu_seconds`` is estimated as request wall-time (``latency_s``) times
    ``gpu_fraction``, the share of the server this run owns. The default
    ``gpu_fraction=1.0`` means one request at a time: this run is charged the
    full measured latency as GPU-seconds. If several jobs share one server,
    set ``gpu_fraction`` to ``1 / n_concurrent`` (or the fraction of GPUs
    reserved for this run).
    """

    name = "vllm-executor"

    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        lora_name: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        gpu_fraction: float = 1.0,
        timeout_s: float = 120.0,
        http_client: Any | None = None,
        chat_template_kwargs: Optional[dict] = None,
        stop: Optional[list[str]] = None,
        max_prompt_tokens: Optional[int] = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.lora_name = lora_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.gpu_fraction = gpu_fraction
        self.timeout_s = timeout_s
        self._http = http_client
        # Prompt budget: when set, the conversation is fitted to this many prompt
        # tokens with the SAME policy SFT training uses (fit_messages_to_budget), so
        # a conversation the model was trained on never 400s at serve time. Measured
        # 2026-09-15 (HJ-1R arm B): 6/114 episodes crashed with vLLM 400 Bad Request
        # on max_model_len=32768 because prompt_only prepends the plan packet and
        # api digest, making its prompts longer than arm A's.
        self.max_prompt_tokens = max_prompt_tokens
        # Lazily loaded; never touched when max_prompt_tokens is None.
        self._tokenizer: Any = None
        self._tokenizer_loaded = False
        # Passed straight through to vLLM, which hands them to the model's Jinja
        # chat template. Granite 4.2's template defines `enable_thinking`, default
        # True, and a thinking model will spend its whole budget reasoning without
        # ever emitting an action -- measured 2026-09-15: 3072 output tokens of
        # deliberation and no fenced block.
        self.chat_template_kwargs = chat_template_kwargs or None
        # Stop sequences end the generation at the close of the first action. Without
        # them Granite writes an action, then invents the output it expects, then
        # reasons over its own invention for the rest of the budget -- observed
        # 2026-09-15 on every executor_alone episode. The parser only ever reads the
        # first block, so the rest was pure GPU cost. Do NOT put a bare "```" here: it
        # matches the OPENING fence of a fenced block and truncates to nothing.
        self.stop = list(stop) if stop else None

    def complete(self, messages: list[dict], **kw) -> tuple[str, Usage]:
        client = self._ensure_client()
        model = kw.get("lora_name") or self.lora_name or self.model
        messages = list(messages)
        n_messages_dropped = 0
        if self.max_prompt_tokens is not None:
            messages, n_messages_dropped, _ = fit_messages_to_budget(
                messages,
                max_tokens=self.max_prompt_tokens,
                length_fn=self._count_prompt_tokens,
            )
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kw.get("temperature", self.temperature),
            "max_tokens": kw.get("max_tokens", self.max_tokens),
        }
        ctk = kw.get("chat_template_kwargs", self.chat_template_kwargs)
        if ctk:
            payload["chat_template_kwargs"] = ctk
        stop = kw.get("stop", self.stop)
        if stop:
            payload["stop"] = stop
        url = self._chat_url()
        # 400 backstop: the tokenizer's count can disagree with the server's. Drop
        # the oldest remaining middle message and retry, at most twice, then give up
        # and raise as before. Never silently shrink below the anchor set.
        n_400_retries = 0
        for attempt in range(3):
            payload["messages"] = messages
            t0 = time.perf_counter()
            response = client.post(url, json=payload)
            latency_s = time.perf_counter() - t0
            try:
                response.raise_for_status()
            except Exception as exc:
                if (
                    response.status_code == 400
                    and len(messages) > 3
                    and attempt < 2
                ):
                    n_400_retries += 1
                    del messages[2]
                    continue
                raise
            break
        body = response.json()
        text = ""
        choices = body.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            text = message.get("content") or ""
            if not text:
                # With a reasoning parser enabled (e.g. granite_thinking_parser) the
                # model's whole generation can land in reasoning_content, leaving
                # content empty -- which reaches the loop as an unparseable "" and is
                # logged as parse_error with no hint of why. Observed 2026-09-15:
                # granite-4.2-8b spent all 1024 max_tokens and returned "".
                text = message.get("reasoning_content") or ""
        usage_raw = body.get("usage") or {}
        cached = 0
        details = usage_raw.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            cached = int(details.get("cached_tokens") or 0)
        gpu_seconds = latency_s * float(self.gpu_fraction)
        usage = Usage(
            model=str(model),
            provider="vllm",
            input_tokens=int(usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens") or 0),
            cached_input_tokens=cached,
            output_tokens=int(usage_raw.get("completion_tokens") or usage_raw.get("output_tokens") or 0),
            reasoning_output_tokens=int(usage_raw.get("reasoning_tokens") or 0),
            latency_s=latency_s,
            gpu_seconds=gpu_seconds,
            n_calls=1,
            raw={
                "gpu_fraction": self.gpu_fraction,
                "gpu_seconds_formula": "latency_s * gpu_fraction",
                "base_url": self.base_url,
                "lora_name": self.lora_name,
                "max_prompt_tokens": self.max_prompt_tokens,
                "n_messages_dropped": n_messages_dropped,
                "n_400_retries": n_400_retries,
            },
        )
        return text, usage

    def close(self) -> None:
        if self._http is not None and hasattr(self._http, "close"):
            self._http.close()

    def _get_tokenizer(self) -> Any:
        """Lazily load the model tokenizer; never called when max_prompt_tokens is None."""
        if self._tokenizer_loaded:
            return self._tokenizer
        self._tokenizer_loaded = True
        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model)
        except Exception as exc:  # never crash an episode over a tokenizer
            logger.warning(
                "could not load tokenizer for %s (%s); falling back to a "
                "conservative characters//3 length heuristic",
                self.model,
                exc,
            )
            self._tokenizer = None
        return self._tokenizer

    def _count_prompt_tokens(self, messages: list[dict]) -> int:
        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            apply = getattr(tokenizer, "apply_chat_template", None)
            try:
                if callable(apply):
                    text = apply(messages, tokenize=False, add_generation_prompt=True)
                else:
                    text = "\n".join(str(m.get("content", "")) for m in messages)
                return len(tokenizer.encode(text))
            except Exception:
                pass
        text = "\n".join(str(m.get("content", "")) for m in messages)
        return len(text) // 3

    def _chat_url(self) -> str:
        base = self.base_url
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def _ensure_client(self) -> Any:
        if self._http is not None:
            return self._http
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - exercised only without httpx
            raise RuntimeError("httpx is required for VLLMExecutor") from exc
        self._http = httpx.Client(timeout=self.timeout_s)
        return self._http


@dataclass
class MockExecutor:
    """Scripted executor. Emits canned actions; never touches the network."""

    name: str = "mock-executor"
    script: list[str] = field(default_factory=lambda: list(DEFAULT_EXECUTOR_SCRIPT))
    task_scripts: dict[str, list[str]] = field(default_factory=dict)
    last_lora_name: Optional[str] = None
    last_messages: list[dict] | None = None
    _index: int = 0
    _task_index: dict[str, int] = field(default_factory=dict)

    def complete(self, messages: list[dict], **kw) -> tuple[str, Usage]:
        self.last_messages = messages
        self.last_lora_name = kw.get("lora_name")
        task_id = kw.get("task_id")
        raw = self._next_raw(task_id)
        usage = Usage(
            model=self.last_lora_name or "mock-executor",
            provider="mock",
            input_tokens=120,
            output_tokens=40,
            latency_s=0.01,
            gpu_seconds=0.01,
            n_calls=1,
            raw={"lora_name": self.last_lora_name},
        )
        return raw, usage

    def close(self) -> None:
        return None

    def _next_raw(self, task_id: str | None) -> str:
        if task_id and task_id in self.task_scripts:
            i = self._task_index.get(task_id, 0)
            script = self.task_scripts[task_id]
            self._task_index[task_id] = i + 1
            if i >= len(script):
                return "COMPLETE"
            return script[i]
        if self._index >= len(self.script):
            return "COMPLETE"
        raw = self.script[self._index]
        self._index += 1
        return raw
