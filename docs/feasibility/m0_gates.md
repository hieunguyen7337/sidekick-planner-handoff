# M0 gates G2 / G3 — feasibility (U1)

Measured 2026-09-15 on QUT Aqua. Every number is tagged
`[OBSERVED <path>:<line>]` or `[INFERRED]`. Jobs ran on compute nodes, not `aquarius01`.

Pinned stack:

| artifact | value | evidence |
|---|---|---|
| Python | 3.12.13 | `/scratch/n12194778/sidekick/logs/env_versions.json:2` |
| venv | `/scratch/n12194778/sidekick/env` (7.9G) + uv-cache 12G | `.../logs/venv_du.txt:1-2` |
| torch | **2.13.0+cu130** (CUDA 13.0 wheel, not cu12x) | `env_versions.json:75-76` |
| vLLM | **0.29.0** (>= 0.20) | `env_versions.json:13` |
| transformers / peft / trl / bitsandbytes | 5.17.0 / 0.20.0 / 1.13.0 / 0.50.2 | `env_versions.json` |
| AppWorld | git `42b5bcf3cd334fee33f0c37c02070a9f5807add5` (0.2.0.dev0) | `env_versions.json:50` |
| granite-4.2-8b | `f8de16cdcdbc6c779ca517604e050d82cc119e44` | `fetch_models.json:12` |
| granite-4.2-3b | `e459acceac81e5fe67c07d9cfc72329a332e7eb1` | `fetch_models.json:21` |
| Qwen3-1.7B | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` | `fetch_models.json:28` |
| HF_HOME bytes added | 29002944333 (~27.0 GiB) | `fetch_models.json:6-7` |

`uv pip install torch` first resolved `torch==2.14.0`; `vllm>=0.20` then **downgraded** it to `2.13.0+cu130`. Recorded in `campaign/workers/logs/U1_env_build.out:41,307-323`. Freeze: `/scratch/n12194778/sidekick/env-freeze.txt`.

Exact commands that worked (copy-pasteable):

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 HF_HOME=/scratch/n12194778/hf
cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
qsub scripts/pbs/env_build.pbs          # job 25383489, Exit_status 0
qsub scripts/pbs/g2_appworld.pbs        # latest good: 25384720, Exit_status 0
# GPU: site remaps -q gpu_inter -> gpu_batch_exec. hpc --gpu still started:
hpc --async --gpu -c 12 -m 64gb -t 02:00:00 bash scripts/setup/g3_serve_granite.sh
# job 25384419, Exit_status 0. CUDA_HOME must point at pip nvcc (see G3 failures).
```

Site note: `cpu_inter_exec` / `gpu_inter_exec` are `from_route_only`. `#PBS -q cpu_inter` still landed on `cpu_batch_exec`; GPU jobs landed on `gpu_batch_exec`. Putting `qlist=gpu_inter_exec` in `select` while the hook sets `Resource_List.qlist=gpu_batch_exec` makes the job *Can Never Run*. Do not do that.

---

## G2 — AppWorld

**Verdict: PASS**

(split sizes differ from the 105/60/168/417 table; treated as a finding, not a bug.)

### Commands

```bash
export APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld
export APPWORLD_COMMIT=42b5bcf3cd334fee33f0c37c02070a9f5807add5
# inside the venv, after materializing Git LFS bundles (gate script does this):
appworld install
appworld download data --root "$APPWORLD_ROOT" --with-setup
appworld verify tasks --root "$APPWORLD_ROOT" --with-setup
# then scripts/setup/g2_appworld_gate.py
```

### Failures (verbatim) then recovery

1. First G2 job `25384166` (`campaign/workers/logs/U1_g2_appworld.out:34`):
   ```
   Exception: File /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/appworld/.source/apps.bundle is a Git LFS pointer and not a bundle file.
   ```
   Cause: `uv pip install git+https://...@42b5bcf3...` left LFS pointer files. Gate now downloads the blobs from `media.githubusercontent.com` (apps.bundle 193950 B, tests.bundle 204701 B). Then `appworld install` and `download data` succeed.

2. In-process `time.perf_counter()` after `AppWorld(...)` returns 0 / epoch-sized junk because AppWorld's `freezegun` patches it. First JSON had `execute_print1.mean_s = 0.0` and load times ~1.68e9. Fixed by `time.clock_gettime(CLOCK_MONOTONIC_RAW)`. Numbers below are from that rerun (job `25384720`).

### `appworld verify tasks`

```
✅ Passed 147/147 tasks
```

[OBSERVED `/scratch/n12194778/sidekick/logs/g2_appworld_gate.json:56`]

### Split sizes

| split | expected | observed | source |
|---|---|---|---|
| train | 105 | **90** | `g2_appworld_gate.json:60-61` |
| dev | 60 | **57** | `:71` |
| test_normal | 168 | **168** | `:81` |
| test_challenge | 417 | **417** | `:91` |

Train −15, dev −3 versus the brief. Tests match. Finding, not a local bug.

### Programmatic loop

- Probe task `82e2fac_1` — instruction: "[instruction omitted: AppWorld protected content]" [OBSERVED json `instruction_head`]
- Ground truth executed as `compiled_solution_code + "\nsolution(apis, requester)"` [OBSERVED `ground_truth_run.method`]
- `world.evaluate()` type: `TestTracker` [OBSERVED `:145`]
- `world.task_completed()` → `true` [OBSERVED `:186`]

**`world.evaluate().to_dict()` shape (paste for the harness):**

```json
{
  "success": true,
  "difficulty": 1,
  "num_tests": 2,
  "passes": [
    {"requirement": "assert answers match.", "label": "no_op_fail"},
    {"requirement": "assert no model changes.", "label": "no_op_pass"}
  ],
  "failures": []
}
```

[OBSERVED `g2_appworld_gate.json:169-184`]

There is **no `tgc` / `sgc` key**. The seam's `BaseEnv.evaluate() -> {success, tgc, sgc, report}` must map `success` itself (and optionally `len(passes)/num_tests`). `TestTracker` also exposes `.success`, `.report()`, `.to_dict()`, `.task_completed` [OBSERVED `:145-167` dir listing].

### Measurements

| quantity | value | tag |
|---|---|---|
| first world load | 2.283 s | [OBSERVED `g2_appworld_gate.json:224`] |
| later world load | 0.165 s | [OBSERVED `:225`] |
| `execute("print(1)")` mean / min / max (n=20) | 0.0164 / 0.0139 / 0.0309 s | [OBSERVED `:197`] |
| 8 worlds × 8 processes wall | 4.716 s | [OBSERVED `: parallel.wall_s`] |
| 8/8 succeeded | true | [OBSERVED `:693`] |
| peak RSS / process | 585–606 MB (max 606192 kB) | [OBSERVED `:704`] |
| max safe pool on 32 CPUs | **32** (CPU-bound; ~0.6 GB/world so RAM is not the limiter on a 256 GB node) | RSS observed; 256 GB and 70% headroom **[INFERRED]** |
| `api_docs` raw | 475943 chars (~118986 tok @ 4 chars) | chars [OBSERVED `:188`]; tokens **[INFERRED]** `:189` |
| after `compress_parameters()` | 228378 chars (~57095 tok) | [OBSERVED `:189` region]; `has_compress_parameters: true` |

One world per process holds: eight spawn workers with unique `experiment_name=g2_par/roll_out_<k>` all returned `ok: true`. Do not share an `AppWorld` across threads in one process (`freezegun`).

---

## G3 — Granite 4.2-8B + LoRA

**Verdict: PASS**

Executor is `GraniteForCausalLM` on one **NVIDIA H100 80GB HBM3** (`gpu1n011`). Do **not** fall back to Qwen3-8B for LoRA serving — it worked.

### Commands that worked

```bash
export HF_HOME=/scratch/n12194778/hf
export CUDA_HOME=/scratch/n12194778/sidekick/env/lib/python3.12/site-packages/nvidia/cu13
export PATH="$CUDA_HOME/bin:$PATH" LD_LIBRARY_PATH="$CUDA_HOME/lib:${LD_LIBRARY_PATH:-}"
export VLLM_ALLOW_RUNTIME_LORA_UPDATING=1
# 1) PEFT smoke (already saved):
/scratch/n12194778/sidekick/env/bin/python scripts/setup/g3_lora_smoke.py
# 2) serve (flags that actually came up):
vllm serve ibm-granite/granite-4.2-8b \
  --served-model-name granite-4.2-8b --dtype bfloat16 --max-model-len 32768 \
  --enable-lora --max-loras 4 --max-lora-rank 64 \
  --tool-call-parser qwen3_coder --enable-auto-tool-choice \
  --reasoning-parser granite_thinking_parser \
  --reasoning-parser-plugin $HF_HOME/hub/models--ibm-granite--granite-4.2-8b/snapshots/f8de16cdcdbc6c779ca517604e050d82cc119e44/granite_thinking_parser.py \
  --gpu-memory-utilization 0.85 --host 127.0.0.1 --port 8000
```

`granite_thinking_parser` **was accepted** on vLLM 0.29.0 with the plugin file from the model repo. No need to drop it.

### Failures (verbatim) then recovery

1. First serve (job `25384170`) died in FlashInfer JIT warmup:
   ```
   RuntimeError: Could not find nvcc and default cuda_home='/usr/local/cuda' doesn't exist
   ```
   [OBSERVED `campaign`/hpc spool + `/scratch/n12194778/sidekick/logs/g3_vllm_flag_attempts.txt` from that attempt]
   Fix: `CUDA_HOME=.../site-packages/nvidia/cu13` (pip `nvidia-cuda-nvcc`). Restart job `25384419` then reached ready in **76 s** [OBSERVED `g3_serve.json` `load_s`].

2. Probe helper set `lora_served=false` because it only looked at `message.content`, which is `null` while Granite is still thinking. The adapter **did** return text in `message.reasoning` with HTTP 200 and `"model": "smoke_lora"`. Treat as LoRA-serve **PASS**. After `--lora-modules` restart, reasoning even drifted toward the smoke-train template ("Say the number 29 twice") — evidence the adapter is actually on the GPU.

### OpenAI `usage` block (verbatim, cost ledger)

Chat `/v1/chat/completions` (job `25384419`):

```json
{
  "prompt_tokens": 22,
  "total_tokens": 128,
  "completion_tokens": 106,
  "prompt_tokens_details": null,
  "completion_tokens_details": { "reasoning_tokens": 0 }
}
```

[OBSERVED `/scratch/n12194778/sidekick/logs/g3_probe.json` chat usage]

Tool-calling request (same server; parser `qwen3_coder`): HTTP 200, tool `get_current_weather` args `{"city": "Boston"}`. Usage:

```json
{
  "prompt_tokens": 288,
  "total_tokens": 386,
  "completion_tokens": 98,
  "prompt_tokens_details": null,
  "completion_tokens_details": { "reasoning_tokens": 0 }
}
```

No `cached_tokens` / `cached_input_tokens` on these short prompts [OBSERVED]. Ledger should default cached to 0.

Chat content: `"Hello!"`. Tool `content` null, `tool_calls` populated.

### Measurements

| quantity | value | tag |
|---|---|---|
| GPU | H100 80GB HBM3, 81559 MiB | [OBSERVED `g3_lora_smoke.json:14`] |
| LoRA train: model load | 6.19 s | [OBSERVED `g3_lora_smoke.json:21`] |
| LoRA train wall / trainer runtime | 16.95 s / 16.70 s (max_steps=20, r=64, α=128) | [OBSERVED `:30-32`] |
| Peak GPU train (nvidia-smi / torch max alloc) | 22483 MiB / 22548054528 B (~21.0 GiB) | [OBSERVED `:44, :62`] |
| Adapter files | `adapter_config.json`, `adapter_model.safetensors`, tokenizer | [OBSERVED `:47-53`] saved under `/scratch/n12194778/sidekick/artifacts/adapters/smoke_lora` |
| vLLM ready | 76 s | [OBSERVED `g3_serve.json` `load_s`] |
| Serving GPU | 70059–70165 MiB / 81559 MiB | [OBSERVED `g3_serve.json` + `g3_probe.json:6`] |
| First-token latency (stream) | 0.0279 s | [OBSERVED `g3_probe.json` `stream_ttft.ttft_s`] |
| tok/s concurrency 1 | 133.3 (32 completion tokens / 0.240 s) | [OBSERVED conc1] |
| tok/s concurrency 16 | 1807.5 (512 completion tokens / 0.283 s wall; 16/16 ok) | [OBSERVED conc16] |
| Dynamic LoRA load | HTTP 200 `Success: LoRA adapter 'smoke_lora' added successfully.` | [OBSERVED `lora_load`] |
| Adapter request | HTTP 200, `model=smoke_lora`, text in `message.reasoning` | [OBSERVED `lora_chat.body`] |

`--max-lora-rank 64` is required (train r=64). `--max-loras 4` as specified.

---

## Implications for the harness (not implemented here)

- AppWorld `evaluate().to_dict()` ≠ seam dict; map `success` (and `num_tests`/`passes`) yourself.
- Freeze time inside a world: use `CLOCK_MONOTONIC_RAW` (or equivalent) for step latency.
- Pool size: 1 world / process; 32 is safe on a 32-CPU node at ~0.6 GB RSS.
- Executor prompts: uncompressed `api_docs` ~476k chars; `compress_parameters()` ~228k. Budget accordingly.
- vLLM `usage` uses `prompt_tokens` / `completion_tokens` / `completion_tokens_details.reasoning_tokens`. Thinking text may sit in `message.reasoning` with `content=null`.
- Serving Granite 4.2-8B + LoRA on 1×H100 at `max_model_len=32768` fits (~70 GiB). Set `CUDA_HOME` to the pip CUDA 13 tree or module CUDA before `vllm serve`.
