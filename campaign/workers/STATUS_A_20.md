# STATUS A20 (U-B1PBS)

State: DONE
Updated: 2026-09-19

## Milestone
- Wrote this STATUS as first action.
- Wrote `scripts/pbs/b1_pilot.pbs` (hj6 structure + §13 invocation + three independent guards + `SMOKE_ONLY`).
- Harness under `campaign/workers/scratch_A20/` (not `tests/`).
- `bash -n` rc=0. Guards all fired on bad input (job 25491633.aqua).
- Suite: **413 passed, 1 skipped** (same job).
- Report: `campaign/workers/A20_B1_PBS.md`.
- Did not qsub the GPU pilot. Did not invoke `codex`. Did not commit. Did not write under `/scratch/.../results/`.

## Files owned
- `scripts/pbs/b1_pilot.pbs`
- `campaign/workers/A20_B1_PBS.md`
- `campaign/workers/STATUS_A_20.md` (this)
- `campaign/workers/scratch_A20/`

## Constraints in force
- Zero planner calls. Do not invoke `codex`. Do not submit this job or any GPU job.
- Do not touch `docs/prereg_b1_pilot.md`, `scripts/setup/branch_counterfactual.py`, `campaign/workers/scratch_A16/run_b1_pilot.py`, `src/`, `configs/`, or any other `scripts/pbs/` file.
- Do not commit. Do not run git.
- Login node: no Python/pytest; compute via `timeout 900 hpc ...`.
