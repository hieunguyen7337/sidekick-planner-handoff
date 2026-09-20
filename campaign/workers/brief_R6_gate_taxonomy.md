# R6 — the B1 smoke gate fails on normal episode endings, not just infrastructure faults

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
Narrow fix on the critical path. Do only what is below.

## What happened (observed, job `25559066`, 2026-09-20)

The repaired B1 smoke reached a healthy server, passed its identity check, confirmed the frozen
sample, made a **real live planner call**, and then killed itself:

```
[b1] OPERATOR_CONFIRM branches_to_run=1600 max_planner_calls_total=10000 ...
[b1] FATAL: smoke_only: 1 rows with branch_error_type; stopping
[b1] smoke spend: n_rows=1 live_planner_calls_sum=1 branch_planner_calls_tick_sum=7 planner_tokens_sum=24562
```

The single row that triggered it:

```
error_type: limit        error_detail: None
steps: 40                replay_k: 29
live_calls: 1            tick_calls: 7        tokens: 24562
run_id: fixed_k/1/07b42fd_3__b5_treated_s102
```

That branch is **healthy**. It ran eleven live steps past the replayed prefix and spent a real
planner call. `limit` means the episode hit its step ceiling, which is an ordinary way for an
AppWorld episode to end, not a fault.

## The cause is the specification, not the implementation

The brief for the previous unit said "FATAL if any row has a non-null `branch_error_type`". That
was written from the 2026-09-19 data, where every row happened to be `crash`, and it wrongly
generalised to the whole taxonomy. The gate does exactly what it was told.

`error_type` is set to any of `limit | timeout | parse_error | crash | api_error | None`
[OBSERVED src/sidekick/systems/loop.py:317, 346, 386, 438, 660; the taxonomy comment is at
src/sidekick/protocols/schemas.py:126]. `limit` is assigned when the step budget is exhausted
[OBSERVED loop.py:317, 660].

## Fix

In `scripts/pbs/b1_pilot.pbs`, split the taxonomy into two classes and gate only on the first.

**Infrastructure faults — these still FATAL**: `crash`, `api_error`, `timeout`.
These mean the harness, the server or the planner failed, which is what the smoke exists to
detect. `timeout` stays fatal deliberately: the pre-registration's quota-stall rule already
treats `api_error + timeout` as the signal that the planner is unavailable.

**Ordinary episode outcomes — these must NOT FATAL**: `limit`, `parse_error`, and `None`.
A step-limit ending and an unparseable executor turn are things the agent does; a smoke that
forbids them can never pass.

Requirements:
- Print a **count of every error type seen**, both classes, in the spend line, so a run that is
  quietly all-`limit` is visible even though it passes. Do not hide the benign ones.
- When an infrastructure fault fires, keep the existing behaviour: name the count and print
  `branch_error_detail` for the first three.
- Keep the other two gate conditions exactly as they are: no row stepping past `replay_k + 1` is
  fatal, and zero summed planner tokens is fatal. Both were correct, and on this run both would
  have passed.
- Define the fatal set as a single named list in one place so a future reader can see the policy
  rather than infer it from a condition.

## Test both directions, again

The last two guards to reach a live job were each verified only on the input they were meant to
reject, and each then rejected something healthy. Do not repeat that. Extend
`campaign/workers/scratch_A20/test_b1_pilot_guards.py` (you own it) with:

1. a row with `limit` → gate **passes**, and the error-type count line shows `limit=1`
2. a row with `parse_error` → gate **passes**
3. a row with `crash` → FATAL, detail printed
4. a row with `api_error` → FATAL
5. a row with `timeout` → FATAL
6. a mixed sample of `limit` plus `crash` → FATAL, and the count line shows both

Every currently-passing case in that harness must keep passing.

## Constraints

- `aquarius01` is a login node — steering only. No python, pip, tar, rsync there. Tests run in a
  PBS job via `hpc bash -c '...'`. `timeout` on every command. BLAS 1 thread.
- Do not commit, do not run git, do not `qsub` any GPU job.
- Do not edit `scripts/pbs/hj8_frontier.pbs` (a live job is running from it right now),
  `src/sidekick/runner.py`, `scripts/setup/branch_counterfactual.py`, or `scripts/analysis/*`.
- `docs/prereg_b1_pilot.md` is frozen.
- Suite must stay at **433 passed, 1 skipped**: `-m pytest tests -q --import-mode=importlib`.
  `bash -n scripts/pbs/b1_pilot.pbs` clean. Report the exact final line.

## Return contract

Write `campaign/workers/STATUS_R6.md` as you go. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`. Final report, eight lines or fewer: the fatal set you defined and where, the six
test cases with the evidence each behaved correctly, the suite's final line.
