# Status X37 — Zero-Shot Qwen3-8B Prefix-Handoff Receiver

## Config Paths & Diffs [OBSERVED configs/hj15_prefix_zsq_m6.yaml:1-50, configs/hj15_prefix_zsq_m9.yaml:1-50]

- `configs/hj15_prefix_zsq_m6.yaml`
- `configs/hj15_prefix_zsq_m9.yaml`

Exact diff against `configs/hj14_prefix_m6.yaml` and `configs/hj14_prefix_m9.yaml` [OBSERVED configs/hj14_prefix_m6.yaml:1-28, configs/hj14_prefix_m9.yaml:1-28]:
- Header comment describes zero-shot Qwen3-8B receiver (no LoRA, second-family control).
- `campaign_id`: `hj14_prefix_m{6,9}_20260924` → `hj15_prefix_zsq_m{6,9}_20260923`.
- `executor.lora_name`: `sft_b_plus_qwen8b` → `null` (with explicit no-adapter hazard comment).

## `FREE_ARMS` Entries [OBSERVED scripts/pbs/hj12_prefix.pbs:174-175]

```bash
  "prefix_handoff|${REPO}/configs/hj15_prefix_zsq_m6.yaml|hj15_prefix_zsq_m6"
  "prefix_handoff|${REPO}/configs/hj15_prefix_zsq_m9.yaml|hj15_prefix_zsq_m9"
```

## PBS Harness Hunk [OBSERVED scripts/pbs/hj12_prefix.pbs:916-985]

### Before (`scripts/pbs/hj12_prefix.pbs:914-977`)
```bash
  need_handoff=0
  for spec in "${PENDING_ARMS[@]}"; do
    IFS='|' read -r system cfg stem <<<"${spec}"
    fields="$(hj12_executor_fields "${cfg}")" || exit $?
    arm_model="${fields%%|*}"
    arm_lora="${fields#*|}"
    if [[ "${arm_model}" != "${MODEL}" ]]; then
      continue
    fi
    if [[ -n "${arm_lora}" ]]; then
      alias_ok=0
      for allowed in "${ALLOWED_ALIASES[@]}"; do
        if [[ "${arm_lora}" == "${allowed}" ]]; then
          alias_ok=1
          break
        fi
      done
      if [[ "${alias_ok}" -eq 0 ]]; then
        echo "[hj12] FATAL: ${cfg} executor.lora_name=${arm_lora} not in served aliases ${ALLOWED_ALIASES[*]} for base ${MODEL}"
        exit 2
      fi
    fi
    if [[ "${arm_lora}" == "${ALIAS_SFT_B_PLUS_HANDOFF}" ]]; then
      need_handoff=1
    fi
    GROUP_ARMS+=("${spec}")
  done
  echo "[hj12] serving_record base_model=${MODEL} alias=${EXPECT_ALIAS} adapter=${ADAPTER_PATH} n_arms=${#GROUP_ARMS[@]}"
  register_lora "${EXPECT_ALIAS}" "${ADAPTER_PATH}"
  if [[ "${need_handoff}" -eq 1 ]]; then
    echo "[hj12] serving_record base_model=${MODEL} alias=${ALIAS_SFT_B_PLUS_HANDOFF} adapter=${ADAPTER_SFT_B_PLUS_HANDOFF} n_arms=${#GROUP_ARMS[@]}"
    register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"
  fi
  if [[ "${#LORA_MODULES[@]}" -eq 0 ]]; then
    echo "[hj12] FATAL: no LoRA modules registered for base ${MODEL}; set the matching ADAPTER_* path" >&2
    exit 2
  fi
  if [[ "${#LORA_MODULES[@]}" -gt "${MAX_LORAS}" ]]; then
    echo "[hj12] FATAL: ${#LORA_MODULES[@]} LoRA modules exceeds --max-loras ${MAX_LORAS}: ${LORA_MODULES[*]}" >&2
    exit 2
  fi
  echo "[hj12] lora count ${#LORA_MODULES[@]} <= max-loras ${MAX_LORAS}"

  kill_vllm
  hj12_choose_vllm_port
  model_tag="${MODEL//\//_}"
  VLOG="${LOGDIR}/${JOB_CID}.${JOBTAG}_vllm_${model_tag}.log"
  echo "[hj12] vlog=${VLOG}"
  # The --lora-modules line. Alias comes from ALIAS_* / executor.lora_name, not the directory name.
  setsid "${SIDEKICK_VENV}/bin/vllm" serve "${MODEL}" \
    --served-model-name "${MODEL}" \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --host 127.0.0.1 --port "${VLLM_PORT}" \
    --gpu-memory-utilization 0.85 \
    --enable-lora \
    --max-loras "${MAX_LORAS}" \
    --max-lora-rank 64 \
    --lora-modules "${LORA_MODULES[@]}" \
    > "${VLOG}" 2>&1 &
  VLLM_PID=$!
  echo "[hj12] vllm serve ${MODEL} pid=${VLLM_PID} port=${VLLM_PORT} --enable-lora --max-loras ${MAX_LORAS} --max-lora-rank 64 --lora-modules ${LORA_MODULES[*]}"
```

### After (`scripts/pbs/hj12_prefix.pbs:916-985`)
```bash
  need_expect=0
  need_handoff=0
  for spec in "${PENDING_ARMS[@]}"; do
    IFS='|' read -r system cfg stem <<<"${spec}"
    fields="$(hj12_executor_fields "${cfg}")" || exit $?
    arm_model="${fields%%|*}"
    arm_lora="${fields#*|}"
    if [[ "${arm_model}" != "${MODEL}" ]]; then
      continue
    fi
    if [[ -n "${arm_lora}" ]]; then
      alias_ok=0
      for allowed in "${ALLOWED_ALIASES[@]}"; do
        if [[ "${arm_lora}" == "${allowed}" ]]; then
          alias_ok=1
          break
        fi
      done
      if [[ "${alias_ok}" -eq 0 ]]; then
        echo "[hj12] FATAL: ${cfg} executor.lora_name=${arm_lora} not in served aliases ${ALLOWED_ALIASES[*]} for base ${MODEL}"
        exit 2
      fi
    fi
    if [[ "${arm_lora}" == "${EXPECT_ALIAS}" ]]; then
      need_expect=1
    fi
    if [[ "${arm_lora}" == "${ALIAS_SFT_B_PLUS_HANDOFF}" ]]; then
      need_handoff=1
    fi
    GROUP_ARMS+=("${spec}")
  done
  if [[ "${need_expect}" -eq 1 ]]; then
    echo "[hj12] serving_record base_model=${MODEL} alias=${EXPECT_ALIAS} adapter=${ADAPTER_PATH} n_arms=${#GROUP_ARMS[@]}"
    register_lora "${EXPECT_ALIAS}" "${ADAPTER_PATH}"
  fi
  if [[ "${need_handoff}" -eq 1 ]]; then
    echo "[hj12] serving_record base_model=${MODEL} alias=${ALIAS_SFT_B_PLUS_HANDOFF} adapter=${ADAPTER_SFT_B_PLUS_HANDOFF} n_arms=${#GROUP_ARMS[@]}"
    register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"
  fi
  if [[ "${#LORA_MODULES[@]}" -gt "${MAX_LORAS}" ]]; then
    echo "[hj12] FATAL: ${#LORA_MODULES[@]} LoRA modules exceeds --max-loras ${MAX_LORAS}: ${LORA_MODULES[*]}" >&2
    exit 2
  fi
  echo "[hj12] lora count ${#LORA_MODULES[@]} <= max-loras ${MAX_LORAS}"

  kill_vllm
  hj12_choose_vllm_port
  model_tag="${MODEL//\//_}"
  VLOG="${LOGDIR}/${JOB_CID}.${JOBTAG}_vllm_${model_tag}.log"
  echo "[hj12] vlog=${VLOG}"
  # The --lora-modules line. Alias comes from ALIAS_* / executor.lora_name, not the directory name.
  LORA_SERVE_FLAGS=()
  if [[ "${#LORA_MODULES[@]}" -gt 0 ]]; then
    LORA_SERVE_FLAGS=(
      --enable-lora
      --max-loras "${MAX_LORAS}"
      --max-lora-rank 64
      --lora-modules "${LORA_MODULES[@]}"
    )
  fi
  setsid "${SIDEKICK_VENV}/bin/vllm" serve "${MODEL}" \
    --served-model-name "${MODEL}" \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --host 127.0.0.1 --port "${VLLM_PORT}" \
    --gpu-memory-utilization 0.85 \
    ${LORA_SERVE_FLAGS[@]+"${LORA_SERVE_FLAGS[@]}"} \
    > "${VLOG}" 2>&1 &
  VLLM_PID=$!
  echo "[hj12] vllm serve ${MODEL} pid=${VLLM_PID} port=${VLLM_PORT} ${LORA_SERVE_FLAGS[*]}"
```

## Test Names [OBSERVED tests/unit/test_hj15_prefix_zsq.py:68-175]

In `tests/unit/test_hj15_prefix_zsq.py`:
1. `test_hj15_prefix_zsq_matches_hj14_except_campaign_id_and_lora_name`
2. `test_hj15_prefix_zsq_configs_resolve_to_base_qwen_without_lora`
3. `test_hj15_zsq_free_arms_lines_match_existing_format`
4. `test_qwen_zero_shot_group_does_not_require_qwen_adapter`
5. `test_qwen_group_containing_hj14_prefix_m6_missing_adapter_is_fatal`
6. `test_qwen_group_containing_hj14_prefix_m6_with_adapter_succeeds`

## Unrun Evaluation Command [INFERRED]

```bash
ARMS="hj15_prefix_zsq_m6 hj15_prefix_zsq_m9" DATE=20260923 qsub -v ARMS="hj15_prefix_zsq_m6 hj15_prefix_zsq_m9",DATE=20260923 scripts/pbs/hj12_prefix.pbs
```
