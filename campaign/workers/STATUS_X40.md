# STATUS X40 — three cost axes and multiplicity control

## Milestone 1: Files Created (Units A & B Initialized)
- [OBSERVED scripts/analysis/j8_noncached_cost.py:16,27,76,150]: `usage_noncached_tokens`, `last_plan_event_noncached_tokens`, `attach_sft_plan_source_plan_tokens`, `noncached_episode_cost` imported into `scripts/analysis/j12_cost_axes.py`.
- [OBSERVED scripts/analysis/j8_frontier.py:140,247,886,1045,1142]: `parse_arm_spec`, `parse_seeds`, `summarise_arm`, `paired_contrast`, `paired_diff_scenario` imported into `scripts/analysis/j12_cost_axes.py`.
- [OBSERVED scripts/setup/hj1_gate.py:22,23,44,124]: `BOOTSTRAP`, `SEED`, `scenario_of`, `paired_diff` referenced.
- [OBSERVED scripts/analysis/j13_mechanism.py:57-73]: `validate_output_path` copied to guard outputs against test splits and `/scratch/.../results/`.
- Created `scripts/analysis/j12_cost_axes.py` implementing the three cost axes (`noncached_tokens_per_episode`, `usd_per_episode`, `hosted_calls_per_episode`), ranking stability, flip detection, and non-inferiority across currencies.
- Created `tests/unit/test_j12_cost_axes.py`.

## In Progress
- Implementing `holm_adjusted_intervals` and the `multiplicity` block in `scripts/analysis/hj12_shape.py` and unit tests in `tests/unit/test_hj12_shape.py`.
