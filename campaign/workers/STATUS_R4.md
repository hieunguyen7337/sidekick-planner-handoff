# STATUS_R4: 2026-09-19 Collision Post-Mortem, Discard Record, and B1 Amendment

## 1. Verification Summary

All facts stated in `brief_R4_postmortem.md` were verified directly against tree logs, code, and results; **0 facts failed verification**:
- **Job collision & port bind**: Jobs `25519712` (B1) and `25519749` (J8) ran concurrently on node `gpu0n007` at 23:45:45 [OBSERVED campaign/workers/logs/b1_pilot_train_20260919.25519712.aqua.out:1, campaign/workers/logs/hj8_frontier_live_20260919livesmoke.25519749.aqua.out:1]. Both logged `Application startup complete` on port 8000 [OBSERVED /scratch/n12194778/sidekick/logs/b1_pilot_train_20260919.25519712.aqua_vllm.log:94, /scratch/n12194778/sidekick/logs/hj8_frontier_live_20260919livesmoke.25519749.aqua_vllm.log:94]. B1 vLLM log explicitly identified port 8000 owned by PID 233054 (J8) [OBSERVED /scratch/n12194778/sidekick/logs/b1_pilot_train_20260919.25519712.aqua_vllm.log:111-112].
- **LoRA mismatch & crash**: J8 server had only `sft_b_plus` loaded; B1's requests for `sft_b` generated exactly 20 × `404 The model 'sft_b' does not exist` [OBSERVED /scratch/n12194778/sidekick/logs/hj8_frontier_live_20260919livesmoke.25519749.aqua_vllm.log:101-145 (20 occurrences)]. B1 recorded 20/20 `branch_error_type: "crash"` and `branch_planner_tokens: 0` [OBSERVED /scratch/n12194778/sidekick/results/b1_pilot_train_20260919_smoke/branch_runs.jsonl:1-20].
- **Node-wide pkill cross-job kill**: B1 cleanup killed J8 vLLM server at 23:48:18 [OBSERVED /scratch/n12194778/sidekick/logs/hj8_frontier_live_20260919livesmoke.25519749.aqua_vllm.log:152]. J8 arm 1 logged 5 executor completions and 2 live planner calls before death [OBSERVED campaign/workers/logs/hj8_frontier_live_20260919livesmoke.25519749.aqua.out:131-145]; arms 2–10 failed on step 1 [OBSERVED :150-609].
- **Legacy script hazards**: Node-wide `pkill` confirmed in `scripts/pbs/hj6_branches.pbs:131-132` and `scripts/pbs/hj3_eval.pbs:125-126` [OBSERVED]. Hardcoded port 8000 confirmed in `hj4_correction.pbs:183,197`, `hj4b_fixed_k_dev.pbs:157,171`, `hj1a_executor_alone.pbs:77,93`, `hj1c_fixed_k.pbs:86,95`, `hj1c_prompt_only.pbs:83,92`, and `hj15_state_probe.pbs:77,133,144,258,271,294,307,317,333,346,356,395,408` [OBSERVED].
- **Smoke gate false pass**: B1 gate printed `n_rows=20 branch_planner_calls_sum=88 unknown_call_rows=0` and exited 0 despite 20 crashes and 0 live calls [OBSERVED campaign/workers/logs/b1_pilot_train_20260919.25519712.aqua.out:540].
- **Budget cap replayed ticks**: `--max-planner-calls-total` summed replay-inclusive `branch_planner_calls` [OBSERVED scripts/setup/branch_counterfactual.py:1291, 1297-1318, :883-905, src/sidekick/systems/loop.py:119-133] instead of live calls [OBSERVED docs/prereg_b1_pilot.md:158-199].

## 2. Files Modified and Created

1. `docs/FOLLOWUPS.md`: Appended entry documenting the 2026-09-19 collision, false-pass smoke gate, live-call budget cap, 2026-09-20 fixes (port derivation, env override, identity-verified health check, process-group shutdown, trap EXIT, outcome-based gate, live-call budget counting), and legacy script hazards.
2. `campaign/RUNS.md`: Appended discard record invalidating `/scratch/n12194778/sidekick/results/b1_pilot_train_20260919_smoke` and every `hj8_*_20260919livesmoke_smoke` tree.
3. `README.md`: Updated stale Status section at lines 30-31 from "Plan stage... no training run and no evaluation campaign has been submitted" to current "Campaign stage" reflecting completed milestones (HJ-1/1R, HJ-2B, HJ-1.5, SFT adapters, HJ-6, J8a baselines).
4. `docs/prereg_b1_pilot_amendment_20260920.md`: Created scientific amendment documenting the live-call budget cap technical correction, establishing why it is a correction and confirming zero valid B1 data existed at amendment time.
5. `campaign/workers/STATUS_R4.md`: This report.

## 3. R4b Re-Citation against Real Code (2026-09-20)

- Re-verified all 7 repair items in `docs/FOLLOWUPS.md` against landed implementations in `scripts/pbs/hj8_frontier.pbs`, `scripts/pbs/b1_pilot.pbs`, `src/sidekick/runner.py`, and `scripts/setup/branch_counterfactual.py`.
- Replaced all brief citations (`brief_R1_hj8_port.md`, `brief_R2_b1_gate.md`) in `docs/FOLLOWUPS.md` with verified `[OBSERVED <path>:<line>]` citations.
- Recorded the budget cap behaviour change: `spent_from_rows` in `scripts/setup/branch_counterfactual.py:942-977` no longer filters on `is_done_row`, charging crashed/incomplete branches the unknown-cost factor of 81 rather than 0, faithful to §8 pre-registration.
- Corrected `README.md` Status section from claiming active execution to stating harness repairs are complete and J8/B1 campaigns are the next submissions.

