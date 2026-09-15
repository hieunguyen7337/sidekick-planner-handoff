"""sidekick: executor may ASK_PLANNER, gated by the verifier."""
from __future__ import annotations

from typing import Any

from sidekick.systems.loop import ConfigurableSystem, RunLimits, SystemPolicy


class Sidekick(ConfigurableSystem):
    name = "sidekick"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=True,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=True,
        adapter_name="sidekick",
        verifier_threshold=0.5,
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
