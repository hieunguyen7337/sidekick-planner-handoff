# STATUS_X38 — Narrated-Prefix Arm Implementation

### 1. Script & CLI
Script: `scripts/analysis/hj16_narrate_prefix.py` [OBSERVED `scripts/analysis/hj16_narrate_prefix.py:1`]
CLI flags: `--source-campaign`, `--source-system`, `--m`, `--seeds`, `--with-observations`, `--out`, `--force`. Refuses `--out` under `/scratch/n12194778/sidekick/results/` or containing `test_normal`/`test_challenge` [OBSERVED `scripts/analysis/hj16_narrate_prefix.py:92-106`].

### 2. Event Selection & Truncation Parity
- Selection calls `build_handoff_prefix` [OBSERVED `src/sidekick/prefix_source.py:110-189`] and `_events_of_last_attempt` [OBSERVED `src/sidekick/replay.py:111-117`]. It guarantees exact parity with `prefix_handoff` by using the same clamping `effective_m = min(m, n_source_actions)` [OBSERVED `src/sidekick/prefix_source.py:139`] and filtering only `CODE`/`COMPLETE` actions via `_action_from_payload` [OBSERVED `src/sidekick/replay.py:46-60`].
- Observation truncation mirrors `loop.py:587-589` [OBSERVED `src/sidekick/systems/loop.py:587-589`] and `_history_from_events` [OBSERVED `src/sidekick/training/sft_data.py:236`]: raw `payload.text` is preserved verbatim without character truncation; prompt budget fitting is applied globally by `fit_messages_to_budget` [OBSERVED `src/sidekick/protocols/prompts.py:135-182`].

### 3. Configs & Diff against Template
Template: `configs/hj8_sft_plan_bplus.yaml` [OBSERVED `configs/hj8_sft_plan_bplus.yaml:1-47`].
Configs created:
- `configs/hj16_narrated_m9_zs.yaml` (`campaign_id: hj16_narrated_m9_zs_20260923`, `packet_source: .../packets/hj16_narrated_m9`, `lora_name: null`)
- `configs/hj16_narrated_obs_m9_zs.yaml` (`campaign_id: hj16_narrated_obs_m9_zs_20260923`, `packet_source: .../packets/hj16_narrated_obs_m9`, `lora_name: null`)
- `configs/hj16_narrated_m9_bplus.yaml` (`campaign_id: hj16_narrated_m9_bplus_20260923`, `packet_source: .../packets/hj16_narrated_m9`, `lora_name: sft_b_plus`)
- `configs/hj16_narrated_obs_m9_bplus.yaml` (`campaign_id: hj16_narrated_obs_m9_bplus_20260923`, `packet_source: .../packets/hj16_narrated_obs_m9`, `lora_name: sft_b_plus`)
Diff against template: header comments, `campaign_id`, `packet_source`, and `executor.lora_name`.
*Note*: `scripts/setup/verify_configs.py:146-162` will report failure on these four configs until the packet directories exist on disk [OBSERVED `scripts/setup/verify_configs.py:154-156`].

### 4. Harness & System Check
Added to `scripts/pbs/hj12_prefix.pbs:176-179` [OBSERVED `scripts/pbs/hj12_prefix.pbs:176-179`]:
```bash
  "sft_plan|${REPO}/configs/hj16_narrated_m9_zs.yaml|hj16_narrated_m9_zs"
  "sft_plan|${REPO}/configs/hj16_narrated_obs_m9_zs.yaml|hj16_narrated_obs_m9_zs"
  "sft_plan|${REPO}/configs/hj16_narrated_m9_bplus.yaml|hj16_narrated_m9_bplus"
  "sft_plan|${REPO}/configs/hj16_narrated_obs_m9_bplus.yaml|hj16_narrated_obs_m9_bplus"
```
`sft_plan` citation: `SftPlan.policy_defaults` defines `adapter_name="sft_plan"` [OBSERVED `src/sidekick/systems/sft_plan.py:18`]. Adapter dispatch is resolved via `executor.lora_name` in `make_executor` [OBSERVED `src/sidekick/runner.py:183`].

### 5. Unit Tests
Defined in `tests/unit/test_hj16_narrated.py` [OBSERVED `tests/unit/test_hj16_narrated.py:1`]:
- `test_action_selection_parity`
- `test_cached_packet_planner_loading`
- `test_with_observations_flag`
- `test_effective_m_short_prefix_and_manifest`
- `test_hj16_configs_diff_and_lora_resolution`
- `test_out_under_scratch_results_and_heldout_splits_refused`
- `test_pbs_free_arms_lines`

### 6. Execution Commands (Unrun)
(a) Build packet directories:
```bash
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 python scripts/analysis/hj16_narrate_prefix.py --source-campaign /scratch/n12194778/sidekick/results/hj1b_planner_20260915 --source-system planner_alone --m 9 --seeds 1,2 --out /scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m9
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 python scripts/analysis/hj16_narrate_prefix.py --source-campaign /scratch/n12194778/sidekick/results/hj1b_planner_20260915 --source-system planner_alone --m 9 --seeds 1,2 --with-observations --out /scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_obs_m9
```
(b) Submit untailored pair:
```bash
qsub -v ARMS="hj16_narrated_m9_zs hj16_narrated_obs_m9_zs" scripts/pbs/hj12_prefix.pbs
```
