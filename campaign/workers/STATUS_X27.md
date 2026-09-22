# STATUS_X27

**State:** complete. Submitted nothing. Downloaded nothing. Did not commit. Did not touch `scripts/analysis/j8_frontier.py`.

## Task A — tokenizer / base-model id

One default: `_DEFAULT_TOKENIZER_ID = ibm-granite/granite-4.2-8b` [OBSERVED `src/sidekick/training/sft_data.py:31`]. `resolve_tokenizer_id` / `_try_tokenizer(name)` / `--tokenizer-id` thread it; unset → granite, then `SIDEKICK_TOKENIZER_ID` [OBSERVED `:34-51,:470-479`]. `matched_sft` labels use `tokenizer_label`, not a second granite string [OBSERVED `matched_sft.py:552,:685`].

Byte-identical default: `tests/unit/test_tokenizer_id.py` (`test_default_and_explicit_granite_jsonl_are_byte_identical`) — default vs `tokenizer_id=ibm-granite/granite-4.2-8b` same JSONL bytes and tokenizer field.

## Task B — Qwen train (unrun)

Cached id **`Qwen/Qwen3-8B`**: hub dir `$HOME/.cache/huggingface/hub/models--Qwen--Qwen3-8B`, `refs/main` = `b968826d9c46dd6066d109eabc6255188de91218`, 5 safetensors shards present [OBSERVED that tree]. **Not** under `/scratch/n12194778/hf/hub` (only `Qwen3-1.7B` there). `train_sft.pbs` now sets `HF_HOME=$HOME/.cache/huggingface` and `HF_HUB_OFFLINE=1` when `BASE_MODEL=Qwen/Qwen3-8B`; granite still forces scratch [OBSERVED `scripts/pbs/train_sft.pbs:40-50`].

Same data as granite iaware: `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl` (`data_sha256` `f2f439d9a24df8e1ac3ca5f94a4f0360aeb23e7564597a082f26dbaf5c77d066`) [OBSERVED adapter `manifest.json:4-5`].

Matched HPs (unchanged flags on `train_sft.pbs`; rest from the granite run): epochs 2, lr `1e-4`, rank 64, seed 42 [OBSERVED `train_sft.pbs:63-87`]; `lora_alpha` 128, dropout 0.05, cosine, `warmup_steps` 0.03, bf16, grad checkpointing, `per_device=1`, `grad_accum=8`, `max_length` 32768, targets q/k/v/o/gate/up/down [OBSERVED `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b/manifest.json:48-75,:100`].

Unrun:

```
qsub -v DATA_JSONL=/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl,ADAPTER_OUT=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_qwen8b,BASE_MODEL=Qwen/Qwen3-8B scripts/pbs/train_sft.pbs
```

## Task C — hj14 eval

Configs (campaign_id `hj14_*_20260924`, model `Qwen/Qwen3-8B`, alias `sft_b_plus_qwen8b`):

- `configs/hj14_executor_alone.yaml`
- `configs/hj14_sft_plan.yaml`
- `configs/hj14_prefix_m{2,4,6,7,8,9,10,11}.yaml`

`FREE_ARMS` [OBSERVED `hj12_prefix.pbs:157-166`]:

```
"executor_alone|${REPO}/configs/hj14_executor_alone.yaml|hj14_executor_alone"
"sft_plan|${REPO}/configs/hj14_sft_plan.yaml|hj14_sft_plan"
"prefix_handoff|${REPO}/configs/hj14_prefix_m2.yaml|hj14_prefix_m2"
… m4,m6,m7,m8,m9,m10,m11 same shape
```

Pending arms grouped by `executor.model`; vLLM restarts; granite → `sft_b_plus` / `.../sft_b_plus_iaware_granite8b`; Qwen → `sft_b_plus_qwen8b` / `.../sft_b_plus_iaware_qwen8b` plus home `HF_HOME`. Mismatch of YAML `lora_name` vs served alias is FATAL [OBSERVED `:365-421,:868-950`].

**Verify which base+adapter served an episode:** job log `[hj12] serving_record base_model=… alias=… adapter=…` [OBSERVED `:915`]; `vllm serve <base> … --lora-modules <alias>=<path>` and `/v1/models` contains that base and alias [OBSERVED `:532`]; YAML `executor.model` / `executor.lora_name`; action events `usage.model` and `usage.raw.lora_name` [OBSERVED `executor.py:248,:331-346`]; `run_start.payload.policy.adapter_name` [OBSERVED `loop.py:627`].

**Replay vs chat template:** `_history_from_events` branches on `event_type` only (no `actor`) and emits role/content via `format_executor_action` [OBSERVED `sft_data.py:206-258`]. Prefix eval rebuilds `exec_turns` from that [OBSERVED `loop.py:587-593`]. Templates apply at vLLM from the served base, not in replay. Confirmed by `test_history_from_events_keys_on_event_type_not_actor`.

## Suite

`timeout 900 hpc -c 4 -m 16gb -t 00:20:00 … pytest tests -q --import-mode=importlib` job `25689191.aqua`:

```
543 passed, 1 skipped, 1 warning in 50.59s
```
