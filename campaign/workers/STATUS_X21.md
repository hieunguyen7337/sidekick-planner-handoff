# STATUS X21

## Files changed or created

1. `docs/prereg_hj12_dev_20260922.md` — appended the correction only [OBSERVED docs/prereg_hj12_dev_20260922.md:343-357].
2. `campaign/RUNS.md` — appended the correction and unified-frontier section [OBSERVED campaign/RUNS.md:2538-2620].
3. `docs/claims_ledger.md` — created the claims ledger with the requested columns, all eight Task 2 contrasts, and all six qualifications [OBSERVED docs/claims_ledger.md:1-23].
4. `campaign/workers/STATUS_X21.md` — created this status record [INFERRED].

## Exact appended headings

- `## Correction 2026-09-23 — the executor acted in every "no-handoff" episode` appears in both registered records [OBSERVED docs/prereg_hj12_dev_20260922.md:343] [OBSERVED campaign/RUNS.md:2538].
- `## 15. The unified frontier — both channels on one cost axis — 2026-09-22` appears in the run ledger [OBSERVED campaign/RUNS.md:2554].

Byte-for-byte comparison of each edited file's original-length prefix against its pre-edit copy succeeded; no line was added or changed above existing content [INFERRED].

## Number audit against the unified report

All report-checkable arm scores, token costs, contrasts, confidence intervals, chord tests, the m11 non-inferiority result, matched-budget values, TGC result, and 53% rounded share matched the JSON at the displayed precision [OBSERVED campaign/results/hj12_unified_frontier_20260922.report.json: keys "arms", "contrasts", "noninferiority", "chord"].

The exceptions were:

- The 38 and 113 executor-action counts are absent from the report, so they could not be matched there [INFERRED]. X18 independently records 38 actions across 32 m9 episodes and 113 across 60 m11 episodes [OBSERVED campaign/workers/brief_X18_prefix_terminal_guard.md:33-37].
- The brief's `executor_alone` cost “~0” does not match a numeric report value: `cost_per_episode` is `null`, while `planner_calls_total` is 0 [OBSERVED campaign/results/hj12_unified_frontier_20260922.report.json: keys "arms.executor_alone.cost_per_episode", "arms.executor_alone.planner_calls_total"].
- The brief's stated cost order places `advise_oracle_esc` after the 43,823-token arm [OBSERVED campaign/workers/brief_X21_record_corrections.md:48-52], but its report cost is 7,585 tokens/episode, so the final table uses the report's order [OBSERVED campaign/results/hj12_unified_frontier_20260922.report.json: keys "arms.advise_oracle_esc.cost_per_episode", "arms.advise_fixed_k_10.cost_per_episode"].

The configuration/runtime numbers 25, 81, and 8 are not report fields [INFERRED]; each matched its separately cited source [OBSERVED configs/pilot_planner_alone.yaml:25] [OBSERVED configs/hj8_fixed_k_3.yaml:39-41] [OBSERVED src/sidekick/systems/loop.py:70]. No contradictory numeric report value was found [INFERRED].
