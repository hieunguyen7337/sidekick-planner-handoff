# STATUS_X41 — Paper Figures Generator (F6)

## CLI Signature
`scripts/analysis/figures.py --results-dir campaign/results --out-dir paper/figures --manifest paper/figures/figures_manifest.json [--only <fig_id>] [--dpi 200]` [OBSERVED scripts/analysis/figures.py:433-445].

## Milestone Per Figure
- **F1 · Depth Curve**: Reads `arms.prefix_m{2..11}.goal_pass_all` from `hj13_shape_post_guard_20260923.report.json` [OBSERVED docs/claims_ledger.md:61-63]; `arms.zs_m{6,9,11}.goal_pass_all` from `hj13_zeroshot_depth_m{6_m9,9_m11}_20260923.report.json` [OBSERVED docs/claims_ledger.md:51,65]; `arms.ceiling_cap{25,81}.goal_pass_all` from `hj13_ceiling_cap25_vs_cap81_20260923.report.json` [OBSERVED docs/claims_ledger.md:69]; `arms.{sft_plan,executor_alone}.goal_pass_all` from `hj12_unified_frontier_scenario_20260923.report.json` [OBSERVED docs/claims_ledger.md:10,20]. Draws shaded 7.00 pp NI margin below cap-25. Draws no vertical breakpoint marker (F1-RESULT-04) [OBSERVED docs/claims_ledger.md:64].
- **F2 · Matched-Budget Channel**: Reads `arms.prefix_m{2..11}.{cost_per_episode,goal_pass_all}`, `arms.advise_fixed_k_{3,10}`, `arms.executor_alone`, `arms.sft_plan`, `arms.planner_alone` from `hj12_unified_frontier_scenario_20260923.report.json` [OBSERVED docs/claims_ledger.md:10-21]; `arms.advice_fullctx_k10.{planner_tokens_per_episode,goal_pass_all}` from `hj13_advice_fullctx_matched_20260923.report.json` [OBSERVED docs/claims_ledger.md:82].
- **F3 · Tailoring Receiver Gap**: Reads `contrasts.goal_pass_all_prefix_m{6,9,11}_zeroshot_minus_prefix_m{6,9,11}_tailored.{diff_pp,ci95_pp}` from `hj13_receiver_contrast_m{6,9,11}_20260923.report.json` [OBSERVED docs/claims_ledger.md:39,53,66]. Suffix-adapter series skipped and recorded in manifest if unrun.
- **F4 · Mechanism**: Left panel reads `m1_api_novelty.cumulative_by_position.{1..20}.cum_first_uses_share` [OBSERVED docs/claims_ledger.md:74]; Right panel reads `m3_prefix_exhausted.primary.decompositions.m6_to_m{9,11}.{contribution_handoff_subset_pp,contribution_silenced_subset_pp,share_of_rise_from_handoff_pct,delta_total_pp}` from `hj13_mechanism_zeroshot_20260923c.report.json` [OBSERVED docs/claims_ledger.md:77,85]. Stacked bars label handoff percentage (83.8%, 60.5%).
- **F5 · Second Family**: Reads `arms.zsq_m{6,9}.goal_pass_all` from `hj15_qwen_zeroshot_curve_20260923.report.json` [OBSERVED docs/claims_ledger.md:76]; guards against missing Qwen floor reports (`hj15_executor_alone_zsq` / `hj15_prompt_only_zsq`) by recording skip in manifest rather than drawing floorless curve [OBSERVED campaign/workers/brief_X41_figures.md:61-65].

## Fatal Conditions Implemented
- Missing report JSON file raises `SystemExit` naming figure and file [OBSERVED scripts/analysis/figures.py:86-98].
- Missing report key raises `SystemExit` naming figure, file, key [OBSERVED scripts/analysis/figures.py:101-112].
- Empty series raises `SystemExit` naming figure [OBSERVED scripts/analysis/figures.py:161,186,252,357].
- Output path inside scratch results or containing test splits raises `ValueError` via `validate_output_path()` [OBSERVED scripts/analysis/figures.py:64-77].

## Test Names in `tests/unit/test_figures.py`
- `test_missing_report_file_is_fatal` [OBSERVED tests/unit/test_figures.py:114-127]
- `test_missing_json_key_is_fatal` [OBSERVED tests/unit/test_figures.py:130-144]
- `test_empty_series_is_fatal` [OBSERVED tests/unit/test_figures.py:147-161]
- `test_manifest_lists_every_generated_figure_and_its_keys` [OBSERVED tests/unit/test_figures.py:164-184]
- `test_skipped_figure_records_a_reason_and_does_not_fail` [OBSERVED tests/unit/test_figures.py:187-198]
- `test_validate_output_path_refuses_forbidden_locations` [OBSERVED tests/unit/test_figures.py:201-212]
- `test_no_breakpoint_marker_in_depth_curve` [OBSERVED tests/unit/test_figures.py:215-233]

## Execution Command for PBS / Claude
```bash
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 pytest -v tests/unit/test_figures.py
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 python scripts/analysis/figures.py --results-dir campaign/results --out-dir paper/figures --manifest paper/figures/figures_manifest.json --dpi 200
```
[INFERRED based on AGENTS.md rules 1 & 5 and brief_X41_figures.md:5-7].
