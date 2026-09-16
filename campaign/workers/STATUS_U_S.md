# STATUS_U_S — complete the J3 evaluation job

## Gaps
- [x] Gap 1: `configs/hj3_sft_b_exec.yaml:21-29` prompt budget + 300s timeouts
- [x] Gap 2: `scripts/pbs/hj3_eval.pbs:68-89` CFG_EXEC/CFG_PLAN; missing → exit 2
- [x] Gap 3: `hj3_eval.pbs:57` adapter `_s123_`; `ALIAS_SFT_B=sft_b` at :56
- [x] Gap 4: `run_arm` at :139; A `:250` executor_alone; B `:254` sft_plan
- [x] Gap 5: probe `:279-315`; skip-if-complete; rc in final exit `:319-325`

## Objection
Brief/FOLLOWUPS name `limits.max_prompt_tokens`. Runner reads
`executor.max_prompt_tokens` [OBSERVED src/sidekick/runner.py:166-169].
Corrected form is under executor [OBSERVED configs/hj3_sft_plan.yaml:34].
Implemented under executor so the field is not a no-op.

## Verification [OBSERVED]
- `bash -n scripts/pbs/hj3_eval.pbs` → rc=0
- `verify_configs.py` (hpc 25401753.aqua): `all configs OK`
- pytest (hpc 25401752.aqua): `191 passed, 1 skipped in 10.06s`
- no qsub of the eval job, no git
