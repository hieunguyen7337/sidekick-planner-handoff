# STATUS — X3 failure anatomy

## State
- [x] Brief read.
- [x] STATUS file created (this file).
- [x] See "State (final)" below for completion.

## Command (planned)
Superseded — see final command below.

## Notes / blockers
(none yet)

## State (final)
- [x] `scripts/analysis/failure_anatomy.py` written (stdlib + `sidekick.replay._events_of_last_attempt`).
- [x] Run under `hpc`; output written and JSON-valid (67,404 bytes).
- [x] Headline numbers below. DONE.

## Command (final successful run)
`timeout 1800 hpc bash -c 'cd /mnt/.../plan-2026-09-15 && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python scripts/analysis/failure_anatomy.py'`
Note: plain `python3` on the HPC node lacks pydantic; used the repo's venv interpreter.
Output: `campaign/results/failure_anatomy_dev_20260921.json`.

## Headlines (all [OBSERVED output JSON])
- Episodes: 114/114/114 per arm; 0 excluded; 0 multi-run_start files.
- **S1 2x2** (planner_alone x executor, n_pairs=114): sft_plan goal_pass & tgc_pass: 31 / 5 / **38** / 40 (fail-fail / planner_fail-exec_pass / **planner_pass-exec_fail** / pass-pass). fixed_k_10: 29 / 7 / **38** / 40. Opportunity cell = 38 pairs (33 distinct tasks) for both arms and both metrics.
- **S2 first-error**: BRIEF PREMISE MISMATCH — 0 non-null `error_type` fields in all 228 executor event files (`grep -c` non-null error_type: 0; obs text starting "ERROR": 0). Failures instead surface as observation text starting `Execution failed` [grep -c on observation lines: fixed_k 644, sft 689]. Using that marker: 69 sft failures, 61 with a first error; fraction-of-episode min/p25/50/p75/max = 0.025/0.125/0.214/0.375/0.733; **67.2% fall in the first third**; 26.1% hit max_steps. fixed_k: 67 failures, 60 with error; 0.025/0.100/0.214/0.357/0.667; **73.3% first third**; 20.9% hit max_steps. Failures DO cluster early.
- **S3 planner steps**: n=114, 5/9/12/16/24; share shorter than 2/4/6/9 = 0.000/0.000/0.018/0.175. Grid at m=6,9 holds; m=2,4 empty.
- **S4 novelty** (regex `apis\.([a-z][a-z_0-9]*)\.([A-Za-z_][A-Za-z_0-9]*)\s*\(`, first match per action code): miss rate planner 0.1784 (1530 actions), executor 0.1080 (4221). Novel share by position: planner 0.699/0.494/0.386/0.333/0.231 (bins 1-3/4-6/7-9/10-12/13-40); executor 0.664/0.512/0.454/0.333/0.120. Novelty decays with position in both arms — explicit PROXY, caveats in JSON note.
- **S5 per-app**: "not derivable" (task ids are AppWorld hashes; no app field without reading benchmark internals — forbidden).

## Claims / verification
- Every quoted string above reproduced by `grep -c` in this run, counts stated. [OBSERVED /tmp/x3_run5.log; campaign/results/failure_anatomy_dev_20260921.json]
- Brief's "observation payloads carry an error_type" is wrong for this data — error_type is always null; documented fallback used. [OBSERVED grep counts above]
- Hit_max_steps detection: actions >= run_start limits.max_steps with no done/truncated observation. [INFERRED convention]
