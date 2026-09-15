"""fixed_k: prompt_only plus planner review every k steps (default 5)."""
from __future__ import annotations

from typing import Any

from sidekick.systems.loop import ConfigurableSystem, RunLimits, SystemPolicy


class FixedK(ConfigurableSystem):
    name = "fixed_k"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=True,
        review_every_k=5,
        use_router=False,
        gate_ask_with_verifier=False,
    )

    def __init__(
        self,
        planner: Any,
        executor: Any | None = None,
        verifier: Any | None = None,
        limits: RunLimits | None = None,
        policy: SystemPolicy | None = None,
        k: int | None = None,
        **kwargs: Any,
    ) -> None:
        if k is not None:
            kwargs["review_every_k"] = k
        super().__init__(planner, executor=executor, verifier=verifier, limits=limits, policy=policy, **kwargs)
