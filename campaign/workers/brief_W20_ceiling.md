# W-20 — re-cut the estimand excluding ceiling points (analysis only)

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Read-only analysis. Change no production code. Do not commit. `/scratch/.../results/` is
read-only frozen evidence — write outputs under `campaign/workers/`.**

## The problem

At many intervention points the **untreated** condition already scores 1.0. There is no
headroom, so `help` is exactly 0.000 *by definition* and the point can never be labelled
`needed` no matter how good the intervention is. On earlier (partial, two-replicate) train
data this was **232 of 734 points ≈ 32%**.

Those points are structurally incapable of supporting the hypothesis, yet they sit in the
denominator of `f` and in the mean Δ. On the earlier data, excluding them moved mean Δ from
**−0.0206 to +0.0098**, with help 0.164 > harm 0.140 — i.e. the sign of the headline effect
flipped. That was computed before the four-replicate relabelling and **must be redone**.

## Data

- train branch rows: `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl`
- dev branch rows: `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl`

Row fields: `key` (`campaign/seed/task_id/i/condition/branch_seed`), `condition`
(`treated`/`untreated`), `branch_seed` (101/102/103/104), `branch_gpr` (null when crashed).
A **point** is `key` truncated to its first four `/`-separated fields. A point is **complete**
on a seed set when every (condition, seed) pair has a non-null `branch_gpr`.
`Δ = mean(treated) − mean(untreated)` over the four replicates.

A reference implementation of the point grouping is
`campaign/workers/scratch_W19/analyze_delta.py` — reuse its grouping logic rather than
reinventing it, but write your own script under `campaign/workers/scratch_W20/`.

## Definitions to use — and to test rather than assume

- **Ceiling point**: `mean(untreated) >= 1.0` (report also the count at `>= 0.999` in case of
  float noise, and say whether it differs).
- **Floor point**: `mean(untreated) <= 0.0` *and* `mean(treated) <= 0.0` — no intervention
  could show benefit because nothing succeeds either way. Report these separately; **do not**
  merge them into the ceiling class.
- **help** = `max(Δ, 0)`, **harm** = `max(−Δ, 0)`, averaged over the relevant point set.

## What to produce

For **train and dev separately**, and at **both δ = 0.166 (frozen) and δ = 0.100** (the
train-derived floor from W-19):

1. Counts: total complete points, ceiling points, floor points, and the remainder
   ("contestable" points). Give each as n and as a fraction.
2. The label distribution — needed / needless / ambiguous — on **all complete points** and on
   **contestable points only**, side by side.
3. **`f` defined as `needed / n` and `1 − f`**, for both point sets.
   🔺 Be careful here: `f` is the **needed** fraction, not the needless fraction. A previous
   analysis got this wrong. State the numerator and denominator explicitly next to every `f`
   you print, so the definition is checkable from the output alone.
4. mean Δ, mean help, mean harm — on all complete points and on contestable points only.
5. The contribution of ceiling points alone to the overall mean Δ (they should drag it down;
   quantify by how much).

## Interpretation rules

- 🔺 **Do not recommend a change to the pre-registration.** This is neutral evidence for the
  user's decision.
- Excluding ceiling points changes a **denominator**, so it should raise `f` without creating
  a single new `needed` point. **Verify that the `needed` count is genuinely unchanged by the
  exclusion** and say so explicitly — if it changes, something is wrong with the definition
  and you should report that rather than explain it away.
- Report the floor-point result even if it is uninteresting.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. All computation in a PBS job:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit a GPU job.** Quota is exhausted
  until 2026-09-19 ~21:13.
- Other workers own `scripts/setup/branch_counterfactual.py`,
  `scripts/setup/fit_feature_verifier.py`, `src/sidekick/agents/planner.py`,
  `src/sidekick/training/matched_sft.py` and `scripts/pbs/hj6_branches.pbs`. **Do not touch
  any of them.**
- **Do not commit.** Report at `campaign/workers/W20_CEILING.md`, resume state at
  `campaign/workers/STATUS_W_20.md`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The counts and both label tables, with `f` numerators and denominators shown.
- mean Δ / help / harm, all points vs contestable only.
- Explicit confirmation that the `needed` count is unchanged by the exclusion.
- Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]` with the job id that produced it.
