# STATUS R1 — hj8 port / scoped shutdown / identity health / ARMS

State: DONE
Updated: 2026-09-20

## Milestone 0 — start
- Read `campaign/workers/brief_R1_hj8_port.md`.
- Did not touch `scripts/pbs/b1_pilot.pbs`, `scripts/setup/branch_counterfactual.py`, `tests/unit/test_branch_counterfactual.py`, `scripts/analysis/*`, `docs/*`, `campaign/RUNS.md`, `README.md`, or `test_b1_pilot_guards.py`.
- Did not qsub any GPU job. Did not commit. Did not run git.

## Milestone 1 — code
- `src/sidekick/runner.py`: `resolve_executor_base_url` (env > yaml > default); `make_executor` uses it; `run_single` records `executor_base_url` in the run manifest.
- `tests/unit/test_vllm_base_url.py`: env wins / yaml wins / default / empty env / manifest field.
- `scripts/pbs/hj8_frontier.pbs`: per-job `VLLM_PORT`, `setsid`, group `kill -TERM/--KILL -- -PID`, identity `/v1/models` + pgid check, `trap kill_vllm EXIT`, ARMS override, walltime `10:00:00`, smoke escalation table, `HJ8_GUARD_SELFTEST`.
- Login-node `bash -n`: rc=0. `grep -c 8000` = 0; `grep -c pkill` = 0 [OBSERVED this session].

## Milestone 2 — validation
- Job **25558360.aqua** (cpu_inter, not a GPU job). Log: `/home/n12194778/.hpc-spool/20260920-132053-2325532.out`.
- Guards: `ALL_GUARDS_FIRED` [OBSERVED that log; `grep -c ALL_GUARDS_FIRED` = 1].
- Suite: **433 passed, 1 skipped, 1 warning in 34.99s** [OBSERVED that log; `grep -c '433 passed, 1 skipped'` = 1]. Baseline was 413 passed, 1 skipped; never fewer; zero failures. The extra tests are this unit's 5 plus others already in the worktree.

## Guard fire evidence (same job; `grep -c` of the quoted string)
- missing alias: `missing LoRA alias(es): sft_b_plus` count=2 [OBSERVED /home/n12194778/.hpc-spool/20260920-132053-2325532.out]
- foreign pgid: `held by pid=4242 pgid=99999, expected pgid=11111` count=2 [OBSERVED same]
- unknown stem: `unknown ARMS stem not_a_real_stem` count=2 [OBSERVED same]
- env URL: `GUARD_FIRED env_base_url` count=2 [OBSERVED same]
(count=2 is the FATAL/GUARD line plus the harness `GREP_NEEDLE` echo of the same string.)

## Resume
Unit complete. No further work unless the orchestrator asks.

## Constraints kept
- No GPU `qsub`. No `/scratch/.../results/` writes. No git. Login node: bash -n / grep only; python/pytest inside `hpc`.
