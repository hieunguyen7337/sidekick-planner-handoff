# Sidekick — proof-of-concept plan (v2, 2026-09-15)

**A small executor specialised to one frozen hosted planner, trained to know when to call for help.**

Companion to `../RESEARCH_PROJECT_SPEC.md` (the full research spec). This plan is a **deliberately
reduced, resource-matched proof of concept** of that spec. Where the two differ, §2 records the
deviation and why. The v1 plan, which assumed a locally served 120B planner and two benchmark domains,
is superseded and kept at `archive/plan_v1_local_planner_2026-09-15.md`.

Fact tags: **[measured]** observed on this cluster, **[verified]** checked against a primary source
today, **[VERIFY]** an assumption with an owning gate. Nothing tagged [VERIFY] may reach a config file
untagged.

---

## 0. Decisions in one screen

| question | decision | why |
|---|---|---|
| Name | **Sidekick** (package `sidekick`, repo to be renamed `~/sidekick`) | the method in one word: a small executor that serves one planner and knows when to call the hero |
| Frozen planner | **`gpt-5.6-luna` via the Codex CLI**, effort `medium`, shell tool disabled | hosted, frozen, token-billed, verified working from a compute node tonight [measured]; scores 85.1 TGC on AppWorld test_normal [verified] |
| Executor | **`ibm-granite/granite-4.2-8b`**, LoRA r=64; `granite-4.2-3b` as the capability-gap arm; `Qwen/Qwen3-8B` only as a tooling fallback | dense text-only transformer (clean LoRA in PEFT and vLLM), Apache-2.0, already agent/coding post-trained, cross-family to the planner [verified] |
| Verifier | `Qwen/Qwen3-1.7B` + one calibrated head | cheap; one head is enough for a PoC |
| Domain | **AppWorld only** | pure Python, no containers, programmatic state evaluation, a published luna number to anchor against |
| Scope | prove the mechanism, not beat the leaderboard | all claims are internal and paired; see §5 |
| Cost units | planner **tokens / calls / dollars**, executor GPU-seconds | the planner is a closed hosted model, so FLOPs are not available; tokens are what it actually bills |
| Compute | PBS jobs only, 1 GPU per job, ≤ 12 h, resumable | site rule; `gpu_inter_exec` is nearly empty, `gpu_batch_exec` had 189 queued tonight [measured] |
| Storage | code in the repo; data, models, adapters in `/scratch/n12194778/sidekick`; HF cache `/scratch/n12194778/hf` | home already holds 2.04 TB / 17 M files [measured] |
| Budget | ≈ 120 H100-hours, ≈ 33k planner turns, **US$80–130** at luna list prices; proposed cap **US$250** | §7 |

---

## 1. What was measured tonight

**G1 — the planner works from a batch node.** Job 25382616 on `cpu1n045`, 60 s wall [measured]:

| check | result |
|---|---|
| `codex exec` reaches the API from a compute node | exit 0, returned the requested token |
| usage accounting | `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens` all present |
| multi-turn | `thread_id` returned, so `codex exec resume <id>` is available |
| sandbox | **zero** bwrap/landlock mentions in stderr with `--disable shell_tool` → today's bwrap failure cannot affect the harness |
| quota visibility | no `rate_limits` field → plan quota is **invisible** from jobs, as the docs warn |
| scaffolding overhead | a trivial prompt still cost **15,378 input tokens** |

That last number is the single most important cost fact in this plan: every fresh planner call pays
roughly 15k input tokens before our prompt is added. It is why the harness resumes threads (cached input
is billed at 10%) rather than starting fresh ones, and why `max_planner_calls` is capped per episode.

**Cluster** [measured 2026-09-15]: 14 × (4 × H100 80 GB) + 5 × (8 × A100 40 GB); `gpu_inter_exec` ≤ 2
GPU / 12 h and nearly idle; `gpu_batch_exec` ≤ 8 GPU / 48 h but 189 queued / 92 running;
`/scratch/n12194778` on Weka with 135 TB free; maintenance window **2026-09-16 ~08:00**, and PBS refuses
to start any job whose walltime crosses it.

**Codex configuration trap** [measured]: `~/.codex/config.toml` sets `model = "gpt-5.6-sol"` and
`model_reasoning_effort = "xhigh"`. Every harness call must pass `-m gpt-5.6-luna` and
`-c model_reasoning_effort=medium` explicitly, or the experiment silently runs a different, far more
expensive planner. The resolved values are logged into every event.

---

## 2. Deviations from the spec, and why

| spec asks for | this PoC does | reason |
|---|---|---|
| a frozen **frontier** planner | a frozen **hosted** planner, `gpt-5.6-luna` — the cheapest GPT-5.6 tier | no frontier key is funded; luna is genuinely frozen, hosted and billed, and is far stronger than any ≤ 9B executor. The paper says "hosted planner, luna tier", never "frontier" |
| AppWorld **and** TerminalBench | AppWorld only | no Docker/Podman on this cluster and Apptainer has no fakeroot, so Harbor cannot run; a second domain is not needed to prove a mechanism |
| FLOPs-based cost accounting | tokens, calls and dollars for the planner; GPU-seconds for the executor | a closed model exposes no FLOPs |
| two executor sizes (8B + 14B) | one family, 8B primary and 3B as the capability-gap arm | halves the training budget; the size axis is not the claim |
| 5-head verifier | one head ("escalate now") | a PoC needs calibration, not a taxonomy |
| online RL (verl/GRPO) | offline only: SFT then DPO | RL is where the published gains come from, but it is 400+ GPU-hours; the PoC states plainly that it tests offline post-training only |
| 14 system variants | 8 | see §5 |
| cross-planner transfer | optional, out of scope by default | needs a second funded planner |
| ε = 3 pp non-inferiority | ε = 5 pp | smaller sample, honest about power |

Every one of these is recorded as a deviation in `docs/experiment_registry.md` when the study runs.

---

## 3. Models

### 3.1 Planner (frozen)

`gpt-5.6-luna` through `codex exec`. The frozen definition, pinned in every run manifest: model id,
`model_reasoning_effort=medium`, the prompt template hash, Codex CLI version (`0.153.4` tonight), and
the calendar window of the runs. There is no temperature control, so planner sampling noise is handled
by the paired design: all arms of a comparison run in the same window, paired by task and seed.

Invocation, verified tonight:

```
codex exec --json --skip-git-repo-check -s read-only --disable shell_tool \
  -m gpt-5.6-luna -c model_reasoning_effort=medium -C <empty per-call dir> \
  [--output-schema <schema>.json] <prompt>   < /dev/null
```

`--disable shell_tool` is mandatory: it keeps the planner a pure text oracle, keeps costs comparable
across arms, and avoids the sandbox entirely. `--ephemeral` is banned because it silently breaks
`resume`. Multi-turn modes use `codex exec resume <thread_id>` so the stable prefix is cached at 10% of
input price.

**Anchor** [verified from the official leaderboard JSON]: `gpt-5.6-luna` with the "kecaipan capybara"
scaffold scores **85.1 TGC / 73.2 SGC** on test_normal in 9.3 mean interactions, and **73.4 / 52.5** on
test_challenge. Our own planner-alone arm will differ because our scaffold is different; the
leaderboard number is context, and our measured planner-alone arm is the baseline that matters.

### 3.1a Pinned versions (verified 2026-09-15, to be re-confirmed by the M0 gates)

| thing | pin |
|---|---|
| AppWorld | commit `42b5bcf3cd334fee33f0c37c02070a9f5807add5` on `main`, dated 2026-09-03 [verified via the GitHub API] — PyPI `0.1.3.post1` lags `main` |
| `ibm-granite/granite-4.2-8b` | revision `f8de16cdcdbc6c779ca517604e050d82cc119e44`, 4 safetensors shards [verified via the HF API] |
| vLLM | 0.29.0 is current on PyPI; Granite 4.2 needs ≥ 0.20 for `granite_thinking_parser` [verified] |
| Codex CLI | 0.153.4 [measured] |

Every run manifest records these, and a changed pin starts a new run prefix rather than continuing an
old one.

### 3.2 Executor (trainable)

**`ibm-granite/granite-4.2-8b`** [verified from the model card and config.json today]: dense
`GraniteForCausalLM`, 40 layers, hidden 4096, GQA 32/8, 128K native context, bf16, Apache-2.0, released
2026-08-25. Reported: BFCL v4 52.39, τ³-bench 58.06, SWE-bench Verified 47.67, Terminal-Bench 2.1 20.56,
LiveCodeBench v6 73.24, IFBench 79.33, MMLU-Pro 74.04. vLLM ≥ 0.20 with a `granite_thinking_parser`,
tool parser `qwen3_coder`.

Why it beats the alternatives for this study: it is a **plain dense transformer**, so LoRA in PEFT and
adapter serving in vLLM are both first-class — no Mamba layers and no MoE expert routing to work around.
Granite 4.2 is all-dense; the hybrid Mamba-2 variants belong to earlier generations. It is already
post-trained for tool calling and coding, which is exactly the effort we want to avoid spending.

Rejected, with reasons: **Qwen3.5-9B** has the best raw agentic scores (BFCL 66.1) but ships as a
multimodal `Qwen3_5ForConditionalGeneration` with 28 of 32 layers using Gated DeltaNet linear attention,
an open vLLM LoRA crash, and a rejected request for a text-only class — too much engineering risk for a
PoC. **No Qwen 3.6 or 3.8 model exists at ≤ 10B.** `gpt-oss-20b` is the only shortlist model with a
published AppWorld number (76.2 TGC) but shares a family with the planner and has MXFP4 experts.
`Qwen/Qwen3-8B` stays as the fallback if Granite's vLLM LoRA path fails in gate G3; it is already
cached locally.

Adapters: LoRA r=64, α=128, on `q,k,v,o,gate,up,down`. Thinking mode off by default, on as a cost
ablation. Served with `--enable-lora --max-loras 4` so every variant of a sweep shares one server.

### 3.3 Verifier

`Qwen/Qwen3-1.7B` plus a single head predicting "escalating now is worth it", trained on counterfactual
continue-branches, temperature-scaled on dev, reported with Brier score, ECE and AUROC. The same scores
drive the `router_seq` baseline over a frozen executor.

### 3.4 Cost model

Per call we log tokens (input, cached input, cache-write, output, reasoning), latency, and for local
models GPU-seconds. Dollars come from a dated schedule `configs/cost/prices_2026-09.yaml`:
luna at **0.20 / 0.02 cached / 1.20** USD per 1M tokens [verified], local GPU at an assumed
US$2.50/GPU-hour, labelled as an assumption. Reasoning tokens bill as output.

**Frontier-compute displacement**, the headline efficiency metric:
`FCD = 1 − planner_tokens(collaboration) / planner_tokens(planner_alone)`, reported alongside the same
ratio on planner calls and on dollars, always paired by task.

---

## 4. Environment and data — AppWorld

Apache-2.0; the protected bundle may only be redistributed encrypted, and training on model outputs is
explicitly allowed [verified]. Install from a **pinned commit of `main`**, not PyPI: the released
`0.1.3.post1` lags `main` significantly. Data bundle is ~35 MB.

⚠ **Installing AppWorld from git needs a Git LFS workaround on this cluster** [measured, gate G2].
AppWorld ships its app implementations and evaluation tests as encrypted `.bundle` files tracked in Git
LFS. A `pip install git+https://…` does **not** fetch LFS objects, and `git-lfs` is not installed here,
so both bundles arrive as 131-byte pointer stubs and `appworld install` fails with "is a Git LFS pointer
and not a bundle file". Fix: fetch each object over plain HTTPS from
`https://media.githubusercontent.com/media/StonyBrookNLP/appworld/<commit>/src/appworld/.source/<name>.bundle`
and verify it against the `oid sha256` recorded in the pointer it replaces. Both objects were confirmed
to return HTTP 200 at their declared sizes (`apps.bundle` 193,950 B, `tests.bundle` 204,701 B).
`scripts/setup/fix_appworld_lfs.sh` automates this and refuses to install a bundle whose checksum does
not match.

⚠ **Measured split sizes differ from the published ones** [measured, gate G2, job 25384181]. Running
`load_task_ids` against the installed data returns:

| split | paper / README | **measured** |
|---|---|---|
| train | 105 | **90** |
| dev | 60 | **57** |
| test_normal | 168 | 168 |
| test_challenge | 417 | 417 |

The two test splits match exactly, so the loader is behaving; train and dev simply contain fewer task
instances in the installed data version than the paper reports. **All planning numbers below use the
measured values**, which shrinks the supervised training pool by 14% and is worth stating in the paper's
limitations. The cause is not yet established — check whether the shipped data version differs from the
one the paper describes before publishing the number.

Split policy, frozen now:

| split | use |
|---|---|
| train (90) | trajectory collection and all supervised training |
| dev (57) | thresholds, ε, hyper-parameters, prompt iteration, early stopping |
| test_normal (168) | the single final paired evaluation |
| test_challenge (417) | optional out-of-distribution slice, one seed, three systems |

AppWorld's own rule forbids error analysis or prompt tuning on the test splits, and we hold to it.

**Concurrency, the important operational fact** [verified]: AppWorld mocks time with `freezegun`, which
patches process-wide, so **only one world may live per process**. The runner therefore uses
`multiprocessing.Pool` with one world per worker process and a unique `experiment_name` per run.
Threads and asyncio are unusable in unified mode. Gate G2 measures the safe pool size on a 32-CPU node.

Harness limits for every arm, matching the regime used by published AppWorld RL work: **40 interactions
and 32K tokens per episode**, 120 s per step, 25 planner calls. Runs that hit a limit are failures in
the denominator, never dropped.

Executor action space: one `execute(code)` per step, plus `REPORT`, `ASK_PLANNER`, `COMPLETE`.
Irreversible actions (send, pay, delete, post) are tagged from the API metadata and drive the safety
metric.

**Contamination**: AppWorld was published in 2024 and luna's knowledge cutoff is 2026-02-16, so
contamination is plausible and is stated as a limitation. Mitigations: test_challenge, plan paraphrase,
and the fact that every comparison is paired between systems using *the same* planner, which cancels
planner-side memorisation from the contrast that carries the claim.

---

## 5. Systems, and exactly what is being claimed

Eight systems, one loop, one cost path:

| system | role in the argument |
|---|---|
| `planner_alone` | **the baseline the headline claim is measured against** |
| `executor_alone` | shows the raw capability gap and the headroom |
| `prompt_only` | untrained collaboration — is training needed at all? |
| `fixed_k` | cost-matched control: same planner budget, spent on a fixed schedule |
| `sft_plan` | intervention-**agnostic** training: the control for H2 |
| `router_seq` | frozen executor + learned router (sequential), the R2V-style control for H4 |
| `sidekick` | the method: intervention-aware SFT + DPO with verifier-gated escalation |
| `oracle_escalation` | dev-only ceiling on escalation quality |

Hypotheses, all internal and paired:

- **H1** — `sidekick` is non-inferior to `planner_alone` on task goal completion at ε = 5 pp, while
  displacing planner tokens (FCD > 0).
- **H2** — `sidekick` beats `sft_plan` at matched planner cost. This is the intervention-awareness
  claim, and it is the core of the paper.
- **H3** — escalation is calibrated: the verifier beats a fixed schedule (`fixed_k`) and approaches
  `oracle_escalation`, with a low needless-ask rate.
- **H4** — training the escalation decision into the policy (`sidekick`) beats bolting a router onto a
  frozen executor (`router_seq`).

**What is deliberately not claimed**: any leaderboard position, any statement about frontier models, and
any claim about online RL. Published work reaches 87 TGC with on-policy RL on a 14B model; we do offline
LoRA on 90 tasks and say so.

**Realistic expectation, stated in advance.** Published numbers put a frozen ~8B model between 1 and 17
TGC on test_normal, and SFT on a few thousand teacher trajectories around 26–33, while luna is at 85.
So `sidekick` will almost certainly **not** reach non-inferiority at a high displacement rate. The
deliverable is therefore **the quality-versus-displacement frontier**: at what FCD does collaboration
stay within ε, and does `sidekick` dominate `sft_plan`, `router_seq` and `fixed_k` on that frontier.
H2 and H3 are the claims that survive a weak executor; H1 is reported as the frontier curve with the
non-inferiority point marked. This is written down now, before any result, so it cannot be
retrofitted.

---

## 6. What gets built

| component | contract |
|---|---|
| `src/sidekick/protocols/schemas.py` | pydantic v2 types for packet, action, planner response, event, run result; parse failure is a logged event, never a hidden retry |
| `src/sidekick/trajectories/eventlog.py` | append-only JSONL per run plus a manifest (config hash, git commit, model revisions, seed, hostname); raw logs never rewritten |
| `src/sidekick/cost/` | dated price schedule, per-actor ledger, FCD helper |
| `src/sidekick/agents/` | `CodexExecPlanner`, `MockPlanner`, `VLLMExecutor`, `MockExecutor`, verifier and router |
| `src/sidekick/environments/` | `BaseEnv`, `AppWorldEnv` (lazy import, one world per process), `MockEnv` |
| `src/sidekick/systems/` | the eight systems above |
| `src/sidekick/runner.py`, `replay.py` | multiprocessing runner, resumable; replay re-derives state hashes |
| `scripts/pbs/` | job templates, each writing STATUS and resumable |
| `AGENTS.md` | worker rules and the seam contract |

The full seam contract lives in `campaign/briefs/SEAM_CONTRACT.md` and is pasted verbatim into every
brief that touches it.

---

## 7. Programme, budget and calendar

Approximately **10–12 weeks, ≈ 120 H100-hours, ≈ 33k planner turns, US$80–130**.

| milestone | content | GPU-h | planner turns |
|---|---|---|---|
| **M0** gates — **ALL RESOLVED 2026-09-15**, see `feasibility/M0_RESULTS.md` | G1 planner from a batch node **PASS**; G2 AppWorld install/verify/8-way pool **PASS** (needed a Git LFS fix); G3 Granite LoRA train + vLLM adapter serving **PASS** (1,808 tok/s at 16-way); G4 luna worker sandbox **FAIL**, does not affect the study | ≈ 1 used | ≈ 20 used |
| **M1** foundation (1 wk) | uv project, schemas, event log, cost ledger, mock env, tests, AGENTS.md, registry, trimmed literature matrix | 0 | 0 |
| **M2** harness (2 wk) | `AppWorldEnv`, planner client, 8 systems, replay, PBS templates, 3-task live dry run | ≈ 2 | ≤ 100 |
| **M3** pilot (1–2 wk) | dev 57 × {planner_alone, executor_alone 8B/3B, prompt_only, fixed_k} × 2 seeds; capability-gap gate; annotate 50 interventions; **prereg v1 frozen** | ≈ 6 | ≈ 3.5k |
| **M4** data + SFT (2 wk) | train 90 × (2 planner-alone demos + 8 prompt-only rollouts); SFT(b) plan-conditioned and SFT(c) + correction/ASK; dev eval | ≈ 20 | ≈ 7.5k |
| **M5** verifier + DPO (2 wk) | counterfactual branches → labels; verifier; DPO 3 pair types × 3 λ; `router_seq`; oracle; dev eval | ≈ 40 | ≈ 3k |
| **M6** final (1–2 wk) | test_normal 168 × 6 systems × 3 seeds; statistics; optional test_challenge × 1 seed × 3 systems | ≈ 30 (+8) | ≈ 18.6k (+11.7k) |
| **M7** write-up (1 wk) | tables, figures, prereg reconciliation, optional perturbation flags | 0 | ≤ 2k |

Planner spend, computed from the measured 15.4k-token overhead and cached-resume pricing: roughly
**US$80–110**, or **US$130** including test_challenge. Proposed cap **US$250**. On the ChatGPT plan the
same volume is about 4k luna messages per week, which is plausible on Pro and tight on Plus — and
invisible from inside jobs, so a mid-sweep stall would be silent. **Recommendation: use an API key for
M4 onward and keep the plan login for M0–M3.**

Job topology: `select=1:ncpus=32:ngpus=1:mem=128gb`, walltime ≤ 12 h, resumable — one H100 hosts the
executor (vLLM, LoRA hot-swap) and the verifier, 16–32 AppWorld worker processes use the node's CPUs,
and 4–8 concurrent `codex exec` subprocesses talk to the planner. Nothing needs more than one node.

---

## 8. Training

| stage | data | recipe |
|---|---|---|
| S1 SFT(b) plan-conditioned | successful `prompt_only` segments; target = executor action given the packet | TRL SFT, LoRA r=64/α=128, lr 1e-4 cosine, 2 epochs, 32k ctx, loss on executor tokens only |
| S1 SFT(c) + correction/ASK | adds post-correction actions as targets with the failing action loss-masked, and ASK decisions | same |
| S2 verifier | counterfactual continue-branches at each intervention (3 branches × ≤ 10 steps) | Qwen3-1.7B + head, BCE, temperature scaling on dev |
| S3 DPO | pairs: continue ≻ needless ASK; ASK ≻ risky continue before an irreversible action; plan-aligned ≻ later-corrected | TRL DPO on SFT(c), β = 0.1, 1 epoch, LoRA, 3 λ settings |
| S4 calibration | dev only | thresholds and λ chosen on dev; ε and stopping rules frozen in `docs/prereg_v1.md` before any test run |

Every training example's task id goes into the adapter manifest, and a CI test fails if a test-split id
appears.

---

## 9. Evaluation and statistics

Unit of analysis is the task instance, paired by task × seed across systems. Primary outcome is AppWorld
task goal completion, with scenario goal completion reported alongside. Non-inferiority is a one-sided
95% CI on the paired difference against `planner_alone` with ε = 5 pp. Efficiency is FCD on planner
tokens, calls and dollars. Secondary: intervention burden, escalation precision and recall against
oracle labels, needless-ask rate, unsafe/irreversible action rate, and total system cost including
executor GPU-seconds. Crashes, timeouts and limit-hits stay in the denominator. Paired bootstrap with
10k resamples; 3 seeds on the final evaluation.

**Falsification, preregistered**: the method fails if `sidekick` does not beat `sft_plan` at matched
planner cost, or if its escalation is no better calibrated than `fixed_k`.

---

## 10. Risks and gates

| risk | gate or mitigation |
|---|---|
| Granite LoRA does not serve in vLLM | gate G3 tonight; fallback `Qwen/Qwen3-8B`, already cached |
| plan quota stalls a sweep silently | no `rate_limits` in batch output [measured] → move to an API key for M4+ |
| executor too weak for non-inferiority | expected; the deliverable is the frontier curve and the H2/H3 contrasts (§5) |
| planner drift over the study | all arms of a comparison run in one window; model, effort and CLI version pinned in manifests |
| AppWorld contamination | test_challenge, paraphrases, and paired contrasts that cancel planner-side memorisation |
| `/scratch` purge policy unknown | manifests and hashes in git; re-derivation scripts; ask HPC support |
| worker runaway on the login node | rules in every brief; `hpc-guard` backstop; check `hpc-guard --list` after each unit |

---

## 11. Approvals still needed

1. **The name** — Sidekick, or Understudy / Apprentice.
2. **Planner auth for M4 onward** — an API key with a US$250 cap (recommended), or stay on the ChatGPT
   plan quota and accept silent mid-sweep stalls.
3. **Heavy jobs** — everything in `HEAVY_JOBS.md` is specified but unsubmitted, and needs explicit
   approval before it runs.
4. `/scratch/n12194778/sidekick` confirmed as the data root, and the purge policy asked of HPC support.
5. Directory rename `~/iaes` → `~/sidekick` after the branch is merged.
