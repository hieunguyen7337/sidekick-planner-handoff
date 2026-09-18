# STATUS — W-17 (Temperature Fitting Fix & J7 Re-run) — 2026-09-18

## State
- `scripts/setup/fit_feature_verifier.py`:
  - Replaced broken Newton iteration in `fit_temperature` with a robust 1-D golden-section search over `log(T) \in [log(0.05), log(20.0)]` [OBSERVED scripts/setup/fit_feature_verifier.py:325-384].
  - Enforced the invariant guard that calibration never degrades dev NLL compared to `T = 1.0` (returns `1.0` if `nll_opt >= nll_1`) [OBSERVED scripts/setup/fit_feature_verifier.py:381-384].
  - Handled degenerate inputs (empty or single class) returning `T = 1.0` without raising [OBSERVED scripts/setup/fit_feature_verifier.py:338-339].
  - Added `compute_nll` (and `nll` alias) and `rescale_probs` helper functions [OBSERVED scripts/setup/fit_feature_verifier.py:311-322, 443-450].
  - Added dev NLL before and after scaling to `metrics.json` (`report["dev_nll_before"]`, `report["dev_nll_after"]`, `report["dev"]["nll_before"]`, `report["dev"]["nll_after"]`, `report["dev"]["nll"]`) [OBSERVED scripts/setup/fit_feature_verifier.py:494-497].
  - Added threat to validity noting dev calibration metrics are evaluated in-sample on the same dev split used for temperature fitting [OBSERVED scripts/setup/fit_feature_verifier.py:509-511].
- `tests/unit/test_feature_verifier.py`:
  - Added regression unit tests for the 3 synthetic regimes (true T ≈ 1.0, true T ≈ 3.0, uninformative scores T >= 5.0) [OBSERVED tests/unit/test_feature_verifier.py:536-564].
  - Added test for degenerate inputs [OBSERVED tests/unit/test_feature_verifier.py:566-570].
  - Added test verifying the NLL invariant (`NLL(T_fit) <= NLL(1.0)`) [OBSERVED tests/unit/test_feature_verifier.py:573-580].
- Re-run J7 produced artifact `artifacts/verifiers/feature_lr_20260918/` with updated `weights.json`, `metrics.json`, and `feature_spec.json`.

## J7 Comparison (Old vs New)

| Metric | Old (Broken Newton) | New (1-D Golden Section) | Notes |
|---|---|---|---|
| Temperature ($T$) | `0.1290` | `11.0360` | Optimizer artifact fixed; now flattens overconfident logits |
| Dev NLL Before Scaling | *(not recorded)* | `0.7312` | Uncalibrated log-loss |
| Dev NLL After Scaling | *(3.4772 derived)* | `0.6928` | Improved from 0.7312 to 0.6928 |
| Dev Brier Score | `0.4802` | `0.2498` | Calibration miscalibration artifact eliminated |
| Dev ECE | `0.4902` | `0.0136` | Expected calibration error reduced from ~49% to ~1.4% |
| Dev AUROC (all states) | `0.5917` | `0.5917` | Unchanged (rank statistic invariant under monotonic scaling) |
| Dev AUROC (tick states) | `0.5917` | `0.5917` | Unchanged |

## Test Results
- `pytest tests/unit/test_feature_verifier.py`: 26 passed, 0 failures [OBSERVED PBS job 25422294.aqua].
