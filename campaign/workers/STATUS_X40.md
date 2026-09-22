# STATUS X40 — Three Cost Axes (F2) & Multiplicity Control (F1/T7)

## Unit A: Three Cost Axes (`scripts/analysis/j12_cost_axes.py`)
- Reused from `scripts/analysis/j8_noncached_cost.py`:
  - `usage_noncached_tokens` [OBSERVED scripts/analysis/j8_noncached_cost.py:16]
  - `last_plan_event_noncached_tokens` [OBSERVED scripts/analysis/j8_noncached_cost.py:27]
  - `attach_sft_plan_source_plan_tokens` [OBSERVED scripts/analysis/j8_noncached_cost.py:76]
  - `noncached_episode_cost` [OBSERVED scripts/analysis/j8_noncached_cost.py:150]
- Reused from `scripts/analysis/j8_frontier.py` & `j10_report.py`:
  - `parse_arm_spec` [OBSERVED scripts/analysis/j8_frontier.py:140]
  - `parse_seeds` [OBSERVED scripts/analysis/j8_frontier.py:247]
  - `summarise_arm` [OBSERVED scripts/analysis/j8_frontier.py:886]
  - `paired_contrast` [OBSERVED scripts/analysis/j8_frontier.py:1045]
  - `paired_diff_scenario` [OBSERVED scripts/analysis/j8_frontier.py:1142]
  - `load_arm_tree` [OBSERVED scripts/analysis/j10_report.py:355]
  - `validate_output_path` [OBSERVED scripts/analysis/j13_mechanism.py:57]
- CLI:
  `python scripts/analysis/j12_cost_axes.py --arm LABEL=DIR [--arm LABEL=DIR ...] --prices configs/cost/prices_2026-09.yaml --out <report.json> [--out-md <report.md>] [--n-boot 10000] [--seed 20260915] [--cluster scenario]`
- Report schema:
  - `ordering_by_axis`: `{noncached_tokens_per_episode: [arm, ...], usd_per_episode: [arm, ...], hosted_calls_per_episode: [arm, ...]}`
  - `ordering_is_stable_across_axes`: `bool`
  - `ordering_flips`: `[{pair: [arm_a, arm_b], axis_a: str, axis_b: str, order_in_axis_a: [arm_a, arm_b], order_in_axis_b: [arm_b, arm_a]}]`
  - `ni_unchanged_across_axes`: `bool`
- Tests (`tests/unit/test_j12_cost_axes.py`):
  - `test_cached_input_is_billed_at_the_cached_rate`
  - `test_usage_without_cache_split_is_counted_not_assumed`
  - `test_ordering_flip_is_detected`
  - `test_zero_priced_episodes_is_fatal`
  - `test_validate_output_path_refuses_forbidden_locations`
- Batch HPC run command [INFERRED]:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 pytest tests/unit/test_j12_cost_axes.py`

## Unit B: Multiplicity Control (`scripts/analysis/hj12_shape.py`)
- Added `holm_adjusted_intervals(contrasts: dict[str, list[float]], alpha: float = 0.05) -> dict` [OBSERVED scripts/analysis/hj12_shape.py:309] without modifying raw intervals.
- Multiplicity schema:
  `{method: "holm", alpha: 0.05, family: [contrast_names], n_comparisons: int, adjusted: {contrast: {ci95_pp_adjusted: [lo, hi], p_adjusted: float, survives: bool}}}`
- Added adjacent-m contrast sampling in `bootstrap_segmented` and wired `multiplicity` block into `fit_population` and report output.
- Tests (`tests/unit/test_hj12_shape.py`):
  - `test_holm_is_monotone_and_at_least_as_wide_as_raw`
  - `test_holm_matches_a_hand_worked_example`
- Batch HPC run command [INFERRED]:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 pytest tests/unit/test_hj12_shape.py`
