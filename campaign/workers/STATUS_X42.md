# Status X42 — Narrated Curve Configs (m=6, m=11)

## Created Configs
- `configs/hj16_narrated_m6_zs.yaml`: `campaign_id: hj16_narrated_m6_zs_20260923` [OBSERVED configs/hj16_narrated_m6_zs.yaml:6], `packet_source: /scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m6` [OBSERVED configs/hj16_narrated_m6_zs.yaml:16]
- `configs/hj16_narrated_m11_zs.yaml`: `campaign_id: hj16_narrated_m11_zs_20260923` [OBSERVED configs/hj16_narrated_m11_zs.yaml:6], `packet_source: /scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m11` [OBSERVED configs/hj16_narrated_m11_zs.yaml:16]
- `configs/hj16_narrated_m6_bplus.yaml`: `campaign_id: hj16_narrated_m6_bplus_20260923` [OBSERVED configs/hj16_narrated_m6_bplus.yaml:6], `packet_source: /scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m6` [OBSERVED configs/hj16_narrated_m6_bplus.yaml:16]
- `configs/hj16_narrated_m11_bplus.yaml`: `campaign_id: hj16_narrated_m11_bplus_20260923` [OBSERVED configs/hj16_narrated_m11_bplus.yaml:6], `packet_source: /scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m11` [OBSERVED configs/hj16_narrated_m11_bplus.yaml:16]

## PBS Registration
Appended to `FREE_ARMS` array in `scripts/pbs/hj12_prefix.pbs` [OBSERVED scripts/pbs/hj12_prefix.pbs:189-192]:
```bash
  "prompt_only|${REPO}/configs/hj16_narrated_m6_zs.yaml|hj16_narrated_m6_zs"
  "prompt_only|${REPO}/configs/hj16_narrated_m11_zs.yaml|hj16_narrated_m11_zs"
  "sft_plan|${REPO}/configs/hj16_narrated_m6_bplus.yaml|hj16_narrated_m6_bplus"
  "sft_plan|${REPO}/configs/hj16_narrated_m11_bplus.yaml|hj16_narrated_m11_bplus"
```

## Extended Unit Tests
Added to `tests/unit/test_hj16_narrated.py`:
- `test_narrated_curve_configs_point_at_their_own_packet_dir` [OBSERVED tests/unit/test_hj16_narrated.py:534]
- `test_narrated_curve_untailored_runs_under_prompt_only` [OBSERVED tests/unit/test_hj16_narrated.py:544]
- `test_narrated_curve_configs_have_expected_lora` [OBSERVED tests/unit/test_hj16_narrated.py:568]
