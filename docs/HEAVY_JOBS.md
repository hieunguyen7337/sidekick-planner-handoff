# Sidekick — heavy jobs, specified in full

Status **2026-09-16 00:45: HJ-1's go/no-go gate is settled — PASS.** Classes A and B both ran
before the maintenance window. `planner_alone` TGC **0.684** (114/114), `executor_alone`
(granite-4.2-8b, zero-shot) TGC **0.000** (114/114); paired difference **68.42 pp**, 95 % CI
**[59.65, 76.32]** against a ≥ 20 pp threshold. The `granite-4.2-3b` arm was refused by its smoke
gate (the 3B cannot hold the action format) and was not needed: it exists as a fallback for the
executor being *too strong*, which did not happen.

**Two Class C arms also ran, and produced the night's most important result.** `prompt_only` (one
plan) and `fixed_k` (review every 5 steps) both completed 114/114 and both scored TGC **0.000** —
identical to `executor_alone` — so all three differ from `planner_alone` by the same 68.42 pp
[59.65, 76.32]. **936 planner calls in `fixed_k` bought nothing.** The reviews were correct and
specific (they named `apis.supervisor.show_account_passwords()`), the executor often complied, and
it still could not carry the resulting `access_token` across steps. What separates luna from
granite-4.2-8b here is not information that can be handed over in text. `oracle_escalation` remains
unrun. **HJ-2 … HJ-8 are unsubmitted.** Full numbers, the diagnosis and per-job provenance:
`campaign/RUNS.md`; machine-readable report: `campaign/hj1_gate.json`.

⚠ The gate licenses "there is ample headroom", not "the gap is 68 points" — `executor_alone` is
zero-shot where the literature's frozen-8B numbers are few-shot, and `planner_alone` was truncated
by a 25-call cap on 10.5 % of episodes, so the figure is an upper bound. See `campaign/RUNS.md`.

All M0 feasibility gates passed on 2026-09-15 (see `feasibility/M0_RESULTS.md`). Every job below
still needs explicit approval before it runs.

**HJ-1 was split by resource class**, because its six arms barely overlap in what they need and
`runner.py` already takes one `--system` per invocation, so no code change was required:

| class | arms | needs | runs | job |
|---|---|---|---|---|
| A | `executor_alone` (8b, 3b) | GPU only, **zero planner calls** | 228 | `scripts/pbs/hj1a_executor_alone.pbs` |
| B | `planner_alone` | luna only, **no GPU** | 114 | `scripts/pbs/hj1b_planner_alone.pbs` |
| C | `prompt_only`, `fixed_k`, `oracle_escalation` | both at once | 268 | after maintenance |

Classes A and B together settle HJ-1's go/no-go gate (`planner_alone − executor_alone ≥ 20 pp`) and
were run on the evening of 2026-09-15 ahead of the ~08:00 2026-09-16 maintenance shutdown. Class C
needs a GPU and the planner simultaneously and was deferred.

⚠ Splitting arms across calendar windows is acceptable for a **pilot** hunting a ~20 pp effect, where
planner drift is far smaller than the effect. It must **not** be done for HJ-7, where all six systems
must run in one window.

⚠ **Every dollar figure below is luna API list pricing and does not describe spend.** Codex here
authenticates through a ChatGPT plan, so planner calls are covered by the subscription; read the
dollar columns as a token-volume proxy. The binding limit is plan quota, which a batch job cannot
observe. See `FOLLOWUPS.md` §6 for what running HJ-1 actually exposed.

Read with `PLAN.md`. Every job here:

- runs on **one node, one GPU** unless stated, because `gpu_batch_exec` had 189 jobs queued tonight
  while `gpu_inter_exec` was nearly idle;
- has walltime ≤ 12 h and is **resumable** — it skips any run whose result file already exists, so a
  killed job costs only the in-flight runs;
- writes `STATUS.md`, an append-only event log per run, and a manifest pinning model revisions, the
  AppWorld commit, the Codex CLI version, the prompt hashes and the seed;
- pins the planner explicitly with `-m gpt-5.6-luna -c model_reasoning_effort=medium`, because the
  user's Codex config defaults to a different and much more expensive model.

Cost arithmetic uses the measured overhead of **15,378 input tokens per fresh planner call** plus luna
list prices (0.20 / 0.02 cached / 1.20 USD per 1M tokens). Threads are resumed rather than restarted, so
most input is billed at the cached rate.

---

## Dependency order

```
M0 gates (tonight)
   └── HJ-1 pilot ──┬── HJ-2 trajectory collection ── HJ-3 SFT ──┬── HJ-4 branches ── HJ-5 verifier
                    │                                            └── HJ-6 DPO
                    └── (prereg frozen here)                                   └── HJ-7 final eval
                                                                                    └── HJ-8 OOD (optional)
```

---

## HJ-1 — M3 pilot campaign

**Purpose.** Measure the capability gap, the delegable-step fraction and the paired variance that sets
ε. This is the go/no-go for the whole study: if `planner_alone` does not beat `executor_alone` by a wide
margin on our own scaffold, there is nothing to displace.

| field | value |
|---|---|
| Runs | **610 runs** = 5 full arms × 57 dev tasks × 2 seeds (570) + a 20-task `oracle_escalation` probe × 2 seeds (40). Not 684: `oracle_escalation` is a diagnostic probe, not a sixth full arm, so 57 × 6 × 2 overcounts it by 74 |
| Arms | `planner_alone`, `executor_alone` (granite-4.2-8b), `executor_alone` (granite-4.2-3b), `prompt_only`, `fixed_k` (k=5), plus a 20-task `oracle_escalation` probe |
| PBS | `select=1:ncpus=32:ngpus=1:mem=128gb`, `-q gpu_batch_exec`, walltime **08:00:00** |
| Layout | vLLM serves granite-8b and granite-3b (adapters off) on the one H100; 16 AppWorld worker processes; 6 concurrent `codex exec` subprocesses |
| Duration | ≈ 5–7 h [INFERRED — G3 measured 1,808 tok/s at 16-way concurrency, so this holds] |
| Planner turns | ≈ 3,500 |
| Planner cost | **US$8–14** |
| GPU-hours | ≈ 6 |
| Outputs | `results/pilot_<date>/runs.jsonl`, 610 event logs, a variance table, the delegable-step histogram |
| Gate | proceed only if `planner_alone − executor_alone ≥ 20 pp` TGC and ≥ 30% of steps are delegable. If the 8B gap is too small, the 3B arm becomes the executor |
| Risk | a systematically broken prompt wastes the whole run → the job runs a **10-task smoke slice first** and stops if any arm returns 0 successes |

---

## HJ-2 — M4 trajectory collection

**Purpose.** Build the supervised training set from the train split: planner-alone demonstrations,
plus prompt-only rollouts that contain real interventions and real escalations.

⚠ The train split holds **90 tasks, not the documented 105** [measured, gate G2] — a 14% smaller
supervised pool than planned. Consider raising rollouts per task from 8 to 10 to compensate.

| field | value |
|---|---|
| Runs | 90 tasks × (2 `planner_alone` + 8 `prompt_only`) = **900 runs** |
| PBS | same shape, walltime **10:00:00**, resumable |
| Duration | ≈ 8–10 h, likely split across two jobs |
| Planner turns | ≈ 7,500 |
| Planner cost | **US$18–25** |
| GPU-hours | ≈ 20 |
| Outputs | `data/raw/appworld/train/<run_id>/events.jsonl`, and a compacted `data/interim/sft_pairs.parquet` |
| Note | this is the largest single planner spend in the study. Sampling temperature for the executor is the only source of rollout diversity, since luna has no temperature control |

---

## HJ-3 — M4 supervised fine-tuning

**Purpose.** Two SFT variants: (b) plan-conditioned, (c) plan-conditioned plus correction-recovery and
ASK supervision. (c) is the initialisation for DPO; (b) is the intervention-agnostic control that H2 is
measured against.

| field | value |
|---|---|
| PBS | `select=1:ncpus=16:ngpus=1:mem=128gb`, walltime **06:00:00** per variant |
| Recipe | TRL SFT + PEFT LoRA r=64 α=128 on `q,k,v,o,gate,up,down`, lr 1e-4 cosine, 2 epochs, 32k context, gradient checkpointing, loss on executor tokens only |
| Duration | ≈ 2–4 h per variant on one H100 [INFERRED — G3 smoke: 6.2 s load, 17 s for a tiny run, 20 GB peak] |
| GPU-hours | ≈ 8 for both, ≈ 16 with the 3B arm and a seed repeat |
| Planner cost | **US$0** — no planner calls during training |
| Outputs | `artifacts/adapters/sft_b_granite8b`, `artifacts/adapters/sft_c_granite8b`, plus manifests listing every training task id |
| Guard | CI test fails if any dev or test task id appears in an adapter manifest |
| Then | dev evaluation of each adapter: 57 tasks × 2 arms × 2 seeds ≈ 228 runs, ≈ 1 h, ≈ US$2 |

---

## HJ-4 — M5 counterfactual branch collection

**Purpose.** Labels for the verifier. At each intervention point in the M4 logs, branch the executor
forward without the planner's help and record what happens: does it fail, does it violate the plan, how
expensive is recovery, was the intervention worth it.

| field | value |
|---|---|
| Branches | ≈ 600 intervention points × 3 branches × ≤ 10 steps = **≈ 1,800 short rollouts** |
| PBS | one GPU, walltime **06:00:00** |
| Planner turns | ≈ 0 — branches are executor-only by construction |
| Planner cost | **≈ US$0** |
| GPU-hours | ≈ 10 |
| Outputs | `data/interim/branch_labels.parquet` with the five label fields |
| Note | this is the cheapest high-value job in the study, because it buys supervision without touching the planner |

---

## HJ-5 — M5 verifier training and calibration

| field | value |
|---|---|
| Model | `Qwen/Qwen3-1.7B` + one head |
| PBS | one GPU, walltime **03:00:00** |
| Duration | ≈ 1 h |
| GPU-hours | ≈ 2 |
| Outputs | `artifacts/verifier/v1`, reliability diagram, Brier / ECE / AUROC on dev, the chosen threshold |
| Cost | US$0 |

---

## HJ-6 — M5/M6 preference optimisation

**Purpose.** The method itself: teach the executor when escalating is worth its cost.

| field | value |
|---|---|
| Pairs | three types — continue ≻ needless ASK; ASK ≻ risky continue before an irreversible action; plan-aligned ≻ later-corrected |
| Sweep | 3 λ settings (escalation penalty weight) × 1 seed, initialised from SFT(c) |
| PBS | one GPU, walltime **04:00:00** per setting |
| Duration | ≈ 1–2 h each |
| GPU-hours | ≈ 12 for the sweep, ≈ 20 including dev evaluations |
| Planner cost | dev evaluation of 3 settings ≈ 360 runs ≈ **US$4** |
| Outputs | `artifacts/adapters/sidekick_dpo_lambda{1,2,3}`, the dev frontier plot that selects one |
| Freeze | after this, `docs/prereg_v1.md` is frozen and **no further tuning is allowed** |

---

## HJ-7 — M6 final evaluation on test_normal

**Purpose.** The only run that produces the headline numbers. Everything is frozen before it starts.

| field | value |
|---|---|
| Runs | 168 tasks × 6 systems × 3 seeds = **3,024 runs** |
| Systems | `planner_alone`, `executor_alone`, `prompt_only`, `fixed_k`, `sft_plan`, `sidekick` |
| PBS | `select=1:ncpus=32:ngpus=1:mem=128gb`, walltime **12:00:00**, expected to need **2–3 jobs** |
| Duration | ≈ 20–24 h total |
| Planner turns | ≈ 18,600 |
| Planner cost | **US$45–60** |
| GPU-hours | ≈ 30 |
| Outputs | `results/final_<date>/runs.jsonl`, the paired bootstrap tables, the quality-versus-displacement frontier, all 12 paper figures |
| Rule | run once. A re-run after seeing the numbers is a protocol violation and would be recorded as one |

---

## HJ-8 — M6 out-of-distribution slice (optional)

| field | value |
|---|---|
| Runs | 417 test_challenge tasks × 3 systems × 1 seed = **1,251 runs** |
| PBS | one GPU, walltime **12:00:00** |
| Duration | ≈ 10–12 h |
| Planner turns | ≈ 11,700 |
| Planner cost | **US$28–35** |
| GPU-hours | ≈ 8 |
| Decide | only if HJ-7 produced a publishable contrast |

---

## Totals if everything runs

| | GPU-hours | planner turns | planner cost |
|---|---|---|---|
| HJ-1 … HJ-7 | ≈ 110 | ≈ 33,000 | **US$77–105** |
| plus HJ-8 | ≈ 118 | ≈ 45,000 | **US$105–140** |

Against a proposed cap of **US$250**, which leaves room for reruns after a bug.

## What could make these numbers wrong

1. **The 15.4k-token overhead per fresh call** is measured on an empty prompt. Adding the AppWorld API
   documentation digest could push input past 30k per call, roughly doubling the fresh-call cost. The
   harness caches aggressively through thread resume; G2 measures the real digest size and HJ-1 reports
   actual cost per run, which replaces every estimate here.
2. **Episode length.** These estimates assume 10–25 interactions per task. The published luna scaffold
   used 9.3; ReAct-style scaffolds use 17–30. The 40-step cap bounds the worst case.
3. **Queue contention.** `gpu_batch_exec` had 189 jobs queued tonight. Wall-clock calendar, not
   GPU-hours, is the binding constraint on this study.
4. **Plan quota versus API key.** On the ChatGPT plan, a sweep can stall mid-run with no visible signal,
   because `rate_limits` is absent from batch output. HJ-2 onward should use an API key.
