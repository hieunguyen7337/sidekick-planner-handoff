"""Executor prompt renderer. Shared by inference (`loop.py`) and SFT data build."""
from __future__ import annotations

from typing import NamedTuple

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


class BudgetFit(NamedTuple):
    """Result of ``fit_messages_to_budget``.

    ``selected, n_messages_dropped, representable, n_chars_elided``.
    """

    selected: list[dict]
    n_messages_dropped: int
    representable: bool
    n_chars_elided: int


def _elision_marker(n_elided: int) -> str:
    return f"\n... [{n_elided} characters elided] ...\n"


def _middle_elide_content(content: str, n_keep: int) -> tuple[str, int]:
    """Keep ``n_keep`` original characters (head + tail); elide the middle."""
    text = str(content)
    n = len(text)
    if n_keep >= n:
        return text, 0
    n_keep = max(0, n_keep)
    n_elided = n - n_keep
    marker = _elision_marker(n_elided)
    if n_keep == 0:
        return marker, n_elided
    head_len = n_keep // 2
    tail_len = n_keep - head_len
    return text[:head_len] + marker + text[n - tail_len :], n_elided


def _elide_index_to_fit(
    messages: list[dict],
    idx: int,
    max_tokens: int,
    length_fn,
) -> int:
    """Middle-elide ``messages[idx]`` until ``length_fn`` is under budget.

    Keeps as many original characters as will fit. Returns characters removed
    from that message's original content. Does not mutate other messages.
    """
    original = str(messages[idx].get("content", ""))
    if not original:
        return 0
    current_len = length_fn(messages)

    def _trial(n_keep: int) -> tuple[str, int, int]:
        content, n_elided = _middle_elide_content(original, n_keep)
        trial_msgs = list(messages)
        trial_msgs[idx] = {**messages[idx], "content": content}
        return content, n_elided, length_fn(trial_msgs)

    _, _, original_len = _trial(len(original))
    if original_len <= max_tokens:
        return 0

    lo, hi = 0, len(original)
    best_keep = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        _, _, trial_len = _trial(mid)
        if trial_len <= max_tokens:
            best_keep = mid
            lo = mid + 1
        else:
            hi = mid - 1
    n_keep = best_keep if best_keep >= 0 else 0
    content, n_elided, trial_len = _trial(n_keep)
    if trial_len <= max_tokens or trial_len < current_len:
        messages[idx] = {**messages[idx], "content": content}
        return n_elided
    return 0


def _elide_oversize(messages: list[dict], max_tokens: int, length_fn) -> tuple[list[dict], int]:
    """Elide the longest messages first until ``length_fn`` is under budget."""
    out = list(messages)
    total_elided = 0
    order = sorted(
        range(len(out)),
        key=lambda i: len(str(out[i].get("content", ""))),
        reverse=True,
    )
    for idx in order:
        if length_fn(out) <= max_tokens:
            break
        total_elided += _elide_index_to_fit(out, idx, max_tokens, length_fn)
    return out, total_elided


def fit_messages_to_budget(
    messages: list[dict],
    *,
    max_tokens: int,
    length_fn,
) -> BudgetFit:
    """Drop whole middle messages, then middle-elide oversized anchors if needed.

    Returns ``BudgetFit(selected, n_messages_dropped, representable, n_chars_elided)``.

    ``messages[0]`` (system) and ``messages[1]`` (task framing) and the LAST
    message are always kept; only messages between the framing pair and the
    last message are eligible, removed oldest-first, never split — half a
    fenced code block is a syntactically broken prompt. When even the anchor
    set ``[0], [1], last`` exceeds ``max_tokens``, oversized message *content*
    is middle-elided (head and tail kept, explicit marker at the cut) so a
    representable prompt exists. ``representable`` is ``False`` only if the
    fully-elided anchors still exceed ``max_tokens``: returns the unmodified
    list so the caller decides, rather than a damaged prompt.

    ``length_fn(messages) -> int`` is injected so training can count with a
    real tokenizer and serving with its own — one policy, two counters, no
    train/serve drift in WHICH messages survive or HOW content is elided.
    """
    selected = list(messages)
    n = len(selected)
    if n == 0:
        return BudgetFit(selected, 0, True, 0)
    if length_fn(selected) <= max_tokens:
        return BudgetFit(selected, 0, True, 0)

    anchors = [selected[0], selected[1], selected[-1]] if n >= 3 else list(selected)
    n_chars_elided = 0
    if length_fn(anchors) > max_tokens:
        elided, n_chars_elided = _elide_oversize(anchors, max_tokens, length_fn)
        if length_fn(elided) > max_tokens:
            return BudgetFit(list(messages), 0, False, 0)
        if n >= 3:
            selected[0], selected[1], selected[-1] = elided[0], elided[1], elided[2]
        else:
            selected = elided

    dropped = 0
    while len(selected) > 3 and length_fn(selected) > max_tokens:
        del selected[2]
        dropped += 1
    return BudgetFit(selected, dropped, True, n_chars_elided)


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
