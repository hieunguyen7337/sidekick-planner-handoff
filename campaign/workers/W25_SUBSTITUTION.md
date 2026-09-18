# W-25 — substitution test: later reviews in the untreated arm

**Analysis only. No production code modified. Nothing committed. Zero live `codex` / planner calls. No GPU jobs.**

Script: `campaign/workers/scratch_W25/substitution.py`  
Raw verbatim output: `campaign/workers/scratch_W25/w25_out.txt`  
PBS job: **25447958.aqua** on `cpu1n040`, finished after 70s, ngpus=0 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:1-12]`  
Permutation seed: **20260918**; **N_PERM = 10,000** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:13]`  
Spearman permutation seed: **20260919**; **10,000** shuffles of `n_later` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:14]`

Every number below is tagged `[OBSERVED <path>:<line>]` to that raw log, or `[INFERRED]` if it is a restatement.

This unit does not recommend a course of action, does not declare the substitution account supported or refuted, and does not propose amending δ, the branch definition, or the pre-registration.

---

## 0. Population, `n_later`, and logs

Loading, completeness, and the contestable mask are the W-24 / W-20 definitions: seeds **101–104**, non-null `branch_gpr` in both conditions, contestable = non-ceiling and non-floor on **observed** means (`mean(untreated) >= 1.0` ceiling; `mean(untreated) <= 0` and `mean(treated) <= 0` floor). Completeness keys match W-24 exactly `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:33-38]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:251-256]`.

`n_later` on a replicate is the count of `event_type == "intervention"` events with `step > s` in that untreated branch’s `events.jsonl`. The point-level value is the **median of the four untreated replicates**. Event logs are treated as ground truth. Half-integer medians occur when the two central replicates differ by one; they are kept as their own rows so those points are not dropped from the dose-response table. Bucket `3+` is median `>= 3` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:17-18]`.

`f` = needed / n_bucket. The needless count is never called `f`.

### Branch directories

| split | untreated logs expected (complete × 4) | opened and readable | missing | unreadable |
|---|---:|---:|---:|---:|
| train | 1588 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:47]` | 1588 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:48]` | 0 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:49]` | 0 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:50]` |
| dev | 1328 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:265]` | 1328 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:266]` | 0 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:267]` | 0 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:268]` |

Every complete point had all four untreated logs `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:53-55]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:271-273]`.

### Event log vs proxy `floor((branch_steps − s) / 5)`

| split | pairs | agree | disagree | Pearson r | Spearman ρ |
|---|---:|---:|---:|---:|---:|
| train | 1588 | 1588/1588 = 1.0000000000 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:77-78]` | 0 | 1.0000000000 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:80]` | 1.0000000000 |
| dev | 1328 | 1327/1328 = 0.9992469880 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:299]` | 1 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:298]` | 0.9988170413 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:301]` | 0.9999834107 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:302]` |

On both splits, event-log `n_later` agreed with stored `n_later_reviews` and with `source == "live_policy"` counts (0 disagreements) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:83-85]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:305-307]`. No negative proxies `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:82]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:303]`. The single dev disagreement is left as a logged 1/1328; the event log is the value used below.

### Replicate disagreement

The four untreated replicates are not exchangeable for `n_later`:

| split | points | four values not all equal | rate | median = 0 but max > 0 |
|---|---:|---:|---:|---:|
| train | 397 | 227 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:59]` | 227/397 = 0.5717884131 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:60]` | 34 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:61]` |
| dev | 332 | 218 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:277]` | 218/332 = 0.6566265060 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:278]` | 19 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:279]` |

Median `n_later` = 0 therefore includes 34 train and 19 dev points where at least one untreated replicate had a later review `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:61]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:279]`.

---

## 1. Size of the `n_later = 0` subset

**Train: 175 / 397 complete points.** **Dev: 91 / 332 complete points.** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:89]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:310]`

These are not n ≈ 20. Contestable (post-hoc) `n_later = 0`: train **78**, dev **53** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:196]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:417]`.

Exact median histogram `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:62-74]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:280-295]`:

| median `n_later` | train n | dev n |
|---|---:|---:|
| 0 | 175 | 91 |
| 0.5 | 19 | 22 |
| 1 | 70 | 77 |
| 1.5 | 29 | 26 |
| 2 | 31 | 36 |
| 2.5 | 26 | 20 |
| 3+ (median ≥ 3) | 47 | 60 |
| **total** | **397** | **332** |

---

## 2. Dose-response — all complete points

### Train, δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:96-104]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 175 | +0.0039228571 | 0.0283728571 | 0.0244500000 | 11 | 8 | 11/175 = 0.0628571429 | 3 |
| 0.5 | 19 | +0.0193026316 | 0.0537368421 | 0.0344342105 | 2 | 1 | 2/19 = 0.1052631579 | 1 |
| 1 | 70 | −0.0353214286 | 0.0324678571 | 0.0677892857 | 3 | 11 | 3/70 = 0.0428571429 | −8 |
| 1.5 | 29 | −0.0115517241 | 0.0359827586 | 0.0475344828 | 2 | 4 | 2/29 = 0.0689655172 | −2 |
| 2 | 31 | −0.0006370968 | 0.0500241935 | 0.0506612903 | 3 | 3 | 3/31 = 0.0967741935 | 0 |
| 2.5 | 26 | −0.0571346154 | 0.0394230769 | 0.0965576923 | 2 | 7 | 2/26 = 0.0769230769 | −5 |
| 3+ | 47 | −0.0522234043 | 0.0353138298 | 0.0875372340 | 2 | 12 | 2/47 = 0.0425531915 | −10 |

Needed counts 11+2+3+2+3+2+2 = 25, matching W-24 train needed at δ = 0.166 `[INFERRED]`.

### Train, δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:105-113]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 175 | +0.0039228571 | 0.0283728571 | 0.0244500000 | 20 | 13 | 20/175 = 0.1142857143 | 7 |
| 0.5 | 19 | +0.0193026316 | 0.0537368421 | 0.0344342105 | 5 | 2 | 5/19 = 0.2631578947 | 3 |
| 1 | 70 | −0.0353214286 | 0.0324678571 | 0.0677892857 | 8 | 21 | 8/70 = 0.1142857143 | −13 |
| 1.5 | 29 | −0.0115517241 | 0.0359827586 | 0.0475344828 | 6 | 6 | 6/29 = 0.2068965517 | 0 |
| 2 | 31 | −0.0006370968 | 0.0500241935 | 0.0506612903 | 5 | 3 | 5/31 = 0.1612903226 | 2 |
| 2.5 | 26 | −0.0571346154 | 0.0394230769 | 0.0965576923 | 5 | 9 | 5/26 = 0.1923076923 | −4 |
| 3+ | 47 | −0.0522234043 | 0.0353138298 | 0.0875372340 | 5 | 13 | 5/47 = 0.1063829787 | −8 |

Needed counts 20+5+8+6+5+5+5 = 54, matching W-24 train needed at δ = 0.100 `[INFERRED]`.

### Dev, δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:317-325]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 91 | +0.0121840659 | 0.0326620879 | 0.0204780220 | 7 | 5 | 7/91 = 0.0769230769 | 2 |
| 0.5 | 22 | −0.0211363636 | 0.0359886364 | 0.0571250000 | 2 | 3 | 2/22 = 0.0909090909 | −1 |
| 1 | 77 | +0.0089870130 | 0.0565519481 | 0.0475649351 | 8 | 9 | 8/77 = 0.1038961039 | −1 |
| 1.5 | 26 | −0.0252307692 | 0.0664423077 | 0.0916730769 | 4 | 8 | 4/26 = 0.1538461538 | −4 |
| 2 | 36 | −0.0074791667 | 0.0877152778 | 0.0951944444 | 7 | 7 | 7/36 = 0.1944444444 | 0 |
| 2.5 | 20 | −0.0396875000 | 0.0470875000 | 0.0867750000 | 1 | 4 | 1/20 = 0.0500000000 | −3 |
| 3+ | 60 | +0.0600708333 | 0.0936666667 | 0.0335958333 | 14 | 7 | 14/60 = 0.2333333333 | 7 |

Needed counts 7+2+8+4+7+1+14 = 43, matching W-24 dev needed at δ = 0.166 `[INFERRED]`.

### Dev, δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:326-334]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 91 | +0.0121840659 | 0.0326620879 | 0.0204780220 | 9 | 7 | 9/91 = 0.0989010989 | 2 |
| 0.5 | 22 | −0.0211363636 | 0.0359886364 | 0.0571250000 | 4 | 5 | 4/22 = 0.1818181818 | −1 |
| 1 | 77 | +0.0089870130 | 0.0565519481 | 0.0475649351 | 17 | 12 | 17/77 = 0.2207792208 | 5 |
| 1.5 | 26 | −0.0252307692 | 0.0664423077 | 0.0916730769 | 8 | 10 | 8/26 = 0.3076923077 | −2 |
| 2 | 36 | −0.0074791667 | 0.0877152778 | 0.0951944444 | 12 | 11 | 12/36 = 0.3333333333 | 1 |
| 2.5 | 20 | −0.0396875000 | 0.0470875000 | 0.0867750000 | 6 | 7 | 6/20 = 0.3000000000 | −1 |
| 3+ | 60 | +0.0600708333 | 0.0936666667 | 0.0335958333 | 16 | 9 | 16/60 = 0.2666666667 | 7 |

Needed counts 9+4+17+8+12+6+16 = 72, matching W-24 dev needed at δ = 0.100 `[INFERRED]`.

### Spearman `n_later` vs Δ (all complete points)

| split | n | ρ (average ranks) | two-sided perm p (`n(\|ρ_perm\| ≥ \|obs\|) / 10000`) |
|---|---:|---:|---|
| train | 397 | −0.1633780546 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:92]` | 0.000700 (7/10000) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:93]` |
| dev | 332 | +0.0948570700 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:313]` | 0.083800 (838/10000) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:314]` |

`scipy` was not in the job interpreter; the p-values above are the permutation test, seed 20260919 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:94]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:315]`.

---

## 3. Clean-counterfactual subset: `n_later = 0`, paired sign-flip null

Same null as W-24: within each point, independently per branch seed, swap treated[s] with untreated[s] with probability 0.5; 10,000 permutations; seed **20260918**. One-sided p = `n(perm >= observed) / 10000`. Two-sided p for asymmetry = `n(|perm| >= |observed|) / 10000`. Null 2.5th / 97.5th = `numpy.percentile` linear `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:152-154]`.

### Train, `n_later = 0`, n = **175** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:157]`

Null interval width for mean Δ: 0.0240659286 (2.5th −0.0119057143, 97.5th +0.0121602143) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:158]`. This n is large enough that |mean Δ| ≳ 0.012 would fall outside that interval `[INFERRED]`.

#### δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:160-177]`

| quantity | observed | null mean | null 2.5th | null 97.5th | p | interval |
|---|---|---|---|---|---|---|
| `needed` / `f` | 11 (11/175 = 0.0628571429) | 5.1816 / 0.02960914286 | 2 / 0.01142857143 | 9 / 0.05142857143 | 0.005100 (51/10000) one-sided | **outside** (above) |
| `needless` | 8 (8/175) | 5.1937 | 2 | 9 | 0.118000 (1180/10000) one-sided | **inside** |
| mean Δ | +0.0039228571 | −4.777428571e-06 | −0.01190571429 | 0.01216021429 | 0.254400 (2544/10000) one-sided | **inside** |
| mean help | 0.0283728571 | 0.015225946 | 0.0088385 | 0.02257292857 | 0.000700 (7/10000) one-sided | **outside** (above) |
| mean harm | 0.0244500000 | 0.01523072343 | 0.008569678571 | 0.022393 | 0.006900 (69/10000) one-sided | **outside** (above) |
| needed − needless | 3 | −0.0121 | −6 | 6 | 0.439800 (4398/10000) two-sided | **inside** |

#### δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:178-195]`

| quantity | observed | null mean | null 2.5th | null 97.5th | p | interval |
|---|---|---|---|---|---|---|
| `needed` / `f` | 20 (20/175 = 0.1142857143) | 10.7431 / 0.06138914286 | 6 / 0.03428571429 | 16 / 0.09142857143 | 0.001000 (10/10000) one-sided | **outside** (above) |
| `needless` | 13 (13/175) | 10.728 | 6 | 16 | 0.247100 (2471/10000) one-sided | **inside** |
| mean Δ | +0.0039228571 | −4.777428571e-06 | −0.01190571429 | 0.01216021429 | 0.254400 (2544/10000) one-sided | **inside** |
| mean help | 0.0283728571 | 0.015225946 | 0.0088385 | 0.02257292857 | 0.000700 (7/10000) one-sided | **outside** (above) |
| mean harm | 0.0244500000 | 0.01523072343 | 0.008569678571 | 0.022393 | 0.006900 (69/10000) one-sided | **outside** (above) |
| needed − needless | 7 | 0.0151 | −9 | 9 | 0.162700 (1627/10000) two-sided | **inside** |

Mean Δ / help / harm do not depend on δ.

### Dev, `n_later = 0`, n = **91** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:378]`

Null interval width for mean Δ: 0.0358358516 (2.5th −0.0178765110, 97.5th +0.0179593407) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:379]`. This n is smaller than train’s 175; |mean Δ| ≳ 0.018 would fall outside that interval `[INFERRED]`.

#### δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:381-398]`

| quantity | observed | null mean | null 2.5th | null 97.5th | p | interval |
|---|---|---|---|---|---|---|
| `needed` / `f` | 7 (7/91 = 0.0769230769) | 3.2866 / 0.03611648352 | 1 / 0.01098901099 | 7 / 0.07692307692 | 0.026000 (260/10000) one-sided | **inside** (on the 97.5th) |
| `needless` | 5 (5/91) | 3.2527 | 1 | 7 | 0.207400 (2074/10000) one-sided | **inside** |
| mean Δ | +0.0121840659 | 0.0001394692308 | −0.01787651099 | 0.01795934066 | 0.091900 (919/10000) one-sided | **inside** |
| mean help | 0.0326620879 | 0.01847662527 | 0.009052129121 | 0.02941222527 | 0.006100 (61/10000) one-sided | **outside** (above) |
| mean harm | 0.0204780220 | 0.01833715604 | 0.009156456044 | 0.02933839286 | 0.321600 (3216/10000) one-sided | **inside** |
| needed − needless | 2 | 0.0339 | −5 | 5 | 0.560600 (5606/10000) two-sided | **inside** |

#### δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:399-416]`

| quantity | observed | null mean | null 2.5th | null 97.5th | p | interval |
|---|---|---|---|---|---|---|
| `needed` / `f` | 9 (9/91 = 0.0989010989) | 6.8313 / 0.07506923077 | 3 / 0.03296703297 | 11 / 0.1208791209 | 0.198100 (1981/10000) one-sided | **inside** |
| `needless` | 7 (7/91) | 6.7986 | 3 | 11 | 0.554200 (5542/10000) one-sided | **inside** |
| mean Δ | +0.0121840659 | 0.0001394692308 | −0.01787651099 | 0.01795934066 | 0.091900 (919/10000) one-sided | **inside** |
| mean help | 0.0326620879 | 0.01847662527 | 0.009052129121 | 0.02941222527 | 0.006100 (61/10000) one-sided | **outside** (above) |
| mean harm | 0.0204780220 | 0.01833715604 | 0.009156456044 | 0.02933839286 | 0.321600 (3216/10000) one-sided | **inside** |
| needed − needless | 2 | 0.0327 | −7 | 7 | 0.691200 (6912/10000) two-sided | **inside** |

---

## 4. Confound: composition of the `n_later` buckets

`n_later = 0` is not randomly assigned. Ceiling = `mean(untreated) >= 1.0`. Floor = `mean(untreated) <= 0` and `mean(treated) <= 0`.

### Train, all complete `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:114-122]`

| bucket | n | mean step | mean untreated | ceiling | floor |
|---|---:|---:|---:|---|---|
| 0 | 175 | 14.9714285714 | 0.8500100000 | 95/175 = 0.5428571429 | 2/175 = 0.0114285714 |
| 0.5 | 19 | 10.5263157895 | 0.8616447368 | 3/19 = 0.1578947368 | 0/19 |
| 1 | 70 | 10.6428571429 | 0.7896714286 | 21/70 = 0.3000000000 | 1/70 = 0.0142857143 |
| 1.5 | 29 | 8.7931034483 | 0.7688879310 | 7/29 = 0.2413793103 | 0/29 |
| 2 | 31 | 13.8709677419 | 0.6295725806 | 2/31 = 0.0645161290 | 0/31 |
| 2.5 | 26 | 11.7307692308 | 0.7330384615 | 2/26 = 0.0769230769 | 0/26 |
| 3+ | 47 | 12.6595744681 | 0.5878936170 | 1/47 = 0.0212765957 | 0/47 |

The `n_later = 0` bucket’s ceiling fraction is **95/175 = 0.5428571429**, against **1/47 = 0.0212765957** in `3+` and **131/397 = 0.3299748111** on all complete train `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:42]` `[INFERRED]`. Mean untreated is also highest in the `0` and `0.5` buckets. A Δ difference across buckets can be this composition rather than substitution. Mean branch step is **not** lowest at `n_later = 0` (14.97 vs 12.66 in `3+`) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:116]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:122]`.

### Dev, all complete `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:335-343]`

| bucket | n | mean step | mean untreated | ceiling | floor |
|---|---:|---:|---:|---|---|
| 0 | 91 | 17.3626373626 | 0.7885027473 | 38/91 = 0.4175824176 | 0/91 |
| 0.5 | 22 | 14.3181818182 | 0.7464886364 | 2/22 = 0.0909090909 | 0/22 |
| 1 | 77 | 11.9480519481 | 0.7232564935 | 18/77 = 0.2337662338 | 0/77 |
| 1.5 | 26 | 13.2692307692 | 0.6514615385 | 4/26 = 0.1538461538 | 0/26 |
| 2 | 36 | 14.3055555556 | 0.5864027778 | 4/36 = 0.1111111111 | 0/36 |
| 2.5 | 20 | 12.0000000000 | 0.7071375000 | 1/20 = 0.0500000000 | 0/20 |
| 3+ | 60 | 13.2500000000 | 0.4328833333 | 1/60 = 0.0166666667 | 0/60 |

The `n_later = 0` bucket’s ceiling fraction is **38/91 = 0.4175824176**, against **1/60 = 0.0166666667** in `3+` and **68/332 = 0.2048192771** on all complete dev `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:260]` `[INFERRED]`. Mean untreated falls as `n_later` rises, except for a rebound at `2.5`.

---

## 5. Dose-response restricted to contestable points (post-hoc)

W-20 contestable mask on observed means, then the same `n_later` buckets. Ceiling and floor fractions are 0 in every row by construction `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:123]`.

### Train contestable, δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:124-132]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 78 | +0.0504102564 | 0.0636570513 | 0.0132467949 | 11 | 2 | 11/78 = 0.1410256410 | 9 |
| 0.5 | 16 | +0.0255312500 | 0.0638125000 | 0.0382812500 | 2 | 1 | 2/16 = 0.1250000000 | 1 |
| 1 | 48 | −0.0093229167 | 0.0473489583 | 0.0566718750 | 3 | 6 | 3/48 = 0.0625000000 | −3 |
| 1.5 | 22 | +0.0245454545 | 0.0474318182 | 0.0228863636 | 2 | 0 | 2/22 = 0.0909090909 | 2 |
| 2 | 29 | +0.0029137931 | 0.0534741379 | 0.0505603448 | 3 | 3 | 3/29 = 0.1034482759 | 0 |
| 2.5 | 24 | −0.0556458333 | 0.0427083333 | 0.0983541667 | 2 | 7 | 2/24 = 0.0833333333 | −5 |
| 3+ | 46 | −0.0533586957 | 0.0360815217 | 0.0894402174 | 2 | 12 | 2/46 = 0.0434782609 | −10 |

### Train contestable, δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:133-141]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 78 | +0.0504102564 | 0.0636570513 | 0.0132467949 | 20 | 4 | 20/78 = 0.2564102564 | 16 |
| 0.5 | 16 | +0.0255312500 | 0.0638125000 | 0.0382812500 | 5 | 2 | 5/16 = 0.3125000000 | 3 |
| 1 | 48 | −0.0093229167 | 0.0473489583 | 0.0566718750 | 8 | 13 | 8/48 = 0.1666666667 | −5 |
| 1.5 | 22 | +0.0245454545 | 0.0474318182 | 0.0228863636 | 6 | 2 | 6/22 = 0.2727272727 | 4 |
| 2 | 29 | +0.0029137931 | 0.0534741379 | 0.0505603448 | 5 | 3 | 5/29 = 0.1724137931 | 2 |
| 2.5 | 24 | −0.0556458333 | 0.0427083333 | 0.0983541667 | 5 | 8 | 5/24 = 0.2083333333 | −3 |
| 3+ | 46 | −0.0533586957 | 0.0360815217 | 0.0894402174 | 5 | 13 | 5/46 = 0.1086956522 | −8 |

Train contestable confound (mean step / mean untreated) `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:142-150]`: `n_later = 0` mean step 18.0128205128, mean untreated 0.6891250000 (n = 78); `3+` mean step 12.8260869565, mean untreated 0.5789347826 (n = 46).

### Dev contestable, δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:345-353]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 53 | +0.0236132075 | 0.0560801887 | 0.0324669811 | 7 | 5 | 7/53 = 0.1320754717 | 2 |
| 0.5 | 20 | −0.0128375000 | 0.0395875000 | 0.0524250000 | 2 | 2 | 2/20 = 0.1000000000 | 0 |
| 1 | 59 | +0.0422330508 | 0.0738050847 | 0.0315720339 | 8 | 5 | 8/59 = 0.1355932203 | 3 |
| 1.5 | 22 | −0.0136250000 | 0.0785227273 | 0.0921477273 | 4 | 7 | 4/22 = 0.1818181818 | −3 |
| 2 | 32 | +0.0079921875 | 0.0986796875 | 0.0906875000 | 7 | 6 | 7/32 = 0.2187500000 | 1 |
| 2.5 | 19 | −0.0417763158 | 0.0495657895 | 0.0913421053 | 1 | 4 | 1/19 = 0.0526315789 | −3 |
| 3+ | 59 | +0.0610889831 | 0.0952542373 | 0.0341652542 | 14 | 7 | 14/59 = 0.2372881356 | 7 |

### Dev contestable, δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:354-362]`

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| 0 | 53 | +0.0236132075 | 0.0560801887 | 0.0324669811 | 9 | 6 | 9/53 = 0.1698113208 | 3 |
| 0.5 | 20 | −0.0128375000 | 0.0395875000 | 0.0524250000 | 4 | 4 | 4/20 = 0.2000000000 | 0 |
| 1 | 59 | +0.0422330508 | 0.0738050847 | 0.0315720339 | 17 | 7 | 17/59 = 0.2881355932 | 10 |
| 1.5 | 22 | −0.0136250000 | 0.0785227273 | 0.0921477273 | 8 | 8 | 8/22 = 0.3636363636 | 0 |
| 2 | 32 | +0.0079921875 | 0.0986796875 | 0.0906875000 | 12 | 9 | 12/32 = 0.3750000000 | 3 |
| 2.5 | 19 | −0.0417763158 | 0.0495657895 | 0.0913421053 | 6 | 7 | 6/19 = 0.3157894737 | −1 |
| 3+ | 59 | +0.0610889831 | 0.0952542373 | 0.0341652542 | 16 | 9 | 16/59 = 0.2711864407 | 7 |

Dev contestable confound `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:363-371]`: `n_later = 0` mean step 20.1886792453, mean untreated 0.6368632075 (n = 53); `3+` mean step 13.3898305085, mean untreated 0.4232711864 (n = 59).

### `n_later = 0` contestable permutation (post-hoc; same sign-flip)

Train contestable `n_later = 0`, n = **78**. Null mean-Δ interval [−0.0210964744, +0.0213782051], width 0.0424746795 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:202-204]`.

At δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:206-223]`: `needed`/`f` 11/78 **outside** above null [1, 7]; `needless` 2 **inside** [1, 7]; mean Δ +0.0504102564 **outside** above; mean help **outside** above; mean harm **inside**; asymmetry 9 **outside** (two-sided 9/10000).

At δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:224-241]`: `needed`/`f` 20/78 **outside** above null [4, 13]; `needless` 4 **inside** [4, 12]; mean Δ / help / harm as at δ = 0.166; asymmetry 16 **outside** (two-sided 0/10000).

Dev contestable `n_later = 0`, n = **53**. Null mean-Δ interval [−0.0306804245, +0.0301893868], width 0.0608698113 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:423-425]`. This n is the smallest subset in the unit; |mean Δ| ≳ 0.030 would fall outside that interval `[INFERRED]`.

At δ = 0.166 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:427-444]`: `needed`/`f` 7/53 **outside** above null [1, 6]; `needless` 5 **inside**; mean Δ +0.0236132075 **inside**; mean help **outside** above; mean harm **inside**; asymmetry 2 **inside**.

At δ = 0.100 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:445-462]`: `needed`/`f` 9/53 **inside** [3, 10]; `needless` 6 **inside**; mean Δ **inside**; mean help **outside** above; mean harm **inside**; asymmetry 3 **inside**.

---

## 6. Contract checklist

- PBS job id: **25447958.aqua** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:11]`
- Permutation seed: **20260918**, N_PERM = 10,000 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:13]`
- Branch directories: train 1588 opened, 0 missing, 0 unreadable; dev 1328 opened, 0 missing, 0 unreadable `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:469-470]`
- Event-log vs proxy agreement: train 1588/1588; dev 1327/1328 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:78]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:299]`
- **`n_later = 0` subset: train 175 / 397, dev 91 / 332** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:89]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:310]`
