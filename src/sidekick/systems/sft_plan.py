"""sft_plan: prompt_only protocol with a trained executor adapter."""
from __future__ import annotations

from typing import Any

from sidekick.systems.loop import ConfigurableSystem, RunLimits, SystemPolicy


class SftPlan(ConfigurableSystem):
    name = "sft_plan"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=True,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
        adapter_name="sft_plan",
    )

    def __init__(
        self,
        planner: Any,
        executor: Any | None = None,
        verifier: Any | None = None,
        limits: RunLimits | None = None,
        policy: SystemPolicy | None = None,
        adapter_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        if adapter_name is not None:
            kwargs["adapter_name"] = adapter_name
        super().__init__(planner, executor=executor, verifier=verifier, limits=limits, policy=policy, **kwargs)
