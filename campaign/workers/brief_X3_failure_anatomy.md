# Brief X3 — failure anatomy: where the executor breaks and what "hard" means

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Create the file within your first three actions, then iterate with tests.** Do not spend the whole
turn reasoning before writing code.

## Why

The campaign is about to test whether a hosted planner doing the *opening* of an AppWorld episode,
then handing off to a small local executor, beats either model alone. That design rests on two
assumptions nobody has checked: that executor failures cluster **early**, and that the early steps
are the ones involving **unfamiliar** API calls. If executor episodes actually fail late, on routine
repetition, the whole design is pointed at the wrong end of the episode. Your job is to measure
this. Nothing like it exists — there is no first-error, per-app or novelty analysis anywhere in
`scripts/analysis/`.

## Scope — you own exactly one new file

Create `scripts/analysis/failure_anatomy.py` and nothing else. **Do not modify any existing file**
under `src/`, `scripts/`, `configs/`, `docs/` or `campaign/` — three other units are working in this
tree in parallel and will collide with you. Your only other write is your STATUS file.

Write its output to `campaign/results/failure_anatomy_dev_20260921.json`.

## Inputs (read-only; never write into any results tree)

| label | path |
|---|---|
| `sft_plan_iaware` | `/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware` |
| `fixed_k_10_iaware` | `/scratch/n12194778/sidekick/results/hj8_fixed_k_10_20260921iaware` |
| `planner_alone` | `/scratch/n12194778/sidekick/results/hj1b_planner_20260915` |

Layout is `<system>/<seed>/<task_id>/{events.jsonl,manifest.json,result.json}`; 114 episodes each
(57 tasks × 2 seeds). Event types include `run_start`, `observation`, `plan`, `action`,
`intervention`, `evaluate`, `error`, `run_end`. Action payloads carry `code` and `raw_output`;
observation payloads carry `text` and an `error_type`. Take the events of the **last** `run_start`
only — a retried run appends to the dead attempt's log with nothing marking the boundary, and
double-counting it is a real defect that has bitten this codebase (see
`src/sidekick/replay.py:110+`, `_events_of_last_attempt`, which you may import and reuse).

## Report these five sections into the JSON

1. **The 2×2 opportunity table.** Per (task_id, seed) pair, planner outcome × executor outcome, on
   `goal_pass` and separately on TGC. The cell where the planner succeeds and the executor fails is
   the room a handoff design has; report its size and list those task_ids.
2. **First-error position.** For each executor failure: the step index of the first observation
   carrying an `error_type`, the total steps taken, whether `max_steps` was hit, and that index as a
   fraction of the episode. Give the distribution (min/25/50/75/max) and the share of failures whose
   first error falls in the first third of the episode. **This is the section the handoff design
   depends on, so state the numbers plainly whichever way they fall.**
3. **Planner step-count distribution** for `planner_alone`: min/25/50/75/max, and the share of
   episodes shorter than each of m = 2, 4, 6, 9. This validates or corrects a grid already chosen.
4. **API novelty by position.** Extract called API names from action `code` with a documented regex
   (report the regex and its miss rate — how many actions yielded no name). For each step index,
   the share of actions whose API name appears for the **first time** in that episode versus a
   repeat. Report the curve separately for planner and executor episodes. This is the operational
   definition of "hard" (novel) versus "tedious" (repeat) that the campaign's mechanism argument
   will rest on, so be explicit that it is a proxy and say what it misses.
5. **Per-app difficulty.** If a task→app mapping is derivable from the data you can already see
   (task_id prefix, instruction text, or a manifest field), report goal_pass by app for each arm. If
   it is not derivable without reading AppWorld's own task metadata, **write "not derivable" and
   move on** — do not go looking for the benchmark's internals.

Also record, at the top level: the exact input paths, episode counts per arm, and how many episodes
were excluded and why.

## How to run it

The interpreter must never run on the login node. Use:
`timeout 1800 hpc bash -c 'cd <repo> && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 <python invocation>'`

Put a `timeout` on every command. Pure standard library plus whatever the repo already depends on;
add no new dependency.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync` or `ffmpeg` there.
- **Read-only** on every path under `/scratch/n12194778/sidekick/results/`. Never write under
  `hj6_branches_train_20260917`.
- **Do not read, analyse or report any `test_normal` or `test_challenge` data. Dev only.**
- Do not submit GPU jobs, run evaluations, or retrain.
- **Do not commit.** I review and commit.
- **Do not interpret the result or recommend next steps.** Report the numbers. The judgement is not
  yours.

## Return contract

`campaign/workers/STATUS_X3.md`, under 600 words, written **at each milestone** so the unit is
resumable if it dies mid-way (this worker lane has died silently before; a STATUS file with resume
state is what makes that recoverable):
- The exact command you ran and the output path.
- The five section headline numbers.
- The API-name regex and its miss rate.
- Each claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`. Any quoted string must be reproduced
  by a literal `grep -c` in the same run, with the count stated.
- If something in this brief is wrong about the data, say so plainly instead of working around it.
