# STATUS_X1 — prefix-handoff runtime

State: **done**. No commit (brief). No GPU, no eval, no `/scratch/.../results` writes.

## Files

Create:
- `src/sidekick/prefix_source.py` — `HandoffPrefix`; `build_handoff_prefix(source_campaign, source_system, task_id, seed, m, env) -> HandoffPrefix`. Added `notes: list[str]` (brief required notes entries; dataclass omitted the field).
- `src/sidekick/systems/prefix_handoff.py` — `PrefixHandoff.__init__(planner, executor=None, verifier=None, limits=None, policy=None, source_campaign=None, source_system="planner_alone", m=0, adapter_name=None, **kwargs)`; `run(env, task_id, seed, log, ledger, prefix=None) -> RunResult`.
- `tests/unit/test_prefix_handoff.py` — seven tests.

Modify:
- `src/sidekick/systems/__init__.py` — import/`SYSTEM_NAMES`/`SYSTEMS`/`__all__` append `prefix_handoff` (10th).
- `src/sidekick/runner.py` — `system_kwargs` block for `prefix_handoff`. **Did not** add it to the adapter tuple at `:242`; the dedicated block already sets `adapter_name`.
- `tests/integration/test_eight_systems_mock.py` — exact tuple now includes `prefix_handoff`. Not owned; required because the file asserts equality, not an 8-name prefix. [OBSERVED tests/integration/test_eight_systems_mock.py:9-20]

## EventType

Chose **`report`** (`actor="system"`). Closed Literal [OBSERVED src/sidekick/protocols/schemas.py:106-109]; `run_start` is emitted by `run_episode` [OBSERVED src/sidekick/systems/loop.py:612-618]; `intervention` would confound intervention counts [OBSERVED src/sidekick/systems/loop.py:133-134]; `error` is the broken path. Injected immediately after the first `run_start` so last-attempt slices still see the payload keys.

Broken episodes: `RunResult.error_type="crash"` (`BROKEN` set). [OBSERVED scripts/setup/campaign_summarize.py:33] Not scored: no `evaluate`.

## Brief vs source

- Tests assert the **full** `SYSTEM_NAMES` tuple, then run every name expecting success. Unconfigured `source_campaign` (None/empty) falls through to `super().run()`; a configured missing path is `missing_source`. [INFERRED needed for `test_all_eight_systems_complete_on_mock` / `test_runner_all_eight_systems`]
- `replay_prefix` with `k=0` returns `remaining=[]` [OBSERVED src/sidekick/replay.py:107]; prefix_source special-cases `effective_m==0`.
- Docstring quotes `replay.py:15-20`: `snapshot_hash` is observation-IO sha256, visible divergence only, not a DB dump. MockEnv hashes file state [OBSERVED src/sidekick/environments/mock_env.py:90-96].
- `plan_first` does not call `planner.plan` when `prefix is not None`. [OBSERVED src/sidekick/systems/loop.py:627]
- Token formula: `input + output + reasoning`; `cached_input_tokens` not added. Fixture exact integer **188**.
- `prefix_source` lazily imports `EpisodePrefix` to avoid a circular import through `systems/__init__.py`.
- X2 also edits `__init__.py` / `runner.py` (not present at finish). X5 `j8_frontier.py` was mid-edit (`root` NameError) during an earlier suite run; later run was green.

## Suite

```
timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

Verbatim final line [OBSERVED /home/n12194778/.hpc-spool/20260921-115638-456937.out]:

```
463 passed, 1 skipped, 1 warning in 36.84s
```

Job `25596411.aqua`. Earlier isolated `tests/unit/test_prefix_handoff.py`: `7 passed` [OBSERVED /home/n12194778/.hpc-spool/20260921-115600-455526.out].
