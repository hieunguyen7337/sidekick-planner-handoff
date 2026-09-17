# W-10 — independently recompute the J6 `needed` fraction from raw columns

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why this unit exists

The campaign plan requires that `needed` be **recomputed from the raw columns by a second
worker type before any number is quoted**. Another implementation already produced a set of
numbers. Yours must be arrived at **independently** so that agreement is evidence.

🔺 **Do not import, read, copy or call `scripts/setup/branch_counterfactual.py`.** It is the
implementation under test. If you read it you have destroyed the purpose of this unit. Work
only from the raw JSONL described below and the rule written out here.

## Input — one file, raw

`/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl`

One JSON object per line, one line per **branch rollout**. Roughly 1,527 lines. Inspect the
keys yourself and report them. Each row identifies:

- an **intervention point** — the combination of campaign/seed/task_id and the intervention
  index within that episode;
- a **condition**: `treated` (the expert correction was injected) or `untreated` (it was omitted);
- a **branch seed**: `101` or `102` (other seeds may appear; ignore anything outside {101, 102});
- an outcome, a goal-pass rate in [0, 1], plus the episode's own factual outcome.

Read the actual field names off the file. Do not assume mine.

## The rule, written out in full — implement exactly this

For each intervention point p:

1. Collect `treated[101]`, `treated[102]`, `untreated[101]`, `untreated[102]`.
2. A point is **complete** only if all four of those exist and none is null. An incomplete
   point is **dropped, never imputed**.
3. `delta(p) = mean(treated[101], treated[102]) - mean(untreated[101], untreated[102])`.
4. The band is a rule, not a number. Using the **train** file
   `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl`,
   compute `band = 75th percentile of |treated[101] - treated[102]|` over train points that
   have both treated samples. State which percentile convention you used (linear
   interpolation vs nearest-rank) and report the value to 6 decimals.
5. `needed := delta > band`, `needless := delta < -band`, `ambiguous := |delta| <= band`.
   Strict inequalities exactly as written.

## Report these numbers

- n lines in each file; n points found in dev; n complete; n dropped and why.
- the band.
- counts and fractions of `needed` / `needless` / `ambiguous` over complete dev points.
- mean delta overall and within each of the three labels.
- the fraction of complete points whose factual outcome lies **outside**
  `[min(treated), max(treated)]` — a validation statistic, not a label.
- **Additionally**, the split-half agreement between the two branch seeds: define
  `d101 = treated[101] - untreated[101]` and `d102 = treated[102] - untreated[102]`, and
  report Pearson r, Spearman rho, the fraction of points where `d101` and `d102` have the
  same sign among points where both are nonzero, and how many points have both `|d101| > band`
  and `|d102| > band` versus how many would be expected if the two were independent.

## Constraints — you are NOT covered by the login-node guard, read this

- `aquarius01` is a **login node for steering only**. Never run `python`, `pip`, `tar`,
  `rsync` or `ffmpeg` there. All computation goes in a PBS job. Use:
  `env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-w10-spool timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<your command>'`
  Your sandbox has `~/.hpc-spool` and `/var/tmp` read-only, which is why `TMPDIR` and
  `HPC_SPOOL` must be set on every such call.
- Pin BLAS to one thread: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.
  The interpreter is `/scratch/n12194778/sidekick/env/bin/python`.
- Put `timeout` on every command.
- **Do not submit any GPU job.** Three J6 jobs are live against these trees.
- **Do not write anything into `/scratch/n12194778/sidekick/results/`.** Those trees are
  live. Put your script and any output under `/tmp/w10/`.
- **Do not commit.** Do not modify the repo except to create
  `campaign/workers/W10_RECOUNT.md` with your findings.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

Short. The numbers above, plus the field names you found. Tag every factual claim
`[OBSERVED <path>:<line>]` or `[INFERRED]`. Reproduce any quoted field name with a literal
`grep -c` in the same run.
