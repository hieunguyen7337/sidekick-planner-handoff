# STATUS A4 (U-V1) — feature_lr verifier wiring

**unit:** A4 / U-V1
**state:** done

## done
- `make_verifier` `feature_lr` branch returns bare `FeatureVerifier.load(path)` at `src/sidekick/runner.py:196`. Not a `ThresholdRouter`. Did not add `.score` to `ThresholdRouter`.
- New `tests/unit/test_make_verifier.py` (9 tests) goes through `make_verifier` for `feature_lr`, `self_p_ask`, `scores`, and default; wraps like `router_seq`; compares like the sidekick ASK gate; checks `system_kwargs["verifier_threshold"]`; plus mock episodes on both arms.
- Did not touch `configs/`, `scripts/`, training, `loop.py`, or `verifier.py`. Did not commit. Zero planner calls. No GPU job. No `/scratch/.../results/` writes.

## pytest (verbatim)

Job `25449961.aqua` on a compute node, 75s wall, pytest 22.14s.
Interpreter `/scratch/n12194778/sidekick/env/bin/python`.

```
.....................................s.................................. [ 20%]
........................................................................ [ 40%]
........................................................................ [ 60%]
........................................................................ [ 80%]
.......................................................................  [100%]
=============================== warnings summary ===============================
tests/unit/test_feature_verifier.py::test_failed_join_is_dropped_not_fitted
  /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
358 passed, 1 skipped, 1 warning in 22.14s
```

Baseline was 349 passed, 1 skipped. 349 + 9 new tests = 358. Never fewer, never a failure. [OBSERVED hpc job 25449961.aqua]

Full job log: `/home/n12194778/.hpc-spool/20260919-002604-1226946.out`

## branches of make_verifier (all have .score)
- `scores` → `ScriptedVerifier.score` [OBSERVED src/sidekick/agents/verifier.py:33] [OBSERVED src/sidekick/runner.py:182-183]
- `self_p_ask` / `self` → `SelfVerifier.score` [OBSERVED src/sidekick/agents/verifier.py:265] [OBSERVED src/sidekick/runner.py:185-186]
- `feature_lr` → `FeatureVerifier.score` [OBSERVED src/sidekick/agents/verifier.py:224] [OBSERVED src/sidekick/runner.py:196]
- default → `ConstantVerifier.score` [OBSERVED src/sidekick/agents/verifier.py:22] [OBSERVED src/sidekick/runner.py:197]

## how to resume
Nothing left. Re-run if needed:

`timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
