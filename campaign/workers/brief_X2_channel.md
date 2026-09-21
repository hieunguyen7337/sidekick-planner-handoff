# Brief X2 — the takeover channel: the planner acts instead of advising

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why

When this system escalates to the hosted planner mid-episode, the planner's reply is injected as a
user turn reading `INTERVENTION: <prose>` and the local 8B executor must interpret it and generate
a fresh action. That channel has now been measured twice and is worth nothing. A counterfactual
pilot over 1,600 branches found 127 helping against 219 harming. After a retrain that removed a
train/serve format mismatch, advice became neutral rather than useful.

The hypothesis this unit makes testable: the planner's *judgement* was never the bottleneck — the
8B model's ability to act on prose was. So let the planner **act**. Same trigger, same one hosted
call, but its code is executed directly instead of being described to a smaller model.

You are also repairing a real defect that would have wasted the whole comparison.

## Scope — you own these files

Modify:
- `src/sidekick/protocols/schemas.py`
- `src/sidekick/systems/loop.py`
- `src/sidekick/agents/planner.py` (the `act` method and nothing else)
- `src/sidekick/systems/action_review_gate.py`
- `src/sidekick/systems/__init__.py` (register `planner_handoff`; leave `prefix_handoff` alone)
- `src/sidekick/runner.py` (`system_kwargs` — add the takeover/handoff block; leave the existing
  `prefix_handoff` block untouched)
- `tests/unit/test_action_review.py`

Create:
- `src/sidekick/systems/planner_handoff.py`
- `tests/unit/test_takeover.py`
- `configs/hj12_takeover_fixed_k_10.yaml`, `hj12_takeover_fixed_k_3.yaml`,
  `hj12_takeover_exception.yaml`, `hj12_advise_exception.yaml`, `hj12_planner_handoff.yaml`

**Do not touch** `src/sidekick/prefix_source.py`, `scripts/`, or any `configs/hj12_prefix_*.yaml` —
another unit owns those and they are already committed.

### One exception, and it is your first task — harden `src/sidekick/systems/prefix_handoff.py`

That file currently contains:

```python
# Unconfigured (no source_campaign): behave like sft_plan so SYSTEM_NAMES
# iteration tests still complete. A configured but missing path is broken.
if not self.source_campaign:
    return super().run(env, task_id, seed, log, ledger, prefix=prefix)
```

**This is a silent-failure hazard and must not reach a GPU run.** If a config misspells the
`handoff:` block, or the runner stops forwarding `source_campaign`, every prefix arm degrades
quietly into `sft_plan` and the experiment produces four plausible, mutually consistent copies of
the 1-call arm. Nothing in the output would look wrong. This project has already lost one whole
campaign to a silent substitution of exactly this shape.

Change it to: fall through to `sft_plan` behaviour **only when `self.m == 0`**, and otherwise raise
a `RuntimeError` naming the missing key, before any episode runs. `m == 0` with no source is a
legitimate degenerate configuration; `m > 0` with no source is always a mistake. Add a test that a
configured `m` with no `source_campaign` raises rather than scoring.

Touch nothing else in that file.

### Second exception — fix two `#PBS` lines in `scripts/pbs/hj12_prefix.pbs`

That script currently has:

```
#PBS -o /mnt/.../campaign/workers/logs/hj12_prefix.out
#PBS -e /mnt/.../campaign/workers/logs/hj12_prefix.err
```

Those are fixed paths, and the prefix phase submits **two jobs in parallel**, so the second job
clobbers the first job's stdout. Change both to the **directory** form that
`scripts/pbs/hj8_frontier.pbs:15` uses, so PBS writes a unique `<jobid>.OU` / `.ER` per job:

```
#PBS -o /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/
#PBS -e /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/
```

Update the adjacent comment, which currently explains the shared-path choice, to say the opposite
and why. Run `bash -n` on the script afterwards. Change nothing else in it — the port derivation,
alias verification, adapter checks and the live-planner guard are all correct and are not yours.

## Defect to repair first — `action_review_gate.py`

`run_action_review` decides approve-versus-replace by reading `resp.code`
(`src/sidekick/systems/action_review_gate.py:53-61`). It gets `resp` from `planner.correct`. But
`CodexExecPlanner.correct` (`src/sidekick/agents/planner.py:316-335`) prompts for *prose* — "Reply
with concise correction text only" — and **never sets `code`**. Against the real hosted planner this
gate can only ever return `approve`, while still spending a planner call to do it. It passed review
because the unit test's stub sets `code` (`tests/unit/test_action_review.py:168`).

Repair: call `planner.act` instead, with a transcript whose final line is
`PROPOSED_ACTION: <formatted action>`. `act` prompts for a fenced action and parses it through
`_maybe_python_fence` (`planner.py:337-352`), so it genuinely returns code. Verdict is `approve`
when the returned code matches the proposal after whitespace normalisation, or when no code comes
back; otherwise `replace`. `act` needs `task_id`, which the gate does not currently receive — thread
it through from the loop.

Then **add a test whose stub mirrors the real planner**: returns prose, `code=None`, for `correct`,
and a fenced action for `act`. The existing test must keep passing. A stub that is more capable than
the model it stands for is how this defect survived.

## Build

### 1. `schemas.py`
- `ExecutorAction.kind` Literal gains `"HANDOFF"`.
- `EventType` Literal gains `"handoff"`.
Both are closed Literals; append, never reorder.

### 2. `loop.py` — `SystemPolicy`
Add `takeover: bool = False` and `handoff_allowed: bool = False`.

### 3. `loop.py` — the takeover path
The review trigger is the `elif force_review and packet is not None:` branch at **`loop.py:752`**.
It currently builds `delta = "\n".join(transcript[-8:])` and calls `planner.correct`. When
`policy.takeover` is set, that branch instead:

```python
resp = call_planner("act", lambda: planner.act(task_id, "\n".join(transcript), timeout_s=timeout_s), step)
if resp is None: break
forced_action = action_from_planner(resp, step)
```
Use the **full** transcript, not the last 8 lines: the planner is solving the task, not commenting
on it, and that is exactly what the existing `planner_drives` branch passes at `loop.py:791-796`.

On success emit an event with `actor="planner"`, `event_type="action"`, the action payload,
`usage=resp.usage` and `env_state_hash=env.snapshot_hash()` — matching `loop.py:803-810`. Increment
a new counter `n_planner_actions`. **Do not** increment `n_interventions`, which counts
`INTERVENTION:` turns, and **do not** append anything to `exec_turns` here.

Then at the executor branch (`loop.py:811-812`), use the planner's action in place of the
executor's:
```python
action = forced_action if forced_action is not None else action_from_executor(step)
```
Reset `forced_action = None` at the top of each step. If `action_from_planner` returns None, fall
through to the executor rather than breaking the episode.

Everything downstream is untouched: the shared execution block at `loop.py:943-970` calls `env.step`
and appends the assistant turn plus the `OBS:` user turn. **The executor's context therefore records
the planner's action as if the executor had taken it** — no new token class, which is the entire
point of the design. Confirm in a test that no `INTERVENTION:` string is appended on this path.

### 4. `loop.py` + `planner.py` — HANDOFF
- `planner.act` gains `allow_handoff: bool = False`. When True, extend its prompt to permit a line
  `HANDOFF` meaning "the remaining work is routine enough for a smaller local executor to finish".
  Keep the existing options unchanged. **v1 carries no note**: a `HANDOFF: <note>` payload would be
  a token class the executor was never trained on, which is the exact mistake this campaign already
  paid a retrain to fix. Plain `HANDOFF`, nothing more.
- `action_from_planner` (`loop.py:404`) must detect a HANDOFF reply **before** falling back to the
  code fence, since `_maybe_python_fence` returns None for it.
- In the `planner_drives` branch: on a HANDOFF action, emit an event with `event_type="handoff"`,
  record `handoff_step = step`, flip a local `driver_is_planner = False`, and `continue`. From then
  on the executor drives. **The handoff consumes the step index** — document that choice in a
  comment; episodes average 14 steps against a 40 cap, so it costs nothing real, and the
  alternative re-entrancy is not worth the complexity.
- Pass `allow_handoff=policy.handoff_allowed` from the loop.

### 5. Run payloads
- `run_start`: append `takeover` and `handoff_allowed` **only when True**. The E4 precedent at
  `loop.py:602-603` does exactly this so existing exact-payload tests keep passing.
- `run_end`: add `n_planner_actions` and `handoff_step` (None when no handoff).

### 6. `systems/planner_handoff.py`
`class PlannerHandoff(PlannerAlone)`, `name = "planner_handoff"`, `policy_defaults` = planner_alone's
with `handoff_allowed=True`. Register it in `systems/__init__.py` — **append** to `SYSTEM_NAMES`
after the existing entries; tests assert the original eight remain a prefix in order.

### 7. `runner.py` — `system_kwargs`
Forward `takeover` and `handoff_allowed` from the top-level config for the systems that can use
them (`fixed_k`, `sidekick`, `router_seq`, `oracle_escalation`, `action_review`, `planner_handoff`),
and forward `adapter_name` for `planner_handoff` the way the existing tuple does.

### 8. Configs
Copy `configs/hj8_fixed_k_10.yaml` and `hj8_fixed_k_3.yaml` (frozen — copy, never edit), adding
`takeover: true` and a new `campaign_id` of the form `hj12_takeover_fixed_k_<K>_20260923`. Keep
every executor setting, limit and price path identical so the only difference from the existing
advise arms is the channel.
- `hj12_takeover_exception.yaml` / `hj12_advise_exception.yaml`: base on
  `configs/hj11_action_review_exception.yaml` (frozen — copy), `verifier.kind: rule_trigger`,
  `rules: [on_exception]`; the first sets `takeover: true`, the second does not. These two are a
  matched pair and must differ in exactly that one key — diff them and paste the diff in STATUS.
- `hj12_planner_handoff.yaml`: `system: planner_handoff`, a **live** planner (no cached packet
  replay — this arm buys its own plan and its own steps), `handoff_allowed: true`.
- Every config that serves the executor uses `lora_name: sft_b_plus`, which the PBS harness
  registers against `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b`.

### 9. Tests — `tests/unit/test_takeover.py`
With `MockEnv` and stub planners:
1. Takeover at a scheduled review executes the planner's code: the `env.step` sequence contains it,
   and `exec_turns` gains an assistant turn holding that action followed by an `OBS:` user turn.
2. **No `INTERVENTION:` turn is appended on the takeover path**, and `n_interventions` stays 0 while
   `n_planner_actions` is 1.
3. The same config with `takeover=False` produces the `INTERVENTION:` turn and no planner action —
   the two arms differ only in the channel.
4. A planner returning an unparseable reply falls through to the executor without ending the episode.
5. `HANDOFF` flips the driver: actions before it carry `actor="planner"`, actions after carry
   `actor="executor"`, and `handoff_step` is recorded in `run_end`.
6. `handoff_allowed=False` means a `HANDOFF` string is never offered in the prompt and, if returned
   anyway, does not flip the driver.
7. The ledger charges an `act` call exactly as it charges a `correct` call (`loop.py:316-392`).

## Constraints

- `aquarius01` is a **login node**. No interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Run the
  suite in PBS: `timeout 1800 hpc bash -c 'cd <repo> && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 <pytest invocation>'`.
- pytest needs `--import-mode=importlib`. The suite must stay at **≥ 462 passed, 0 failed** (it was
  456 before this wave; the prefix unit added tests — check the current count first and never let it
  fall).
- `timeout` on every command.
- **Do not `qsub` any GPU job, run any evaluation, or retrain.** No hosted planner is to be called:
  every test uses a stub.
- **Read-only** on `/scratch/n12194778/sidekick/results/`.
- **Do not commit.** I review the diff and commit.
- Do not read, analyse or report any `test_normal` or `test_challenge` data.
- FROZEN, read but never edit: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.

## Return contract

`campaign/workers/STATUS_X2.md`, under 900 words, updated at each milestone so the unit is
resumable:
- Files created/modified and the exact changed signatures.
- The diff between the two exception configs, pasted.
- The suite command and its final counts, pasted.
- Confirmation that the takeover path appends no `INTERVENTION:` turn, with the test name that
  proves it.
- Each claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`.
- Anything in this brief that is wrong about the code — say so plainly rather than working around
  it silently.
