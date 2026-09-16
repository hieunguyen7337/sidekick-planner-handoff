# STATUS_U_W — prepare J4 (do not submit)

Owner: U-W
Started: 2026-09-17
Finished: 2026-09-17
Do not submit. Do not commit.

## Checklist

- [x] 1. `configs/hj4_correction.yaml` — campaign `hj4_correction_train_20260917`, `fixed_k: 5`, J2 packet replay, `executor.lora_name: sft_b`, 300s timeouts, `executor.max_prompt_tokens: 30720`, `limits.max_planner_calls: 81`
- [x] 2. `scripts/pbs/hj4_correction.pbs` — `#PBS -N hj4-correction`, walltime 06:00:00, one `fixed_k` train arm, smoke `${CID}_smoke` wiped before/after, `--gate --expect-planner --expect-model gpt-5.6-luna`, no probe, merge-safe archive, `ALIAS_SFT_B=sft_b`
- [x] 3. `scripts/setup/verify_configs.py` BOTH_LIVE entry for the new config (`CachedPacketPlanner` is what `make_planner` returns when `packet_source` is set)
- [x] 4. `bash -n` parse, `verify_configs.py` via hpc, unit+reproducibility pytest via hpc
- [x] 5. No `qsub` of `hj4_correction.pbs`. No git.

## lora_name / alias pair

- config: `lora_name: sft_b` [OBSERVED configs/hj4_correction.yaml:25]
- pbs: `ALIAS_SFT_B="${ALIAS_SFT_B:-sft_b}"` [OBSERVED scripts/pbs/hj4_correction.pbs:53]
- pbs adapter: `ADAPTER_SFT_B=.../sft_b_s123_granite8b` [OBSERVED scripts/pbs/hj4_correction.pbs:54]

## max_prompt_tokens

Under `executor:`, not `limits:` [OBSERVED configs/hj4_correction.yaml:21-35]. Runner reads `exec_cfg["max_prompt_tokens"]` [OBSERVED src/sidekick/runner.py:166].

## Archive (verbatim)

```
mkdir -p "${HOME}/sidekick_data/${CID}" && cp -a "${OUT}/${CID}/." "${HOME}/sidekick_data/${CID}/"
```

[OBSERVED scripts/pbs/hj4_correction.pbs:216]

## Verification [OBSERVED]

- `bash -n scripts/pbs/hj4_correction.pbs` → rc=0
- `verify_configs.py` (hpc 25401787.aqua): `all configs OK`
- pytest (hpc 25401788.aqua): `196 passed, 1 skipped in 9.23s`

## Notes

Packet source and `planner_alone` subtree exist on scratch [OBSERVED ls of `/scratch/n12194778/sidekick/results/hj2b_planner_train_20260916`]. Adapter dir exists [OBSERVED ls of `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_s123_granite8b`].
