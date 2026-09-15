# U1 — Sidekick environment bring-up and M0 gates G2/G3 (owner: Cursor)

## Deadline — read first

The cluster enters a **maintenance window at 2026-09-16 ~08:00 AEST**. PBS will not start any job whose
walltime exceeds the time remaining. Therefore:

- every job you submit uses **walltime <= 03:00:00**;
- **do not submit any job after 2026-09-16 03:00 AEST** — instead write what is left into STATUS.md;
- prefer the `cpu_inter_exec` / `gpu_inter_exec` queues (nearly empty tonight) over `gpu_batch_exec`
  (189 jobs queued). `hpc` uses the interactive queues by default.

## Goal (what "done" means)

A working Python environment plus verified downloads on `/scratch`, and two feasibility gates answered
with evidence:

- **G2** — AppWorld installs, its data downloads, `appworld verify tasks` passes, one train task can be
  driven programmatically, and N worlds run in parallel with measured per-step latency.
- **G3** — `ibm-granite/granite-4.2-8b` serves under vLLM on one H100 with LoRA enabled, answers an
  OpenAI-compatible request, and a 10-minute PEFT LoRA training smoke run completes on a toy dataset.

Deliverables are the scripts, the STATUS file and a feasibility report. **You are not building the
research harness in this unit** — another worker owns `src/sidekick/`.

## Absolute paths

- Repo (your workspace): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
- Data root (create it): `/scratch/n12194778/sidekick`
- Virtual env: `/scratch/n12194778/sidekick/env`
- HF cache: `/scratch/n12194778/hf`   (export `HF_HOME` to this in every job)
- Your outputs:
  - `scripts/setup/build_env.sh` — builds the venv, installs everything, idempotent, re-runnable
  - `scripts/setup/fetch_models.sh` — downloads the models listed below
  - `scripts/setup/g2_appworld_gate.py` — the AppWorld gate (runs inside a job only)
  - `scripts/setup/g3_serve_granite.sh` and `scripts/setup/g3_lora_smoke.py`
  - `scripts/pbs/env_build.pbs`, `scripts/pbs/g2_appworld.pbs`, `scripts/pbs/g3_granite.pbs`
  - `docs/feasibility/m0_gates.md` — the report (format below)
  - `campaign/workers/logs/U1_STATUS.md` — the STATUS file, updated after every milestone

## Hard constraints (this is a shared HPC login node)

1. **Never run Python, package installs, model downloads, `tar`, `rsync` or `ffmpeg` on the login node
   `aquarius01`.** They run **inside a PBS job**: either `timeout 14400 hpc -c 8 -m 32gb -t 02:00:00 <cmd>`
   or `qsub` with one of your `.pbs` files. `hpc` takes an argv; for a compound command use
   `hpc bash -lc '<cmd>'`.
2. **Put `timeout <seconds>` in front of every command you run**, without exception.
3. On the login node export `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.
4. **Do not run any `git` command.** Claude commits. Do not touch `.git/` or `.claude/worktrees/`.
5. **Never print the value of any token, key or credential.** Names only.
6. Keep any single job under 3 hours and write progress to STATUS.md as you go, so an interrupted unit
   can resume.
7. Do not modify anything under `src/sidekick/`, `campaign/briefs/`, `docs/PLAN.md` or
   `RESEARCH_PROJECT_SPEC.md` — other workers and Claude own those.

## Step 1 — environment (`scripts/setup/build_env.sh`, run via `scripts/pbs/env_build.pbs`)

Use `uv` (already installed at `~/.local/bin/uv`, version 0.11.18, with CPython 3.11.15 and 3.12.13
available). Create the venv at `/scratch/n12194778/sidekick/env` on **Python 3.12**.

Install, in this order, into that venv (use `uv` and let it resolve versions; pin what it resolves into
`/scratch/n12194778/sidekick/env-freeze.txt` at the end):

- `torch` (CUDA 12.x build matching driver 580.178.04 / CUDA 13.0 — the default PyPI cu12x wheel is
  expected to work; record the exact wheel you got)
- `vllm` (needs to be **>= 0.20** for Granite 4.2's `granite_thinking_parser`; record the version)
- `transformers`, `accelerate`, `peft`, `trl`, `datasets`, `bitsandbytes` (optional if it fails)
- `pydantic>=2`, `pyyaml`, `pytest`, `pandas`, `pyarrow`, `httpx`
- `huggingface_hub[cli]`
- **AppWorld from git, not PyPI**: PyPI `0.1.3.post1` lags the `main` branch significantly. Install from
  `git+https://github.com/StonyBrookNLP/appworld@<commit>` where `<commit>` is the current `main` HEAD.
  Resolve that commit hash first with `timeout 60 curl -s https://api.github.com/repos/StonyBrookNLP/appworld/commits/main`
  and **record the hash in STATUS.md and in the report** — everything downstream pins it.

Record disk usage of the venv when finished.

## Step 2 — models (`scripts/setup/fetch_models.sh`)

With `HF_HOME=/scratch/n12194778/hf`, download (inside a job):

| model | why | approx size |
|---|---|---|
| `ibm-granite/granite-4.2-8b` | the executor | ~16 GB bf16 |
| `ibm-granite/granite-4.2-3b` | small-executor fallback / capability-gap arm | ~6 GB |
| `Qwen/Qwen3-1.7B` | verifier backbone | ~3.5 GB |

Use `hf download <repo>` (or `huggingface-cli download`). Record the resolved **revision hash** of each
one — the study pins revisions, not tags. Report the total bytes added to `/scratch`.

## Step 3 — G2, the AppWorld gate (`scripts/setup/g2_appworld_gate.py`)

Inside a job (CPU only, no GPU needed):

1. `appworld install` then `appworld download data` (data bundle is only ~35 MB), with
   `APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld`. Then `appworld verify tasks` (2-3 min) and
   report pass/fail verbatim.
2. Confirm the split sizes with `load_task_ids("train"|"dev"|"test_normal"|"test_challenge")`. Expected
   **105 / 60 / 168 / 417**. Report what you actually got — if it differs, that is a finding, not a bug
   to fix.
3. Drive **one train task** programmatically and evaluate it:
   `AppWorld(task_id=..., experiment_name="g2_probe")`, read `world.task.instruction`, run the task's
   **ground-truth / reference solution** if one is reachable from the API (`world.task.ground_truth`),
   else a trivial `world.execute("print(1)")`, then `world.evaluate()` and `world.task_completed()`.
   The point is to prove the loop works end to end and to see the shape of the evaluate() return value.
   **Paste the actual structure of `world.evaluate()`'s return into the report** — the harness depends
   on it.
4. Measure: time to first world load, time for a later world load, and mean wall time of
   `world.execute("print(1)")` over 20 calls.
5. **Parallelism**: AppWorld mocks time with `freezegun`, which is process-wide, so only ONE world may
   live per process. Verify this by running **8 worlds in 8 separate processes** with
   `multiprocessing.Pool` (each with a unique `experiment_name` such as `g2_par/roll_out_<k>`), each
   executing a few statements and evaluating. Report wall time, whether all 8 succeeded, and peak RSS
   per process. Then state the maximum safe pool size for a node with 32 CPUs.
6. Report the size of `world.task.api_docs` rendered as text (characters and rough tokens), and the same
   after `compress_parameters()` if that method exists. This decides how big the executor prompt is.

## Step 4 — G3, the Granite serving and LoRA gate

Submit ONE GPU job (`hpc --gpu` style, or `scripts/pbs/g3_granite.pbs` with
`select=1:ncpus=12:ngpus=1:mem=64gb`, `-q gpu_inter_exec`, **walltime 02:00:00**):

1. Start vLLM's OpenAI-compatible server on `granite-4.2-8b` with `--enable-lora --max-loras 4
   --max-model-len 32768`, plus the Granite-specific flags from the model card
   (`--tool-call-parser qwen3_coder`, reasoning parser `granite_thinking_parser` if the installed vLLM
   exposes it — if a flag is rejected, report the exact error and retry without it).
2. Wait for readiness, then send one `/v1/chat/completions` request and one tool-calling request.
   Record: model load time, first-token latency, and tokens/sec at concurrency 1 and 16.
   **Report the `usage` block of the response verbatim** — the cost ledger reads those fields.
3. Train a **throwaway LoRA** with PEFT/TRL: r=64, alpha=128, target modules
   `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`, on ~50 synthetic examples for <= 10
   minutes, just to prove the adapter trains and saves. Save to
   `/scratch/n12194778/sidekick/artifacts/adapters/smoke_lora`.
4. Load that adapter into the running vLLM server (dynamic LoRA load, or restart with `--lora-modules`)
   and confirm a request routed to the adapter returns text. **This is the load-bearing check** — if
   LoRA serving does not work for `GraniteForCausalLM`, say so loudly; the fallback executor is
   `Qwen/Qwen3-8B`, which is already in `~/.cache/huggingface/hub`.
5. Record peak GPU memory for serving and for training.

## Return contract

Write `docs/feasibility/m0_gates.md` containing, for each of G2 and G3:

- **Verdict**: PASS / PARTIAL / FAIL, in the first line of the section.
- The exact commands that worked (copy-pasteable), and the version/commit/revision of everything
  installed or downloaded.
- The measurements asked for above, in a table.
- Every failure verbatim: the command, the error text, and what you did next.
- Tag every factual claim `[OBSERVED <path>:<line>]` (a file you wrote, or a job log under
  `~/.hpc-spool/`) or `[INFERRED]`. Do not state a number you did not measure.

Also keep `campaign/workers/logs/U1_STATUS.md` current with: milestone reached, job IDs submitted,
what remains, and the exact command to resume. Finish by printing a summary of at most 25 lines:
the two verdicts, the pinned versions (AppWorld commit, vLLM version, model revisions), the key
measurements, and anything that blocks the harness work.
