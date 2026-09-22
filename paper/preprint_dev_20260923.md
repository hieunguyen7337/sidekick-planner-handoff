---
title: "Steering Local Agentic Executors via Action Prefixes: Channel Dominance, Prefix Depth, and Mechanism on the AppWorld Benchmark"
date: "2026-09-23"
author: "Sidekick Research Group"
abstract: |
  We examine compute allocation when pairing a compact local model (IBM Granite 4.2 8B) with a strong hosted planner (GPT-5.6 Luna) on complex interactive environments. Across paired evaluations on the AppWorld dev benchmark (57 tasks, $n = 114$ paired episodes across 19 scenario clusters), we establish three primary empirical findings. First, spending hosted budget as executable action prefixes strictly dominates spending it as natural-language prose advice: at matched triggers ($k = 10$) and full context, action execution outperforms prose critique by +6.69 percentage points in goal pass rate (95% scenario-clustered bootstrap interval [+1.29, +13.48], task-clustered [+1.47, +12.35]) while reducing non-cached tokens (41,464 vs. 49,819), provider dollars ($0.004820 vs. $0.005494), and hosted calls (2.316 vs. 2.465) per episode. Second, handoff quality rises with prefix depth across a span—gaining +10.21 pp on goal pass rate ([+2.60, +18.20] scenario, [+3.80, +16.81] task) and +16.67 pp on Total Goal Criterion (TGC; [+5.26, +28.07] scenario, [+7.02, +26.32] task) between depths $m = 6$ and $m = 9$ zero-shot. However, Holm correction yields adjusted $p = 1.0$ across all eight adjacent transitions, and segmented regression yields $\tau = 8$ with CI [4, 9] (failing registered threshold test S3), confirming a continuous span gain rather than a discrete threshold jump. Third, environment resets demonstrate that this benefit is primarily informational: rendering 9 planner actions as plain text into a fresh environment is statistically indistinguishable from physical execution (+1.84 pp tailored scenario [−2.67, +6.76]; +1.69 pp untailored scenario [−4.16, +7.11]), recovering 97% of the untailored execution gain over the single-plan floor. All evaluations are conducted strictly on the AppWorld development split.
---

# Steering Local Agentic Executors via Action Prefixes: Channel Dominance, Prefix Depth, and Mechanism on the AppWorld Benchmark

## 1. Introduction

Autonomous language agents in digital environments must navigate long horizons, discover multi-application APIs, and maintain coherent state. Frontier foundation models exhibit high planning competence but remain expensive, latency-constrained, and privacy-sensitive to run as interactive loops over many steps. Compact local models (e.g., 8B open weights) provide high throughput and low marginal cost, yet suffer from error compounding, syntax fragility, and poor exploratory discovery when deployed autonomously.

This tension motivates hybrid systems pairing a small local executor with a strong hosted planner. The core question is: **through which communication channel, and at what depth of intervention, should the hosted budget be spent?** Existing approaches typically configure the hosted model as an asynchronous critic or upfront planner emitting natural-language advice or stepwise plans.

In this work, we demonstrate that natural-language advice is fundamentally the wrong medium for steering local executors. Across extensive paired evaluations on the AppWorld benchmark, spending hosted budget as concrete, executable **action prefixes** strictly dominates natural-language critique in task quality, token consumption, provider expenditure, and latency.

Our contributions are grounded in an exact pre-registered claims ledger (`docs/claims_ledger.md`):

- **Channel Dominance at Matched Trigger (CHAN-C1-02, COST-01):** At matched triggers ($k = 10$) and full transcript context, direct action takeover outperforms prose advice by +6.69 pp on `goal_pass` (scenario 95% CI [+1.29, +13.48], task [+1.47, +12.35]) while strictly dominating advice across non-cached tokens (41,464 vs. 49,819), provider dollars ($0.004820 vs. $0.005494), and hosted calls (2.316 vs. 2.465).
- **Equivalence of Live Takeover and Oracle Replay (CHAN-C1-03):** A live takeover loop calling the planner online is statistically indistinguishable at $n = 114$ from replayed oracle prefix trajectories at depth $m = 9$ (+1.55 pp, scenario [−3.46, +7.04], task [−4.41, +8.01]) and $m = 11$ (−0.91 pp, scenario [−6.74, +5.94], task [−6.90, +5.16]).
- **Span-Based Scaling without Stepwise Discontinuities (MULT-01, F1-RESULT-01..04, SHAPE-10):** Handoff quality increases with prefix depth (+10.21 pp `goal_pass` [+2.60, +18.20] scenario; +16.67 pp TGC [+5.26, +28.07] scenario from $m = 6$ to $m = 9$ zero-shot). However, Holm correction yields adjusted $p = 1.0$ across all eight adjacent transitions, and segmented regression yields $\tau = 8$ with CI [4, 9] (failing registered threshold test S3), confirming a continuous gain across spans rather than a discrete threshold jump.
- **Informational Mechanism over Physical State (NARR-01, NARR-02):** Replaying 9 planner actions as plain text into a fresh environment is statistically indistinguishable from physical execution (+1.84 pp tailored scenario [−2.67, +6.76]; +1.69 pp untailored scenario [−4.16, +7.11]), recovering 97% of the untailored execution gain over the one-plan floor.
- **Substitutability of Depth and Receiver Specialization (TAILOR-07, HF-02, MECH-07):** Deep prefixes eliminate the need for executor fine-tuning: receiver gaps decay with depth (−4.12 pp at $m = 6$, −0.06 pp at $m = 9$, +2.46 pp at $m = 11$). Furthermore, pre-registered handoff-suffix adapter training (C3) flattens the depth curve without extending the upper ceiling.
- **Second-Family Replication (QWEN-04, QWEN-03):** The monotonic depth effect replicates within zero-shot `Qwen/Qwen3-8B` prefix arms (`goal_pass` 0.4491 at $m = 6$ to 0.7306 at $m = 11$, TGC 0.1491 to 0.4912), while format censuses establish that its baseline floor (0.2481) reflects terminal token non-emission rather than task competence.

---

## 2. Experimental Setup

### 2.1 Benchmark and Interaction Loop

We evaluate all methods on AppWorld, a synthetic environment comprising nine day-to-day applications accessed via RESTful APIs. Agents generate and execute interactive Python code that inspects state, handles multi-user permissions, and mutates state across applications.

Following `docs/limitations_external_20260923.md`, our experiments employ a minimal interaction harness designed to isolate the steering channel without scaffold-induced confounds. The agent emits Python code blocks executed against the live AppWorld environment; standard outputs, errors, and return values append to the episode transcript.

### 2.2 Models and Roles

- **Hosted Planner:** We utilize `gpt-5.6-luna` accessed through hosted API endpoints, configured strictly with `model_reasoning_effort: medium` and frozen prompt hashes. The planner serves as the source for initial plans, live advice critiques, live action takeovers, and replayed prefix trajectories.
- **Local Executors:** Primary local executor is `ibm-granite/granite-4.2-8b`, evaluated under three configurations: (1) **untailored zero-shot** (base weights with null LoRA adapter); (2) **generally-tailored** (`sft_b_plus`, resolving to `sft_b_plus_iaware_granite8b`, trained on interaction recovery data); and (3) **handoff-suffix trained** (`sft_b_plus_handoff_granite8b`, trained on 615 trajectory suffixes aligned to handoff cut points; DATA-01, HF-TRAIN-01). As a secondary model family, we evaluate zero-shot `Qwen/Qwen3-8B`.

### 2.3 Steering Channels and Handoff Paradigms

We compare four interaction paradigms:
1. **Autonomous Floor:** The local executor operates alone from step 0 with no planner intervention (`executor_alone`).
2. **One-Plan Floor (`plan_only` / `sft_plan`):** The planner generates an initial natural-language plan at step 0; the executor operates autonomously thereafter.
3. **Prose Advice Channel (`advise_fixed_k`):** The executor runs autonomously, but every $k$ steps the planner inspects the transcript and injects a prose critique. We evaluate both context-starved variants (8-line window) and full-context controls (`advise_fixed_k_10_fullctx`, passing the complete transcript).
4. **Action Prefix & Takeover Channel:** The planner executes environment actions directly. In the **replayed prefix** paradigm (`prefix_m`), the first $m$ actions from a recorded planner trajectory are replayed into the environment, followed by a post-prefix terminal guard silencer if the task already finished (GUARD-01). In the **live takeover** paradigm (`takeover_fixed_k_10`), the planner is invoked online at step $k = 10$, emits an executable action executed directly in the environment, and returns control to the executor.

### 2.4 Metrics, Dataset Scope, and Statistical Estimation

- **Metrics:** We report `goal_pass_rate` (`goal_pass`, fraction of required task assertions satisfied) and **Total Goal Criterion (TGC)**, a strict binary metric requiring 100% of goal requirements and state verifications to pass.
- **Dataset Scope:** All evaluations are conducted on the AppWorld **dev** split, consisting of 57 tasks evaluated across 2 seeds ($n = 114$ paired episodes clustered into 19 scenario groups; 3 multi-party synchronization tasks excluded at environment setup; `docs/limitations_external_20260923.md`).
- **Bootstrap Protocol:** Confidence intervals are computed using 10,000 paired percentile bootstrap draws, reporting both **scenario-clustered** (primary) and **task-clustered** 95% confidence intervals.
- **Non-Inferiority Margin:** For non-inferiority hypotheses against planner ceilings, we adopt the pre-registered margin of $\delta = 7.00$ percentage points (pp).

---

## 3. The Action Channel Beats the Advice Channel at Matched Trigger

To resolve whether hosted budget is more effectively spent as supervisory prose or direct environment actions, we examine pre-registered primary channel contrast C1 (CHAN-C1-00, CHAN-C1-02). We compare live action takeover (`takeover_fixed_k_10`) against full-context prose advice (`advise_fixed_k_10_fullctx`). Both arms are matched: identical trigger condition ($k = 10$), same cached initial plan, identical executor model and adapter, and both supply the complete episode transcript to the planner (CHAN-C1-00).

The action channel decisively outperforms prose advice. On `goal_pass`, `takeover_fixed_k_10` achieves 0.8007 compared to 0.7339 for `advise_fixed_k_10_fullctx` (TGC 0.5175 vs. 0.4386). The paired difference is **+6.69 pp**, with a 95% scenario-clustered CI of **[+1.29, +13.48]** and task-clustered CI of **[+1.47, +12.35]** (CHAN-C1-02). Because both intervals strictly exclude zero under 10,000 bootstrap draws, the superiority of the action channel is established at the pre-registered trigger. Against the one-plan floor (`sft_plan`, 0.7181), takeover provides a significant gain of **+8.26 pp [+3.84, +13.11]**, whereas advice provides only **+1.57 pp [−2.91, +5.91]**, failing to show a resolvable difference from the floor.

A central methodological concern regarding prefix handoffs is that replaying recorded oracle trajectories cannot be deployed live without ground-truth traces. We address this directly via CHAN-C1-03 by evaluating online live takeover against oracle replayed prefixes. Against oracle prefix replay at depth $m = 9$ (0.7852) and depth $m = 11$ (0.8098), live takeover (0.8007) yields paired differences of **+1.55 pp** (scenario [−3.46, +7.04], task [−4.41, +8.01]) and **−0.91 pp** (scenario [−6.74, +5.94], task [−6.90, +5.16]) respectively. Crucially, because both confidence intervals span zero (widths ±6–7 pp), we conclude that **we cannot distinguish live takeover from oracle prefix replay at $n = 114$**. We do not claim mathematical equality, but rather that live execution achieves parity within experimental resolution, validating deployability.

Finally, we confirm that the poor performance of prose advice is not an artifact of critic context starvation (ADV-FC-01, ADV-FC-02). Evaluating full-transcript control (`advise_fixed_k_10_fullctx`, 0.7339) against the context-starved baseline (`advise_fixed_k_10`, 0.6964) yields a non-significant difference of **+3.74 pp** (scenario [−1.39, +9.13], task [−1.72, +9.53]). Furthermore, full-context advice exceeds the matched adapter plan floor (`hj8_sft_plan_bplus_20260921iaware`, 0.7181) by only **+1.57 pp** (scenario [−2.91, +5.91], task [−3.04, +6.30]; TGC +4.39 pp [−4.39, +12.28]). Advice remains indistinguishable from the floor under both truncated and complete reviewer contexts (Figure F2).

---

## 4. Economic Dominance and Multi-Currency Cost Frontiers

We evaluate whether supervisory critique is cheaper across three cost currencies: non-cached input/output tokens, provider dollars billed under published price cards, and total hosted API calls (COST-01, COST-02, COST-03).

On the registered matched-trigger pair, the action channel **strictly dominates** the advice channel across all three axes simultaneously (COST-01). Comparing `takeover_fixed_k_10` to `advise_fixed_k_10_fullctx`:
- **Non-Cached Tokens:** 41,464 tokens/episode for takeover vs. 49,819 tokens/episode for advice (saves 8,355 tokens).
- **Provider Expenditure:** $0.004820/episode for takeover vs. $0.005494/episode for advice (saves $0.000674).
- **Hosted Calls:** 2.316 calls/episode for takeover vs. 2.465 calls/episode for advice (saves 0.149 calls).

Because `takeover_fixed_k_10` achieves +6.69 pp higher `goal_pass` while requiring fewer tokens, fewer dollars, and fewer API calls, there is no cost axis on which prose advice buys back its quality deficit.

```
Table 1: Unified Cost and Quality Frontier on AppWorld Dev Split (n = 114).
All usage records report explicit cached-input splits (n_usage_without_cache_split = 0; COST-01).
--------------------------------------------------------------------------------------------------
Arm / System Configuration        Goal Pass    TGC     Non-Cached Tokens   USD / Ep.   Calls / Ep.
--------------------------------------------------------------------------------------------------
executor_alone (granite 8B)        0.5289    0.1316                   0   $0.000000          0.00
plan_only (sft_plan iaware)        0.7181    0.3947              23,906   $0.003015          1.00
advise_fixed_k_10 (starved ctx)    0.6964    0.4123              43,823   $0.004386          2.42
advise_fixed_k_10_fullctx          0.7339    0.4386              49,819   $0.005494          2.46
takeover_fixed_k_10 (action C1)    0.8007    0.5175              41,464   $0.004820          2.32
advise_fixed_k_3 (starved ctx)     0.7012    0.4561             204,500   $0.012203          6.82
prefix_m6 (action prefix)          0.7237    0.4298             221,043   $0.016268          6.98
prefix_m9 (action prefix)          0.7852    0.5614             357,448   $0.022740          9.77
prefix_m11 (action prefix)         0.8098    0.6053             443,361   $0.026475         11.25
ceiling_cap25 (planner alone)      0.8284    0.6842             684,453   $0.035479         14.43
ceiling_cap81 (planner alone)      0.7637    0.5702           1,160,215   $0.048208         17.35
--------------------------------------------------------------------------------------------------
```

Cost ordering is highly consistent across arms (COST-02). The only observed ordering flip occurs between `advise_k10_starved` and `takeover_k10`: takeover requires fewer non-cached tokens (41,464 vs. 43,823) and calls (2.32 vs. 2.42) but slightly more dollars ($0.004820 vs. $0.004386) due to generating reasoning tokens rather than reading cached prompt context. This rank swap is off the critical path and does not alter the frontier ordering `executor_alone` < `plan_only` < $k=10$ arms < `advise_k3` < `prefix_m6` < `prefix_m9` < `prefix_m11` < `ceiling_cap25` < `ceiling_cap81`.

We formally evaluate non-inferiority (NI) to the cap-81 planner ceiling (`ceiling_cap81`, 0.5702 TGC) across all three currencies under the registered 7.00 pp margin (COST-03). The non-inferiority verdict is **strictly currency-invariant**: exactly two arms pass on all three cost axes simultaneously while achieving significant cost reductions. Specifically, `prefix_m11` achieves **+3.51 pp** on TGC (scenario 95% CI [−6.14, +13.16], task [−5.26, +12.28]), passing the non-inferiority test while saving 716,854 non-cached tokens ([−1,314,868, −292,751]), $0.0217 ([−0.0390, −0.0094]), and 6.10 hosted calls ([−9.25, −3.34]) per episode. `ceiling_cap25` also passes (+11.40 pp, CI [+1.75, +21.05]). Non-inferiority fails for `prefix_m9` (−0.88 pp, CI [−9.65, +7.89]) strictly because its confidence interval lower bound exceeds 7.00 pp, rather than due to point estimate degradation (we conclude NI is not established at $m = 9$, not that $m = 9$ is inferior).

---

## 5. Prefix Depth: Continuous Span Scaling vs. Discrete Thresholds

We systematically characterize the relationship between prefix depth $m$ and execution quality across the complete grid $m \in \{2, 4, 6, 7, 8, 9, 10, 11\}$.

Following the introduction of the post-prefix terminal guard (GUARD-01), all-episodes `goal_pass_rate` is **monotonically increasing** across the depth grid: 0.6856 at $m = 2$, 0.7190 at $m = 4$, 0.7237 at $m = 6$, 0.7544 at $m = 7$, 0.7627 at $m = 8$, 0.7852 at $m = 9$, 0.8065 at $m = 10$, and 0.8098 at $m = 11$ (SHAPE-01, SHAPE-06). The pre-guard dip observed in pilot runs was eliminated once executor actions following replayed completion tokens were suppressed.

```
Figure F1: Goal pass rate against prefix handoff depth m for tailored and untailored receivers,
compared against the cap-25 (0.8284) and cap-81 (0.7637) planner ceilings, plan-only floor (0.7181),
and executor-alone floor (0.5289). (Referenced from paper/figures/f1_depth_curve.pdf).
```

### 5.1 The Honest Negative: Multiplicity Control and Segmented Regression

We subject the depth curve to pre-registered statistical testing. First, applying Holm-Bonferroni correction at $\alpha = 0.05$ across the family of 8 adjacent single-step transitions ($m0\rightarrow m2$, $m2\rightarrow m4$, $m4\rightarrow m6$, $m6\rightarrow m7$, $m7\rightarrow m8$, $m8\rightarrow m9$, $m9\rightarrow m10$, $m10\rightarrow m11$) yields an **adjusted $p$-value of 1.0 for all eight comparisons** (MULT-01). Every unadjusted and adjusted interval spans zero (e.g., $m6\rightarrow m7$ [−4.35, +10.18]; $m8\rightarrow m9$ [−1.75, +7.14]; $m10\rightarrow m11$ [−3.82, +4.18]). **No individual adjacent step is statistically significant.**

Second, pre-registered two-phase segmented regression (F1-RESULT-01..04) yields a split verdict across all four evaluation populations and both guard settings:
- **S1 (Flatness Below Breakpoint):** Holds in 8/8 configurations; pre-break slope $\beta_1$ includes zero ($\beta_1 = -0.00125$, 95% CI [−0.00637, +0.00815] on all episodes post-guard).
- **S2 (Rise Above Breakpoint):** Holds in 8/8 configurations; post-break slope $\beta_1 + \beta_2$ is strictly positive (+0.0245 with one-sided lower bound +0.0097 on $m10$ handoff keys; +0.0241 with lower bound +0.0071 on $m11$ handoff keys).
- **S3 (Threshold Localization):** Fails in 8/8 configurations; the 95% bootstrap confidence interval for breakpoint location $\tau$ spans [4, 9] (point estimate $\tau = 8$ on handoff-pinned populations, lower bound 4.0).

Per F1-RESULT-04, the precise finding is: **quality is flat in handoff depth below a breakpoint and rises above it (S1 and S2 hold), but because the breakpoint interval spans [4, 9], the registered threshold test S3 does not pass and no specific threshold location is claimed.** Figure F1 contains no artificial breakpoint markers.

### 5.2 Span-Based Scaling and Zero-Shot Gains

While adjacent steps are not individually resolvable, the depth effect across a multi-step span is substantial and statistically resolved (SHAPE-10, CHAN-ZS-04). For the untailored zero-shot receiver (`ibm-granite/granite-4.2-8b`, base weights), moving from $m = 6$ to $m = 9$ produces a **+10.21 pp** rise in `goal_pass` (0.6825 to 0.7845), with a 95% scenario-clustered CI of **[+2.60, +18.20]** (task **[+3.80, +16.81]**), and a **+16.67 pp** rise in TGC (0.3860 to 0.5526, scenario **[+5.26, +28.07]**, task **[+7.02, +26.32]**). Extending untailored zero-shot from $m = 9$ to $m = 11$ provides an additional **+4.99 pp** `goal_pass` (reaching 0.8345; task [+0.26, +9.31]) and **+7.02 pp** TGC (reaching 0.6228; scenario [+0.88, +14.04]; CHAN-ZS-04).

We verify that this span rise is not an artifact of run-to-run sampling noise. Replicate evaluations yield single-arm variations of 0.04 pp at $m = 6$ (0.7241 vs. 0.7237; NOISE-02) and 1.82 pp at $m = 9$ (0.8033 vs. 0.7852; NOISE-03). The maximum replicate difference of 1.82 pp yields a $2\times$ noise threshold of 3.63 pp, which is cleared by the observed 6.15 pp tailored rise and the 10.21 pp zero-shot rise, confirming that the span effect exceeds experimental noise (NOISE-03, NOISE-04).

---

## 6. What the Prefix Actually Conveys: The Narrated Control

Does an executed prefix assist the local model because the environment has physically advanced into a partially solved state, or because the prefix provides concrete in-context demonstrations of API usage and argument syntax?

To separate physical state from informational content, we evaluate the **narrated prefix control** (NARR-01, NARR-02). The planner's first 9 actions are rendered as plain-text execution traces appended to the initial prompt, but the local executor is initialized at **step 0 in a completely fresh environment**—matching the informational content of $m = 9$ while completely resetting the physical environment state.

```
Table 2: Physical Prefix Execution vs. Plain-Text Narration at Depth m = 9 (n = 114 paired).
--------------------------------------------------------------------------------------------------
Receiver / Metric       Physical m = 9   Narrated m = 9   Diff (pp)   Scenario 95% CI   Task 95% CI
--------------------------------------------------------------------------------------------------
Tailored Goal Pass              0.7852           0.7667     +1.84      [-2.67, +6.76]   [-3.70, +7.75]
Tailored TGC                    0.5614           0.5263     +3.51     [-5.26, +11.40]  [-4.39, +11.40]
Untailored Goal Pass            0.7845           0.7676     +1.69      [-4.16, +7.11]   [-3.70, +7.38]
Untailored TGC                  0.5526           0.4912     +6.14     [-2.63, +14.91]  [-1.75, +14.91]
--------------------------------------------------------------------------------------------------
```

Across all eight comparisons in Table 2, **every confidence interval includes zero** (NARR-01). Physical execution cannot be distinguished from plain-text narration at $n = 114$.

Evaluating narration against the single-plan floor demonstrates that text alone in a fresh environment captures nearly the entire gain of prefix execution (NARR-02). For the untailored receiver, plain-text narration provides **+47.92 pp** in `goal_pass` (scenario [+38.67, +56.27]) and **+43.86 pp** in TGC (scenario [+30.70, +56.14]) over the base floor (0.2885 `goal_pass` / 0.0526 TGC), capturing **97%** of the `goal_pass` gain and **88%** of the TGC gain achieved by physical execution. For the tailored receiver, narration provides **+13.16 pp** on TGC ([+5.26, +21.93]) over the plan floor, capturing **79%** of the execution TGC gain (the tailored `goal_pass` difference over floor is +4.86 pp [−0.56, +10.61], including zero).

```
Figure F6: Narrated versus executed prefix at m = 9, both receivers, on goal pass rate and TGC,
each against the one-plan floor with 95 percent bootstrap intervals. Asterisks mark lift over the
floor whose interval excludes zero; the tailored goal-pass narrated point carries none, because its
interval includes zero. The narrated and executed intervals overlap across both metrics and both
receivers, which is the finding of this section.
```

This establishes the central informational mechanism of this work: **the prefix operates as concrete, executable programming instructions rather than as an environment mutator.** Prose critique fails (CHAN-C1-02, −6.69 pp), but the exact same actions delivered as text in a fresh environment succeed.

---

## 7. Receivers and Tailoring: Non-Stacking Substitutability

We investigate whether executor fine-tuning interacts constructively with prefix depth, evaluating three distinct receiver variants across depths $m \in \{6, 9, 11\}$ on identical prefix trajectories (TAILOR-01, TAILOR-04, TAILOR-07, HF-01, HF-02).

```
Table 3: Three-Way Receiver Evaluation Across Depths (Goal Pass Rate, n = 114 paired; HF-02).
--------------------------------------------------------------------------------------------------
Receiver Configuration                      Depth m = 6        Depth m = 9        Depth m = 11
--------------------------------------------------------------------------------------------------
Untailored Base (Granite 8B zero-shot)           0.6825             0.7845              0.8345
Standard Tailored (sft_b_plus)                   0.7237             0.7852              0.8098
Handoff-Suffix Tailored (sft_b_plus_handoff)     0.7480             0.7840              0.8033
--------------------------------------------------------------------------------------------------
```

Paired scenario-clustered contrasts reveal a striking, monotonic pattern (Figure F3, HF-02):
- **At $m = 6$:** Trained receivers hold a directional lead: base minus standard adapter is **−4.12 pp [−10.41, +1.64]**; base minus handoff adapter is **−6.55 pp [−13.92, +0.23]**; standard minus handoff is **−2.43 pp [−7.42, +2.97]**.
- **At $m = 9$:** All three receivers converge to within 0.12 pp: base minus standard is **−0.06 pp [−7.06, +6.77]**; base minus handoff is **+0.05 pp [−6.35, +6.17]**; standard minus handoff is **+0.12 pp [−3.08, +3.12]**.
- **At $m = 11$:** The ordering reverses, with the untailored receiver leading numerically: base minus standard is **+2.46 pp [−1.48, +6.43]**; base minus handoff is **+3.12 pp [−1.97, +8.15]**; standard minus handoff is **+0.65 pp [−4.21, +5.37]**.

While all individual paired intervals include zero at $n = 114$, overarching curve spans over $m = 6 \rightarrow 11$ differ substantially: untailored climbs **15.20 pp**, standard adapter climbs **8.61 pp**, and handoff-suffix adapter climbs only **5.53 pp**.

The pre-registered hypothesis C3—asking whether training specifically on handoff suffixes extends the upper ceiling—is answered in the **negative**. Handoff-suffix fine-tuning raises shallow-depth performance but flattens the curve thereafter. Taken together with TAILOR-06 and MECH-07, **prefix depth, general executor tailoring, and suffix-specific training are partially substitutable and do not stack**. Each intervention provides the executor with domain syntax and API conventions; whichever is applied first captures the available gains, leaving the least specialized receiver with the greatest headroom to benefit from deep prefixes.

```
Figure F3: Receiver gap (untailored base minus tailored sft_b_plus) across handoff depths
m = 6, 9, 11 with scenario-clustered 95% bootstrap intervals. (paper/figures/f3_tailoring_gap.pdf).
```

---

## 8. Mechanism Decomposition: API Discovery and Compounding Error

To understand why deep prefixes succeed where prose advice fails, we analyze two complementary mechanisms: API novelty discovery and compounding error suppression (MECH-01, MECH-05, MECH-07).

```
Figure F4: Mechanism decomposition. Left (M1): cumulative share of first API uses by planner position.
Right (M3): decomposition of zero-shot depth rises into handoff-earned and silenced-episode contributions.
(Referenced from paper/figures/f4_mechanism.pdf).
```

### 8.1 Front-Loaded API Discovery (M1)

Interactive software tasks require discovering valid endpoints, function names, and argument schemas. In an audit of 673 first API invocations across 114 planner source episodes (mean 5.9 per episode; MECH-01), discovery is heavily front-loaded:
- Position $k = 1$: 16.9% of all first uses completed.
- Position $k = 3$: 35.5% completed.
- Position $k = 6$: 60.5% completed.
- Position $k = 9$: **78.3%** completed.
- Position $k = 11$: **86.6%** completed.

The per-position probability of introducing a novel API drops from 100% at step 1 to 48.2% at steps 5–6, 36.7% at steps 9–10, and 27.1% over steps 11–20. A prefix of depth $m = 9$ handles over three-quarters of the entire task's exploratory discovery, relieving the local executor of unconstrained search.

### 8.2 Compounding Error Suppression (M2)

Tracking environment observations across handoff episodes reveals that prefix depth dramatically reduces executor failure rates (MECH-05). For the tailored executor, the fraction of handoff episodes encountering at least one execution error falls from **85.09%** at $m = 2$ to **56.76%** at $m = 6$, **42.68%** at $m = 9$, and **40.85%** at $m = 10$. For the untailored executor, error incidence falls from **80.18%** at $m = 6$ to **64.63%** at $m = 9$ and **61.11%** at $m = 11$.

Conditional on erroring, the tailored executor's errors become concentrated at the initial handoff seam (share of first errors occurring at step 1 rises from 20.62% at $m = 2$ to 40.00% at $m = 9$ and 51.72% at $m = 10$). Depth does not make the executor better at error recovery; rather, it places the executor in a mature environment state where fewer error-prone decisions remain.

### 8.3 Handoff-Earned vs. Silenced Decompositions (M3)

Because deep prefixes can solve tasks completely before handoff occurs (silencing the executor on 31 episodes at $m = 9$ and 56 episodes at $m = 11$; GUARD-01), we decompose the all-episodes gain into handoff-earned vs. prefix-exhausted components (MECH-07). On the matched zero-shot transition $m = 6 \rightarrow 9$ (82 handoff episodes, 32 silenced), **83.8% of the +10.21 pp rise is earned on the handoff subset itself**, where the executor took over and improved from 0.6221 to 0.7410 (+11.89 pp gain). The depth gain is genuine executor improvement on live handoffs, rather than an accounting artifact of prefix silencing.

---

## 9. Generalization Across Model Families: Qwen3-8B Evaluation

To establish whether prefix depth scaling generalizes beyond IBM Granite, we evaluate `Qwen/Qwen3-8B` (zero-shot, `lora_name: null`) replaying identical planner trajectories (QWEN-02, QWEN-03, QWEN-04).

Across depths $m \in \{6, 9, 11\}$, Qwen3-8B displays clean, monotonic scaling across every recorded dimension (QWEN-04):
- **Goal Pass Rate:** 0.4491 at $m = 6$ $\rightarrow$ 0.7017 at $m = 9$ $\rightarrow$ **0.7306** at $m = 11$ (+28.15 pp span).
- **TGC (Binary All-Pass):** 0.1491 at $m = 6$ $\rightarrow$ 0.3772 at $m = 9$ $\rightarrow$ **0.4912** at $m = 11$ (+0.342 span).
- **Completed Successes:** 17/114 at $m = 6$ $\rightarrow$ 43/114 at $m = 9$ $\rightarrow$ **56/114** at $m = 11$.
- **Mean Episode Steps:** 29.61 at $m = 6$ $\rightarrow$ 21.47 at $m = 9$ $\rightarrow$ **18.95** at $m = 11$.
- **Step-Limit Exhaustions:** 74/114 at $m = 6$ $\rightarrow$ 39/114 at $m = 9$ $\rightarrow$ **31/114** at $m = 11$.


Paired scenario- and task-clustered intervals for the span (QWEN-05; note the stored keys are signed `m_lower minus m11`, so these are their negation): m = 6 to m = 11 gives **+28.15 pp** on `goal_pass`, scenario [+19.63, +38.47], task [+20.96, +35.72], and **+34.21 pp** on TGC, scenario [+24.56, +44.74], task [+24.56, +43.86]; both exclude zero. The shorter m = 9 to m = 11 step excludes zero on TGC at **+11.40 pp** ([+3.51, +19.30]) but includes zero on `goal_pass` at **+2.90 pp** ([-7.03, +1.61]). TGC is therefore the more sensitive metric for this family, which is what the floor defect below predicts: `goal_pass` carries per-task partial credit that is invariant to whether the model completes anything, and TGC does not. As with the Granite curve, the effect is reported as a rise across a span and never as a jump at a named depth.

```
Figure F5: Within-prefix depth curve for Qwen3-8B zero-shot at m = 6, 9 and 11. No floor is drawn:
both Qwen floor arms score identically and complete no tasks, so no floor-relative lift is
measurable, and the figure generator refuses to render the curve without that annotation.
```

### 9.1 Crucial Methodological Limitation: The Qwen Floor Defect

While Qwen3-8B scales robustly with prefix depth, **no floor-relative lift may be claimed for this model** (QWEN-02, QWEN-03). A complete census of the zero-shot Qwen floor arms reveals that `executor_alone` and `prompt_only` score an identical **0.2481** `goal_pass`, **0.0000** TGC, and **0/114** successes, with the step budget exhausted in 114/114 and 113/114 episodes respectively, the one remaining episode ending in a parse error (mean 40.00 vs. 39.89 steps). Supplying an upfront plan moved the score in **zero of 114 episodes**.

Action event auditing confirms that Qwen3-8B emits the terminal completion action (`COMPLETE`) exactly **0 times in 114 executor-alone episodes and 0 times in 80 prompt-only episodes**, but emits it 32 times at $m = 6$ and 37 times at $m = 9$ (QWEN-02). Under identical prompt templates and byte-identical stop tokens, Granite completes 53 of 114 plan episodes. Qwen3-8B fails to emit the completion action until it observes format demonstrations in-context. Consequently, the 0.2481 baseline score is invariant to the plan and accompanies zero completed tasks. We did not audit the scorer, so we do not assert what produces it. The depth effect replicates cleanly *within prefix arms* (where format demonstrations are common to all arms and difference out), but comparisons against the zero-shot floor are uninterpretable.

---

## 10. Related Work and External Benchmark Comparison

We situate our findings within published evaluations on AppWorld (`docs/external_comparison_20260923.md`):

- **AppWorld Baselines (Trivedi et al., ACL 2024):** The benchmark introduction evaluates ReAct, Plan & Execute (PlanExec), Full Code + Reflexion, and Iterative Parallel Function Calling across GPT-4o, GPT-4-Turbo, and LLaMA-3-70B-Instruct. On `test_normal`, GPT-4o ReAct achieves 48.8% TGC / 32.1% SGC, while PlanExec achieves 44.6% TGC / 23.2% SGC. LLaMA-3-70B achieves 24.4% TGC (Full Code + Reflexion) and 20.8% TGC (ReAct). Smaller open models without specialization (Mistral-7B-CodeAct, ToolLLaMA-7B) score 0.0% TGC.
- **Scaffolding and Training Innovations:** LOOP (Anonymous, arXiv:2502.01600) achieves a +9.0 pp relative gain over o1 (~71% TGC) using a 32B open model. CANOPY (Pu et al., arXiv:2609.01245) reports 86.9% TGC on `test_normal` and 67.6% on `test_challenge` with Qwen3-14B via outcome-only RL. ACE (Anonymous, ICLR 2026 / arXiv:2510.04618) yields a +17.1% relative gain with DeepSeek-V3.1. ProST (Bijoy et al., IJCNLP-AACL 2025 / arXiv:2509.04508) evaluates progressive sub-task training on ~8B open models (26.0–33.0% TGC). Three Roles, One Model (Anonymous, arXiv:2604.11465) evaluates Qwen3-8B under a 3-role scaffold (8.9% TGC FP16 / 5.9% AWQ). User-in-the-loop interactions are benchmarked by AppWorld-UL (Anonymous, ICML 2026 / arXiv:2607.20536; 48.6% overall success with Claude Opus 4.7).
- **Public Leaderboard Anchor:** On the AppWorld leaderboard, the Kecaipan Capybara scaffold utilizing `gpt-5.6-luna` achieves 85.1% TGC / 73.2% SGC on `test_normal` and 73.4% TGC / 52.5% SGC on `test_challenge`.

### Non-Comparability of Absolute Dev Scores

As detailed in `docs/limitations_external_20260923.md`, our dev-split pass rates (0.72–0.83) cannot be directly compared against published test-split leaderboard rankings due to four methodological differences: (1) we employ a minimal interaction loop (14.4 mean calls vs. 9.3 on complex scaffolds); (2) evaluations are strictly on the dev split; (3) our environment uses 57 pinned dev tasks (excluding 3 multi-party synchronization tasks); and (4) our planner uses frozen `medium` reasoning effort. Internal validity is maintained via paired bootstrap contrasts on identical task-seed initializations.

---

## 11. Limitations and Methodological Integrity

We document the boundary conditions of our study and the analytical defects identified and repaired during the campaign:

1. **Development Split Scope:** Experiments were executed exclusively on the 57-task AppWorld development split ($n = 114$ paired episodes). Test splits (`test_normal`, `test_challenge`) remain untouched (`docs/prereg_j9_freeze_20260920.md`).
2. **Single Planner Family:** Handoff trajectories and advice critiques were generated exclusively with `gpt-5.6-luna` at `medium` reasoning effort. Cross-planner transferability remains unmeasured.
3. **Cap-81 Ceiling Inversion (CEIL-01, CEIL-04):** Extending planner call cap from 25 to 81 calls resulted in lower performance: `ceiling_cap81` scored **0.7637 `goal_pass` / 0.5702 TGC** vs. **0.8284 / 0.6842** for `ceiling_cap25` (paired difference **−6.47 pp `goal_pass`**, scenario [−11.68, −1.37], task [−12.48, −0.46]; TGC **−11.4 pp** [−21.05, −1.75]). Cap-81 episodes averaged 16.35 actions (max 40) vs. 13.42 for cap-25 (max 24), demonstrating that unconstrained budget allows over-acting in the tail, corrupting environment state.
4. **Qwen Floor Format Confound:** Zero-shot Qwen3-8B fails to emit termination tokens without in-context demonstrations, invalidating floor-relative lift claims (QWEN-02, QWEN-03).
5. **Analysis Defects Found and Repaired:**
   - *Terminal Guard Defect (GUARD-01, MECH-01..03):* Early runs allowed actions following replayed completion tokens; resolved by adding a fatal post-prefix terminal check.
   - *Handoff Flag Path (MECH-02, GUARD-01/X33d):* The mechanism script initially inspected an invalid JSON key; resolved by aligning paths and making zero-count populations fatal.
   - *Error Scan Actor Filter (MECH-04, MECH-05):* Initial audits filtered observations on executor identity, yielding 0.00% error rates; repaired to scan observation return text.
   - *Adapter Build Mismatch (ADV-FC-02):* Initial H1 advice contrasts paired against an older 0.7000 adapter build; corrected to use the standard 0.7181 `iaware` build.
   - *Cost Token Pricing (COST-01):* Local executor tokens were initially passed to hosted pricing calculators; corrected to filter exclusively on hosted usage events.
   - *Segmented Fit Float Tie-Breaking (TIEBREAK-01):* Exact RSS float comparisons in segmented regression produced spurious breakpoints on straight lines; resolved via scaled RSS tolerances.

---

## 12. Conclusion

When pairing a strong hosted planner with a small local executor on complex interactive environments, communication bandwidth is best spent as concrete action prefixes rather than natural-language advice. Action execution strictly dominates prose critique in performance, token cost, and financial expenditure. The benefits of prefix handoffs accumulate continuously across depth spans by relieving the local model of exploratory API discovery and compounding error traps, operating primarily through informational demonstration rather than environment mutation.

---
