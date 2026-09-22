# Status X38b

## Hunks Before / After

- `scripts/pbs/hj12_prefix.pbs:176-177` [OBSERVED `scripts/pbs/hj12_prefix.pbs:176-177`]:
  - Before: `"sft_plan|...|hj16_narrated_m9_zs"` / `"sft_plan|...|hj16_narrated_obs_m9_zs"`
  - After: `"prompt_only|...|hj16_narrated_m9_zs"` / `"prompt_only|...|hj16_narrated_obs_m9_zs"`
- `scripts/pbs/hj12_prefix.pbs:853` [OBSERVED `scripts/pbs/hj12_prefix.pbs:853`]:
  - Before: `prefix_handoff|sft_plan|executor_alone) ;;`
  - After: `prefix_handoff|sft_plan|prompt_only|executor_alone) ;;`
- `configs/hj16_narrated_m9_zs.yaml:3,7` and `configs/hj16_narrated_obs_m9_zs.yaml:3,7` [OBSERVED `configs/hj16_narrated_m9_zs.yaml:3`, `configs/hj16_narrated_obs_m9_zs.yaml:3`]:
  - Added header line citing `sft_plan.py:18` default override and `runner.py:256-258`.
- `tests/unit/test_hj16_narrated.py:260-270,448-481,518-521` [OBSERVED `tests/unit/test_hj16_narrated.py:260-270,448-481,518-521`]:
  - Replaced `_served_model_direct` with `_served_model` matching `test_hj15_prefix_zsq.py:53-70`.
  - Updated `test_hj16_configs_diff_and_lora_resolution` for `prompt_only` (None adapter) vs `sft_plan` (`sft_b_plus`).
  - Added `test_zs_config_under_sft_plan_would_request_phantom_alias`.
  - Updated `test_pbs_free_arms_lines` for `prompt_only`.

## Tests
- `test_action_selection_parity` [OBSERVED `tests/unit/test_hj16_narrated.py:273`]
- `test_observation_presence_flag` [OBSERVED `tests/unit/test_hj16_narrated.py:355`]
- `test_effective_m_short_prefix_and_manifest` [OBSERVED `tests/unit/test_hj16_narrated.py:397`]
- `test_hj16_configs_diff_and_lora_resolution` [OBSERVED `tests/unit/test_hj16_narrated.py:431`]
- `test_zs_config_under_sft_plan_would_request_phantom_alias` [OBSERVED `tests/unit/test_hj16_narrated.py:474`]
- `test_out_under_scratch_results_and_heldout_splits_refused` [OBSERVED `tests/unit/test_hj16_narrated.py:483`]
- `test_pbs_free_arms_lines` [OBSERVED `tests/unit/test_hj16_narrated.py:515`]

## Submission Line
```bash
qsub -v ARMS="hj16_narrated_m9_zs hj16_narrated_obs_m9_zs",DATE=20260923 scripts/pbs/hj12_prefix.pbs
```
[INFERRED from `scripts/pbs/hj12_prefix.pbs:12-13`]
