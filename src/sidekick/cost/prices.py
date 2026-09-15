"""Price schedule loaded from YAML (rates per 1M tokens, USD)."""
from __future__ import annotations

from pathlib import Path

import yaml

from sidekick.protocols.schemas import Usage


class UnknownModelError(ValueError):
    """Raised when a usage record references a model absent from the schedule."""


class PriceSchedule:
    def __init__(self, data: dict) -> None:
        self.schedule_date: str = data.get("schedule_date", "")
        self.source: str = data.get("source", "")
        self.models: dict[str, dict[str, float]] = dict(data.get("models", {}))
        local = data.get("local", {}) or {}
        self.usd_per_gpu_hour: float = float(local.get("usd_per_gpu_hour", 0.0))

    @classmethod
    def load(cls, path: str | Path) -> "PriceSchedule":
        with open(path, "r", encoding="utf-8") as fh:
            return cls(yaml.safe_load(fh) or {})

    def cost_usd(self, usage: Usage) -> float:
        """USD cost for one Usage record.

        - codex: (input - cached_input) at `input`, cached_input at `cached_input`,
          (output + reasoning_output) at `output` — reasoning tokens are billed as output.
        - vllm: gpu_seconds/3600 * usd_per_gpu_hour, no token cost.
        - mock: 0.0.
        """
        if usage.provider == "mock":
            return 0.0
        if usage.provider == "vllm":
            return usage.gpu_seconds / 3600.0 * self.usd_per_gpu_hour
        # provider == "codex"
        rates = self.models.get(usage.model)
        if rates is None:
            raise UnknownModelError(f"model {usage.model!r} not in price schedule")
        input_rate = float(rates["input"]) / 1_000_000.0
        cached_rate = float(rates["cached_input"]) / 1_000_000.0
        output_rate = float(rates["output"]) / 1_000_000.0
        uncached_input = max(0, usage.input_tokens - usage.cached_input_tokens)
        output_total = usage.output_tokens + usage.reasoning_output_tokens
        return (
            uncached_input * input_rate
            + usage.cached_input_tokens * cached_rate
            + output_total * output_rate
        )
