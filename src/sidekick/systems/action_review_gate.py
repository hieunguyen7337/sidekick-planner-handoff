"""Pre-execution action review, called from ``run_episode``.

Kept out of ``loop.py`` so the episode loop file does not grow further. The
planner transport is still ``planner.correct`` via the loop's ``call_planner``.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from sidekick.agents.verifier import ConstantVerifier
from sidekick.protocols.prompts import format_executor_action
from sidekick.protocols.schemas import DelegationPacket, ExecutorAction, PlannerResponse


def run_action_review(
    *,
    action: ExecutorAction,
    step: int,
    packet: Optional[DelegationPacket],
    policy: Any,
    verifier: Any,
    trajectory_state: dict[str, Any],
    transcript: list[str],
    planner: Any,
    timeout_s: float,
    call_planner: Callable[[str, Callable[[], PlannerResponse], int], PlannerResponse | None],
    emit: Callable[..., None],
) -> ExecutorAction | None:
    """If the gate fires, call planner.correct on the proposal before env.step.

    Non-empty ``resp.code`` that differs from the proposal is a replacement;
    otherwise the proposal is approved unchanged.
    """
    if not getattr(policy, "review_proposed_action", False) or packet is None:
        return action
    state = dict(trajectory_state)
    proposed = action.model_dump()
    # Score against the proposal without changing trajectory_state keys used by
    # feature_lr (those keep last_action = previous executed action).
    state["proposed_action"] = proposed
    scored = verifier or ConstantVerifier()
    if not (scored.score(state) > float(policy.verifier_threshold)):
        return action
    proposed_text = format_executor_action(action)
    delta = "\n".join(list(transcript) + [f"PROPOSED_ACTION: {proposed_text}"])
    resp = call_planner(
        "correct",
        lambda: planner.correct(packet, delta, timeout_s=timeout_s),
        step,
    )
    if resp is None:
        return None
    replacement: ExecutorAction | None = None
    if resp.code and resp.code.strip():
        proposed_code = (action.code or "").strip() if action.kind == "CODE" else ""
        if resp.code.strip() != proposed_code:
            replacement = ExecutorAction(
                kind="CODE",
                code=resp.code,
                raw_output=resp.raw_output or resp.code,
            )
    verdict = "replace" if replacement is not None else "approve"
    emit(
        step=step,
        actor="planner",
        event_type="action_review",
        payload={
            "verdict": verdict,
            "proposed": proposed,
            "replacement": None if replacement is None else replacement.model_dump(),
            "correction": resp.correction,
        },
        usage=resp.usage,
    )
    if replacement is not None:
        emit(
            step=step,
            actor="planner",
            event_type="action",
            payload=replacement.model_dump(),
        )
    return replacement if replacement is not None else action
