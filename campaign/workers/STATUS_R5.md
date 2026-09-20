# STATUS_R5 — B1 LoRA identity check stdin/heredoc fix

State: DONE
Updated: 2026-09-20
Job: **25559004.aqua** (`/home/n12194778/.hpc-spool/20260920-133705-2646568.out`)

## Fix [OBSERVED scripts/pbs/b1_pilot.pbs:339-366]

`b1_vllm_require_lora_ids` now pipes the curl body into `"${PY}" -c '...' "$@"` so stdin stays the pipe. Empty body FATALS `/v1/models body is empty`. Parse and missing-alias message strings unchanged. Function sits above `B1_GUARD_SELFTEST` so the harness can call it. Live caller unchanged [OBSERVED scripts/pbs/b1_pilot.pbs:713].

## Other `"${PY}" - ... <<'PY'` [OBSERVED scripts/pbs/b1_pilot.pbs]

- `:97` `b1_assert_preflight_line` — argv only, no pipe. Not this defect.
- `:232` `print_smoke_spend` — argv only, no pipe. Not this defect.
- `:315` `b1_smoke_error_count` — argv only, no pipe. Not this defect.

The only pipe-into-heredoc-fed-interpreter was the identity check. No other occurrence to fix. Did not touch `hj8_frontier.pbs`.

## Four cases [OBSERVED spool 25559004]

```
PASS lora_ids_ok
  | [b1] vllm /v1/models ids=['ibm-granite/granite-4.2-8b', 'sft_b'] required_aliases=['sft_b']
PASS lora_ids_missing
  | [b1] vllm /v1/models ids=['ibm-granite/granite-4.2-8b', 'sft_b_plus'] required_aliases=['sft_b']
  | [b1] FATAL: vllm /v1/models missing lora alias(es): ['sft_b']
PASS lora_ids_not_json
  | [b1] FATAL: /v1/models JSON did not parse: Expecting value: line 1 column 1 (char 0)
PASS lora_ids_empty
  | [b1] FATAL: /v1/models body is empty
```

Harness: `n_pass=29 n_fail=0` `ALL_GUARDS_FIRED` [OBSERVED spool]. Login `bash -n` rc=0. Suite: `433 passed, 1 skipped, 1 warning in 26.89s` [OBSERVED spool].

Did not commit, did not qsub a GPU job, did not write under `/scratch/.../results/`.
