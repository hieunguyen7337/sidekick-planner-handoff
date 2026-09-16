# Preregistration: Intervention-Aware Executor Specialization for Frozen Hosted Planners (Sidekick v1)

**Status**: **DRAFT** — To be frozen strictly after the preference-optimization milestone (HJ-6) reports and before any evaluation on `test_normal` (HJ-7).  
**Date**: 2026-09-16  
**Study**: Sidekick Proof-of-Concept (IAES)  
**Repository**: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15` [OBSERVED campaign/workers/briefs/PREREG_draft.md:4]  
**Frozen on**: ____________________  

### Open Fields Pending Prior Milestones

The following three parameters are left open and will be instantiated from their respective prior milestone reports before freezing:
1. **DPO Escalation Penalty ($\lambda$)**: TBD from HJ-6 (selected on the dev Pareto frontier from $\lambda \in \{0.1, 0.5, 1.0\}$) [OBSERVED docs/HEAVY_JOBS.md:191-198].
2. **Verifier Decision Threshold ($\tau$)**: TBD from HJ-5 (calibrated for escalation precision/recall on dev counterfactual branch labels) [OBSERVED docs/HEAVY_JOBS.md:176-180].
3. **Executor Model Backbone**: TBD from HJ-1.5 (`ibm-granite/granite-4.2-8b` primary vs. `Qwen/Qwen3-8B` fallback, decided by the state-tracking probe) [OBSERVED campaign/RUNS.md:348-358].

---

## 1. The Claim Being Tested

Autonomous software agents that rely exclusively on high-capacity hosted language models incur heavy token and dollar costs when executing routine, programmatic tool calls. While dividing labour between a strong planner and a smaller executor is intuitively appealing, unadapted small executors lack domain agency, whereas generic plan-conditioned imitation fails to teach the executor when it must escalate back to the planner.

The thesis of this project is that **a small, locally served executor model specialised to one frozen hosted planner (`sidekick`) matches the planner-alone baseline's task success rate while displacing a substantial fraction of expensive planner compute** [OBSERVED campaign/workers/briefs/PREREG_draft.md:27-31, docs/PLAN.md:3, 241-255].

### 1.1 Hypotheses

All hypotheses are directional, falsifiable predictions evaluated under paired experimental conditions on identical task instances and random seeds:

- **H1 (Task Quality Non-Inferiority with Compute Displacement — Headline Claim)**:  
  The collaborative system (`sidekick`) achieves AppWorld Task Goal Completion (TGC) that is non-inferior to the frozen hosted planner operating alone (`planner_alone`) within a margin of $\epsilon = 7\text{ percentage points}$ ($\text{TGC}_{\text{sidekick}} \ge \text{TGC}_{\text{planner\_alone}} - 0.07$ evaluated via one-sided 95% paired bootstrap confidence interval), while achieving strictly positive frontier-compute displacement on planner tokens ($FCD_{\text{tokens}} > 0$).  
  **Primary Status**: Task goal completion non-inferiority is the primary scientific hurdle; frontier-compute displacement is the co-primary efficiency condition.

- **H2 (Intervention-Aware Training Superiority)**:  
  Intervention-aware post-training (`sidekick`: SFT with correction supervision + verifier-guided DPO) achieves strictly higher TGC than intervention-agnostic plan-conditioned imitation (`sft_plan`, instantiated as the data-matched control `sft_b_plus`) at matched planner token expenditure ($p < 0.05$, paired bootstrap). This tests whether learned escalation offers value beyond simply increasing supervised training volume.

- **H3 (Calibrated Escalation vs. Static Review)**:  
  Dynamic, verifier-gated escalation in `sidekick` achieves superior escalation calibration against oracle intervention labels compared to a fixed periodic review schedule (`fixed_k`), exhibiting a lower needless-ask rate, higher intervention efficiency, and a dominating cost-quality Pareto curve.

- **H4 (Integrated Policy vs. Bolted-On Router)**:  
  Embedding the escalation decision directly into the executor policy (`sidekick`) achieves a superior empirical cost-quality Pareto frontier compared to pairing a frozen executor with an external post-hoc residual-risk router (`router_seq`).

### 1.2 Advance Capability Expectations and Falsification Criteria

- **Advance Expectation on Weak Executors**: Published benchmarks on AppWorld indicate that frozen ~8B open models achieve between 1.0% and 17.0% TGC on `test_normal`, and supervised fine-tuning on thousands of teacher demonstrations reaches 26.0%–33.0% TGC, whereas `gpt-5.6-luna` scores 85.1% TGC [OBSERVED docs/PLAN.md:102, 256-258]. It is therefore expected that an 8B executor will **not** achieve non-inferiority ($\epsilon = 7\text{ pp}$) at high displacement rates ($FCD > 0.70$).  
- **Core Deliverable**: The primary empirical deliverable is the **quality-versus-displacement Pareto frontier**. The non-inferiority point will be explicitly marked on this curve.  
- **Preregistered Falsification**: The method will be declared falsified if `sidekick` fails to outperform `sft_plan(sft_b_plus)` at matched planner cost (H2 fails), or if its escalation is no better calibrated than a fixed periodic schedule `fixed_k` (H3 fails). A failure of H1 at high displacement will be reported transparently on the frontier curve and not retrofitted post hoc.

---

## 2. Experimental Design and Statistical Power

### 2.1 Benchmark and Split Allocation

The final evaluation (HJ-7) is conducted exclusively on the official **`test_normal`** split of the **AppWorld** benchmark [OBSERVED docs/PLAN.md:186, docs/HEAVY_JOBS.md:217]:
- **Evaluation Benchmark**: AppWorld `test_normal` (168 tasks across 56 scenarios) [OBSERVED docs/PLAN.md:186].
- **No Contamination Policy**: `test_normal` is evaluated strictly once at milestone M6 (HJ-7). No prompt tuning, threshold calibration, error analysis, or model retraining is permitted on test splits [OBSERVED campaign/workers/briefs/PREREG_draft.md:61, docs/PLAN.md:204].
- **Supervised Training Split**: AppWorld `train` (measured at 90 tasks, 30 scenarios) [OBSERVED docs/PLAN.md:184, docs/HEAVY_JOBS.md:119].
- **Tuning and Calibration Split**: AppWorld `dev` (measured at 57 tasks, 19 scenarios) [OBSERVED docs/PLAN.md:185, campaign/RUNS.md:9].

### 2.2 System Arms in HJ-7

HJ-7 evaluates six systems across 168 tasks and $N = 3$ random seeds ($168 \times 6 \times 3 = 3,024$ total evaluation runs) [OBSERVED docs/HEAVY_JOBS.md:217-218]:

| System Name | Description & Role in Scientific Argument |
|---|---|
| `planner_alone` | Frozen hosted planner (`gpt-5.6-luna`) executes all steps (the reference baseline for H1 and FCD). |
| `executor_alone` | Base executor model without planner assistance (establishes the zero-shot capability floor). |
| `prompt_only` | Base executor model executing a single initial delegation packet from `gpt-5.6-luna` without re-entry. |
| `fixed_k` | Cost-matched static control: planner reviews and intervenes every $k=5$ executor steps. |
| `sft_plan` | Intervention-agnostic control (`sft_b_plus`): executor trained on identical data volume with ASK targets masked to post-correction actions. |
| `sidekick` | Proposed system: intervention-aware SFT(c) + DPO ($\lambda$) with verifier-gated dynamic `ASK_PLANNER` escalation. |

### 2.3 Sample Size and Margin Justification (Power Analysis)

The sample size of **$N = 3$ seeds** and the non-inferiority margin of **$\epsilon = 7\text{ percentage points}$** are frozen based on the pre-run power analysis conducted in `scripts/setup/hj7_power.py` and recorded in `campaign/results/hj7_power.json` [OBSERVED campaign/results/hj7_power.json:469-505, docs/HEAVY_JOBS.md:206-214]:

1. **Measured Baseline Discordance**: On the dev split (57 tasks $\times$ 2 seeds), `planner_alone` exhibited an empirical seed discordance rate of **28.0702%** (16 discordant task pairs out of 57; 31 concordant successes, 10 concordant failures) [OBSERVED campaign/results/hj7_power.json:471-475]. The marginal TGC gap between seed 1 (0.6491) and seed 2 (0.7193) was 7.0175 pp [OBSERVED campaign/results/hj7_power.json:480-488, campaign/RUNS.md:91].
2. **Power under Latent-Difficulty Model**: Calibrated against this measured variance, Monte Carlo simulations (2,000 experiment replicates, 200 bootstrap replicates per rep) over 168 tasks show that the smallest non-inferiority margin resolvable at $\ge 80\%$ power when `sidekick` matches `planner_alone` (true rate 0.68) is **7 pp at N = 3** (simulated power = **0.8600** $\pm$ 0.0078 MCSE, mean CI half-width = 4.58 pp) [OBSERVED campaign/results/hj7_power.json:235-260, 502].
3. **Why Additional Seeds Do Not Help**: Sizing to $N = 4$ or $N = 5$ seeds yields identical resolvable margins of **7 pp** (power = 0.9280 at N = 4, 0.9640 at N = 5) [OBSERVED campaign/results/hj7_power.json:339, 423, 503-504]. While extra seeds narrow the CI half-width (4.58 pp at N=3 $\rightarrow$ 3.98 pp at N=4 $\rightarrow$ 3.55 pp at N=5), they fail to resolve $\epsilon = 5\text{ pp}$ at $\ge 80\%$ power (power at $\epsilon = 5\text{ pp}$ is only **0.5910** at N = 3, **0.6755** at N = 4, and **0.8090** at N = 5) [OBSERVED campaign/results/hj7_power.json:250, 334, 418]. The binding constraint on statistical power is the fixed number of benchmark tasks (168), not the seed count. Budgeting more than 3 seeds would waste cluster quota without changing the resolvable margin.
4. **Sensitivity under Worst-Case Mixture Model**: Under the pessimistic common-or-independent mixture correlation model (`campaign/results/hj7_power_mixture.json`), statistical power is strictly lower: at N = 3, power at $\epsilon = 7\text{ pp}$ reaches only 0.4590, and the smallest resolvable margin at $\ge 80\%$ power is **10 pp even at N = 5** (power = 0.8320; power at $\epsilon = 7\text{ pp}$ is 0.5300) [OBSERVED campaign/results/hj7_power_mixture.json:255, 423, 499-505]. This sensitivity result will be reported alongside the primary analysis.
5. **Independent corroboration on the train split, and why the conservative estimate was kept.** The
   discordance above is measured on dev (57 tasks). HJ-2B gives a second, larger, fully independent
   estimate of the same quantity from the same frozen planner: on **train, 90 tasks × 2 seeds**,
   discordance is **18.89%** (17 of 90; 58 concordant successes, 15 concordant failures) with a
   seed-1/seed-2 marginal gap of only **1.11 pp** (0.7444 vs 0.7333)
   [OBSERVED campaign/results/hj2b_planner_train_20260916.runs.jsonl, 180 runs].
   The two estimates are **not significantly different** — 16/57 carries a standard error of ≈5.9 pp
   and 17/90 one of ≈4.1 pp, so the 9.2 pp difference is ≈1.3 combined standard errors, and the
   pooled estimate over all 147 task-pairs is **22.4%**. The dev figure is therefore an unlucky-draw
   high estimate rather than a contradiction, and the striking 7.0 pp dev seed gap that originally
   motivated this analysis does **not** reproduce on the larger split.
   ⚠ The design is nevertheless calibrated on the **dev** figure, deliberately. Higher assumed noise
   means lower assumed power, so ε = 7 pp is the **conservative** choice: if the true discordance is
   nearer 19%, the realised power at ε = 7 pp exceeds the 0.860 stated above. Re-deriving ε downward
   from the friendlier train number after seeing it would be exactly the post-hoc margin selection a
   preregistration exists to prevent.

---

## 3. Primary Metric and Exact Statistical Test

### 3.1 Primary Metric Specification

- **Per-Run Metric**: AppWorld Task Goal Completion ($\text{TGC} \in \{0.0, 1.0\}$), determined by programmatic evaluation of ground-truth state assertions and collateral damage checks [OBSERVED docs/PLAN.md:90-95, 215-218].
- **Task-Level Aggregation**: For each system and task $i \in \{1, \dots, 168\}$, the task score is the mean TGC across the $N = 3$ evaluated seeds:
  $$\overline{\text{TGC}}_{i, \text{system}} = \frac{1}{3} \sum_{s=1}^3 \text{TGC}_{i, s, \text{system}}$$
- **Paired Difference**: For each task $i$, the paired difference against the baseline is:
  $$\Delta_i = \overline{\text{TGC}}_{i, \text{sidekick}} - \overline{\text{TGC}}_{i, \text{planner\_alone}}$$

### 3.2 Exact Bootstrap Test

The statistical test for non-inferiority will be executed using the exact bootstrap procedure implemented in **`scripts/setup/hj1_gate.py`**, specifically the **`paired_diff()`** function [OBSERVED scripts/setup/hj1_gate.py:111-139, campaign/results/hj7_power.json:4-6]:

- **Resampling Method**: 10,000 paired bootstrap resamples of the task difference vector $(\Delta_1, \dots, \Delta_{168})$ [OBSERVED scripts/setup/hj1_gate.py:28, 126-130].
- **Random Seed**: Fixed at `SEED = 20260915` [OBSERVED scripts/setup/hj1_gate.py:29].
- **Confidence Interval**: Percentile bootstrap 95% confidence interval $[\text{ci95\_pp}[0], \text{ci95\_pp}[1]]$ derived from the 2.5th and 97.5th percentiles of resampled mean differences [OBSERVED scripts/setup/hj1_gate.py:129-136].
- **Decision Rule**: Non-inferiority is formally declared if and only if the lower endpoint satisfies:
  $$\text{ci95\_pp}[0] \ge -7.00\text{ percentage points}$$
  [OBSERVED campaign/results/hj7_power.json:5].

---

## 4. Secondary Metrics and Advance Directionality

All secondary outcomes are assigned an advance directional expectation:

1. **Scenario Goal Completion (SGC)**:  
   Fraction of AppWorld scenarios (clusters of 3 tasks) where all constituent tasks succeed ($1.0$ if all tasks pass, $0.0$ otherwise) [OBSERVED scripts/setup/hj1_gate.py:49-88].  
   *Direction*: $\text{SGC}_{\text{sidekick}} \ge \text{SGC}_{\text{sft\_plan}}$.
2. **Planner Calls per Episode ($n_{\text{calls}}$)**:  
   Total number of hosted planner invocations attempted per episode [OBSERVED campaign/RUNS.md:168-175, docs/PLAN.md:157-158].  
   *Direction*: $\text{sidekick} \ll \text{planner\_alone}$ (expected $\le 4.0$ vs. $13.5$ in `planner_alone`) [OBSERVED campaign/RUNS.md:9].
3. **Planner Token Expenditure ($C_P$)**:  
   Total billed planner tokens per episode (input + $0.10 \times \text{cached input} + \text{output} + \text{reasoning output}$) [OBSERVED docs/PLAN.md:99, 153].  
   *Direction*: $\text{sidekick} \ll \text{planner\_alone}$, establishing $FCD_{\text{tokens}} = 1 - C_{P, \text{sidekick}} / C_{P, \text{planner\_alone}} > 0$.
4. **Frontier Cost per Solved Task ($C_{\text{solved}}$)**:  
   Total system dollar cost (luna token list prices + local GPU compute amortized at US$2.50/GPU-hour) divided by the number of completed tasks [OBSERVED docs/PLAN.md:152-155].  
   *Direction*: $\text{sidekick} < \text{planner\_alone}$.
5. **Escalation ASK Rate ($r_{\text{ask}}$)**:  
   Fraction of executor steps emitting `ASK_PLANNER` ($N_{\text{asks}} / N_{\text{steps}}$).  
   *Direction*: Monotonically decreasing with penalty weight $\lambda$.
6. **Verifier Gating Fraction ($f_{\text{gated}}$)**:  
   Fraction of raw executor `ASK_PLANNER` actions approved by the verifier ($N_{\text{approved\_asks}} / N_{\text{raw\_asks}}$).  
   *Direction*: $\ge 60\%$ (calibrated on dev to eliminate false-alarm escalations).
7. **Unsafe Irreversible Action Violations**:  
   Number of unauthorized calls to irreversible APIs (send, pay, delete, post) without planner confirmation.  
   *Direction*: Exactly zero for `sidekick`.

---

## 5. Controls and What Each One Rules Out

To isolate the mechanism of intervention awareness, the six arms rule out specific alternative explanations:

1. **`planner_alone` (Hosted Reference)**: Rules out task difficulty and defines the performance ceiling under full hosted intelligence.
2. **`executor_alone` (Zero-Shot Capability Floor)**: Rules out the baseline competence of the small model without guidance and measures the maximum headroom available to close.
3. **`prompt_only` (One-Shot Plan Following)**: Rules out zero-shot instruction following. As observed in HJ-1, a single static plan yields 0.000 TGC because the executor fails to carry state across steps [OBSERVED campaign/RUNS.md:11, 99-138].
4. **`fixed_k` (Periodic Intervention Control)**: Rules out naive brute-force periodic review ($k=5$). In HJ-1, 936 expert corrections in `fixed_k` produced 0.000 TGC [OBSERVED campaign/RUNS.md:12, 144-197]. It establishes whether dynamic escalation is superior to fixed interval scheduling at matched planner calls.
5. **`sft_plan` / `sft_b_plus` (The Crucial Data-Volume Control)**:  
   The `sft_plan` baseline in HJ-7 is instantiated using **`sft_b_plus`**. `sft_b_plus` is trained on the exact same trajectory dataset as `sidekick`, but every `ASK_PLANNER` target is replaced by the corresponding post-correction ground-truth action [OBSERVED campaign/workers/briefs/PREREG_draft.md:48-51].  
   *Scientific Purpose*: `sidekick` and `sft_b_plus` receive **identical supervised token volume and demonstration coverage**. The contrast `sidekick` vs. `sft_b_plus` differs **strictly in the availability of the `ASK_PLANNER` escalation channel**. Without `sft_b_plus`, any performance advantage of `sidekick` over `sft_plan` could be dismissed as an artifact of seeing more training data or post-correction examples rather than learned escalation.

---

## 6. Stopping, Execution, and Exclusion Rules

### 6.1 Strict Denominator and Zero-Exclusion Commitment

- **Complete Accounting**: Every initialized task instance in the $168 \times 6 \times 3 = 3,024$ matrix is included in the denominator of all reported metrics. No task or seed may be pruned, filtered, or dropped post hoc [OBSERVED AGENTS.md:7].
- **Failure Scoring**: Any run ending in `limit`, `timeout`, `crash`, `parse_error`, or `api_error` is scored as $\text{TGC} = 0.0$ and $\text{SGC} = 0.0$ [OBSERVED scripts/setup/hj1_gate.py:15-16, 96-108].

### 6.2 Global Episode Constraints

All arms operate under identical global execution bounds [OBSERVED docs/PLAN.md:211-213, campaign/briefs/SEAM_CONTRACT.md:188-191]:
- `max_steps = 40`
- `max_tokens_per_episode = 32000`
- `per_step_timeout_s = 120`
- `max_planner_calls = 25` (reconciled across all arms)

### 6.3 Retry vs. Drop Criteria

- **Infrastructure Retries**: A run may be retried if and only if it failed due to external HPC infrastructure faults (e.g., PBS job preemption, node power loss, transient OS network socket reset) prior to the completion of the batch sweep.
- **Model Behavioral Errors**: Behavioral failures (such as infinite API loops, invalid action syntax, uncaught Python exceptions in generated code, or context limit exhaustion) are logged with their respective `error_type` and are **never retried**.
- **Quota-Stall Integrity Rule**: If cumulative `api_error + timeout` exceeds **5.0%** across any arm, the entire campaign sweep is paused to resolve quota or network issues before resuming. If cumulative `api_error + timeout \le 5.0%`, the run is valid and all unrecovered errors remain scored as 0.0 in the denominator.

### 6.4 Single Evaluation Commitment

Evaluation on `test_normal` will occur strictly **once**. Re-running an arm after inspecting test results constitutes a fatal protocol violation and is prohibited [OBSERVED AGENTS.md:7, docs/HEAVY_JOBS.md:225].

---

## 7. Decided Parameters vs. Open Parameters

### 7.1 Decided and Frozen Parameters

| Component / Parameter | Pinned Value | Source Reference |
|---|---|---|
| Planner Model | `gpt-5.6-luna` | `docs/PLAN.md:21` |
| Planner Reasoning Effort | `medium` | `docs/PLAN.md:21` |
| Planner Scaffolding | `--disable shell_tool`, `--skip-git-repo-check`, `-s read-only` | `docs/PLAN.md:92` |
| Codex CLI Version | `0.153.4` | `docs/PLAN.md:114` |
| AppWorld Commit | `42b5bcf3cd334fee33f0c37c02070a9f5807add5` | `docs/PLAN.md:111` |
| Pricing Schedule | Luna: \$0.20 input / \$0.02 cached / \$1.20 output per 1M; GPU: \$2.50/h | `docs/PLAN.md:153-154` |
| LoRA Hyperparameters | $r = 64$, $\alpha = 128$, targets: `q,k,v,o,gate,up,down`, lr 1e-4 cosine | `docs/PLAN.md:140, 317` |
| Supervised Training Size | AppWorld `train` (90 tasks $\times$ 2 seeds = 180 teacher episodes, HJ-2B) | `docs/HEAVY_JOBS.md:109-111` |
| Test Split & Task Count | AppWorld `test_normal` (168 tasks) | `docs/PLAN.md:186` |
| Number of Seeds ($N$) | $N = 3$ | `campaign/results/hj7_power.json:502` |
| Non-Inferiority Margin ($\epsilon$) | $\epsilon = 7\text{ percentage points}$ | `campaign/results/hj7_power.json:502` |
| Bootstrap Resamples | 10,000 resamples (`SEED = 20260915`) | `scripts/setup/hj1_gate.py:28-29` |

### 7.2 Open Parameters (To Be Frozen Prior to HJ-7)

The following parameters remain open and will be populated sequentially by earlier campaign jobs:

1. **DPO Penalty Weight ($\lambda$)**:  
   - *Status*: Open.  
   - *Owning Job*: **HJ-6** (Preference Optimization Sweep).  
   - *Selection Rule*: The value $\lambda \in \{0.1, 0.5, 1.0\}$ that maximizes FCD while maintaining dev TGC within $\epsilon = 7\text{ pp}$ on the dev Pareto frontier [OBSERVED docs/HEAVY_JOBS.md:191-198].
2. **Verifier Escalation Threshold ($\tau$)**:  
   - *Status*: Open.  
   - *Owning Job*: **HJ-5** (Verifier Training & Calibration).  
   - *Selection Rule*: Threshold calibrated on dev counterfactual branch labels to maximize AUROC and maintain escalation precision $\ge 70\%$ [OBSERVED docs/HEAVY_JOBS.md:176-180].
3. **Executor Model Selection**:  
   - *Status*: Open.  
   - *Owning Job*: **HJ-1.5** (State-Tracking Probe).  
   - *Selection Rule*: `ibm-granite/granite-4.2-8b` is retained if probe agreement is $\ge 40\%$; switches to fallback `Qwen/Qwen3-8B` if Granite agreement is $< 15\%$ and Qwen is materially superior [OBSERVED campaign/RUNS.md:353-357].

---

## 8. Threats to Validity

1. **Prompt Visibility Asymmetry in Preliminary Baselines**:  
   In the initial HJ-1 pilot, the executor prompt contained a defect where executed actions were omitted from the prompt transcript (`loop.py:647-651`), showing the executor only environment observations without its own generated code [OBSERVED campaign/RUNS.md:198-221]. This caused the 8B model to appear incapable of maintaining state. This baseline is being re-measured under a corrected multi-turn prompt in HJ-1R (`hj1r_exec8b_20260916` and `hj1r_prompt_only_20260916`) [OBSERVED campaign/RUNS.md:320-346]. All training and final evaluation in HJ-7 strictly employ the unified prompt renderer (`protocols/prompts.render_executor_messages`) [OBSERVED docs/PLAN.md:338-340].
2. **Planner Call Truncation (Baseline Floor Effect)**:  
   In HJ-1, 10.5% of `planner_alone` episodes (12 of 114) were terminated by global limit constraints, with 11 of those 12 hitting `max_planner_calls = 25` [OBSERVED campaign/RUNS.md:77, 82-89]. Consequently, the observed `planner_alone` score of 0.684 on dev is an artificially truncated floor rather than an unconstrained upper bound.
3. **Dev-Split Overfitting and Distribution Shift**:  
   All prompt templates, stop tokens, verifier thresholds, and DPO hyperparameters are tuned exclusively on the 57 dev tasks. Although `test_normal` is strictly held out, hyperparameter selection on dev introduces the risk of empirical distribution shift.
4. **Planner Benchmark Contamination**:  
   The knowledge cutoff for `gpt-5.6-luna` is 2026-02-16 [OBSERVED docs/PLAN.md:219], whereas AppWorld was published in 2024. Memorization of AppWorld task structures by the hosted planner is plausible. However, because all primary and secondary hypotheses evaluate paired contrasts against the identical planner instance on the exact same task instances, planner-side memorization bias is canceled across comparative arms [OBSERVED docs/PLAN.md:221-222].
