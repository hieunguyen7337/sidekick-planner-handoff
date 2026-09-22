---
title: "Steering Local Agentic Executors via Action Prefixes: Channel Dominance, Prefix Depth, and Mechanism on the AppWorld Benchmark"
date: "2026-09-23"
author: "Sidekick Research Group"
abstract: |
  We examine compute allocation when pairing a compact local model (IBM Granite 4.2 8B) with a strong hosted planner (GPT-5.6 Luna) on complex interactive environments. Across paired evaluations on the AppWorld dev benchmark (57 tasks, $n = 114$ paired episodes across 19 scenario clusters), we establish four primary empirical findings. First, spending hosted budget as executable action prefixes strictly dominates spending it as natural-language prose advice: at matched triggers ($k = 10$) and full context, action execution outperforms prose critique by +6.69 percentage points in goal pass rate (95% scenario-clustered bootstrap interval [+1.29, +13.48], task-clustered [+1.47, +12.35]) while reducing non-cached tokens (41,464 vs. 49,819), provider dollars ($0.004820 vs. $0.005494), and hosted calls (2.316 vs. 2.465) per episode. Second, handoff quality rises with prefix depth across a span—gaining +10.21 pp on goal pass rate ([+2.60, +18.20] scenario, [+3.80, +16.81] task) and +16.67 pp on Total Goal Criterion (TGC; [+5.26, +28.07] scenario, [+7.02, +26.32] task) between depths $m = 6$ and $m = 9$ zero-shot. However, Holm correction yields adjusted $p = 1.0$ across all eight adjacent transitions, and segmented regression yields $\tau = 8$ with CI [4, 9] (failing registered threshold test S3), confirming a continuous span gain rather than a discrete threshold jump. Third, environment resets show that what the prefix conveys is largely informational, but how far that goes depends on the receiver: rendering the planner's actions as plain text into a fresh environment matches physical execution at every depth tested on a receiver fine-tuned on the planner's trajectories (−2.51, −1.84 and −0.49 pp at $m = 6, 9, 11$, all intervals including zero, and non-inferior at $m \ge 9$ against a 7.00 pp margin), while on an untailored receiver execution wins at the deep end (−6.58 pp, scenario [−9.98, −3.64] at $m = 11$) and the narrated curve saturates after $m = 9$. Fourth, in a pre-registered test of the obvious objection that the action channel merely buys more planner effort, prose advice reviewed at every step consumes 3.2$\times$ the non-cached tokens and 1.7$\times$ the hosted calls of the deepest action prefix and still scores 14.68 pp lower (scenario [−22.09, −7.04]). All evaluations are conducted strictly on the AppWorld development split.
---

# Steering Local Agentic Executors via Action Prefixes: Channel Dominance, Prefix Depth, and Mechanism on the AppWorld Benchmark

## 1. Introduction

Autonomous language agents in digital environments must navigate long horizons, discover multi-application APIs, and maintain coherent state. Frontier foundation models exhibit high planning competence but remain expensive, latency-constrained, and privacy-sensitive to run as interactive loops over many steps. Compact local models (e.g., 8B open weights) provide high throughput and low marginal cost, yet suffer from error compounding, syntax fragility, and poor exploratory discovery when deployed autonomously.

This tension motivates hybrid systems pairing a small local executor with a strong hosted planner. The core question is: **through which communication channel, and at what depth of intervention, should the hosted budget be spent?** Existing approaches typically configure the hosted model as an asynchronous critic or upfront planner emitting natural-language advice or stepwise plans.

In this work, we demonstrate that natural-language advice is fundamentally the wrong medium for steering local executors. Across extensive paired evaluations on the AppWorld benchmark, spending hosted budget as concrete, executable **action prefixes** strictly dominates natural-language critique in task quality, token consumption, provider expenditure, and hosted call count. We do not measure wall-clock latency and make no claim about it.

Our contributions are grounded in an exact pre-registered claims ledger (`docs/claims_ledger.md`):

- **Channel Dominance at Matched Trigger (CHAN-C1-02, COST-01):** At matched triggers ($k = 10$) and full transcript context, direct action takeover outperforms prose advice by +6.69 pp on `goal_pass` (scenario 95% CI [+1.29, +13.48], task [+1.47, +12.35]) while strictly dominating advice across non-cached tokens (41,464 vs. 49,819), provider dollars ($0.004820 vs. $0.005494), and hosted calls (2.316 vs. 2.465).
- **Advice Does Not Catch Up When Bought Above the Action Channel's Price (CHAN-PRICE-01):** In a pre-registered test (`docs/prereg_h2_advice_at_price_20260923.md`), prose advice reviewed at every step with full context spends 1,414,410 non-cached planner tokens and 19.02 hosted calls per episode — 3.2$\times$ the tokens and 1.7$\times$ the calls of the deepest action prefix — and still scores 14.68 pp lower on `goal_pass` (scenario [−22.09, −7.04], task [−21.56, −7.79]). Ten times the review frequency does not buy quality. The difference is the channel, not the budget.
- **Equivalence of Live Takeover and Oracle Replay (CHAN-C1-03):** A live takeover loop calling the planner online is statistically indistinguishable at $n = 114$ from replayed oracle prefix trajectories at depth $m = 9$ (+1.55 pp, scenario [−3.46, +7.04], task [−4.41, +8.01]) and $m = 11$ (−0.91 pp, scenario [−6.74, +5.94], task [−6.90, +5.16]).
- **Span-Based Scaling without Stepwise Discontinuities (MULT-01, F1-RESULT-01..04, SHAPE-10):** Handoff quality increases with prefix depth (+10.21 pp `goal_pass` [+2.60, +18.20] scenario; +16.67 pp TGC [+5.26, +28.07] scenario from $m = 6$ to $m = 9$ zero-shot). However, Holm correction yields adjusted $p = 1.0$ across all eight adjacent transitions, and segmented regression yields $\tau = 8$ with CI [4, 9] (failing registered threshold test S3), confirming a continuous gain across spans rather than a discrete threshold jump.
- **Informational Mechanism, Bounded by the Receiver (NARR-03, NARR-04):** Replaying the planner's actions as plain text into a fresh environment matches physical execution at $m = 6, 9, 11$ on the tailored receiver (−2.51, −1.84, −0.49 pp, every interval including zero; non-inferior at $m \ge 9$ against the registered 7.00 pp margin). On the untailored receiver the substitution breaks down with depth: execution wins by 6.58 pp at $m = 11$ (scenario [−9.98, −3.64]) and the narrated curve gains only +0.10 pp from $m = 9$ to $m = 11$ while the tailored one gains +3.81 pp ([+0.79, +6.97]). A per-episode difference-in-differences resolves the interaction at $m = 11$ (**+6.09 pp**, scenario [+1.56, +11.00], task [+0.63, +11.85]; TGC +12.28 pp [+0.88, +26.32]) and at neither $m = 6$ nor $m = 9$; with three depths examined we report this as resolved at one depth, not as a general interaction.
- **A Substitutability Pattern That Does Not Replicate (TAILOR-07, C81-02, HF-02):** On the first planner sample the untailored-minus-tailored receiver gap moves monotonically with depth (−4.12, −0.06, +2.46 pp at $m = 6, 9, 11$), suggesting depth substitutes for fine-tuning. On an independent planner sample the same gap runs −2.76, +0.31, −1.80 pp: non-monotone, ending with the tailored receiver ahead rather than behind. No individual receiver gap is resolved on either sample, so we report this as an observation made on one sample and not reproduced on a second, rather than as a finding.
- **Depth Replicates in a Second Family; the Fine-Tuning Recipe Does Not (QWEN-04, QWEN-03, QWEN-06):** The monotonic depth effect replicates within zero-shot `Qwen/Qwen3-8B` prefix arms (`goal_pass` 0.4491 at $m = 6$ to 0.7306 at $m = 11$, TGC 0.1491 to 0.4912), while format censuses establish that its baseline floor (0.2481) reflects terminal token non-emission rather than task competence. Training Qwen with the identical dataset and recipe that lifts Granite's one-plan floor by ~43 pp moves Qwen's by ~1 pp, because the terminal convention is 2.44% of the supervised targets and Qwen does not acquire it at that rate (0–0.07% of its actions) while Granite reproduces it almost exactly (3.00%). Depth transfers across families; this fine-tuning recipe does not.

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

#### Trajectory sourcing, and why it has to be stated

Every prefix arm in this paper *replays* a recorded planner campaign rather than calling the planner
online. That is what removes planner sampling noise from the depth curve — measured at 0.04 pp of
executor-side replicate variation against 6.47 pp between two planner runs (CEIL-02) — and it is what
makes the receiver comparisons exactly paired, since both receivers consume byte-identical prefixes.

The cost is that a prefix arm and a ceiling arm are comparable only if they replay the **same** campaign.
We run two planner samples: a 25-call-capped campaign and an 81-call-capped one. A prefix arm sourced
from the cap-25 campaign and compared against the cap-81 ceiling is paired **by task, not by
trajectory** — the two arms saw different planner behaviour on the same task. We state each arm's source
campaign wherever it matters, and §5.4 reports a ceiling claim that does not survive being measured
like-for-like. Readers checking a number against the ledger should check its source campaign first.

---

## 3. The Action Channel Beats the Advice Channel at Matched Trigger

To resolve whether hosted budget is more effectively spent as supervisory prose or direct environment actions, we examine pre-registered primary channel contrast C1 (CHAN-C1-00, CHAN-C1-02). We compare live action takeover (`takeover_fixed_k_10`) against full-context prose advice (`advise_fixed_k_10_fullctx`). Both arms are matched: identical trigger condition ($k = 10$), same cached initial plan, identical executor model and adapter, and both supply the complete episode transcript to the planner (CHAN-C1-00).

The action channel decisively outperforms prose advice. On `goal_pass`, `takeover_fixed_k_10` achieves 0.8007 compared to 0.7339 for `advise_fixed_k_10_fullctx` (TGC 0.5175 vs. 0.4386). The paired difference is **+6.69 pp**, with a 95% scenario-clustered CI of **[+1.29, +13.48]** and task-clustered CI of **[+1.47, +12.35]** (CHAN-C1-02). Because both intervals strictly exclude zero under 10,000 bootstrap draws, the superiority of the action channel is established at the pre-registered trigger. Against the one-plan floor (`sft_plan`, 0.7181), takeover provides a significant gain of **+8.26 pp [+3.84, +13.11]**, whereas advice provides only **+1.57 pp [−2.91, +5.91]**, failing to show a resolvable difference from the floor.

A central methodological concern regarding prefix handoffs is that replaying recorded oracle trajectories cannot be deployed live without ground-truth traces. We address this directly via CHAN-C1-03 by evaluating online live takeover against oracle replayed prefixes. Against oracle prefix replay at depth $m = 9$ (0.7852) and depth $m = 11$ (0.8098), live takeover (0.8007) yields paired differences of **+1.55 pp** (scenario [−3.46, +7.04], task [−4.41, +8.01]) and **−0.91 pp** (scenario [−6.74, +5.94], task [−6.90, +5.16]) respectively. Crucially, because both confidence intervals span zero (widths ±6–7 pp), we conclude that **we cannot distinguish live takeover from oracle prefix replay at $n = 114$**. We do not claim mathematical equality, but rather that live execution achieves parity within experimental resolution, validating deployability.

Finally, we confirm that the poor performance of prose advice is not an artifact of critic context starvation (ADV-FC-01, ADV-FC-02). Evaluating full-transcript control (`advise_fixed_k_10_fullctx`, 0.7339) against the context-starved baseline (`advise_fixed_k_10`, 0.6964) yields a non-significant difference of **+3.74 pp** (scenario [−1.39, +9.13], task [−1.72, +9.53]). Furthermore, full-context advice exceeds the matched adapter plan floor (`hj8_sft_plan_bplus_20260921iaware`, 0.7181) by only **+1.57 pp** (scenario [−2.91, +5.91], task [−3.04, +6.30]; TGC +4.39 pp [−4.39, +12.28]). Advice remains indistinguishable from the floor under both truncated and complete reviewer contexts (Figure F2).

---

### 3.1 Advice at the Action Channel's Price

The obvious objection to Section 3 is that the action channel simply buys more planner effort. We
pre-registered a test of it (`docs/prereg_h2_advice_at_price_20260923.md`), naming the arm, the four
predictions, the analysis script and the output path before the run. The arm, `advise_fixed_k_1_fullctx`,
reviews the executor's work at **every step** with full context — ten times the review frequency of the
$k = 10$ advice arm.

Table 1b: Advice bought at the action channel's budget (n = 114 paired, scenario 95% CI).

| Arm | `goal_pass` | Non-cached planner tokens / episode | Hosted calls / episode |
|---|---|---|---|
| `advise_fixed_k_10_fullctx` | 0.7339 | 49,819 | 2.46 |
| `advise_fixed_k_1_fullctx` | **0.6630** | **1,414,410** | **19.02** |
| `prefix_m9` | 0.7852 | 357,448 | 9.77 |
| `prefix_m11` | 0.8098 | 443,361 | 11.25 |

Advice at every step consumes **3.2× the non-cached tokens** and **1.7× the hosted calls** of the deepest
action prefix, and scores **14.68 pp lower** on `goal_pass` (scenario [−22.09, −7.04], task
[−21.56, −7.79]) and 15.79 pp lower on TGC ([−28.07, −3.51]). Against `prefix_m9` the gap is −12.21 pp
([−19.81, −3.72]).

Three of the four registered predictions held. **P1** (advice minus the one-plan floor includes zero) held
at −5.51 pp ([−13.15, +2.51]), though the registered *point* prediction of [−2, +5] pp was missed on the
low side: reviewing every step leaves the executor numerically *below* the one-plan floor. **P2** (advice
minus `prefix_m11` negative, excluding zero) held decisively. **P3** (ten times the review frequency does
not buy quality) held at −7.08 pp ([−14.78, +0.67]); we note it is marginal on the task clustering, where
the upper bound is +0.01.

**P4 failed, and we report the failure and our handling of it explicitly.** P4 predicted non-cached
tokens in [300k, 700k]; the observed 1,414,410 is roughly twice the top of that range. The prereg's remedy
for a P4 failure is written for the *opposite* case — an arm that lands below 300k and so was never
actually priced at the action channel's budget, in which case P2 must be reported as untested. That hazard
is excluded here *a fortiori*: advice was bought far above the action channel's budget, not below it. We
therefore report P2 as tested and supported, while flagging that this is a deviation from the literal text
of a frozen prereg. A reader who declines that judgement should treat P2 as untested at the registered
budget and rely on Section 4, which establishes the same channel ordering at **matched trigger and matched
context**, where no budget question arises.

**Figure F8** places all four arms on cost and quality axes: the advice arms sit at the bottom of the quality range at both ends of the cost range, while the action prefixes sit above them in between.

By the prereg's own decision rule, P1 and P2 both holding establishes the channel claim at matched budget:
**advice does not reach the action channel's quality even when priced at or above it; the difference is the
channel, not the budget.**

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

We formally evaluate non-inferiority (NI) to the cap-81 planner ceiling (`ceiling_cap81`, 0.5702 TGC) across all three currencies under the registered 7.00 pp margin (COST-03). The non-inferiority verdict is **strictly currency-invariant**: exactly two arms pass on all three cost axes simultaneously while achieving significant cost reductions. Specifically, `prefix_m11` achieves **+3.51 pp** on TGC (scenario 95% CI [−6.14, +13.16], task [−5.26, +12.28]), passing the non-inferiority test while saving 716,854 non-cached tokens ([−1,314,868, −292,751]), $0.0217 ([−0.0390, −0.0094]), and 6.10 hosted calls ([−9.25, −3.34]) per episode. `ceiling_cap25` also passes (+11.40 pp, CI [+1.75, +21.05]). Non-inferiority fails for `prefix_m9` (−0.88 pp, CI [−9.65, +7.89]) strictly because its confidence interval **upper** bound exceeds 7.00 pp — the contrast is reported as ceiling minus arm, so non-inferiority requires the upper bound to sit below the margin — rather than due to point estimate degradation (we conclude NI is not established at $m = 9$, not that $m = 9$ is inferior).

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

### 5.3 Replication on an Independent Planner Sample

Every prefix arm above replays one planner run, the cap-25 trajectories, which invites the objection that the effect rests on a single lucky sample. We therefore replayed a second, independent set: the cap-81 planner trajectories, whose source planner scores **6.47 pp below** the cap-25 planner (CEIL-01). The untailored curve is complete (C81-01).

The depth effect replicates. `goal_pass` runs 0.7201, 0.7650 and 0.7932 at $m = 6, 9, 11$, and TGC 0.4561, 0.5263 and 0.5526. Over the span $m = 6 \rightarrow 11$ the rise is **+7.31 pp** on `goal_pass` (scenario [+2.07, +12.80]) and **+9.65 pp** on TGC (scenario [+2.63, +16.67]), both excluding zero. As on the original curve, and consistent with MULT-01, **no single adjacent step is individually significant**: $m = 6 \rightarrow 9$ is +4.49 pp [−1.72, +11.29] and $m = 9 \rightarrow 11$ is +2.82 pp [−1.55, +7.16] on `goal_pass`.

The generality result is the endpoint comparison. At $m = 11$ the cap-81 prefix differs from the cap-25 prefix by **−4.13 pp**, scenario [−8.84, +0.50], task [−9.74, +1.44] — **including zero**. A materially weaker planner run therefore yields a prefix of statistically indistinguishable value at depth 11, which is the strongest evidence available here against the single-sample objection.

The curve is **compressed rather than translated**: it starts higher (0.7201 against 0.6825 at $m = 6$) and ends lower (0.7932 against 0.8345 at $m = 11$), a span of 7.31 pp against 15.20 pp. The two curves converge with depth, so this is a replication of the *effect*, not of the *curve*.

The tailored cap-81 arms have since completed: `goal_pass` 0.7477, 0.7619 and 0.8111 at $m = 6, 9, 11$. At $m = 11$ the tailored arm is essentially unchanged by the source swap (0.8111 against 0.8098 under cap-25 sourcing), while the untailored arm loses 4.13 pp. The depth step $m = 9 \rightarrow 11$ is +4.92 pp [−0.43, +10.36] tailored against +2.82 pp [−1.55, +7.16] untailored — the *reverse* of the ordering under cap-25 sourcing (+2.46 tailored against +4.99 untailored). Neither pair is resolved, and the fact that their ordering inverts with the trajectory source is a further reason we make no claim about a tailoring $\times$ depth interaction anywhere in this paper.

### 5.4 A Correction: One Ceiling Claim Does Not Survive Like-for-Like Sourcing

The cap-81 arms permit a comparison the earlier sections could not make. Every prefix arm in §4 and §5.1–5.2 replays **cap-25** trajectories, while `ceiling_cap81` is an independent **cap-81** planner sample; contrasts between them are paired by task, not by trajectory. With the cap-81-sourced prefixes we can pair prefix and ceiling on the *same* planner run.

Doing so withdraws one statement. Under the mismatched pairing, the untailored $m = 11$ arm appeared **significantly above** the cap-81 ceiling (ceiling minus arm −7.08 pp, [−12.61, −1.87], excluding zero). Like-for-like it is **−2.95 pp [−8.65, +1.91]**, which includes zero. The apparent superiority was carried by the trajectory-source mismatch, not by the receiver. The tailored arm is likewise nominally above the ceiling but unresolved (−4.75 pp [−11.75, +1.16]).

What survives is the weaker and correct claim: both $m = 11$ arms are **non-inferior** to a hosted planner that acts at every step for up to 81 calls, at the registered 7.00 pp margin. We report this correction because the mismatch was flagged in our own records before it was measured, and measuring it changed the answer. The arm carrying this paper's primary result is unaffected: the channel contrast against the cap-81-sourced tailored prefix is **−14.81 pp [−21.20, −7.96]**, against −14.68 pp under the original sourcing.

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

**This equivalence is measured at $m = 9$, and $m = 9$ is where the two curves are closest.** The narrated curve has since completed at $m = 6$ and $m = 11$ on the untailored receiver, and execution beats narration **significantly** at both, on both clusterings: narrated versus executed `goal_pass` is 0.6128 against 0.6825 at $m = 6$, 0.7676 against 0.7845 at $m = 9$, and 0.7686 against 0.8345 at $m = 11$. Same-depth contrasts (NARR-03): at $m = 6$ TGC is −13.16 pp (scenario [−21.05, −5.26]); at $m = 9$ everything spans zero; at $m = 11$ `goal_pass` is −6.58 pp ([−9.98, −3.64]) and TGC −11.40 pp ([−22.81, −2.63]). The narrated curve also saturates: it gains +0.10 pp from $m = 9$ to $m = 11$ ([−4.75, +5.14]) while the executed curve climbs 0.7845 to 0.8345. **The claim of this section is therefore that information, not state, carries the prefix benefit at moderate depth — not that state never matters.** Beyond $m \approx 9$ the executed environment contributes something text does not. One practical corollary does survive at every depth measured: narration at $m = 9$ and at $m = 11$ beats *execution* at $m = 6$ (+8.52 pp [+2.32, +14.75] and +8.62 pp [+2.24, +15.02]), so deeper narration is worth more than shallower execution. **This paragraph describes the untailored receiver; §6.1 shows the tailored receiver does not share either the deep-end gap or the saturation.**

Evaluating narration against the single-plan floor demonstrates that at $m = 9$ text alone in a fresh environment captures nearly the entire gain of prefix execution (NARR-02); the shares below are specific to that depth. For the untailored receiver, plain-text narration provides **+47.92 pp** in `goal_pass` (scenario [+38.67, +56.27]) and **+43.86 pp** in TGC (scenario [+30.70, +56.14]) over the base floor (0.2885 `goal_pass` / 0.0526 TGC), capturing **97%** of the `goal_pass` gain and **88%** of the TGC gain achieved by physical execution. For the tailored receiver, narration provides **+13.16 pp** on TGC ([+5.26, +21.93]) over the plan floor, capturing **79%** of the execution TGC gain (the tailored `goal_pass` difference over floor is +4.86 pp [−0.56, +10.61], including zero).

```
Figure F6: Narrated versus executed prefix at m = 9, both receivers, on goal pass rate and TGC,
each against the one-plan floor with 95 percent bootstrap intervals. Asterisks mark lift over the
floor whose interval excludes zero; the tailored goal-pass narrated point carries none, because its
interval includes zero. The narrated and executed intervals overlap across both metrics and both
receivers AT THIS DEPTH. Note the depth AND the receiver: on the UNTAILORED receiver execution beats narration at m = 6 and m = 11 (NARR-03), so m = 9 is a crossing point there; on the TAILORED receiver no depth shows a resolved gap (NARR-04).
```

This establishes the central informational mechanism of this work: **at moderate depth the prefix operates as concrete, executable programming instructions rather than as an environment mutator.** Prose critique fails (CHAN-C1-02, −6.69 pp), but the exact same actions delivered as text in a fresh environment succeed.

---

### 6.1 The Substitution Is Receiver-Dependent

The paragraph above is measured on the **untailored** receiver. The tailored narrated curve has since
completed at all three depths (NARR-04), and it does not behave the same way.

Table 2b: Narrated minus executed `goal_pass`, by receiver and depth (n = 114 paired, scenario 95% CI).

| $m$ | Untailored | Tailored |
|---|---|---|
| 6 | −6.96 [−13.67, +0.63] | −2.51 [−8.68, +3.41] |
| 9 | −1.69 [−7.10, +4.16] | −1.84 [−6.76, +2.68] |
| 11 | **−6.58 [−9.98, −3.64]** | −0.49 [−4.10, +3.21] |

On the tailored receiver **every** same-depth contrast includes zero, on both metrics: `goal_pass`
−2.51, −1.84, −0.49 pp and TGC −2.63, −3.51, +0.88 pp at $m = 6, 9, 11$. Against the pre-registered
7.00 pp non-inferiority margin, narration is **non-inferior to execution at $m = 9$ and $m = 11$ on the
tailored receiver** (`goal_pass` lower bounds −6.76 and −4.10), and fails only at $m = 6$ (−8.68). On the
untailored receiver NI fails at every depth (−13.67, −7.10, −9.98).

The two narrated curves also differ in shape. The untailored narrated curve **saturates** after $m = 9$,
gaining +0.10 pp to $m = 11$ ([−5.14, +4.75]). The tailored one does not: +6.82 pp from $m = 6$ to $m = 9$
([+0.63, +12.61]), a further **+3.81 pp** to $m = 11$ ([+0.79, +6.97]), and +10.63 pp across the span
([+4.91, +16.34]) — all excluding zero. The practical corollary from the untailored receiver holds here
too: tailored narration at $m = 11$ beats tailored *execution* at $m = 6$ by +8.12 pp ([+3.18, +13.67]).

**Figure F7** plots these six contrasts with their scenario-clustered intervals and the zero line.

The natural reading is that **receiver tailoring is what allows a description of the planner's actions to
substitute for having executed them**: a receiver trained on the planner's own trajectories reconstructs
from text what an untrained one cannot, and the untrained receiver stops extracting additional value from
deeper narration past $m = 9$.

**The interaction is now measured, and it resolves at the deep end only** (DID-01). Comparing *which* of
six contrasts happens to exclude zero is not a test of an interaction: two contrasts can differ in
significance while the difference between them is indistinguishable from zero. We therefore form the
difference-in-differences

$$\mathrm{DiD}(m) = \big(\text{narrated} - \text{executed}\big)_{\text{tailored}} - \big(\text{narrated} - \text{executed}\big)_{\text{untailored}}$$

**per episode**, and bootstrap clusters of that single derived series (10,000 resamples, seed 20260924,
$n = 114$ paired episodes, no episode dropped). Forming it per episode matters: all four arms replay the
same $(\text{task}, \text{seed})$ episodes, so subtracting two separately bootstrapped gaps would discard
the episode-level pairing the replay design buys and widen the interval enough to hide a real effect.

Table 2c: DiD by depth, `goal_pass`, scenario-clustered 95% CI (task-clustered in parentheses).

| $m$ | DiD | scenario CI | task CI |
|---|---|---|---|
| 6 | +4.45 | [−6.71, +14.25] | [−5.07, +13.98] |
| 9 | −0.16 | [−8.36, +7.11] | [−8.51, +8.04] |
| 11 | **+6.09** | **[+1.56, +11.00]** | **[+0.63, +11.85]** |

At $m = 11$ the interval excludes zero on **both** clusterings, and TGC agrees at **+12.28 pp** (scenario
[+0.88, +26.32], task [+2.63, +22.81]). So the stronger statement is now available at that depth: the
tailored receiver closes the narration-execution gap significantly more than the untailored one, +6.09 pp
of gap closed, from −0.49 pp against −6.58 pp. At $m = 6$ the point estimate has the same sign but the
interval spans zero, and at $m = 9$ the DiD sits on zero.

⚠ **Three depths and two metrics were tested and only $m = 11$ resolves, so this is exploratory, not
confirmatory.** The correct sentence is "the interaction is resolved at $m = 11$", never "the interaction
holds". The receiver × depth grid was planned in advance, but this reading was formed after seeing it. We
report the two unresolved depths beside the resolved one for exactly that reason.

---

### 6.2 Observations Add Nothing the Actions Did Not Already Carry

The narrated packet renders the planner's *actions* as text. A natural follow-up is whether the
planner's *observations* — what those actions returned — carry part of the benefit, since a prefix
plausibly helps by handing over discovered facts (account identifiers, API shapes) rather than a
sequence of moves. We ran the actions+observations variant at $m = 9$ on both receivers (NARR-05).

| Receiver | actions only | + observations | plain − obs, `goal_pass` | TGC |
|---|---|---|---|---|
| Untailored | 0.7676 | 0.7841 | −1.64 [−6.46, +2.97] | −1.75 [−9.65, +5.26] |
| Tailored | 0.7667 | 0.7401 | +2.67 [−1.62, +7.49] | +2.63 [−5.26, +12.28] |

All eight intervals include zero, and the point estimates run in **opposite directions** on the two
receivers: observations nominally help the untailored receiver and nominally hurt the tailored one.
Opposite-signed unresolved effects of this size are what noise looks like, so we report the null:
observation text adds nothing detectable at $n = 114$. What the prefix conveys is the planner's
**sequence of actions**, not the facts those actions returned.

We flag one asymmetry without overclaiming it. Against the 7.00 pp non-inferiority margin, untailored
actions+observations narration *is* non-inferior to execution at $m = 9$ (−0.04 pp, scenario
[−5.12, +5.11]), whereas plain untailored narration at the same depth is not (−1.69 pp, scenario
[−7.10, +4.16], whose lower bound falls just outside the margin). That is a difference in which
non-inferiority statements are licensed, not evidence that observations helped: the direct contrast
between the two narrated variants is the −1.64 pp interval above, which includes zero.

---

## 7. Receivers and Tailoring: A Pattern That Does Not Replicate

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

### 7.1 The Crossover Is Specific to One Planner Sample

The reading above — that depth substitutes for receiver tailoring, because the untailored receiver overtakes the tailored one by $m = 11$ — rests on the *shape* of a three-point sequence, since no individual within-depth receiver gap is resolved at $n = 114$ on either sample (HF-02). We tested that shape on the independent cap-81 trajectories, both receivers, all six arms complete (C81-02).

**It does not reproduce.** On cap-25 the untailored-minus-tailored gap runs −4.12, −0.06, +2.46 pp, monotone, ending with the untailored receiver ahead. On cap-81 it runs **−2.76, +0.31, −1.80 pp** on `goal_pass` (TGC 0.00, +1.75, −4.39): non-monotone, and ending with the **tailored** receiver ahead. All six cap-81 intervals include zero.

The depth effect itself replicates on both receivers of the second sample — the tailored span $m = 6 \rightarrow 11$ is +6.34 pp `goal_pass` (scenario [+0.28, +12.94]) and +14.04 pp TGC ([+3.51, +26.32]), both excluding zero. What fails to replicate is the ordering at the deep end.

We therefore demote "depth substitutes for tailoring" from a finding to **an observation made on one planner sample and not reproduced on a second**. What survives: both tailoring and depth raise the shallow end; no within-depth receiver gap is resolved on either sample; and the deep-end ordering is not stable across samples. ⚠ This is equally not evidence *against* substitutability — the intervals are ±5–11 pp wide and would not resolve the 2–4 pp effects at issue. The claim is simply not robust enough to carry weight.

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


### 9.2 Tailoring Does Not Transfer to the Second Family, and the Reason Is Measurable

The second family was also evaluated *tailored*, using an adapter trained on the identical 497-row dataset (`sha256 f2f439d9…`), the identical recipe, and the identical hyperparameters as the Granite adapter. That arm does **not** give the second family the floor it was run to provide, and the reason is specific enough to state (QWEN-06).

The tailored Qwen one-plan floor scores **0.2583** `goal_pass` / **0.0088** TGC, against the zero-shot Qwen floor's 0.2481 — a gain of about one percentage point, where the same recipe lifts Granite's one-plan floor by roughly **43 pp**. It ends **105 of 114 episodes on the step limit**.

Three candidate explanations were tested; two are excluded by measurement.

1. **The adapter was not applied.** False. `run_start` records `adapter_name: sft_b_plus_qwen8b`, and the tailored and zero-shot `prefix_m6` arms are *not* per-episode identical — 67/114 share a step count, 78/114 a `goal_pass` — with arm means 0.4803 against 0.4491. The adapter is loaded and it changes behaviour.
2. **A train/serve prompt mismatch.** Real, but not the cause (QWEN-07). Training renders conversations with `apply_chat_template(..., add_generation_prompt=False)` and passes no `enable_thinking` (`src/sidekick/training/sft_data.py:349`, `:489`), while Qwen3's template appends `<think>\n\n</think>\n\n` to the generation prompt exactly when `enable_thinking` is defined and false — which the eval configs pass. The adapter was therefore trained to act at position 0 of the assistant turn and served being asked to continue after a scaffold it never saw, a shift landing precisely where the decision to stop is made. Granite's template defaults the variable instead, so the two families are not affected alike. We ran the A/B: the same adapter, served with `chat_template_kwargs` removed so the prompt is byte-identical to training. It changes nothing that matters — 108/114 episodes still exhaust the step limit, `goal_pass` moves to **0.2484**, and terminal actions rise only from 0/4,385 to **3/4,431**. The defect is worth repairing; repairing it would not have rescued the arm.
3. **The training signal for termination is thin, and acquiring it is family-dependent.** This is what survives. Across the 497 rows there are 6,767 assistant targets, of which only **165 — 2.44% — are the terminal action**, appearing in 33.2% of rows; masking is sound (`n_dropped_fully_masked_before_truncation: 0`). Granite acquires the convention at almost exactly the rate it is taught, emitting the terminal action in **64 of 2,130** executor actions (**3.00%**) against a 2.44% training rate. Qwen emits it in **0 of 4,385** (0%), and 3 of 4,431 (0.07%) once the template is corrected.

This sharpens rather than contradicts §9.1. That section observed that Qwen emits the terminal action only after seeing format demonstrations in context. The tailored arm shows that **supervised fine-tuning at this data scale does not substitute for those demonstrations in this family**: the convention is acquired in-context and not by fine-tuning, while the same fine-tuning teaches it to Granite.

The $m = 11$ half of the A/B measures that contrast directly, and it is the sharpest evidence we have for it. The same adapter under the same corrected prompt scores 0.7367 with a prefix, statistically indistinguishable from the 0.7370 of its scaffolded counterpart — so the template again makes no difference. But the *action mix* does: with a replayed prefix in context the model emits the terminal action **13 times in 891 executor actions (1.46%)**, against 0.07% on the bare floor. A twenty-fold change in the rate of the very behaviour fine-tuning failed to install, produced by nothing but an in-context demonstration. Where the two channels differ is itself a result, and it is consistent with the paper's larger finding that what the prefix supplies is information the receiver can act on immediately.

Two consequences follow, and we hold to both. First, the tailored Qwen floor measures step-limit exhaustion rather than task competence, exactly as QWEN-02 and QWEN-03 record for the zero-shot floor, so **no floor-relative tailoring claim may use it as a denominator**. Second, the tailored Qwen depth curve — 0.4803, 0.6437, 0.7370 at $m = 6, 9, 11$ against the zero-shot 0.4491, 0.7017, 0.7306 — has a receiver gap that is non-monotone and *negative* at $m = 9$, and we report it as confounded by the termination failure rather than as a second-family tailoring result. Enriching the terminal-action share of the training set would plausibly fix this, but it would change the recipe and so destroy the like-for-like comparison with Granite that is the entire purpose of the second family. We record it as future work and do not claim it.

What does survive from this family is the claim §9 actually makes: the **depth** effect replicates in a second executor family, within prefix arms where format demonstrations are common to every arm and difference out. Tailoring does not transfer; depth does.

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
3. **Cap-81 Ceiling Inversion (CEIL-01, CEIL-04):** Extending planner call cap from 25 to 81 calls resulted in lower performance: `ceiling_cap81` scored **0.7637 `goal_pass` / 0.5702 TGC** vs. **0.8284 / 0.6842** for `ceiling_cap25` (paired difference **−6.47 pp `goal_pass`**, scenario [−11.68, −1.37], task [−12.48, −0.46]; TGC **−11.4 pp** [−21.05, −1.75]). Cap-81 episodes averaged 16.35 actions (max 40) vs. 13.42 for cap-25 (max 24), demonstrating that unconstrained budget allows over-acting in the tail, corrupting environment state. A third cap-81 planner sample (CEIL-06) closes the "one unlucky draw" reading: per-seed `goal_pass` is 0.8253 and 0.8315 at cap 25 against 0.7700, 0.7574 and 0.7819 at cap 81, so **the lowest cap-25 sample exceeds the highest cap-81 sample by 4.34 pp and the two families do not overlap across five samples**, with a within-cap spread of 0.62 pp and 2.45 pp respectively. Two and three samples are a spread across what we have, not a variance estimate.
4. **Qwen Floor Format Confound, Zero-Shot *and* Tailored:** Zero-shot Qwen3-8B fails to emit termination tokens without in-context demonstrations, invalidating floor-relative lift claims (QWEN-02, QWEN-03). The tailored Qwen floor is confounded the same way and for a reason we can name (QWEN-06, §9.2): the terminal action is only 165 of 6,767 supervised targets (2.44%), Granite acquires the convention at 3.00% of its actions while Qwen emits it at 0–0.07%, and 105 of 114 tailored episodes end on the step limit. Neither Qwen floor may serve as a denominator, and the tailored Qwen depth curve is reported as confounded rather than as a second-family tailoring result.
5. **Receiver Interaction Resolved at One Depth Only (DID-01, NARR-04):** Our central mechanism
   reading — that receiver tailoring is what permits narration to substitute for execution — is now
   tested as a difference-in-differences with an interval rather than by comparing which paired
   contrasts resolve (§6.1). It resolves at $m = 11$ (+6.09 pp, scenario [+1.56, +11.00], task
   [+0.63, +11.85]; TGC +12.28 pp [+0.88, +26.32]) and at neither $m = 6$ (+4.45, spans zero) nor
   $m = 9$ (−0.16). Three depths and two metrics were examined and one cell resolves, so the claim
   we make is "the interaction is resolved at $m = 11$", not "the interaction holds"; it is
   exploratory rather than confirmatory, and a confirmatory read would need to register that single
   depth in advance.
6. **Tailoring × Depth Is Unresolved, Not Absent (DID-02, C81-02):** The monotone decay of the
   receiver gap with depth, on which the depth-substitutes-for-tailoring reading rests, does not
   reproduce on an independent planner sample, where the sequence is non-monotone and ends with the
   opposite ordering. The corresponding difference-in-differences is now measured on both samples and
   resolves on neither: cap-25 **−2.53 pp** (scenario [−7.66, +2.53]) against cap-81 **+2.10 pp**
   ([−4.71, +9.01]) — opposite in sign, both spanning zero. The honest statement is that an effect of
   this size is **unmeasurable at $n = 114$**, not that it is absent, and the paper does not explain
   the crossover it cannot resolve.
7. **Deviation from a Frozen Pre-Registration (CHAN-PRICE-02):** H2's cost prediction P4 specified
   non-cached planner tokens in [300k, 700k]; the arm spent 1,414,410. The remedy attached to a P4
   failure is written for the opposite case, an arm priced *below* the action channel's budget, in
   which case the primary contrast must be reported as untested. We judged that remedy inapplicable
   because the arm was priced far above the budget rather than below it, and we report the primary
   contrast as supported. We flag this as a deviation rather than absorbing it, and direct a reader
   who declines the judgement to the matched-trigger result in Section 4, which carries no budget
   question.
8. **Test Suite Collection Defect Found Late:** For six days the project's configured test command
   (`pytest tests/`, via `testpaths`) aborted during collection: two directories contained a test
   module of the same basename with no package marker, so the second import collided with the first.
   Test runs during that period executed the unit directory alone, and the 34 integration tests were
   silently outside every reported pass count. Repaired by renaming; the full tree now reports 625
   passed, 1 skipped. No result in this paper depends on the integration tests, but the episode is
   recorded because a green suite that is not running everything is exactly the failure mode this
   project's analysis defects share.
9. **Analysis Defects Found and Repaired:**
   - *Terminal Guard Defect (GUARD-01, MECH-01..03):* Early runs allowed actions following replayed completion tokens; resolved by adding a fatal post-prefix terminal check.
   - *Handoff Flag Path (MECH-02, GUARD-01/X33d):* The mechanism script initially inspected an invalid JSON key; resolved by aligning paths and making zero-count populations fatal.
   - *Error Scan Actor Filter (MECH-04, MECH-05):* Initial audits filtered observations on executor identity, yielding 0.00% error rates; repaired to scan observation return text.
   - *Adapter Build Mismatch (ADV-FC-02):* Initial H1 advice contrasts paired against an older 0.7000 adapter build; corrected to use the standard 0.7181 `iaware` build.
   - *Cost Token Pricing (COST-01):* Local executor tokens were initially passed to hosted pricing calculators; corrected to filter exclusively on hosted usage events.
   - *Segmented Fit Float Tie-Breaking (TIEBREAK-01):* Exact RSS float comparisons in segmented regression produced spurious breakpoints on straight lines; resolved via scaled RSS tolerances.

---

## 12. Conclusion

When pairing a strong hosted planner with a small local executor on complex interactive environments, communication bandwidth is best spent as concrete action prefixes rather than natural-language advice. At a matched trigger and matched context, action execution dominates prose critique on quality and on all three cost axes simultaneously, and prose does not catch up when bought at 3.2× the token budget. The benefit of a prefix accumulates across a span of depths rather than at a threshold, and it operates primarily through informational demonstration rather than environment mutation: narrating the planner's actions into a fresh environment recovers most of the effect, and at $m = 11$ how much it recovers depends measurably on whether the receiver was trained on that planner's trajectories.

Two boundaries are worth stating beside the result. The depth effect replicates in a second executor family, but the fine-tuning recipe does not — the second family never acquires the harness's terminal convention from a training set in which it is 2.44% of the targets, while the first acquires it at the rate it is taught. And every number here is one environment, one planner model, and the development split; the confirmatory read is registered and not yet run.

---

---

## Appendix A. Reproducibility

Every number in this paper is produced by a script from a campaign directory of per-episode
`result.json` files, and is recorded in `docs/claims_ledger.md` with the report path and the JSON key
it came from. `scripts/analysis/preprint_number_audit.sh` enforces this mechanically: it takes the set
difference between the figures printed here and the figures in the ledger, and fails if the paper
claims anything the ledger cannot source. It exits 0 on this draft over 77 percentage-point figures
and 83 four-decimal rates.

That check exists because of a real failure. A worker drafting the cost table invented three of its
eleven TGC values — one a fill-down of the row above, one wrong by 10.52 pp — while reporting zero
outstanding work, and the entire `goal_pass` column beside them was correct, so nothing looked wrong
(QUAL-03). An instruction to flag uncertain values cannot catch that, because a model that does not
know it is guessing cannot comply with it. A set difference can, and did.

### A.1 Figures

No figure is drawn from retyped numbers. `scripts/analysis/figures.py` reads each series out of a
report by key, and refuses to render a panel whose key is missing rather than silently omitting it
(FIG-01). `paper/figures/figures_manifest.json` records, for every figure, its source reports and the
exact keys.

| Figure | Source report(s) |
|---|---|
| F1 depth curve | `hj13_shape_post_guard_bands`, `hj12_unified_frontier_scenario`, `hj13_ceiling_cap25_vs_cap81`, `hj13_zeroshot_depth_m6_m9`, `hj13_zeroshot_depth_m9_m11` |
| F2 channel at matched budget | `hj12_unified_frontier_scenario`, `hj13_advice_fullctx_matched` |
| F3 tailoring gap | `hj13_receiver_contrast_m6` / `_m9` / `_m11` |
| F4 mechanism | `hj13_mechanism_zeroshot_20260923c` |
| F5 second family | `hj15_qwen_curve` |
| F6 narrated vs executed | `hj16_narrated_tailored_complete`, `hj16_narrated_untailored_complete` |
| F7 narrated minus executed | `hj16_narrated_curve_bplus`, `hj16_narrated_curve_zs` |
| F8 advice cost vs quality | `hj13_advice_at_price`, `hj13_advice_at_price_cost` |

All report files carry the `_20260923` or `_20260924` suffix and live under `campaign/results/`.

### A.2 Models, adapters and decoding

| role | model | adapter |
|---|---|---|
| Planner | `gpt-5.6-luna`, `reasoning_effort: medium`, frozen for the whole campaign | — |
| Executor, tailored | `ibm-granite/granite-4.2-8b` | `sft_b_plus_iaware_granite8b` |
| Executor, untailored | `ibm-granite/granite-4.2-8b` | none (`lora_name: null`) |
| Executor, suffix-trained | `ibm-granite/granite-4.2-8b` | `sft_b_plus_handoff_granite8b` |
| Second family, tailored | `Qwen/Qwen3-8B` | `sft_b_plus_iaware_qwen8b` |
| Second family, untailored | `Qwen/Qwen3-8B` | none |

Both tailored adapters were trained on the identical file
`sft_b_plus_iaware_20260920.jsonl` (`sha256 f2f439d9…`, 497 rows, 6,767 assistant targets), LoRA rank
64 / alpha 128, two epochs, `max_length` 32768, bf16, on an H100. Decoding is temperature 0.7,
`max_tokens` 2048, with stop sequences ending generation at the close of the first action.

⚠ **An untailored arm must be configured under the `prompt_only` system, never under `sft_plan`.**
`SftPlan.policy_defaults` sets `adapter_name: "sft_plan"` (`src/sidekick/policies/sft_plan.py:18`), so
an untailored config placed under `sft_plan` silently receives the base model while every log line
still names the alias (`src/sidekick/runner.py:256-258`). The arm then measures a configuration no one
intended and returns entirely plausible numbers.

### A.3 Pre-registration

| document | scope |
|---|---|
| `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md` (+ amendment) | the original protocol and the pilot |
| `docs/prereg_j9_freeze_20260920.md` | the freeze, including the one-read rule for the test split |
| `docs/prereg_hj12_dev_20260922.md` | the dev frontier and its gates |
| `docs/prereg_hj13_shape_20260923.md` | the depth-shape hypotheses, the replicate floor and the kill conditions |
| `docs/prereg_h2_advice_at_price_20260923.md` | advice bought above the action channel's price |
| `docs/prereg_j10_amendment_20260924.md` | the registered confirmatory read, **not yet run** |

Registered text is amended by appending, never by editing what it already says; the amendment record
in each document is the audit trail. Where we departed from a frozen document we say so in
§11 rather than absorbing it — see item 7, a prediction whose attached remedy did not fit the
direction in which it failed.

### A.4 Statistical protocol

Contrasts are paired on `(task_id, seed)` and bootstrapped over **clusters**, not episodes: 10,000
percentile draws, scenario-clustered as primary and task-clustered reported beside it, because the 57
dev tasks form only 19 scenario groups and tasks within a scenario are not independent. A crashed
episode scores 0 under the all-episodes population; `error_type == "limit"` is not a crash and keeps
its recorded score. Difference-in-differences contrasts are formed **per episode** before averaging,
so the pairing between the two gaps survives into the bootstrap (§6.1).

### A.5 Provenance and what is not yet automated

The results in this draft were produced at commit `c448a8d` of the analysis tree. ⚠ Per-episode
`result.json` files do **not** yet carry the git SHA of the code that produced them, so provenance is
established at campaign granularity through `campaign/RUNS.md` rather than per episode. That is a
known gap, it is tracked, and it is the one piece of the reproducibility story we cannot currently
check mechanically.
