# STATUS_U_T — probe serving configuration

Owner: U-T
Started: 2026-09-17
Finished: 2026-09-17
Do not submit any job. Do not commit.

## Checklist

- [x] 1. `scripts/setup/state_probe.py` — `--chat-template-kwargs` and `--stop` CLI args passed to `VLLMExecutor`
- [x] 2. Report stamps `chat_template_kwargs` and `stop`; `PROBE_SCHEMA_VERSION` 2 → 3
- [x] 3. `scripts/pbs/hj3_eval.pbs` — paired baseline probe + serving kwargs/stop on both probes
- [x] 4. Walltime 04:00:00 → 08:00:00
- [x] 5. Tests in `tests/unit/` covering kwargs/stop/None/schema/malformed JSON

## Verification

- `bash -n scripts/pbs/hj3_eval.pbs` exit 0
- pytest via hpc job 25401771: 196 passed, 1 skipped in 11.06s
  (baseline 191 passed, 1 skipped; +5 new tests)

## Notes

Serving values taken from `configs/hj3_sft_b_exec.yaml` and matched the brief snippet.
No qsub of hj3_eval. No commit. Results under `/scratch/.../results/` untouched.
