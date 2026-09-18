# A9 / A9b — J7 verifier threshold against the attenuation ceiling

Unit: A9b (U-J7 re-issue). Analysis only. Zero planner calls. No GPU. No commit.
No edits to `src/`, `configs/`, `scripts/`, `campaign/RUNS.md`, `docs/PLAN.md`,
`docs/HEAVY_JOBS.md`, or `docs/prereg_v1.md`. Proposed prereg wording is in §5
of this report only.

Compute: PBS `25454021.aqua` on `cpu1n040`, exit 0, walltime 5s, ngpus=0
[OBSERVED /home/n12194778/.hpc-spool/20260919-021228-2979767.out:23-56].
Script: `campaign/workers/scratch_A9b/a9_ceiling.py`.
Raw JSON: `campaign/workers/scratch_A9b/a9_ceiling_out.json`.
Interpreter: `/scratch/n12194778/sidekick/env/bin/python`, `PYTHONPATH=src:.`.

A first job (`25453926.aqua`) crashed after loading because two float spellings
of the frozen band (`0.166` and `0.16599999999999993`) were treated as distinct;
that was a script error, not an analysis result. Rounded to 6 decimals they are
one value, 0.166 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:8-15].

Every factual claim is `[OBSERVED <path>:<line>]` or `[INFERRED]`.

---

## Headline (so a reviewer does not have to recompute)

J7's fitted dev AUROC is **0.5916711736073553** on n = 86
[OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:20]
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:49-61].

The √0.45 ≈ 0.67 figure in the A9 brief is a **Pearson correlation**, not an
AUROC. Under the Gaussian true-score model that justifies √ρ as corr(θ, Δ),
a perfect predictor of the latent effect scores **AUROC 0.962** against the
same two-sided band labels [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:367-379].
A split-half empirical proxy on J7's actual needed/needless subset scores
**mean AUROC 0.9285** (three 2-vs-2 splits: 0.839, 0.969, 0.978)
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:228-230].
**0.65 and 0.70 are both below that ceiling.** The threshold was not unmeetable
by construction. 0.59 is a genuinely weak ranking of these labels by these
features, not a noise-floor miss. It is also a thin estimate: the 95%
point-bootstrap CI is **[0.4677, 0.7111]** and includes 0.50, 0.65, and 0.70
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:68-73, 463-467].

This unit does **not** pick between the document's 0.70 and the W-16/A9
operational 0.65. Both were missed as point estimates. The proposed change is
disclosure plus floor/ceiling reporting, not a lowered absolute bar. See §5.

---

## 0. Ledger vs artifact vs briefs — discrepancies, not averages

### 0.1 The fitted number

| source | dev AUROC | notes |
|---|---|---|
| artifact `metrics.json` | **0.5916711736073553** | `auroc_all_states` = `auroc_tick_states` [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:20-21] |
| this job, scoring the saved weights on reconstructed states | **0.5916711736073553** | bit-identical, `dev_match_artifact: true` [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:57-65] |
| W-16 report | 0.5917 (0.591671) | same artifact [OBSERVED campaign/workers/W16_J7_FIT.md:51] |
| W-17 / FOLLOWUPS | 0.5916711736073553 | AUROC invariant to the temperature fix [OBSERVED docs/FOLLOWUPS.md:806] |
| A9 brief paraphrase | "0.59" | [OBSERVED campaign/workers/brief_A9_threshold_respec.md:15] |

They agree. Nothing is averaged. The analysis uses 0.5916711736073553.

Dev n = 86 (43 needed / 43 needless); train n = 71 (25 needed / 46 needless);
joins dropped 0 [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:4-51]
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:17-47].
Temperature after W-17 is 11.036… (flattening), not the broken-Newton 0.129
still sitting in the W-16 narrative [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:28]
[OBSERVED campaign/workers/W16_J7_FIT.md:72]. AUROC is invariant to that fix.

### 0.2 The pre-registered threshold is not a single number

| source | stated AUROC threshold |
|---|---|
| `docs/prereg_v1.md` secondary metric 6 | **AUROC ≥ 0.70** [OBSERVED docs/prereg_v1.md:146-147] |
| A9 brief | **dev AUROC ≥ 0.65** [OBSERVED campaign/workers/brief_A9_threshold_respec.md:14] |
| W-16 brief / W-16 report | 0.65 [OBSERVED campaign/workers/brief_W16_j7fit.md:44] [OBSERVED campaign/workers/W16_J7_FIT.md:66] |
| `docs/PLAN.md` H3 | qualitative; **no numeric AUROC** [OBSERVED docs/PLAN.md:249-250] |

0.65 does **not** appear in `docs/prereg_v1.md`. This unit does not resolve
that ambiguity. The fitted 0.5917 misses **either** bar as a point estimate.
H3 in the prereg body is also qualitative ("high AUROC") rather than 0.70
[OBSERVED docs/prereg_v1.md:50-51].

### 0.3 Reliability figures the √0.45 heuristic is built on

These are reliabilities of the **continuous** 4-replicate mean Δ on all
complete points (including ambiguous), not of the binary needed/needless
labels on the J7 fit subset:

| quantity | predicted from 2 seeds | measured at 4 seeds | this job (dev, 332 complete) |
|---|---:|---:|---:|
| mean single-replicate Pearson r | 0.164 | **0.1697** | (not re-estimated as a single-seed mean) |
| reliability of the 2-replicate mean | 0.282 | **0.2902** | — |
| reliability of the 4-replicate mean | 0.440 | **0.4504** | **0.4504198** |

Ledger: [OBSERVED campaign/RUNS.md:1798-1805].
Recomputed as the mean of three 2-vs-2 Spearman-Brown values 0.50264, 0.30744,
0.54118 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:165, 188, 211, 224].
Those three splits match RUNS.md's 0.5026, 0.3074, 0.5412
[OBSERVED campaign/RUNS.md:1805]. The 0.4504 figure is a central estimate with
that spread; it is not tight.

Two-seed vs four-seed **binary** labels on the same 332 points: agreement
276/332, **zero** needed ↔ needless flips [OBSERVED campaign/RUNS.md:1809-1813]
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:234-239]. This job
also counted 34 two-seed-polar → four-seed-ambiguous and 22 the other way
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:237-238]. Noise on
this population is band-crossing, not polarity reversal of the J7 classes.

J7 drops incomplete and ambiguous rows and fits only needed vs needless
[OBSERVED scripts/setup/fit_feature_verifier.py:213-235]
[OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:35-51].

---

## 1. Ceiling derivation — the √0.45 ≈ 0.67 heuristic is the wrong scale

### 1.1 What the heuristic actually is

Classical test theory: if an observed measure X has reliability
ρ = Var(T) / Var(X), a perfect predictor of the true score T correlates with
X at corr(T, X) = √ρ. With ρ = 0.4504, √ρ = 0.6711
[INFERRED, √0.4504; OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:369].
The A9 brief treated that **correlation** as if it were an **AUROC** ceiling
[OBSERVED campaign/workers/brief_A9_threshold_respec.md:19-21].
AUROC is P(score_pos > score_neg), a Mann–Whitney probability, not a Pearson r.

### 1.2 Measurement model (assumptions, not silent)

1. **What ρ measures.** RUNS.md ρ is Pearson reliability of the continuous
   4-replicate mean Δ on all complete points, including ambiguous
   [OBSERVED campaign/RUNS.md:1796-1805]. J7 AUROC is computed on binary
   needed/needless after dropping |Δ| ≤ δ, δ = 0.166
   [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:20-51]
   [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:15].
   These are not the same estimand.
2. **Gaussian true-score model.** Δ = θ + ε, θ ⊥ ε, Var(θ) = ρ Var(Δ), so
   corr(θ, Δ) = √ρ by construction. Labels Y = 1[Δ > δ], 0[Δ < −δ], else
   dropped. A perfect predictor of the latent effect scores with **θ**, not
   with Δ. This is a model. [INFERRED]
3. **RCN formula, for contrast only.** If a latent *binary* Y* of prevalence
   0.5 is flipped independently with rate ε, a perfect predictor of Y* has
   AUROC ceiling 1 − ε = 0.5(1 + √r) when r = (1 − 2ε)² is the replicate
   correlation of the *binary* labels. Plugging the *continuous* ρ_Δ = 0.45
   into that formula is a category error. [INFERRED]
4. **Tautology.** AUROC of the 4-replicate Δ itself against J7's binary labels
   is 1.0 by construction, because those labels *are* a threshold of that Δ
   (dev n = 86, train n = 71)
   [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:231-233, 326-328].
   That is not a ceiling for a state-feature predictor. It is a sanity check
   that the label definition was implemented as written.

### 1.3 The same ρ = 0.4504 on four scales

| translation | formula | value | what it is |
|---|---|---:|---|
| brief heuristic | √ρ | **0.6711** | Pearson corr(θ, Δ) on *all* points, **not** AUROC [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:399] |
| RCN binary ceiling, mis-plugging ρ_Δ | 0.5(1 + √ρ) | **0.8356** | would be an AUROC ceiling only if ρ were binary-label reliability at p = 0.5 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:400] |
| point-biserial √ρ → binormal AUROC | Φ(d'/√2) with r_pb = √ρ, p = 0.5 | **0.8998** | treats 0.671 as corr(score, *binary* Y), which it is not [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:401] |
| Gaussian MC: AUROC of θ vs band-thresholded Δ | 200,000 draws, μ = 0.00970, σ = 0.1749, δ = 0.166, ρ = 0.4504 | **0.9622** | the AUROC that belongs to this measurement model [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:367-379, 402] |
| tautological Δ vs J7 labels | AUROC(Δ, 1[Δ>δ]) on \|Δ\|>δ | **1.0** | label definition, not a state-predictor ceiling [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:231] |

MC sanity: corr(θ, Δ) on all draws was 0.6709 against constructed √ρ = 0.6711
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:369, 377]. The
selection into the tails raises corr(θ, Δ) on the kept set to 0.8143, which
is why the AUROC (0.962) is much higher than √ρ (0.671)
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:378-379].
J7 *only evaluates on those tails*. Using √ρ as an AUROC ceiling ignores
exactly the selection the labels perform.

At the single-replicate reliability 0.1697 the same MC still gives AUROC
0.8238, not 0.412 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:337-350].
Even that weaker reliability does not put 0.65 above the AUROC ceiling.

**The 0.67 figure is therefore wrong as a bound on J7 AUROC.** A threshold of
0.65 or 0.70 is not “at or above the measurable ceiling” because √0.45 ≈ 0.67.
That sentence confuses two scales. The honest question is empirical: what
AUROC does a split-half (or perfect-θ) predictor of the latent effect
achieve against the binary labels J7 is scored on, and what AUROC do these
*features* support.

---

## 2. Empirical floor and ceiling on J7's labels

A7's precedent is to report a feature-blind floor *and* a capacity ceiling,
not 0.50 alone [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:71-83]
[OBSERVED artifacts/verifiers/value_fn_20260919/metrics.json:141-149].
Copied here, with the difference that J7 labels are needed/needless at timer
ticks, not back-propagated episode outcomes.

### 2.1 Feature-blind floors

| floor | dev AUROC | what it is |
|---|---:|---|
| constant / train class prior | **0.5000** | chance for a rank statistic with both classes present [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:92, 106] |
| train per-step-index prior | **0.5070** | A7 analogue; 7 step keys on train n = 71 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:93-97] |
| train per-`n_interventions` prior | **0.5070** | identical to step prior: on k = 5 ticks the two keys are collinear [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:98-102] |

J7's step-prior floor is chance. That is unlike A7, where the step-prior
floor was 0.6245 because episode-success labels are strongly determined by
how far the episode got [OBSERVED artifacts/verifiers/value_fn_20260919/metrics.json:149].
J7's `needed` label is not a back-propagated outcome, so “which tick is
this” is not a free 0.62. [INFERRED]

Raw monotonic scores on *dev* (not a prior, not feature-blind in the A7
sense — they are single frozen features):

| univariate score | dev AUROC |
|---|---:|
| `step` | **0.6001** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:103] |
| `n_interventions` | **0.6001** (same ranking) [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:104] |
| `transcript_chars` | **0.6095** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:105] |
| fitted `feature_lr_v1` | **0.5917** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:57] |

The fitted head **does not beat a single frozen counter** on this 86-point
dev split. The gap 0.610 − 0.592 is well inside sampling noise (see §2.4).
The reading is A7-like on the feature side: the linear combination of
`feature_lr_v1` is not extracting task-state signal beyond the obvious
counters. [INFERRED]

### 2.2 Feature-capacity k-NN proxy — analogue failed, stated as such

A7's k-NN ceiling used 12,383 train steps [OBSERVED artifacts/verifiers/value_fn_20260919/metrics.json:113].
J7 has 71 train points in 13-D. The same proxy is not a ceiling here:

| k-NN | AUROC |
|---|---:|
| train→dev, k = 3, cross-task | **0.4908** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:109-116] |
| train→dev, k = 5 | **0.4473** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:117-126] |
| train→dev, k = 9 | **0.5403** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:127-135] |
| pooled leave-one-task-out k = 5 (n = 157; sensitivity, circular-ish) | **0.5744** [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:137-145] |

k-NN sits at or below chance and **below** the LR. It is not an upper bound
on what these features can do; it is an underpowered neighbour vote. This
unit does **not** use it as the J7 ceiling. The honest feature-side pair is
the 0.50/0.507 floor and the ~0.60 univariate counters / 0.59 LR cluster.
[INFERRED]

### 2.3 Label-noise ceiling (the quantity the brief actually asked for)

Independent 2-vs-2 split of seeds {101,102,103,104}. Score = half-mean Δ_A.
Labels = needed/needless cut from independent half-mean Δ_B at δ = 0.166.
Because Δ_A is itself noisy, this AUROC is a **lower** bound on the AUROC of
a perfect θ-predictor. [INFERRED]

**On every 4-complete point that is polar on half B** (not J7's subset):

| split (A vs B) | AUROC | n_polar_B | polar-agreement when both halves polar |
|---|---:|---:|---:|
| {101,102} vs {103,104} | 0.6803 | 115 | 39/53 = 0.736 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:154-176] |
| {101,103} vs {102,104} | 0.6547 | 91 | 31/48 = 0.646 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:177-199] |
| {101,104} vs {102,103} | 0.7860 | 104 | 44/56 = 0.786 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:200-222] |
| **mean (range)** | **0.7070 [0.6547, 0.7860]** | | [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:225-227] |

This set includes 2-rep tail points that the 4-rep mean later calls
ambiguous. It is *not* J7's evaluation set. 0.65 sits at the bottom of this
three-split range; 0.70 sits inside it. That is the most conservative
empirical proxy, and even here 0.65 is a high bar against a *noisy* score,
not proof the labels contain no 0.65 of information.

**On J7's actual subset** (4-rep complete and non-ambiguous, then labelled
by half B when half B is also polar):

| split | AUROC | n scored (of 86) |
|---|---:|---:|
| {101,102} vs {103,104} | 0.9688 | 61 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:173-175] |
| {101,103} vs {102,104} | 0.8391 | 59 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:196-198] |
| {101,104} vs {102,103} | 0.9776 | 68 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:219-221] |
| **mean (range)** | **0.9285 [0.8391, 0.9776]** | [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:228-230] |

The weakest split is the same one whose continuous reliability was the
outlier 0.307 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:188]
[OBSERVED campaign/RUNS.md:1805]. Even that split's AUROC on the J7 tail is
0.839, above 0.70. Train-side J7-kept split-half mean is 0.9648
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:323].

Gaussian perfect-θ AUROC against the same band, using the empirical (μ, σ)
of the 332 complete dev Δs, is 0.9622 at ρ = 0.4504
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:151-152, 367-379].
That sits inside the J7-kept split-half range. The two independent routes
(empirical split-half on the eval subset, parametric perfect-θ) agree that
the label-noise ceiling on J7's labels is about **0.93–0.96**, not 0.67.

### 2.4 Interval on the fitted AUROC

10,000 bootstrap resamples, seed 20260918, same as W-16
[OBSERVED campaign/workers/W16_J7_FIT.md:61]
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:68-89].

| | AUROC | 95% CI | boot mean | boot sd |
|---|---:|---|---:|---:|
| point-level (W-16 analogue) | 0.5917 | **[0.4677, 0.7111]** | 0.5933 | 0.0624 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:68-77] |
| task-level (37 tasks; A7 analogue) | 0.5917 | **[0.4576, 0.7416]** | 0.5965 | 0.0724 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:79-90] |

W-16 quoted [0.4677, 0.7113] as `[INFERRED]`
[OBSERVED campaign/workers/W16_J7_FIT.md:63]. This job's point-level interval
matches the low end to four decimals and differs by 0.0002 at the high end
(percentile interpolation). They are not averaged; this report uses
[0.4677, 0.7111]. Both intervals include 0.50, 0.65, and 0.70
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:463-467].
A point estimate of 0.5917 does not statistically reject chance, 0.65, or
0.70. That is the thin-fit warning W-16 already recorded
[OBSERVED campaign/workers/W16_J7_FIT.md:38-40, 66].

---

## 3. J7 restated against floor and ceiling

Let A = 0.5916711736073553
[OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:405].

**Against label noise** (the brief's question):

| | ceiling | (A − 0.5) / (ceiling − 0.5) | mapping the point-boot CI through a *fixed* ceiling [INFERRED] |
|---|---:|---:|---|
| J7-kept split-half mean 0.9285 | 0.9285 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:441-448] | **0.214** | [−0.075, 0.493] |
| Gaussian θ at ρ = 0.4504 | 0.9622 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:450-457] | **0.198** | [−0.070, 0.457] |
| all-polar-B split-half mean 0.7070 (not J7's subset) | 0.7070 [OBSERVED campaign/workers/scratch_A9b/a9_ceiling_out.json:414-421] | **0.443** | [−0.156, 1.020] |

The CI-mapped fractions treat the ceiling as fixed, so they understate
uncertainty in the denominator. The three-split range of the J7-kept ceiling
is already [0.839, 0.978]; using 0.839 instead of 0.9285 raises the point
fraction only to (0.592 − 0.5) / (0.839 − 0.5) = 0.271 [INFERRED]. It does
not move the reading.

**Against features:**

| | value |
|---|---|
| floor (constant) | 0.500 |
| floor (step prior) | 0.507 |
| fitted LR | 0.592 |
| univariate `transcript_chars` | 0.610 |
| k-NN k = 5 | 0.447 (not a ceiling; discarded) |

(A − 0.5) / (0.610 − 0.5) = 0.83 if one treats the best univariate as a
feature ceiling [INFERRED]. That comparison is descriptive, not a bound:
on n = 86, 0.592 and 0.610 are the same number. The LR is in the mush with
its own features, far below the label ceiling.

**Against the named thresholds, as fractions of the J7-kept label ceiling
0.9285** [INFERRED]:

- 0.65 sits at (0.65 − 0.5) / 0.4285 = **0.350** of the chance-to-ceiling gap.
- 0.70 sits at **0.467** of that gap.
- 0.59 sits at **0.214** of that gap.

0.65 is a third of the way from chance to what the labels contain. It is not
near-perfection on this scale.

---

## 4. Plain-language corrected reading (one paragraph)

J7's 0.59 is a genuinely weak ranking of the intervention-needed labels by
the frozen nine-counter state, not a near-ceiling score and not a mid-range
success against an unmeetable bar. The labels J7 is scored on are the stable
tails of Δ: an independent half of the branch replicates ranks those tails
at about 0.93 AUROC, and a Gaussian model of the same reliability puts a
perfect latent-effect predictor at 0.96, so both 0.65 and the document's
0.70 were reachable in label space. What failed is the estimator. On 86
dev points the fitted logistic does not beat scoring by transcript length
or step index (~0.60), sits 0.09 above chance, and a 95% interval still
covers 0.50 through 0.70. The A7-style pairing of floor and ceiling is what
makes that readable: against a ~0.50 feature-blind floor this is a small
bump with a CI that includes the floor; against a ~0.93 label-noise ceiling
it is about one-fifth of the available gap. Lowering 0.65 after seeing 0.59
would convert that miss into a pass by moving the goal. The miss of the
written 0.70 (and of the operational 0.65) should stay a miss; the
attenuation analysis explains why 0.59 is weak, not why 0.65 was impossible.

---

## 5. Proposed replacement wording for `docs/prereg_v1.md`

**Proposal for review. Not applied.** This unit does not edit
`docs/prereg_v1.md`. It also does not choose 0.65 vs 0.70; the document
currently says 0.70 and the J7 operational briefs said 0.65.

The only honest change is one that a reviewer can see was written **after**
seeing 0.5917, that records the miss, and that does **not** lower the
absolute bar to a number the fitted verifier would pass. A new numeric
fraction-of-ceiling cut chosen so that 0.21 fails-or-passes to taste would
be the same offence with extra arithmetic. This proposal therefore **adds a
reporting rule** that could have been written before J7, and **keeps the
original absolute threshold as a recorded miss**.

Proposed insertion after secondary metric 6 (`docs/prereg_v1.md` around
lines 146–147), marked as a post-result amendment:

---

> **Amendment 2026-09-19 (post-result, J7) — verifier discrimination,
> attenuation, and the original threshold.**
>
> Secondary metric 6 originally stated: “Discrimination AUROC ≥ 0.70 …
> evaluated against dev counterfactual branch labels.” Independently, the
> J7 fit brief (W-16) and the A9 analysis brief used an operational figure
> of 0.65 that does not appear in this document. This amendment does not
> choose between those two numbers.
>
> The fitted `feature_lr_v1` verifier, scored on the J6 four-replicate
> needed/needless labels (ambiguous excluded), reached dev AUROC
> 0.5916711736073553 (n = 86; 43/43; 95% point-bootstrap CI [0.4677, 0.7111];
> 95% task-bootstrap CI [0.4576, 0.7416]). That point estimate misses both
> 0.65 and 0.70. This paragraph is written with knowledge of that result.
>
> **What is not being changed.** The original absolute threshold is not
> lowered to a number the fitted verifier would pass. A post-hoc drop from
> 0.70 (or 0.65) to ≤ 0.59 would make the pre-registration ornamental. The
> miss is recorded.
>
> **Why an attenuation note is added anyway.** After J6 it was known that
> the 4-replicate mean Δ has reliability ≈ 0.45 on all complete points, and
> it was conjectured that √0.45 ≈ 0.67 was an AUROC ceiling that made 0.65
> unmeetable. That translation is a correlation-scale heuristic; AUROC is
> not a correlation. On the needed/needless tails that J7 actually scores,
> a 2-vs-2 split-half of Δ reaches mean AUROC 0.93 (range 0.84–0.98) and a
> Gaussian true-score model at ρ = 0.45 reaches 0.96. Label noise does not
> make 0.65 or 0.70 unmeetable. The 0.59 is a weak state-feature ranking
> (the fitted head does not beat univariate `transcript_chars` / `step` on
> this split; the 95% CI includes 0.50).
>
> **Reporting rule that could have been written before seeing J7, and is
> falsifiable as a description of the measurement.** Every verifier AUROC
> reported against J6 labels is to be published with three companions,
> computed from the same rows without reference to the fitted head's
> pass/fail:
> 1. *Floor* — AUROC of a constant score (0.50) and of the train
>    per-step-index class prior applied to dev.
> 2. *Label-noise ceiling proxy* — mean AUROC, over the three 2-vs-2
>    partitions of branch seeds {101,102,103,104}, of half-mean Δ predicting
>    binary needed/needless labels cut from the complementary half at the
>    frozen δ, restricted to the evaluation subset (complete,
>    non-ambiguous under the four-replicate mean). This is a proxy, not a
>    mathematical bound; the three split values are published as a range.
> 3. *Interval* — a bootstrap CI for the fitted AUROC (task-level when
>    multiple ticks share a task).
>
> Under that reporting rule, J7 reads: AUROC 0.59 [0.47, 0.71] against floor
> 0.50 / 0.51 and label-noise ceiling 0.93 [0.84, 0.98], i.e. about 0.21 of
> the chance-to-ceiling gap, with a CI that includes the floor. That is a
> miss of the original 0.70, not a near-ceiling pass.

---

## 6. What this does *not* license

- It does not license treating 0.59 as a pass.
- It does not license a new absolute threshold of 0.55, 0.58, or “0.80 × 0.67”.
- It does not license refitting the verifier or adding features under the
  same run prefix [OBSERVED AGENTS.md experiment-hygiene: frozen means frozen].
- It does not resolve whether the written original is 0.70 or 0.65; it
  reports both.
- k-NN on n = 71 is not evidence that the features have no capacity; it is
  evidence that this proxy is the wrong tool at this n. The univariate
  counters already show that whatever ranking exists is small.

---

## 7. Job output (verbatim)

First attempt, `25453926.aqua`, traceback only (float band). Second attempt,
`25454021.aqua`, full stdout [OBSERVED /home/n12194778/.hpc-spool/20260919-021228-2979767.out:1-21]:

```
START a9_ceiling
executable /scratch/n12194778/sidekick/env/bin/python
argv ['campaign/workers/scratch_A9b/a9_ceiling.py']
loading metrics/weights/branches
kept/joined 71 71 86 86
reproduced dev AUROC 0.5916711736073553 artifact 0.5916711736073553 match True
bootstrap point {'auroc': 0.5916711736073553, 'ci_low': 0.46773105090186856, 'ci_high': 0.711114922813036, 'boot_mean': 0.5932558982093952, 'boot_sd': 0.062441913555735994, 'n_boot': 10000, 'n_valid': 10000, 'n_skipped_single_class': 0, 'seed': 20260918}
bootstrap task {'auroc': 0.5916711736073553, 'ci_low': 0.4575723661584317, 'ci_high': 0.7415833256343927, 'boot_mean': 0.5964529648969108, 'boot_sd': 0.0723699066610436, 'n_boot': 10000, 'n_valid': 10000, 'n_skipped_single_class': 0, 'seed': 20260918}
floors {"constant_0_5": 0.5, "step_prior": {"auroc": 0.5070308274743104, "n_keys_train": 7, "global_prior": 0.352112676056338}, "n_interventions_prior": {"auroc": 0.5070308274743104, "n_keys_train": 7, "global_prior": 0.352112676056338}, "univariate_step": 0.6000540832882639, "univariate_n_interventions": 0.6000540832882639, "univariate_transcript_chars": 0.6095186587344511, "train_class_prior_constant_score": 0.5}
knn {"k3": {"k": 3, "n_refs": 71, "n_pos_ref": 25, "n_neg_ref": 46, "n_scored": 86, "n_short_neighbourhood": 0, "auroc": 0.4908058409951325}, "k5": {"k": 5, "n_refs": 71, "n_pos_ref": 25, "n_neg_ref": 46, "n_scored": 86, "n_short_neighbourhood": 0, "auroc": 0.4472687939426717}, "k9": {"k": 9, "n_refs": 71, "n_pos_ref": 25, "n_neg_ref": 46, "n_scored": 86, "n_short_neighbourhood": 0, "auroc": 0.5402920497566251}}
knn loto {'k': 5, 'n_refs': 157, 'n_pos_ref': 68, 'n_neg_ref': 89, 'n_scored': 157, 'n_short_neighbourhood': 0, 'auroc': 0.574438202247191}
label_noise_dev mean SB 0.4504197985363601 mean split-half AUROC polar 0.7070171984934803 j7 kept 0.9285097476728529
mc single_rep_ledger 0.8237914827944445 sqrt_rho 0.4119465984809196
mc two_rep_ledger 0.9015438842983791 sqrt_rho 0.5387021440462253
mc four_rep_ledger 0.9621692017084679 sqrt_rho 0.6711184694225008
mc four_rep_recomputed 0.9621700919119132 sqrt_rho 0.671133219663846
```

PBS: `Exit_status = 0`, `resources_used.walltime = 00:00:05`, `ngpus=0`
[OBSERVED /home/n12194778/.hpc-spool/20260919-021228-2979767.out:32, 55].
No verifier artifact was written. Nothing under `/scratch/.../results/` was
modified. `docs/prereg_v1.md` was not edited.
