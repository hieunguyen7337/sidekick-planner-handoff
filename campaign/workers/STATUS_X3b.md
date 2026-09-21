# STATUS_X3b — two additions to failure anatomy

DONE. No commit.

## Command
`timeout 1800 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python scripts/analysis/failure_anatomy.py'`

Wrapper around that command copied the JSON to `/tmp/failure_anatomy_before_x3b.json` and compared sections 2–5 after. Job 25596413; 35s on a compute node. [OBSERVED hpc stdout]

## termination_reasons (sum 114 per arm)

| arm | limit | crash | timeout | parse_error | api_error | null |
|---|---:|---:|---:|---:|---:|---:|
| sft_plan_iaware | 18 | 0 | 0 | 0 | 0 | 96 |
| fixed_k_10_iaware | 14 | 0 | 0 | 1 | 0 | 99 |
| planner_alone | 12 | 0 | 0 | 1 | 0 | 101 |

`sft_plan_iaware` `limit` = **18** (matches the stated expected value). [OBSERVED campaign/results/failure_anatomy_dev_20260921.json:34]
`limit` is not in `BROKEN`. [OBSERVED scripts/setup/campaign_summarize.py:33; JSON:31]

## section1b_goal_pass_continuous

sft_plan_iaware (n=114): mean `goal_pass_rate` planner 0.8284, executor 0.7181; planner>executor 42, equal 62, executor> 10; paired mean diff 11.02 pp, task-clustered 95% CI [4.27, 17.89], 10000 resamples. [OBSERVED JSON:396-422]
fixed_k_10_iaware (n=114): planner 0.8284, executor 0.6964; 44 / 59 / 11; 13.2 pp, CI [4.91, 21.31], 10000. [OBSERVED JSON:426-452]
Bootstrap is `hj1_gate.paired_diff(..., resample="task")`. [OBSERVED scripts/analysis/failure_anatomy.py:282; scripts/setup/hj1_gate.py:28,150]

Section 1 `goal_pass` renamed to `tgc_from_goal_pass_eq_1` with identity note; `tgc_pass` kept. [OBSERVED JSON:61,142]

## Sections 2–5 unchanged

Parsed objects equal before vs after for `section2_first_error_position`, `section3_planner_step_counts`, `section4_api_novelty`, `section5_per_app_difficulty`; both arms' `tgc_pass` blocks identical. [OBSERVED hpc stdout compare]
JSON bytes: **67404** before, **70093** after. [OBSERVED `wc -c`; hpc `BEFORE_BYTES`/`AFTER_BYTES`]
Section 2 `sft_plan_iaware` `share_first_error_in_first_third` still 0.6721. [OBSERVED JSON:468]
