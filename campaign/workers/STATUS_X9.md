# STATUS_X9 — live harness and two recorded hazards

State: **done**. No commit, no `qsub`, no GPU, no `configs/` edits.

## MAX_PLANNER_CALLS = 3500

High-end table sum is 280+780+170+170+900 = 2300 hosted calls. Default **3500** is ~1.5× that: enough for variance (and cached-plan ledger ticks if `call_planner` rewrites `n_calls` to attempts [INFERRED src/sidekick/systems/loop.py:395-397]) without letting an every-step exception arm (~40×114 = 4560) launch the next one.

Spend ceiling reads **`ledger_totals.planner_calls_total`** [OBSERVED scripts/setup/campaign_summarize.py:152], not top-level `planner_calls_total` (replay-inclusive, :142) and not `planner_calls_live_total` (:146). After each arm the running total is incremented from that key; if it exceeds 3500 the job FATALs before the next arm.

## PBS

Created `scripts/pbs/hj12_live.pbs` from `hj12_prefix.pbs`. Kept per-job `VLLM_PORT=$(( 20000 + jobnum % 20000 ))`, `/v1/models` alias identity (brief said `/v1/records`; prefix/hj8 use `/v1/models` [OBSERVED scripts/pbs/hj12_live.pbs:437]), `setsid` + EXIT trap, no `pkill -f`, directory `#PBS -o/-e`, `ARMS`/`SMOKE_ONLY`, `--workers 6`, 3-task smoke. Inverted guard: each selected YAML must resolve `type: codex` and `model: gpt-5.6-luna` before any episode; `packet_source` is allowed (plan replay, live reviews). Always `--expect-planner --expect-model gpt-5.6-luna`. Per-arm table: episodes, live calls, calls/ep, planner-authored `action` events, `handoff_step` min/median/max/never. Takeover with 0 planner-authored actions: WARN on smoke, FATAL on full.

`bash -n scripts/pbs/hj12_live.pbs` [OBSERVED login-node]:

```
(stdout empty)
bash_n_exit=0
```

## 2a

Removed the `TypeError` swallow in `CachedPacketPlanner.act`; it calls `inner.act(..., allow_handoff=allow_handoff)` directly [OBSERVED src/sidekick/agents/planner.py:819-822]. `RecordingInner.act` lacked `allow_handoff`; updated the stub rather than keeping the swallow [OBSERVED tests/unit/test_cached_planner.py:111]. Added `test_act_propagates_inner_typeerror_without_dropping_allow_handoff`.

## FOLLOWUPS titles (appended; file not restructured)

- OPEN 2026-09-21 — the action-review gate will almost always replace
- OPEN 2026-09-21 — `HANDOFF` is matched as a whole line anywhere in the planner's output

## Suite [OBSERVED hpc 25607268.aqua]

```
485 passed, 1 skipped, 1 warning in 40.59s
```

Brief floor 483 not breached. This unit added one test [INFERRED].
