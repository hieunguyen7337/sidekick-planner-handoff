# STATUS X19 — scenario-clustered bootstrap + limit-exclusion sensitivity

**Unit:** X19
**State:** in_progress
**Last update:** 2026-09-23

## Files
- Owned: `scripts/analysis/j8_frontier.py`, `tests/unit/test_j8_frontier.py`, this STATUS, three new JSONs in `campaign/results/`.
- Read-only: everything else (`scripts/setup/hj1_gate.py` reused via import, not edited).

## Flags added
- `--cluster {task,scenario}` (default `task` = existing output unchanged).
- `--exclude-reference-limit` (default off; sensitivity analysis only).

## New JSON keys
Per contrast / NI / chord row: `ci95_pp_scenario`, `diff_pp_scenario`, `diff_scenario`,
`ci95_scenario`, `n_clusters_scenario`, `n_pairs_scenario`,
`mean_cluster_size_scenario`, `resample_unit_scenario`; under `--cluster scenario`
the primary fields switch to scenario clustering and the task values move to
`*_task` keys, plus `holds_scenario` / `deficit_ci_upper_pp_scenario` on NI rows.
Top level: `cluster`, `cluster_note`, `exclude_reference_limit`,
`reference_episodes_excluded_limit`.

## Verification runs
Pending.
