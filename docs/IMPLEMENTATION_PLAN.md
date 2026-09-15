# IAES — implementation plan for the QUT Aqua HPC

Status: **plan only, nothing launched** (2026-09-15). Companion to `../RESEARCH_PROJECT_SPEC.md`
(the spec; this plan never overrides it — where they differ, the spec wins and the difference is a
deviation to record in `docs/experiment_registry.md`).

Every fact below is tagged **[measured]** (observed on this cluster today), **[verified]** (checked
against a primary/public source today, source named) or **[VERIFY]** (assumption to be checked by an
M0 unit before anything is built on it). Nothing tagged [VERIFY] may reach a config file untagged.

---

## 0. Decisions in one screen

| question | decision | why |
|---|---|---|
| Where does compute run? | PBS jobs only (`gpu_batch_exec`, `gpu_inter_exec`, `cpu_batch_exec`); the login node only submits/steers | site rule + `hpc-guard` (12 h CPU/wall cap on login processes) [measured] |
| Frozen "frontier" planner | **No API key exists on this box** [measured]. Primary planner A = a locally served open-weight model (`openai/gpt-oss-120b`, 1×H100). Planner B (cross-planner transfer) = a second family (`Qwen/Qwen3.5-122B-A10B`, 2–4×H100) [VERIFY]. Planner C = a true API frontier model on a small *paired evaluation slice only*, if the user funds a key (est. US$300–600) | reproducible, token-accountable, free at the margin; the paper must then say "frozen stronger planner" and use planner C for the frontier claim |
| Executor | `Qwen/Qwen3-8B` (already cached) as primary, `Qwen/Qwen3-14B` as second size; both LoRA r=64; non-thinking mode default, thinking mode as a cost ablation | Apache-2.0, dense (clean LoRA on vLLM), ProST/R2V-class sizes |
| Domains | D1 **AppWorld** (primary, no containers). D2 **Terminal-Bench 2.x** *gated* on the container-runtime unit (M0-G1) — Apptainer without fakeroot means pull prebuilt images or build SIFs on a Docker machine. Fallback D2′ = repo-level tasks via **mini-swe-agent's native Apptainer support** with prebuilt SWE images | AppWorld = ProST comparability + programmatic state eval; TB = R2V comparability; the site has Apptainer only |
| Training stack | `uv` project (Python 3.12), vLLM for serving (OpenAI-compatible, LoRA hot-swap, prefix cache), TRL+PEFT for SFT/DPO, `verl` (or SkyRL) for optional online RL | all pip-installable into a venv on `/scratch`; no custom image build needed (no fakeroot) |
| Storage | code + small results in `~/iaes` (Lustre); models, images, raw trajectories, checkpoints in `/scratch/n12194778/iaes` (Weka, 134 TB free) [measured]; HF cache moved to `/scratch/n12194778/hf` | home already holds 2.04 TB / 17 M files; raw traces are large and file-heavy |
| Who builds it | Claude plans/briefs/verifies; Cursor = harness core & container runner; Cline = schemas, cost, tests, tooling; agy = literature/docs/prereg; luna = fact-finding & audits (standing rule 2026-09-02) | |

---

## 1. Resource inventory (measured 2026-09-15)

### 1.1 Compute

| resource | value | source |
|---|---|---|
| GPU nodes | **14 × (4 × H100 80 GB HBM3)**, 168 CPU, ~1 TB RAM each (13 report `gpu_mem` 85.5 GB; 1 is MIG-sliced 3g.20gb/1g.10gb); **5 × (8 × A100 40 GB)** + 2 other A100 vnodes (16, 28 GPUs — department partitions `saivt_igpu/qvpr/qcr-users`, not ours) | `pbsnodes -a` |
| Driver / CUDA | 580.178.04 / CUDA 13.0 on `gpu1n012`; modules CUDA 11.8–12.8, cuDNN 9.5, GCC ≤ 15.2, Anaconda3/2024.02 | probe job 25380340 |
| `gpu_batch_exec` | ≤ 8 GPU, ≤ 256 CPU, ≤ 1920 GB, **48 h** walltime; per user ≤ 32 GPUs / 32 running jobs; **busy: 271 queued, 87 running, 678 held** | `qstat -Qf` |
| `gpu_inter_exec` | ≤ 2 GPU, 12 CPU, 68 GB, 12 h; ≤ 2 queued/running per user (`hpcwork --gpu`, `hpc --gpu`) | `qstat -Qf` |
| `cpu_batch_exec` | ≤ 2048 CPU, 48 h; 49 nodes × 188 CPU × 1.5 TB | `qstat -Qf`, `pbsnodes` |
| `cpu_inter_pers` | 1 CPU / 4 GB / **368 h** — a persistent slot (candidate for a lightweight run-registry/ledger service) | `qstat -Qf` |
| Maintenance | login banner on 2026-09-15 19:40: **scheduled maintenance window in 12 h 14 min** — jobs whose walltime crosses it will not start until after | `/etc/motd` |
| CPU nodes | RHEL 9.6, Apptainer 1.5.3 (setuid, overlay+underlay+fusemount on, **0 subuid entries → no `--fakeroot`**), no Podman, Docker client only (no daemon/socket on login or compute) | probes 25380336/25380340 |
| Egress from compute nodes | huggingface.co 200, pypi.org 200, github.com 200, registry-1.docker.io 401 (reachable), ghcr.io 401 (reachable); `apptainer exec docker://alpine` pulled and ran | probe 25380340 |
| Python | system 3.9.21; `uv 0.11.18` with CPython 3.11.15 and 3.12.13 already installed | probe |

### 1.2 Storage

| path | fs | size / use | note |
|---|---|---|---|
| `/mnt/hpccs01/home/n12194778` (= `~`) | Lustre | 5.2 PB pool, 83 % full; user 2.04 TB, **17.0 M files**, no hard quota set | keep code + small results here |
| `/scratch/n12194778` (= `/mnt/weka/scratch/...`) | Weka | 683 TB, 134 TB free | models, images, raw traces, checkpoints. **Purge policy unknown [VERIFY]** — ask HPC support; keep manifests + hashes in `~/iaes/results/manifests` so anything purged is re-derivable |
| `/tmp` | Weka (shared, **not node-local**) | 3.7 TB | do not assume node-local disk; use `$TMPDIR` inside jobs, `HPC_SPOOL` for codex workers |

### 1.3 Already cached models (`~/.cache/huggingface/hub`, revisions to be pinned)

Qwen3-8B, Qwen3-32B, Qwen3-30B-A3B, Qwen3.6-27B-FP8, Qwen3.6-35B-A3B-FP8, Qwen3.8-27B (+FP8), gemma-4-31b-it,
granite-4.1-8b-fp8, Ministral-3-14B-Instruct-2512, harrier-oss-v1-27b, Qwen2.5-VL-3B, embedding/reranker models.
→ Qwen3-8B (executor) and Qwen3.8-27B / Qwen3-32B (mid-strength role-swap planners) cost nothing to start with.

### 1.4 Worker lanes and their state

`codex` MCP (gpt-5.6-luna) **failed today** with `bwrap: Creating new namespace failed: Out of memory`
before running anything (session cgroup `memory.max` = 8 GB, `memory.current` = 2.4 GB, 0 stale bwrap
processes; cause not established). Retest before relying on luna for M0; `codex exec` from a PBS job is
the workaround if the login-node sandbox stays broken. Cursor/Cline/agy were not exercised today.

---

## 2. Constraints that shape everything

1. **No frontier API.** The spec's "frozen frontier planner" becomes a *frozen stronger open-weight
   planner* served locally, which is fully reproducible and token-accountable (vLLM `usage` fields,
   `cached_tokens` via prefix caching). The paper's frontier claim rests on planner C (API) if funded;
   otherwise the paper is honestly scoped to "frozen stronger planner" and says so in
   `docs/novelty_boundary.md`. This is the single biggest scientific consequence of the site.
2. **Apptainer only, no fakeroot.** Anything that is a Dockerfile must become a pulled OCI image or a
   SIF built elsewhere. AppWorld is pure Python (Docker optional) [verified: README]. Terminal-Bench 2.x
   is Harbor + Docker/Podman [verified: tbench.ai, harborframework.com]; prebuilt-image packaging exists
   for TB 2.1/4.0 (AnyEval) and Harbor 0.22 has "prebuilt context staging" [verified: search] — whether
   a *public* registry serves every TB-2.x task image is **[VERIFY]** (M0-G1). SWE-bench-family images
   are published on Docker Hub and mini-swe-agent runs natively on Apptainer [verified: README].
3. **48 h walltime, busy queue.** Every long unit checkpoints, writes a STATUS file, and resumes from
   the event log; submit early, size for ≤ 40 h, expect multi-hour queue waits.
4. **Login-node rules bind the workers, not just Claude.** Every brief carries: `timeout` on everything,
   no `python`/`pip`/`tar`/`rsync`/`ffmpeg` on `aquarius01`, installs and runs via `hpc` or `qsub`,
   `OMP_NUM_THREADS=1` on the login node, `env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-<unit>-spool` for codex,
   `-c 'sandbox_workspace_write.network_access=true'` on any codex launch that submits jobs.
5. **Context budget.** Workers receive extracts, not paths to 200 k-token artifacts; result JSON is
   queried with `jq`, never read whole.

---

## 3. Models

### 3.1 Planners (frozen: model id + revision hash + prompt hash + sampling params + vLLM version)

| role | model | serving | status |
|---|---|---|---|
| **A (primary)** | `openai/gpt-oss-120b` — 117 B MoE, 5.1 B active, MXFP4 ≈ 61–65 GB, Apache-2.0, tool-use oriented | 1 × H100, vLLM, `--max-model-len 65536`, prefix caching on | [VERIFY revision + harmony chat template in the pinned vLLM] |
| **B (transfer)** | `Qwen/Qwen3.5-122B-A10B` — 122 B MoE, 10 B active, Apache-2.0 (search: Qwen3.5 lineup 0.8 B–122 B) | BF16 ≈ 244 GB → TP=4 on one H100 node; FP8 → TP=2 | [VERIFY existence/revision/FP8 checkpoint/TP divisibility] |
| B′ (if B fails) | `Qwen/Qwen3.8-Flash-Next` — 180 B total (125 B core + 51 B n-gram table + 4 B MTP), 6 B active, FP8 172.8 GiB; vendor recipe recommends 8×H200 TEP; official FP8 block size 128 is TP-constrained | risky on 4×H100 | [VERIFY TP4 feasibility] — not first choice |
| mid-strength (role swap / capability-gap axis) | `Qwen/Qwen3.8-27B` (dense, Apache-2.0, released 2026-08-14 [verified: VentureBeat/HF]), `Qwen/Qwen3-32B` — both already cached | 1 × H100 each | ready |
| **C (frontier, optional)** | one API model (Claude / GPT / Gemini current tier) for a *held-out paired slice*: 168 AppWorld test-normal tasks × {planner-alone, prompt-only, IAES} × 1 seed ≈ 75 M input tokens (mostly cacheable) + ~5 M output ≈ **US$300–600 at 2026 list prices** | needs a key + budget → **approval required** | not started |

Pair-selection factorial (spec §Model Selection) runs in M3 on 50 AppWorld dev tasks:
planner ∈ {A, B} × executor ∈ {Qwen3-8B, Qwen3-14B} × allocation ∈ {strong-alone, small-alone,
strong-plan/small-exec, small-plan/strong-exec} = 16 configs × 50 tasks × 1 seed = 800 runs
(≈ 4 node-hours). Primary pair = the one with the largest planner–executor gap on which prompt-only
delegation already moves ≥ 30 % of steps to the executor.

### 3.2 Executors (trainable)

| model | params | why | LoRA/serving |
|---|---|---|---|
| `Qwen/Qwen3-8B` (cached) | 8.2 B dense | Apache-2.0; tool calling; the size class of Endless-Terminals/R2V SLMs | PEFT LoRA r=64 on q/k/v/o/gate/up/down; vLLM `--enable-lora` hot-swaps one adapter per system variant |
| `Qwen/Qwen3-14B` | 14.8 B dense | second size (H2 capacity argument; ProST used 14B) | 2 × H100 for SFT at 32 k context |
| alt: `openai/gpt-oss-20b` | 21 B MoE / 3.6 B active | same-family-as-planner-A ablation (planner leakage) | MoE LoRA in vLLM is limited → optional, M7 |
| newer Qwen 3.5/3.6 small dense checkpoints | — | may dominate Qwen3-8B in 2026 | [VERIFY at M1: pick the newest Apache-2.0 dense 7–9 B and 14 B with vLLM LoRA support; freeze before M3] |

Verifier `V_phi`: `Qwen/Qwen3-1.7B` with a 5-head regression/classification top (failure-if-continue,
plan-violation, expected recovery cost, positive-EV-of-intervention, irreversible/unsafe), trained on
counterfactual labels; alternative = a value head on the executor's own LoRA (cheaper at inference).
Router (R2V baseline) = calibrated logistic/GBM over `V_phi` outputs + trajectory features, Brier-calibrated,
CVaR-constrained threshold chosen on dev only [verified: R2V abstract describes a Brier-calibrated, CVaR-constrained router trained on the frozen policy's residual failures].

### 3.3 Cost model (mechanism units first, dollars second)

Per call we log: input/output/cached tokens, latency, GPU-seconds (vLLM metrics), and compute
**FLOPs ≈ 2 × active_params × tokens** (A: 10.2 GFLOP/token; B: 20 GFLOP/token; Qwen3-8B: 16.4 GFLOP/token;
Qwen3-14B: 29.6 GFLOP/token). Dollars come from a *versioned* schedule
`configs/cost/prices_<date>.yaml` holding (i) published per-token hosted prices for the same open models
on the run date and (ii) a $/GPU-hour rate for amortised local serving. FCD is reported on every unit
(tokens, calls, FLOPs, GPU-s, wall, $). Retries and failed calls are logged with `error_type` and count.

---

## 4. Environments and datasets

### 4.1 D1 — AppWorld (primary) [verified: github.com/StonyBrookNLP/appworld README + paper]

- `pip install appworld && appworld install && appworld download data`; Python ≥ 3.11; Docker optional;
  Apache-2.0 (protected bundles: redistribute only encrypted).
- 750 tasks: **train 105 / dev 60 / test_normal 168 / test_challenge 417**; state-based programmatic
  evaluation (`world.evaluate()` / `appworld evaluate`); serverless mode (in-process TestClient) → one
  environment per CPU core, no ports.
- Split policy (frozen now): trajectories for training come **only** from train (+ dev for validation);
  thresholds/ε/hyper-parameters on dev; **test_normal = primary test**; **test_challenge = OOD/harder
  test**, run once per final system. ProST trained on the same public split, so the comparison is fair.
- Executor tools = AppWorld's Python-code action (one `execute(code)` per step) plus `REPORT`,
  `ASK_PLANNER`, `REQUEST_APPROVAL`, `COMPLETE`. Irreversible-action tagging: any API call that
  sends/pays/deletes/posts (AppWorld API metadata lists methods) → `recoverability: irreversible`.
- Contamination: AppWorld (2024) predates all the 2026 models; mitigations = test_challenge, plan
  paraphrases, perturbation suite, and reporting the per-task-family overlap with any public solution
  traces we can find (M7).
- Cost: ~25 steps/task, ~150 k planner prompt tokens (≈ 85 % prefix-cached) and ~8 k output per
  planner-alone run; ≈ 200–400 trajectories / node-hour at 32-way concurrency [INFERRED — measure in M3].

### 4.2 D2 — Terminal domain (gated)

Test set: **Terminal-Bench 2.x** (2.0 = 89 tasks; 2.1 exists as `harbor-framework/terminal-bench-2-1`)
[verified: tbench.ai / GitHub]. R2V-Agent reports TerminalBench as one of its three benchmarks
[verified: arXiv 2605.16604 abstract]; which TB version/subset they used is **[VERIFY]** from the PDF.

Training tasks (TB has no train split): **Endless Terminals** (3,255 procedurally generated tasks,
arXiv 2601.16443), **nvidia/Nemotron-RL-Agentic-Terminal-Pivot-v1** (630 tasks, HF),
OpenThoughts-Agent-v1-RL (723 terminal tasks) [verified: search results; licences and formats **[VERIFY]**].
All are containerised (Dockerfile per task).

**M0-G1 runtime gate (2 weeks max):**
1. Confirm whether TB-2.x task images are pullable from a public registry (Harbor task.toml `docker_image`
   / AnyEval packaging / Harbor 0.22 prebuilt contexts). If yes → `apptainer pull docker://…` on a compute
   node into `/scratch/n12194778/iaes/images/` (est. 89 × 1–5 GB).
2. If not → build the images with Docker on the user's other machine (the one `argus_v23_download/README.md`
   refers to), `docker save | apptainer build task.sif docker-archive://…`, copy SIFs to `/scratch`.
3. Write `TerminalEnv` = a thin Apptainer task runner that consumes the Harbor task format
   (`task.toml`, instruction, `tests/`, solution) using `apptainer instance start --writable-tmpfs
   --containall`, `apptainer exec` for agent commands, and the task's own test script for scoring;
   parity-check 5 tasks against Harbor's Docker run on the other machine (same pass/fail).
4. If neither 1 nor 2 works by the gate deadline → **D2′**: repo-level coding tasks via mini-swe-agent's
   Apptainer backend with prebuilt images from a **time-filtered** source (SWE-rebench / SWE-bench-Live
   monthly slices after the executor's training cutoff) [VERIFY availability]; Terminal-Bench then moves
   to cloud sandboxes (Daytona/Modal via Harbor) **only with an approved budget**.

### 4.3 D3 — repo-level coding (stronger paper; same machinery as D2′)

mini-swe-agent + Apptainer, prebuilt images, time-filtered instances; executor tools = bash only.
Added after M6 only if D1 + D2 are on track.

### 4.4 Perturbation suite (M7, both domains)

Plan paraphrase (planner A re-sampled at T=1.0 → same plan, different wording), omitted success
criteria, conflicting constraints, corrupted/truncated observations (drop 30 % of tool output),
flaky tools (5 % transient failures), injected instructions inside tool output, wrong planner
assumption (plan references a non-existent resource), irreversible-action traps (a task whose shortest
path deletes/pays), long-context accumulation (≥ 40 steps). Each is a config flag on the environment
wrapper, not a new dataset.

---

## 5. What gets built (repo layout as in the spec; only the load-bearing seams are listed)

| component | contract (Claude owns; written identically into every brief that touches it) |
|---|---|
| `src/iaes/protocols/schemas.py` | pydantic v2 models for the delegation packet, executor action, planner response and the **event** record exactly as in the spec; every parse keeps `raw_output`; parse failure is an event (`error_type=parse_error`), never a retry hidden from stats |
| `src/iaes/trajectories/eventlog.py` | append-only JSONL per run (`data/raw/<domain>/<run_id>/events.jsonl`) + run manifest (`results/manifests/<run_id>.json` with config hash, git commit, dirty flag, hardware, vLLM/model revisions, seed); Parquet compaction job writes to `data/interim`; **never rewrites raw** |
| `src/iaes/agents/*` | `Planner`, `Executor`, `Verifier`, `Router` are provider-agnostic: an `LLMClient` interface (OpenAI-compatible HTTP for vLLM; a `MockClient` for tests) returns text + usage; the agents never know which backend |
| `src/iaes/environments/*` | `BaseEnv.reset(task_id, seed) / step(action) / evaluate() / snapshot_hash()`; `AppWorldEnv`, `TerminalEnv` (Apptainer), `MockEnv` (deterministic grid-of-files toy with irreversible actions) |
| `src/iaes/systems/*` | one class per system variant: `planner_alone`, `executor_alone`, `prompt_only`, `fixed_review_k`, `role_swap`, `query_router`, `r2v_router`, `iaes`, `oracle_escalation`, `equal_cost_selfconsistency` — all on the *same* loop and cost code |
| `src/iaes/cost/*` | `PriceSchedule` (dated YAML), `CostLedger` (per-actor tokens/FLOPs/GPU-s/$), reconciliation test against the raw events |
| `src/iaes/annotations/*` | intervention labels (type × necessity × attributed cause) written to `data/interim/annotations/*.jsonl` with annotator id, version, timestamp, confidence; counterfactual-branch builder |
| `src/iaes/rewards/*` | the Lagrangian terms of the spec as pure functions over a trajectory + branches; unit-tested on fixtures |
| `src/iaes/training/*` | thin wrappers: `sft.py` (TRL SFTTrainer + PEFT, loss masks), `dpo.py` (TRL DPOTrainer), `verifier.py`, `online.py` (verl config generator) |
| `scripts/pbs/*.pbs` | job templates: `serve_planner.pbs`, `serve_executor.pbs`, `collect.pbs`, `train_sft.pbs`, `train_dpo.pbs`, `eval.pbs` — each writes `STATUS.md` and is resumable |
| `AGENTS.md` | the worker rules of §2.4 + seam contracts + "never touch `data/raw`" |

Replay: `iaes replay <run_id>` re-executes the environment from logged actions and asserts the
logged `environment_state_hash` sequence — M2 acceptance criterion.

---

## 6. Experimental program, compute and calendar

Throughput assumptions (to be replaced by M3 measurements): gpt-oss-120b on 1×H100 ≈ 1.5–2.5 k
output tok/s aggregate at 32 concurrent requests; Qwen3-8B ≈ 3 k tok/s; AppWorld env step ≈ 0.2 s;
Apptainer terminal step ≈ 0.5–2 s, instance start ≈ 3–10 s [INFERRED].

| milestone | what runs | GPU budget (H100-h) | wall (incl. queue) |
|---|---|---|---|
| **M0 gates** (parallel with M1) | G1 container runtime; G2 vLLM serving of A + Qwen3-8B in one 2-GPU `gpu_inter` job with throughput numbers; G3 AppWorld install + one scripted task evaluated inside an `hpc` job; G4 cross-node HTTP (vLLM in a GPU job ↔ harness in a CPU job); G5 luna/codex sandbox retest | ~10 | 1–2 wk |
| **M1** foundation | repo, `uv.lock`, literature matrix + bib (verified), novelty boundary, registry, AGENTS.md | 0 | 2 wk |
| **M2** protocol + instrumentation | schemas, event log, cost ledger, mock env, replay, 10 baseline systems on the mock env, CI (`pytest`, no GPU) | 0 | 2–3 wk |
| **M3** untrained pilot | 50 AppWorld dev tasks × {planner-alone, executor-alone, prompt-only, fixed-review k∈{1,3,5}, role-swap} × 2 seeds = 700 runs; pair-selection factorial (800 runs); 20 TB-2 tasks if G1 passed; manual labelling of 100 interventions by 2 annotators (κ reported); power analysis | ~15 | 2 wk |
| **M4** supervised baselines | collect training data on AppWorld train+dev: 165 tasks × (8 planner-alone + 8 prompt-only) samples + counterfactual branches at every intervention (≈ 6 k trajectory-equivalents ≈ 30 node-h); terminal train subset 600 tasks × 4 samples × 2 systems (≈ 100 node-h if G1 passed). Train 4 SFT variants × 2 sizes (≈ 80 GPU-h). Evaluate each on test_normal × 3 seeds | ~350 | 3 wk |
| **M5** verifier + R2V | labels from branches; `V_phi`; router; oracle router; threshold sweeps (≈ 10 GPU-h training + 50 GPU-h evaluation) | ~60 | 2 wk |
| **M6** IAES | preference pairs from branches/corrections; DPO on the best SFT (≈ 8 GPU-h × 6 penalty ablations × 2 sizes); joint executor+escalation training; multiplier sweep (5 λ settings); optional online RL with verl (2 nodes × 4 H100 × 24–48 h = 200–400 GPU-h); full ablation table on test_normal × 3 seeds | ~300 (+400 if online RL) | 4 wk |
| **M7** generalisation/safety | cross-planner (train A → eval B, and C if funded), test_challenge (417 × 1 seed × 6 systems), TB-2 full (89 × 3 seeds × 14 systems ≈ 3.7 k runs ≈ 60–120 node-h), perturbation suite (+30 %), blinded attribution of 200 failures | ~250 | 3 wk |
| **M8** paper artifacts | tables/figures from result files; prereg vs. outcome reconciliation; release checklist | 0 | 2 wk |
| **total** | | **≈ 1,000–1,400 H100-h** (≈ 250–350 node-hours on 4×H100 nodes) | **≈ 5 months** |

The per-user cap is 32 GPUs and the queue is contended, so the campaign is planned as many ≤ 40 h
jobs of 1–4 GPUs each rather than a few large ones; `results/manifests/` is the resume index.

### 6.1 Job topology

- **Collection / evaluation job** (`gpu_batch_exec`, `select=1:ncpus=64:ngpus=4:mem=512gb`,
  40 h): GPU0 planner A; GPU1 executor vLLM with `--enable-lora --max-loras 4` (all executor variants
  of a sweep share the server); GPU2 verifier + second executor replica; GPU3 spare or planner-B shard.
  Harness + 32–64 AppWorld serverless envs (or 8 Apptainer instances) on the node's CPUs. Everything
  local → no cross-node dependency. Planner B (TP=4) needs its own 4-GPU job + executor in a second job
  (G4 confirms cross-node HTTP; if it fails, B is served FP8 at TP=2 next to a 1-GPU executor).
- **Training job**: `select=1:ncpus=32:ngpus=2:mem=256gb` (8 B, 32 k ctx, grad-ckpt, Liger) or
  `ngpus=4` (14 B); TRL + PEFT + DeepSpeed ZeRO-2 or FSDP; checkpoints every 30 min to `/scratch`.
- **Online RL job** (optional): `select=2:ncpus=64:ngpus=4:mem=512gb`, verl with vLLM rollout, LoRA
  actor, planner A as an external frozen server inside the same allocation.
- **Dev/interactive**: `hpcwork --gpu` (2 GPU, 12 h) for serving smoke tests and `hpc --gpu` for
  one-off commands.

---

## 7. Training plan, concretely

| stage | data | recipe | frozen before | output |
|---|---|---|---|---|
| S0 pilot | M3 runs | none | — | throughput, variance, ε, power, annotation guide v1, failure taxonomy v1 |
| S1 SFT (4 variants) | AppWorld train (+ terminal train subset): (a) generic-agent traces from executor-alone successes + planner-alone successes re-rendered without plans; (b) plan-conditioned: successful prompt-only segments (target = executor action given packet); (c) + correction/recovery: post-correction action as target, failing action loss-masked; (d) ProST-style: curriculum over sub-task depth by epoch | TRL SFT, LoRA r=64/α=128, lr 1e-4 cosine, 2 epochs, 32 k ctx, loss only on executor tokens; 3 seeds for the winner | M3 pair choice | `artifacts/adapters/sft_{a,b,c,d}_{8b,14b}` |
| S2 verifier | counterfactual branches: at each intervention, 3 "continue" branches × ≤ 15 steps → labels (failed-if-continued, violated-plan, recovery cost, PEV of intervention, irreversible) | Qwen3-1.7B + heads, BCE/Huber, temperature scaling on dev; report Brier/ECE/AUROC/AUPRC/FNR@high-risk | S1 winner | `V_phi`, reliability plots |
| S3 IAES-DPO | pairs: (continue ≻ needless ASK), (ASK ≻ risky continue before irreversible), (plan-aligned ≻ later-corrected), (evidence-rich REPORT ≻ report that triggered re-verification); weights from the Lagrangian terms; 5 λ settings | TRL DPO on S1(c), β ∈ {0.05, 0.1}, 1 epoch, LoRA | S2 | `artifacts/adapters/iaes_dpo_λ*` |
| S3′ joint vs sequential | same pairs with the ASK decision (i) trained jointly in the policy vs (ii) executor frozen + R2V router | — | — | H4 evidence |
| S4 online (optional) | verl GRPO, reward = Lagrangian with verified intermediate rewards (state-hash checks, test pass) + reward-hacking probes (planner-call spam, REPORT spam) | 24–48 h, 8 H100 | S3 results | `artifacts/adapters/iaes_rl` |
| S5 calibration | dev only | choose ASK thresholds / λ on dev; **prereg** ε (candidate: 3 pp absolute TGC on AppWorld, justified by pilot paired variance) and safety thresholds in `docs/prereg_v1.md` before any test run of M6 | — | prereg doc |

Training-eval hygiene: task ids of every training example are recorded in the adapter manifest;
`tests/reproducibility/test_split_leakage.py` fails CI if any test task id appears.

---

## 8. Evaluation and statistics (as the spec; the parts this site changes)

- Unit = task instance; runs paired by task × seed across systems (same vLLM seeds; note vLLM is
  only approximately deterministic under batching → 3 seeds, report variance).
- Primary: success (AppWorld TGC + SGC; TB pass), FCD on tokens/calls/FLOPs/GPU-s, total system cost,
  intervention burden, escalation quality, unsafe-action rate. Paired bootstrap CIs (10 k resamples),
  hierarchical logistic regression (task, seed random effects) for success, non-inferiority test
  against planner-alone at ε.
- Denominators always include crashed/parse-failed/timeout runs (`error_type` non-null).
- `scripts/make_paper_tables.py` renders the 12 figures/tables of the spec from `results/metrics/*.parquet`.

---

## 9. Worker routing and the first briefs

| unit | worker | brief (all under `campaign/briefs/`, absolute paths, STATUS file, `[OBSERVED]/[INFERRED]` contract) |
|---|---|---|
| U0.1 model/benchmark verification | luna (read-only, network on) or agy | resolve every [VERIFY] in §3–4: model cards, revisions, licences, vLLM support, TB-2.x image registry, dataset licences; output `docs/verification/2026-09_models_benchmarks.md` |
| U0.2 serving smoke test | Cursor | `hpcwork`-style PBS job: vLLM serving gpt-oss-120b + Qwen3-8B(+LoRA) on 2 GPUs; measure tok/s at 1/8/32 concurrency; `configs/models/*.yaml` |
| U0.3 AppWorld bring-up | Cline | uv project on `/scratch`, `appworld install/download`, run + evaluate one train task with the reference solution inside an `hpc` job; pin versions |
| U0.4 container gate | Cursor | §4.2 steps 1–3 on a compute node; parity table; `docs/feasibility/terminal_apptainer.md` |
| U0.5 cross-node HTTP | Cline | vLLM in a GPU job, curl from a CPU job; record hostnames/ports/latency |
| U1.1 literature + bib | agy, luna cross-check | `docs/literature_matrix.md` (machine-readable YAML block per paper), `paper/bibliography.bib`, `docs/novelty_boundary.md`; every DOI/URL fetched |
| U1.2 schemas + event log + cost + tests | Cline | seam contract from §5 pasted verbatim; ≥ 40 unit tests; no GPU |
| U1.3 harness core + mock env + 10 systems + replay | Cursor | critical path; depends on U1.2's schemas (contract fixed first) |
| U2.1 AppWorldEnv + pilot runner + PBS templates | Cursor | after U0.3; dry-run on 3 tasks with `MockClient` then 3 tasks live |
| U3.1 pilot campaign | Claude dispatches, Cline monitors | launch **only after user approval** |

Claude's own checklist per unit: read the diff, rerun the tests, `jq` the numbers, `hpc-guard --list`
after any long-running worker, one memory line per non-obvious lesson.

---

## 10. Risks and go/no-go gates

| risk | gate / mitigation |
|---|---|
| Open-weight planner is not "frontier" | pilot must show planner A ≥ executor + 20 pp on AppWorld dev and ≥ 30 % of steps delegable; planner C slice if funded; wording in novelty boundary |
| Terminal domain infeasible on Apptainer | M0-G1 two-week gate → D2′ (SWE-style via mini-swe-agent) documented as a spec deviation |
| Queue contention / 48 h cap | resumable jobs, early submission, ≤ 4 GPU units; use A100-40GB nodes for 8 B executor evals |
| AppWorld train split too small (105) → overfitting | dev early-stopping, test_challenge OOD, paraphrase/perturbation suite, terminal domain as second evidence |
| `/scratch` purge | manifests + hashes in git; re-derivation scripts; ask HPC support for the policy |
| Same-family planner/executor (Qwen B × Qwen executor) | that is the H6 measurement, not a confound — but planner A is cross-family by design |
| Worker runaways on the login node | rules in every brief; `hpc-guard` backstop; `--list` after each unit |
| Silent quality loss behind cost gains | unsafe/irreversible rate and constraint adherence are primary metrics; denominators include failures |

---

## 11. Immediate next actions (need the user's word before compute or spending)

1. **Approve M0/M1** (no money; ~10 GPU-h of cluster time): dispatch U0.1–U0.5 and U1.1–U1.3.
2. **Decide the terminal-domain path**: attempt TB-2.x on Apptainer (recommended, 2-week gate) vs. go
   straight to D2′ (SWE-style) vs. fund cloud sandboxes.
3. **Decide on planner C**: obtain an API key + ~US$300–600 budget for the frontier paired slice, or
   accept the "frozen stronger open planner" scoping.
4. Confirm `/scratch/n12194778/iaes` as the data root and ask HPC support for the purge policy.
5. Retest the codex sandbox (`bwrap` failure) so luna units can run; otherwise route U0.1 to agy.

Nothing in this plan has been executed: no model downloaded, no package installed, no job beyond the
two 40-second probe jobs (25380336, 25380340) submitted.
