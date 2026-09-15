# M0 feasibility gates — verified results, 2026-09-15

Every number here was read from a job artifact or a job log, not from a worker's summary. Job ids are
given so each claim can be re-checked. Worker-authored detail lives alongside this file; where the two
disagree, this one was verified independently.

| gate | question | verdict |
|---|---|---|
| **G1** | Can the frozen planner be called from a batch node, with token accounting? | **PASS** |
| **G2** | Does AppWorld install, evaluate and parallelise without containers? | **PASS** (after a Git LFS fix) |
| **G3** | Does Granite 4.2-8B train a LoRA and serve it under vLLM? | **PASS** |
| **G4** | Is the luna worker sandbox usable on the login node? | **FAIL** (does not affect the study) |

---

## G1 — the planner, from a compute node

Job 25382616 on `cpu1n045`, 60 s including queue.

- `codex exec` reached the API and returned the requested token; exit 0.
- Usage accounting present in the JSON stream: `input_tokens`, `cached_input_tokens`,
  `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens`.
- `thread.started` carried a `thread_id`, so `codex exec resume` is available for multi-turn and for
  prompt caching.
- With `--disable shell_tool` there were **zero** bwrap or landlock mentions in stderr: no sandbox is
  created, so the login-node sandbox failure cannot affect the harness.
- No `rate_limits` field, confirming ChatGPT-plan quota is invisible from inside jobs.

**The cost fact that shapes the budget:** a trivial prompt still consumed **15,378 input tokens** of
Codex scaffolding. Every fresh call pays that before our prompt. Hence thread resume (cached input bills
at 10%) and a hard per-episode cap on planner calls.

## G2 — AppWorld

Jobs 25384166 (failed), 25384179 (fix), 25384181 (pass), all on `cpu1n040`.

**It failed first, for a reason worth keeping.** AppWorld ships its app implementations and evaluation
tests as encrypted bundles tracked in Git LFS. A `pip install git+…` does not fetch LFS objects and
`git-lfs` is not installed on this cluster, so both bundles arrived as 131-byte pointer stubs and
`appworld install` refused them.

The fix fetches each object over plain HTTPS from GitHub's media endpoint and verifies it against the
sha256 in the pointer it replaces, refusing to install on a mismatch. Both matched their declared sizes,
193,950 and 204,701 bytes. `scripts/setup/fix_appworld_lfs.sh` is idempotent.

After the fix:

| measurement | value |
|---|---|
| `appworld install` / `download data` / `verify tasks` | all exit 0 |
| Data on disk | 195 MB, 733 task directories |
| 8 worlds in 8 processes | all 8 succeeded, **5.05 s** wall |
| `world.evaluate()` returns | `success`, `difficulty`, `num_tests`, `passes`, `failures` |
| Gate failures | 0 |

**⚠ The published split sizes are wrong for the installed data.** `load_task_ids` returns:

| split | paper / README | measured |
|---|---|---|
| train | 105 | **90** |
| dev | 60 | **57** |
| test_normal | 168 | 168 |
| test_challenge | 417 | 417 |

Both test splits match exactly, so the loader is correct and the supervised pool is simply 14% smaller
than planned. All planning numbers now use the measured values. The cause should be established before
the number appears in a paper.

## G3 — Granite 4.2-8B: LoRA training and serving

Jobs 25384170 and 25384419 on `gpu1n011`, one H100 80 GB.

**LoRA training**

| measurement | value |
|---|---|
| torch / CUDA | 2.13.0+cu130 / 13.0, available |
| Model load | 6.19 s |
| Train (PEFT LoRA r=64, α=128) | 16.95 s, final loss 0.915 |
| GPU after load / after train | 17.6 GB / 20.0 GB |
| Failures | none |

**Serving under vLLM 0.29.0**

| measurement | value |
|---|---|
| Server ready | yes, 76 s load, 70.1 GB of 81.6 GB at `--gpu-memory-utilization 0.85` |
| Chat completion | HTTP 200 in 0.82 s, usage fields present |
| **Dynamic LoRA load** | HTTP 200 via `POST /v1/load_lora_adapter` — "added successfully" |
| **Request routed to the adapter** | HTTP 200, response `model` = `smoke_lora` |
| Throughput, 1 request | 133 tok/s |
| Throughput, 16 concurrent | **1,808 tok/s**, 16 of 16 succeeded |
| Failures | none |

Working flags, exactly:

```
--dtype bfloat16 --max-model-len 32768 --enable-lora --max-loras 4 --max-lora-rank 64
--gpu-memory-utilization 0.85 --tool-call-parser qwen3_coder --enable-auto-tool-choice
--reasoning-parser granite_thinking_parser --reasoning-parser-plugin <snapshot>/granite_thinking_parser.py
```

Two corrections to earlier impressions, both worth recording because they nearly changed a decision:

1. The Granite reasoning-parser plugin **does** work. The first attempts failed while FlashInfer
   JIT-compiled kernels against a CUDA toolkit that is not installed (modules stop at 12.8; torch is
   cu130). Once the compile cache was warm the full configuration started. **Budget ~76 s of startup,
   and expect the first-ever start on a node to be slower.**
2. Runtime adapter loading **does** work through the API, which the sweep design depends on: one server
   can host several variants and route per request rather than restarting between arms.

At 1,808 tok/s for 16 concurrent requests, the throughput assumptions in `HEAVY_JOBS.md` hold.

## G4 — the luna worker sandbox (login node)

**Still broken**, reproduced twice: `bwrap: Creating new namespace failed: Out of memory`, and through
the MCP tool "command execution failed due to insufficient memory".

**Likely cause, found tonight:** login-node memory pressure, not a codex defect. This session's cgroup is
capped at 8 GB, the node had 19 GB free of 187 GB with another user's process holding 7.3 GB, and an
unrelated background wait was OOM-killed in the same window. Each worker CLI costs 150–350 MB, so about
four concurrent units is the practical ceiling.

**This does not affect the study.** The planner path disables the shell tool, so it never creates a
sandbox, which is exactly what G1 demonstrated. Only delegation *to* luna is unavailable; work routes to
the other CLIs instead.

---

## What this means for the campaigns

Nothing in `HEAVY_JOBS.md` is blocked on feasibility any more. The remaining gates on that work are
scientific and budgetary, not technical: approve the planner authentication, and accept the measured
split sizes shrinking the supervised pool by 14%.

The binding constraint is scheduling, not capability. At 21:20 every 4-GPU H100 node was full, a
non-interactive `qsub` is routed to the contended batch queue whatever queue it names, and PBS will not
start a job whose walltime crosses a maintenance window. Submit early, stay at one GPU, keep jobs under
12 hours, and make every campaign resumable.
