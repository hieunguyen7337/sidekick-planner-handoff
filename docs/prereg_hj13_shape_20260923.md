# Preregistration: HJ-13 — the shape of the allocation curve, tailoring, and replication

**Status**: FROZEN on commit. Amendments append; no line above this one is ever edited.
**Date**: 2026-09-23
**Relationship to earlier documents**: extends `docs/prereg_hj12_dev_20260922.md` (which remains
frozen and whose Gate G1 verdict stands as recorded: **failed**). It does not modify
`docs/prereg_j9_freeze_20260920.md`; the J9 primary metric (`goal_pass_rate`), the 7.00 pp
non-inferiority margin, and TGC-reported-alongside are inherited unchanged.

---

## 1. Why this document exists, and what it may and may not claim

Phase P1 measured quality against prefix depth $m$ for $m \in \{2,4,6\}$, then $\{7,8,9,10,11\}$ after
seeing the first grid. The resulting curve is flat through $m=6$ and rises thereafter. **That shape
was observed before this document was written.** Any test of it on those same episodes is therefore
**exploratory**, and this pre-registration does not launder it into a confirmatory result.

What this document registers is:

1. the **exact test** that will be applied to the shape, fixed before it is run, so the analysis is
   not chosen to flatter the data (§3);
2. the datasets on which that test is **confirmatory** because they do not yet exist (§4);
3. the **repairs** whose outcome could move every number, registered before they are applied (§2);
4. the **tailoring** contrasts, whose data do not yet exist and which are therefore confirmatory (§5).

### 1.1 What is exploratory and what is confirmatory

| analysis | data | status |
|---|---|---|
| shape test on `hj12_prefix_m{2,4,6,7,8,9,10,11}_20260922` | exists, already seen | **exploratory** |
| shape test on the post-repair re-runs (`hj13_prefix_*`) | does not exist | confirmatory for the repair's effect only, since the underlying episodes are re-runs of seen arms |
| shape test on the second executor family (`hj14_*`, §4) | does not exist, different base model | **confirmatory** |
| zero-shot receiver contrast (§5.1) | does not exist | **confirmatory** |
| suffix-adapter contrast (§5.2) | does not exist | **confirmatory** |
| scenario-clustered intervals (§2.2) | recomputation of existing data | sensitivity analysis |

No result from an exploratory row may be described in any write-up as confirming a hypothesis. The
word "confirmatory" is reserved for the three rows marked so above.

---

## 2. Registered repairs (their outcome is not predicted; their existence is registered)

### 2.1 The prefix terminal guard

`run_episode` rebuilds the terminal flag of a replayed prefix
[OBSERVED `src/sidekick/systems/loop.py:582`, `:144-157`] but enters the live loop unconditionally
[OBSERVED `src/sidekick/systems/loop.py:690`]; the only termination check happens after an action has
been taken [OBSERVED `src/sidekick/systems/loop.py:1053`]. Episodes whose source trajectory already
ended therefore gave the executor additional actions and additional step budget: 38 executor actions
across m9's 32 such episodes, 113 across m11's 60.

**Registered change**: a policy field `post_prefix_terminal`, defaulting to `stop`, under which the
live loop does not run when the replayed prefix already terminated. All prefix arms are re-run under
`stop` as `hj13_prefix_m<k>_<date>`.

**Registered consequence, stated before the re-run**: the affected arms' scores are expected to
**fall**, most at large $m$ where the prefix-exhausted population is largest. Specifically we predict
`prefix_m11` will lose more than `prefix_m9`, and that `prefix_m11 − planner_alone` will no longer be
positive. If instead the scores are unchanged, the population was not driving the result and that is
recorded as such.

### 2.2 The resampling unit

The 57 dev tasks are 19 scenarios × 3 variants [OBSERVED `scripts/setup/hj1_gate.py:45-46`]. All
prior intervals cluster on task. Every interval from this document forward is reported **twice**,
clustered on task and on scenario, with the scenario-clustered interval treated as primary wherever
the two disagree about whether an interval excludes zero or clears the margin.

### 2.3 The comparator's call cap

`planner_alone` ran under `max_planner_calls: 25` [OBSERVED `configs/pilot_planner_alone.yaml:25`];
every arm compared against it used 81 [OBSERVED `configs/hj8_fixed_k_3.yaml:39-41`]. Until a re-run
at 81 exists, every non-inferiority statement against `planner_alone` is reported with the phrase
"against the 25-call-capped planner", and a sensitivity analysis excluding reference episodes that
terminated on `limit` is reported beside it.

---

## 3. The registered shape test

Let $q(m)$ be `goal_pass_rate` at prefix depth $m$, over $m \in \{0, 2, 4, 6, 7, 8, 9, 10, 11\}$ where
$m=0$ denotes `sft_plan` (plan only, no replayed actions).

**Primary specification — segmented linear regression with one unknown breakpoint.**
Fit $q(m) = \beta_0 + \beta_1 m + \beta_2 (m - \tau)_+$ with breakpoint $\tau$ estimated by
profiling over integer candidates $\tau \in \{4,6,7,8,9\}$ and selecting the minimiser of residual
sum of squares. Confidence intervals for $\tau$, $\beta_1$ and $\beta_1 + \beta_2$ come from the same
paired percentile bootstrap used throughout the campaign — 10,000 resamples, seed 20260915, resampling
**scenarios** (and, reported alongside, tasks), refitting the whole segmented model within each
resample so the breakpoint's uncertainty is propagated rather than conditioned away.

**Registered hypotheses.**

- **S1 (pre-threshold flatness)**: $\beta_1 = 0$. Rejected only if the interval for $\beta_1$ excludes
  zero.
- **S2 (post-threshold rise)**: $\beta_1 + \beta_2 > 0$, one-sided at the 95% level.
- **S3 (the threshold is real)**: the bootstrap interval for $\tau$ excludes $m \le 4$.

**The shape claim is supported only if S1 is not rejected, S2 holds, and S3 holds.** Any other
combination is reported as "no threshold established".

**Robustness, pre-specified, reported whether or not it agrees**: (a) an isotonic (monotone) fit,
reporting where the fitted function first exceeds the `sft_plan` floor by more than 5 pp; (b) the
same segmented fit on TGC; (c) the same fit on the three populations already defined in
`docs/prereg_hj12_dev_20260922.md` §3.4 and on the pinned key sets produced by `--handoff-keys-from`;
(d) the same fit with $m$ re-expressed as a **percentile of the planner's own step-count
distribution**, so the result is comparable to studies that parameterise the switch point that way.

**Multiplicity**: S1–S3 form one family. The robustness analyses are not corrected and are labelled
descriptive.

**Replicate noise floor**: `prefix_m6` and `prefix_m9` are re-run once more under identical settings
in a single job. The absolute difference between replicates at each $m$ is the noise floor. If the
observed $m6 \rightarrow m9$ rise is not at least twice the larger replicate difference, the shape
claim is withdrawn regardless of S1–S3.

---

## 4. Replication on a second executor family (confirmatory)

The same SFT(b+) recipe is applied to a second open-weight base model (Qwen3-8B; locally cached) and
the full prefix grid is re-run as `hj14_*`. The planner trajectories are already recorded, so this
costs no hosted calls.

**Registered prediction, made before the data exist**: S1, S2 and S3 will all hold on the second
family, and the estimated breakpoint $\tau$ will fall within $\pm 2$ steps of the granite estimate.

**Falsification**: if the second family shows a monotone rise from $m=2$ with no flat segment, or no
rise at all, the "threshold" is a property of one model, not of the allocation problem, and the thesis
will say so in those words.

---

## 5. Tailoring (confirmatory — none of this data exists yet)

### 5.1 The zero-shot receiver

`prefix_m{6,9,11}` are re-run with the **base** executor and no adapter. This reproduces, inside our
setting, the configuration used by prior work on continuing another model's trajectory, where
receivers are prompted zero-shot.

**Registered prediction**: the zero-shot receiver will show a **smaller** rise across $m$ than the
tailored executor; specifically `zero_shot_m11 − zero_shot_m6` will be at least 5 pp lower than
`tailored_m11 − tailored_m6`.

**Falsification**: if the zero-shot receiver shows the same rise, tailoring is not what makes the
action channel work, and the thesis drops "tailored" from its central claim and reports the negative.

### 5.2 The suffix-trained adapter (Claim C3)

Adapter `sft_b_plus_handoff_granite8b`, trained by the existing recipe with hyper-parameters identical
to `iaware` so that training data is the only difference. Data: the 270 recorded training-split
planner trajectories cut at $m \in \{6, 9, 11\}$; suffix assistant turns are supervised targets,
prefix assistant turns are context with labels masked. No handoff note is introduced in this version:
a new token class at serving time requires training and serving to change together, and that is out
of scope here.

**Registered prediction**: the suffix-trained adapter will beat `sft_b_plus_iaware` on
`prefix_m{6,9,11}` by a margin whose scenario-clustered interval excludes zero on at least one $m$,
and will move the estimated breakpoint $\tau$ **down** by at least one step.

**Registered regression check**: `sft_plan` and `executor_alone` are re-run on the new adapter. If
either falls by more than 5 pp, the adapter is reported as a trade rather than an improvement.

---

## 6. Cost axes

Every frontier is reported on three axes, all pre-specified: (a) non-cached hosted planner tokens per
episode (primary, as in HJ-12); (b) provider-priced dollars per episode including cache reads and
writes, under the price card at `configs/cost/prices_2026-09.yaml`, which is frozen on commit of this
document; (c) hosted calls per episode. An arm ordering or non-inferiority verdict that changes
between axes is reported as such and not resolved silently in favour of one axis.

Local GPU cost is **not** included in any axis. The thesis states plainly that the local executor's
compute is real and unpriced here, and that the displacement claim is about hosted spend only.

---

## 7. What would make us abandon the central claim

Stated in advance, so the decision is not made after seeing which way the data fell:

1. The prefix terminal guard (§2.1) removes the rise — i.e. after the repair, `prefix_m9` and
   `prefix_m11` no longer exceed `prefix_m6` by an interval excluding zero.
2. S1 is rejected — the curve was never flat, and "threshold" was an artefact of grid spacing.
3. The replicate noise floor exceeds half the $m6 \rightarrow m9$ rise.
4. The second family shows no threshold **and** the zero-shot receiver shows the same rise as the
   tailored one — the effect would then be neither general nor attributable to tailoring.

If any of 1–3 occurs, the contribution reduces to the priced channel comparison plus the regime
finding, and the thesis is written that way.

---

## 8. Hygiene commitments

- No test-split file is read, loaded or listed under this document. Test evaluation requires a
  separate amendment and the authorisation recorded in `docs/prereg_j9_freeze_20260920.md` §8.1.
- Every number entering a write-up has a row in `docs/claims_ledger.md` naming the artifact and key.
- Arms produced under this document use the `hj13_*` (repaired granite) and `hj14_*` (second family)
  prefixes. Existing `hj12_*` artifacts are never overwritten.
- Exploratory rows in §1.1 are labelled exploratory in every table and figure caption in which they
  appear.

---

## Amendment 2026-09-22 17:25 — complete grid, measured replicate floor, and the three populations the §3 test is run on

This section **appends**. No line above it is edited. The §3 model, breakpoint candidates
$\{4,6,7,8,9\}$, bootstrap (10,000, seed 20260915, scenario-clustered primary with task-clustered
alongside, full refit including $\tau$ inside every resample), hypotheses S1–S3, combined verdict
rule, robustness set (a)–(d), and multiplicity statement are unchanged.

**Grid complete.** Every arm `hj12_prefix_m{2,4,6,7,8,9,10,11}_{20260922,20260923}` has 114/114
episodes. $m=10$ and $m=11$ now enter the registered $m$-set in §3; they are not inferred. The
post-guard silenced series (executor never acted) is 0, 0, 3, 8, 20, 31, 41, 56 at
$m=2,4,6,7,8,9,10,11$. The m=9 count is 31, correcting 30 in an earlier table.

**Primary series.** The §3 test is run on the post-guard `hj12_prefix_m*_20260923` arms as the
primary series, and separately on the pre-guard `hj12_prefix_m*_20260922` arms as the comparison.
The two series are **not pooled**: they are different configurations at $m \ge 6$. $m=0$ is the
existing `sft_plan` arm in both runs.

**Replicate noise floor, now measured.** At $m=2$ and $m=4$ the terminal guard never fires
(`executor.n_calls = 0` in 0 of 114 episodes in both dates). Those two pairs are therefore pure
replicates of one configuration, differing only in sampling (`sampling_seed` null, temperature 0.7).
Observed $|\Delta|$ on `goal_pass_rate`: 3.31 pp at $m=2$ (0.7187 vs 0.6856) and 1.50 pp at $m=4$
(0.7340 vs 0.7190). **3.31 pp** is the observed maximum single-arm replicate deviation at $n=114$
across the two available replicate pairs. It is a floor estimate from a very small sample, not a
variance estimate: it is never called a standard error and is not converted into a CI. The §3
withdrawal condition — if the observed $m6 \rightarrow m9$ rise is not at least twice the larger
replicate difference, the shape claim is withdrawn regardless of S1–S3 — uses this 3.31 pp figure.
The same floor is the comparator for the already-measured advice-channel contrast
(`advise_fixed_k_10 − advise_fixed_k_3` = −0.48 pp).

**§2.1 prediction, per $m$, no curve-level pass/fail.** The registered prediction is that affected
arms' scores are expected to **fall**, most at large $m$; specifically `prefix_m11` will lose more
than `prefix_m9`, and `prefix_m11 − planner_alone` will no longer be positive. Each $m$ is reported
separately with the observed pre/post $\Delta$, the silenced count, and the 3.31 pp floor. This
amendment does not restate or soften that language, and it does not summarise the grid as a single
pass or fail.

**Three populations the §3 test is run on** (all pre-specified here, before this unit's test is
executed):

1. **All-episodes** ($n=114$), crash scores $0.0$ on `goal_pass_rate` and TGC, matching HJ-12 §3.4
   headline.
2. **Pinned to m10's handoff keys**, using `scripts/analysis/j8_frontier.py`'s existing
   `--handoff-keys-from` path: the defining arm's `handoff_occurred is True` key set, applied to
   every other arm (`handoff_flag_keys` / `restrict_to_defining_handoff`; the flag takes effect
   inside the non-inferiority / handoff-only block, not the pairwise `contrasts` block). Expected
   $n=71$.
3. **Pinned to m11's handoff keys**, same mechanism. Expected $n=54$.

The HJ-12 §3.4 **survivors** cut remains robustness (c), reported whether or not it agrees.
Robustness (a)(b)(d) are unchanged.

**Which handoff definition.** Two population definitions differ by two episodes at m10: the
harness `handoff_occurred` flag gives 71; `totals.per_actor.executor.n_calls > 0` gives 73. The
registered pin is `handoff_occurred`. The report names the episodes that differ (SHAPE-04) and does
not silently switch definition.

**Why the pinned sets are in the test.** Pairwise contrasts on the controlled populations are
underpowered (at $n=54$ over 19 scenarios the intervals span roughly $\pm 8$ pp). The segmented
model pools the whole curve. If the bootstrap interval for $\tau$ is so wide that it is
uninformative, that fact is reported as a finding about the design's power.

**Controlled-population curves already seen (exploratory; they do not change the test).** Post-guard
pinned to m11 keys ($n=54$): 0.7119, 0.7001, 0.6967, 0.6839, 0.6801, 0.7167, 0.7487, 0.7558 at
$m=2,4,6,7,8,9,10,11$. Pinned to m10 keys ($n=71$): 0.7145, 0.7052, 0.7053, 0.7139, 0.6991, 0.7282,
0.7694 at $m=2..10$. Seeing them before running §3 is why this run stays **exploratory** on these
arms (§1.1). Confirmatory rows in §1.1 are not opened.

**Percentile remapping (robustness d), specified.** Let $s_i$ be the source planner's executed
action count on episode $i$ (the `n_source_actions` handoff payload, which is the same quantity
prereg HJ-12 §7.3 counted on `hj1b_planner_20260915`). Then $p(m) = 100 \times \#\{i : s_i \le m\}/n$,
the empirical CDF in percent. The §3 fit is repeated with $x = p(m)$ in place of $m$, profiling the
same integer $\tau$ candidates mapped through $p$. Ties in residual sum of squares take the smallest
$\tau$.

**Tie-break, specified.** Among $\tau \in \{4,6,7,8,9\}$, the minimiser of RSS is selected; if two
candidates share the minimum RSS, the smallest $\tau$ is kept. This is the rule that makes a
straight line fail S3 (interval includes 4) rather than invent a threshold.

**Status of results from this test.** Exploratory on `hj12_prefix_*_20260922` and
`hj12_prefix_*_20260923`. Not confirmatory.

## Outcome record — 2026-09-22 19:15 (appended; nothing above this line edited)

**Registered replicate (§3, "Replicate noise floor") executed as specified.** PBS job 25693138,
`ARMS="hj12_prefix_m6 hj12_prefix_m9"`, `DATE=20260923rep`, one job, the same frozen configs and the
same post-guard code as the originals `hj12_prefix_m{6,9}_20260923`.

| m | original | replicate | absolute difference |
|---|---:|---:|---:|
| 6 | 0.7237 | 0.7241 | 0.04 pp |
| 9 | 0.7852 | 0.8033 | 1.82 pp |

Larger replicate difference 1.82 pp; twice it is 3.63 pp; observed m6→m9 rise 6.15 pp (replicate
pair: 7.92 pp). **The withdrawal condition does not fire.** Under the substitute floor introduced by
the 2026-09-22 amendment above (3.31 pp, guard-free m2/m4 pairs) it would have; the registered text
governs, and both floors are reported beside every statement of the shape claim. S1–S3 verdicts are
unchanged: S1 holds 8/8, S2 holds 8/8, S3 fails 8/8 (`hj13_shape_{pre,post}_guard_20260923.report.json`),
so the claim is stated as "flat below a breakpoint and rising above it; the breakpoint is not
located" (claims ledger F1-RESULT-04, NOISE-03). Report:
`campaign/results/hj13_replicate_floor_20260923.report.json`.
