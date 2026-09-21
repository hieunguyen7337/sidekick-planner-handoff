"""planner_handoff: planner drives until a HANDOFF, then the local executor finishes."""
from __future__ import annotations

from dataclasses import replace

from sidekick.systems.planner_alone import PlannerAlone


class PlannerHandoff(PlannerAlone):
    name = "planner_handoff"
    policy_defaults = replace(PlannerAlone.policy_defaults, handoff_allowed=True)
