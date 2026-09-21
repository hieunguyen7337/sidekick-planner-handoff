# STATUS_X11 — within-arm spend guard

State: **done**. No commit, no `qsub`, no GPU, no eval, no `configs/` or `src/` edits. `MAX_PLANNER_CALLS` stayed **3780**; six `LIVE_ARMS` unchanged [OBSERVED scripts/pbs/hj12_live.pbs:72, :155-162].

## SAFETY = 1.2

Mid-range in 1.1–1.3 [OBSERVED :128-135]. Three smoke episodes are a noisy estimator; this only has to catch an order-of-magnitude overrun (never-handoff ~40 calls/ep × 114), not a precise budget. 20% pad against a lucky-low smoke, biased toward stopping [INFERRED].

## Projection

Smoke figure: `ledger_totals.planner_calls_total` / `n_runs` (never replay-inclusive `planner_calls_total`) [OBSERVED :649-670]. Formula: `ceil(cpe × N_FULL_TASKS × N_FULL_SEEDS × SAFETY)` with 57 × 2 × 1.2 [OBSERVED :670, :124-126]. After a passing smoke, before the full run [OBSERVED :991-998]. Printed on every smoked arm. FATAL before the full run when `RUNNING_PLANNER_CALLS + projection > MAX_PLANNER_CALLS`. `SMOKE_ONLY` prints and does not FATAL on it. Between-arm ceiling unchanged [OBSERVED :627-644].

```
[hj12] project ${stem}: smoke_key=ledger_totals.planner_calls_total smoke_live=${live} n_episodes=${n_ep} calls_per_episode=${cpe} n_full_tasks=${N_FULL_TASKS} n_seeds=${N_FULL_SEEDS} safety=${SAFETY} projection=${proj} running=${RUNNING_PLANNER_CALLS} ceiling=${MAX_PLANNER_CALLS}
[hj12] FATAL: arm ${stem} projected ${proj} live planner calls (${cpe} calls/ep from smoke) plus running ${RUNNING_PLANNER_CALLS} exceed MAX_PLANNER_CALLS=${MAX_PLANNER_CALLS}; not launching the full run
```

Runaway smoke 3×41 [OBSERVED tests/unit/test_hj12_within_arm_guard.py]: `projection=5609 running=0 ceiling=3780` then FATAL `projected 5609 ... (41.00 calls/ep from smoke) plus running 0 exceed MAX_PLANNER_CALLS=3780`.

## Zero-takeover on smoke

0 planner-authored `action` events [OBSERVED :791-821]:
- `fixed_k`: FATAL if any smoke `result.json` has `steps >= k` (`fixed_k:` in the YAML); else WARN that the smoke was uninformative.
- `router_seq`: FATAL if any episode contains `Execution failed. Traceback:` [OBSERVED src/sidekick/agents/verifier.py:56]; else WARN uninformative.
Full/complete still FATALs on zero actions with no gate test.

```
[hj12] FATAL: takeover arm ${stem} has 0 planner-authored action events on smoke and at least one episode could have triggered the ${reason} gate; ran the advise path; not launching the full run
[hj12] WARN: takeover arm ${stem} has 0 planner-authored action events on smoke — smoke was uninformative (no episode reached the ${reason} gate)
```

`reason` is `fixed_k steps>=k` or `exception marker`.

## bash -n [OBSERVED login-node]

```
(stdout empty)
bash_n_exit=0
```

## Suite [OBSERVED hpc 25607613.aqua]

```
498 passed, 1 skipped, 1 warning in 38.02s
```

X10 was 492; this unit added 6 tests [INFERRED].
