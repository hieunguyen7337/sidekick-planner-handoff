# W-24 — the permutation null for the label rule: is `f` above chance at all?

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Analysis only. CPU only. Zero planner calls. Do not modify production code. Do not commit.**

## Why this unit exists

The campaign's headline result is `f`, the fraction of intervention points labelled `needed`,
and a second quantity that has been computed but never quoted: the "allocation headroom",
mean `help` = mean(max(Δ, 0)), which is what a perfect oracle router would capture.

**Neither has ever been compared against a null.** Both are selection statistics computed on a
noisy Δ, and selecting the top tail of a noisy quantity produces an apparently positive result
even when the true effect is exactly zero. A quick Gaussian check is ambiguous rather than
reassuring: Δ is spiky with a large mass at exactly 0 (within-condition SD is 0 at the median),
so the Gaussian approximation does not describe it and cannot be used to reason about the tail.

So the null must be measured empirically. That is this unit, and it costs nothing but CPU.

## Data

- Train: `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl`
- Dev: `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl`

🔺 **Read-only. Do not write anything under `/scratch/.../results/`.**

`campaign/workers/scratch_W20/analyze_ceiling.py` already loads these files, groups rows into
points, and filters to complete points. **Reuse its loading and grouping logic** so this unit's
population matches W-20's exactly. Put your script in `campaign/workers/scratch_W24/`.

## Definitions — quote these exactly; an earlier unit got this wrong

A **point** is keyed `(campaign, seed, task_id, i)`. A point is **complete** when every replicate
branch seed is present for **both** conditions. Confirm and report how many replicate seeds there
actually are per condition (W-20 found 101, 102, 103, 104).

- Δ = mean(treated) − mean(untreated), over the replicate seeds.
- `needed` := Δ > δ. `needless` := Δ < −δ. `ambiguous` := |Δ| ≤ δ.
- ⚠ **`f` = needed / n.** It is **not** the needless fraction. A previous analysis pass reported
  the needless column as `f` and the error propagated into a decision. Print the literal
  numerator and denominator next to every `f` you report.
- `help` = max(Δ, 0); `harm` = max(−Δ, 0).
- **oracle gain over always-intervene** = mean(harm); **over never-intervene** = mean(help).
  (Both follow from mean(treated) + mean(harm) = mean(untreated) + mean(help).) Verify that
  identity holds numerically in your output and say so.

## The null: a paired sign-flip permutation

The branch design uses **common random numbers** — `treated[s]` and `untreated[s]` share branch
seed `s`, and the measured pairing correlation is r ≈ 0.656 train / 0.588 dev. A permutation that
ignores the pairing would destroy that correlation and produce a null that is too wide, making the
observed result look better than it is. **Do not pool and reshuffle.**

The correct null for paired data under H0 "the intervention has no effect at this point":

> For each point, and **independently for each branch seed `s`**, swap `treated[s]` with
> `untreated[s]` with probability 0.5. Then recompute Δ, the labels, and every statistic below.

This preserves the CRN pairing and the empirical score distribution exactly, and assumes only
exchangeability of the two conditions within a seed — which is precisely H0.

Run **10,000 permutations**. Use a fixed, reported seed so the result reproduces.

## What to report

For **train** and **dev**, and for both the **all-complete** and **contestable** point sets
(contestable = excluding ceiling points where mean(untreated) = 1.000 and floor points — W-20's
definition), at **δ = 0.166** and **δ = 0.100**:

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | | | | | |
| `needless` count | | | | | |
| mean Δ | | | | | |
| mean `help` (oracle gain vs never) | | | | | |
| mean `harm` (oracle gain vs always) | | | | | |

The one-sided p is the fraction of permutations whose statistic is ≥ the observed value.

Also report, because it is the cleanest single test of whether *any* signal exists:

- **The asymmetry statistic** `needed − needless`, observed vs null. Under H0 the sign-flip null
  makes this symmetric around 0 by construction, so it is the sharpest available test of a real
  directional effect. Give its observed value, null distribution and two-sided p.

## Interpretation you must NOT do

Report the numbers. **Do not recommend a course of action, do not declare the thesis supported or
refuted, and do not propose amending δ or the pre-registration.** State plainly what each p-value
does and does not license, and note that the contestable-set results are a post-hoc subset and
must be labelled as such.

If a statistic's observed value falls inside its null interval, say so in plain words rather than
softening it.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 10,000 permutations over ~400 points is small; if it does not finish in 20 minutes, vectorise
  rather than raising the walltime.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job.** Quota is exhausted
  until 2026-09-19 ~21:13.
- **Do not commit.** Suite must stay at **349 passed, 1 skipped** if you touch anything importable
  (you should not need to).
- Write `campaign/workers/STATUS_W_24.md` with resume state.
- Report to `campaign/workers/W24_PERMNULL.md`. Keep the raw script output in
  `campaign/workers/scratch_W24/w24_out.txt`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The tables above, filled.
- The PBS job id, and the permutation seed.
- The replicate-seed count per condition that you actually observed.
- Confirmation that the identity mean(treated) + mean(harm) = mean(untreated) + mean(help) holds.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
