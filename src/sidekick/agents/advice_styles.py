"""Advice-prompt styles added after B2 (plan 2026-09-24, D2).

planner.build_advice_prompt owns "correction" and "neutral" and dispatches "structured" here.
The style lives in its own module so planner.py keeps its line numbers, which frozen
registration text cites (planner.py:956-962).

"structured" is directed advice in the ManagerWorker/Minions style, the prior-work baseline a
reviewer set against the terse correction prompt (plan G3, G8): the planner names the next
subgoal, the steps to reach it and a completion check. It keeps the packet and transcript lines
identical to the neutral style, so the two styles differ only in their instruction lines.
"""
from __future__ import annotations

from sidekick.protocols.schemas import DelegationPacket


def build_structured_advice_prompt(packet: DelegationPacket, transcript_delta: str) -> str:
    return (
        "Direct the executor's next steps, as a manager directs a worker. "
        "Reply in exactly this structure:\n"
        "GOAL: the subgoal the executor should complete next.\n"
        "STEPS: numbered concrete steps to reach it; include code where it helps.\n"
        "CHECK: how the executor can tell the subgoal is done.\n"
        f"packet:\n{packet.model_dump_json()}\n"
        f"transcript_delta:\n{transcript_delta}\n"
    )
