# STATUS X18 — prefix terminal guard

## Files
- `src/sidekick/systems/loop.py` only (plus new `tests/unit/test_prefix_terminal_guard.py`).
- Did not edit `replay.py`, configs, `scripts/pbs/`, or `campaign/results/`. No git, no `qsub` of an evaluation.

## Policy
- Field: `SystemPolicy.post_prefix_terminal: Literal["stop", "continue"] = "stop"` [OBSERVED `src/sidekick/systems/loop.py:73`].
- `"stop"` is the default science; `"continue"` is the pre-guard loop.

## Guard
- Helper `prefix_is_terminal` is true if the rebuilt last obs has `done` or the last prefix **action** event is `COMPLETE` [OBSERVED `loop.py:163-171`].
- After `run_start` / token check, `skip_live_loop` is set only when `prefix is not None` and policy is `"stop"` and the prefix is terminal [OBSERVED `loop.py:706-718`]. The live `for` then `break`s before any executor call [OBSERVED `loop.py:717-718`]. `steps_taken` is `last_obs.step`.
- `"continue"` still enters the live loop. Each live **executor** action (not takeover `forced_action`) increments `n_post_terminal_actions` when the prefix was already terminal [OBSERVED `loop.py:924-925`].
- Empty-range `for`/`else` must not mark `"stop"` as `max_steps` limit [OBSERVED `loop.py:1088`].

## Recording
- `run_start`: when `prefix is not None`, `payload["policy"]["post_prefix_terminal"]` is written next to the existing `prefix` block [OBSERVED `loop.py:636-642`]. Omitted when `prefix is None`.
- `run_end`: `n_post_terminal_actions` only if `prefix is not None` (0 under `"stop"`) [OBSERVED `loop.py:1150-1151`].

## `prefix is None`
The guard does **not** change that path: `last_obs` still comes from `env.reset`; `skip_live_loop` stays False; `run_start` has no `prefix` / `post_prefix_terminal`; `run_end` has no `n_post_terminal_actions`. The extra `if skip_live_loop: break` is a false predicate. Fresh reset-`done` is not handled. [OBSERVED `loop.py:660`, tests `test_no_prefix_guard_is_noop`]

## SEAM_CONTRACT
Contract lists `review_proposed_action` / `takeover` / `handoff_allowed` only. `post_prefix_terminal` is not named there. Implemented as this brief specified anyway.

## Tests
1. `test_terminal_prefix_stop_asks_zero_executor_actions`
2. `test_terminal_prefix_continue_matches_legacy_and_counts_extra_actions`
3. `test_mid_episode_prefix_executor_runs_normally`
4. `test_no_prefix_guard_is_noop`
5. `test_run_start_records_post_prefix_terminal_policy`

X18 file [OBSERVED hpc 25679851.aqua]:
```
5 passed, 1 warning in 4.42s
```

Full suite [OBSERVED hpc 25679885.aqua]:
```
11 failed, 500 passed, 1 skipped, 1 warning in 40.39s
```
All 11 are `NameError: _attach_scenario_ci` in `scripts/analysis/j8_frontier.py` (X19 mid-edit; not this unit). Subtracting that file: 473 prior non-j8 + 5 new = 478 [INFERRED from 506 = 473+33 j8 tests]. Confirming ignore run [OBSERVED hpc 25680134.aqua]:
```
478 passed, 1 skipped, 1 warning in 36.24s
```
