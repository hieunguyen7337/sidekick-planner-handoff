# Brief X38b — the untailored narrated arms must run under `prompt_only`, not `sft_plan`

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Read files, write files, stop.
Make your first file edit within your first three actions. Small unit: four edits and two tests.

## The defect, traced

X38 wired the two untailored narrated-prefix arms (`configs/hj16_narrated_m9_zs.yaml`,
`configs/hj16_narrated_obs_m9_zs.yaml`, `executor.lora_name: null`) under the `sft_plan` system in
`scripts/pbs/hj12_prefix.pbs:176-177`. That is wrong at runtime:

- `src/sidekick/runner.py:256-258` passes `adapter_name` to the system **only when the config's
  `lora_name` is truthy**. With `null` nothing is passed.
- `src/sidekick/systems/sft_plan.py:11-19` then supplies its own default,
  `policy_defaults.adapter_name = "sft_plan"`.
- The executor's request model is `kw.get("lora_name") or self.lora_name or self.model`
  (`src/sidekick/agents/executor.py:248`), and the run loop passes the **policy's** adapter name, so
  the request would name the alias `sft_plan` — an alias no vLLM launch serves. Per the recorded
  hazard (`configs/hj13_prefix_zs_m6.yaml:29`) an unserved alias either fails or silently hits the base
  model while `usage.model` names the alias. Either way the arm is not what it claims to be.
- X38's test `test_hj16_configs_diff_and_lora_resolution` (`tests/unit/test_hj16_narrated.py:424-457`)
  did not catch this because it issues `complete()` with the **config's** `lora_name`
  (`:261-270`), not the **policy's** adapter name that the run loop actually uses.

`PromptOnly` (`src/sidekick/systems/prompt_only.py`) is the identical `ConfigurableSystem` policy
without the adapter default — it is what the base-receiver plan-only baseline `hj1r_prompt_only`
ran under. So the untailored pair belongs under `prompt_only`; the tailored pair stays under
`sft_plan` with `lora_name: sft_b_plus`.

## Edits

1. `scripts/pbs/hj12_prefix.pbs:176-177`: change the system field of the two `hj16_narrated*_zs`
   `FREE_ARMS` entries from `sft_plan` to `prompt_only`. Leave the two `_bplus` entries as `sft_plan`.
2. Same file, the free-system case list (`case "${system}" in prefix_handoff|sft_plan|executor_alone)`
   near `:745-850`): add `prompt_only` to that alternation so the arm is treated as free (cached
   planner, zero hosted calls), not as a live arm. Cite the exact line. If `prompt_only` appears in any
   other system allow-list in the same file, add it there too; say where.
3. Header comment of the two `_zs` configs: state that they run under `prompt_only` and why (one
   sentence, citing `sft_plan.py:18` and `runner.py:256-258`).
4. `tests/unit/test_hj16_narrated.py`:
   - fix `test_pbs_free_arms_lines` for the new system fields;
   - **replace** the request-model check in `test_hj16_configs_diff_and_lora_resolution` with the
     real path: build the system via `system_kwargs(<system>, cfg, task_id, seed)` and
     `get_system(<system>, planner=MockPlanner(), executor=ex, **kw)` exactly as
     `tests/unit/test_hj15_prefix_zsq.py:52-69` (`_served_model`) does, then call
     `ex.complete(..., lora_name=system.policy.adapter_name)` and assert the POSTed `"model"`:
     for the `_zs` pair under `prompt_only` it must equal `ibm-granite/granite-4.2-8b` and
     `system.policy.adapter_name` must be `None`; for the `_bplus` pair under `sft_plan` it must
     equal `sft_b_plus`;
   - add `test_zs_config_under_sft_plan_would_request_phantom_alias`: the same `_zs` config built
     under `sft_plan` yields `system.policy.adapter_name == "sft_plan"` and a POSTed model of
     `"sft_plan"` — this test documents the hazard so it cannot be reintroduced.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Never background a
  command.
- Do not edit `src/sidekick/**` (the fix is a wiring fix, not a runtime change), `scripts/analysis/**`,
  or any frozen config. Do not touch the four `hj16_*` configs beyond the header comment.
- Read-only on `/scratch/n12194778/sidekick/results/`. Never read or list `test_normal`/`test_challenge`.
- **Do not commit.**

## Return contract

`campaign/workers/STATUS_X38b.md`, under 250 words: each hunk before/after with line numbers; the
test names; the `qsub` line for the untailored pair. Tag claims `[OBSERVED path:line]` / `[INFERRED]`.
**Do not claim any test passes.**
