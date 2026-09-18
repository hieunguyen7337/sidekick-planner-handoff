# STATUS A-12 — J10 analysis script (written before the data)

**Task:** `campaign/workers/brief_A12_j10_analysis.md`
**Status:** DONE
**Ownership:** `scripts/analysis/j10_report.py`, `tests/unit/test_j10_report.py`,
`campaign/workers/A12_J10_ANALYSIS.md`, `campaign/workers/a12_dryrun_dev.py`,
`campaign/workers/a12_dryrun/`, this file.
Did not / will not touch `src/`, `configs/`, `scripts/pbs/`,
`scripts/setup/branch_counterfactual.py`, `scripts/setup/state_probe.py`,
`scripts/setup/hj1_gate.py`, `scripts/setup/verify_configs.py`,
`src/sidekick/systems/loop.py`, `docs/prereg_v1.md`.

**Do not commit. Zero planner calls. No GPU job. No `/scratch/.../results/` writes.
No `test_normal` / `test_challenge` reads.**

## Resume state

- [x] M0 brief read; STATUS written.
- [x] M1 prereg §2.2 / §3 / §7.2 + existing analysis conventions read; ambiguities listed (not resolved).
- [x] M2 script + unit tests written (refuse on test split without flag; missing ≠ 0).
- [x] M3 pytest via `hpc` (390 passed, 1 skipped, 0 failed; never fewer than 365/1).
- [x] M4 dry-run on **dev** archives only (`hj3_*`, `hj4b_*`, `hj1*`); plumbing check labelled as such.
- [x] M5 `A12_J10_ANALYSIS.md` written with resampling unit, missing-data handling, verbatim dry-run output.

## pytest (verbatim)

Job `25452369.aqua`:

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

```
390 passed, 1 skipped, 1 warning in 22.60s
```

`tests/unit/test_j10_report.py` only, job `25452348.aqua`: `16 passed in 8.71s`.

## Dev dry-run (verbatim headlines)

Job `25452526.aqua`. Scratch results were read, never written.

```
PLUMBING CHECK, NOT A RESULT. COMPLETE matrix; hypothesis decisions follow.
PLUMBING CHECK, NOT A RESULT. INCOMPLETE: missing_arm:sidekick
PLUMBING CHECK, NOT A RESULT. INCOMPLETE: incomplete_arm:sidekick; unequal_cluster_sizes:sidekick
PLUMBING CHECK, NOT A RESULT. COMPLETE matrix; hypothesis decisions follow.
```

JSON: `campaign/workers/a12_dryrun/{A_complete_standin,B_missing_arm,C_missing_metric,D_crashed_episode}.json`.
Report: `campaign/workers/A12_J10_ANALYSIS.md`.

## Notes

Resampling unit is **task**. Missing `tgc` is `null`, not 0. Eleven prereg ambiguities
are listed in the script and the report and were not resolved in code.
