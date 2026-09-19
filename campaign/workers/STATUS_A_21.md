# STATUS A21 — resume-aware 1600-branch guard

**Unit:** A21 (U-B1PBS2)
**State:** DONE (2026-09-19)

## Milestone

- Wrote this STATUS as first action.
- Replaced A20's `branches_to_run == 1600` with sample identity: fresh `to_run==1600`; resume `completed_branch_keys + to_run == 1600` (`to_run < 1600`); `> 1600` gets the foreign-branches FATAL. 6216 and cap≠10000 still fatal on both paths.
- Completed count uses `completed_branch_keys(load_jsonl(...))`, not raw lines.
- `OPERATOR_CONFIRM` line added. Grep-for-PREFLIGHT loop unchanged. Prereg not edited.
- Login `bash -n` rc=0. Job **25499131.aqua**: harness `n_pass=18 n_fail=0`; suite **413 passed, 1 skipped**.
- Report: `campaign/workers/A21_RESUME_GUARD.md`.
- Did not qsub the GPU pilot. Did not invoke `codex`. Did not commit. Did not write under `/scratch/.../results/`.

## Files owned

- `scripts/pbs/b1_pilot.pbs`
- `campaign/workers/scratch_A20/`
- `campaign/workers/A21_RESUME_GUARD.md`
- `campaign/workers/STATUS_A_21.md` (this)

## Constraints in force

- Zero planner calls. Do not invoke `codex`. Do not submit the B1 job or any GPU job.
- Do not touch `docs/prereg_b1_pilot.md`, `scripts/setup/branch_counterfactual.py`, `campaign/workers/scratch_A16/run_b1_pilot.py`, `src/`, `configs/`, or any other `scripts/pbs/` file.
- Do not commit. Do not run git.
- Login node: no Python/pytest; compute via `timeout 900 hpc ...`.
