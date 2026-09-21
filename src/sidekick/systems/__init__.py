from sidekick.systems.action_review import ActionReview
from sidekick.systems.executor_alone import ExecutorAlone
from sidekick.systems.fixed_k import FixedK
from sidekick.systems.oracle_escalation import OracleEscalation
from sidekick.systems.planner_alone import PlannerAlone
from sidekick.systems.prefix_handoff import PrefixHandoff
from sidekick.systems.prompt_only import PromptOnly
from sidekick.systems.router_seq import RouterSeq
from sidekick.systems.sidekick import Sidekick
from sidekick.systems.sft_plan import SftPlan

# Seam contract lists eight names. action_review is an additional experimental
# system (E4). Keep the original eight first so existing exact-tuple tests stay
# a prefix; append extras (action_review, then prefix_handoff).
SYSTEM_NAMES = (
    "planner_alone",
    "executor_alone",
    "prompt_only",
    "fixed_k",
    "sft_plan",
    "router_seq",
    "sidekick",
    "oracle_escalation",
    "action_review",
    "prefix_handoff",
)

SYSTEMS = {
    "planner_alone": PlannerAlone,
    "executor_alone": ExecutorAlone,
    "prompt_only": PromptOnly,
    "fixed_k": FixedK,
    "sft_plan": SftPlan,
    "router_seq": RouterSeq,
    "sidekick": Sidekick,
    "oracle_escalation": OracleEscalation,
    "action_review": ActionReview,
    "prefix_handoff": PrefixHandoff,
}


def get_system(name: str, **kwargs):
    try:
        cls = SYSTEMS[name]
    except KeyError as exc:
        raise KeyError(f"unknown system {name!r}; known: {list(SYSTEM_NAMES)}") from exc
    return cls(**kwargs)


__all__ = [
    "SYSTEMS",
    "SYSTEM_NAMES",
    "get_system",
    "PlannerAlone",
    "ExecutorAlone",
    "PromptOnly",
    "FixedK",
    "SftPlan",
    "RouterSeq",
    "Sidekick",
    "OracleEscalation",
    "ActionReview",
    "PrefixHandoff",
]
