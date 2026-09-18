# STATUS A13 (U-V4) — two small guards on the J8 harness

Unit: A13 / U-V4
Started: 2026-09-19
State: DONE — `scripts/pbs/hj8_frontier.pbs` edited; not submitted; not committed.

## Resume state
- Done. Re-read this file and the PBS script if another session picks up.
- Did not submit the job or any GPU job.
- Did not commit.
- Did not touch `configs/`, `src/`, `scripts/setup/`, `scripts/analysis/`, `/scratch/.../results/`, or `/scratch/.../adapters/`.
- Did not invoke `codex`.
- No PBS-script test harness exists in `tests/` (pytest only); did not invent one.

## Files owned
- `scripts/pbs/hj8_frontier.pbs`
- `campaign/workers/STATUS_A_13.md` (this)

## What changed
1. `register_lora` now requires `adapter_config.json` and one of `adapter_model.safetensors` / `adapter_model.bin` / `adapter_model.pt`. FATAL names the missing file.
2. `SMOKE_ONLY=1` (default `0`) runs smoke+gate then stops before the 57×2 campaign. Does not `--purge-broken` or write a manifest on the real cid. `scid=${cid}_smoke` is still removed after the gate.

## Checks
- `timeout 30 bash -n scripts/pbs/hj8_frontier.pbs` → exit 0 [OBSERVED]
- `shellcheck` not on PATH [OBSERVED `command -v shellcheck`]
- Isolated `/tmp` copies of the guard: half-trained dir → rc=2 missing `adapter_config.json`; config-only → rc=2 missing weights; `.safetensors`/`.bin`/`.pt` → pass [OBSERVED]
- In-progress trainer dir still has only `trainer_state/` + `train_log.jsonl` [OBSERVED `ls -la /scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b`]
- Completed adapter has `adapter_config.json` + `adapter_model.safetensors` [OBSERVED `ls -la .../sft_b_s123_granite8b`]

## Blockers
- None.
