# STATUS X29 — finish scenario clustering

**Unit:** X29
**State:** complete
**Last update:** 2026-09-22

## Files
- Owned: `scripts/analysis/j8_frontier.py`, `tests/unit/test_j8_frontier.py`, this STATUS, `campaign/results/x19_check_default.report.json`, `campaign/results/hj12_unified_frontier_scenario_20260923.report.json`, `campaign/results/hj12_unified_frontier_scenario_nolimit_20260923.report.json`.
- Not edited: `src/`, `configs/`, `scripts/pbs/`.

## Three tests

1. `test_chord_row_reports_scenario_interval` — needed `ci95_pp_scenario`, `ci95_pp_task == ci95_pp`, `resample_unit == "task"`. Missing: floor copied from ref made chord denom 0, so the empty return had no scenario keys. Assertions kept; fixture now uses a cheaper floor; undefined chords still stamp cluster keys.
2. `test_exclude_reference_limit_cli_writes_sensitivity_block` — needed `reference_episodes_excluded_limit` counts and a diagnostic NI block with `n_pairs == 6`. Missing: `NameError: limited`; 8-row arms were skipped by `complete_n`. Fixed drop keys; NI/chord/contrasts now use any arm with `cleaned`.
3. `test_exclude_reference_limit_without_reference_arm_records_reason` — no-reference reason already worked. The extra default check asked for `contrasts["tgc_all_sidekick"]`. Existing keys are `tgc_all_{a}_minus_{b}` [OBSERVED `scripts/analysis/j8_frontier.py` combinations loop]. A one-arm report cannot emit that key without breaking the 14-arm naming contract. Second arm added; assertion now uses `tgc_all_sidekick_minus_other`. Cluster-field asserts unchanged.

## Tests [OBSERVED hpc 25687377.aqua]

```
45 passed in 12.72s
```

Full suite, excluding X24's untracked `tests/unit/test_handoff_sft.py` and `tests/unit/test_hj13_prefix_zs.py` [OBSERVED hpc 25686397.aqua]:

```
523 passed, 1 skipped, 1 warning in 47.96s
```

## Default keys

Walk of every pre-existing key in `hj12_unified_frontier_20260922.report.json` vs `x19_check_default.report.json`: **2 mismatches**, both `oracle_semantics` / `oracle_semantics_citation` line numbers in `loop.py` (644/749 vs 660/777) [OBSERVED hpc 25686669.aqua]. Those citations are live; `loop.py` is not this unit. Every NI/contrast/chord numeric field matched, including `prefix_m11` `ci95_pp` `[-5.27, 6.34]`.

`scenario_of` is the `hj1_gate` import [OBSERVED `tests/unit/test_j8_frontier.py` `test_scenario_of_is_imported_not_reimplemented`].

## Table `goal_pass_all` vs `planner_alone`

| arm | diff_pp | task CI | scenario CI | nolimit n | nolimit task CI | nolimit scenario CI |
|---|---|---|---|---|---|---|
| prefix_m9 | −1.5 | [−8.1, 5.62] | [−8.98, 6.77] | 102 | [−13.2, −3.65] | [−14.15, −3.0] |
| prefix_m11 | +0.23 | [−5.27, 6.34] | [−5.7, 7.02] | 102 | [−10.16, −1.98] | [−9.8, −2.57] |
| advise_fixed_k_3 | −12.72 | [−19.92, −4.95] | [−20.03, −3.6] | 102 | [−25.54, −12.79] | [−25.34, −13.17] |
| sft_plan | −11.02 | [−17.88, −4.27] | [−19.69, −2.05] | 102 | [−24.08, −11.62] | [−25.79, −9.77] |

Default n_pairs=114. Nolimit = sensitivity block under `--cluster scenario --exclude-reference-limit` [OBSERVED `campaign/results/hj12_unified_frontier_scenario_nolimit_20260923.report.json`]. Default CIs [OBSERVED `campaign/results/x19_check_default.report.json`].

- 19 scenarios; task mode used 57 clusters, scenario mode used 19 [OBSERVED `x19_check_default.report.json` `n_clusters` / `n_clusters_scenario` on `prefix_m11.goal_pass_all`].
- `prefix_m11` non-inferiority still holds under scenario clustering (`holds_scenario` True; scenario CI [−5.7, 7.02]) [OBSERVED same].
- 12 reference episodes excluded as `limit` (`loaded_error_type_limit` 12, `n_excluded` 12, `n_reference_after` 102); `prefix_m11` flips True→False on both task and scenario holds; the other three table arms stay False [OBSERVED nolimit report `reference_episodes_excluded_limit` and sensitivity `noninferiority.arms`].
