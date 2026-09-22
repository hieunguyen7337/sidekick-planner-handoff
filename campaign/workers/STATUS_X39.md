# STATUS X39 — Wave 1 Configs & Runner Registration

## Files Created
Nine configuration files were authored:
1. `configs/hj15_prefix_zsq_m11.yaml` [OBSERVED configs/hj15_prefix_zsq_m11.yaml:1-50]
2. `configs/hj15_executor_alone_zsq.yaml` [OBSERVED configs/hj15_executor_alone_zsq.yaml:1-34]
3. `configs/hj15_prompt_only_zsq.yaml` [OBSERVED configs/hj15_prompt_only_zsq.yaml:1-47]
4. `configs/hj17_prefix_c81_zs_m6.yaml` [OBSERVED configs/hj17_prefix_c81_zs_m6.yaml:1-52]
5. `configs/hj17_prefix_c81_zs_m9.yaml` [OBSERVED configs/hj17_prefix_c81_zs_m9.yaml:1-52]
6. `configs/hj17_prefix_c81_zs_m11.yaml` [OBSERVED configs/hj17_prefix_c81_zs_m11.yaml:1-52]
7. `configs/hj17_prefix_c81_bplus_m6.yaml` [OBSERVED configs/hj17_prefix_c81_bplus_m6.yaml:1-52]
8. `configs/hj17_prefix_c81_bplus_m9.yaml` [OBSERVED configs/hj17_prefix_c81_bplus_m9.yaml:1-52]
9. `configs/hj17_prefix_c81_bplus_m11.yaml` [OBSERVED configs/hj17_prefix_c81_bplus_m11.yaml:1-52]

## Campaign ID Validation
Each `campaign_id` matches the basename plus date suffix:
- `hj15_prefix_zsq_m11.yaml` -> `campaign_id: hj15_prefix_zsq_m11_20260923` [OBSERVED configs/hj15_prefix_zsq_m11.yaml:5]
- `hj15_executor_alone_zsq.yaml` -> `campaign_id: hj15_executor_alone_zsq_20260923` [OBSERVED configs/hj15_executor_alone_zsq.yaml:6]
- `hj15_prompt_only_zsq.yaml` -> `campaign_id: hj15_prompt_only_zsq_20260923` [OBSERVED configs/hj15_prompt_only_zsq.yaml:6]
- `hj17_prefix_c81_zs_m6.yaml` -> `campaign_id: hj17_prefix_c81_zs_m6_20260923` [OBSERVED configs/hj17_prefix_c81_zs_m6.yaml:7]
- `hj17_prefix_c81_zs_m9.yaml` -> `campaign_id: hj17_prefix_c81_zs_m9_20260923` [OBSERVED configs/hj17_prefix_c81_zs_m9.yaml:7]
- `hj17_prefix_c81_zs_m11.yaml` -> `campaign_id: hj17_prefix_c81_zs_m11_20260923` [OBSERVED configs/hj17_prefix_c81_zs_m11.yaml:7]
- `hj17_prefix_c81_bplus_m6.yaml` -> `campaign_id: hj17_prefix_c81_bplus_m6_20260923` [OBSERVED configs/hj17_prefix_c81_bplus_m6.yaml:7]
- `hj17_prefix_c81_bplus_m9.yaml` -> `campaign_id: hj17_prefix_c81_bplus_m9_20260923` [OBSERVED configs/hj17_prefix_c81_bplus_m9.yaml:7]
- `hj17_prefix_c81_bplus_m11.yaml` -> `campaign_id: hj17_prefix_c81_bplus_m11_20260923` [OBSERVED configs/hj17_prefix_c81_bplus_m11.yaml:7]

## PBS Runner Registration & Case Statement Check
Diff hunk appended to `FREE_ARMS` in `scripts/pbs/hj12_prefix.pbs` [OBSERVED scripts/pbs/hj12_prefix.pbs:180-188]:
```bash
  "executor_alone|${REPO}/configs/hj15_executor_alone_zsq.yaml|hj15_executor_alone_zsq"
  "prompt_only|${REPO}/configs/hj15_prompt_only_zsq.yaml|hj15_prompt_only_zsq"
  "prefix_handoff|${REPO}/configs/hj15_prefix_zsq_m11.yaml|hj15_prefix_zsq_m11"
  "prefix_handoff|${REPO}/configs/hj17_prefix_c81_zs_m6.yaml|hj17_prefix_c81_zs_m6"
  "prefix_handoff|${REPO}/configs/hj17_prefix_c81_zs_m9.yaml|hj17_prefix_c81_zs_m9"
  "prefix_handoff|${REPO}/configs/hj17_prefix_c81_zs_m11.yaml|hj17_prefix_c81_zs_m11"
  "prefix_handoff|${REPO}/configs/hj17_prefix_c81_bplus_m6.yaml|hj17_prefix_c81_bplus_m6"
  "prefix_handoff|${REPO}/configs/hj17_prefix_c81_bplus_m9.yaml|hj17_prefix_c81_bplus_m9"
  "prefix_handoff|${REPO}/configs/hj17_prefix_c81_bplus_m11.yaml|hj17_prefix_c81_bplus_m11"
```

The free-system case statement line was verified:
```bash
    prefix_handoff|sft_plan|prompt_only|executor_alone) ;;
```
[OBSERVED scripts/pbs/hj12_prefix.pbs:862]

## Tests Created
Unit tests were implemented in `tests/unit/test_hj17_c81_configs.py` [OBSERVED tests/unit/test_hj17_c81_configs.py:1-144]:
1. `test_c81_configs_point_at_the_cap81_campaign` [OBSERVED tests/unit/test_hj17_c81_configs.py:74]
2. `test_c81_configs_preserve_template_m` [OBSERVED tests/unit/test_hj17_c81_configs.py:83]
3. `test_qwen_zeroshot_configs_have_null_lora` [OBSERVED tests/unit/test_hj17_c81_configs.py:90]
4. `test_untailored_qwen_plan_arm_is_not_registered_under_sft_plan` [OBSERVED tests/unit/test_hj17_c81_configs.py:98]
5. `test_all_free_arms_configs_exist` [OBSERVED tests/unit/test_hj17_c81_configs.py:127]
