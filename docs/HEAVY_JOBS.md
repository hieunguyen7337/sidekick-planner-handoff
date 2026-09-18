# Sidekick — heavy jobs, specified in full

Status **2026-09-19: Re-sequenced per W-24/W-25/A7/A9 findings. J5b paused, J8 unblocked via SFT(b+).**
- **HJ-1 / HJ-1R / HJ-1.5 (J1)**: Settled. Granite-4.2-8B retained over Qwen3-8B based on pre-registered agreement (0.256 under serving configuration, rising with depth) [OBSERVED campaign/RUNS.md:636-660, 1275-1298]. Honest untrained dev baselines established: `executor_alone` TGC 0.0175, `prompt_only` TGC 0.0439 [OBSERVED campaign/RUNS.md:445-446].
- **HJ-2B (J2)**: Teacher demonstrations on train complete (180/180, 133 solved; extended to 230 trajectories in `sft_b_s123_p075.jsonl`) [OBSERVED campaign/RUNS.md:390-405, 819-829].
- **HJ-3 (J3)**: SFT(b) adapter complete (job 25401722) and evaluated (job 25401780). Gate PASSED: `sft_plan` TGC 0.4298 (+37.72 pp over untrained prompt-only, CI [28.07, 47.37]); probe agreement rose 0.256 → 0.492 [OBSERVED campaign/RUNS.md:940-970, 1005-1025].
- **J4 (HJ-2C)**: Fixed-k correction data on `sft_b` on train complete (180/180, TGC 0.577, 495 interventions) [OBSERVED campaign/RUNS.md:1080-1102, 1161-1171]. 495/495 interventions are `forced: true` on a 5-step timer (0 `ask` events).
- **J6 (HJ-4 branches)**: Completed on 4 seeds (397 train / 332 dev complete). W-24 showed train `needed` labels are indistinguishable from noise (p = 0.712) [OBSERVED campaign/workers/W24_PERMNULL.md:54]. W-25 showed this was an estimand substitution artefact [OBSERVED campaign/workers/W25_SUBSTITUTION.md:20-21]. J6 recovery is **demoted**.
- **J5a (`sft_b_plus`)**: Active executor policy (teacher + post-correction actions).
- **J5b (`sft_c`)**: **PAUSED** because train ASK labels are noise. H2 and H3 do not require `sft_c`; only H4 requires it, which is conditional on the clean-counterfactual pilot.
- **J7 (HJ-5 verifier)**: Completed. Feature logistic regression dev AUROC 0.5917 against label ceiling ~0.93 (genuine miss of preregistered threshold; reporting rule added) [OBSERVED campaign/workers/A9_THRESHOLD.md:25-35]. Value-function escalator dropped as uninformative (A7, dev AUROC 0.6212 below step prior floor) [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:61,77].
- **J8 (dev frontier)**: Unblocked with 12 configs using `sft_b_plus`, `router_seq`, `sidekick` (self P(ASK) gating), `fixed_k_{3,5,10}`, `sft_plan_bplus`, `executor_alone_bplus`, and `oracle_escalation` [OBSERVED campaign/workers/STATUS_A_5b.md:22-32].

Read with `PLAN.md`. Every job here:
- runs on **one node, one GPU** unless stated;
- has walltime ≤ 12 h and is **resumable**;
- writes `STATUS.md`, an append-only event log per run, and a manifest pinning model revisions, the AppWorld commit (`42b5bcf`), the Codex CLI version (`0.153.4`), prompt hashes and seed;
- pins the planner explicitly with `-m gpt-5.6-luna -c model_reasoning_effort=medium`.

---

## Dependency Order

```
Feasibility gates (2026-09-15)
   └── J1 (pilot & probe) ── J2 (teacher demos) ── J3 (SFT(b)) ── J4 (train fixed_k)
          └── J4b (dev fixed_k) ── J5a (sft_b_plus) ── J7 (verifier) ── J8 (dev frontier sweep)
                 │                                                          └── J9 (freeze on dev) ── J10 (test_normal)
                 ├── J6 (counterfactual branches; DEMOTED)                                                   └── J11 (optional)
                 └── J5b (sft_c; PAUSED pending clean-counterfactual pilot)
```

---

## HJ-1 / J1 — M3 Pilot Campaign & Probes (COMPLETE)

**Purpose.** Measure capability gap, delegable-step fraction, baseline prompt behavior, and executor state-tracking probe.
- HJ-1: Gated PASS on `planner_alone − executor_alone ≥ 20 pp` [OBSERVED campaign/RUNS.md:3-17].
- HJ-1R: Untrained baselines re-run under corrected multi-turn prompt (`executor_alone` TGC 0.0175, `prompt_only` TGC 0.0439) [OBSERVED campaign/RUNS.md:445-446].
- HJ-1.5: Serving-config probe validated Granite-4.2-8B (agreement 0.256, rising with depth to 0.400) [OBSERVED campaign/RUNS.md:636-660, 1275-1298].

---

## HJ-2B / J2 — M4 Teacher Demonstrations on Train (COMPLETE)

**Purpose.** Build SFT(b) teacher set from AppWorld train split.
- Campaign `hj2b_planner_train_20260916`, job 25397852: 90 train tasks × 2 seeds = 180 episodes, TGC 0.739, 2,613 planner calls [OBSERVED campaign/RUNS.md:390-405].
- Extended with third seed to 230 trajectories (196 solved + 34 partial ≥ 0.75) in `sft_b_s123_p075.jsonl` [OBSERVED campaign/RUNS.md:819-829].

---

## HJ-3 / J3 — M4 Supervised Fine-Tuning SFT(b) (COMPLETE)

**Purpose.** Train and evaluate plan-conditioned imitation adapter `sft_b`.
- Training (job 25401722): Granite-4.2-8B LoRA r=64 α=128, 2 epochs, train loss 0.1414, 2059 s wall [OBSERVED campaign/RUNS.md:811-830].
- Evaluation (job 25401780): Dev 57 × 2 seeds = 114 runs. `sft_plan` TGC **0.4298** (+37.72 pp over untrained `prompt_only`, 95% CI [28.07, 47.37]); probe agreement rose 0.256 → 0.492 [OBSERVED campaign/RUNS.md:940-970, 1005-1025]. **Gate PASSED in full.**

---

## J4 (HJ-2C) — M4 Correction Data on Trained Policy (COMPLETE)

**Purpose.** Run `fixed_k` (k=5) on `sft_b` on train (90 tasks × 2 seeds = 180 episodes) to harvest post-correction demonstrations and branch points.
- Campaign `hj4_correction_train_20260917`, jobs 25401962 / 25402025: 180/180 episodes, TGC 0.577, 495 interventions (2.71/ep), 675 hosted calls [OBSERVED campaign/RUNS.md:1080-1102, 1161-1171].
- Finding: 495/495 interventions are `forced: true` on a fixed timer (0 asks). Reviewer speaks before executor acts and never overrides an action. Supervised ASK targets cannot be derived from J4 data alone [OBSERVED campaign/RUNS.md:1211-1256].

---

## J4b — Gate A: Periodic Review Evaluation on Dev (NEW)

**Purpose.** Evaluate `fixed_k` (k=5) on `sft_b` on **dev** (57 tasks × 2 seeds = 114 runs) with cached plans from `hj1b_planner_20260915` to establish whether timer-based review provides value on held-out tasks paired against `sft_plan(sft_b)` (dev TGC 0.4298).

| field | value |
|---|---|
| Runs | 57 dev tasks × 2 seeds = **114 runs** |
| PBS | `select=1:ncpus=32:ngpus=1:mem=128gb`, walltime **04:00:00** |
| Duration | ≈ 1.5–2 h [INFERRED] |
| Planner turns | ≈ 450–550 live review calls [INFERRED] |
| Planner cost | **US$2–4** [INFERRED] |
| GPU-hours | ≈ 2 [INFERRED] |
| Gate A Rule | Paired bootstrap $\text{TGC}(\text{fixed\_k}, \text{sft\_b}, \text{dev}) - \text{TGC}(\text{sft\_plan}, \text{sft\_b}, \text{dev})$: <br>• **$\ge +7\text{ pp}$, CI excludes 0**: reviewer adds real quality on held-out tasks $\rightarrow$ proceed to J6.<br>• **CI includes 0**: interventions add nothing a learned policy could capture $\rightarrow$ **stop before J5–J8 spend** [OBSERVED campaign/RUNS.md:1361-1385]. |

---

## J6 (HJ-4) — Gate B: Counterfactual Branch Collection & Label Generation (COMPLETED / RECOVERY DEMOTED)

**Purpose.** Branch forward without corrections from each intervention point in J4 (train) and J4b (dev) to generate `needed`, `needless`, and `harmful` oracle labels.

- Completed across 4 branch seeds (397 train complete, 332 dev complete).
- W-24 showed train `needed` labels (25/397 at δ=0.166) are indistinguishable from noise (paired sign-flip permutation null p = 0.7124) [OBSERVED campaign/workers/W24_PERMNULL.md:54].
- W-25 demonstrated this was an estimand substitution artefact (untreated arm received substitute reviews ~5 steps later) [OBSERVED campaign/workers/W25_SUBSTITUTION.md:20-21].
- J6 branch recovery is **demoted**; clean-counterfactual pilot (`--untreated-mode suppress_next`, A8) licenses testing whether signal recovers without re-running mass branches.

---

## J5a / J5b (HJ-3b) — M4 Supervised Fine-Tuning of Matched Adapters (J5a ACTIVE / J5b PAUSED)

**Purpose.** Train two matched adapters:
- **J5a (`sft_b_plus`)**: J2 teacher demonstrations + J4 post-correction actions with **no `ASK_PLANNER` targets** (the active executor policy for J8).
- **J5b (`sft_c`)**: J2 teacher demonstrations + J4 post-correction actions + **`ASK_PLANNER` targets at J6 `needed` intervention points**. **PAUSED** because train ASK labels are noise (W-24). H2 and H3 are reachable without `sft_c`; only H4 is conditional on it.

| field | value |
|---|---|
| PBS | `select=1:ncpus=16:ngpus=1:mem=128gb`, walltime **06:00:00** per variant |
| Recipe | TRL SFT + PEFT LoRA r=64 α=128 on `q,k,v,o,gate,up,down`, lr 1e-4 cosine, 2 epochs, 32k context, loss on executor tokens only |
| GPU-hours | ≈ 4–6 per adapter [INFERRED] |
| Planner cost | **US$0** during training |
| Outputs | `artifacts/adapters/sft_b_plus_granite8b` (trained), `artifacts/adapters/sft_c_granite8b` (paused) |

---

## J7 (HJ-5) — M5 Verifier Training and Calibration (COMPLETED)

**Purpose.** Train and calibrate verifier head on J6 counterfactual branch labels.

- Feature logistic regression over `feature_lr_v1` (`scripts/setup/fit_feature_verifier.py`, `artifacts/verifiers/feature_lr_20260918/weights.json`).
- Dev AUROC **0.5917** [0.4677, 0.7111] (A9b, PBS `25454021.aqua`) [OBSERVED campaign/workers/A9_THRESHOLD.md:25-40]. Genuine miss of preregistered threshold; reporting rule added.
- Value function $V(\text{state}) = P(\text{success} \mid \text{state})$ achieved dev AUROC 0.6212 below feature-blind step-prior floor of 0.6245 (A7, PBS `25451256.aqua`); dropped from live J8 routing [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:61,77].

---

## HJ-6 — M5/M6 Preference Optimisation (SUPERSEDED / DROPPED)

🔺 **Superseded 2026-09-17 — DPO is dropped.**  
The sidekick's operating points on the cost-quality Pareto frontier are obtained by thresholding the policy's own $P(\text{ASK})$ / verifier score at serve time (`gate_ask_with_verifier`), rather than training three separate DPO $\lambda$ models. This requires one adapter instead of three, enables continuous sweep across arbitrarily many operating points, and directly provides the H3 calibration measurement [OBSERVED campaign/RUNS.md:1354-1358].

---

## J8 — M5 Dev Frontier Sweep & Calibration (READY)

**Purpose.** Sweep operating thresholds $\tau \in [0.3, 0.7]$ on dev (57 tasks × 2 seeds) to construct empirical quality-versus-displacement Pareto frontier for `sidekick(\tau)` (self P(ASK) gating on `sft_b_plus`) and `router_seq(\tau)` (sequential FeatureVerifier).
- 12 configurations created (`configs/hj8_*.yaml`), verified via `scripts/setup/verify_configs.py` (exit 0) [OBSERVED campaign/workers/STATUS_A_5b.md:22-32, 140-143].
- PBS harness `scripts/pbs/hj8_frontier.pbs` ready with adapter validation and `SMOKE_ONLY` guards (A6, A13) [OBSERVED campaign/workers/STATUS_A_6.md:3-5, STATUS_A_13.md:20-22].
- Evaluates dev AUROC, ECE, needless-ask rate, and identifies $\tau^*$ and $k_{\text{matched}}$.

| field | value |
|---|---|
| Runs | 57 tasks × 2 seeds across 12 configurations = 1,368 runs (with cache hits for shared prefixes) [INFERRED] |
| PBS | 1 GPU, walltime **08:00:00** (`scripts/pbs/hj8_frontier.pbs`) |
| GPU-hours | ≈ 6–8 [INFERRED] |
| Planner turns | ≈ 800–1,200 [INFERRED] |
| Planner cost | **US$3–6** [INFERRED] |
| Outputs | Dev quality-versus-displacement Pareto curve, resolved $\tau^*$, resolved $k_{\text{matched}}$ |

---

## J9 — M6 Preregistration Freeze

**Purpose.** Freeze all remaining open parameters in `docs/prereg_v1.md` strictly on **dev** prior to running J10 [OBSERVED campaign/RUNS.md:1410-1436]:
- Pinned: $\tau^*$, router $\tau^*$, $k_{\text{matched}}$ rule (*$k \in \{3, 5, 10\}$ nearest to sidekick dev calls/ep, interpolating to 7 on tie*), ASK prompt template, oracle label rule, and final arm list.

---

## J10 (HJ-7) — M6 Final Evaluation on `test_normal`

**Purpose.** The single test evaluation producing the headline numbers. Everything is frozen before it starts.
- **Primary Endpoint**: H2 conjunctive over 504 paired comparisons (168 tasks × 3 seeds):
  1. `sidekick` $\ge$ `fixed_k(k_matched)` $- 7\text{ pp}$
  2. `sidekick` $>$ `sft_plan(sft_b_plus)`, CI excluding 0
  3. `sidekick` planner calls/episode $<$ `fixed_k(k=5)`'s, CI excluding 0 [OBSERVED campaign/RUNS.md:1418-1424].
- **Secondary**: H1 non-inferiority vs `planner_alone` at $\epsilon = 7\text{ pp}$ with $FCD_{\text{tokens}} > 0$; H4 `sidekick` vs `router_seq(\tau^*)` at matched calls; H3 dev AUROC/ECE; dev needed-fraction $f$.

| field | value |
|---|---|
| Runs | 168 tasks × 6 systems × 3 seeds = **3,024 runs** |
| Systems | `planner_alone`, `executor_alone`, `prompt_only`, `fixed_k(k_matched)`, `sft_plan(sft_b_plus)`, `sidekick(\tau^*)` |
| PBS | `select=1:ncpus=32:ngpus=1:mem=128gb`, walltime **12:00:00**, expected to need 2–3 jobs |
| Duration | ≈ 20–24 h total [INFERRED] |
| Planner turns | ≈ 15,000–18,600 [INFERRED] |
| Planner cost | **US$40–60** [INFERRED] |
| GPU-hours | ≈ 25–30 [INFERRED] |
| Rule | **Run once.** A re-run after inspecting test results is a fatal protocol violation [OBSERVED AGENTS.md:7, campaign/RUNS.md:1436]. |

---

## J11 (HJ-8) — M6 Out-of-Distribution Slice on `test_challenge` (Optional)

| field | value |
|---|---|
| Runs | 417 test_challenge tasks × 3 systems × 1 seed = **1,251 runs** |
| PBS | one GPU, walltime **12:00:00** |
| Planner turns | ≈ 11,700 [INFERRED] |
| Planner cost | **US$28–35** [INFERRED] |
| GPU-hours | ≈ 8 [INFERRED] |
| Decide | only if J10 produced a publishable contrast |

---

## Totals Across the Reordered Campaign

| Milestone / Job | GPU-hours | Planner Turns | Planner Cost |
|---|---|---|---|
| J1–J4 (HJ-1/1R/1.5, HJ-2B, HJ-3, HJ-4 train fixed_k) [COMPLETED] | ≈ 30 [INFERRED] | ≈ 7,500 [INFERRED] | ≈ US$25 [INFERRED] |
| J4b (dev fixed_k, Gate A) | ≈ 2 [INFERRED] | ≈ 500 [INFERRED] | ≈ US$3 [INFERRED] |
| J6 (counterfactual branches, Gate B) | ≈ 8 [INFERRED] | 0 | US$0 |
| J5a/b (SFT adapters `sft_b_plus` / `sft_c`) | ≈ 10 [INFERRED] | 0 | US$0 |
| J7 (verifier training) | ≈ 2 [INFERRED] | 0 | US$0 |
| J8 (dev frontier sweep) | ≈ 8 [INFERRED] | ≈ 1,000 [INFERRED] | ≈ US$5 [INFERRED] |
| J10 (HJ-7 test_normal final) | ≈ 30 [INFERRED] | ≈ 18,000 [INFERRED] | ≈ US$50 [INFERRED] |
| **Total (J1 … J10)** | **≈ 90** [INFERRED] | **≈ 27,000** [INFERRED] | **≈ US$83** [INFERRED] |
| plus J11 (test_challenge) | ≈ 98 [INFERRED] | ≈ 38,700 [INFERRED] | ≈ US$115 [INFERRED] |

Budget remains well within the proposed **US$250** cap.
