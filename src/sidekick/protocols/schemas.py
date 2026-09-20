"""Pydantic schemas for the Sidekick seam contract (v1). Do not rename fields."""
from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

Role = Literal["planner", "executor", "verifier", "environment", "system"]
# "cache" is NOT a synonym for "mock": the campaign gate treats a zero-token
# "mock" planner record as a mistyped planner.type silently falling back to
# MockPlanner. A replayed archived packet is a real plan that bought nothing,
# and must not trip that check — hence its own provider tag.
Provider = Literal["codex", "vllm", "mock", "cache"]


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
    # Executor P(ASK) at the first generated token. None means "not measured"
    # (no logprobs). 0.0 means "measured, mass was zero". Never coerce None to 0.0.
    p_ask: Optional[float] = None
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
    "report", "evaluate", "error", "run_end", "action_review",
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
    goal_pass_rate: Optional[float] = None
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


def _is_data_literal(code: str) -> bool:
    """True if ``code`` is a single bare literal collection or constant, i.e. data.

    Distinguishes an action from a hallucinated environment reply generically, without the
    parser needing to know anything about AppWorld's API surface.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Expr):
        return False
    return isinstance(
        tree.body[0].value, (ast.List, ast.Dict, ast.Tuple, ast.Set, ast.Constant)
    )


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


# Lines that are pure wrapper: an XML-ish tag on its own, a fence, or a bare language
# marker. Everything Granite has produced so far is real Python inside one of these.
# A line made of nothing but markup: any XML-ish tag, a fence, a bare language marker, or
# a stray angle bracket, in any combination.
#
# This deliberately does NOT enumerate tag names. Enumerating lost three times in one
# evening -- the list had tool_call, function, parameter, py, python, code, and the very
# next sample closed with </sandbox>, then another put the tag and the language marker on
# one line as `<tool_call> python`. The invariant is not which tags Granite picks, it is
# that a wrapper line carries no Python. A real line of Python is never composed solely of
# tags and markers, so matching the shape is both safer and stable under variants nobody
# has seen yet.
_WRAPPER_LINE_RE = re.compile(
    r"^\s*(?:(?:"
    r"</?[A-Za-z][\w.:-]*[^<>]*/?>"      # <tool_call>, </sandbox>, <function=foo>
    r"|```[A-Za-z0-9_+-]*"                # fence, opening or closing
    r"|\b(?:python|py)\b"                 # bare language marker
    r"|[<>]"                              # stray bracket, as in `python>`
    r")\s*)+$",
    re.IGNORECASE,
)
# Salvage only fires when the model was visibly *trying* to delimit code. Without this
# gate, prose that happens to be a valid Python expression could be executed.
_WRAPPER_HINT_RE = re.compile(r"</?[A-Za-z][\w.:-]*[^<>]*>|```")


def _unwrapped_block(raw: str) -> tuple[int, str] | None:
    """Last resort: strip wrapper lines and keep the remainder if it is valid Python.

    Granite 4.2 does not have one output format, it has several, and it picks between
    them per generation. Measured on three consecutive smoke gates, all with thinking off
    and all containing correct code:

        <tool_call>\\n<py>\\nCODE\\n</py>\\n</section>
        <tool_call>\\npython\\nCODE\\n</parameter>\\n</function>
        ```python\\nCODE\\n```

    Adding a regex per variant loses: the next model, or the next vLLM version, invents
    another. Stripping the delimiters and asking Python whether what remains compiles is
    stable under variants nobody has seen yet.

    Two guards keep this from promoting prose to an action: the text must show a wrapper
    token at all, and the remainder must both compile *and* contain a call. A bare
    ``COMPLETE`` compiles perfectly well as a Name expression, and running it would raise
    NameError inside the environment instead of completing the task.
    """
    if not _WRAPPER_HINT_RE.search(raw):
        return None
    # The FIRST contiguous run of non-wrapper lines, not every non-wrapper line joined.
    # Granite often writes its action and then hallucinates the environment's reply after
    # it, and a hallucinated reply can itself be valid Python -- a list of constructor
    # calls, say -- so joining everything would hand the environment the model's
    # invention along with its action. Taking the first block keeps the action and
    # discards whatever it dreamed afterwards.
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in raw.splitlines():
        if _WRAPPER_LINE_RE.match(line):
            if current:
                blocks.append(current)
                current = []
            continue
        if not line.strip() and not current:
            continue
        current.append(line)
    if current:
        blocks.append(current)
    for block in blocks:
        candidate = "\n".join(block).strip()
        # A call is the mark of an action; it also rejects a bare COMPLETE, which would
        # otherwise compile as a Name and raise NameError in the environment.
        if "(" not in candidate or not _parses(candidate):
            continue
        # A lone list/dict/tuple literal is data, not an action -- it is what a
        # hallucinated environment reply looks like, e.g.
        #   [Transaction(id='txn_001', amount=25.0), Transaction(...)]
        # which contains calls and compiles cleanly. Executing it would raise NameError
        # on the model's own invention.
        if _is_data_literal(candidate):
            continue
        return 0, candidate
    return None


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
    if best is not None:
        return best[1]
    # Neither delimiter matched. Fall back to stripping wrappers and asking Python.
    unwrapped = _unwrapped_block(raw)
    return unwrapped[1] if unwrapped else None


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
