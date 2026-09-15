"""planner_alone: planner drives every step via act(); no executor."""
from __future__ import annotations

from sidekick.systems.loop import ConfigurableSystem, SystemPolicy


class PlannerAlone(ConfigurableSystem):
    name = "planner_alone"
    policy_defaults = SystemPolicy(
        plan_first=False,
        planner_drives=True,
        allow_executor_ask=False,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
    )
