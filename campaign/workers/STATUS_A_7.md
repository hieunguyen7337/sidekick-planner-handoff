# STATUS_A_7.md — A7 (U-VF) value function

Unit: A7. Owner of: scripts/setup/fit_value_function.py,
tests/unit/test_fit_value_function.py, campaign/workers/A7_VALUE_FUNCTION.md,
campaign/workers/scratch_A7/, STATUS_A_7.md.

## Milestones

- [x] M0 brief read; reuse plan fixed: _extractor_features (verifier.py:137-181),
      _events_of_last_attempt (replay.py:111-117), trajectory_state reconstruction
      pattern (fit_feature_verifier.py:89-131), LR+temperature machinery
      (fit_feature_verifier.py:247-505).
- [x] M1 scripts/setup/fit_value_function.py written.
- [x] M2 tests/unit/test_fit_value_function.py written.
- [x] M3 unit tests pass in PBS job: `331 passed, 1 skipped, 1 warning in
      16.09s` (tests/unit + fixtures + reproducibility, job 25451256.aqua).
- [x] M4 fit run in PBS job (FIT_EXIT=0, job 25451058/25451256):
      artifacts/verifiers/value_fn_20260919/ written (weights.json,
      feature_spec.json, metrics.json).
- [x] M5 report campaign/workers/A7_VALUE_FUNCTION.md written.

## Notes

- Zero planner calls; CPU only; /scratch results read-only.
- p_ask kept as None (extractor does not read it — verifier.py:137-181 has no
  p_ask term). Live measured p_ask payloads counted: 0.
- Outcome field: result.json `success` bool; goal_pass_rate fallback; runs.jsonl
  never used.
- Multi-run_start trap confirmed: 114 files, ALL in hj1a_exec8b_20260915
  (that campaign is excluded as zero-success anyway).
- KEY FINDING: dev AUROC 0.6212 [0.546, 0.689] sits AT the feature-blind
  step-prior floor (0.6245); k-NN ceiling proxy 0.6356. V under feature_lr_v1
  is ~feature-blind — do NOT wire into routing yet; binding constraint is the
  frozen feature spec, not the head.

## Resume

If this session dies: run M3/M4 commands from A7_VALUE_FUNCTION.md once written;
artifact + report may already exist — check before re-running.
