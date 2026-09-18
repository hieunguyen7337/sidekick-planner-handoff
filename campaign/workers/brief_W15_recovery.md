# W-15 — make crashed branches recoverable, and make planner cost visible and bounded

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**One file of production code is in scope: `scripts/setup/branch_counterfactual.py`.**
Another worker is concurrently editing `src/sidekick/agents/planner.py` — **do not touch it.**

## Background — what happened, so the requirements make sense

J6 ran the counterfactual branches. 1,498 of 9,272 branches crashed: 1,357 in
`hj6_branches_train_20260917/branch_runs.jsonl` and 141 in the dev one. The cause was that
J6 consumed 37,368 hosted planner calls and exhausted the Codex quota mid-run. J6 was
budgeted at **zero** planner calls, because the branch definition changed on 2026-09-17 to
keep the reviewer live in both arms and the cost table was never updated.

Two defects follow from that, and this unit fixes both.

## Defect 1 — a crashed branch is recorded as "done", so resume never retries it

A crashed branch still gets a row appended to `branch_runs.jsonl`, with
`"branch_gpr": null` and `"branch_error_type": "crash"`
[OBSERVED scripts/setup/branch_counterfactual.py:982-986].

`completed_branch_keys` [OBSERVED :432-448] builds its key set from **every** row, without
looking at `branch_gpr` or `branch_error_type`. The driver then does

```
done = completed_branch_keys(load_jsonl(out_root / "branch_runs.jsonl")) if resume else set()
```

[OBSERVED :1008]. So a crashed branch is permanently excluded from every future resume.
This was confirmed in production: job 25419442 resumed the train campaign after the crashes
and reported `n_jobs=0, n_finished=0, n_skipped=0` — it recovered nothing, because all 6,216
rows exist.

**Verified property you should rely on:** `group_branch_samples` does
`samples.setdefault(pk, {})[(condition, branch_seed)] = row` [OBSERVED :631], and rows are
read from the file in order, so **the last row for a key wins**. A retry can therefore simply
append a new row; the successful row supersedes the crashed one with no deletion or rewriting.
Confirm this yourself and cite it, then build on it.

### Requirement 1

- A row is "done" only if it represents a usable result: `branch_gpr` is not null **and**
  `branch_error_type` is falsy. Rows failing that are retried on the next resume.
- Keep the old behaviour reachable behind a flag (e.g. `--no-retry-errors`) so a run can be
  reproduced exactly as it was.
- Decide where this belongs — a parameter on `completed_branch_keys`, or a separate function
  the driver calls. Either is fine; do not change the meaning of `completed_branch_keys`
  without updating every caller and its tests.
- Do **not** delete, rewrite or deduplicate `branch_runs.jsonl`. It is append-only by design
  [OBSERVED :9]; superseding happens at aggregation time.

## Defect 2 — planner cost is invisible, and unbounded

A branch row carries no planner cost field at all. Its keys are exactly:
`actual_gpr, actual_solved, branch_error_type, branch_gpr, branch_gpr_local, branch_seed,
branch_solved, branch_steps, campaign, condition, correction, i, key, n_later_reviews,
replay_k, review_every_k, run_id, sampling_seed, seed, step, task_id`
[OBSERVED /scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl:1].

There is a `max_planner_calls` at [OBSERVED :382], but that is a **per-episode** cap read from
config. Nothing bounds or even counts what a *campaign* spends. That is why 37,368 calls went
unnoticed until the quota ran out.

### Requirement 2

- **Record per-branch planner cost** on every branch row: the number of planner calls and the
  number of planner tokens that branch consumed. Take them from the episode result if it
  carries them; otherwise derive them from that branch's own `events.jsonl`. **State in your
  report which source you used, with a `path:line` citation.** Use `null` when genuinely
  unavailable — never a silent `0`, which would recreate the exact class of defect this
  campaign has been bitten by repeatedly.
- **Preflight projection**: before dispatching, print one line giving the number of branches
  to run and the projected planner calls, with the per-branch factor stated explicitly rather
  than hidden in a constant.
- **Campaign budget**: a `--max-planner-calls-total N` option. The driver accumulates observed
  planner calls across completed branches and, once the total crosses `N`, **stops dispatching
  new branches and exits cleanly with rc=0** after its normal final aggregation, printing a
  line that says the budget stopped it and that a resume continues. It must not raise, and it
  must not leave the output tree in a state a resume cannot pick up. Default is unlimited, so
  behaviour is unchanged unless the flag is passed.
- In-flight branches at the moment the budget trips may finish normally; do not kill them.

## Tests (pytest, in the existing style and location for this script)

1. A crashed row followed by a successful row for the same key: aggregation uses the
   successful one (this pins the last-wins property).
2. Resume with a crashed row present re-dispatches that branch; with `--no-retry-errors` it
   does not.
3. A successful row is never re-dispatched on resume (guard against over-retrying).
4. The budget stop: with a small `--max-planner-calls-total`, the run stops early, exits 0,
   writes its derived files, and a subsequent resume continues from where it stopped.
5. Per-branch planner cost appears on rows, and is `null` rather than `0` when unavailable.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Anything that computes goes in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Do not make a real `codex` call. Do not submit a GPU job. Do not run J6.** The Codex
  quota is exhausted until 2026-09-19 ~21:13 — that exhaustion is what this unit is about.
  Tests use fakes and fixtures only.
- 🔺 **Do not modify `src/sidekick/agents/planner.py`** — another worker owns it right now.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- **Do not modify anything under `/scratch/.../results/`.** The J6 outputs are frozen evidence.
- Run the suite as `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`.
  Current state to match or beat: **335 passed, 1 skipped, 0 failures** (another worker may
  add a few; never fewer than 335 and never a failure).
- Write `campaign/workers/STATUS_W_15.md` with resume state, updated at each milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- One line with `path:line` for each of: where "done" now excludes error rows; where per-branch
  planner cost is recorded; where the budget stop happens.
- The source you used for planner cost, cited.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
