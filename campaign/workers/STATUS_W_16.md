# STATUS W-16 — run J7: fit and calibrate the feature verifier

**Unit:** W-16. **No live `codex` call. No GPU job. Do not commit.**
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Resume state

- **Milestone:** complete. J7 fit executed, metrics extracted, bootstrap confidence intervals computed, all unit tests passed. Waiting for orchestrator review/commit.
- **Fit job [OBSERVED]:** PBS job `25422197.aqua` → exited 0 in 25s. Log: `/home/n12194778/.hpc-spool/20260918-130339-2829023.out`
  - Output artifact directory: `artifacts/verifiers/feature_lr_20260918/`
  - Train: $n=71$ (25 positive, 46 negative), AUROC = 0.7183, Brier = 0.2189, ECE = 0.0654
  - Dev: $n=86$ (43 positive, 43 negative), AUROC = 0.5917, Brier = 0.4802, ECE = 0.4902, Temperature $T = 0.1290$
- **Bootstrap evaluation job [OBSERVED]:** PBS job `25422203.aqua` → exited 0 in 25s. Log: `/home/n12194778/.hpc-spool/20260918-130427-2839304.out`
  - Dev AUROC 95% Bootstrap CI (10,000 resamples): `[0.4677, 0.7113]` [INFERRED]
- **Verifier unit test suite [OBSERVED]:** PBS job `25422210.aqua` → `23 passed, 1 warning in 1.56s` (zero failures). Log: `/home/n12194778/.hpc-spool/20260918-130458-2845263.out`

## Owned files (this unit)

- `artifacts/verifiers/feature_lr_20260918/weights.json`
- `artifacts/verifiers/feature_lr_20260918/feature_spec.json`
- `artifacts/verifiers/feature_lr_20260918/metrics.json`
- `campaign/workers/W16_J7_FIT.md`
- `campaign/workers/STATUS_W_16.md` (this file)

## Key Findings & Power Warning

- **Fit is underpowered:** Train positives = **25** ($< 30$). With $n_{\text{train}}=71$, the fit is thin.
- **Ambiguous rows confirmed excluded:** 326 train rows and 246 dev rows with `ambiguous == True` were excluded from dataset prior to fitting/scaling (`scripts/setup/fit_feature_verifier.py:233-235`). [OBSERVED scripts/setup/fit_feature_verifier.py:233-235]
- **Dev AUROC confidence interval:** Point estimate 0.5917 with 95% CI `[0.4677, 0.7113]` encompasses 0.50 and spans across the 0.65 threshold.
- Detailed report written to `campaign/workers/W16_J7_FIT.md`.
