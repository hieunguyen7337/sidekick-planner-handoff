# Preregistration: Intervention-Aware Executor Specialization for Frozen Hosted Planners (Sidekick v1)

**Date**: 2026-09-15  
**Study**: Sidekick Proof-of-Concept (IAES)  
**Repository**: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`  
**Status**: Preregistered draft (prior to M3 pilot and M6 final test execution)

---

## 1. Questions and Hypotheses

Frontier language-model agents incur substantial economic and computational cost when high-capacity models execute routine environment interactions, tool calls, and state parsing. While heterogeneous collaboration (strong planner, weak executor) is established, existing systems either use unadapted executors, apply generic plan-conditioned supervised fine-tuning, or attach external post-hoc risk routers.

This study investigates: **Can a small executor model be post-trained specifically for one frozen hosted planner so that it safely absorbs long-horizon execution, minimizes downstream planner intervention burden, and maximizes frontier-compute displacement while remaining non-inferior in task success?**

### Hypotheses

All hypotheses are directional, falsifiable predictions evaluated under paired experimental conditions (identical task instances and random seeds):

- **H1 (Non-Inferiority with Compute Displacement)**:  
  The collaborative system (`sidekick`) achieves AppWorld Task Goal Completion (TGC) that is non-inferior to the frozen hosted planner operating alone (`planner_alone`) within a margin of $\epsilon = 5\text{ percentage points}$ ($Q_{\text{sidekick}} \ge Q_{\text{planner\_alone}} - 0.05$ at one-sided $\alpha = 0.05$), while achieving strictly positive frontier-compute displacement on planner tokens ($FCD_{\text{tokens}} > 0$).

- **H2 (Intervention-Aware Training Superiority)**:  
  Intervention-aware post-training (`sidekick`: SFT with correction masking + DPO on intervention preferences) achieves strictly higher TGC than intervention-agnostic plan-conditioned imitation (`sft_plan`) at matched planner token expenditure ($Q_{\text{sidekick}} > Q_{\text{sft\_plan}} \mid C_P$), or conversely achieves strictly higher $FCD_{\text{tokens}}$ at matched TGC ($p < 0.05$, paired bootstrap).

- **H3 (Calibrated Escalation)**:  
  Verifier-gated dynamic escalation in `sidekick` achieves superior escalation calibration against oracle intervention labels compared to a fixed periodic review schedule (`fixed_k`), exhibiting lower needless-ask rate ($N_{\text{needless\_ask}} / N_{\text{asks}}$), higher AUROC, and a dominating cost-quality Pareto curve.

- **H4 (Integrated Policy vs. Bolted-On Router)**:  
  Training the escalation decision directly into the executor policy via intervention-aware post-training (`sidekick`) achieves a superior empirical cost-quality Pareto frontier compared to a two-stage sequential baseline consisting of a frozen executor policy paired with an external residual-risk router (`router_seq`).

### Advance Prediction and Rule on Primary Claims

> **Preregistered Capability Expectation**:  
> Published benchmarks on AppWorld establish that a frozen ~8B open model achieves only 1.0–17.0% TGC on `test_normal`, and supervised fine-tuning on thousands of trajectories reaches approximately 26.0–33.0% TGC, whereas the hosted planner (`gpt-5.6-luna`) achieves 85.1% TGC [verified].  
> Therefore, this plan explicitly predicts in advance that an 8B executor will **not** achieve non-inferiority ($\epsilon = 5\text{ pp}$) at high displacement rates ($FCD > 0.70$).  
>  
> **Scientific Decision Rule**:  
> The core deliverable of this study is the empirical **quality-versus-displacement Pareto frontier** across the intervention-penalty sweep ($\lambda$). Hypotheses **H2** (intervention-awareness vs. plain SFT) and **H3** (calibrated escalation vs. fixed review) are the primary theoretical claims that survive a weak executor backbone. A failure of H1 at high displacement must be reported transparently on the frontier curve and must **not** be rewritten post hoc as if H1 were never the headline question.

---

## 2. Experimental Design

### 2.1 Systems Evaluated

Eight systems are implemented within a unified execution harness sharing identical schemas, timeouts, and cost accounting:

| System Name | Description & Role in the Scientific Argument |
|---|---|
| `planner_alone` | Frozen hosted planner (`gpt-5.6-luna`) executes all steps alone (the baseline for H1 and FCD). |
| `executor_alone` | Base executor (`granite-4.2-8b`) runs without planner (measures capability gap and headroom). |
| `prompt_only` | Untrained executor conditioned on planner delegation packets (measures prompt-only zero-shot collaboration). |
| `fixed_k` | Cost-matched control: planner reviews and intervenes every $k$ fixed executor steps ($k \in \{2, 4, 8\}$). |
| `sft_plan` | Intervention-agnostic training: executor trained on successful plan-conditioned trajectories (control for H2). |
| `router_seq` | R2V-style sequential baseline: frozen executor + external calibrated risk router (control for H4). |
| `sidekick` | Proposed method: intervention-aware SFT(c) + verifier-guided DPO with explicit `ASK_PLANNER` action. |
| `oracle_escalation` | Dev-only reference ceiling: escalates at steps known counterfactually to require planner intervention. |

### 2.2 Domain and Split Allocation

The benchmark domain is **AppWorld** (750 tasks across 250 scenarios):

- **`train` (105 tasks / 35 scenarios)**: Trajectory collection (2 planner-alone demonstrations + 8 prompt-only rollouts per task) and all supervised/preference training.
- **`dev` (60 tasks / 20 scenarios)**: Hyperparameter selection, escalation threshold calibration, temperature scaling for verifier, prompt iteration, and stopping decisions.
- **`test_normal` (168 tasks / 56 scenarios)**: The single final evaluation benchmark evaluated over 3 distinct random seeds (504 task evaluations per system; 3,024 runs across primary systems).
- **`test_challenge` (417 tasks / 139 scenarios)**: Optional out-of-distribution evaluation (unseen apps), evaluated on 1 seed for 3 key systems (`planner_alone`, `sft_plan`, `sidekick`).

### 2.3 Paired Task Design

All comparisons are strictly paired by `(task_id, seed)`. For every task instance:
1. Environment state initialization is identical across all system arms.
2. The identical frozen planner configuration (`gpt-5.6-luna`, `model_reasoning_effort=medium`, pinned CLI version `0.153.4`) is queried across all collaborative and planner-alone arms.
3. Differences in performance and cost are computed per pair, canceling task-difficulty variance and planner-side memorization noise.

### 2.4 Freezing Timeline

1. **Protocol & Schemas**: Frozen at Milestone M1 (`src/sidekick/protocols/schemas.py`).
2. **Prices & Pricing Schedule**: Frozen at M1 (`configs/cost/prices_2026-09.yaml`).
3. **Training Data & Models**: LoRA checkpoints and verifier heads frozen at M5.
4. **Hyperparameters & Decision Thresholds**: Multipliers $\lambda \in \{0.1, 0.5, 1.0\}$, verifier thresholds, and non-inferiority margin $\epsilon = 0.05$ frozen at M5 on `dev`.
5. **Final Evaluation**: Executed at M6 on `test_normal` strictly once.

---

## 3. Primary and Secondary Outcomes

### 3.1 Primary Outcomes

1. **Task Goal Completion (TGC)**:  
   Binary programmatic evaluation of final environment state assertions and collateral damage checks ($1.0$ if all task requirements met and no collateral violations; $0.0$ otherwise).
2. **Frontier-Compute Displacement ($FCD_{\text{tokens}}$)**:  
   Paired token savings ratio relative to planner operating alone:
   $$FCD_{\text{tokens}} = 1 - \frac{\text{PlannerTokens}(\text{collaboration})}{\text{PlannerTokens}(\text{planner\_alone})}$$

### 3.2 Secondary Outcomes

1. **Scenario Goal Completion (SGC)**: Fraction of scenarios (groups of 3 related tasks) where all constituent tasks succeed.
2. **Frontier Calls Displacement ($FCD_{\text{calls}}$)** and **Dollar Displacement ($FCD_{\text{dollars}}$)**.
3. **Total System Cost ($C_{\text{total}}$)**: Sum of planner API costs ($0.20/1M input, $0.02/1M cached input, $1.20/1M output USD) plus local executor/verifier compute amortized at $\$2.50/\text{H100 GPU-hour}$.
4. **Planner Intervention Burden ($I$)**:
   - Number of planner corrections per task ($N_{\text{correct}}$).
   - Number of planner takeovers per task ($N_{\text{takeover}}$).
   - Planner rework tokens incurred to repair executor mistakes ($C_{\text{rework}}$).
   - Avoidable intervention rate: fraction of planner interventions triggered by false-alarm escalations or executor misreporting.
5. **Escalation Quality**:
   - Escalation precision, recall, AUROC, and Brier score against oracle continuation labels.
   - **Needless-Ask Rate**: Fraction of `ASK_PLANNER` actions where counterfactual continuation would have succeeded without intervention.
6. **Safety & Policy Violations**:
   - **Unsafe Action Rate**: Frequency of executing irreversible actions (send, pay, delete, post) without planner confirmation or when forbidden by constraints.
   - **Constraint Violation Rate**: Rate of violating explicit constraints in the delegation packet.

---

## 4. Analysis Plan

### 4.1 Statistical Testing Framework

- **Unit of Analysis**: The task instance pair $\Delta_i = Y_{i, \text{system}} - Y_{i, \text{baseline}}$ on task $i \in \{1, \dots, N\}$.
- **Paired Bootstrap Resampling**: 10,000 bootstrap resamples stratified by scenario cluster to account for intra-scenario correlation.
- **Hypothesis Testing for H1 (Non-inferiority)**:  
  One-sided 95% bootstrap confidence interval on $\Delta_{\text{TGC}} = \text{TGC}_{\text{sidekick}} - \text{TGC}_{\text{planner\_alone}}$. Non-inferiority is declared if the lower bound of the 95% CI satisfies:
  $$\text{LB}_{0.95}(\Delta_{\text{TGC}}) \ge -\epsilon = -0.05$$
- **Hypothesis Testing for H2, H3, H4**:  
  Paired differences evaluated with two-sided and one-sided bootstrap tests ($\alpha = 0.05$).

### 4.2 Multiple-Comparison Policy

- The primary evaluation of H1 and the Pareto frontier across the $\lambda$ sweep ($\lambda \in \{0.1, 0.5, 1.0\}$) is reported as non-dominated empirical frontiers with bootstrap confidence bands.
- Secondary hypothesis tests across multiple $\lambda$ endpoints will apply Benjamini-Hochberg False Discovery Rate (FDR) control at $q = 0.05$.

### 4.3 Handling of Missing Data, Crashes, and Limit-Hits

- **Strict Denominator Rule**: All tasks initialized must be accounted for in the denominator.
- **Failures and Timeouts**: Runs exceeding the global limits (`max_steps=40`, `max_tokens_per_episode=32000`, `per_step_timeout_s=120`, `max_planner_calls=25`), environment crashes, or API errors are assigned $\text{TGC} = 0.0$ and recorded with an explicit `error_type` (`limit`, `timeout`, `crash`, `parse_error`, `api_error`).
- No failed run may be pruned, filtered, or excluded from reported statistics.

---

## 5. Stopping and Decision Rules

### 5.1 Falsification and Abandonment Rules (Evaluated at Milestone M3/M5 on `dev`)

The method will be considered falsified and development pivoted if any of the following occur on `dev`:
1. **Intervention-awareness failure**: `sidekick` fails to achieve higher TGC than `sft_plan` at matched planner token budget ($p > 0.10$ on dev bootstrap).
2. **Escalation calibration failure**: The process verifier achieves an AUROC $\le 0.55$ or fails to improve Brier score over baseline task failure prevalence.
3. **Excessive intervention overhead**: Planner scaffolding and verification token overhead exceeds 75% of planner-alone tokens, rendering $FCD_{\text{dollars}} \le 0$.

### 5.2 Replication and Success Criteria for H2

A successful demonstration of H2 requires:
- A statistically significant positive paired difference in TGC on `test_normal` for `sidekick` vs. `sft_plan` at matched planner token budget ($\Delta_{\text{TGC}} > 0$, $p < 0.05$, paired bootstrap).

### 5.3 Single Final Test Run Rule

The test splits (`test_normal` and `test_challenge`) will be evaluated exactly **once** at Milestone M6. No prompt adjustments, hyperparameter re-tuning, threshold tweaks, or post-hoc model retraining are permitted following test evaluation.

---

## 6. Explicit Non-Claims

To maintain rigorous scientific boundaries, this study explicitly does **not** claim:

1. **No State-of-the-Art Leaderboard Claim**: We do not claim to beat top AppWorld leaderboard entries that employ 400+ GPU-hour on-policy RL algorithms (e.g., CANOPY 14B at 86.9% TGC or LOOP 32B). Our work is restricted to offline post-training (LoRA SFT + DPO) on 105 training tasks.
2. **No Frontier-Model Capability Claim**: The planner used is `gpt-5.6-luna` (the lowest-cost hosted GPT-5.6 tier), selected for budget tractability and token billing rather than maximum reasoning capacity.
3. **No General Online-RL Claim**: We do not evaluate online policy gradients or PPO/GRPO in the environment loop.
4. **No Exact Preservation Guarantee**: Unlike speculative decoding in token generation, interactive agent delegation under partial observability cannot offer lossless behavioral equivalence. Non-inferiority is strictly an empirical statistical property.

---

## 7. Spec Deviations Register

Seeded from §2 of `docs/PLAN.md`, recording all intentional reductions from `RESEARCH_PROJECT_SPEC.md`:

| Spec Requirement | Proof-of-Concept Implementation | Rationale | Date Recorded |
|---|---|---|---|
| Frozen frontier planner | Frozen hosted planner: `gpt-5.6-luna` (medium reasoning effort) | No frontier key funded; luna is frozen, hosted, token-billed, and sufficiently strong (85.1% TGC). | 2026-09-15 |
| Dual domains (AppWorld + TerminalBench) | AppWorld only | No root/fakeroot for Docker/Podman/Harbor on cluster; pure Python environment suffices to prove mechanism. | 2026-09-15 |
| FLOPs-based cost accounting | Tokens, calls, dollars for planner; GPU-seconds for executor | Closed hosted API provides no FLOP counters; billing reflects real economic cost. | 2026-09-15 |
| Two executor sizes (8B + 14B) | One family: `granite-4.2-8b` (primary) + `3b` (capability-gap arm) | Halves training budget; model size axis is not the core scientific claim. | 2026-09-15 |
| 5-head verifier architecture | Single-head verifier ("escalate now") | PoC requires risk calibration, not a multi-class taxonomy. | 2026-09-15 |
| Online RL (verl / GRPO) | Offline post-training only: SFT(c) + DPO | On-policy RL requires 400+ GPU-hours; PoC specifically tests offline sample-efficient post-training. | 2026-09-15 |
| 14 system variants | 8 systems (`planner_alone`, `executor_alone`, `prompt_only`, `fixed_k`, `sft_plan`, `router_seq`, `sidekick`, `oracle_escalation`) | Retains exact controls needed for H1–H4 while minimizing compute. | 2026-09-15 |
| Cross-planner transfer evaluation | Out of scope by default | Requires a second funded hosted planner API. | 2026-09-15 |
| Non-inferiority margin $\epsilon = 3\text{ pp}$ | Margin $\epsilon = 5\text{ pp}$ | Reflects realistic statistical power with $N=168 \times 3\text{ seeds}$ on AppWorld. | 2026-09-15 |
