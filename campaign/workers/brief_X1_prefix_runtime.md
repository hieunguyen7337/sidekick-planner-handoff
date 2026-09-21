# Brief X1 — the prefix-handoff runtime (planner does the first m steps, executor finishes)

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You are building the runtime for the campaign's decisive next experiment. It costs **zero hosted
planner calls**: the planner's first `m` steps are *replayed from recorded episodes already on
disk*, and only the local executor runs live.

## Why (context you need to make good decisions)

The hosted planner (`gpt-5.6-luna`) solves AppWorld dev at goal_pass 0.83 using ~14 steps per
episode. The local 8B executor with a cached plan reaches 0.70 at one planner call. Injecting
planner *advice* mid-episode (`INTERVENTION:` turns) has been measured repeatedly and is worth
nothing. The open question is whether the planner doing the **opening stretch itself**, then handing
a partly-solved episode to the executor, lands between those two points at a fraction of the cost.

## Scope — you own these files, and only these

Create:
- `src/sidekick/prefix_source.py`
- `src/sidekick/systems/prefix_handoff.py`
- `tests/unit/test_prefix_handoff.py`

Modify:
- `src/sidekick/systems/__init__.py` (register `prefix_handoff` only)
- `src/sidekick/runner.py` (one new block in `system_kwargs` only)

**Do not touch** `src/sidekick/systems/loop.py`, `src/sidekick/protocols/schemas.py`,
`src/sidekick/agents/planner.py`, `src/sidekick/systems/action_review_gate.py`,
`scripts/analysis/`, `scripts/pbs/`, or any `configs/*.yaml`. Another unit owns those **right now,
in parallel**. Editing them will collide.

## What already exists and must be reused, not reimplemented

Read these before writing anything.

1. **`src/sidekick/replay.py:63-108` — `replay_prefix(events_path, k, env) -> (world, remaining)`.**
   It reads the events of the *last* attempt, resets a fresh env to the recorded `task_id`/`seed`,
   and calls `world.step(...)` for the first `k` executed (`CODE`/`COMPLETE`) actions. It returns
   the still-open world (**caller owns closing it**) and the events after the last replayed
   observation. It **never inspects `Event.actor`**, so a `planner_alone` recording replays exactly
   like an executor recording. `k` larger than the trajectory is clamped. Use this function. Do not
   write a second replay loop.
2. **`src/sidekick/replay.py:110+` — `_events_of_last_attempt(events_path)`.** All events after the
   last `run_start`, in file order. You need this to compute the *prefix* events (everything up to
   and including the last replayed observation), because `replay_prefix` returns only the
   *remainder*. Prefix = the events of the last attempt minus the trailing `remaining` slice.
3. **`src/sidekick/systems/loop.py:69-105` — `EpisodePrefix`** with fields `events`, `start_step`,
   `inject_correction`, `skip_review_at_start`, `local_eval_step`, `skip_next_scheduled_review`.
   You set only `events` and `start_step`; leave the rest at their defaults.
4. **`src/sidekick/systems/loop.py:209-231` — `ConfigurableSystem.run(env, task_id, seed, log,
   ledger, prefix=None)`.** The `prefix` parameter already exists. Only
   `scripts/setup/branch_counterfactual.py:1122-1155` passes it today; no runner path does. You are
   adding the second caller.
5. **`src/sidekick/systems/loop.py:556-578`** — when a prefix is supplied, `run_episode` does **not**
   call `env.reset`; it rebuilds the executor's chat history from the prefix events via
   `_history_from_events` and appends the instruction/plan/observations to the transcript. So the
   env you hand to `run_episode` must be the already-stepped world that `replay_prefix` returned.
6. **`src/sidekick/training/sft_data.py:186-258` — `_history_from_events`.** This renders recorded
   actions as `assistant` turns and observations as `user` `OBS:` turns, keyed on `event_type`,
   **with no actor predicate**. This is the same function the SFT dataset builder uses, which is why
   a planner-authored prefix is on-distribution for the executor. Nothing to change here.
7. **`src/sidekick/systems/sft_plan.py`** — the policy your new system must match for the live
   suffix (executor drives, `plan_first=True`, no scheduled reviews).

## The source data

`/scratch/n12194778/sidekick/results/hj1b_planner_20260915/` — **READ ONLY, never write here.**
Layout: `planner_alone/<seed>/<task_id>/{events.jsonl,manifest.json,result.json}`.
114 episode directories (57 tasks × 2 seeds; seeds are `1` and `2`). Action events carry
`actor: "planner"` and `payload.code`. Episode step counts: min 5, median 12, max 25.

## Build this

### 1. `src/sidekick/prefix_source.py`

```python
@dataclass
class HandoffPrefix:
    prefix: EpisodePrefix | None
    env: BaseEnv                      # still open, stepped to the handoff point
    effective_m: int                  # actions actually replayed (clamped)
    n_source_actions: int             # executed actions in the source episode
    handoff_occurred: bool            # effective_m < n_source_actions
    hash_ok: bool
    replayed_planner_tokens: int
    broken_reason: str | None         # None, "missing_source", "replay_divergence", "replay_error"


def build_handoff_prefix(
    source_campaign: str | Path,
    source_system: str,
    task_id: str,
    seed: int,
    m: int,
    env: BaseEnv,
) -> HandoffPrefix: ...
```

Behaviour:
- Resolve `<source_campaign>/<source_system>/<seed>/<task_id>/events.jsonl`. Missing → return with
  `prefix=None`, `broken_reason="missing_source"`. Never invent a fallback path.
- `n_source_actions` = executed (`CODE`/`COMPLETE`) actions in the last attempt.
- Call `replay_prefix(events_path, m, env)`. Compute `effective_m = min(m, n_source_actions)`.
- **Hash check.** After replay, compare `env.snapshot_hash()` against the `env_state_hash` recorded
  on the last replayed observation event. Mismatch → `hash_ok=False`,
  `broken_reason="replay_divergence"`. An exception during replay → `broken_reason="replay_error"`
  with the detail preserved.
  ⚠ Record in the module docstring, quoting `replay.py:15-20`, that `snapshot_hash` is a sha256 of
  the observation history, **not** a database dump, so it detects visible divergence only. Do not
  describe it as proof the world state matches.
- `replayed_planner_tokens`: sum `usage` over the replayed prefix's events whose `actor` is
  `"planner"`, adding input + output + reasoning tokens and **excluding `cached_input_tokens`**.
  Cached tokens are re-sent context, not new work; counting them would misprice the arm. If a usage
  field is absent, treat it as 0 and set a `notes` entry — never guess.
- Build `EpisodePrefix(events=<prefix events>, start_step=effective_m + 1)`.
- Return the world from `replay_prefix` as `env`. Do not close it.

### 2. `src/sidekick/systems/prefix_handoff.py`

`class PrefixHandoff(ConfigurableSystem)`, `name = "prefix_handoff"`, `policy_defaults` identical to
`SftPlan`'s (`plan_first=True`, `planner_drives=False`, `allow_executor_ask=True`,
`review_every_k=None`, `use_router=False`, `gate_ask_with_verifier=False`). `__init__` accepts
`source_campaign`, `source_system`, `m`, `adapter_name`.

Override `run(env, task_id, seed, log, ledger, prefix=None)`:
- Call `build_handoff_prefix(...)` with the env it was given.
- If `broken_reason` is set: emit an `error` event with that reason and return a `RunResult` marked
  broken in the way the rest of the codebase marks broken episodes — **read `RunResult` in
  `src/sidekick/protocols/schemas.py` and follow the existing convention; do not invent a field.**
- Otherwise emit one event before the live suffix begins recording the handoff facts:
  `event_type="run_start"` is already emitted by `run_episode`, so emit a **separate** event with
  `actor="system"` and an existing permitted `event_type` carrying payload keys `effective_m`,
  `n_source_actions`, `handoff_occurred`, `hash_ok`, `replayed_planner_tokens`, `source_campaign`.
  ⚠ `EventType` is a closed `Literal` in `protocols/schemas.py` and **you may not edit that file**.
  Pick an existing member that fits (inspect the Literal and choose; `run_start` is emitted by the
  loop, so choose another). State in your STATUS file which member you chose and why. If genuinely
  none fits, stop and say so in STATUS rather than editing the schema.
- Then call `run_episode(...)` (or `super().run(...)`) with the replayed env and the built prefix.
- Live `planner_calls_total` must stay 0 for this arm: the policy schedules no reviews and the
  planner is never called. Assert this in a test.

### 3. `src/sidekick/systems/__init__.py`

Append `"prefix_handoff"` to `SYSTEM_NAMES` (**after** the existing nine — existing tests assert the
original eight are a prefix, so append, never reorder), add it to `SYSTEMS`, the import, and
`__all__`.

### 4. `src/sidekick/runner.py` — `system_kwargs` only

```python
if name == "prefix_handoff":
    h = cfg.get("handoff") or {}
    if h.get("source_campaign"):
        kwargs["source_campaign"] = str(h["source_campaign"])
    kwargs["source_system"] = str(h.get("source_system", "planner_alone"))
    kwargs["m"] = int(h.get("m", 0))
    adapter = (cfg.get("executor") or {}).get("lora_name") or cfg.get("adapter_name")
    if adapter:
        kwargs["adapter_name"] = adapter
```
Add `"prefix_handoff"` to the existing adapter-forwarding tuple at `runner.py:243` only if that
does not duplicate the assignment above — your call, but say which you did.

### 5. Tests — `tests/unit/test_prefix_handoff.py`

Use `MockEnv` (`src/sidekick/environments/mock_env.py`), which `replay.py` documents as the
reliable replay target. Write a small recorded `events.jsonl` fixture in `tmp_path` whose action
events carry `actor="planner"`. Cover:
1. m=2 on a 5-action source → `effective_m=2`, `handoff_occurred=True`, the executor's `exec_turns`
   contain the two replayed actions as assistant turns each followed by an `OBS:` user turn, and the
   plan is present in the transcript.
2. m beyond the episode length → `effective_m == n_source_actions`, `handoff_occurred=False`.
3. A deliberately corrupted recorded `env_state_hash` → `hash_ok=False`,
   `broken_reason="replay_divergence"`, and the episode is reported broken rather than scored.
4. Missing source directory → `broken_reason="missing_source"`.
5. `replayed_planner_tokens` excludes `cached_input_tokens` (fixture with both set; assert the
   exact expected integer).
6. The live suffix makes **zero** planner calls (ledger `planner_calls_total == 0`).
7. `get_system("prefix_handoff", ...)` constructs, and `SYSTEM_NAMES` still starts with the original
   eight in order.

## Constraints

- `aquarius01` is a **login node**. Never run the interpreter, `pip`, `tar`, `rsync` or `ffmpeg`
  there. Run the test suite in a PBS job: `timeout 1800 hpc bash -c 'cd <repo> && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 <pytest invocation>'`.
- **pytest requires `--import-mode=importlib`.** The suite must stay at **≥ 456 passed, 0 failed**.
- Put a `timeout` on every command.
- **Read-only** with respect to everything under `/scratch/n12194778/sidekick/results/`.
- **Do not commit.** I review the diff and commit.
- Do not read, analyse or report any `test_normal` or `test_challenge` data.
- Do not submit GPU jobs, do not run any evaluation, do not retrain.
- Do not edit `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`, `docs/prereg_j9_freeze_20260920.md`,
  or any `hj8_*` / `hj11_*` config — all FROZEN.

## Return contract

`campaign/workers/STATUS_X1.md`, under 800 words, updated **at each milestone** (not only at the
end) so the unit is resumable if it is killed:
- Every file you created or modified, with the exact new/changed function signatures.
- Which `EventType` member you chose for the handoff record, and why.
- The exact suite command and its final counts, pasted.
- Each factual claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`.
- Anything in this brief that turned out to be wrong about the code — say so plainly rather than
  working around it silently. Previous units were saved by workers reading the source instead of
  trusting the brief.
