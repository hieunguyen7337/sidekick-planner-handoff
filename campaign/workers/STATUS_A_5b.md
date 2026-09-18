# STATUS A-5b — J8 frontier configs (re-issue)

**Task:** `campaign/workers/brief_A5b_j8_configs.md`
**Status:** DONE (2026-09-19)
**Ownership:** `configs/*.yaml`, `scripts/setup/verify_configs.py` and its test, this file.
Did not touch `src/sidekick/runner.py`, `src/sidekick/agents/`, `scripts/pbs/`,
`scripts/setup/fit_value_function.py`, `scripts/setup/branch_counterfactual.py`.

**Do not commit. Zero planner calls. No GPU job. No `/scratch/.../results/` writes.**

## Resume state

- [x] M0 brief read; STATUS written.
- [x] M1 existing configs + runner facts checked (on_missing reaches ctor; FeatureVerifier.load is a file; oracle_labels is inline).
- [x] M2 oracle_labels.json transcribed into configs/hj8_oracle_escalation.yaml (empty lists kept; missing keys not invented).
- [x] M3 12 hj8 YAML files on disk.
- [x] M4 `verify_configs.py` run; exit 0. Did not change the script.
- [x] M5 optional `max_prompt_tokens` presence check already present; reported, not duplicated.
- [x] M6 pytest via `hpc`: 365 passed, 1 skipped.
- [x] M7 this STATUS updated with verbatim outputs.

## Configs created (12)

| file | campaign_id | notes |
|---|---|---|
| configs/hj8_executor_alone_bplus.yaml | hj8_executor_alone_bplus_20260919 | mock planner; no packet_source |
| configs/hj8_sft_plan_bplus.yaml | hj8_sft_plan_bplus_20260919 | packet_source + on_missing: fail |
| configs/hj8_fixed_k_{3,5,10}.yaml | hj8_fixed_k_{3,5,10}_20260919 | `fixed_k:` per file; cached plan, live reviews |
| configs/hj8_router_seq_tau{03,05,07}.yaml | hj8_router_seq_tau{03,05,07}_20260919 | feature_lr → weights.json |
| configs/hj8_sidekick_tau{03,05,07}.yaml | hj8_sidekick_tau{03,05,07}_20260919 | self_p_ask on sft_b_plus, not sft_c |
| configs/hj8_oracle_escalation.yaml | hj8_oracle_escalation_20260919 | 106 oracle_labels keys inlined |

Did not copy `hj4_correction_train_20260917` into any of these.

## Design note (live arms + packet_source)

The brief named `packet_source` only on sft_plan. I also set it (with `on_missing: fail`) on every plan_first live arm, matching `configs/hj4b_fixed_k_dev.yaml`. Rationale: `CachedPacketPlanner.correct` / `act` still forward to the inner Codex planner, so reviews/escalations remain live, the up-front plan matches sft_plan, and a plan cache miss aborts instead of spending. If the orchestrator wanted fully live `plan()` calls, drop `packet_source` from the ten live configs.

## Three facts — honoured, tree agrees

1. `on_missing` reaches `CachedPacketPlanner` at `src/sidekick/runner.py:147`. Literal: `on_missing: fail` (`configs/hj8_sft_plan_bplus.yaml:20`).
2. `FeatureVerifier.load` reads a JSON file (`src/sidekick/agents/verifier.py:229`). Literal: `path: /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/artifacts/verifiers/feature_lr_20260918/weights.json` (`configs/hj8_router_seq_tau03.yaml:37`).
3. Runner indexes `cfg.get("oracle_labels")` (`src/sidekick/runner.py:226-232`). Inlined; no path key. Roundtrip vs the scratch JSON: 106 keys, `equal True` (job 25451871.aqua). Empty lists kept; absent pairs not invented.

Nothing in the tree contradicted the three facts.

## verify_configs.py

Did **not** edit `scripts/setup/verify_configs.py` or `tests/unit/test_verify_configs_prompt_budget.py`.

The prompt-budget presence check the brief asked about is already there (`validate_prompt_budget`, lines 68-71) plus seven unit tests. Frozen pilots omit the key and sit on `FROZEN_PILOT_ALLOWLIST` (lines 20-28). Adding a stricter check would fail those seven; brief says report rather than mass-edit frozen configs. All twelve new configs set `executor.max_prompt_tokens: 30720`.

The brief said the script currently exits non-zero. I did not snapshot a pre-write run. After the twelve files existed it exited 0 (job 25451871.aqua). [INFERRED] the in-tree allowlist + hj3/hj4 keys already made the old failure impossible before this unit.

### verify_configs.py verbatim (job 25451871.aqua)

```
configs/pilot_exec_8b.yaml
  executor -> vllm-executor
  planner  -> MockPlanner
  chat_template_kwargs -> {'enable_thinking': False}
  stop -> ['</py>', '</python>', '</tool_call>']
  max_tokens -> 2048

configs/pilot_exec_3b.yaml
  executor -> vllm-executor
  planner  -> MockPlanner
  chat_template_kwargs -> {'enable_thinking': False}
  stop -> ['</py>', '</python>', '</tool_call>']
  max_tokens -> 2048

configs/pilot_planner_alone.yaml
  executor -> mock-executor
  planner  -> CodexExecPlanner
  planner model -> ?

configs/pilot_prompt_only.yaml
  executor -> vllm-executor
  planner  -> CodexExecPlanner
  stop -> ['</py>', '</python>', '</tool_call>']
  chat_template_kwargs -> {'enable_thinking': False}

configs/pilot_fixed_k.yaml
  executor -> vllm-executor
  planner  -> CodexExecPlanner
  stop -> ['</py>', '</python>', '</tool_call>']
  chat_template_kwargs -> {'enable_thinking': False}

configs/hj4_correction.yaml
  executor -> vllm-executor
  planner  -> CachedPacketPlanner
  stop -> ['</py>', '</python>', '</tool_call>']
  chat_template_kwargs -> {'enable_thinking': False}

configs/hj1r_prompt_only.yaml
  packet subtree -> planner_alone

configs/hj3_sft_plan.yaml
  packet subtree -> planner_alone

configs/hj4_correction.yaml
  packet subtree -> planner_alone

configs/hj4b_fixed_k_dev.yaml
  packet subtree -> planner_alone

configs/hj8_fixed_k_10.yaml
  packet subtree -> planner_alone

configs/hj8_fixed_k_3.yaml
  packet subtree -> planner_alone

configs/hj8_fixed_k_5.yaml
  packet subtree -> planner_alone

configs/hj8_oracle_escalation.yaml
  packet subtree -> planner_alone

configs/hj8_router_seq_tau03.yaml
  packet subtree -> planner_alone

configs/hj8_router_seq_tau05.yaml
  packet subtree -> planner_alone

configs/hj8_router_seq_tau07.yaml
  packet subtree -> planner_alone

configs/hj8_sft_plan_bplus.yaml
  packet subtree -> planner_alone

configs/hj8_sidekick_tau03.yaml
  packet subtree -> planner_alone

configs/hj8_sidekick_tau05.yaml
  packet subtree -> planner_alone

configs/hj8_sidekick_tau07.yaml
  packet subtree -> planner_alone

all configs OK
```

VERIFY_EXIT=0

## pytest (verbatim)

Job `25451933.aqua`. Interpreter `/scratch/n12194778/sidekick/env/bin/python`.

```
.....................................s.................................. [ 19%]
........................................................................ [ 39%]
........................................................................ [ 59%]
........................................................................ [ 78%]
........................................................................ [ 98%]
......                                                                   [100%]
=============================== warnings summary ===============================
tests/unit/test_feature_verifier.py::test_failed_join_is_dropped_not_fitted
  /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
365 passed, 1 skipped, 1 warning in 20.55s
```

Baseline 365 passed, 1 skipped. Never fewer, never a failure. [OBSERVED job 25451933.aqua]

## Checks not done

Did not qsub a GPU job. Did not invoke `codex`. Did not write under `/scratch/.../results/`. Did not commit.
