# STATUS — W-4 (FeatureVerifier) — 2026-09-17

## State
- `src/sidekick/agents/verifier.py`: added `FeatureVerifier`, `feature_spec()`
  (frozen spec `feature_lr_v1`, 13 columns), extractor helpers. Pure stdlib.
- `src/sidekick/runner.py`: `make_verifier` resolves
  `verifier: {kind: feature_lr, path: <abs>, threshold: <tau>}` into a
  `ThresholdRouter(FeatureVerifier.load(path), tau)`; threshold falls back to
  `cfg.verifier_threshold` then 0.5.
- `scripts/setup/fit_feature_verifier.py`: CPU-only pure-stdlib fit. Drops
  `label_status=incomplete` (never imputed), excludes `ambiguous` and reports
  the counts, fits on train, temperature-scales on dev (1-D Newton on dev NLL),
  writes `artifacts/verifiers/feature_lr_<date>/{weights.json,feature_spec.json,
  metrics.json}` with dev AUROC/Brier/ECE, positive rate and n per stage,
  tick-state vs all-state AUROC, and recorded threats to validity.
- `tests/unit/test_feature_verifier.py`: synthetic tests per brief.

## Known approximations [INFERRED]
- Actions are not echoed to the transcript (loop.py:519-524 line set only), so
  `last_action_repeat` is implemented as: the last action's normalized
  code/message text appears anywhere in the transcript (PLAN/INTERVENTION quote
  it, or OBS traceback echoes it). `distinct_apis` counts distinct dotted call
  names matched by regex over the transcript.
- `random` import in the fit script is currently unused beyond potential
  seeding; GD init is zeros (deterministic, convex objective).

## Not done / blocked
- No real fit: branches.jsonl is empty/stale until J6 jobs finish (brief forbids
  fitting on live J6 output). Run later:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 python scripts/setup/fit_feature_verifier.py --branches <j6>/branches.jsonl --out artifacts/verifiers`

## Resume
- Tests: `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
- Final run (hpc job 25413688.aqua):
  `325 passed, 1 skipped in 22.73s` — 0 failures. Baseline before this unit
  was 286 passed, 1 skipped [OBSERVED brief_W4_verifier.md:94]; other units
  added tests concurrently (e.g. test_p_ask_gate.py), all passing in this run.
- Iteration history: run 1 (25413677) 13 failures — tests called
  `fit._extractor_features` before the function-local import bound it, plus a
  wrong AUROC ascending/descending rank sign, a token regex that required a
  `:`/`=` separator, and a saturated-log-odds division in one test. All fixed;
  run 2 (25413681) 1 failure — a test expected score 1.0 for z=5 (sigmoid(5)=
  0.9933), assertion corrected, not code; run 3 (25413688) all green.

## Frozen feature spec (feature_lr_v1), columns in vector order
step, n_interventions, n_asks, last_obs_is_error, consecutive_error_run,
last_action_repeat, distinct_apis, token_leak, transcript_chars,
last_action_kind_CODE, last_action_kind_REPORT, last_action_kind_ASK_PLANNER,
last_action_kind_COMPLETE.
