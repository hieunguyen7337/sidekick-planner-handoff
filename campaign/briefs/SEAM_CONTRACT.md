# Sidekick — seam contract v1 (owned by Claude; do not change without asking)

Every worker that touches these types uses EXACTLY these names, fields and signatures.
Python 3.12, pydantic v2. Package root `src/sidekick/`. Absolute repo root:
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Types — `src/sidekick/protocols/schemas.py`

```python
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

Role = Literal["planner", "executor", "verifier", "environment", "system"]
Provider = Literal["codex", "vllm", "mock"]

class Usage(BaseModel):
    model: str
    provider: Provider
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    latency_s: float = 0.0
    gpu_seconds: float = 0.0          # executor/verifier only; 0.0 for hosted planner
    n_calls: int = 1
    raw: dict[str, Any] = Field(default_factory=dict)

class PlanStep(BaseModel):
    index: int
    description: str
    expected_outcome: str = ""
    apps: list[str] = Field(default_factory=list)

class DelegationPacket(BaseModel):    # planner -> executor
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
    kind: Literal["CODE", "REPORT", "ASK_PLANNER", "COMPLETE"]
    code: Optional[str] = None         # required when kind == "CODE"
    message: Optional[str] = None      # REPORT/COMPLETE payload
    ask_reason: Optional[str] = None   # required when kind == "ASK_PLANNER"
    confidence: Optional[float] = None
    raw_output: str = ""               # ALWAYS keep the model's raw text

class PlannerResponse(BaseModel):
    kind: Literal["PLAN", "CORRECTION", "ANSWER", "ACTION"]
    packet: Optional[DelegationPacket] = None
    correction: Optional[str] = None
    code: Optional[str] = None         # planner-alone mode emits code directly
    raw_output: str = ""
    usage: Usage
    thread_id: Optional[str] = None    # codex session id, for resume

class Observation(BaseModel):
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
```

**Rule:** a parse failure is an `Event` with `error_type="parse_error"`, never a silent retry.
Every retry is its own logged event with `n_calls` incremented.

## Event log — `src/sidekick/trajectories/eventlog.py`

```python
class EventLog:
    def __init__(self, root: str | Path, run_id: str) -> None: ...   # appends to <root>/<run_id>/events.jsonl
    def append(self, event: Event) -> None: ...                      # one JSON object per line, flush each write
    def write_manifest(self, manifest: dict) -> None: ...            # <root>/<run_id>/manifest.json
    def close(self) -> None: ...
    def __enter__(self) / __exit__(...)                              # context manager
    @staticmethod
    def read(path: str | Path) -> Iterator[Event]: ...
```
Raw logs are append-only and NEVER rewritten.

## Cost — `src/sidekick/cost/`

```python
# prices.py
class PriceSchedule:
    @classmethod
    def load(cls, path: str | Path) -> "PriceSchedule": ...
    def cost_usd(self, usage: Usage) -> float: ...
# ledger.py
class CostLedger:
    def __init__(self, prices: PriceSchedule) -> None: ...
    def add(self, actor: Role, usage: Usage) -> None: ...
    def totals(self) -> dict[str, Any]: ...
    # totals() keys, exactly:
    #   per_actor: {actor: {input_tokens, cached_input_tokens, output_tokens,
    #                       reasoning_output_tokens, n_calls, gpu_seconds, usd}}
    #   planner_tokens_total, planner_calls_total, executor_tokens_total,
    #   gpu_seconds_total, usd_total, replayed_planner_tokens
```
`replayed_planner_tokens` sums a replayed prefix's planner usage **excluding `cached_input_tokens`**
because cached tokens are re-sent context rather than new work.

`configs/cost/prices_2026-09.yaml` (rates per 1M tokens, USD):
`gpt-5.6-luna: {input: 0.20, cached_input: 0.02, output: 1.20}`;
`local_gpu: {usd_per_gpu_hour: 2.50}` (amortised H100, documented as an assumption).

## Agents — `src/sidekick/agents/`

```python
class LLMClient(Protocol):
    def complete(self, messages: list[dict], **kw) -> tuple[str, Usage]: ...

class PlannerClient(Protocol):
    name: str
    def plan(self, task_id: str, goal: str, context: str) -> PlannerResponse: ...
    def correct(self, packet: DelegationPacket, transcript_delta: str) -> PlannerResponse: ...
    def act(self, task_id: str, transcript: str) -> PlannerResponse: ...   # planner-alone
    def close(self) -> None: ...
```
Implementations: `CodexExecPlanner` (subprocess `codex exec --json`), `MockPlanner` (deterministic,
no network, used by every test).

## Environments — `src/sidekick/environments/`

```python
class BaseEnv(ABC):
    def reset(self, task_id: str, seed: int) -> Observation: ...
    def step(self, action: ExecutorAction) -> Observation: ...
    def evaluate(self) -> dict: ...        # {"success": bool, "tgc": float, "sgc": float|None, "report": dict}
    def snapshot_hash(self) -> str: ...
    def close(self) -> None: ...
    @property
    def instruction(self) -> str: ...
    @property
    def api_docs_digest(self) -> str: ...
```
`AppWorldEnv` (real), `MockEnv` (deterministic toy with an irreversible action, no deps).

## Systems — `src/sidekick/systems/`

```python
class System(Protocol):
    name: str
    def run(self, env: BaseEnv, task_id: str, seed: int, log: EventLog,
            ledger: CostLedger) -> RunResult: ...
```
Ten names, exactly: `planner_alone`, `executor_alone`, `prompt_only`, `fixed_k`,
`sft_plan`, `router_seq`, `sidekick`, `oracle_escalation`,
`action_review` (built, E4, repair pending),
`prefix_handoff` (being built now — the planner's first `m` recorded steps are replayed onto a fresh environment and the executor finishes the episode live).

## Policy flags & configuration blocks

Policy flags (recorded in `run_start` event payload `policy` dict):
- `review_proposed_action: bool`
- `takeover: bool`
- `handoff_allowed: bool`
- `post_prefix_terminal: "stop" | "continue"` — recorded only when an episode starts from a replayed prefix. `"stop"` (default) ends the episode with the replayed outcome when the prefix already terminated; `"continue"` is the pre-2026-09-23 behaviour in which the executor still acted. `run_end` then carries `n_post_terminal_actions`.

Handoff configuration block (`handoff:` in system YAML configs):
```yaml
handoff:
  source_campaign: str   # directory path containing recorded source prefix episodes
  source_system: str     # source system name (e.g. planner_alone)
  m: int                 # prefix step count to replay before executor handoff
```

## Global run limits (every system, every arm)
`max_steps=40`, `max_tokens_per_episode=2000000`, `per_step_timeout_s=300`,
`max_planner_calls=81` (= 2·max_steps + 1) for every arm from HJ-8 onward. ⚠ The HJ-1 ceiling arm `hj1b_planner_20260915` ran under the older `max_planner_calls=25`, which ended 11 of its 12 `limit` episodes; comparisons against it understate the planner until the cap-81 re-run exists. Exceeding one ends the run with `error_type="limit"`, counted as a failure
in the denominator.

