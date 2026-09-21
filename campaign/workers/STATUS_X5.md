# STATUS_X5 — PBS harness, hj12 configs, frontier analysis

State: **done**

## Files
Created: `scripts/pbs/hj12_prefix.pbs`, `configs/hj12_prefix_m{2,4,6,9}.yaml`
Modified: `scripts/analysis/j8_frontier.py`

## CLI (defaults)
- `--cost-key` default `planner_calls_live` (unchanged). Also `planner_tokens_live`, `replayed_planner_tokens` (handoff payload, else ledger tokens so reference/floor are not dropped). Recorded 0 is a cost; no /0.
- `--reference-arm` default None. Non-inferiority is arm−reference; holds iff `ci95_pp[0] >= -7.00`. Primary `goal_pass_rate`, secondary `tgc`, all-episodes and survivors always.
- `--floor-arm` default None (brief did not name this; chord needs it). Residual uses existing `paired_diff` with a plug-in cost fraction.

## PBS
`bash -n scripts/pbs/hj12_prefix.pbs` → exit 0 [OBSERVED].
Adapter served: `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b` alias `sft_b_plus`. Dir has `adapter_config.json` + `adapter_model.safetensors` [OBSERVED ls]. `register_lora` asserts both before serve.
Kept from hj8: per-job `VLLM_PORT`, fatal unless alias in `GET /v1/models` `data[].id`, `setsid` + EXIT trap kills that process group only, `ARMS`/`SMOKE_ONLY`/`DATE`, walltime `04:00:00`. Runner `--system prefix_handoff` (`SYSTEM=` override). Smoke table: episodes, `effective_m`, `handoff_occurred`, `hash_ok`, replayed tokens, live calls; WARN if live ≠ 0.

`prefix_handoff` is in `SYSTEM_NAMES` [OBSERVED `python -m sidekick.runner --help`]. This unit did not create it.

## Tests
`tests/unit/test_j8_frontier.py`: 20 passed in 1.30s [OBSERVED hpc 25596403].
`tests/unit`: 425 passed, 1 failed — `test_prefix_handoff.py::test_m2_of_five_handoff_and_history` (`report` vs `run_start`). X1-owned; not edited [OBSERVED hpc 25596409].
`verify_configs.py`: all configs OK; four prefix YAMLs resolve `packet subtree -> planner_alone` [OBSERVED 25596403].

## Dry-run
```
timeout 1800 hpc -c 4 -m 16gb -t 00:25:00 bash -lc 'PY=/scratch/n12194778/sidekick/env/bin/python
$PY scripts/analysis/j8_frontier.py
  --arm planner_alone=/scratch/n12194778/sidekick/results/hj1b_planner_20260915
  --arm sft_plan=/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware
  --arm incomplete=/tmp/j8_x5_incomplete
  --reference-arm planner_alone --floor-arm sft_plan
  --cost-key planner_calls_live --out /tmp/j8_frontier_x5_dryrun.json'
```
Stdout (job 25596403), truncated H3:

```
REFUSE headline: arm 'incomplete' has 0 rows (need 114)
arm                              n  n_crashed  tgc_all tgc_surv   gp_all  gp_surv    calls  crash/call%
planner_alone                  114          0   0.6842   0.6842   0.8284   0.8284     1645         0.00
sft_plan                       114          0   0.3947   0.3947   0.7181   0.7181      114         0.00
incomplete                       0          0  REFUSED
handoff diagnostics ... cost/ep planner_alone=14.4298 sft_plan=1.0000; handoff/hash/m = NA
non-inferiority vs planner_alone ... sft_plan goal_pass_rate all-episodes holds=False diff_pp=-11.02 ci95_pp=[-17.88, -4.27]
sft_plan tgc all-episodes holds=False diff_pp=-28.95 ci95_pp=[-40.35, -17.54]
chord ... no prefix arm (only floor+reference)
headline: (refused)
```

JSON under `/tmp` on the compute node, not `campaign/results/`.

## Brief vs code
1. Shared `#PBS -o hj12_prefix.out` overwrites; hj8 uses unique `.OU` [OBSERVED hj8_frontier.pbs:7-15]. Named `-o`/`-e` as specified, plus CID+jobid `exec` log.
2. “CI upper bound below 7 pp” is the deficit writing; implemented `ci95_pp[0] >= -7` matching `f1_test` and prereg_hj12 §3.2 [OBSERVED docs/prereg_hj12_dev_20260922.md:61].
3. `--floor-arm` added; brief only named `--reference-arm`.
4. j8 scores only `crash` as 0; prereg_hj12 scores all broken types 0. Kept existing j8 [OBSERVED coerce_crash_quality].
5. `replayed_planner_tokens` falls back to ledger tokens [INFERRED] so planner_alone/sft_plan are not dropped.
