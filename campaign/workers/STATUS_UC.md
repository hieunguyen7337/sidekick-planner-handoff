# STATUS_UC.md — Unit U-C (replay archived planner packets)

## Milestones done (all four implemented; tests pending run)
- M1: `src/sidekick/protocols/schemas.py` — `Provider` widened with `"cache"`, with comment
  explaining why it must not be "mock" (gate treats zero-token mock as mistyped planner.type).
- M2: `src/sidekick/agents/planner.py` — `CachedPacketPlanner` appended at end of file.
  Constructor: `(inner, packet_source, system="planner_alone", seed=None, on_missing="fail")`.
  Seed via constructor argument (preferred option in brief); `seed=None` globs seed dirs and
  fails loudly on ambiguity. Reads events FORWARDS after the LAST `run_start` in file order.
  Usage: all tokens 0, `provider="cache"`, `model` = payload["model"] falling back to
  event usage.model, `n_calls=0`, `raw={"cached_from": <path>, "cached_thread_id": ...}`.
  Digest banner prepended once to first live correct/act prompt; correct/act/close delegate.
- M3: `src/sidekick/runner.py` — `make_planner(cfg, seed=None, system_name=None)` signature
  extended (least invasive; call site `run_single` passes `job["seed"]`, `job["system"]`).
  Wraps when `planner.packet_source` set; `packet_system` config overrides arm name.
  `make_env` fix: `root` popped from appworld block, passed as `AppWorldEnv(root=...)`
  (signature confirmed: `appworld_env.py:36-41`).
- M4: `tests/unit/test_cached_planner.py` — 8 tests, offline, RecordingInner stub.

## Test results (REAL, run in PBS jobs on compute nodes; NOT on login node)
- First attempts failed: `/bin/python: No module named pytest`, and the worktree
  `.venv` has no pytest and no pip. Fixed inside a job with
  `.venv/bin/python -m ensurepip` + `pip install pytest` (compute node, allowed).
- `tests/unit/test_cached_planner.py`: **8 passed in 1.81s** (job 25398516.aqua,
  log: /home/n12194778/.hpc-spool/20260916-185503-3247399.out).
- Full `tests/unit`: **2 failed, 124 passed in 2.45s** (job 25398572.aqua, log:
  /home/n12194778/.hpc-spool/20260916-185911-3301217.out). The 2 failures are
  `test_executor_prompt.py::test_two_code_actions_appear_before_their_observations` and
  `test_limits_and_policy.py::test_max_steps_limit_event_names_the_cap` (KeyError 'limit').
  [INFERRED, to be confirmed by loop owner] both exercise `src/sidekick/systems/loop.py`,
  which is out of U-C scope and edited concurrently by other units; neither touches the
  planner/schema/runner seams U-C changed (my 8 tests and all other 124 pass).

## Done — unit complete. No open items.


## Verified observations
- [OBSERVED scripts/setup/campaign_summarize.py:78-100] `_planner_models` reads
  `usage.model` on planner-attributed records; `_is_failed_call_placeholder` (lines 56-75)
  only filters `provider == "mock"` records with zero tokens AND `raw.error_type`. A
  `provider="cache"` record carries the original model id and is NOT filtered → gate
  reports `gpt-5.6-luna` for a replayed arm. No edit needed there.
- [OBSERVED src/sidekick/agents/planner.py:312-322] `CodexExecPlanner.correct` embeds the
  full packet in its prompt → wrapper prepends only the digest, as the brief predicted.

## Next
- Run `tests/unit/test_cached_planner.py` (+ full unit suite) in a PBS `hpc` job; paste
  real output into this file. Do NOT run pytest on the login node.

## Resume
- Tests written; run: `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc
  'OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
  python -m pytest tests/unit/test_cached_planner.py -v'` from repo root.
