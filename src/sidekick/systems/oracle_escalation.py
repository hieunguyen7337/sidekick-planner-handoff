"""oracle_escalation: escalate exactly when a recorded oracle label says to."""
from __future__ import annotations

from typing import Any, Iterable

from sidekick.systems.loop import ConfigurableSystem, RunLimits, SystemPolicy


class OracleEscalation(ConfigurableSystem):
    name = "oracle_escalation"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=False,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
        oracle_steps=frozenset(),
    )

    def __init__(
        self,
        planner: Any,
        executor: Any | None = None,
        verifier: Any | None = None,
        limits: RunLimits | None = None,
        policy: SystemPolicy | None = None,
        oracle_steps: Iterable[int] | None = None,
        **kwargs: Any,
    ) -> None:
        if oracle_steps is not None:
            kwargs["oracle_steps"] = frozenset(int(s) for s in oracle_steps)
        super().__init__(planner, executor=executor, verifier=verifier, limits=limits, policy=policy, **kwargs)
