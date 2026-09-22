# Brief U3 — difference-in-differences with intervals for the two interactions

## Goal

Build `scripts/analysis/j14_did.py` plus unit tests. It computes a **difference-in-differences (DiD)
with a cluster bootstrap interval** for two interactions the paper currently only implies. Both run on
data that already exists on disk. Zero jobs to launch, zero hosted calls.

"Done" means: the script exists, `tests/unit/test_j14_did.py` passes on a scripted fixture whose DiD is
known by construction, and the two reports named in §4 have been written.

## Why this exists (read this; it decides the design)

`paper/preprint_dev_20260923.md` Limitation 5 currently says, in the paper's own words:

> Our central mechanism reading — that receiver tailoring is what permits narration to substitute for
> execution — rests on comparing *which* paired contrasts resolve on each receiver, not on a
> difference-in-differences. The DiD carries no interval in our analysis. "No resolved gap on the
> tailored receiver" is a weaker statement than "a significantly smaller gap than on the untailored
> receiver", and we do not make the stronger one.

Comparing "this contrast excludes zero, that one does not" is **not** a test of an interaction. Two
contrasts can differ in significance while their difference is indistinguishable from zero. This unit
replaces that reasoning with the estimand the claim actually needs. Either outcome is publishable: an
interval excluding zero upgrades the mechanism claim, an interval including zero bounds it honestly.

## Definitions — implement exactly these

Episodes are keyed `(task_id, seed)`. Every quantity below is computed **per episode first**, then
averaged, so the bootstrap resamples whole clusters and never breaks the pairing.

### DiD-1 — narration x receiver, at each depth m in {6, 9, 11}

```
gap_tailored(m)   = mean over episodes of [ narrated_tailored(m)   - executed_tailored(m)   ]
gap_untailored(m) = mean over episodes of [ narrated_untailored(m) - executed_untailored(m) ]
DiD_1(m)          = gap_tailored(m) - gap_untailored(m)
```

Positive DiD_1 means narration substitutes for execution **better** on the tailored receiver — the
paper's mechanism reading. Report DiD_1 at each of m = 6, 9, 11 separately. Do not pool the depths.

### DiD-2 — tailoring x depth, on each planner sample separately

```
depth_gain_tailored   = mean over episodes of [ tailored(m11)   - tailored(m9)   ]
depth_gain_untailored = mean over episodes of [ untailored(m11) - untailored(m9) ]
DiD_2                 = depth_gain_tailored - depth_gain_untailored
```

Compute DiD_2 **twice**: once on the cap-25 planner sample, once on the cap-81 sample. They are
expected to disagree in sign — that disagreement is the point, and it is why the paper reports
substitutability as a one-sample observation (ledger C81-02). Report both; do not average them.

### Estimation

- Metrics: `goal_pass_rate` (primary) and `tgc` (secondary). Run every DiD on both.
- Population: all shared episodes across **all four** arms in the DiD; a crashed episode scores 0
  (this is the project's `population="all"` convention). Report `n_pairs` and how many keys were
  dropped for not appearing in all four arms — if that number is not 0, say so loudly in the report.
- Bootstrap: **10,000** resamples, percentile interval, **fixed seed 20260924**.
  Primary resample unit = **scenario** (`scenario_of(task_id)`), secondary = **task**. Report both,
  the way the existing reports do (`*_task` beside the primary).
- Resample **clusters, not episodes**, and recompute the entire DiD inside each resample. Do not
  bootstrap the two gaps independently and subtract their intervals — that throws away the pairing
  and gives a wrong (too wide) interval. This is the single most important correctness property of
  this unit.

## Files in scope

Create:
- `scripts/analysis/j14_did.py`
- `tests/unit/test_j14_did.py`

Read and reuse, do not re-implement:
- `scripts/analysis/j8_frontier.py` — `paired_contrast` at `:1045` and `paired_diff_scenario` at
  `:1142` are the existing clustered-bootstrap machinery, and `scenario_of` is already imported at
  `:58`. Match their output-field naming so the new report reads like the existing ones.
- `scripts/analysis/j8_frontier.py:140` `parse_arm_spec` — the `LABEL=DIR` CLI convention to copy.
- `tests/unit/test_j8_frontier.py` and `tests/unit/test_hj12_shape.py` — the fixture style to follow.

Out of scope: do not modify `j8_frontier.py` or any other existing analysis script; do not touch
anything under `/scratch/.../results/`; do not touch `configs/`; do not edit the paper or the ledger.

## Campaign directories (verified present on disk 2026-09-23)

Root: `/scratch/n12194778/sidekick/results/`

Tailored granite receiver, cap-25 source (post-guard arms — these exact dates, the `_20260922` and
`_20260923rep` variants are a different population and must not be substituted):
- `hj12_prefix_m6_20260923`, `hj12_prefix_m9_20260923`, `hj12_prefix_m11_20260923`

Untailored granite receiver, cap-25 source:
- `hj13_prefix_zs_m6_20260923`, `hj13_prefix_zs_m9_20260923`, `hj13_prefix_zs_m11_20260923`

Narrated, tailored receiver: `hj16_narrated_m6_bplus_20260923`, `hj16_narrated_m9_bplus_20260923`,
`hj16_narrated_m11_bplus_20260923`

Narrated, untailored receiver: `hj16_narrated_m6_zs_20260923`, `hj16_narrated_m9_zs_20260923`,
`hj16_narrated_m11_zs_20260923`

cap-81 source, tailored: `hj17_prefix_c81_bplus_m9_20260923`, `hj17_prefix_c81_bplus_m11_20260923`
cap-81 source, untailored: `hj17_prefix_c81_zs_m9_20260923`, `hj17_prefix_c81_zs_m11_20260923`

Result layout is `<campaign>/<system>/<seed>/<task>_<variant>/result.json`.

## Outputs

Write to `campaign/results/`:
1. `j14_did_narration_receiver_20260924.report.json` — DiD-1 at m = 6, 9, 11, both metrics.
2. `j14_did_tailoring_depth_20260924.report.json` — DiD-2 on both planner samples, both metrics.

Each report must carry, per DiD: the point estimate, both intervals, `n_pairs`, the four arm labels
and their source directories, the four component means, the two gaps, the bootstrap seed, and the
resample unit. A number that cannot be traced back to a directory from this report is useless to us.

## Constraints — these are not optional

- **The login node is for steering only.** Never run the interpreter, the test suite, or any
  multi-minute command directly on `aquarius01`. Everything computational goes through a job:
  `timeout 1200 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '...'`.
- Put `timeout` on every command you run.
- Pin BLAS to one thread in any job you launch: export `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`,
  `MKL_NUM_THREADS=1`.
- The interpreter is `/scratch/n12194778/sidekick/env/bin/python`; set `PYTHONPATH=src:.` from the repo
  root, which is `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`.
- **Do NOT submit anything with `qsub`.** If you believe a PBS job is needed, stop and say so in STATUS.
- **Do not read, list, or load any `test_normal` or `test_challenge` data.** Dev split only.
- Ignore `.claude/worktrees/` and `.git/`.
- Do not `git commit`, do not `git stash`, do not create branches.

## Return contract

Write `campaign/workers/STATUS_U3.md` as you go — update it at each milestone, not only at the end, so
a killed session is resumable. It must contain:

1. What you created, with paths.
2. The test command you ran and its **verbatim** last 15 lines of output.
3. The DiD point estimates and intervals, as a small table.
4. Every factual claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`. If you state that a number
   came from a file, a literal `grep`/`jq` in the same session must be able to produce it.
5. Anything you could not finish, named plainly. An unfinished item reported honestly is worth more to
   us than a complete-looking report with an invented number in it — we have had a worker fill a
   results table with plausible fabricated values and report zero TODOs, and it cost a day to catch.

Create the two files within your first three actions, then iterate with the tests.
