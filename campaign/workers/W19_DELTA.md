# W-19 — Is the frozen δ too conservative for a four-replicate Δ?

**Analysis only. No production code touched. Nothing committed. No planner calls, no GPU jobs.**
Script: `campaign/workers/scratch_W19/analyze_delta.py`. Raw output:
`campaign/workers/scratch_W19/w19_out.txt`. Executed in PBS jobs **25422390.aqua** (syntax
check, failed fast), **25422402.aqua** (full analysis) and **25422408.aqua** (frozen-δ
reproduction). Every number below is `[INFERRED]` (computed by that script from the data
files) unless tagged `[OBSERVED]` to a source line.

## 0. Anchors — the pipeline reproduces the frozen numbers

- Frozen rule reproduced: 75th percentile of `|treated[101] − treated[102]|` over complete
  train points gives **n = 741, p75 = 0.1660** `[INFERRED, job 25422408.aqua]` — matches the
  frozen δ = 0.166 `[OBSERVED brief_W19_delta.md:16]`. So the percentile method and point
  definition agree with how 0.166 was originally derived.
- Four-replicate train labels at δ = 0.166 reproduce the brief exactly: **needed 25 /
  needless 46 / ambiguous 326, f = 0.1159** `[OBSERVED brief_W19_delta.md:32]`, `[INFERRED
  w19_out.txt:67]`.
- Coverage: train 777 points, **397 complete on all four seeds**; dev 382 points, **332
  complete** `[INFERRED w19_out.txt:8,40]`.

## 1. Measured σ (within-condition SD of 4 replicates per complete point)

`[INFERRED w19_out.txt:9–10,41–42]` — sample SD over the 4 treated / 4 untreated replicates.

| | median | IQR | p90 |
|---|---|---|---|
| train treated | 0.000 | (0.000, 0.137) | 0.289 |
| train untreated | 0.000 | (0.000, 0.144) | 0.289 |
| dev treated | 0.000 | (0.000, 0.250) | 0.346 |
| dev untreated | 0.000 | (0.000, 0.250) | 0.314 |

Median 0 is real: scores are mostly 0/1 and replicate perfectly at many points. The noise
lives in the upper tail.

**Observed SD of Δ across replicate subsets** (measured, not theory):

| reps | train SD(Δ) | dev SD(Δ) |
|---|---|---|
| (101,102) | 0.1925 | 0.2174 |
| (103,104) | 0.1789 | 0.2107 |
| all four | **0.1495** | **0.1749** |

`[INFERRED w19_out.txt:19–21,51–53]`. The 2→4 replicate shrinkage is ~0.80, not the naive
1/√2 ≈ 0.71 — consistent with the discrete, skewed score distribution (SD is not a clean
scale parameter here).

## 2. CRN correlation (treated vs untreated at the same branch seed)

`[INFERRED w19_out.txt:11–15,43–47]`

| seed | train r | dev r |
|---|---|---|
| 101 | 0.599 | 0.580 |
| 102 | 0.685 | 0.616 |
| 103 | 0.658 | 0.553 |
| 104 | 0.682 | 0.604 |
| mean | **0.656** | **0.588** |

Substantial positive pairing: Var(Δ) gains a −2ρσ²/n term, so the true noise of the
thresholded statistic is **lower** than any independent-samples estimate. Any δ derived
without CRN is an **upper bound** on the appropriate band — the conservatism direction is
confirmed.

## 3. Derived noise floor for a four-replicate Δ

Null: split the 4 treated (and 4 untreated) replicates into two disjoint pairs, take
`|mean(pair A) − mean(pair B)|`, pool the 3 disjoint pairings × 2 conditions × points.
That is a same-condition difference of two 2-replicate means.

Arithmetic `[INFERRED w19_out.txt:17–18,33–34,49–50]`:
- null statistic: Var = σ²/2 + σ²/2 = σ²/2 → SD = σ/√2
- 4-replicate Δ: Var = σ²/4 + σ²/4 = σ²/2 → SD = σ/√2

**The null is already on exactly the same scale as the estimator being thresholded — no
further √2 adjustment is needed.** (With CRN, real Δ is even less noisy: SD(Δ) ≈
σ·√(2(1−ρ)/4) ≈ 0.41σ at ρ = 0.66, vs 0.71σ for the null — so the derived δ is conservative.)

Result — 75th percentile of the null:

- **train: δ_derived = 0.100** (n = 2382 null draws; p50 = 0.000, p90 = 0.250)
  `[INFERRED w19_out.txt:16]`
- dev: δ_derived = 0.200 (n = 1992; p50 = 0.000, p90 = 0.300) `[INFERRED w19_out.txt:48]`

Train noise is genuinely smaller than dev noise. Since the labels being computed are for
train points, **δ_derived = 0.100 (train) is the headline derived value.** The frozen 0.166
sits above train's floor but below dev's — the frozen δ is conservative on train, not on
dev. Note also that the single-draw |Δ| p75 measured on train at 2 replicates is 0.167

## 4. Label sensitivity (complete four-replicate points)

Train `[INFERRED w19_out.txt:58–71]`:

| δ | needed | needless | ambiguous | f | 1−f |
|---|---|---|---|---|---|
| 0.020 | 89 | 116 | 192 | 0.292 | 0.708 |
| 0.040 | 81 | 104 | 212 | 0.262 | 0.738 |
| 0.060 | 72 | 87 | 238 | 0.219 | 0.781 |
| 0.080 | 63 | 79 | 255 | 0.199 | 0.801 |
| **0.083** | **62** | **78** | **257** | **0.197** | **0.804** |
| 0.100 | 54 | 67 | 276 | 0.169 | 0.831 |
| 0.140 | 32 | 52 | 313 | 0.131 | 0.869 |
| **0.166 (frozen)** | **25** | **46** | **326** | **0.116** | **0.884** |
| 0.180 | 22 | 45 | 330 | 0.113 | 0.887 |
| 0.200 | 18 | 33 | 346 | 0.083 | 0.917 |
| 0.250 | 9 | 20 | 368 | 0.050 | 0.950 |

Dev `[INFERRED w19_out.txt:74–87]`:

| δ | needed | needless | ambiguous | f | 1−f |
|---|---|---|---|---|---|
| **0.083** | **85** | **66** | **181** | **0.199** | **0.801** |
| 0.100 | 72 | 61 | 199 | 0.184 | 0.816 |
| 0.166 (frozen) | 43 | 43 | 246 | 0.130 | 0.870 |
| 0.200 | 36 | 33 | 263 | 0.099 | 0.901 |

## 5. The two numbers that matter (train, derived δ = 0.100)

- **Training-signal count: 54 needed points** (vs 25 at the frozen δ; needless rises
  46 → 67; ambiguous falls 326 → 276). `[INFERRED w19_out.txt:63,67]`

## 6. Stability check (labels flipping between disjoint 2-replicate halves)

`[INFERRED w19_out.txt:91–97]`

| split | δ = 0.083 | δ = 0.100 (derived, train) | δ = 0.166 (frozen) |
|---|---|---|---|
| train | 0.6574 | **0.6851** | 0.7229 |
| dev | 0.6205 | 0.6355 | 0.6355 |

Direction is as predicted: halving δ costs agreement on train (0.7229 → 0.6851, −3.8 pts).
But: **the reference 0.8388 agreement at δ = 0.166 does not reproduce** — we measure 0.7229
on train (and 0.6355 on dev) with this exact label rule and point definition
`[INFERRED w19_out.txt:93,96]`. The 0.8388 figure was presumably computed on a different
population or pairing scheme `[INFERRED]`; anyone weighing the stability argument should
re-derive it under the same protocol before using it. At our measured baseline, δ = 0.100
loses only ~4 points of half-agreement while roughly doubling the `needed` count.

## 7. Verdict (neutral)

1. The theory in the brief is directionally correct: the frozen δ was calibrated to a
   2-replicate single-draw difference (reproduced: p75 = 0.166 exactly), which is √2×
   noisier than a 4-replicate Δ, and CRN (r ≈ 0.59–0.68) makes the Δ even less noisy still.
2. Applying the same rule to the estimator actually being thresholded gives **δ = 0.100
   (train)** — 0.066 lower than frozen — with no further adjustment needed.
3. That δ is a **conservative upper bound** (same-condition null ignores the CRN reduction).
4. Labels at δ = 0.100: needed 54, f = 0.169. Halving the ambiguity zone costs ~4 points of
   half-agreement against a measured 0.7229 baseline.
5. Counterweight: dev noise is larger (derived 0.200); a dev-calibrated floor would
   *shrink* positives. The train/dev discrepancy in the noise floor itself (0.100 vs 0.200)
   is the strongest argument that any amendment decision needs a decision about which
   split defines the rule.
6. Per the brief: **no recommendation is made here to change the pre-registration.** This
   document is only the evidence for the user's decision.

## Caveats / notes

- The score distribution is discrete (0/1-heavy); SD and percentile-based bands are coarse
  there — medians of 0 are genuine, not bugs.
- The main script printed the TRAIN report block twice (identical output both times; the
  driver had a leftover duplicate call). Outputs were byte-identical, so all numbers above
  are unaffected `[OBSERVED w19_out.txt:7–21 vs 23–37]`.
- `branch_gpr` null rows: 1357 in train, 141 in dev; dropped only from incomplete points,
  never deleted `[INFERRED w19_out.txt:8,40]`.

- **Headline: f = 0.169, 1 − f = 0.831** (vs f = 0.116, 1 − f = 0.884 at the frozen δ).
  `[INFERRED w19_out.txt:63,67]`

If instead the dev-calibrated derived δ = 0.200 were used on train: needed 18, f = 0.083 —
**fewer positives than the frozen δ**. Per the brief's rule, stated with equal prominence:
a defensible noise-floor derivation does not *automatically* buy positives; it depends on
which split calibrates the floor. `[INFERRED w19_out.txt:69]`

`[INFERRED w19_out.txt:19]` — exactly the frozen δ — confirming that the frozen δ was
calibrated to a **2-replicate single-draw** yardstick, which is √2× noisier than the
4-replicate Δ.

