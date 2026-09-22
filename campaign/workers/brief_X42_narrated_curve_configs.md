# Brief X42 — four configs giving the narrated-prefix arm a curve instead of one point

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Make your first file edit within your
first three actions. Claude submits every job.

## Why

The narrated-prefix arm at m=9 has landed and it is the session's most important mechanism result:
rendering the planner's first 9 recorded actions as **text** into the plan slot, with the executor
starting from step 0 in a **fresh** environment, scores 0.7665 (tailored) and 0.7773 (untailored) against
the **executed** prefix's 0.7852 and 0.7845. So most of the depth effect travels as information, not as
replayed environment state.

The immediate next question a reviewer asks is whether the *narrated* arm has the same **depth
dependence** as the executed arm, or whether text saturates earlier. That needs m=6 and m=11 points.
The packet directories are already built (zero hosted cost, rendered from recorded trajectories):

- `/scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m6` — 114 episodes, manifest present
- `/scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m11` — 114 episodes, manifest present

## The four configs

Copy the existing m=9 configs and change **only** the header comment, `campaign_id` and
`planner.packet_source`. Keep every other line byte-identical, including the long inline comments.

| new file | copy from | packet_source | campaign_id |
|---|---|---|---|
| `configs/hj16_narrated_m6_zs.yaml` | `configs/hj16_narrated_m9_zs.yaml` | `…/packets/hj16_narrated_m6` | `hj16_narrated_m6_zs_20260923` |
| `configs/hj16_narrated_m11_zs.yaml` | `configs/hj16_narrated_m9_zs.yaml` | `…/packets/hj16_narrated_m11` | `hj16_narrated_m11_zs_20260923` |
| `configs/hj16_narrated_m6_bplus.yaml` | `configs/hj16_narrated_m9_bplus.yaml` | `…/packets/hj16_narrated_m6` | `hj16_narrated_m6_bplus_20260923` |
| `configs/hj16_narrated_m11_bplus.yaml` | `configs/hj16_narrated_m9_bplus.yaml` | `…/packets/hj16_narrated_m11` | `hj16_narrated_m11_bplus_20260923` |

Each header comment must state: the plan slot carries the planner's first **m** recorded actions rendered
as text, the executor runs from step 0 in a fresh environment, and the arm is **information-matched and
state-unmatched** to `prefix_m<m>`.

🔺 **The `_zs` (untailored) pair runs under the `prompt_only` system, the `_bplus` pair under `sft_plan`.**
This is not cosmetic: `SftPlan.policy_defaults.adapter_name = "sft_plan"`
[`src/sidekick/systems/sft_plan.py:18`] and `runner.py:256-258` forwards `adapter_name` whenever it is
set, so an untailored config (`lora_name: null`) run under `sft_plan` requests an alias that is not in
`--lora-modules`; vLLM then silently serves the BASE model while `usage.model` names the alias — a
believable number measuring a configuration no arm runs in. The m=9 configs already encode this split;
preserve it exactly.

## Register them

`scripts/pbs/hj12_prefix.pbs`, the `FREE_ARMS` array, appending four lines in the existing
`system|abs_config_path|arm_name` format with `${REPO}` as the neighbours use it:

```
prompt_only|${REPO}/configs/hj16_narrated_m6_zs.yaml|hj16_narrated_m6_zs
prompt_only|${REPO}/configs/hj16_narrated_m11_zs.yaml|hj16_narrated_m11_zs
sft_plan|${REPO}/configs/hj16_narrated_m6_bplus.yaml|hj16_narrated_m6_bplus
sft_plan|${REPO}/configs/hj16_narrated_m11_bplus.yaml|hj16_narrated_m11_bplus
```

## Tests

Extend `tests/unit/test_hj16_narrated.py`:

1. `test_narrated_curve_configs_point_at_their_own_packet_dir` — each new config's
   `planner.packet_source` ends in `hj16_narrated_m6` or `hj16_narrated_m11` matching its own name, and
   the directory exists.
2. `test_narrated_curve_untailored_runs_under_prompt_only` — parse the `FREE_ARMS` block and assert each
   `hj16_narrated_m{6,11}_zs` line begins `prompt_only|` and each `_bplus` line begins `sft_plan|`.
3. `test_narrated_curve_configs_have_expected_lora` — `_zs` configs have `executor.lora_name is None`;
   `_bplus` configs have `executor.lora_name == "sft_b_plus"`.

Follow the real-path style already in that file (go through `system_kwargs` / `get_system`; do not
re-implement the resolution).

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`, `tar`, `rsync`. Never
  background anything. `timeout` on anything you do run.
- Do not edit `src/sidekick/**`, any frozen config (`hj8_*`, `hj11_*`, `hj12_prefix_m*.yaml`), or anything
  under `docs/prereg_*`. Never read or list `test_normal` / `test_challenge`. Never write under
  `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X42.md`, under 300 words: the four files created with their `campaign_id` and
`packet_source`; the exact `FREE_ARMS` hunk; the test names. `[OBSERVED path:line]` / `[INFERRED]` on
every claim. **Do not claim any test passes.**
