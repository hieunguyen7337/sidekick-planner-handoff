# A15 (U-J8A) — analyse the two J8a baselines properly, and record them

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `campaign/RUNS.md` (append a J8a entry), and a report at
`campaign/workers/A15_J8A.md`. You may add a small analysis helper under
`campaign/workers/scratch_A15/` if you need one.
**Do not touch** `src/`, `configs/`, `scripts/pbs/`, `docs/`, or `scripts/analysis/j10_report.py`
itself — you are a **user** of that script, not its author. If it needs a fix, **report the fix;
do not make it.**

🔺 **Do not submit any GPU job and do not re-run any arm.** The data exists. Analysis only.

## What just landed

Job `25460140` ran `ARMSET=free` and finished exit 0 in 48m50s, both arms `rc=0`, both gates PASS
[OBSERVED campaign/workers/logs/hj8_frontier_free_20260919.25460140.aqua.out].

Two dev campaigns under `/scratch/n12194778/sidekick/results/` (read-only):
- `hj8_executor_alone_bplus_20260919` — `executor_alone`, no planner at all
- `hj8_sft_plan_bplus_20260919` — `sft_plan`, cached packets only

Both are dev 57 tasks × seeds {1,2}, `n_broken = 0`, and **zero hosted planner calls**
(`planner_tokens_total: 0`, `usd_total: 0.0`; `sft_plan`'s 114 "calls" are cache replays).

The per-seed figures printed in the job log are:

| arm | tgc seed1 | tgc seed2 | steps_mean | mean_goal_pass_rate |
|---|---|---|---|---|
| executor_alone | 0.1404 | 0.1228 | 21.94 | 0.5289 |
| sft_plan | 0.4211 | 0.3860 | 19.62 | 0.7000 |

⚠ **Those are unpaired seed means with no interval, and must not be quoted as the result.** That
is exactly what this unit exists to replace.

## The task

**1 · Run `scripts/analysis/j10_report.py` on these two campaigns.** It was written and dry-run on
dev for precisely this shape of data [OBSERVED campaign/workers/A12_J10_ANALYSIS.md]. Read that
report first for its interface and its conventions. It resamples **by task**, because paired seeds
within a task are not independent.

🔺 **This is also the script's first contact with real J8 data.** If it needs any hand-holding,
special-casing, or an edit to run — **that is a finding and it must be in your report**, because
its whole purpose is to run unmodified on J10. Report exactly what you had to do, even if it was
nothing. "It ran unmodified" is a valuable result; a silent workaround is a serious one.

**2 · Produce the paired contrast** `sft_plan − executor_alone` on the tasks the two arms share,
with:
- the paired mean difference in TGC and in goal-pass-rate, each with a **task-clustered bootstrap
  CI**;
- the number of tasks actually paired, and any task present in one arm but not the other;
- cost alongside quality: planner calls per episode and steps per episode for each arm.

**3 · Sanity-check the arms against each other.** `executor_alone` must show **exactly zero**
planner calls; if it does not, stop and report that before anything else. Confirm `n_broken = 0`
independently rather than trusting the log line, and report any episode that hit `max_steps`.

**4 · Append a J8a entry to `campaign/RUNS.md`** in the style of the existing campaign entries —
match how neighbouring entries are structured rather than inventing a format. It must record: the
job id, the two campaign ids, the paired contrast with intervals, the zero-quota confirmation, and
the caveat that these are the **two baselines**, not a frontier: no live-planner arm has run yet,
so nothing here speaks to adaptive-vs-fixed allocation.

## Two things not to conclude

- A large `sft_plan − executor_alone` gap shows the **planner's contribution is large**. It does
  **not** show that adaptive allocation beats fixed allocation — that is what the live arms test.
  Do not write the stronger claim.
- These are **dev** numbers, on a split that has been looked at many times. They calibrate and
  they bound; they are not evidence about the thesis. Say so.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, **synchronously**:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`. A job returning in ~1s has crashed;
  read its output before believing it.
- 🔺 **Zero planner calls. Do not invoke `codex`** — quota is exhausted until ~21:13 today.
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Read the campaigns; never write them.
- 🔺 **Do not read, analyse or report any `test_normal` or `test_challenge` data.**
- **Do not commit.** Suite baseline **406 passed, 1 skipped**; you should not affect it.
- Write `campaign/workers/STATUS_A_15.md` in your first three actions, updated per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The paired contrast with task-clustered intervals, and the number of tasks paired.
- 🔺 **Whether `j10_report.py` ran unmodified**, and precisely what you did if it did not.
- The zero-planner-call confirmation for `executor_alone`, verified from the artifacts.
- The `campaign/RUNS.md` entry as written.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
