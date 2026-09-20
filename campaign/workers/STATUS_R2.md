# STATUS R2 — B1 outcome smoke gate / live-call cap / port contract

State: DONE
Updated: 2026-09-20

## Milestone 0 — start
- Read `campaign/workers/brief_R2_b1_gate.md` and `campaign/briefs/SEAM_CONTRACT.md`.

## Milestone 1 — code in place
- `scripts/setup/branch_counterfactual.py`: live `totals.planner_calls_total` on rows as `branch_live_planner_calls`; `branch_error_detail` from first error event; cap sums live calls (missing/None → `planner_factor`). `branch_planner_calls` still replay-inclusive.
- `scripts/pbs/b1_pilot.pbs`: C1 port/setsid/group-kill/trap/identity; smoke gate FATALS on error / no live step / zero tokens; `SMOKE_TARGET_ROWS` 16→32 (2 points → 4 points × 2 × 4 seeds).
- Guards: original 18 kept; added smoke + C1 cases.

## Milestone 2 — validation
- Job **25558482.aqua** (`/home/n12194778/.hpc-spool/20260920-132250-2367987.out`).
- Login `bash -n` rc=0. `grep -c 8000` = 0. `grep -c pkill` = 0. `grep -c SMOKE_TARGET_ROWS=32` = 1. [OBSERVED login grep 2026-09-20]
- Harness: `n_pass=24 n_fail=0` `ALL_GUARDS_FIRED` [OBSERVED spool: `grep -c 'n_pass=24 n_fail=0'` = 1]
- Smoke gates fired on crafted jsonl: error-type, no live step, zero tokens [OBSERVED spool `grep -c` each FATAL = 1]
- Port pick: `vllm_port=39712` for `PBS_JOBID=25519712.aqua` [OBSERVED spool:85]
- Suite: `433 passed, 1 skipped, 1 warning in 28.42s` [OBSERVED spool:104]
- Did not qsub GPU, did not edit `docs/prereg_b1_pilot.md`, did not touch R1 files.

## Resume
Done. If re-opened: do not re-run GPU; do not commit.

