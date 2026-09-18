# W-24 — paired sign-flip permutation null for `f` and oracle-gain statistics

**Analysis only. No production code modified. Nothing committed. Zero live `codex` / planner calls. No GPU jobs.**

Script: `campaign/workers/scratch_W24/permnull.py`  
Raw verbatim output: `campaign/workers/scratch_W24/w24_out.txt`  
PBS job: **25443463.aqua** on `cpu1n040`, exit 0, walltime 5s, ngpus=0 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:1]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:181-192]`  
Permutation seed: **20260918**; **N_PERM = 10,000** `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:6-7]`

Every number below is tagged `[OBSERVED <path>:<line>]` to that raw log, or `[INFERRED]` if it is a restatement rather than a printed field.

---

## 0. Contract, population, and identity

### Null (not a pooled reshuffle)

For each complete point, and independently for each branch seed `s`, `treated[s]` was swapped with `untreated[s]` with probability 0.5. Δ, labels, and every statistic were then recomputed. This is equivalent to multiplying the per-seed difference by ±1. Pairing is preserved; scores are not pooled across seeds or points `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:11-12]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:46]`.

Loading, completeness, and the contestable definition are copied from W-20 (`load`, `complete`, `SEEDS=(101,102,103,104)`). Contestable = non-ceiling and non-floor on **observed** means (`mean(untreated) >= 1.0` ceiling; `mean(untreated) <= 0` and `mean(treated) <= 0` floor). That mask is **fixed** from the observed data and is **not** re-derived after each permutation. Contestable results are a **post-hoc subset** `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:13]`.

One-sided p = `n(perm >= observed) / 10000`. Two-sided p for `needed − needless` = `n(|perm| >= |observed|) / 10000`. Null 2.5th / 97.5th = `numpy.percentile` linear `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:10]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:14-15]`.

`f` = needed / n. The needless count is reported separately and is never called `f`.

### Replicate seeds actually present

Both files, both conditions, contain exactly the four branch seeds **101, 102, 103, 104** `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:23-24]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:102-103]`. Completeness therefore matches W-20: a point is complete when all four seeds are present with non-null `branch_gpr` for both conditions.

| split | rows | null gpr | total points | complete | incomplete | ceiling | floor | contestable (post-hoc) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 6216 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:22]` | 1357 | 777 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:26]` | 397 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:27]` | 380 | 131 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:34]` | 3 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:35]` | 263 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:36]` |
| dev | 3056 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:101]` | 141 | 382 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:105]` | 332 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:106]` | 50 | 68 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:113]` | 0 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:114]` | 264 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:115]` |

Pearson r(treated, untreated) over (point, seed) pairs on complete points: train **0.6552847123** (n_pairs=1588) `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:30-31]`; dev **0.5881005416** (n_pairs=1328) `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:109-110]`.

### Identity `mean(treated) + mean(harm) = mean(untreated) + mean(help)`

Holds on every printed subset (abs diff ≤ 3.331e-16 < 1e-12):

- train all-complete: 0.8121977329974813 = 0.8121977329974810, abs_diff=3.331e-16, holds=True `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:38-41]`
- train contestable: abs_diff=1.110e-16, holds=True `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:74]`
- dev all-complete: abs_diff=1.110e-16, holds=True `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:117-120]`
- dev contestable: abs_diff=1.110e-16, holds=True `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:153]`

---

## 1. Train, all-complete (n = 397)

### δ = 0.166 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:49-59]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 25 (25/397 = 0.0629722922) | 26.9653 / 0.06792267003 | 19 / 0.04785894207 | 36 / 0.09068010076 | 0.712400 (7124/10000) |
| `needless` count | 46 (46/397) | 26.947 | 19 | 36 | 0.000000 (0/10000) |
| mean Δ | −0.0143929471 | 9.444937028e-05 | −0.01162361461 | 0.01179480479 | 0.992600 (9926/10000) |
| mean `help` (oracle vs never) | 0.03410075567 | 0.03317165951 | 0.02676120907 | 0.0398476228 | 0.384600 (3846/10000) |
| mean `harm` (oracle vs always) | 0.04849370277 | 0.03307721014 | 0.02661437343 | 0.03986911209 | 0.000000 (0/10000) |

Plain interval statements: observed `needed`/`f` **falls inside** its null interval. Observed `needless` **falls above** its null interval (46 > 36). Observed mean Δ **falls below** its null interval (−0.01439 < −0.01162). Observed mean `help` **falls inside** its null interval. Observed mean `harm` **falls above** its null interval.

### δ = 0.100 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:60-70]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 54 (54/397 = 0.1360201511) | 52.2613 / 0.1316405542 | 41 / 0.1032745592 | 64 / 0.161209068 | 0.412100 (4121/10000) |
| `needless` count | 67 (67/397) | 52.0826 | 41 | 63 | 0.005000 (50/10000) |
| mean Δ | −0.0143929471 | 9.444937028e-05 | −0.01162361461 | 0.01179480479 | 0.992600 (9926/10000) |
| mean `help` | 0.03410075567 | 0.03317165951 | 0.02676120907 | 0.0398476228 | 0.384600 (3846/10000) |
| mean `harm` | 0.04849370277 | 0.03307721014 | 0.02661437343 | 0.03986911209 | 0.000000 (0/10000) |

Plain interval statements: observed `needed`/`f` **falls inside** its null interval. Observed `needless` **falls above** its null interval (67 > 63). Mean Δ / `help` / `harm` are the same quantities as at δ = 0.166 (they do not depend on δ).

---

## 2. Train, contestable (n = 263) — **post-hoc subset**

Ceiling 131 and floor 3 points excluded using **observed** means, then the sign-flip null is applied to the remaining 263 points `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:32-36]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:72]`.

### δ = 0.166 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:73-83]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 25 (25/263 = 0.0950570342) | 22.3542 / 0.08499695817 | 15 / 0.05703422053 | 31 / 0.1178707224 | 0.287600 (2876/10000) |
| `needless` count | 31 (31/263) | 22.3228 | 15 | 30 | 0.022000 (220/10000) |
| mean Δ | +0.002766159696 | 0.0001267460076 | −0.01628940114 | 0.01625665399 | 0.374700 (3747/10000) |
| mean `help` | 0.05147528517 | 0.04244342747 | 0.03350377852 | 0.05177250475 | 0.028200 (282/10000) |
| mean `harm` | 0.04870912548 | 0.04231668146 | 0.03341423479 | 0.05161321293 | 0.091000 (910/10000) |

Plain interval statements: observed `needed`/`f` **falls inside** its null interval. Observed `needless` **falls above** its null interval (31 > 30). Observed mean Δ **falls inside** its null interval. Observed mean `help` **falls inside** its null interval (0.051475 < 0.051773). Observed mean `harm` **falls inside** its null interval.

### δ = 0.100 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:84-94]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 54 (54/263 = 0.2053231939) | 44.4936 / 0.1691771863 | 34 / 0.1292775665 | 55 / 0.2091254753 | 0.044300 (443/10000) |
| `needless` count | 45 (45/263) | 44.3605 | 34 | 55 | 0.481500 (4815/10000) |
| mean Δ | +0.002766159696 | 0.0001267460076 | −0.01628940114 | 0.01625665399 | 0.374700 (3747/10000) |
| mean `help` | 0.05147528517 | 0.04244342747 | 0.03350377852 | 0.05177250475 | 0.028200 (282/10000) |
| mean `harm` | 0.04870912548 | 0.04231668146 | 0.03341423479 | 0.05161321293 | 0.091000 (910/10000) |

Plain interval statements: observed `needed`/`f` **falls inside** its null interval (54 ≤ 55). Observed `needless` **falls inside** its null interval. Mean Δ / `help` / `harm` as above.

---

## 3. Dev, all-complete (n = 332)

### δ = 0.166 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:128-138]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 43 (43/332 = 0.1295180723) | 32.7821 / 0.09874126506 | 24 / 0.07228915663 | 42 / 0.1265060241 | 0.020400 (204/10000) |
| `needless` count | 43 (43/332) | 32.8766 | 24 | 42 | 0.022500 (225/10000) |
| mean Δ | +0.009701807229 | −8.20373494e-05 | −0.01554371235 | 0.01521287651 | 0.106200 (1062/10000) |
| mean `help` | 0.05893222892 | 0.04291150444 | 0.03441912651 | 0.05158682229 | 0.000300 (3/10000) |
| mean `harm` | 0.04923042169 | 0.04299354179 | 0.03451568148 | 0.0519877259 | 0.079600 (796/10000) |

Plain interval statements: observed `needed`/`f` **falls above** its null interval (43 > 42). Observed `needless` **falls above** its null interval (43 > 42). Observed mean Δ **falls inside** its null interval. Observed mean `help` **falls above** its null interval. Observed mean `harm` **falls inside** its null interval.

### δ = 0.100 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:139-149]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 72 (72/332 = 0.2168674699) | 58.4331 / 0.1760033133 | 47 / 0.1415662651 | 70 / 0.2108433735 | 0.015200 (152/10000) |
| `needless` count | 61 (61/332) | 58.5672 | 47 | 70 | 0.368500 (3685/10000) |
| mean Δ | +0.009701807229 | −8.20373494e-05 | −0.01554371235 | 0.01521287651 | 0.106200 (1062/10000) |
| mean `help` | 0.05893222892 | 0.04291150444 | 0.03441912651 | 0.05158682229 | 0.000300 (3/10000) |
| mean `harm` | 0.04923042169 | 0.04299354179 | 0.03451568148 | 0.0519877259 | 0.079600 (796/10000) |

Plain interval statements: observed `needed`/`f` **falls above** its null interval (72 > 70). Observed `needless` **falls inside** its null interval. Mean Δ / `help` / `harm` as at δ = 0.166.

---

## 4. Dev, contestable (n = 264) — **post-hoc subset**

Ceiling 68 and floor 0 excluded using **observed** means `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:111-115]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:151]`.

### δ = 0.166 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:152-162]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 43 (43/264 = 0.1628787879) | 30.4008 / 0.1151545455 | 22 / 0.08333333333 | 39 / 0.1477272727 | 0.004600 (46/10000) |
| `needless` count | 36 (36/264) | 30.5026 | 22 | 40 | 0.136300 (1363/10000) |
| mean Δ | +0.02368560606 | −9.121098485e-05 | −0.01864962121 | 0.01816860795 | 0.006000 (60/10000) |
| mean `help` | 0.07411174242 | 0.04991639063 | 0.03960213068 | 0.06043001894 | 0.000000 (0/10000) |
| mean `harm` | 0.05042613636 | 0.05000760161 | 0.03986815814 | 0.06078153409 | 0.461900 (4619/10000) |

Plain interval statements: observed `needed`/`f` **falls above** its null interval. Observed `needless` **falls inside** its null interval. Observed mean Δ **falls above** its null interval. Observed mean `help` **falls above** its null interval. Observed mean `harm` **falls inside** its null interval.

### δ = 0.100 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:163-173]`

| quantity | observed | null mean | null 2.5th | null 97.5th | one-sided p (`n≥obs / 10000`) |
|---|---|---|---|---|---|
| `needed` count and `f` = needed/n | 72 (72/264 = 0.2727272727) | 54.1853 / 0.2052473485 | 43 / 0.1628787879 | 65 / 0.2462121212 | 0.001900 (19/10000) |
| `needless` count | 50 (50/264) | 54.3154 | 43 | 66 | 0.797300 (7973/10000) |
| mean Δ | +0.02368560606 | −9.121098485e-05 | −0.01864962121 | 0.01816860795 | 0.006000 (60/10000) |
| mean `help` | 0.07411174242 | 0.04991639063 | 0.03960213068 | 0.06043001894 | 0.000000 (0/10000) |
| mean `harm` | 0.05042613636 | 0.05000760161 | 0.03986815814 | 0.06078153409 | 0.461900 (4619/10000) |

Plain interval statements: observed `needed`/`f` **falls above** its null interval. Observed `needless` **falls inside** its null interval. Mean Δ / `help` / `harm` as at δ = 0.166.

---

## 5. Asymmetry `needed − needless` (two-sided)

Under this sign-flip null the statistic is symmetric around 0 by construction. Two-sided p = `n(|perm| >= |obs|) / 10000`.

| split | subset | δ | observed | null mean | null 2.5th | null 97.5th | two-sided p | inside null interval? |
|---|---|---|---|---|---|---|---|---|
| train | all-complete | 0.166 | −21 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:59]` | 0.0183 | −14 | 14 | 0.005200 (52/10000) | no (below) |
| train | all-complete | 0.100 | −13 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:70]` | 0.1787 | −20 | 20 | 0.219800 (2198/10000) | yes |
| train | contestable (post-hoc) | 0.166 | −6 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:83]` | 0.0314 | −13 | 13 | 0.414100 (4141/10000) | yes |
| train | contestable (post-hoc) | 0.100 | +9 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:94]` | 0.1331 | −18 | 19 | 0.368900 (3689/10000) | yes |
| dev | all-complete | 0.166 | 0 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:138]` | −0.0945 | −16 | 16 | 1.000000 (10000/10000) | yes |
| dev | all-complete | 0.100 | +11 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:149]` | −0.1341 | −22 | 21 | 0.337500 (3375/10000) | yes |
| dev | contestable (post-hoc) | 0.166 | +7 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:162]` | −0.1018 | −16 | 15 | 0.414400 (4144/10000) | yes |
| dev | contestable (post-hoc) | 0.100 | +22 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:173]` | −0.1301 | −21 | 20 | 0.040100 (401/10000) | no (above) |

---

## 6. What these p-values do and do not license

**One-sided p** is the Monte Carlo fraction of these 10,000 paired sign-flips in which the statistic was ≥ the observed value `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:14]`. It is a test of the alternative “this number is larger than under within-seed exchangeability of treated and untreated.” A small one-sided p licenses rejecting that null in the **upper** tail at this Monte Carlo resolution (grain 1/10000). It does not license a causal policy claim, a statement about other estimators, or any change to δ or the pre-registration.

A large one-sided p does **not** license the claim that the statistic is small, and does **not** license accepting the null. Train all-complete mean Δ is the example: one-sided p = 0.992600 because −0.01439 is in the **lower** tail `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:55]`; the same observed value **falls outside** the two-sided 95% null interval on the low side. The percentile interval, not the upper-tail p, is the comparison for “is this value unusual in either direction.”

**p = 0/10000** means none of these 10,000 draws were ≥ observed `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:54]`. That does not mean the true p is zero; it means the Monte Carlo estimate is 0 at grain 0.0001.

**Two-sided p for `needed − needless`** is the Monte Carlo fraction with absolute value at least as large as observed `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:15]`. Under this null the statistic is symmetric about 0. A small two-sided p licenses rejecting that symmetry. It does not identify `f` (needed/n) as the quantity that is off-null, and it does not license treating needless as `f`. On train all-complete at δ = 0.166 the observed asymmetry is −21 (more needless than needed) `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:59]`. On dev all-complete at δ = 0.166 the observed asymmetry is 0 and the two-sided p is 1 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:138]`.

**Contestable-set p-values** are computed after dropping ceiling and floor points defined from the same observed means that define Δ. They are a post-hoc subset and do not have the same sampling interpretation as the all-complete tables.

This unit reports the comparison to the paired sign-flip null. It does not recommend a course of action, does not declare the campaign thesis supported or refuted, and does not propose amending δ or the pre-registration.
