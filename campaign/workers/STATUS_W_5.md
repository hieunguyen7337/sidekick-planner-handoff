# STATUS W-5 — executor P(ASK) gate

**state:** complete
**resume:** implementation and tests landed. No commit. No qsub.

## owned / touched

- `src/sidekick/protocols/schemas.py` — `Usage.p_ask: Optional[float] = None`
- `src/sidekick/agents/executor.py` — first-token logprobs → `p_ask`; `ban_ask_prefix` logit_bias
- `src/sidekick/agents/verifier.py` — `SelfVerifier` appended after W-4 `FeatureVerifier`
- `src/sidekick/agents/__init__.py` — export `SelfVerifier`
- `src/sidekick/systems/loop.py` — `trajectory_state["p_ask"]`; self-gated one-shot re-decode
- `src/sidekick/runner.py` — `verifier.kind: self_p_ask` and nested `threshold`
- `tests/unit/test_p_ask_gate.py` — 22 tests
- this STATUS file

## objection (implemented the brief anyway)

campaign/RUNS.md §3 says first-token ASK mass is a correlate and wants the conditional sequence probability of the full ASK prefix. The W-5 brief requires first-token top-k mass. Code follows the brief. [OBSERVED campaign/RUNS.md:1561-1573] [OBSERVED campaign/workers/brief_W5_pask_gate.md:49-58]

Action payloads now carry `p_ask`, so event JSON is not byte-identical to pre-W-5 logs. Ungated ASK_IGNORED control flow (no re-decode) is unchanged. [INFERRED]

## pytest [OBSERVED]

Prescribed command, via `hpc-py` (no PBS/`qsub`):

```
hpc-py -m pytest tests -q --import-mode=importlib
```

verbatim last line: `12 failed, 313 passed, 1 skipped in 19.14s`

All 12 failures are W-4's `tests/unit/test_feature_verifier.py` (`fit._extractor_features` missing on the fit module; auroc/token_leak mismatches). W-5 did not edit that file.

W-5-only recheck (same runner, `--ignore=tests/unit/test_feature_verifier.py`):

verbatim last line: `308 passed, 1 skipped in 13.65s`

That is baseline 286 + 22 W-5 tests, 0 failures. [OBSERVED]

W-5 file alone: `22 passed in 1.23s`

## return contract lines

- computed: `src/sidekick/agents/executor.py:318` (`p_ask_from_choice` at `:107`, returns mass or None at `:113-126`)
- recorded: `src/sidekick/systems/loop.py:488` (action payload); also `Usage.p_ask` at `executor.py:335`
- None vs 0.0: `executor.py:116` (no logprobs → None, else mass including 0.0); `schemas.py:37`; `verifier.py:267-269` (`is None` → +inf, `0.0` stays 0.0); `loop.py:489`

---

# W-5b — P(ASK) instrumentation strictly opt-in

**state:** complete
**resume:** implementation and tests landed. No commit. No GPU qsub.

## owned / touched (this unit)

- `src/sidekick/agents/executor.py` — `VLLMExecutor.logprobs` defaults False; request fields only if opted in
- `src/sidekick/systems/loop.py` — `p_ask` / `p_ask_fallback` on action/ask payloads only when `SelfVerifier`; `complete(..., logprobs=True)` on that path
- `src/sidekick/runner.py` — `make_executor` sets `logprobs=True` when `verifier.kind` is `self_p_ask` / `self`. No new config key.
- `tests/unit/test_p_ask_gate.py` — four new opt-in tests; existing W-5 tests kept
- this STATUS file

## notes

- `trajectory_state["p_ask"]` stays unconditional. It is only passed to `verifier.score` / `router.should_escalate`; not written to `events.jsonl`. [OBSERVED src/sidekick/systems/loop.py:515] [OBSERVED src/sidekick/systems/loop.py:691] [OBSERVED src/sidekick/systems/loop.py:786]
- None vs 0.0 on the self-gate path is unchanged: absent key = off; `null` = on unmeasurable; `0.0` = measured zero. [INFERRED]

## pytest [OBSERVED]

Prescribed command (CPU queue, no GPU):

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

job `25414057.aqua` on `cpu_inter`. verbatim:

```
.................................s...................................... [ 21%]
........................................................................ [ 43%]
........................................................................ [ 65%]
........................................................................ [ 87%]
..........................................                               [100%]
329 passed, 1 skipped in 13.61s
```

That is prior 325 + 4 W-5b tests, 0 failures. [OBSERVED]

## return contract lines

- logprobs default: `src/sidekick/agents/executor.py:207` (`logprobs: bool = False`); applied at `:269` (`kw.get("logprobs", self.logprobs)`)
- event-key suppression: `src/sidekick/systems/loop.py:393-405` (`p_ask_event_fields`); applied at action `:504` and ask `:799`, `:834`, `:858`
- measurement on for sidekick: `src/sidekick/runner.py:158` (`verifier.kind` in `self_p_ask`/`self` → `VLLMExecutor(logprobs=True)` at `:175`); loop also passes `logprobs=True` when `SelfVerifier` at `loop.py:438-439`
