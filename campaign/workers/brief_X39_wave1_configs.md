# Brief X39 — nine configs: the Qwen zero-shot floor, and the cap-81 second planner sample

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`, or any multi-minute command.** Make your
first file edit within your first three actions. Claude submits every job; you only write files.

## Why

Two gaps block the thesis. (1) The Qwen3-8B zero-shot prefix curve has m=6 and m=9 running but **no floor
of its own** — without `executor_alone` and one-plan on the same base model, a rise at m=9 is
uninterpretable, and there is no m=11 point. (2) Every prefix arm so far replays ONE planner sample
(`hj1b_planner_20260915`, the 25-call-cap run). A second, independent planner sample already exists on
disk at cap 81 — replaying it costs zero hosted calls and answers "does the curve shape survive a
different planner sample?", which is the generality question a top venue asks.

## A. Three configs completing the Qwen zero-shot family

Template: `configs/hj15_prefix_zsq_m9.yaml` (Qwen3-8B, `lora_name: null`). Copy it and change ONLY the
header comment, `campaign_id`, and the fields named. Keep every other line byte-identical, including the
long inline comments — they are load-bearing documentation.

| new file | copy from | change |
|---|---|---|
| `configs/hj15_prefix_zsq_m11.yaml` | `configs/hj15_prefix_zsq_m9.yaml` | `campaign_id: hj15_prefix_zsq_m11_20260923`; `handoff.m: 11` |
| `configs/hj15_executor_alone_zsq.yaml` | `configs/hj14_executor_alone.yaml` | `campaign_id: hj15_executor_alone_zsq_20260923`; `executor.lora_name: null` (with the same explanatory comment used in `hj15_prefix_zsq_m9.yaml:28`) |
| `configs/hj15_prompt_only_zsq.yaml` | `configs/hj14_sft_plan.yaml` | `campaign_id: hj15_prompt_only_zsq_20260923`; `executor.lora_name: null` (same comment) |

🔺 **`hj15_prompt_only_zsq.yaml` must be registered under the `prompt_only` system, NOT `sft_plan`.**
`SftPlan.policy_defaults.adapter_name = "sft_plan"` [`src/sidekick/systems/sft_plan.py:18`] and
`runner.py:256-258` passes `adapter_name` whenever it is set, so an untailored config run under `sft_plan`
requests a phantom alias that is not in `--lora-modules`. vLLM then silently serves the BASE model while
`usage.model` names the alias — a believable number measuring a configuration no arm runs in. This is the
exact hazard X38b fixed for the narrated arms; `configs/hj16_narrated_m9_zs.yaml` is the pattern to follow.

## B. Six configs replaying the cap-81 planner sample

The second sample is `/scratch/n12194778/sidekick/results/hj13_planner_alone_cap81_20260923`, system
`planner_alone`, 114 `result.json` files (verified). For each new file, copy the named template and change
ONLY the header comment, `campaign_id`, `handoff.source_campaign` and `planner.packet_source` (both point
at the cap-81 campaign so the plan and the replayed actions come from the same sample).

| new file | copy from |
|---|---|
| `configs/hj17_prefix_c81_zs_m6.yaml` | `configs/hj13_prefix_zs_m6.yaml` |
| `configs/hj17_prefix_c81_zs_m9.yaml` | `configs/hj13_prefix_zs_m9.yaml` |
| `configs/hj17_prefix_c81_zs_m11.yaml` | `configs/hj13_prefix_zs_m11.yaml` |
| `configs/hj17_prefix_c81_bplus_m6.yaml` | `configs/hj12_prefix_m6.yaml` |
| `configs/hj17_prefix_c81_bplus_m9.yaml` | `configs/hj12_prefix_m9.yaml` |
| `configs/hj17_prefix_c81_bplus_m11.yaml` | `configs/hj12_prefix_m11.yaml` |

`campaign_id` is the file's basename plus `_20260923`, e.g. `hj17_prefix_c81_zs_m6_20260923`.
Each header comment must state: replays the **cap-81** planner sample (0.7637 goal_pass) rather than the
cap-25 `hj1b` sample (0.8284), as the second-planner-sample generality check; and that `handoff.m` is
unchanged from the template.

⚠ `configs/hj12_prefix_*.yaml` are **frozen** — copy them, never edit them.

## C. Register all nine in the PBS runner

`scripts/pbs/hj12_prefix.pbs`, the `FREE_ARMS` array (`:149-179`). Append nine lines in the existing
`system|abs_config_path|arm_name` format, using `${REPO}` exactly as the neighbouring lines do:

```
executor_alone|${REPO}/configs/hj15_executor_alone_zsq.yaml|hj15_executor_alone_zsq
prompt_only|${REPO}/configs/hj15_prompt_only_zsq.yaml|hj15_prompt_only_zsq
prefix_handoff|${REPO}/configs/hj15_prefix_zsq_m11.yaml|hj15_prefix_zsq_m11
prefix_handoff|${REPO}/configs/hj17_prefix_c81_zs_m6.yaml|hj17_prefix_c81_zs_m6
prefix_handoff|${REPO}/configs/hj17_prefix_c81_zs_m9.yaml|hj17_prefix_c81_zs_m9
prefix_handoff|${REPO}/configs/hj17_prefix_c81_zs_m11.yaml|hj17_prefix_c81_zs_m11
prefix_handoff|${REPO}/configs/hj17_prefix_c81_bplus_m6.yaml|hj17_prefix_c81_bplus_m6
prefix_handoff|${REPO}/configs/hj17_prefix_c81_bplus_m9.yaml|hj17_prefix_c81_bplus_m9
prefix_handoff|${REPO}/configs/hj17_prefix_c81_bplus_m11.yaml|hj17_prefix_c81_bplus_m11
```

Check `:853`-ish (the free-system case list) already accepts `executor_alone`, `prompt_only`,
`prefix_handoff` and `sft_plan`; if `executor_alone` or `prompt_only` is missing, add it. Quote the line
you checked in your STATUS file either way.

## D. Tests

Extend `tests/unit/test_hj16_narrated.py` (or add `tests/unit/test_hj17_c81_configs.py` if cleaner) with:

1. `test_c81_configs_point_at_the_cap81_campaign` — all six `hj17_*` configs have
   `handoff.source_campaign` and `planner.packet_source` equal to the cap-81 path, and that path exists.
2. `test_c81_configs_preserve_template_m` — each `hj17_prefix_c81_{zs,bplus}_mN.yaml` has `handoff.m == N`.
3. `test_qwen_zeroshot_configs_have_null_lora` — the three `hj15_*` new configs have
   `executor.lora_name is None` and `executor.model == "Qwen/Qwen3-8B"`.
4. `test_untailored_qwen_plan_arm_is_not_registered_under_sft_plan` — parse the `FREE_ARMS` block of
   `scripts/pbs/hj12_prefix.pbs` and assert the line naming `hj15_prompt_only_zsq` begins `prompt_only|`.
   Follow the real-path style of `test_zs_config_under_sft_plan_would_request_phantom_alias`
   (`tests/unit/test_hj16_narrated.py`) — go through `system_kwargs`/`get_system`, do not re-implement.
5. `test_all_free_arms_configs_exist` — every `FREE_ARMS` line's config path resolves to a real file.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`, `tar`, `rsync`. Never
  background anything. `timeout` on any command you do run.
- Do not edit `src/sidekick/**`, any `hj8_*`/`hj11_*`/`hj12_prefix_m*.yaml` config, or any file under
  `docs/prereg_*`. Never read or list `test_normal` / `test_challenge`. Never write under
  `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X39.md`, under 400 words: the nine files created; the exact diff hunk added to
`hj12_prefix.pbs`; the free-system case line you checked, quoted; the test names; and one line per config
confirming `campaign_id` matches the basename. `[OBSERVED path:line]` / `[INFERRED]` on every claim.
**Do not claim any test passes** — you cannot run them.
