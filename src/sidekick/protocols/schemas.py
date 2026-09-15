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


_FENCE_RE = re.compile(r"```[ \t]*python[ \t]*\r?\n(.*)```", re.DOTALL | re.IGNORECASE)


def parse_executor_action(raw: str) -> ExecutorAction:
    """Extract an ExecutorAction from model text.

    Priority order: fenced ```python block -> CODE, "ASK_PLANNER:" line -> ASK_PLANNER,
    "REPORT:" line -> REPORT, "COMPLETE" -> COMPLETE. raw_output is always the
    untouched input. Raises ActionParseError(raw_output=raw) on no match.
    """
    m = _FENCE_RE.search(raw)
    if m:
        code = m.group(1).strip()
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
        if stripped == "COMPLETE":
            return ExecutorAction(kind="COMPLETE", raw_output=raw)
    raise ActionParseError(raw_output=raw)


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
