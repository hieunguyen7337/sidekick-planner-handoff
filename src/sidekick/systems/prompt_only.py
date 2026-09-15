"""prompt_only: plan once; executor may ASK_PLANNER; planner answers via correct()."""
from __future__ import annotations

from sidekick.systems.loop import ConfigurableSystem, SystemPolicy


class PromptOnly(ConfigurableSystem):
    name = "prompt_only"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=True,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
    )
