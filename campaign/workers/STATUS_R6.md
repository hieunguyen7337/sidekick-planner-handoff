# STATUS_R6 — B1 smoke gate taxonomy (limit/parse_error vs crash/api_error/timeout)

State: DONE
Updated: 2026-09-20
Job: **25559627.aqua** (`/home/n12194778/.hpc-spool/20260920-135551-2984622.out`)

## Milestone 0 — start

- Cause: gate FATALs on any non-null `branch_error_type`. Job `25559066` died on one healthy `limit` row after a live planner call [OBSERVED brief_R6_gate_taxonomy.md:11-23].
- Taxonomy: `limit | timeout | parse_error | crash | api_error | None` [OBSERVED src/sidekick/systems/loop.py:317, 346, 386, 438, 660; src/sidekick/protocols/schemas.py:126]. `limit` is budget exhaustion [OBSERVED loop.py:317, 660].

## Milestone 1 — code in place

- Fatal set `B1_SMOKE_FATAL_ERROR_TYPES=(crash api_error timeout)` [OBSERVED scripts/pbs/b1_pilot.pbs:46]. Both `print_smoke_spend` and `b1_smoke_error_count` take `"${B1_SMOKE_FATAL_ERROR_TYPES[@]}"` as argv [OBSERVED b1_pilot.pbs:236, 327].
- Spend line includes `error_type_counts=` for every type seen, both classes [OBSERVED b1_pilot.pbs:295-300].
- Ordinary `limit` / `parse_error` / `None` do not FATAL [OBSERVED b1_pilot.pbs:271-272, 344].
- Live-step and zero-token gates unchanged [OBSERVED b1_pilot.pbs:307-318].
- Did not edit `docs/prereg_b1_pilot.md`, `hj8_frontier.pbs`, `runner.py`, `branch_counterfactual.py`, or `scripts/analysis/*`.

## Milestone 2 — validation [OBSERVED spool 25559627]

Login `bash -n` rc=0 [OBSERVED login 2026-09-20]. Harness: `n_pass=36 n_fail=0` `ALL_GUARDS_FIRED`.

Six taxonomy cases (verbatim spend/FATAL lines):

```
PASS smoke_limit_ok
  | [b1] smoke spend: n_rows=1 ... error_type_counts=limit=1 ...
PASS smoke_parse_error_ok
  | [b1] smoke spend: n_rows=1 ... error_type_counts=parse_error=1 ...
PASS smoke_crash_fatal
  | [b1] FATAL: smoke gate: 1 rows with branch_error_type
  | [b1] smoke error_detail: HTTPStatusError: 404 The model 'sft_b' does not exist
PASS smoke_api_error_fatal
  | [b1] FATAL: smoke gate: 1 rows with branch_error_type
PASS smoke_timeout_fatal
  | [b1] FATAL: smoke gate: 1 rows with branch_error_type
PASS smoke_limit_plus_crash_fatal
  | [b1] smoke spend: n_rows=2 ... error_type_counts=crash=1,limit=1 ...
  | [b1] FATAL: smoke gate: 1 rows with branch_error_type
```

Prior cases still pass (3-crash details, no-live-step, zero-tokens, smoke_ok with `None=1`).

Suite final line: `433 passed, 1 skipped, 1 warning in 31.15s` [OBSERVED spool].

Did not commit, did not qsub a GPU job, did not write under `/scratch/.../results/`.
