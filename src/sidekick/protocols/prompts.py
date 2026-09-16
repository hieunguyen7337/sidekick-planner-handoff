"""Executor prompt renderer. Shared by inference (`loop.py`) and SFT data build."""
from __future__ import annotations

from sidekick.protocols.schemas import DelegationPacket, ExecutorAction

# Moved verbatim from `loop._executor_messages`. Encodes two measured 2026-09-15
# failure modes; do not "improve" the wording.
EXECUTOR_SYSTEM_PROMPT: str = (
    "You are an executor acting in a live environment. Each turn you emit exactly "
    "one action and nothing else.\n"
    "\n"
    "The four actions:\n"
    "  a ```python fenced block, to run code\n"
    "  ASK_PLANNER: <what you need decided>\n"
    "  REPORT: <what you found>\n"
    "  COMPLETE, or COMPLETE: <answer> when the task asked a question\n"
    "\n"
    "A complete turn looks like this, in full:\n"
    "\n"
    "```python\n"
    "print(apis.spotify.show_song_library())\n"
    "```\n"
    "\n"
    "That is the entire reply. Do not reason out loud first, do not emit more than "
    "one action, and do not write what you expect the output to be: the environment "
    "runs your code and puts the real output in the transcript next turn. Everything "
    "after the first action is discarded. When you do not know what an API returns, "
    "call it and look rather than guessing.\n"
    "\n"
    "Both failure modes here are measured, on 2026-09-15, and both scored 0.0 on "
    "tasks the model could otherwise do. granite-4.2-8b wrote a correct call to "
    "show_song_library(), then invented a plausible song list as its result and "
    "reasoned over the invention until its budget ran out. granite-4.2-3b narrated "
    "its intentions for 1,661 tokens -- \"I'll use the search_songs API\", \"let me "
    "check the API docs first\" -- and never emitted a single line of code."
)

_HISTORY_ROLES = {"assistant", "user"}


def format_executor_action(action: ExecutorAction) -> str:
    """Canonical text for an executor action, in the form ``parse_executor_action`` accepts.

    Reconstructs from parsed fields (not ``raw_output``) so history is one spelling:
    a ```python fence, ``ASK_PLANNER:``, ``REPORT:``, ``COMPLETE`` / ``COMPLETE:``.
    """
    if action.kind == "CODE":
        return f"```python\n{action.code}\n```"
    if action.kind == "ASK_PLANNER":
        return f"ASK_PLANNER: {action.ask_reason}"
    if action.kind == "REPORT":
        return f"REPORT: {action.message or ''}"
    if action.kind == "COMPLETE":
        if action.message:
            return f"COMPLETE: {action.message}"
        return "COMPLETE"
    raise ValueError(f"unknown executor action kind: {action.kind!r}")


def render_executor_messages(
    *,
    instruction: str,
    api_docs: str = "",
    packet: DelegationPacket | None = None,
    history: list[dict],
) -> list[dict]:
    """Build the executor prompt as a multi-turn conversation.

    ``api_docs`` is not optional in practice. Without it the model is never told it
    is inside AppWorld and has an ``apis`` object to call, so it concludes the task
    is impossible -- observed 2026-09-15, where planner_alone answered a Spotify
    task with "the Spotify plugin is not installed" and every arm scored 0.0 TGC.
    The environment computes the digest for exactly this purpose.
    """
    user = f"Task: {instruction}\n"
    if api_docs:
        # api_docs already carries its own usage preamble (calling convention, print
        # vs return, how to get full parameter detail). Do not restate it here: two
        # sets of instructions that drift apart is worse than one.
        user += f"{api_docs}\n"
    if packet is not None:
        user += f"Plan: {packet.model_dump_json()}\n"
    for i, turn in enumerate(history):
        role = turn.get("role") if isinstance(turn, dict) else None
        if role not in _HISTORY_ROLES:
            raise ValueError(
                f"history[{i}] role must be 'assistant' or 'user', got {role!r}"
            )
    return [
        {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
        {"role": "user", "content": user},
        *history,
    ]
