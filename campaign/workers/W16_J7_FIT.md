# W-16 J7 Feature Verifier Fit Report

**Unit:** W-16 — Fit and calibrate the feature verifier (`feature_lr_v1`).
**Date:** 2026-09-18
**Command executed:**
```bash
timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python scripts/setup/fit_feature_verifier.py --train-branches /scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branches.jsonl --dev-branches /scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branches.jsonl --train-campaign /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 --dev-campaign /scratch/n12194778/sidekick/results/hj4b_fixed_k_dev_20260917 --out artifacts/verifiers --date 20260918'
```
**Exit Status:** 0 [OBSERVED /home/n12194778/.hpc-spool/20260918-130339-2829023.out:1] (PBS Job ID `25422197.aqua`)

---

## 1. Sample Counts, Exclusions, and Statistical Power

### Summary Table

| Metric / Category | Train | Dev |
|---|---:|---:|
| Raw rows read | 777 | 382 |
| Episode feature join dropped | 0 | 0 |
| Successfully joined | 777 | 382 |
| Incomplete labels dropped (`label_status == 'incomplete'`) | 380 | 50 |
| Ambiguous points excluded (`ambiguous == True`) | 326 | 246 |
| Missing label dropped | 0 | 0 |
| **Points used for fit / evaluation ($n$)** | **71** | **86** |
| **Positive points ($y = 1$, `needed`)** | **25** | **43** |
| **Negative points ($y = 0$, `needless`)** | **46** | **43** |
| Positive class fraction | 35.21% (0.352113) | 50.00% (0.500000) |
| Tick states count ($n_{\text{tick}}$) | 71 / 71 (100%) | 86 / 86 (100%) |

*[OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:4-55]*

### Exclusion Checks & Confirmation
- **Ambiguous points exclusion:** Confirmed. In `scripts/setup/fit_feature_verifier.py:233-235`, rows with `ambiguous == True` are strictly excluded from dataset filtering prior to fitting or temperature scaling. [OBSERVED scripts/setup/fit_feature_verifier.py:233-235] Exactly 326 ambiguous rows in train and 246 ambiguous rows in dev were excluded. [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:32,41]
- **Incomplete rows:** 380 incomplete rows in train and 50 in dev were dropped and never imputed. [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:31,40]
- **Join drops:** 0 points dropped during prefix trajectory state joins across both train and dev splits. [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:48,53]

### 🔺 Power Assessment: Thin / Underpowered Fit
Train positive count is **25** (strictly $< 30$). The logistic regression fit is **severely underpowered**. 
Because the effective sample size is small ($n_{\text{train}}=71$ with 25 positives), the point estimate on dev cannot be interpreted as a definitive test of the 0.65 threshold without reporting the confidence interval.

---

## 2. Model Performance & Bootstrap Confidence Intervals

### Performance Metrics

| Split / Metric | Train | Dev (Raw / Pre-scaling) | Dev (Scaled / Post-scaling) |
|---|---:|---:|---:|
| $n$ | 71 | 86 | 86 |
| AUROC (all states) | 0.7183 (0.718261) | 0.5917 (0.591671) | 0.5917 (0.591671) |
| AUROC (tick states) | 0.7183 (0.718261) | 0.5917 (0.591671) | 0.5917 (0.591671) |
| Brier score | 0.2189 (0.218931) | 0.2682 (0.268220) | 0.4802 (0.480153) |
| Expected Calibration Error (ECE) | 0.0654 (0.065401) | 0.1447 (0.144688) | 0.4902 (0.490190) |
| Temperature ($T$) | — | — | 0.1290 (0.129018) |

*[OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:6-21]*
*[INFERRED pre-scaling dev metrics via PBS Job 25422203.aqua running bootstrap script]*

### Dev AUROC Bootstrap Confidence Interval
Computed via 10,000 bootstrap resamples with replacement over the 86 dev evaluation points (RNG seed `20260918`):
- **Dev AUROC point estimate:** 0.5917 [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:18]
- **Dev AUROC 95% Bootstrap CI (percentile [2.5%, 97.5%]):** **`[0.4677, 0.7113]`** [INFERRED via PBS Job 25422203.aqua]
- **Dev AUROC Bootstrap Mean:** 0.5933, **Std Error:** 0.0624 [INFERRED via PBS Job 25422203.aqua]

**Interpretation:** The 95% confidence interval `[0.4677, 0.7113]` encompasses 0.50 (chance level) up to 0.71. It spans both sides of the pre-registered 0.65 threshold. This confirms the statistical thinness of the sample: a point estimate of 0.5917 does not statistically reject 0.65 or 0.50.

---

## 3. Calibration and Temperature Scaling Analysis

- **Fitted Temperature:** $T = 0.1290176631829565$ [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:21]
- **Calibration degradation:** Because $T \ll 1.0$, temperature scaling drastically steepens the predicted probabilities towards 0.0 and 1.0. 
  - On the dev set (50% positive rate, low separability), this extreme sharpening sharply increased dev Brier score from **0.2682** (raw) to **0.4802** (scaled), and dev ECE from **0.1447** (raw) to **0.4902** (scaled). [INFERRED via PBS Job 25422203.aqua]
  - On train, the model achieved Brier = 0.2189 and ECE = 0.0654. [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:7-8]

---

## 4. Feature Weights

Model parameters fitted with $L_2 = 1.0$ batch gradient descent:
- **Intercept (unstandardized):** `-0.6960562271662087` [OBSERVED artifacts/verifiers/feature_lr_20260918/weights.json:132]
- **Feature spec version:** `feature_lr_v1` [OBSERVED artifacts/verifiers/feature_lr_20260918/weights.json:2]

### Detailed Feature Table

| Feature Name | Raw Mean | Raw Std | Standardized Weight ($w_{\text{std}}$) | Unstandardized Weight ($w_{\text{unstd}}$) |
|---|---:|---:|---:|---:|
| `transcript_chars` | 18965.75 | 18065.37 | +0.095553 | +5.289311e-06 |
| `step` | 12.75 | 7.06 | +0.018053 | +2.556952e-03 |
| `n_interventions` | 1.55 | 1.41 | +0.018053 | +1.278476e-02 |
| `distinct_apis` | 1.96 | 1.64 | -0.003315 | -2.021543e-03 |
| `token_leak` | 0.08 | 0.28 | -0.008772 | -3.153703e-02 |
| `last_action_repeat` | 0.01 | 0.12 | -0.031210 | -2.648533e-01 |
| `last_obs_is_error` | 0.34 | 0.47 | -0.082754 | -1.749425e-01 |
| `n_asks` | 0.00 | 1.00 | 0.000000 | 0.000000e+00 |
| `consecutive_error_run` | 0.00 | 1.00 | 0.000000 | 0.000000e+00 |
| `last_action_kind_CODE` | 1.00 | 1.00 | 0.000000 | 0.000000e+00 |
| `last_action_kind_REPORT` | 0.00 | 1.00 | 0.000000 | 0.000000e+00 |
| `last_action_kind_ASK_PLANNER` | 0.00 | 1.00 | 0.000000 | 0.000000e+00 |
| `last_action_kind_COMPLETE` | 0.00 | 1.00 | 0.000000 | 0.000000e+00 |

*[OBSERVED artifacts/verifiers/feature_lr_20260918/weights.json:117-131]*
*[Standardized weights and feature stats OBSERVED via PBS Job 25422203.aqua]*

### Signal Breakdown
- **Positive signals:** Longer transcripts (`transcript_chars` $w_{\text{std}} = +0.0956$), later step numbers (`step` $w_{\text{std}} = +0.0181$), and higher intervention count (`n_interventions` $w_{\text{std}} = +0.0181$) correlate with higher probability of intervention being `needed`.
- **Negative signals:** Error observations (`last_obs_is_error` $w_{\text{std}} = -0.0828$) and repeated actions (`last_action_repeat` $w_{\text{std}} = -0.0312$) carry negative weights.
- **Zero signal / Inactive features:** `n_asks`, `consecutive_error_run`, and action type one-hot indicators had zero variance / zero weights in the training set.

---

## 5. Artifacts Written

1. `artifacts/verifiers/feature_lr_20260918/weights.json` [OBSERVED]
2. `artifacts/verifiers/feature_lr_20260918/feature_spec.json` [OBSERVED]
3. `artifacts/verifiers/feature_lr_20260918/metrics.json` [OBSERVED]

---

## 6. Verification & Test Suite

- Ran `tests/unit/test_feature_verifier.py` in PBS Job `25422210.aqua`:
  - **Result:** `23 passed, 1 warning in 1.56s` (100% pass) [OBSERVED /home/n12194778/.hpc-spool/20260918-130458-2845263.out:13]
