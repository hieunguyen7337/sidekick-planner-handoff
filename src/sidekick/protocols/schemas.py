"""Pydantic schemas for the Sidekick seam contract (v1). Do not rename fields."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

Role = Literal["planner", "executor", "verifier", "environment", "system"]
Provider = Literal["codex", "vllm", "mock"]


class Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")  # raw is a free-form dict; no forbid here

    model: str
    provider: Provider
    # ge=0: negative token counts are always a bug and would silently corrupt
    # cost totals and displacement ratios.
    input_tokens: int = Field(0, ge=0)
    cached_input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    reasoning_output_tokens: int = Field(0, ge=0)
    latency_s: float = Field(0.0, ge=0.0)
    gpu_seconds: float = Field(0.0, ge=0.0)  # executor/verifier only; 0.0 for hosted planner
    n_calls: int = Field(1, ge=0)
    raw: dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    description: str
    expected_outcome: str = ""
    apps: list[str] = Field(default_factory=list)


class DelegationPacket(BaseModel):    # planner -> executor
    model_config = ConfigDict(extra="forbid")

    packet_id: str
    task_id: str
    goal: str
    plan_steps: list[PlanStep] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    context_digest: str = ""
    created_at: str                    # ISO-8601 UTC


class ExecutorAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["CODE", "REPORT", "ASK_PLANNER", "COMPLETE"]
    code: Optional[str] = None         # required when kind == "CODE"
    message: Optional[str] = None      # REPORT/COMPLETE payload
    ask_reason: Optional[str] = None   # required when kind == "ASK_PLANNER"
    confidence: Optional[float] = None
    raw_output: str = ""               # ALWAYS keep the model's raw text

    @model_validator(mode="after")
    def _check_kind(self) -> "ExecutorAction":
        if self.kind == "CODE" and not (self.code and self.code.strip()):
            raise ValueError('kind == "CODE" requires non-empty code')
        if self.kind == "ASK_PLANNER" and not (self.ask_reason and self.ask_reason.strip()):
            raise ValueError('kind == "ASK_PLANNER" requires non-empty ask_reason')
        return self


class PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["PLAN", "CORRECTION", "ANSWER", "ACTION"]
    packet: Optional[DelegationPacket] = None
    correction: Optional[str] = None
    code: Optional[str] = None         # planner-alone mode emits code directly
    raw_output: str = ""
    usage: Usage
    thread_id: Optional[str] = None    # codex session id, for resume


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str                          # what the environment returned
    step: int
    done: bool = False
    truncated: bool = False
    env_state_hash: Optional[str] = None
    error_type: Optional[str] = None


EventType = Literal[
    "run_start", "plan", "action", "observation", "intervention", "ask",
    "report", "evaluate", "error", "run_end",
]


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")  # payload is free-form

    run_id: str
    task_id: str
    system: str
    seed: int
    step: int
    ts: str                            # ISO-8601 UTC
    actor: Role
    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    usage: Optional[Usage] = None
    env_state_hash: Optional[str] = None
    error_type: Optional[str] = None   # parse_error | timeout | crash | api_error | None


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    system: str
    seed: int
    success: bool                      # AppWorld task_goal_completion for this task
    tgc: Optional[float] = None
    sgc: Optional[float] = None
    steps: int = 0
    n_planner_calls: int = 0
    n_asks: int = 0
    n_interventions: int = 0
    error_type: Optional[str] = None
    totals: dict[str, Any] = Field(default_factory=dict)   # from CostLedger.totals()


class ActionParseError(ValueError):
    """Raised by parse_executor_action when no action can be extracted."""

    def __init__(self, raw_output: str, message: str = "no executor action found in model output") -> None:
        super().__init__(message)
        self.raw_output = raw_output


# Two readings of the same text, and neither is right on its own. Greedy `(.*)` runs to
# the LAST closing fence, which is what a block containing a nested ``` inside a
# triple-quoted string needs, but on a reply carrying two separate blocks it swallows the
# prose between them. Lazy `(.*?)` is the reverse. So try the short read and widen only
# when it does not parse as Python -- the ambiguity is real, and syntax is the evidence
# that settles it.
_FENCE_LAZY_RE = re.compile(r"```[ \t]*python[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)
_FENCE_GREEDY_RE = re.compile(r"```[ \t]*python[ \t]*\r?\n(.*)```", re.DOTALL | re.IGNORECASE)
_FENCE_OPEN_RE = re.compile(r"```[ \t]*python[ \t]*\r?\n", re.IGNORECASE)
_TRAILING_BACKTICKS_RE = re.compile(r"`+[ \t]*\r?\n?\s*$")
# Granite 4.2 with thinking off does not reach for a markdown fence: it emits its
# native tool-call shape, `<tool_call><py>...</py>`, even though no tools are declared.
# Observed 2026-09-15: every executor_alone episode died parse_error at step 1 while the
# code inside the tag was perfectly good Python. The closing tag is optional so a stop
# sequence may cut it off without costing us the action.
_PY_TAG_RE = re.compile(r"<py(?:thon)?>[ \t]*\r?\n?(.*?)(?:</py(?:thon)?>|$)", re.DOTALL | re.IGNORECASE)


def _parses(code: str) -> bool:
    """True if ``code`` is syntactically valid Python. Blank counts as invalid: an empty
    capture is never the block the model meant, it is a sign the delimiters were read
    wrongly."""
    if not code.strip():
        return False
    try:
        compile(code, "<executor-action>", "exec")
    except (SyntaxError, ValueError):  # ValueError: source containing null bytes
        return False
    return True


def _fenced_block(raw: str) -> tuple[int, str] | None:
    lazy = _FENCE_LAZY_RE.search(raw)
    if not lazy:
        # No closing fence anywhere. Either the model never finished the block or
        # max_tokens cut it off mid-generation. Salvage it only if what we got is
        # valid Python: a truncated block usually is not, and running half a
        # statement against a live environment is worse than reporting a parse error.
        open_fence = _FENCE_OPEN_RE.search(raw)
        if open_fence:
            tail = raw[open_fence.end():]
            # Also try it with a fumbled closing fence trimmed. Observed 2026-09-15,
            # planner_alone run 383cbac_3 seed 2: the model closed with two backticks
            # instead of three, so nothing matched a close, and
            #   print(apis.supervisor.complete_task(answer=42, status="success"))
            # -- a correct answer -- was discarded as unparseable and the episode scored
            # 0.0. Both candidates still have to compile, so this cannot turn prose into
            # an action.
            for candidate in (tail, _TRAILING_BACKTICKS_RE.sub("", tail)):
                if _parses(candidate):
                    return open_fence.start(), candidate
        return None
    if _parses(lazy.group(1)):
        return lazy.start(), lazy.group(1)
    greedy = _FENCE_GREEDY_RE.search(raw)
    if greedy and _parses(greedy.group(1)):
        return greedy.start(), greedy.group(1)
    return lazy.start(), lazy.group(1)  # neither parses; report the short read


def _tagged_block(raw: str) -> tuple[int, str] | None:
    m = _PY_TAG_RE.search(raw)
    return (m.start(), m.group(1)) if m else None


def _first_code_block(raw: str) -> str | None:
    """Return the earliest python block, in whichever of the two spellings comes first.

    Earliest rather than fence-first: a reply that narrates in a fence and then acts in
    a `<py>` tag (or the reverse) should run the action the model reached for first,
    the same one a human reading top to bottom would take.
    """
    best: tuple[int, str] | None = None
    for finder in (_fenced_block, _tagged_block):
        found = finder(raw)
        if found and (best is None or found[0] < best[0]):
            best = found
    return best[1] if best else None


def parse_executor_action(raw: str) -> ExecutorAction:
    """Extract an ExecutorAction from model text.

    Priority order: first python block (a ```python fence or a <py> tag, whichever the
    model reached for first) -> CODE, "ASK_PLANNER:" line -> ASK_PLANNER,
    "REPORT:" line -> REPORT, "COMPLETE" -> COMPLETE. raw_output is always the
    untouched input. Raises ActionParseError(raw_output=raw) on no match.
    """
    block = _first_code_block(raw)
    if block:
        code = block.strip()
        if code:
            return ExecutorAction(kind="CODE", code=code, raw_output=raw)
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("ASK_PLANNER:"):
            reason = stripped[len("ASK_PLANNER:"):].strip()
            if reason:
                return ExecutorAction(kind="ASK_PLANNER", ask_reason=reason, raw_output=raw)
            continue  # empty reason would fail the model validator; treat as no match
        if stripped.startswith("REPORT:"):
            return ExecutorAction(kind="REPORT", message=stripped[len("REPORT:"):].strip(), raw_output=raw)
        # "COMPLETE: <answer>" as well as a bare "COMPLETE". AppWorld scores
        # answer-returning tasks on the answer passed to
        # apis.supervisor.complete_task(answer=...), so dropping the text after the
        # colon throws away the result. Observed 2026-09-15: a planner answered
        # "COMPLETE: Placeholder Song A, Placeholder Song B, ..." and the exact-match
        # test rejected it as unparseable, scoring a solved task 0.0.
        if stripped == "COMPLETE" or stripped.startswith("COMPLETE:"):
            answer = stripped[len("COMPLETE:"):].strip() if ":" in stripped else ""
            return ExecutorAction(kind="COMPLETE", message=answer or None, raw_output=raw)
    raise ActionParseError(raw_output=raw)


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
