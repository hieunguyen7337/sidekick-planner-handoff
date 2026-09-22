# STATUS X24 — tailoring arms

**Unit:** X24  
**State:** complete  
**Submitted:** nothing. No `qsub` of eval or `train_sft.pbs`. Data build and pytest used `hpc` only.

## Task A — zero-shot receiver

Configs (copies of frozen `hj12_prefix_m{6,9,11}`; only header, `campaign_id`, `executor.lora_name` differ):

- `configs/hj13_prefix_zs_m6.yaml` (`hj13_prefix_zs_m6_20260923`)
- `configs/hj13_prefix_zs_m9.yaml` (`hj13_prefix_zs_m9_20260923`)
- `configs/hj13_prefix_zs_m11.yaml` (`hj13_prefix_zs_m11_20260923`)

`lora_name: null` is the checkable no-adapter form. `VLLMExecutor.complete` sends `model = kw.lora_name or self.lora_name or self.model` [OBSERVED `src/sidekick/agents/executor.py:248`]. `run_episode` passes `lora_name=policy.adapter_name` [OBSERVED `src/sidekick/systems/loop.py:489`]. `PrefixHandoff.policy_defaults.adapter_name` is now `None` so a null YAML key does not re-inject the old `sft_plan` alias (a mismatch still hits BASE while `usage.model` names the alias) [OBSERVED `src/sidekick/systems/prefix_handoff.py:50`]. Tailored configs still overlay `sft_b_plus` via `system_kwargs` [OBSERVED `src/sidekick/runner.py:288-290`].

**Run-record check.** On executor `action` events: zero-shot has `usage.model == ibm-granite/granite-4.2-8b` and `usage.raw.lora_name == null` [OBSERVED `executor.py:332,346`]; tailored has both equal to `sft_b_plus`. `run_start.payload.policy.adapter_name` matches [OBSERVED `loop.py:627`]. Test: `test_zero_shot_configs_resolve_to_base_not_sft_b_plus_alias` POSTs those model ids.

`FREE_ARMS` added (nothing else in that PBS):

```
"prefix_handoff|${REPO}/configs/hj13_prefix_zs_m6.yaml|hj13_prefix_zs_m6"
"prefix_handoff|${REPO}/configs/hj13_prefix_zs_m9.yaml|hj13_prefix_zs_m9"
"prefix_handoff|${REPO}/configs/hj13_prefix_zs_m11.yaml|hj13_prefix_zs_m11"
```

[OBSERVED `scripts/pbs/hj12_prefix.pbs:144-146`]

## Task B — suffix adapter data

JSONL: `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_handoff_granite8b_20260923.jsonl`  
Manifest beside it. Source: 270 train episodes, seeds 1–3 [OBSERVED `ls` of `hj2b_planner_train_20260916/planner_alone`]. `hpc` job `25682548.aqua`, 1065s, exit 0. No HANDOFF note (`grep -c HANDOFF:` = 0).

| m | rows | dropped too short |
|---|------|-------------------|
| 6 | 258 | 12 |
| 9 | 215 | 55 |
| 11 | 156 | 114 |

[OBSERVED manifest `:11-15,:18-19,:24-28`]. 258+12 = 215+55 = 156+114 = 270. Total sequences 629. `m=11` keeps 156/270; that sparsity is visible, not inferred later.

Masking test: `test_cut_m2_masks_exact_prefix_token_positions`. Known 4-action trajectory, cut `m=2`. Asserts the full `labels` vector and the **exact position lists** of `-100` vs real ids via CharChatTokenizer template deltas; prefix assistant spans are all `-100`, suffix assistant spans equal `input_ids`.

Hyper-parameters matched to iaware (data is the only intended difference). From `scripts/pbs/train_sft.pbs:54-78` and iaware `manifest.json` `:48-75,:100`: epochs 2, lr `1e-4`, rank 64, seed 42, effective batch 8 (`per_device=1`, `grad_accum=8`), `max_length` 32768, cosine, `warmup_steps` 0.03, bf16, grad checkpointing, `lora_alpha` 128, dropout 0.05, target modules q/k/v/o/gate/up/down. Unrun:

```
qsub -v DATA_JSONL=/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_handoff_granite8b_20260923.jsonl,ADAPTER_OUT=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_handoff_granite8b,BASE_MODEL=ibm-granite/granite-4.2-8b scripts/pbs/train_sft.pbs
```

## Suite

Ignored `tests/unit/test_j8_frontier.py` (other unit). Job `25682449.aqua`.

```
timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib --ignore=tests/unit/test_j8_frontier.py'
484 passed, 1 skipped, 1 warning in 43.36s
```
