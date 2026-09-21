# STATUS_X6 — free-arm gate vs replayed planner calls

State: **done**

Cause in the brief is correct. `summarise` `planner_calls_total` is the sum of `n_planner_calls` [OBSERVED scripts/setup/campaign_summarize.py:119-142]. `prefix_handoff` seeds that from `counters_from_events(prefix.events)` [OBSERVED src/sidekick/systems/loop.py:566-568]. Ledger `totals.planner_calls_total` is hosted spend. The free-arm gate was checking the first; it now checks the second. `expect_planner` branch unchanged [OBSERVED scripts/setup/campaign_summarize.py:178-189].

## Files
Modified: `scripts/setup/campaign_summarize.py`, `tests/unit/test_campaign_gate.py` (existing module tests; did not create a new file).

## Diff
- New summary key `planner_calls_live_total` from ledger totals (`int(totals.get("planner_calls_total") or 0)`). Original `planner_calls_total` kept, still replay-inclusive [OBSERVED scripts/setup/campaign_summarize.py:142-146].
- Free-arm (`expect_planner` false) fails only when live ≠ 0. Comment names `prefix_handoff`: live 0 with replay-inclusive > 0 is the normal correct state [OBSERVED scripts/setup/campaign_summarize.py:190-199].

## Failure message (exact)

```
expected zero live planner calls but saw {live} (replay-inclusive count {replay_inclusive}, models={models}) -- this arm was supposed to be free
```

Example: `expected zero live planner calls but saw 4 (replay-inclusive count 9, models={}) -- this arm was supposed to be free`

## Tests
1. `test_free_arm_prefix_handoff_replay_is_not_spend`
2. `test_free_arm_live_spend_fails_with_both_counts`
3. `test_non_free_arm_zero_calls_still_fails_expect_planner`
4. `test_summary_keeps_replay_inclusive_planner_calls_total`

## Suite
hpc job 25596782 [OBSERVED]:

```
467 passed, 1 skipped, 1 warning in 39.92s
```

Was 463 passed, 1 skipped; +4 tests, no fall [INFERRED from brief baseline + four new tests].
