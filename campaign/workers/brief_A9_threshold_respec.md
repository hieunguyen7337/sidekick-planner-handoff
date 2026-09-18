# A9 (U-J7) — re-specify the verifier threshold against the attenuation ceiling

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** **Analysis and documentation only — no refit, no retraining, no new artifact.**
Your output files: `campaign/workers/A9_THRESHOLD.md` (the analysis) and a proposed edit to the
J7 threshold specification in `docs/prereg_v1.md`.
**Do not touch** `src/`, `configs/`, `scripts/pbs/`, `scripts/setup/`, or any other doc — other
units own those this cycle. In particular **another unit owns `campaign/RUNS.md`, `docs/PLAN.md`
and `docs/HEAVY_JOBS.md`**; it will fold your conclusion in afterwards. Leave them alone.

## The problem

J7 pre-registered a **dev AUROC ≥ 0.65** threshold for the escalation verifier. The fitted
verifier reached **0.59** and was read as a failure.

That reading may be wrong, because **0.65 is at or above the measurable ceiling.** The labels the
verifier is scored against are themselves noisy: label reliability is ~**0.17** for a single
replicate and ~**0.45** at k = 4. A **perfect** predictor — one that recovers the true latent
label exactly — correlates with labels of reliability 0.45 at only about **√0.45 ≈ 0.67**. A
threshold of 0.65 therefore demands near-perfection, and "0.59 < 0.65" may be reporting the
noise floor rather than the estimator.

This matters beyond bookkeeping: J7's apparent failure is one of the results that made the
campaign look negative. If the threshold was unmeetable by construction, that has to be said
plainly — and **equally plainly if it was not.**

## What to produce

1. **Derive the ceiling properly, and show the derivation.** State the assumed measurement model,
   where the reliability figures come from, and how reliability maps to a bound on achievable
   AUROC. The √0.45 ≈ 0.67 figure above is a **correlation-scale** heuristic; AUROC is not a
   correlation. Either justify the translation between the two scales or replace it with a
   defensible bound and say why. **Do not simply repeat my number — check it.** If it is wrong,
   that is the most useful thing you can report.

2. **Restate J7's result against that ceiling.** Report the attenuation-corrected figure, or
   express the threshold as a *fraction of the ceiling* rather than an absolute AUROC. Give the
   interval, not just the point.

3. **Say what the corrected reading is.** Is 0.59 near-ceiling, mid-range, or genuinely weak?
   One paragraph, in plain language, that a reviewer could read without recomputing anything.

4. **Propose the replacement specification** for `docs/prereg_v1.md` — exact wording, marked as a
   proposal for review, not silently substituted. It must be a rule that could have been written
   *before* seeing the result, and it must be falsifiable.

🔺 **Pre-registration integrity is the point of this unit.** Loosening a threshold after seeing a
number that missed it is exactly what pre-registration exists to prevent. The only honest version
of this change states, in the document: what the original threshold was, that it was missed, why
it is being revised, and that the revision was made **with knowledge of the result**. Write it
that way. A reviewer who spots an unannounced post-hoc loosening will discard the whole campaign,
and they would be right to.

## A worked precedent in this repo

A sibling unit did this correctly for the value function last night: it reported dev AUROC 0.6212
against a **feature-blind step-prior floor of 0.6245** and a **k-NN ceiling proxy of 0.6356**,
which turned an uninterpretable "0.62" into a clear finding (the head is no better than a step
counter). See `artifacts/verifiers/value_fn_20260919/metrics.json`
(`attenuation_floor_step_prior_auroc`, `attenuation_ceiling_knn_proxy`, `attenuation_note`) and
`campaign/workers/A7_VALUE_FUNCTION.md`. **Reporting a floor as well as a ceiling is the part
worth copying** — a number between them is uninformative, and only the pair shows that.

Consider whether an analogous empirical ceiling proxy is computable for J7 from the existing
labels. If it is, it is stronger evidence than any analytic bound. If it is not, say why.

## Where the inputs are

Start from `docs/prereg_v1.md` (the J7 specification), `campaign/RUNS.md` (the J7 result and the
reliability figures), `campaign/workers/W24_PERMNULL.md` (the permutation null and the label-noise
evidence), and `artifacts/verifiers/feature_lr_20260918/metrics.json`. Read what is there rather
than reconstructing it — and if the numbers in the ledger disagree with the numbers in the
artifact, **report the discrepancy; do not average or pick one.**

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. Any computation goes in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** If you touch nothing importable the suite is unaffected; baseline is
  **365 passed, 1 skipped**.
- Write `campaign/workers/STATUS_A_9.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The ceiling derivation, with its assumptions stated and my √0.45 heuristic explicitly checked.
- J7's result restated against ceiling (and floor, if computable), with an interval.
- The plain-language corrected reading, one paragraph.
- The proposed prereg wording, including the disclosure that it was revised post-result.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
