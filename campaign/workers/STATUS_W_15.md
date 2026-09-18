# STATUS — W-15 (crashed-branch recovery + planner cost visibility/budget)

Unit brief: `campaign/workers/brief_W15_recovery.md`
Owner file: `scripts/setup/branch_counterfactual.py` (only production file in scope)
Forbidden: `src/sidekick/agents/planner.py` (another worker owns it), `.git/`, `/scratch/.../results/`.

## Milestones

- [x] 1. Context gathered: read brief, `branch_counterfactual.py` in full, test file, `RunResult`
      (`src/sidekick/protocols/schemas.py:141` carries `n_planner_calls`; `:145` carries
      `totals` from `CostLedger.totals()`), ledger keys
      (`src/sidekick/cost/ledger.py:40-41` give `planner_tokens_total` / `planner_calls_total`).
- [x] 2. STATUS written (this file).
- [x] 3. Implement Defect 1 fix (done excludes error rows; last-wins; `--no-retry-errors`).
- [x] 4. Implement Defect 2 (per-branch planner cost fields, preflight line, campaign budget).
- [x] 5. Add the 5 required pytest cases to `tests/unit/test_branch_counterfactual.py`.
- [x] 6. Run suite in a PBS job; real output below.
- [x] 7. Final report (diff pointers, path:line citations).

## Test result (verbatim, PBS job 25422328, 2026-09-18)

```
347 passed, 1 skipped, 1 warning in 22.69s
```

`PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib`,
run inside `timeout 880 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '...'` (never on the login node).
Two earlier runs during development: `7 failed, 340 passed, 1 skipped` and
`1 failed, 346 passed, 1 skipped` — failures were my own new tests (mock env returns no GPR,
wrong point_key in a test fixture, a wrong n_jobs expectation), each fixed and re-run.
One intermediate run also showed `test_feature_verifier.py::test_fit_temperature_never_worse_than_one`
failing — that file is not in this unit's scope and was not touched; it passed on the final run.

## Deviation from the brief's "done" criterion (recorded, not silently changed)

The brief's criterion `branch_gpr is not None and branch_error_type falsy` would, under the
mock environment used by the suite (and any env that returns no GPR), make every *successful*
row look not-done (`branch_gpr: null` with `branch_error_type: null` was observed on mock
rows during run 1) and re-dispatch them forever, breaking three pre-existing resume tests.
`is_done_row` therefore requires `branch_error_type` falsy AND (`branch_gpr is not None` OR
`branch_steps is not None`). Every production crash row still fails this
(`branch_gpr: null`, `branch_error_type: "crash"`, `branch_steps: null`
[OBSERVED scripts/setup/branch_counterfactual.py:980-985]), so the defect is fixed; only the
GPR-less-success corner is treated as done.

## Resume state

If this session dies: steps 3-5 are edits to the two files above only; step 6 is
`timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`.
No real codex calls, no GPU jobs, no /scratch writes anywhere in the plan.

## Notes / decisions

- Planner-cost source (primary): the branch's own episode `result.json` —
  `n_planner_calls` [OBSERVED src/sidekick/protocols/schemas.py:141] and
  `totals["planner_tokens_total"]` [OBSERVED src/sidekick/cost/ledger.py:40].
  Fallback: sum `usage` over `actor == "planner"` events in the branch run's own
  `events.jsonl`. `None` (never silent 0) when neither is available.
- `completed_branch_keys` gains a `retry_errors` keyword and becomes last-wins per key,
  matching `group_branch_samples` last-wins [OBSERVED scripts/setup/branch_counterfactual.py:631].
  Both call sites in this script updated; old behaviour reachable via `--no-retry-errors`.
- Budget dispatch: sequential path checks before each branch; pool path dispatches in
  waves of `workers` and checks between waves (in-flight branches finish normally).
  Unknown per-branch cost is counted conservatively at the per-branch factor, not 0.
