# Preregistration: Intervention-Aware Executor Specialization for Frozen Hosted Planners (Sidekick v1)

**Status**: **DRAFT** — To be frozen strictly at milestone J9 (after the dev frontier sweep at J8) and before the single evaluation on `test_normal` (J10).  
**Date**: 2026-09-16 (restructured 2026-09-17)  
**Study**: Sidekick Proof-of-Concept (IAES)  
**Repository**: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15` [OBSERVED campaign/workers/briefs/PREREG_draft.md:4]  
**Frozen on**: ____________________  

### Parameters Frozen at J9 (on dev, never revisited)

The following parameters, rules, and configurations are resolved on **dev** at milestone J8/J9 and never revisited after J9 [OBSERVED campaign/RUNS.md:1410-1433]:
1. **Sidekick Operating Threshold ($\tau^*$)**: Resolved on dev by thresholding the policy's own $P(\text{ASK})$ / verifier gate score along the empirical quality-displacement Pareto curve at J8 [OBSERVED campaign/RUNS.md:1354-1358]. (Note: DPO stage HJ-6 was dropped on 2026-09-17; operating points are swept via serve-time thresholding on a single adapter, doubling as the H3 calibration measurement).
2. **Router Decision Threshold ($\text{router } \tau^*$)**: Decision threshold for `router_seq`, calibrated on dev to match `sidekick`'s planner call budget.
3. **`k_matched` Rule**: Stated as a **rule, not a number**: *the $k \in \{3, 5, 10\}$ whose dev calls per episode is nearest the sidekick's, interpolating to $k = 7$ if $k = 5$ and $k = 10$ tie* [OBSERVED campaign/RUNS.md:1430-1432]. Resolved on dev at J8 and never revisited after J9.
4. **ASK Template String**: Fixed prompt template string for `ASK_PLANNER` invocation.
5. **Oracle Label Rule**: Fixed at Gate B (J6) on counterfactual continue-branches (two seeds, 101 and 102, temperature 0.7 without correction):
   - `needed := mean(branch_gpr) < actual_gpr`
   - `needless := mean(branch_gpr) >= actual_gpr` (the boundary case is needless)
   - `harmful := mean(branch_gpr) > actual_gpr`; `needed_strict :=` both samples below actual
   - either sample missing $\rightarrow$ `incomplete`, no label, never imputed [OBSERVED campaign/RUNS.md:1389-1396].
6. **Arm List**: Pinned arm definitions for J10 (`planner_alone`, `executor_alone`, `prompt_only`, `fixed_k(k_matched)`, `sft_plan(sft_b_plus)`, `sidekick(\tau^*)`, and optionally `router_seq(\tau^*)`).

---

## 1. The Claim Being Tested

Autonomous software agents that rely exclusively on high-capacity hosted language models incur heavy token and dollar costs when executing routine, programmatic tool calls. While dividing labour between a strong planner and a smaller executor is intuitively appealing, unadapted small executors lack domain agency, whereas generic plan-conditioned imitation fails to teach the executor when it must escalate back to the planner.

The thesis of this project is that **a small, locally served executor model specialised to one frozen hosted planner (`sidekick`) achieves superior task performance through intervention-aware training while selectively requesting planner assistance to displace costly hosted planner compute** [OBSERVED campaign/workers/briefs/PREREG_draft.md:27-31, docs/PLAN.md:3, 241-255, campaign/RUNS.md:1337-1360].

### 1.1 Hypotheses and Primary Endpoint

All hypotheses are directional, falsifiable predictions evaluated under paired experimental conditions on identical task instances and random seeds:

- **Primary Endpoint — H2 (Adaptive Escalation Superiority — Conjunctive)**:  
  Evaluated on AppWorld `test_normal` over 168 tasks $\times N=3$ seeds = 504 paired comparisons, via one-sided 95% paired bootstrap (10,000 resamples). Tested using `sft_b_plus` as the policy with dynamic escalation (self $P(\text{ASK})$ gating / sequential routing), reachable without `sft_c`. All three conditions must hold [OBSERVED campaign/RUNS.md:1418-1424]:
  1. `sidekick` $\ge$ `fixed_k(k_matched)` $- 7\text{ pp}$
  2. `sidekick` $>$ `sft_plan(sft_b_plus)`, CI excluding 0
  3. `sidekick` planner calls/episode $<$ `fixed_k(k=5)`'s, CI excluding 0

  **Why conjunctive**:  
  The conjunction has teeth. A policy that never asks passes (1) trivially only when the timer is worthless, and (3) trivially always — but then fails (2), because it *is* `sft_plan`. A policy that always asks passes (2) and fails (3). Only a policy that asks selectively passes all three. H1 becomes secondary and is reported whatever it shows [OBSERVED campaign/RUNS.md:1425-1428].

- **Secondary Hypotheses**:
  - **H1 (Task Quality Non-Inferiority vs. `planner_alone`)**:  
    `sidekick` achieves AppWorld Task Goal Completion (TGC) non-inferior to `planner_alone` within $\epsilon = 7\text{ percentage points}$ ($\text{TGC}_{\text{sidekick}} \ge \text{TGC}_{\text{planner\_alone}} - 0.07$, one-sided 95% paired bootstrap CI), with strictly positive frontier-compute displacement on planner tokens ($FCD_{\text{tokens}} > 0$) [OBSERVED campaign/RUNS.md:1412-1428].  
    *Status*: Secondary, reported whatever it shows. Dev measurements (SFT TGC 0.430 vs. planner 0.684) show an 8B executor cannot match the planner alone at high displacement, so the deliverable for H1 is the quality-versus-displacement Pareto frontier.
  - **H3 (Escalation Calibration & Dev AUROC / ECE)**:  
    Dynamic escalation in `sidekick` (self $P(\text{ASK})$ gating / sequential routing) achieves superior calibration against oracle intervention labels on dev compared to static periodic review (`fixed_k`), exhibiting lower needless-ask rate, high AUROC, and low ECE. Reachable with `sft_b_plus`.
  - **H4 (Integrated Policy vs. Bolted-On Router — Conditional)**:  
    `sidekick(sft_c)` achieves superior TGC compared to `router_seq(\tau^*)` on `sft_b_plus` at matched planner calls ($p < 0.05$, paired bootstrap). **Explicitly conditional** on the clean-counterfactual pilot (`suppress_next` mode in A8) demonstrating trainable label signal. If the pilot fails, `sft_c` remains paused and H4 is not evaluated.
  - **Dev Needed-Fraction ($f$)**:  
    The fraction of `fixed_k` timer interventions that were outcome-critical ($f_{\text{dev}}$), evaluated by counterfactual continue-branches at Gate B (J6) [OBSERVED campaign/RUNS.md:1386-1409].

### 1.2 Advance Capability Expectations and Falsification Criteria

- **Advance Expectation on Weak Executors**: Published benchmarks on AppWorld indicate that frozen ~8B open models achieve between 1.0% and 17.0% TGC on `test_normal`, and supervised fine-tuning reaches 26.0%–33.0% TGC, whereas `gpt-5.6-luna` scores 85.1% TGC [OBSERVED docs/PLAN.md:102, 256-258]. On dev, `sft_plan(sft_b)` scores 0.4298 vs `planner_alone` 0.6842 [OBSERVED campaign/RUNS.md:952-954]. An 8B executor is therefore not expected to achieve non-inferiority ($\epsilon = 7\text{ pp}$) at high displacement rates ($FCD > 0.70$).  
- **Core Deliverable**: The empirical deliverable is the **quality-versus-displacement Pareto frontier**. The non-inferiority point will be explicitly marked on this curve.  
- **Preregistered Falsification (Verbatim from RUNS.md:1434-1436)**:  
  *if (2) fails, intervention-aware training did not beat intervention-agnostic training on this data; if (3) fails, it did not save cost. Either is reported as measured. J10 runs once.* [OBSERVED campaign/RUNS.md:1434-1436]

---

## 2. Experimental Design and Statistical Power

### 2.1 Benchmark and Split Allocation

The final evaluation (J10, formerly HJ-7) is conducted exclusively on the official **`test_normal`** split of the **AppWorld** benchmark [OBSERVED docs/PLAN.md:186, docs/HEAVY_JOBS.md:217]:
- **Evaluation Benchmark**: AppWorld `test_normal` (168 tasks across 56 scenarios) [OBSERVED docs/PLAN.md:186].
- **No Contamination Policy**: `test_normal` is evaluated strictly once at milestone J10. No prompt tuning, threshold calibration, error analysis, or model retraining is permitted on test splits [OBSERVED campaign/workers/briefs/PREREG_draft.md:61, docs/PLAN.md:204].
- **Supervised Training Split**: AppWorld `train` (measured at 90 tasks, 30 scenarios) [OBSERVED docs/PLAN.md:184, docs/HEAVY_JOBS.md:119].
- **Tuning and Calibration Split**: AppWorld `dev` (measured at 57 tasks, 19 scenarios) [OBSERVED docs/PLAN.md:185, campaign/RUNS.md:9].

### 2.2 System Arms in J10

J10 evaluates the system arms across 168 tasks and $N = 3$ random seeds ($168 \times N_{\text{arms}} \times 3$ evaluation runs; 504 paired comparisons per contrast) [OBSERVED campaign/RUNS.md:1418-1424]:

| System Name | Description & Role in Scientific Argument |
|---|---|
| `planner_alone` | Frozen hosted planner (`gpt-5.6-luna`) executes all steps (reference ceiling for H1 and FCD). |
| `executor_alone` | Base executor model without planner assistance (establishes the zero-shot capability floor). |
| `prompt_only` | Base executor model executing a single initial delegation packet from `gpt-5.6-luna` without re-entry. |
| `fixed_k(k_matched)` | Cost-matched static control: planner reviews every $k_{\text{matched}}$ steps, where $k_{\text{matched}}$ is resolved on dev at J8. |
| `sft_plan(sft_b_plus)` | Intervention-agnostic control (`sft_b_plus`): executor trained on identical data volume without ASK targets. |
| `sidekick(\tau^*)` | Proposed system: intervention-aware SFT(c) with verifier-gated dynamic `ASK_PLANNER` escalation at threshold $\tau^*$. |
| `router_seq(\tau^*)` | (Optional comparative arm for H4): frozen executor paired with sequential external router at threshold $\tau^*$. |

### 2.3 Sample Size and Margin Justification (Power Analysis)

The sample size of **$N = 3$ seeds** and the non-inferiority margin of **$\epsilon = 7\text{ percentage points}$** are frozen based on the pre-run power analysis conducted in `scripts/setup/hj7_power.py` and recorded in `campaign/results/hj7_power.json` [OBSERVED campaign/results/hj7_power.json:469-505, docs/HEAVY_JOBS.md:206-214]:

1. **Measured Baseline Discordance**: On the dev split (57 tasks $\times$ 2 seeds), `planner_alone` exhibited an empirical seed discordance rate of **28.0702%** (16 discordant task pairs out of 57; 31 concordant successes, 10 concordant failures) [OBSERVED campaign/results/hj7_power.json:471-475]. The marginal TGC gap between seed 1 (0.6491) and seed 2 (0.7193) was 7.0175 pp [OBSERVED campaign/results/hj7_power.json:480-488, campaign/RUNS.md:91].
2. **Power under Latent-Difficulty Model**: Calibrated against this measured variance, Monte Carlo simulations (2,000 experiment replicates, 200 bootstrap replicates per rep) over 168 tasks show that the smallest non-inferiority margin resolvable at $\ge 80\%$ power when `sidekick` matches `planner_alone` (true rate 0.68) is **7 pp at N = 3** (simulated power = **0.8600** $\pm$ 0.0078 MCSE, mean CI half-width = 4.58 pp) [OBSERVED campaign/results/hj7_power.json:235-260, 502].
3. **Why Additional Seeds Do Not Help**: Sizing to $N = 4$ or $N = 5$ seeds yields identical resolvable margins of **7 pp** (power = 0.9280 at N = 4, 0.9640 at N = 5) [OBSERVED campaign/results/hj7_power.json:339, 423, 503-504]. While extra seeds narrow the CI half-width (4.58 pp at N=3 $\rightarrow$ 3.98 pp at N=4 $\rightarrow$ 3.55 pp at N=5), they fail to resolve $\epsilon = 5\text{ pp}$ at $\ge 80\%$ power (power at $\epsilon = 5\text{ pp}$ is only **0.5910** at N = 3, **0.6755** at N = 4, and **0.8090** at N = 5) [OBSERVED campaign/results/hj7_power.json:250, 334, 418]. The binding constraint on statistical power is the fixed number of benchmark tasks (168), not the seed count. Budgeting more than 3 seeds would waste cluster quota without changing the resolvable margin.
4. **Sensitivity under Worst-Case Mixture Model**: Under the pessimistic common-or-independent mixture correlation model (`campaign/results/hj7_power_mixture.json`), statistical power is strictly lower: at N = 3, power at $\epsilon = 7\text{ pp}$ reaches only 0.4590, and the smallest resolvable margin at $\ge 80\%$ power is **10 pp even at N = 5** (power = 0.8320; power at $\epsilon = 7\text{ pp}$ is 0.5300) [OBSERVED campaign/results/hj7_power_mixture.json:255, 423, 499-505]. This sensitivity result will be reported alongside the primary analysis.
5. **Independent Corroboration on the Train Split, and Why the Conservative Estimate Was Kept**:  
   The discordance above is measured on dev (57 tasks). HJ-2B gives a second, larger, fully independent estimate of the same quantity from the same frozen planner: on **train, 90 tasks × 2 seeds**, discordance is **18.89%** (17 of 90; 58 concordant successes, 15 concordant failures) with a seed-1/seed-2 marginal gap of only **1.11 pp** (0.7444 vs 0.7333) [OBSERVED campaign/results/hj2b_planner_train_20260916.runs.jsonl, 180 runs]. The two estimates are **not significantly different** — 16/57 carries a standard error of ≈5.9 pp and 17/90 one of ≈4.1 pp, so the 9.2 pp difference is ≈1.3 combined standard errors, and the pooled estimate over all 147 task-pairs is **22.4%**. The dev figure is therefore an unlucky-draw high estimate rather than a contradiction, and the striking 7.0 pp dev seed gap that originally motivated this analysis does **not** reproduce on the larger split.  
   ⚠ The design is nevertheless calibrated on the **dev** figure, deliberately. Higher assumed noise means lower assumed power, so ε = 7 pp is the **conservative** choice: if the true discordance is nearer 19%, the realised power at ε = 7 pp exceeds the 0.860 stated above. Re-deriving ε downward from the friendlier train number after seeing it would be exactly the post-hoc margin selection a preregistration exists to prevent.

---

## 3. Primary Metric and Exact Statistical Test

### 3.1 Primary Metric Specification

- **Per-Run Metric**: AppWorld Task Goal Completion ($\text{TGC} \in \{0.0, 1.0\}$), determined by programmatic evaluation of ground-truth state assertions and collateral damage checks [OBSERVED docs/PLAN.md:90-95, 215-218].
- **Task-Level Aggregation**: For each system and task $i \in \{1, \dots, 168\}$, the task score is the mean TGC across the $N = 3$ evaluated seeds:
  $$\overline{\text{TGC}}_{i, \text{system}} = \frac{1}{3} \sum_{s=1}^3 \text{TGC}_{i, s, \text{system}}$$
- **Paired Difference**: For each task $i$ and contrast arm $\text{baseline}$:
  $$\Delta_i = \overline{\text{TGC}}_{i, \text{sidekick}} - \overline{\text{TGC}}_{i, \text{baseline}}$$

### 3.2 Exact Bootstrap Test

The statistical evaluation of the primary endpoint (H2) will be executed using the exact bootstrap procedure implemented in **`scripts/setup/hj1_gate.py`**, specifically the **`paired_diff()`** function [OBSERVED scripts/setup/hj1_gate.py:111-139, campaign/results/hj7_power.json:4-6]:

- **Resampling Method**: 10,000 paired bootstrap resamples of the task difference vector $(\Delta_1, \dots, \Delta_{168})$ [OBSERVED scripts/setup/hj1_gate.py:28, 126-130].
- **Random Seed**: Fixed at `SEED = 20260915` [OBSERVED scripts/setup/hj1_gate.py:29].
- **Confidence Interval**: Percentile bootstrap 95% confidence interval $[\text{ci95\_pp}[0], \text{ci95\_pp}[1]]$ derived from the 2.5th and 97.5th percentiles of resampled mean differences [OBSERVED scripts/setup/hj1_gate.py:129-136].
- **Decision Rule (Primary Conjunctive H2)**:
  1. `sidekick` $\ge$ `fixed_k(k_matched)` $- 7.00\text{ pp}$ ($\text{ci95\_pp}[0] \ge -7.00\text{ pp}$ against `fixed_k(k_matched)`)
  2. `sidekick` $>$ `sft_plan(sft_b_plus)` ($\text{ci95\_pp}[0] > 0.00\text{ pp}$ against `sft_plan(sft_b_plus)`)
  3. `sidekick` planner calls/episode $<$ `fixed_k(k=5)`'s ($\text{ci95\_pp}[1] < 0.00$ calls against `fixed_k(k=5)`)
  [OBSERVED campaign/RUNS.md:1418-1424].

---

## 4. Secondary Metrics and Advance Directionality

All secondary outcomes are assigned an advance directional expectation:

1. **Scenario Goal Completion (SGC)**:  
   Fraction of AppWorld scenarios (clusters of 3 tasks) where all constituent tasks succeed ($1.0$ if all tasks pass, $0.0$ otherwise) [OBSERVED scripts/setup/hj1_gate.py:49-88].  
   *Direction*: $\text{SGC}_{\text{sidekick}} \ge \text{SGC}_{\text{sft\_plan}}$.
2. **Planner Calls per Episode ($n_{\text{calls}}$)**:  
   Total number of hosted planner invocations attempted per episode [OBSERVED campaign/RUNS.md:168-175, docs/PLAN.md:157-158].  
   *Direction*: $\text{sidekick} \ll \text{planner\_alone}$ (expected $\le 4.0$ vs. $13.5$ in `planner_alone`) [OBSERVED campaign/RUNS.md:9].
3. **Planner Token Expenditure ($C_P$) & Compute Displacement ($FCD_{\text{tokens}}$)**:  
   Total billed planner tokens per episode (input + $0.10 \times \text{cached input} + \text{output} + \text{reasoning output}$) [OBSERVED docs/PLAN.md:99, 153].  
   *Direction*: $\text{sidekick} \ll \text{planner\_alone}$, establishing $FCD_{\text{tokens}} = 1 - C_{P, \text{sidekick}} / C_{P, \text{planner\_alone}} > 0$.
4. **Frontier Cost per Solved Task ($C_{\text{solved}}$)**:  
   Total system dollar cost (luna token list prices + local GPU compute amortized at US$2.50/GPU-hour) divided by the number of completed tasks [OBSERVED docs/PLAN.md:152-155].  
   *Direction*: $\text{sidekick} < \text{planner\_alone}$.
5. **Escalation ASK Rate ($r_{\text{ask}}$)**:  
   Fraction of executor steps emitting `ASK_PLANNER` ($N_{\text{asks}} / N_{\text{steps}}$).  
   *Direction*: Monotonically decreasing with operating threshold $\tau^*$.
6. **Verifier Calibration and Discrimination (AUROC / ECE / Brier)**:  
   Discrimination AUROC $\ge 0.70$ and Expected Calibration Error (ECE) evaluated against dev counterfactual branch labels.

   > **Amendment 2026-09-19 (post-result, J7) — verifier discrimination, mathematical retraction, and reporting rule.**
   >
   > Secondary metric 6 originally specified: “Discrimination AUROC $\ge 0.70$ … evaluated against dev counterfactual branch labels.” Working briefs (e.g. W-16, A9) subsequently used an operational figure of 0.65 that did not appear in this document. Document history confirms **0.70** is the written registered threshold in this preregistration text, while 0.65 was an operational target introduced in working briefs. The fitted verifier misses both as a point estimate.
   >
   > The fitted `feature_lr_v1` verifier, scored on the J6 four-replicate needed/needless labels (ambiguous excluded), reached dev AUROC **0.5916711736073553** ($n = 86$; 43/43; 95% point-bootstrap CI [0.4677, 0.7111]; 95% task-bootstrap CI [0.4576, 0.7416]) [OBSERVED artifacts/verifiers/feature_lr_20260918/metrics.json:20, campaign/workers/A9_THRESHOLD.md:25-40]. That point estimate misses both 0.65 and 0.70. This amendment is written with full knowledge of that result.
   >
   > **Retraction of earlier attenuation claim:** An earlier working claim held that label reliability $\rho \approx 0.4504$ made 0.65 or 0.70 unmeetable by construction because $\sqrt{0.45} \approx 0.67$. That claim is mathematically incorrect and is **formally retracted**. $\sqrt{\rho}$ bounds a Pearson correlation, not an AUROC rank statistic. Under the same Gaussian true-score model at $\rho = 0.4504$, a perfect predictor of the latent effect scores AUROC **0.9622** against the band-thresholded labels [OBSERVED campaign/workers/A9_THRESHOLD.md:29-32, 156-166], and a 2-vs-2 split-half empirical proxy on J7's own dev evaluation subset reaches mean AUROC **0.9285** (range 0.8391–0.9776) [OBSERVED campaign/workers/A9_THRESHOLD.md:33-35, 266-269]. The threshold was reachable; 0.5917 is a genuine miss.
   >
   > **What is not being changed:** The original absolute threshold (0.70) is **not lowered** to a number the fitted verifier would pass. A post-hoc drop from 0.70 (or 0.65) to $\le 0.59$ would make the pre-registration ornamental. The miss is recorded.
   >
   > **Reporting rule adopted with disclosure:** Every verifier AUROC reported against J6 labels is to be published with three companions, computed from the same rows without reference to the fitted head's pass/fail:
   > 1. *Floor* — AUROC of a constant score (0.5000) and of the train per-step-index class prior applied to dev (0.5070) [OBSERVED campaign/workers/A9_THRESHOLD.md:195-197].
   > 2. *Label-noise ceiling proxy* — mean AUROC over the three 2-vs-2 partitions of branch seeds {101,102,103,104}, evaluated on the complete non-ambiguous dev subset (0.9285, range [0.8391, 0.9776]) [OBSERVED campaign/workers/A9_THRESHOLD.md:266-269].
   > 3. *Interval* — bootstrap CI for the fitted AUROC ([0.4677, 0.7111] point-level; [0.4576, 0.7416] task-level) [OBSERVED campaign/workers/A9_THRESHOLD.md:292-293].
   >
   > Under this reporting rule, J7 reads: AUROC 0.5917 [0.47, 0.71] against floor 0.50 / 0.51 and label-noise ceiling 0.93 [0.84, 0.98] — capturing $\approx 0.21$ of the chance-to-ceiling gap, with a CI covering the floor. The fitted head does not beat univariate `transcript_chars` (0.6095) or `step` (0.6001) [OBSERVED campaign/workers/A9_THRESHOLD.md:210-213].

7. **Dev Needed-Fraction ($f_{\text{dev}}$)**:  
   Fraction of periodic timer interventions classified as `needed` via counterfactual branching at Gate B (J6).
8. **Unsafe Irreversible Action Violations**:  
   Number of unauthorized calls to irreversible APIs (send, pay, delete, post) without planner confirmation.  
   *Direction*: Exactly zero for `sidekick`.

---

## 5. Controls and What Each One Rules Out

To isolate the mechanism of intervention awareness, the arms rule out specific alternative explanations:

1. **`planner_alone` (Hosted Reference)**: Rules out task difficulty and defines the performance ceiling under full hosted intelligence.
2. **`executor_alone` (Zero-Shot Capability Floor)**: Rules out the baseline competence of the small model without guidance and measures the maximum headroom available to close.
3. **`prompt_only` (One-Shot Plan Following)**: Rules out zero-shot instruction following. Re-evaluated in HJ-1R at TGC 0.0439 under the corrected multi-turn prompt [OBSERVED campaign/RUNS.md:446, 459].
4. **`fixed_k(k_matched)` (Periodic Intervention Control)**: Rules out brute-force periodic review ($k \in \{3, 5, 10\}$ matched to sidekick call volume). Establishes whether dynamic, need-based escalation is superior to fixed interval scheduling at matched planner calls.
5. **`sft_plan(sft_b_plus)` (The Crucial Data-Volume Control)**:  
   The `sft_plan` baseline is instantiated using **`sft_b_plus`**. `sft_b_plus` is trained on the exact same trajectory dataset as `sidekick` (J2 teacher demonstrations + J4 post-correction actions), with **no `ASK_PLANNER` targets** [OBSERVED campaign/RUNS.md:1258-1266, 1349-1350].  
   *Scientific Purpose*: `sidekick` and `sft_b_plus` receive **identical supervised token volume and demonstration coverage**. The contrast `sidekick` vs. `sft_b_plus` differs **strictly in the availability of the `ASK_PLANNER` escalation channel**. Without `sft_b_plus`, any performance advantage of `sidekick` over `sft_plan` could be dismissed as an artifact of seeing more training data or post-correction examples rather than learned escalation.

---

## 6. Stopping, Execution, and Exclusion Rules

### 6.1 Strict Denominator and Zero-Exclusion Commitment

- **Complete Accounting**: Every initialized task instance in the $168 \times N_{\text{arms}} \times 3$ matrix is included in the denominator of all reported metrics. No task or seed may be pruned, filtered, or dropped post hoc [OBSERVED AGENTS.md:7].
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

Evaluation on `test_normal` (J10) will occur strictly **once**. Re-running an arm after inspecting test results constitutes a fatal protocol violation and is prohibited [OBSERVED AGENTS.md:7, docs/HEAVY_JOBS.md:225, campaign/RUNS.md:1436].

---

## 7. Decided Parameters vs. Parameters Frozen at J9

### 7.1 Decided and Frozen Parameters

| Component / Parameter | Pinned Value | Source Reference |
|---|---|---|
| Planner Model | `gpt-5.6-luna` | `docs/PLAN.md:21` |
| Planner Reasoning Effort | `medium` | `docs/PLAN.md:21` |
| Planner Scaffolding | `--disable shell_tool`, `--skip-git-repo-check`, `-s read-only` | `docs/PLAN.md:92` |
| Codex CLI Version | `0.153.4` | `docs/PLAN.md:114` |
| AppWorld Commit | `42b5bcf3cd334fee33f0c37c02070a9f5807add5` | `docs/PLAN.md:111` |
| Pricing Schedule | Luna: \$0.20 input / \$0.02 cached / \$1.20 output per 1M; GPU: \$2.50/h | `docs/PLAN.md:153-154` |
| Executor Model Backbone | `ibm-granite/granite-4.2-8b` (settled at HJ-1.5, agreement 0.256 on serving config) | `campaign/RUNS.md:636-660, 1275-1298` |
| LoRA Hyperparameters | $r = 64$, $\alpha = 128$, targets: `q,k,v,o,gate,up,down`, lr 1e-4 cosine | `docs/PLAN.md:140, 317` |
| Supervised Training Size | AppWorld `train` (90 tasks $\times$ 3 seeds, 230 trajectories in `sft_b_s123_p075.jsonl`) | `campaign/RUNS.md:819-829` |
| Test Split & Task Count | AppWorld `test_normal` (168 tasks) | `docs/PLAN.md:186` |
| Number of Seeds ($N$) | $N = 3$ | `campaign/results/hj7_power.json:502` |
| Non-Inferiority Margin ($\epsilon$) | $\epsilon = 7\text{ percentage points}$ | `campaign/results/hj7_power.json:502` |
| Bootstrap Resamples | 10,000 resamples (`SEED = 20260915`) | `scripts/setup/hj1_gate.py:28-29` |

### 7.2 Parameters Frozen at Milestone J9 (Prior to J10)

The following parameters remain open during dev milestones J4b–J8 and will be frozen at J9 strictly on **dev**:

1. **Sidekick ASK Operating Threshold ($\tau^*$)**:  
   - *Status*: Open during J8 sweep.  
   - *Selection Rule*: Threshold on $P(\text{ASK})$ / verifier score selected on the dev quality-displacement Pareto curve to maximize compute displacement while satisfying dev non-inferiority [OBSERVED campaign/RUNS.md:1354-1358].
2. **Router Decision Threshold ($\text{router } \tau^*$)**:  
   - *Status*: Open.  
   - *Selection Rule*: Calibrated on dev to match `sidekick` planner call count.
3. **`k_matched` Value**:  
   - *Status*: Open.  
   - *Selection Rule*: Frozen rule: $k \in \{3, 5, 10\}$ nearest to sidekick dev calls per episode (interpolating to $k=7$ on tie) [OBSERVED campaign/RUNS.md:1430-1432].
4. **ASK Template String & Label Rule**:  
   - *Status*: Pinned at J6/J8.

---

## 8. Threats to Validity

1. **Prompt Visibility Asymmetry in Preliminary Baselines**:  
   In the initial HJ-1 pilot, the executor prompt contained a defect where executed actions were omitted from the prompt transcript (`loop.py:647-651`), showing the executor only environment observations without its own generated code [OBSERVED campaign/RUNS.md:198-221]. This caused the 8B model to appear incapable of maintaining state. This baseline was re-measured under a corrected multi-turn prompt in HJ-1R (`hj1r_exec8b_20260916` TGC 0.0175, `hj1r_prompt_only_20260916` TGC 0.0439) [OBSERVED campaign/RUNS.md:445-446]. All subsequent training and evaluation strictly employ the unified prompt renderer (`protocols/prompts.render_executor_messages`) [OBSERVED docs/PLAN.md:338-340].
2. **Planner Call Truncation (Baseline Floor Effect)**:  
   In HJ-1, 10.5% of `planner_alone` episodes (12 of 114) were terminated by global limit constraints, with 11 of those 12 hitting `max_planner_calls = 25` [OBSERVED campaign/RUNS.md:77, 82-89]. Consequently, the observed `planner_alone` score of 0.684 on dev is an artificially truncated floor rather than an unconstrained upper bound. Caps were raised to 81 in HJ-2B where only 1 of 180 hit any limit [OBSERVED campaign/RUNS.md:408-411].
3. **Dev-Split Overfitting and Distribution Shift**:  
   All prompt templates, stop tokens, verifier thresholds, and operating points are tuned exclusively on the 57 dev tasks. Although `test_normal` is strictly held out, hyperparameter selection on dev introduces the risk of empirical distribution shift.
4. **Planner Benchmark Contamination**:  
   The knowledge cutoff for `gpt-5.6-luna` is 2026-02-16 [OBSERVED docs/PLAN.md:219], whereas AppWorld was published in 2024. Memorization of AppWorld task structures by the hosted planner is plausible. However, because all primary and secondary hypotheses evaluate paired contrasts against the identical planner instance on the exact same task instances, planner-side memorization bias is canceled across comparative arms [OBSERVED docs/PLAN.md:221-222].
5. **Verifier Sampling Bias on Timer-Tick States**:  
   The J6 counterfactual branch labels exist only at timer-tick states (steps 5, 10, 15, …) where `fixed_k` interventions occurred, while the router and the sidekick's runtime gate score *every* execution step. Consequently, the verifier is trained on a biased sample of states and its dev calibration may not transfer uniformly to arbitrary execution steps [OBSERVED /home/n12194778/.claude/jobs/91578989/tmp/brief_W6_docs.md:61-65, 88-89].
6. **Train-Split Intervention Optimism**:  
   The `sft_b` policy was trained on the same 90 train tasks from which the J4 correction data was collected. Therefore, train-split intervention statistics (e.g., J4 TGC 0.577, 2.71 interventions per episode) are optimistic; every headline capability and escalation claim must be evaluated strictly on dev or test [OBSERVED /home/n12194778/.claude/jobs/91578989/tmp/brief_W6_docs.md:63-65, campaign/RUNS.md:1082-1108, 1363-1368].
