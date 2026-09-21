"""Pre-execution action review, called from ``run_episode``.

Kept out of ``loop.py`` so the episode loop file does not grow further. The
planner transport is ``planner.act`` via the loop's ``call_planner``.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from sidekick.agents.planner import _maybe_python_fence
from sidekick.agents.verifier import ConstantVerifier
from sidekick.protocols.prompts import format_executor_action
from sidekick.protocols.schemas import DelegationPacket, ExecutorAction, PlannerResponse


def _ws_norm(text: str) -> str:
    return " ".join(text.split())


def _returned_code(resp: PlannerResponse) -> str:
    code = (resp.code or "").strip()
    if code:
        return code
    fenced = _maybe_python_fence(resp.raw_output or "")
    return (fenced or "").strip()


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
    task_id: str,
) -> ExecutorAction | None:
    """If the gate fires, call planner.act on the proposal before env.step.

    Returned code that matches the proposal after whitespace normalisation, or
    no code at all, is an approval; otherwise the proposal is replaced.
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
    act_transcript = "\n".join(list(transcript) + [f"PROPOSED_ACTION: {proposed_text}"])
    resp = call_planner(
        "act",
        lambda: planner.act(task_id, act_transcript, timeout_s=timeout_s),
        step,
    )
    if resp is None:
        return None
    replacement: ExecutorAction | None = None
    returned = _returned_code(resp)
    proposed_code = (action.code or "").strip() if action.kind == "CODE" else ""
    if returned and _ws_norm(returned) != _ws_norm(proposed_code):
        replacement = ExecutorAction(
            kind="CODE",
            code=returned,
            raw_output=resp.raw_output or returned,
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
