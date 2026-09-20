"""action_review: executor proposes; planner may approve or replace before env.step."""
from __future__ import annotations

from typing import Any

from sidekick.systems.loop import ConfigurableSystem, RunLimits, SystemPolicy


class ActionReview(ConfigurableSystem):
    name = "action_review"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=True,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
        adapter_name="sft_plan",
        verifier_threshold=0.5,
        review_proposed_action=True,
    )

    def __init__(
        self,
        planner: Any,
        executor: Any | None = None,
        verifier: Any | None = None,
        limits: RunLimits | None = None,
        policy: SystemPolicy | None = None,
        adapter_name: str | None = None,
        verifier_threshold: float | None = None,
        **kwargs: Any,
    ) -> None:
        if adapter_name is not None:
            kwargs["adapter_name"] = adapter_name
        if verifier_threshold is not None:
            kwargs["verifier_threshold"] = verifier_threshold
        super().__init__(planner, executor=executor, verifier=verifier, limits=limits, policy=policy, **kwargs)
