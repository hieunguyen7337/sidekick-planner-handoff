# D2 — are the intervention points that HELP predictable from a recent environment error?

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**READ-ONLY ANALYSIS.** You may create only the two output files named at the end. Do not modify any
existing file. Do not write anywhere under `/scratch/n12194778/sidekick/results/` — read it only.
Do not run git, do not commit, do not `qsub` a GPU job.

`aquarius01` is a login node — steering only. **All computation must run inside a PBS job via**
`hpc bash -c '...'` (compound commands need `bash -c`). `timeout` on every command. BLAS pinned to
one thread: `export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`. Python interpreter:
`/scratch/n12194778/sidekick/env/bin/python`. Write any script to a file first and run it from the
file.

## Background — the question this answers

The B1 counterfactual pilot is complete: 1600 branches over 200 intervention points, 142 episodes.
Measured outcome, `branch_gpr` treated minus untreated per point:

- mean +0.0048, 95% CI [-0.0125, +0.0223] — indistinguishable from zero
- 17 points (8.5 %) HELP (Δ > +0.166), 19 points (9.5 %) HARM (Δ < -0.166), 164 neutral
- a perfect oracle picking the single best point per episode gains **+0.0335 GPR**, CI [+0.0153, +0.0530]

Learned gates have all failed (AUROC at or below chance on real decision points). The open question
is whether the helping points are identifiable by a **trivial, label-free heuristic** instead:
*did the environment just raise an error?* If they are, a useful gate exists and it needs no
training. If they are not, the gating approach has no cheap rescue.

## The data

`/scratch/n12194778/sidekick/results/b1_pilot_train_20260920/branch_runs.jsonl` — 1600 rows, one per
branch. Relevant fields: `campaign`, `seed`, `task_id`, `i`, `step`, `condition`
(`treated`/`untreated`), `branch_gpr`, `branch_seed`, `key`, `correction`.

A single intervention point is the group `(campaign, seed, task_id, i)`. Its Δ is
`mean(branch_gpr | treated) - mean(branch_gpr | untreated)`. `step` is the source-episode step at
which the intervention was applied.

The **source** episodes live under the campaign named in the `campaign` field — for every row it is
`hj4_correction_train_20260917`. Find, under
`/scratch/n12194778/sidekick/results/hj4_correction_train_20260917/`, the episode matching
`(seed, task_id)` and read its `events.jsonl`.

## What to compute

For each of the 200 intervention points, determine from the source episode's `events.jsonl` whether
an **environment error** occurred in the observations shortly before `step`. Define and report two
windows: the immediately preceding step, and any of the three preceding steps.

You must first establish, and state, **how an environment error is represented in these events** —
inspect the actual event records rather than assuming. Candidates to look for: an `observation`
payload containing a Python traceback, an `Exception`/`Error` string, a non-zero status, or an
explicit error field. Quote the literal marker you keyed on and cite the line of a real event that
contains it. If several markers exist, report each separately.

Then produce a 2×2 and the associated rates:

```
                      Δ > +0.166 (helps)   otherwise
recent error
no recent error
```

Report, for each window: precision (of points flagged by the heuristic, what fraction help),
recall (of helping points, what fraction are flagged), the base rate (17/200), and the lift over
base rate. Do the same with HARM (Δ < -0.166) as the target, because a heuristic that selects
harmful points is as important a finding.

Also report the **mean Δ of the flagged subset** against the mean Δ of the unflagged subset, with a
bootstrap 95 % CI on the difference (2000 resamples over intervention points, seed 0). That number
is what decides whether the heuristic is worth anything: a gate that fires on the flagged subset
earns that mean Δ per firing.

## Honesty requirements

- If the episode or its events cannot be located for some points, report how many and exclude them
  explicitly; do not silently drop them.
- 200 points with 17 positives is a small sample. Report the confidence interval on precision and do
  not describe a difference as real if its interval spans the base rate.
- If the heuristic does no better than chance, say so plainly. That is a useful result and it is the
  outcome I expect; do not search for a variant that looks better and report only that one. If you
  do try more than one definition of "error", report **all** of them, including the ones that failed.

## Return contract

Write `campaign/workers/STATUS_D2.md` (working notes) and
`campaign/results/b1_error_trigger_20260920.json` (the computed table and statistics).

Report back in **twelve lines or fewer**: the error marker you keyed on with its citation, the two
2×2 tables, precision/recall/lift for help and for harm, the mean-Δ difference with CI, how many
points were excluded and why, and a one-line verdict on whether an error-triggered gate is worth
building. Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
