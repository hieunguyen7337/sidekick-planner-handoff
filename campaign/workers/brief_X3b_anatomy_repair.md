# Brief X3b — two additions to the failure anatomy

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Context — read this so you do not "fix" what is already correct

`scripts/analysis/failure_anatomy.py` and its output
`campaign/results/failure_anatomy_dev_20260921.json` are **working and reviewed**. An earlier draft
of this brief described a defect in section 2; the previous unit found and fixed that defect itself
before finishing. Section 2 now correctly detects environment exceptions from observation **text**
(`error_type` is always null for in-environment failures) and reports a populated distribution:
67.2% of `sft_plan_iaware` executor failures have their first error in the first third of the
episode. **Do not re-litigate section 2.** Do not change the exception detection. Do not regenerate
sections 3, 4 or 5.

Two things are genuinely missing. Add them; change nothing else.

## Addition 1 — `termination_reasons` per arm (required, pre-registered)

`docs/prereg_hj12_dev_20260922.md` §7.3 registers per-arm termination counts as a **required**
reporting item, and they are not in the output. The reason it is load-bearing: the next experiment
shares a 40-step budget between replayed planner steps and live executor steps, so step exhaustion
is a pre-registered rival explanation for any quality decline. Without these counts that check
cannot be run.

Add a top-level `termination_reasons` block: for each of the three arms, the count of episodes whose
`result.json` `error_type` is each of `limit`, `crash`, `timeout`, `parse_error`, `api_error`, and
`null` (ran to completion). Counts must sum to 114 per arm.

**Expected value, stated so you cannot tune to it**: `sft_plan_iaware` should show **18** episodes
with `error_type: "limit"`. If your number differs, report yours and say it differs. Do not adjust
the code until it matches — a disagreement here is information, and silently reconciling it would
destroy that.

Note in the block that `limit` is deliberately **not** treated as broken
(`scripts/setup/campaign_summarize.py:33`: `BROKEN = {"api_error", "timeout", "crash",
"parse_error"}` — an episode that spent its step budget is a real outcome, not a broken run).

## Addition 2 — make section 1's metric labelling honest

`section1_opportunity_table` reports a `goal_pass` block and a `tgc_pass` block whose cells are
byte-identical (31/5/38/40 for `sft_plan_iaware`). They are identical because the script binarises
`goal_pass_rate` at 1.0, which **is** the definition of TGC. The numbers are right; the two labels
imply two independent measurements when only one was made.

1. Rename the `goal_pass` block to something that states the threshold, e.g.
   `tgc_from_goal_pass_eq_1`, and add a one-line `note` saying it is identical to `tgc_pass` by
   construction. Keep `tgc_pass` as it is. Delete no numbers.
2. **Add** a genuinely continuous block, `section1b_goal_pass_continuous`, per executor arm:
   - mean `goal_pass_rate` for the planner and for the executor over all 114 pairs;
   - the paired mean difference (planner − executor) with a task-clustered 95% bootstrap CI,
     10,000 resamples — **reuse the bootstrap in `scripts/setup/hj1_gate.py` (`paired_diff`), do not
     write a second one**;
   - the count of pairs where the planner's rate strictly exceeds the executor's, where they are
     equal, and where the executor's is higher.

   This is the continuous companion to the 38-pair opportunity cell, and the campaign's primary
   metric is `goal_pass_rate`, so it should not be missing.

## Constraints

- You own `scripts/analysis/failure_anatomy.py` and
  `campaign/results/failure_anatomy_dev_20260921.json`. **Touch nothing else.** Other units are
  working in this tree in parallel: do not touch `src/`, `scripts/pbs/`, `configs/`, any other
  `scripts/analysis/*.py`, or any file under `docs/` or `campaign/` except your STATUS file.
- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync` or `ffmpeg` there. The
  previous unit found that the HPC node's `python3` lacks `pydantic` and used the repo venv:
  `timeout 1800 hpc bash -c 'cd <repo> && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python scripts/analysis/failure_anatomy.py'`
- `timeout` on every command.
- **Read-only** on everything under `/scratch/n12194778/sidekick/results/`.
- **Dev only.** Never read, analyse or report `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.
- **Do not interpret the results or recommend next steps.**

## Return contract

`campaign/workers/STATUS_X3b.md`, under 400 words:
- The `termination_reasons` table for all three arms, and whether `sft_plan_iaware` showed 18
  `limit` episodes.
- The continuous section 1b numbers, including the CI.
- The exact command run.
- Confirmation that sections 2–5 are unchanged, with the byte size of the JSON before and after.
- Each claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`.
