# STATUS X35 — done

No qsub, no GPU, no commit. `register_lora` still fatals on a missing path when an arm asks for the alias; it is no longer called for every granite group.

## Diff hunk [OBSERVED `scripts/pbs/hj12_prefix.pbs:914-946`]

`ALLOWED_ALIASES` unchanged (`sft_b_plus` + `sft_b_plus_handoff` on granite) [OBSERVED `:910-913`]. Flag set from already-yielded `arm_lora`, not a filesystem check:

```
  need_handoff=0
  ...
    if [[ "${arm_lora}" == "${ALIAS_SFT_B_PLUS_HANDOFF}" ]]; then
      need_handoff=1
    fi
    GROUP_ARMS+=("${spec}")
  ...
  register_lora "${EXPECT_ALIAS}" "${ADAPTER_PATH}"
  if [[ "${need_handoff}" -eq 1 ]]; then
    register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"
  fi
```

## Tests

`test_granite_prefix_zs_group_does_not_require_handoff_adapter`
`test_granite_hf_group_missing_handoff_adapter_is_fatal`

They execute the PBS group-assembly + `register_lora` block with a valid `sft_b_plus` dir and a missing handoff dir. Prefix/zs exits 0 without registering handoff; an `hj13_prefix_hf_*` arm still hits `register_lora` and exits 2. File: `7 passed in 1.43s` [OBSERVED hpc 25691983].

`bash -n scripts/pbs/hj12_prefix.pbs` → EXIT:0 [OBSERVED login-node timeout].

verify_configs.py [OBSERVED hpc 25692053]:
```
all configs OK
```

suite (`pytest tests -q --import-mode=importlib`, **including** `tests/unit/test_j8_frontier.py`) [OBSERVED hpc 25692053]:
```
550 passed, 1 skipped, 1 warning in 40.66s
```

`test_j8_frontier.py` did not fail or error in that run [INFERRED from the summary: no failed/error line; dots only].
