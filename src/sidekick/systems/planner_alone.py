"""planner_alone: planner drives every step via act(); no executor."""
from __future__ import annotations

from sidekick.systems.loop import ConfigurableSystem, SystemPolicy


class PlannerAlone(ConfigurableSystem):
    name = "planner_alone"
    policy_defaults = SystemPolicy(
        # plan_first was False, which silently starved this arm: plan() is the only
        # call that carries env.api_docs_digest, so with it off the planner was never
        # told it had AppWorld APIs at all. Observed 2026-09-15 -- it answered a
        # Spotify task with "the Spotify plugin is not installed" and scored 0.0 TGC
        # on every task. The first call now seeds the codex thread with the API
        # digest, and because act() resumes that same thread, it stays in context.
        plan_first=True,
        planner_drives=True,
        allow_executor_ask=False,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
    )
