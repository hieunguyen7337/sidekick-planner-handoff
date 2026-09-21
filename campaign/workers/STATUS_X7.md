# STATUS_X7 — non-cached planner token axis

State: **done**. Route for the `sft_plan` floor: **source_plan_event** (not the understatement fallback).

## Formula

`planner_tokens_noncached` =
`live_noncached + (replayed_planner_tokens or 0) + (sft_plan_replayed_plan_tokens or 0)`
where `live_noncached = planner.input_tokens + output_tokens + reasoning_output_tokens`
from `totals.per_actor.planner` [OBSERVED scripts/analysis/j8_frontier.py:569-582, scripts/analysis/j8_noncached_cost.py:150-167]. Cached input is never added. The old keys `planner_tokens_live` and `replayed_planner_tokens` are unchanged, including the latter’s fallback onto the cached-inclusive ledger total [OBSERVED scripts/analysis/j8_frontier.py:691-703].

JSON `cost_key_note` states that exclusion [OBSERVED scripts/analysis/j8_frontier.py:2058]. Per arm: `cached_input_tokens_per_episode` and `cached_share_of_inclusive_total`.

## `sft_plan` floor

114/114 `sft_plan` episodes map 1-to-1 onto `/scratch/n12194778/sidekick/results/hj1b_planner_20260915/planner_alone/<seed>/<task_id>/events.jsonl` with exactly one `plan` event (packet present) after last `run_start` [OBSERVED hpc 25596828]. Charged that event’s non-cached usage, matching `CachedPacketPlanner._load_plan_event` [OBSERVED src/sidekick/agents/planner.py:688-724, scripts/analysis/j8_noncached_cost.py:27-64]. Mean **23905.587719** tokens/episode [OBSERVED hpc 25596866 `/tmp/x7_dryrun.json`]. `known_cost_understatements` is `[]`.

## Dry-run cost/ep (n=114)

handoff table lines [OBSERVED hpc 25596866]:

```
planner_tokens_noncached:
planner_alone  cost/ep=684453.2632  cached/ep=588746.1  cache_share=0.457
sft_plan       cost/ep=23905.5877   cached/ep=0.0       cache_share=NA

replayed_planner_tokens (old mix):
planner_alone  cost/ep=1273199.3684
sft_plan       cost/ep=0.0000

planner_tokens_live (cached-inclusive):
planner_alone  cost/ep=1273199.3684
sft_plan       cost/ep=0.0000
```

`planner_alone` noncached = live inclusive − cached = 1273199.368421 − 588746.105263 [OBSERVED]. `sft_plan` cache share is NA because live inclusive is 0 [OBSERVED].

## Tests

`test_noncached_cost_excludes_cached_input_tokens`
`test_prefix_and_live_noncached_costs_are_on_the_same_scale`
`test_old_token_cost_keys_unchanged_when_cached_tokens_present`
`test_sft_plan_noncached_cost_charges_source_plan_event`
`test_sft_plan_unmapped_source_stays_zero_and_is_understated`

## Suite [OBSERVED hpc 25596866]

```
472 passed, 1 skipped, 1 warning in 28.09s
```

Was 467 passed, 1 skipped; +5 tests, no fall [INFERRED].

## Files

Modified: `scripts/analysis/j8_frontier.py`, `tests/unit/test_j8_frontier.py`
Created: `scripts/analysis/j8_noncached_cost.py`
Default `--cost-key` remains `planner_calls_live`. Prefix token axis: `--cost-key planner_tokens_noncached`.
