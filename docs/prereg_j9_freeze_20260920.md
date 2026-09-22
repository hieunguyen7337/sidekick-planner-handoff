# Preregistration: J9 Dev Freeze for Milestone J10 Evaluation (2026-09-20)

**Status**: **FROZEN** — Written on dev evidence only, strictly before reading or evaluating any test split.  
**Date**: 2026-09-20  
**Study**: Sidekick Proof-of-Concept (IAES) — Milestone J9 Pre-Test Freeze  
**Repository**: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`  
**Prior Frozen Documents**: `docs/prereg_v1.md` (2026-09-16, frozen), `docs/prereg_b1_pilot.md` (2026-09-19, frozen)  

---

## 1. What This Document Is

This document is the milestone J9 preregistration freeze, recording the exact hypotheses, primary and secondary metrics, arm list, comparator assignments, and statistical decision rules for the final evaluation on the AppWorld `test_normal` split at milestone J10.

It is written **strictly on dev evidence** (specifically the J8 twelve-arm dev frontier evaluation, $n=114$ pairs across 57 tasks $\times$ 2 seeds [OBSERVED campaign/RUNS.md:2229-2239]) **before any test split has been read, loaded, or evaluated** [INFERRED].

This document explicitly records several major structural modifications from `docs/prereg_v1.md`. It documents:
1. What each change is,
2. The exact empirical justification from dev data that motivated the change,
3. The researcher-degrees-of-freedom risk introduced by post-dev adjustments,
4. The procedural mitigations in place, and
5. What empirical evidence on test would be required to show that each change was wrong.

---

## 2. Decision 1 — The Primary Claim Changes from H2b to F1

### 2.1 The Prior Registered Endpoint (H2b) and Why It Failed on Dev
In `docs/prereg_v1.md` §1.1, the primary endpoint was specified as **H2 (Adaptive Escalation Superiority — Conjunctive)**, containing clause H2b:
$$\text{sidekick} > \text{fixed\_k}(k_{\text{matched}}) \quad \text{and} \quad \text{sidekick} > \text{router\_seq}(\tau^*)$$
evaluated at matched planner calls [OBSERVED docs/prereg_v1.md:35-42, campaign/RUNS.md:1552-1554].

On dev ($n=114$), empirical evaluation at J8 demonstrated that **no learned gate discriminates between needed and needless intervention points**:
- On real decision points (the primary `scored` population, excluding post-episode padding), every gate's AUROC sits at or below chance:
  - `router_seq_tau03`: AUROC **0.5082** ($n=269$, 24 positives, 1,533 escalations) [OBSERVED campaign/RUNS.md:2292, campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]
  - `router_seq_tau05`: AUROC **0.4971** ($n=385$, 36 positives, 12 escalations) [OBSERVED campaign/RUNS.md:2293, campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]
  - `router_seq_tau07`: AUROC **0.5000** ($n=405$, 33 positives, 0 escalations) [OBSERVED campaign/RUNS.md:2294, campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]
  - `sidekick_tau03`: AUROC **0.4332** ($n=400$, 30 positives, 0 escalations) [OBSERVED campaign/RUNS.md:2295, campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]
  - `sidekick_tau05`: AUROC **0.3867** ($n=396$, 34 positives, 0 escalations) [OBSERVED campaign/RUNS.md:2296, campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]
  - `sidekick_tau07`: AUROC **0.4407** ($n=393$, 36 positives, 0 escalations) [OBSERVED campaign/RUNS.md:2297, campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]
- Across all 114 dev episodes, all three `sidekick` arms (`sidekick_tau03`, `sidekick_tau05`, `sidekick_tau07`) and `router_seq_tau07` escalated **zero times**, making exactly 114 planner calls (1.00 calls per episode, consisting solely of the initial cached plan) [OBSERVED campaign/RUNS.md:2252-2255, 2258, 2260].
- These arms are therefore behaviourally identical to `sft_plan` (which also makes 1.00 calls per episode) [OBSERVED campaign/RUNS.md:2245, 2258].

Testing for statistical superiority between a policy and itself is vacuous [INFERRED]. Superiority testing under H2b cannot be satisfied on this adapter (`sft_b_plus`) because the dynamic escalation channel never activates [INFERRED].

### 2.2 The Frozen Primary Claim (F1)
**Freeze**: The primary registered claim for J10 is **Claim F1 — Displacement of Hosted Planner Compute at Non-Inferior Quality** [INFERRED].

Claim F1 evaluates whether the specialised plan-following policy (`sft_plan` / `sidekick_tau05`) achieves quality non-inferior to the nearest fixed review schedule while using strictly fewer planner calls than standard periodic review (`fixed_k_5`) [INFERRED].

Formally, Claim F1 requires both of the following conditions to hold simultaneously on `test_normal` ($N=504$ paired runs, task-clustered bootstrap):
1. **Quality Non-Inferiority**:
   $$\text{ci95\_pp}[0] \ge -7.00\text{ percentage points vs } \text{fixed\_k}(k_{\text{matched}})$$
   where $k_{\text{matched}} = 10$ for 1.00-call policies [OBSERVED campaign/RUNS.md:2264, 2269-2274].
2. **Cost Reduction**:
   $$\text{ci95}[1] < 0.00\text{ planner calls/episode vs } \text{fixed\_k}(5)$$
   [OBSERVED campaign/RUNS.md:2264].

### 2.3 Retention of H2b as a Pre-Registered Negative Result
H2b is **retained as a pre-registered negative result** [INFERRED]. It is not dropped, hidden, or quietly demoted [INFERRED].

The final report will explicitly publish H2b alongside F1, presenting the dev calibration evidence (scored AUROC $\le 0.50$, zero live escalations) and the test evaluation numbers, explaining that the hypothesis failed on dev because the learned gate was unable to discriminate outcome-critical intervention points [INFERRED].

### 2.4 Falsification of the Change
What evidence on test would demonstrate that changing from H2b to F1 was wrong:
- If on `test_normal`, the `sidekick` self-gate or sequential router exhibits non-chance discrimination (e.g. scored AUROC $> 0.60$ with a 95% CI strictly excluding 0.50) and initiates selective escalations that produce a statistically significant quality improvement over `sft_plan` ($\Delta > 0$, CI excluding 0) at matched planner calls [INFERRED].

---

## 3. Decision 2 — The Primary Metric Changes from TGC to Goal-Pass Rate

### 3.1 Description of the Change
In `docs/prereg_v1.md` §3.1, the primary evaluation metric was Task Goal Completion ($\text{TGC} \in \{0.0, 1.0\}$) [OBSERVED docs/prereg_v1.md:106].

**Freeze**: The primary metric for Claim F1 is changed to **`goal_pass_rate`** (the fraction of programmatic task criteria satisfied, $\text{GPR} \in [0.0, 1.0]$) [INFERRED]. **TGC is retained unconditionally as the secondary quality metric** and will be reported for every arm and contrast [INFERRED].

### 3.2 Empirical Justification: Replicate Noise on Dev
The change is justified by direct measurement of stochastic replicate noise on dev across identically behaving arms [INFERRED]:
- The three configurations `configs/hj8_sidekick_tau03.yaml`, `configs/hj8_sidekick_tau05.yaml`, and `configs/hj8_sidekick_tau07.yaml` differ solely in `verifier.threshold` ($0.3 / 0.5 / 0.7$) [OBSERVED campaign/RUNS.md:2325].
- Because all three arms escalated zero times, the verifier threshold had zero causal impact on execution [OBSERVED campaign/RUNS.md:2325-2326]. Operating at `temperature: 0.7`, these three arms constitute three independent stochastic replicates of the same underlying policy [OBSERVED campaign/RUNS.md:2325-2326].
- Across these three replicates on dev ($n=114$ each):
  - **TGC** spans **3.51 percentage points** (0.3596 for $\tau=0.3$, 0.3860 for $\tau=0.5$, 0.3947 for $\tau=0.7$) [OBSERVED campaign/RUNS.md:2253-2255, 2326].
  - **`goal_pass_rate`** spans **0.94 percentage points** (0.6694 for $\tau=0.3$, 0.6694 for $\tau=0.5$, 0.6601 for $\tau=0.7$) [OBSERVED campaign/RUNS.md:2253-2255, 2327].
- The pre-registered non-inferiority margin ($\epsilon = 7\text{ pp}$) is only twice TGC's replicate noise floor ($3.5\text{ pp}$), making a TGC-based non-inferiority test on small samples close to uninformative [OBSERVED campaign/RUNS.md:2329]. `goal_pass_rate` is roughly four times steadier than TGC across identical policy runs [OBSERVED campaign/RUNS.md:2329].

### 3.3 Disclosure of Risk and Methodological Mitigations
**Risk**: Selecting the primary metric after observing dev results is a researcher degree of freedom that could introduce post-hoc selection bias [INFERRED].

**Mitigations**:
1. The decision is made and frozen on dev data only, before unblinding any test data [INFERRED].
2. The decision is justified by a variance property (measurement stability across known-identical replicates) rather than by selecting whichever metric yielded the largest effect size [INFERRED].
3. Both `goal_pass_rate` and TGC are reported unconditionally for all arms, contrasts, and hypotheses [INFERRED].
4. The dev numbers for both metrics are quoted below so readers can assess whether the choice was biased toward flattering the proposed system [INFERRED].

### 3.4 Flattering Comparison on Dev
To assess whether `goal_pass_rate` or TGC presents a more flattering picture of the proposed method:
- **Baseline separation (`sft_plan` vs `executor_alone`)**: TGC presents the more flattering picture of the plan-following capability gap:
  - TGC gap: **+27.19 pp**, 95% CI **[16.67, 37.72]** [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "contrasts" → "tgc_all_executor_alone_minus_sft_plan", sign-flipped].
  - `goal_pass_rate` gap: **+17.11 pp**, 95% CI **[10.36, 23.74]** [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "contrasts" → "goal_pass_all_executor_alone_minus_sft_plan", sign-flipped].
- **Non-inferiority against fixed schedule (`sidekick_tau05` vs `fixed_k_10`)**: `goal_pass_rate` presents the more flattering picture for clearing the $-7\text{ pp}$ non-inferiority bound:
  - TGC contrast: difference is **0.00 pp**, but the 95% CI is **[-8.77, +9.65]** [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "contrasts" → "tgc_all_fixed_k_10_minus_sidekick_tau05", sign-flipped]. Because the lower bound ($-8.77\text{ pp}$) falls below $-7.00\text{ pp}$, the test fails on dev [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "contrasts" → "tgc_all_fixed_k_10_minus_sidekick_tau05", sign-flipped].
  - `goal_pass_rate` contrast: difference is **+2.47 pp** (0.6694 vs 0.6447 [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: keys "arms" → "sidekick_tau05" → "goal_pass_all" and "fixed_k_10" → "goal_pass_all"]), with a 95% CI of **[-4.49, +9.85]** [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "contrasts" → "goal_pass_all_fixed_k_10_minus_sidekick_tau05", sign-flipped], easily clearing the $-7.00\text{ pp}$ non-inferiority threshold.
- Thus, TGC yields a more flattering absolute effect size for executor capability, while `goal_pass_rate` yields a CI half-width of **7.17 pp** versus TGC's **9.21 pp**, a narrowing of about **1.28×** [INFERRED]. This is a much smaller ratio than the replicate-noise ratio of **3.5 pp to 0.9 pp** might suggest, so the case for the metric switch rests on replicate stability rather than on a large gain in interval width [INFERRED].

---

## 4. Decision 3 — The Non-Inferiority Margin (7 pp) and "Matched Calls" Formulation

### 4.1 The Non-Inferiority Margin ($\epsilon = 7\text{ pp}$) Stays Frozen
The non-inferiority margin is **not** altered. It remains fixed at:
$$\epsilon = 7.00\text{ percentage points}$$
[OBSERVED docs/prereg_v1.md:37, 232, campaign/RUNS.md:2264].

Changing both the primary metric and the numerical margin after observing dev results would completely unanchor the preregistration [INFERRED].

### 4.2 Power and Resolution at J10 Sample Size
On dev ($n=114$, 57 tasks $\times$ 2 seeds), paired bootstrap 95% CI half-widths were roughly 9–11 pp [OBSERVED campaign/RUNS.md:2268-2274, 2281]:
- `sidekick_tau05` vs `fixed_k_10`: CI [-8.77, +9.65] (half-width $\approx 9.21\text{ pp}$) [OBSERVED campaign/RUNS.md:2272]
- `oracle_escalation` vs `fixed_k_10`: CI [-10.53, +9.65] (half-width $\approx 10.09\text{ pp}$) [OBSERVED campaign/RUNS.md:2281]
- `router_seq_tau03` vs `fixed_k_3`: CI [-14.91, +9.65] (half-width $\approx 12.28\text{ pp}$) [OBSERVED campaign/RUNS.md:2268]

At J10 ($N=504$, 168 tasks $\times$ 3 seeds), the sample size increases by $504 / 114 \approx 4.42\times$. The standard error scales as $1/\sqrt{4.42} \approx 1/2.10$, narrowing CI half-widths by a factor of $\approx 2.1\times$ to approximately **4.0–5.0 pp** [INFERRED]. This brings the uncertainty interval inside the 7 pp margin, ensuring that non-inferiority is statistically resolvable on test where it was unresolvable on dev [INFERRED].

### 4.3 The "Matched Calls" Limitation
The preregistration machinery identifies $k_{\text{matched}}$ as the fixed review arm whose calls per episode is nearest to the evaluated policy [OBSERVED docs/prereg_v1.md:14, 83, campaign/RUNS.md:1430-1432].

On dev, policies making 1.00 calls per episode (`sft_plan`, `sidekick_tau05`) are paired with `fixed_k_10`, which makes **2.75 calls per episode** (314 calls / 114 episodes) [OBSERVED campaign/RUNS.md:2248, 2258].

**Limitation**: Comparing a 1.00-call policy against a 2.75-call fixed schedule is **not a cost-matched comparison**; it is simply the closest discrete arm available in the pre-registered grid [INFERRED]. The scientific delivery of F1 is a position on the empirical cost-quality Pareto frontier, not a claim of cost-matched equivalence [INFERRED].

---

## 5. Decision 4 — The J10 Evaluation Arm List

### 5.1 Frozen J10 System Arms
Milestone J10 evaluates **5 arms** across AppWorld `test_normal` (168 tasks $\times$ 3 seeds = 504 episodes per arm; 2,520 total episode runs):

| Arm | Model & Scaffolding | Seeds | Role & Empirical Justification |
|---|---|:---:|---|
| **`executor_alone`** | Base `granite-4.2-8b`, no planner, zero-shot | 3 | Anchors the capability floor. Dev TGC is 0.1316 vs 0.4035 for `sft_plan` (+27.19 pp gap) [OBSERVED campaign/RUNS.md:2128, 2244-2245, 2333]. |
| **`sft_plan`** | `sft_b_plus` adapter, initial cached plan (1 call/ep), no escalation | 3 | Core reference policy; represents the quality benchmark for Claim F1 [OBSERVED campaign/RUNS.md:2245]. |
| **`fixed_k_10`** | `sft_b_plus` adapter, periodic planner review every 10 steps | 3 | $k_{\text{matched}}$ comparator for 1.00-call policies (2.75 calls/ep on dev) [OBSERVED campaign/RUNS.md:2248, 2258, 2269-2274]. |
| **`fixed_k_5`** | `sft_b_plus` adapter, periodic planner review every 5 steps | 3 | F1 cost comparator, fixed by F1 decision rule (4.96 calls/ep on dev) [OBSERVED campaign/RUNS.md:2247, 2258, 2264]. |
| **`sidekick_tau05`** | `sft_b_plus` adapter, verifier self-gate at $\tau=0.5$ | 3 | Pre-registered check that the self-gate remains degenerate on test; costs 1.00 calls/ep (cached plan), adding negligible quota cost [OBSERVED campaign/RUNS.md:2254, 2258, 2260]. |

### 5.2 Dropped Arms and Explicit Rationales
The following arms from previous milestones or proposals are excluded from J10:

1. **`planner_alone` (`gpt-5.6-luna`)**:
   - *Spend*: 504 episodes $\times \approx 20$ calls/ep $\approx 10,000$ hosted planner calls (out of an ~11,500 total available quota).
   - *Role*: Served solely secondary hypothesis H1.
   - *Rationale for dropping*: Dropped to protect quota budget for core frontier comparisons [INFERRED]. H1 will rest on dev measurements and earlier HJ-1/HJ-2B runs; this is acknowledged as a deliberate weakening of the H1 claim on test [INFERRED].
2. **`sidekick_tau03`, `sidekick_tau07`, `router_seq_tau07`**:
   - *Rationale for dropping*: All three arms were behaviourally identical to `sidekick_tau05` on dev (0 escalations, 1.00 calls per episode) [OBSERVED campaign/RUNS.md:2252-2255, 2325]. Running redundant degenerate threshold variants on test would consume compute to evaluate the same policy repeatedly [INFERRED].
3. **`router_seq_tau03`**:
   - *Rationale for dropping*: On dev, this arm made **15.39 planner calls per episode** (1,754 total calls) and consumed **203,504,742 planner tokens** ($7.8\times$ `fixed_k_3`) while achieving the worst quality of any active arm (TGC 0.2719, 21 crashes) [OBSERVED campaign/RUNS.md:2250, 2258, 2260]. Running it on test would dominate the campaign's dollar and quota budget to confirm an already established failure mode [INFERRED].
4. **`oracle_escalation`**:
   - *Rationale for dropping*: **Cannot be run on test by construction** [INFERRED]. Oracle escalation decisions are derived from J6 counterfactual branch rollouts on dev; no test-split counterfactual branch labels exist or can be generated without violating split isolation [INFERRED]. Oracle headroom (Claim F2) is therefore strictly a **dev-only** finding [INFERRED].

---

## 6. Decision 5 — Claims Supported by Dev Evidence

The scientific claims supported by the dev frontier evidence are ordered as follows:

1. **Specialised Plan Following is Highly Effective**:  
   A small 8B executor specialised to a frozen hosted planner follows initial plans with high fidelity, achieving TGC **0.4035** (`sft_plan`) versus **0.1316** (`executor_alone`) — an increase of **+27.19 pp** (95% CI **[16.67, 37.72]**) and `goal_pass_rate` **0.7000** vs **0.5289** (**+17.11 pp**, 95% CI **[10.36, 23.74]**) [OBSERVED campaign/RUNS.md:2128-2129, 2244-2245, 2333]. This is the single largest effect measured in the campaign [OBSERVED campaign/RUNS.md:2333].
2. **Fixed Review Schedules Waste Significant Compute**:  
   Periodic intervention schedules allocate reviews indiscriminately: Gate B measurements showed that 232 of 734 scheduled reviews fired on episodes that would have succeeded without intervention ($f_{\text{train}} = 11.31\%$ needed at 2 seeds, $6.30\%$ at 4 seeds) [OBSERVED campaign/RUNS.md:1779, 1834]. This waste is corroborated live by `router_seq_tau03`, which spent 203.5M planner tokens and 15.39 calls/ep only to achieve TGC 0.2719 [OBSERVED campaign/RUNS.md:2250, 2258, 2260].
3. **Adaptive Allocation Shows Potential on Dev**:  
   On dev, `oracle_escalation` matched `fixed_k_10` quality (TGC difference **−0.88 pp**, 95% CI **[−10.53, +9.65]**) while requiring **47% of the calls** (1.30 vs 2.75 calls/ep) and **14% of the planner tokens** (1,496,956 vs 10,329,506 total tokens) [OBSERVED campaign/RUNS.md:2248-2249, 2258, 2260, 2281-2284]. This demonstrates equal quality at substantially lower spend, though not statistical superiority [INFERRED].
4. **Learned Gating Does Not Yet Function**:  
   Neither the linear verifier head nor the sequential router discriminates outcome-critical intervention points on real decision steps (scored AUROCs sit in the range 0.3867–0.5082) [OBSERVED campaign/RUNS.md:2291-2299, 2316]. The executor self-gate's $p_{\text{ask}}$ never exceeds 0.0347 across any arm on `sft_b_plus` against operating thresholds of 0.3, 0.5, and 0.7 [OBSERVED campaign/RUNS.md:2306-2309, 2317]. This is reported as an explicit negative result [INFERRED].

**Core Paper Claim**: The thesis sentence — displacing hosted planner compute at non-inferior quality — is currently carried by the plan-following capability of the specialised executor rather than by dynamic learned gating [INFERRED]. This represents a narrower, more modest result than anticipated in `prereg_v1` [INFERRED].

---

## 7. Decision 6 — B1 Counterfactual Pilot and H4 Out of Scope

1. **B1 Pilot Independence**: The B1 clean-counterfactual pilot (PBS job `25560367`) is currently executing on HPC [OBSERVED brief_J9_freeze.md:6]. Its design, execution, and analysis are governed strictly by the frozen document `docs/prereg_b1_pilot.md` [OBSERVED docs/prereg_b1_pilot.md:1-10].
2. **H4 Scope**: Secondary hypothesis H4 (`sidekick(sft_c)` vs `router_seq`) and adapter training for `sft_c` remain conditional on B1 demonstrating trainable label signal under `suppress_next` [OBSERVED docs/prereg_v1.md:50-51, docs/prereg_b1_pilot.md:10].
3. **Current Adapter Status**: `sft_c` was never trained because initial J6 train ASK labels were statistically indistinguishable from permutation noise ($p = 0.7124$) [OBSERVED campaign/RUNS.md:2039, 2044, 2225].
4. **No Pre-Judgement**: This freeze does not pre-judge B1's outcome or freeze any parameters for H4 [INFERRED].

---

## 8. Decision 7 — Pre-J10 Sign-Off Gate and Open Questions

### 8.1 Explicit Gate Statement
**J10 has NOT been submitted, and the AppWorld `test_normal` split remains unread and unblinded** [INFERRED].

Submitting J10 requires explicit user authorization because it will spend approximately 1,000–1,500 live planner calls and consumes the project's single, non-repeatable test evaluation read [INFERRED].

### 8.2 Open Questions for Sign-Off
The following four specific items are flagged for final user review prior to launching J10:

1. **Random-Escalation Baseline**: Whether to include a synthetic `random_escalation` baseline (escalating at random steps to match `fixed_k_10` call volume) to prove that periodic reviews provide structured guidance beyond arbitrary interruption [INFERRED].
2. **Degenerate Arm Allocation**: Whether allocating test compute (504 runs) to `sidekick_tau05` is worthwhile given its known zero-escalation behaviour on dev, or whether `sft_plan` alone is sufficient to represent 1.00-call performance [INFERRED].
3. **Latency Reporting Limitation**: System execution latency was not accumulated in the run ledger and therefore cannot be reported alongside token and dollar expenditures [INFERRED].
4. **B1 Pilot Timing**: Whether J10 submission should be held until B1 finishes reporting, or if J10 should proceed immediately based on the frozen `sft_b_plus` adapter [INFERRED].

---

## 9. Exact Statistical Protocol for Milestone J10

### 9.1 Evaluation Dataset
- Split: AppWorld **`test_normal`** (168 tasks across 56 scenarios) [OBSERVED docs/prereg_v1.md:69].
- Seeds: $N = 3$ random seeds ($s \in \{1, 2, 3\}$) [OBSERVED docs/prereg_v1.md:76, 231].
- Total runs per arm: $168 \times 3 = 504$ episodes [OBSERVED docs/prereg_v1.md:76].

### 9.2 Bootstrap Specification
- Procedure: Task-clustered paired percentile bootstrap implemented in `scripts/setup/hj1_gate.py` (`paired_diff(resample="task")`) [OBSERVED campaign/RUNS.md:2125-2126].
- Resample Unit: **Task** (clusters of 3 seeds resampled together; 168 clusters) [OBSERVED campaign/RUNS.md:1578, 2235].
- Resamples: 10,000 bootstrap iterations [OBSERVED campaign/RUNS.md:2126].
- Random Seed: Fixed at `SEED = 20260915` [OBSERVED campaign/RUNS.md:2126].

### 9.3 Statistical Decision Rules (Claim F1)
1. Compute task-level paired difference in `goal_pass_rate`:
   $$\Delta_i = \overline{\text{GPR}}_{i, \text{sft\_plan}} - \overline{\text{GPR}}_{i, \text{fixed\_k\_10}}$$
2. Compute 95% bootstrap CI $[\text{ci95\_pp}[0], \text{ci95\_pp}[1]]$.
3. Evaluate:
   - **Quality Rule**: $\text{ci95\_pp}[0] \ge -7.00\text{ percentage points}$
   - **Cost Rule**: $\text{ci95}[1] < 0.00\text{ planner calls/episode vs } \text{fixed\_k\_5}$
4. F1 is confirmed if and only if both conditions hold simultaneously [OBSERVED campaign/RUNS.md:2264].

---

## 10. Research Hygiene and Protocol Commitments

1. **Zero Exclusions**: Every one of the $504 \times 5 = 2,520$ initialized test episodes is included in all metric denominators. No run may be pruned, filtered, or excluded post-hoc [OBSERVED docs/prereg_v1.md:191-192].
2. **Error Accounting**: Runs ending in `limit`, `timeout`, `crash`, `parse_error`, or `api_error` score $0.0$ for both `goal_pass_rate` and TGC in the headline population [OBSERVED docs/prereg_v1.md:193-194, campaign/RUNS.md:2238]. Survivor contrasts will be reported alongside for transparent accounting [OBSERVED campaign/RUNS.md:2238].
3. **Single Evaluation Commitment**: Milestone J10 will be evaluated strictly once. No retuning, prompt modification, threshold re-selection, or re-running is permitted following test evaluation [OBSERVED docs/prereg_v1.md:209-211].

---

## 11. Amendment Record (appended 2026-09-24; nothing above this line is edited)

**Amendment A1** — `docs/prereg_j10_amendment_20260924.md`.

A1 supersedes the J10 primary claim (§4, Claim F1 selective escalation), the five-arm list (§5.1), the
drop of `planner_alone` (§5.2 item 1) and the three-seed design (§9.1). It reinstates `planner_alone` at
cap 81 as both ceiling and prefix trajectory source, registers a nine-arm J10 whose primary is a channel
contrast (action prefix versus full-context prose advice at adverse budget), and fixes two seeds.

The J9 gate at §8.1 was satisfied on 2026-09-24: the user authorised the test read itself and signed off
§8.1 explicitly. A1 was written before any `test_normal` file was read.

§10 item 3 above — the single-evaluation commitment — is **retained in full** and restated in A1 §8, which
additionally registers what may and may not happen if a defect is found after the read.

Do not plan a J10 run from §5.1 of this document. Read A1 first.
