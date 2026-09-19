# A16 (U-B1PRE) — pre-register the clean-counterfactual pilot, before it runs

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit. Do not submit anything.** Your files: a new
`docs/prereg_b1_pilot.md`, and a report at `campaign/workers/A16_B1_PREREG.md`.
**Do not touch** `src/`, `configs/`, `scripts/setup/branch_counterfactual.py`, `docs/prereg_v1.md`,
`campaign/RUNS.md` — other units own those, and the branch script is frozen for this experiment.

🔺 **The entire value of this unit depends on it being finished BEFORE the data exists.** The
document is committed first; the job is submitted afterwards, by the orchestrator, after the quota
resets (~21:13 today). A prediction written after the numbers arrive is worth nothing.

## Background — why this pilot exists

The branch experiment claims to measure `Q(intervention present) − Q(intervention omitted)`, but
until commit `a25d8c9` both arms kept the reviewer live after the focal step, so the untreated arm
received a near-substitute review ~5 steps later. The contrast measured **timing, not value**.

Evidence that this matters, all on **train**: Spearman ρ(`n_later`, Δ) = **−0.163, permutation
p = 0.0007**; on the clean subset (`n_later = 0`, 175 points) `needed` clears its sign-flip null at
**p = 0.0051**, versus **p = 0.712** over all points
[OBSERVED campaign/workers/W25_SUBSTITUTION.md, commit `113b249`].

⚠ Two reasons that is not yet a result: the subset is **doubly post-hoc**, and **dev does not
reproduce** the dose-response (ρ = +0.095, n.s.). This pilot tests it **prospectively**, which is
the only thing that converts it into evidence.

`--untreated-mode suppress_next` (commit `a25d8c9`) makes `n_later = 0` **by construction** rather
than by selection — that is the point of the design.

## The pre-registered prediction — write it EXACTLY as specified

This is decided. Do not reinterpret, soften, or add hypotheses.

**Design.** ~200 train points not previously used for a clean-mode branch, `--untreated-mode
suppress_next`, 4 branch seeds per condition, δ = **0.166** (the frozen band), paired sign-flip
permutation null with **10,000** permutations and an explicitly stated RNG seed.

**Primary population: contestable points** — those with `mean(untreated) < 1.000`. This exclusion
is principled and is fixed in advance: ceiling points are **structurally incapable** of expressing
the `needed` label, so including them moves a denominator without ever moving a numerator
[OBSERVED campaign/workers/W20_CEILING.md]. All-points results are reported **alongside**, always,
whatever they show.

**Primary hypotheses** (both must hold):
- **B1a** — mean Δ (treated − untreated) **> 0** and outside its paired sign-flip null, one-sided
  **p < 0.05**.
- **B1b** — asymmetry (`needed` − `needless`) **> 0** against the same null, two-sided **p < 0.05**.

**Decision rule, fixed now:**
- **Both hold** → the substitution explanation is supported prospectively; `sft_c` becomes
  trainable and H4 returns to the plan.
- **Neither holds** → removing the substitute does not recover the intervention's value; H4 stays
  closed and the campaign reports a negative result **with a mechanism**, which is a publishable
  outcome, not a failure.
- **Exactly one holds** → **inconclusive**. Report as measured and spend no further quota without
  a new plan. Write this branch explicitly; it is the one most likely to be rationalised later.

**Secondary, reported but not gating:** the `needed` count against its null; mean help and mean
harm against theirs; the δ = 0.100 band; and, if the same points have a `schedule_live` result,
the mode-to-mode comparison. **Every secondary is labelled secondary in the document.**

## Also specify, in the document

- **Point selection**: a deterministic, stated rule (ordering + seed) fixed before the run, so the
  sample cannot be chosen to suit. State it precisely enough to reproduce.
- **Cost**: run the script's `PREFLIGHT` projection and record the **projected planner calls**
  before submission, and set `--max-planner-calls-total` as a hard cap. J6 spent 37,368 calls
  against a table that budgeted zero; this pilot does not repeat that. State the cap you propose
  and how the projection was obtained. **Do not invoke the planner to find out** — PREFLIGHT is a
  projection, not a call. If running it needs quota, say so and derive the estimate arithmetically
  instead.
- **Stopping rule**: what happens if the job dies part-way. Partial data must not be analysed as
  though it were the planned sample; say how a resumed or truncated run is handled.
- **What would falsify it**: state plainly the observation that would make you conclude the effect
  is absent. A prediction with no falsifier is not a prediction.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. Any computation goes in a PBS job, **synchronously**:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread.
- 🔺 **Zero planner calls. Do not invoke `codex`.** Quota is exhausted until ~21:13 today, and
  spending it early would consume the pilot's own budget.
- 🔺 **Do not submit the pilot. Do not submit any GPU job. Do not run any branch rollout.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **406 passed, 1 skipped**; a docs-only unit must not affect it.
- Write `campaign/workers/STATUS_A_16.md` in your first three actions, updated per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- `docs/prereg_b1_pilot.md` as written, with the primary hypotheses, the decision rule including
  the inconclusive branch, the point-selection rule, the cost cap and the falsifier.
- The PREFLIGHT projection and the `--max-planner-calls-total` you propose, with the reasoning.
- The exact submission command you recommend — **for the orchestrator to run, not you.**
- Anything in the specification above that you believe is wrong or unachievable: **say so rather
  than silently adjusting it.** This document is the experiment's integrity.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
