# STATUS — W-21 (planner-token fallback + J6 log-path collision)

Unit brief: `campaign/workers/brief_W21_fixes.md`

**Do not commit. Do not submit `hj6_branches.pbs`. Zero planner calls. No GPU qsub.**

## Resume state

- **Milestone:** complete. Tests run. Waiting for orchestrator review/commit.
- **PBS pytest [OBSERVED]:** job `25433187.aqua` → `349 passed, 1 skipped, 1 warning in 22.54s` (zero failures).
- Log: `/home/n12194778/.hpc-spool/20260918-145747-180762.out`

## Owned files (written)

- `scripts/setup/branch_counterfactual.py` — `planner_cost_from_events` four-field token sum + `n_calls==0` stays 0
- `tests/unit/test_branch_counterfactual.py` — two new tests
- `scripts/pbs/hj6_branches.pbs` — CID+jobid logs; `#PBS -o` is the logs directory
- `campaign/workers/STATUS_W_21.md`

## Test result (verbatim, PBS job 25433187, 2026-09-18)

```
349 passed, 1 skipped, 1 warning in 22.54s
```

`PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib`,
run inside `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '...'` (never on the login node).
Prior baseline was 347 passed, 1 skipped; +2 tests in this unit.

## Pointers

- Token sum: `scripts/setup/branch_counterfactual.py:845` (`CostLedger._tokens`)
- `n_calls`: `scripts/setup/branch_counterfactual.py:840-843`
- Output_Path: `#PBS -o` directory at `scripts/pbs/hj6_branches.pbs:15` plus live `exec` to `${CID}.${JOBTAG}.out` at `:43`

## Output_Path approach

PBS evaluates `#PBS -o` at submit and cannot interpolate CID. Copy-at-exit of PBS's Output_Path is also unreliable (mom often writes `.OU` only after the job ends). So:

1. `#PBS -o …/campaign/workers/logs/` (no filename) → PBS writes unique `<job ID>.OU` [OBSERVED `man qsub`: "If path does not include a filename, the default filename has the form <job ID>.OU"]. Train/dev/resume cannot share Output_Path. A job that dies before the script starts still leaves that file.
2. As soon as CID is known, `exec >> ${CID}.${PBS_JOBID}.out` so an early death after startup still leaves a campaign-id log.
3. `VLOG=${LOGDIR}/${CID}.${JOBTAG}_vllm.log` — same uniqueness.

Did not rely on `qsub -o ${CID}.out` alone: a naive `qsub scripts/pbs/hj6_branches.pbs` would still collide, and a resume of the same CID would overwrite.

## Notes

- Accidental held STDIN job `25433171.aqua` from a `qsub -h` man-page lookup; `qdel`'d immediately; never ran.
