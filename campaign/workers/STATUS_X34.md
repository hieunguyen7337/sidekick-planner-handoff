# STATUS X34 — done

No qsub, no GPU, no commit. No placeholder adapter dir. `register_lora` still fatals if the path is missing [OBSERVED `scripts/pbs/hj12_prefix.pbs:344-360`].

**Provenance** (brief addendum, not re-counted): `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_handoff_granite8b_20260923_aligned.jsonl`, 629 rows / 270 episodes, `n_missing_api_docs` 0, tokenizer `ibm-granite/granite-4.2-8b`, `n_rows_cut_offset` 15, `n_truncated` 51, p50 19,258 [INFERRED from brief addendum]. Training job 25690327.

## Task A — configs

- `configs/hj13_prefix_hf_m6.yaml` → `hj13_prefix_hf_m6_20260923`
- `configs/hj13_prefix_hf_m9.yaml` → `hj13_prefix_hf_m9_20260923`
- `configs/hj13_prefix_hf_m11.yaml` → `hj13_prefix_hf_m11_20260923`

Each is the m-matched `hj12_prefix_m{K}.yaml` with only the header comment, `campaign_id`, and `executor.lora_name: sft_b_plus_handoff` changed [OBSERVED `:5,:28` of each hf yaml; field-equal test below].

## Task B — alias + FREE_ARMS

Alias (alongside `sft_b_plus`, not replacing it):

`ALIAS_SFT_B_PLUS_HANDOFF="${ALIAS_SFT_B_PLUS_HANDOFF:-sft_b_plus_handoff}"` [OBSERVED `hj12_prefix.pbs:118`]
`ADAPTER_SFT_B_PLUS_HANDOFF=.../sft_b_plus_handoff_granite8b` [OBSERVED `:119`]
`--lora-modules` via `register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"` on the granite serve [OBSERVED `:941`]. Granite allowed aliases are `sft_b_plus` and `sft_b_plus_handoff` [OBSERVED `:912`].

FREE_ARMS [OBSERVED `:161-163`]:
```
"prefix_handoff|${REPO}/configs/hj13_prefix_hf_m6.yaml|hj13_prefix_hf_m6"
"prefix_handoff|${REPO}/configs/hj13_prefix_hf_m9.yaml|hj13_prefix_hf_m9"
"prefix_handoff|${REPO}/configs/hj13_prefix_hf_m11.yaml|hj13_prefix_hf_m11"
```

`bash -n scripts/pbs/hj12_prefix.pbs` → EXIT:0 [OBSERVED login-node timeout].

## Tests

`tests/unit/test_hj13_prefix_hf.py`: `test_hj13_prefix_hf_matches_hj12_except_campaign_id_and_lora_name`, `test_handoff_configs_resolve_to_sft_b_plus_handoff_alias`, `test_three_receivers_are_distinguishable_on_request_model_and_run_start`, `test_hj13_pbs_registers_handoff_alias_alongside_sft_b_plus`, `test_hj13_hf_free_arms_lines_match_existing_format`.

X34 slice: `13 passed in 0.68s` [OBSERVED hpc 25690966].

verify_configs.py:
```
all configs OK
```

suite (`pytest tests -q --import-mode=importlib --ignore=tests/unit/test_j8_frontier.py`):
```
503 passed, 1 skipped, 1 warning in 34.64s
```

## Unrun eval (after adapter exists)

```
ARMS="hj13_prefix_hf_m6 hj13_prefix_hf_m9 hj13_prefix_hf_m11" DATE=20260923 qsub -v ARMS="${ARMS}",DATE=${DATE} scripts/pbs/hj12_prefix.pbs
```
