"""Cost ledger accumulating per-actor token/cost totals."""
from __future__ import annotations

from typing import Any

from sidekick.cost.prices import PriceSchedule
from sidekick.protocols.schemas import Role, Usage


class CostLedger:
    def __init__(self, prices: PriceSchedule) -> None:
        self.prices = prices
        self._per_actor: dict[str, dict[str, float]] = {}

    def add(self, actor: Role, usage: Usage) -> None:
        bucket = self._per_actor.setdefault(
            actor,
            {
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "n_calls": 0,
                "gpu_seconds": 0.0,
                "usd": 0.0,
            },
        )
        bucket["input_tokens"] += usage.input_tokens
        bucket["cached_input_tokens"] += usage.cached_input_tokens
        bucket["output_tokens"] += usage.output_tokens
        bucket["reasoning_output_tokens"] += usage.reasoning_output_tokens
        bucket["n_calls"] += usage.n_calls
        bucket["gpu_seconds"] += usage.gpu_seconds
        bucket["usd"] += self.prices.cost_usd(usage)

    def totals(self) -> dict[str, Any]:
        per_actor = {actor: dict(bucket) for actor, bucket in self._per_actor.items()}
        return {
            "per_actor": per_actor,
            "planner_tokens_total": self._tokens(per_actor.get("planner", {})),
            "planner_calls_total": int(per_actor.get("planner", {}).get("n_calls", 0)),
            "executor_tokens_total": self._tokens(per_actor.get("executor", {})),
            "gpu_seconds_total": sum(b.get("gpu_seconds", 0.0) for b in per_actor.values()),
            "usd_total": sum(b.get("usd", 0.0) for b in per_actor.values()),
        }

    @staticmethod
    def _tokens(bucket: dict[str, float]) -> int:
        return int(
            bucket.get("input_tokens", 0)
            + bucket.get("cached_input_tokens", 0)
            + bucket.get("output_tokens", 0)
            + bucket.get("reasoning_output_tokens", 0)
        )

    @staticmethod
    def frontier_displacement(collab_totals: dict[str, Any], baseline_totals: dict[str, Any]) -> dict[str, float]:
        """FCD = 1 - collab/baseline for planner tokens and planner calls.

        Divide-by-zero (baseline of 0) yields float("nan").
        """
        out: dict[str, float] = {}
        for key, name in (("planner_tokens_total", "fcd_tokens"), ("planner_calls_total", "fcd_calls")):
            base = baseline_totals.get(key, 0)
            collab = collab_totals.get(key, 0)
            out[name] = 1.0 - collab / base if base else float("nan")
        return out
