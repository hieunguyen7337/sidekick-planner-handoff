"""executor_alone: executor only, task instruction, no plan, no escalation."""
from __future__ import annotations

from sidekick.systems.loop import ConfigurableSystem, SystemPolicy


class ExecutorAlone(ConfigurableSystem):
    name = "executor_alone"
    policy_defaults = SystemPolicy(
        plan_first=False,
        planner_drives=False,
        allow_executor_ask=False,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
    )
