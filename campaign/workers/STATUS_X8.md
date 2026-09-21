# STATUS_X8 — exception pair ids + router channel

State: **done**. No commit. No GPU, no eval, no `qsub`.

## hj12 campaign_id list vs `/scratch`

YAML ids (9, unique among themselves) [OBSERVED `timeout 30 grep -H '^campaign_id:' configs/hj12_*.yaml`]:

| file | campaign_id | exact dir on scratch? |
|---|---|---|
| `hj12_advise_exception.yaml` | `hj12_advise_exception_20260923` | miss |
| `hj12_takeover_exception.yaml` | `hj12_takeover_exception_20260923` | miss |
| `hj12_takeover_fixed_k_3.yaml` | `hj12_takeover_fixed_k_3_20260923` | miss |
| `hj12_takeover_fixed_k_10.yaml` | `hj12_takeover_fixed_k_10_20260923` | miss |
| `hj12_planner_handoff.yaml` | `hj12_planner_handoff_20260923` | miss |
| `hj12_prefix_m2.yaml` | `hj12_prefix_m2_20260922` | miss |
| `hj12_prefix_m4.yaml` | `hj12_prefix_m4_20260922` | miss |
| `hj12_prefix_m6.yaml` | `hj12_prefix_m6_20260922` | miss |
| `hj12_prefix_m9.yaml` | `hj12_prefix_m9_20260922` | miss |

Exact-name check on `/scratch/n12194778/sidekick/results/` and nested `results/results/`: no hits. [OBSERVED login-node `ls`]. Nested tree has `hj12_prefix_m{2,4,6,9}_20260922smoke_smoke` only — different strings, not collisions. Old shared id `hj12_exception_20260923` is unused and absent.

## Pair diff

Rebuilt on `router_seq` + `use_router: true` + `verifier.threshold: 0.5`. Executor / `limits` / `prices` copied from frozen `configs/hj11_action_review_exception.yaml`. Distinct ids (defect 1) plus one experimental key, so `diff` is two hunks, not one:

```
5c5
< campaign_id: hj12_advise_exception_20260923
---
> campaign_id: hj12_takeover_exception_20260923
7a8
> takeover: true
```

[OBSERVED `timeout 15 diff configs/hj12_advise_exception.yaml configs/hj12_takeover_exception.yaml`]

YAML `system:` is not read; launch with `--system router_seq`. [OBSERVED src/sidekick/runner.py:411, :427] YAML `use_router` is not forwarded by `system_kwargs`; `RouterSeq` hardcodes `use_router=True`. [OBSERVED src/sidekick/systems/router_seq.py:16; src/sidekick/runner.py:246-254]

## Escalation wiring

`RuleTriggerVerifier.score` returns `1.0` when `EXCEPTION_MARKER` (`Execution failed. Traceback:`) is in `last_observation` text, else `0.0`. [OBSERVED src/sidekick/agents/verifier.py:56, :117-121] `trajectory_state` supplies `last_observation`. [OBSERVED src/sidekick/systems/loop.py:555-560] `ThresholdRouter.should_escalate` is strict `score > threshold`. [OBSERVED src/sidekick/agents/verifier.py:51] `1.0 > 0.5` is true. `router_seq` builds that router [OBSERVED src/sidekick/systems/loop.py:283-284] and sets `force_review` [OBSERVED src/sidekick/systems/loop.py:744-745]. `verifier.threshold` reaches policy via `system_kwargs` for `router_seq`. [OBSERVED src/sidekick/runner.py:246-251] `takeover` is live only on that `force_review` branch: act vs `INTERVENTION:` prose. [OBSERVED src/sidekick/systems/loop.py:768-830; src/sidekick/runner.py:252-254]

## Test + suite

`test_hj12_exception_pair_distinct_ids_one_key` in `tests/unit/test_verify_configs_prompt_budget.py`.

hpc `25598221.aqua` [OBSERVED /home/n12194778/.hpc-spool/20260921-145545-1368503.out]:

```
484 passed, 1 skipped, 1 warning in 34.93s
```

Was 483 passed, 1 skipped; +1, no fall. `verify_configs.py` (hpc `25599223.aqua`) printed both exception configs (`packet subtree -> planner_alone`) then `all configs OK`.
