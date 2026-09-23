---
title: "Steering Local Agentic Executors via Action Prefixes: Prefix Depth, a Channel Comparison, and Mechanism on AppWorld"
date: "2026-09-23"
author: "Sidekick Research Group"
abstract: |
  We study how to spend a strong hosted planner's budget (GPT-5.6 Luna) on a compact local executor (IBM Granite 4.2 8B) in AppWorld, using paired, cluster-bootstrapped contrasts on the dev split only (57 tasks). Handing control to the executor after $m$ replayed planner actions helps across a span of depths with no localizable breakpoint: from $m = 6$ to $m = 11$ over 171 pooled pairs, `goal_pass` rises +7.70 pp on the untailored receiver (scenario 95% CI [+3.69, +12.06]) and +8.39 pp on the tailored one, yet no adjacent step survives Holm correction and the registered threshold test fails. Against a cap-81 planner-alone ceiling, three of four $m = 11$ arms are non-inferior on both metrics within the registered 7.00 pp margin; against the higher-scoring cap-25 ceiling none is on TGC. At a matched trigger, executed planner actions beat advice written under the registered correction prompt by +6.13 pp over 171 pairs ([+0.75, +12.71]; significant under the registered percentile bootstrap, stable across seven bootstrap seeds; an exact cluster randomization test gives $p = 0.063$), but a neutral advice prompt recovers about three-fifths of that gap (+3.73 pp, [−0.06, +8.24]). A pre-registered decomposition of the gap is unresolved. Mechanistically, deeper prefixes front-load API discovery and suppress compounding errors.
---

# Steering Local Agentic Executors via Action Prefixes: Prefix Depth, a Channel Comparison, and Mechanism on AppWorld

## 1. Introduction

Language agents in digital environments must navigate long horizons, discover multi-application APIs and maintain coherent state. Frontier models plan well but are expensive and privacy-sensitive to run as interactive loops; compact local models (e.g., 8B open weights) are cheap, yet compound errors and explore poorly when deployed alone. Hybrid systems pair a small local executor with a strong hosted planner, which raises the question: **through which channel, and at what depth of intervention, should the hosted budget be spent?** Existing approaches typically use the hosted model as a critic or upfront planner emitting natural-language advice or plans.

In this work, we show that on AppWorld, at a matched trigger and matched context, spending hosted budget as concrete, executable **action prefixes** scores higher than advice written under our registered correction prompt and, as point estimates, costs less in non-cached tokens, provider dollars and hosted calls; of the three cost differences only the dollar saving is itself resolved (§4). A neutral advice prompt recovers about three-fifths of that gap (§3.1), so we claim only that actions beat the registered advice prompt. We do not measure wall-clock latency and make no claim about it.

Every number below traces to a claims ledger (`docs/claims_ledger.md`) that records its source report and JSON key and whether the contrast was registered in advance; exploratory results are marked as such.

- **Actions beat the registered advice prompt at a matched trigger (registered; CHAN-C1-02, DEC-02, DEC-03, COST-01).** At $k = 10$ with full transcript context, action takeover beats advice written under the registered correction prompt by +6.69 pp on `goal_pass` (scenario 95% CI [+1.29, +13.48]; exact 19-scenario randomization test $p = 0.0469$, ROB-02; the TGC version does not survive it), at no greater point-estimate cost on any axis. At 171 pairs the gap is +6.13 pp ([+0.75, +12.71]; exact test $p = 0.063$), and a neutral advice prompt recovers about three-fifths of it (+3.73 pp, [−0.06, +8.24]).
- **The gap's decomposition is unresolved (registered B2; DEC-01 to DEC-04).** Showing the planner's action without executing it (0.7516) or requesting advice under a neutral prompt (0.7658) lands between registered advice (0.7285) and takeover (0.7899); no registered decision rule fires (§3.1).
- **Registered-prompt advice bought above the action channel's price (registered primary H2; CHAN-PRICE-01).** Advice at every step spends 1,414,410 non-cached tokens and 19.02 hosted calls per episode — 3.2$\times$ and 1.7$\times$ the deepest action prefix — and still scores 14.68 pp lower on `goal_pass` (scenario [−22.09, −7.04]).
- **Live takeover matches oracle replay (exploratory; CHAN-C1-03)** at $m = 9$ (+1.55 pp, scenario [−3.46, +7.04]) and $m = 11$ (−0.91 pp, [−6.74, +5.94]).
- **Depth helps across a span; no breakpoint can be localized (MULT-01, F1-RESULT-01..04, ROB-15; SHAPE-10 exploratory).** Untailored `goal_pass` rises +10.21 pp from $m = 6$ to $m = 9$ ([+2.60, +18.20]) and TGC +16.67 pp ([+5.26, +28.07]), but no adjacent step survives Holm correction, the registered threshold test S3 fails, and the prefix arms alone fit a straight line at +1.43 pp per step ([+0.80, +2.04]).
- **What the prefix conveys depends on the receiver (exploratory; NARR-03, NARR-04, DID-01).** Narrating the planner's actions into a fresh environment matches execution at every depth on the tailored receiver (−2.51, −1.84, −0.49 pp at $m = 6, 9, 11$), while on the untailored receiver execution wins at $m = 11$ by 6.58 pp ([−9.98, −3.64]); the difference-in-differences resolves at $m = 11$ only (**+6.09 pp**, scenario [+1.56, +11.00], task [+0.63, +11.85]).
- **Depth replicates in a second family; the fine-tuning recipe does not (QWEN-03, QWEN-04, QWEN-06).** Zero-shot `Qwen/Qwen3-8B` rises from 0.4491 to 0.7306 `goal_pass` between $m = 6$ and $m = 11$, but the recipe that lifts Granite's one-plan floor by ~43 pp moves Qwen's by ~1 pp.
- **What does not hold up (C81-02, ESC-01).** A receiver-gap pattern suggesting that depth substitutes for tailoring does not replicate on a second planner sample, and registered selective escalation is a null (§2.3).

---

## 2. Experimental Setup

### 2.1 Benchmark and Interaction Loop

We evaluate on AppWorld, nine day-to-day applications accessed through APIs, in which agents write and execute Python code that inspects and mutates state across applications. We use a minimal interaction harness that isolates the steering channel from scaffold effects (`docs/limitations_external_20260923.md`): the agent emits code blocks executed against the live environment, and outputs, errors and return values are appended to the transcript.

### 2.2 Models and Roles

- **Hosted Planner:** `gpt-5.6-luna` at `model_reasoning_effort: medium` with frozen prompt hashes, the source of every plan, advice critique, live takeover and replayed prefix.
- **Local Executors:** The primary local executor is `ibm-granite/granite-4.2-8b`, evaluated under three configurations: (1) **untailored zero-shot** (base weights, `lora_name: null`); (2) **tailored** (`sft_b_plus_iaware_granite8b`, the adapter every tailored arm loads, LoRA-trained on 497 rows built from the same hosted planner's solved trajectories on the 90-task AppWorld train split plus post-intervention turns, with the planner's `INTERVENTION:` turns retained; Appendix A.2); and (3) **handoff-suffix trained** (`sft_b_plus_handoff_granite8b`, trained on 615 trajectory suffixes aligned to handoff cut points; DATA-01, HF-TRAIN-01). As a secondary model family, we evaluate zero-shot `Qwen/Qwen3-8B`.

### 2.3 Steering Channels and Handoff Paradigms

We compare four interaction paradigms:
1. **Autonomous Floor** (`executor_alone`): the executor acts alone from step 0.
2. **One-Plan Floor** (`plan_only` / `sft_plan`): the planner writes a natural-language plan at step 0 and the executor acts alone thereafter.
3. **Prose Advice Channel** (`advise_fixed_k`): every $k$ steps the planner reads the transcript and injects a prose critique, either context-starved (an 8-line window) or with the full transcript (`advise_fixed_k_10_fullctx`).
4. **Action Prefix and Takeover Channel:** the planner acts in the environment. A **replayed prefix** (`prefix_m`) replays the first $m$ actions of a recorded planner trajectory, with a post-prefix terminal guard if the task has already finished (GUARD-01); **live takeover** (`takeover_fixed_k_10`) calls the planner online at step $k = 10$ for an action that is executed before control returns to the executor.

**Why every trigger is fixed.** The original primary hypothesis (H2b, `docs/prereg_v1.md`), that a learned gate could call the planner selectively, is a registered null on dev (ESC-01; `docs/prereg_j9_freeze_20260920.md` §6, claim 4): neither the linear verifier head nor the sequential router discriminates the decision points where intervention was needed (scored AUROCs 0.3867–0.5082), and the executor's self-gate probability $p_{\text{ask}}$ never exceeds 0.0347 against thresholds of 0.3–0.7, so the self-gated arms never escalated. Every channel below is therefore triggered on a fixed schedule or replayed to a fixed depth.

### 2.4 Metrics, Dataset Scope, and Statistical Estimation

- **Metrics:** `goal_pass_rate` (`goal_pass`, the fraction of required task assertions satisfied) and **Task Goal Completion (TGC)**, a strict binary metric requiring every goal requirement and state check to pass.
- **Dataset Scope:** the AppWorld **dev** split, 57 tasks × 2 seeds ($n = 114$ paired episodes in 19 scenario groups; 3 multi-party synchronization tasks excluded at environment setup; `docs/limitations_external_20260923.md`).
- **Bootstrap Protocol:** 10,000 paired percentile bootstrap draws, reporting **scenario-clustered** (primary) and **task-clustered** 95% intervals.
- **Small-Cluster Robustness:** Because 19 clusters are few for a percentile bootstrap, headline contrasts were also tested with an exact scenario sign-flip randomization test and wild cluster bootstrap intervals (ROB-01; Appendix A.4); we report where a verdict depends on the method.
- **Non-Inferiority Margin:** the pre-registered $\delta = 7.00$ percentage points (pp) against planner ceilings.

#### Trajectory Sourcing

Every prefix arm in this paper *replays* its prefix from a recorded planner campaign rather than calling
the planner online. After handoff the executor may still ask the planner; in six arms (Appendix A.5)
hosted luna answered 1–31 such asks per arm, and the headline depth curves contain none. Replay is what removes planner sampling noise from the depth curve — measured at 0.04 pp of
executor-side replicate variation against 6.47 pp between two planner runs (CEIL-08) — and it is what
makes the receiver comparisons exactly paired, since both receivers consume byte-identical prefixes.

The cost is that a prefix arm and a ceiling arm are trajectory-paired only if they replay the **same**
campaign. We run two planner samples, capped at 25 and at 81 calls; a cap-25-sourced prefix compared
against the cap-81 ceiling is paired **by task, not by trajectory**. We state each arm's source campaign
wherever it matters, and §5.3 reports a ceiling claim that does not survive being measured like-for-like.

---

## 3. Actions Versus Advice at a Matched Trigger

We examine the pre-registered primary channel contrast C1 (CHAN-C1-00, CHAN-C1-02): live action takeover (`takeover_fixed_k_10`) against full-context advice (`advise_fixed_k_10_fullctx`), which the planner writes under the registered correction prompt ("The executor needs a correction. Reply with concise correction text only."). The arms share the trigger ($k = 10$), the cached initial plan, the executor and adapter, and the full transcript given to the planner (CHAN-C1-00).

Takeover scores 0.8007 `goal_pass` against advice's 0.7339 (TGC 0.5175 vs. 0.4386), a paired difference of **+6.69 pp** (scenario 95% CI **[+1.29, +13.48]**, task **[+1.47, +12.35]**; CHAN-C1-02). Both intervals exclude zero under 10,000 bootstrap draws, so at the pre-registered trigger actions beat the registered advice prompt; a neutral prompt recovers about three-fifths of the gap (§3.1).

The `goal_pass` result also survives an exact randomization test over the 19 scenario clusters, though narrowly ($p = 0.0469$; wild cluster bootstrap [+0.88, +12.48]; ROB-02), so we describe it as significant under both the percentile bootstrap and an exact cluster randomization test rather than as robust. Its TGC companion (+7.89 pp) fails the exact test ($p = 0.0781$), and scenario goal completion does not resolve (ROB-11).

**Extension to 171 pairs (DEC-02).** A third seed adds 57 pairs with plan packets from the cap-81 rather than the cap-25 planner campaign; seeds 1–2 are CHAN-C1-02's pairs, so this is an extension, not a replication. The gap is **+6.13 pp** (scenario [+0.75, +12.71], task [+0.97, +11.73]; TGC +5.26 pp [−0.58, +12.28]): significant under the registered percentile bootstrap, stable across seven bootstrap seeds; an exact cluster randomization test gives $p = 0.063$. A neutral advice prompt recovers +3.73 pp of it (§3.1).

Live takeover is indistinguishable from oracle prefix replay, which needs recorded traces (CHAN-C1-03, exploratory: **+1.55 pp** [−3.46, +7.04] at $m = 9$, **−0.91 pp** [−6.74, +5.94] at $m = 11$). Registered advice's weakness is not context starvation (ADV-FC-01, ADV-FC-02): full-transcript minus 8-line-window advice is **+3.74 pp** ([−1.39, +9.13]), and full-context advice exceeds the plan floor (0.7181) by only **+1.57 pp** ([−2.91, +5.91]) against takeover's **+8.26 pp** ([+3.84, +13.11]; Figure F2).

### 3.1 Decomposing the Gap (B2, pre-registered)

Takeover differs from registered advice in content (an action), in execution, and in prompt: advice is requested under a prompt that presumes an error and caps length. B2 (`docs/prereg_c1_decomposition_20260923.md`) adds two arms at the same trigger and context: **S** shows the planner's action, from takeover's byte-identical act prompt, as advice text and never executes it; **N** requests advice under a neutral prompt. With takeover (**T**) and registered advice (**A**), all four arms have 171 pairs over seeds 1–3 and no crashes (DEC-01).

Table 1a: The B2 decomposition ($n = 171$ paired; `goal_pass`; scenario 95% CI; Holm over D1–D4).

| Arm | `goal_pass` | Contrast | Difference | Scenario 95% CI | Holm $p$ |
|---|---|---|---|---|---|
| T, takeover | 0.7899 | D0 = T − A | +6.13 pp | [+0.75, +12.71] | — |
| A, registered advice | 0.7285 | D1 = T − S (execution) | +3.83 pp | [−1.56, +10.81] | 0.5976 |
| S, action shown, not executed | 0.7516 | D2 = S − A (prompt + content) | +2.30 pp | [−2.43, +7.31] | 0.7208 |
| N, neutral advice | 0.7658 | D3 = N − A (prompt) | +3.73 pp | [−0.06, +8.24] | 0.2192 |
| | | D4 = T − N | +2.40 pp | [−2.94, +8.89] | 0.7208 |

No registered decision rule fires (DEC-01). *Prompt artefact* needed D4's interval to include zero (held) and D3's to exclude it (lower bound −0.06); *execution matters* and *content, not execution* needed D1's and D2's to exclude zero (−1.56, −2.43). The outcome is **unresolved**; we make no decomposition claim. The D3 near miss is stable: its lower bound is below zero at all seven POOL-04 seeds, and the exact sign-flip test gives $p = 0.1089$ (DEC-03).

The neutral prompt alone recovers +3.73 of the +6.13 pp, about three-fifths; takeover's remaining lead over it does not resolve, and on TGC it is −0.58 pp ([−8.77, +7.02]). The executor seldom copies a shown action (exploratory): 38 of 228 were reproduced verbatim as its next action (0.1667), and 182 of 213 shown code actions were not (DEC-04).

**Reading.** The registered advice prompt, not the channel alone, may carry much of the takeover−advice gap; these data cannot apportion it.

---

### 3.2 Advice at the Action Channel's Price

The obvious objection is that the action channel simply buys more planner effort. We
pre-registered a test of it (`docs/prereg_h2_advice_at_price_20260923.md`): the arm
`advise_fixed_k_1_fullctx` reviews the executor's work at **every step** with full context, ten times
the review frequency of the $k = 10$ advice arm. Like every advice arm here it uses the registered
correction prompt, so this and all our advice comparisons are conditional on that prompt; at $k = 10$ a
neutral prompt closes about three-fifths of the takeover−advice gap (§3.1), and neutral advice was not
run at $k = 1$.

Table 1b: Advice bought at the action channel's budget (n = 114 paired, scenario 95% CI).

| Arm | `goal_pass` | Non-cached planner tokens / episode | Hosted calls / episode |
|---|---|---|---|
| `advise_fixed_k_10_fullctx` | 0.7339 | 49,819 | 2.46 |
| `advise_fixed_k_1_fullctx` | **0.6630** | **1,414,410** | **19.02** |
| `prefix_m9` | 0.7852 | 357,448 | 9.77 |
| `prefix_m11` | 0.8098 | 443,361 | 11.25 |

Advice at every step consumes **3.2× the non-cached tokens** and **1.7× the hosted calls** of the deepest
action prefix, and scores **14.68 pp lower** on `goal_pass` (scenario [−22.09, −7.04], task
[−21.56, −7.79]) and 15.79 pp lower on TGC ([−28.07, −3.51]).

Three of the four registered predictions held. **P1** (advice minus the one-plan floor includes zero) held
at −5.51 pp ([−13.15, +2.51]), though the registered *point* prediction of [−2, +5] pp was missed on the
low side. **P2** (advice minus `prefix_m11` negative, excluding zero) held, also under the exact sign-flip
test ($p = 0.0024$) and both wild intervals (ROB-03). **P3** (ten times the review frequency does not buy
quality) held on the registered scenario clustering at −7.08 pp ([−14.78, +0.67]) under every inference
method (ROB-04; task-clustered detail in Appendix A.4). **P4 failed**: it predicted non-cached tokens in [300k, 700k], and the arm spent
1,414,410; we report P2 as tested and flag that judgement as a deviation (CHAN-PRICE-02; Appendix B.1).
**Figure F8** places all four arms on cost and quality axes.

By the prereg's own decision rule, P1 and P2 both holding establishes the claim at matched budget:
**advice under the registered prompt does not reach the action channel's quality even when priced at or
above it, so the gap is not a budget effect.** Whether it is a channel effect is what §3.1 leaves unresolved.

---

## 4. Cost on Three Axes

We price every arm in three currencies: non-cached input/output tokens, provider dollars under published price cards, and hosted API calls (COST-01, COST-02, COST-03).

On the registered matched-trigger pair takeover scores above registered advice and, as point estimates, is cheaper on all three axes (COST-01): per episode, `takeover_fixed_k_10` spends 41,464 non-cached tokens against 49,819 for `advise_fixed_k_10_fullctx`, $0.004820 against $0.005494, and 2.316 hosted calls against 2.465. Paired intervals resolve only the dollar saving (ROB-18): −8,356 non-cached tokens [−17,744, +617], −$0.000674 [−0.001361, −0.000024] (scenario clustering only) and −0.149 hosted calls [−0.368, +0.070]; takeover also uses fewer local executor tokens (−65,070 [−107,348, −23,744]). At 171 pairs (DEC-05; point estimates only) takeover is still the cheapest of B2's four arms in non-cached tokens (41.8k against 53.2k for registered advice) and dollars ($0.00478 against $0.00578), while neutral advice, which recovers about three-fifths of the quality gap (§3.1), makes marginally the fewest hosted calls (2.29 against 2.33).

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

Cost ordering is consistent across currencies (COST-02) except that takeover costs slightly more dollars than starved-context advice ($0.004820 vs. $0.004386) while spending fewer tokens (41,464 vs. 43,823) and calls (2.32 vs. 2.42). `advise_fixed_k_3` ran only with the starved context, so its −1.33 pp against `prefix_m6` ([−8.02, +5.44]) confounds depth with starvation and is no fair version of §3.2's test (ROB-20).

Non-inferiority (NI) to the cap-81 planner ceiling (`ceiling_cap81`, 0.5702 TGC) under the registered 7.00 pp margin is **currency-invariant** (COST-03): the same two arms pass under all three cost axes. Reported as arm minus ceiling, `prefix_m11` scores **+3.51 pp** on TGC (scenario 95% CI [−6.14, +13.16], task [−5.26, +12.28]) while saving 716,854 non-cached tokens ([−1,314,868, −292,751]), $0.0217 ([−0.0390, −0.0094]) and 6.10 hosted calls ([−9.25, −3.34]) per episode; `ceiling_cap25` also passes (+11.40 pp, [+1.75, +21.05]). NI fails for `prefix_m9` (−0.88 pp, [−9.65, +7.89]) because its lower bound falls below −7.00 pp, an interval-width failure rather than a degraded point estimate: NI is not established at $m = 9$, which is not the same as $m = 9$ being inferior. Two qualifications apply (ROB-05, ROB-21). The `prefix_m11` TGC lower bound (−6.14) is stable across bootstrap seeds but, TGC being discrete, one attainable value from failing, and an exact one-sided sign-flip test of NI gives $p = 0.0264$, just above the 2.5% level. Against the higher, trajectory-paired cap-25 ceiling the same arm fails TGC NI (−7.89 pp [−17.54, +2.63]); §5.5 gives both ceilings.

---

## 5. Prefix Depth: A Rise Across a Span, With No Localizable Breakpoint

Across the grid $m \in \{2, 4, 6, 7, 8, 9, 10, 11\}$, with the post-prefix terminal guard in place (GUARD-01), all-episodes `goal_pass_rate` is **monotonically increasing**: 0.6856 at $m = 2$, 0.7190 at $m = 4$, 0.7237 at $m = 6$, 0.7544 at $m = 7$, 0.7627 at $m = 8$, 0.7852 at $m = 9$, 0.8065 at $m = 10$, and 0.8098 at $m = 11$ (SHAPE-01, SHAPE-06). The pre-guard dip observed in pilot runs was eliminated once executor actions following replayed completion tokens were suppressed.

```
Figure F1: Goal pass rate against prefix handoff depth m for tailored and untailored receivers,
compared against the cap-25 (0.8284) and cap-81 (0.7637) planner ceilings, plan-only floor (0.7181),
and executor-alone floor (0.5289). (Referenced from paper/figures/f1_depth_curve.pdf).
```

### 5.1 Multiplicity Control and the Segmented Test

Holm-Bonferroni correction at $\alpha = 0.05$ across the eight adjacent transitions from $m0\rightarrow m2$ to $m10\rightarrow m11$ gives an **adjusted $p$-value of 1.0 for all eight** (MULT-01). Every unadjusted and adjusted interval spans zero (e.g., $m6\rightarrow m7$ [−4.35, +10.18]; $m8\rightarrow m9$ [−1.75, +7.14]; $m10\rightarrow m11$ [−3.82, +4.18]). **No individual adjacent step is statistically significant.**

The pre-registered two-phase segmented regression (F1-RESULT-01..04) gives a split verdict on all four populations and both guard settings:
- **S1 (Flatness Below Breakpoint):** Holds in 8/8 configurations; pre-break slope $\beta_1$ includes zero ($\beta_1 = -0.00125$, 95% CI [−0.00637, +0.00815] on all episodes post-guard).
- **S2 (Rise Above Breakpoint):** Holds in 8/8 configurations; post-break slope $\beta_1 + \beta_2$ is strictly positive (+0.0245 with one-sided lower bound +0.0097 on $m10$ handoff keys; +0.0241 with lower bound +0.0071 on $m11$ handoff keys).
- **S3 (Threshold Localization):** Fails in 8/8 configurations; the 95% bootstrap confidence interval for breakpoint location $\tau$ spans [4, 9] (point estimate $\tau = 8$ on handoff-pinned populations, lower bound 4.0).

The registered composite verdict is negative: S1 and S2 hold but S3 fails, so no threshold location is claimed (F1-RESULT-04). A post hoc hinge-versus-line test narrows this further (ROB-15). A hinge beats a line on the post-guard curve (null-calibrated $p = 0.036$ on scenarios, $0.054$ on tasks) only because of the plan-only $m = 0$ anchor, placing its breakpoint on the lowest candidate ($\tau = 4$, interval [4, 8]); the prefix arms alone ($m = 2$ to $11$) do not reject a line ($p = 0.79$), rising **+1.43 pp per step** ([+0.80, +2.04]), and neither handoff-pinned population rejects linearity ($p = 0.078$, $0.12$). The data therefore **cannot localize a breakpoint**, and "flat, then rising" cannot be distinguished from a steady rise; what is established is a rise across a span (§5.2). Figure F1 draws no breakpoint.

### 5.2 Span-Based Scaling and Zero-Shot Gains

Across a multi-step span the depth effect is resolved (SHAPE-10, exploratory; CHAN-ZS-04). For the untailored receiver, moving from $m = 6$ to $m = 9$ produces a **+10.21 pp** rise in `goal_pass` (0.6825 to 0.7845), with a 95% scenario-clustered CI of **[+2.60, +18.20]** (task **[+3.80, +16.81]**), and a **+16.67 pp** rise in TGC (0.3860 to 0.5526, scenario **[+5.26, +28.07]**, task **[+7.02, +26.32]**). Extending untailored zero-shot from $m = 9$ to $m = 11$ provides an additional **+4.99 pp** `goal_pass` (reaching 0.8345; task [+0.26, +9.31]) and **+7.02 pp** TGC (reaching 0.6228; scenario [+0.88, +14.04]; CHAN-ZS-04).

The span rise is not run-to-run noise: replicate evaluations differ by 0.04 pp at $m = 6$ (0.7241 vs. 0.7237; NOISE-05) and 1.82 pp at $m = 9$ (0.8033 vs. 0.7852; NOISE-03), and twice the larger, 3.63 pp, is cleared by both the 6.15 pp tailored and the 10.21 pp zero-shot rise (NOISE-03, NOISE-04).

---

### 5.3 Replication on an Independent Planner Sample

Every prefix arm above replays one planner run, the cap-25 trajectories. To test whether the effect rests on a single sample we replayed a second, independent set, the cap-81 trajectories, whose planner scores **6.47 pp below** the cap-25 planner (CEIL-07; C81-01).

The depth effect replicates. `goal_pass` runs 0.7201, 0.7650 and 0.7932 at $m = 6, 9, 11$, and TGC 0.4561, 0.5263 and 0.5526. Over the span $m = 6 \rightarrow 11$ the rise is **+7.31 pp** on `goal_pass` (scenario [+2.07, +12.80]) and **+9.65 pp** on TGC (scenario [+2.63, +16.67]), both excluding zero. As on the original curve, and consistent with MULT-01, **no single adjacent step is individually significant**: $m = 6 \rightarrow 9$ is +4.49 pp [−1.72, +11.29] and $m = 9 \rightarrow 11$ is +2.82 pp [−1.55, +7.16] on `goal_pass`.

At $m = 11$ the cap-81 prefix differs from the cap-25 prefix by **−4.13 pp**, scenario [−8.84, +0.50], task [−9.74, +1.44] — **including zero**: a materially weaker planner run yields a prefix of statistically indistinguishable value at depth 11.

The curve is **compressed rather than translated** — it starts higher (0.7201 against 0.6825 at $m = 6$) and ends lower (0.7932 against 0.8345 at $m = 11$), a span of 7.31 pp against 15.20 pp — so this replicates the *effect*, not the *curve*.

The tailored cap-81 arms (0.7477, 0.7619 and 0.8111 at $m = 6, 9, 11$) replicate the span as well; at $m = 11$ the tailored arm is unchanged by the source swap (0.8111 against 0.8098), and the receivers' ordering on the $m = 9 \rightarrow 11$ step inverts between sources (Appendix B.4).

**Like-for-like pairing with the ceiling.** The cap-81 arms also let prefix and ceiling replay the *same* planner run, and this withdraws one earlier statement. Under the mismatched pairing the untailored $m = 11$ arm appeared significantly above the cap-81 ceiling (ceiling minus arm −7.08 pp, [−12.61, −1.87]); paired on the same trajectories it is **−2.95 pp [−8.65, +1.91]**, which includes zero, and the tailored arm is −4.75 pp [−11.75, +1.16] (CEIL-05). The mismatch carried the apparent superiority; the supported statement is non-inferiority (§5.5). The channel result is unaffected: advice at every step against the cap-81-sourced tailored prefix is **−14.81 pp [−21.20, −7.96]**, against −14.68 pp under the original sourcing.

### 5.4 A Third Planner Seed

A third planner seed (CEIL-06) plus six replay arms that make no hosted calls pools the cap-81 sample to
**171** paired episodes, none dropped (POOL-01). The span survives and tightens — over $m = 6 \rightarrow 11$ the untailored receiver gains **+7.70 pp**
(scenario [+3.69, +12.06]) and the tailored one **+8.39 pp** ([+4.20, +12.63]), and both survive exact
sign-flip tests ($p = 0.0019$ and $0.0014$; ROB-06). The tailored $m = 9 \rightarrow 11$ step does not:
its interval [+0.15, +8.75] clears zero by less than the bootstrap's own Monte Carlo error, its lower
bound turns negative at one of seven bootstrap seeds (POOL-04), and the exact test does not reject
($p = 0.0749$), so we report it as unresolved. The tailoring $\times$ depth interaction also stays
unresolved (+2.81 pp, scenario [−2.57, +8.96]; POOL-03). Non-inferiority at 171 pairs and the per-seed
detail are in Appendix B.2; the seed-stability rule is in Appendix A.4.

### 5.5 Non-Inferiority Against Both Ceilings

Because the cap-81 planner scores 6.47 pp below the cap-25 one (CEIL-07), every non-inferiority verdict
depends on the ceiling; Table 4 gives both (ROB-16, ROB-21).

Table 4: Arm minus ceiling, scenario 95% CI ($n = 114$; seed 20260924). H: non-inferior (lower bound ≥ −7.00 pp); F: not. Cap-25-sourced arms are trajectory-paired with the cap-25 ceiling and task-paired with cap-81; cap-81-sourced arms the reverse.

| Arm | `goal_pass` vs cap-25 | `goal_pass` vs cap-81 | TGC vs cap-25 | TGC vs cap-81 |
|---|---|---|---|---|
| tailored $m = 11$ (`prefix_m11`) | −1.86 [−8.51, +6.09] F | +4.61 [−1.42, +11.92] H | −7.89 [−17.54, +2.63] F | +3.51 [−6.14, +13.16] H |
| untailored $m = 11$ | +0.61 [−3.66, +5.58] H | +7.08 [+1.82, +12.78] H | −6.14 [−13.16, +0.88] F | +5.26 [−4.39, +14.91] H |
| tailored $m = 9$ | −4.32 [−12.48, +4.51] F | +2.15 [−4.08, +9.77] H | −12.28 [−23.68, −0.88] F | −0.88 [−9.65, +8.77] F |
| untailored $m = 9$ | −4.39 [−9.52, +0.94] F | +2.08 [−4.39, +9.19] H | −13.16 [−21.05, −5.26] F | −1.75 [−11.40, +8.77] F |
| tailored $m = 11$, cap-81 source | −1.72 [−8.95, +6.47] F | +4.75 [−1.16, +11.81] H | −8.77 [−21.05, +3.51] F | +2.63 [−5.26, +11.40] H |
| untailored $m = 11$, cap-81 source | −3.52 [−9.78, +3.43] F | +2.95 [−1.91, +8.69] H | −13.16 [−23.68, −1.75] F | −1.75 [−7.02, +4.39] F |
| `takeover_fixed_k_10` | −2.77 [−12.34, +7.42] F | +3.70 [−5.17, +13.60] H | −16.67 [−30.70, −1.75] F | −5.26 [−15.79, +5.26] F |

Against the lower, cap-81 ceiling every arm holds on `goal_pass` and three of the four $m = 11$ arms hold
on TGC. Against the trajectory-paired cap-25 ceiling only the untailored $m = 11$ arm holds, on `goal_pass`
alone; the post-guard tailored $m = 11$ arm fails, and the +0.23 pp non-inferiority against cap-25 in our
records (UF-06) belongs to the pre-guard arm. No verdict changes with the bootstrap seed or clustering.

Restricting the cap-25 reference to the 102 episodes in which it did not hit its call cap makes
`prefix_m11` fail (−5.92 pp, scenario [−9.80, −2.57]; CEIL-01), but that exclusion selects on the
reference's own failures, not on harder tasks: on cap-25 the 12 dropped episodes score
0.1488 against 0.9083 on those kept, on cap-81 the 18 dropped score 0.1786 against 0.8734, and the
reference-free difficulty proxies do not resolve (ROB-17, ROB-21). We therefore treat −5.92 pp as a bound
under that selection, not as a de-censored ceiling.

---

## 6. What the Prefix Actually Conveys: The Narrated Control

Does an executed prefix help because the environment has advanced into a partially solved state, or because it demonstrates API usage and argument syntax in context? The **narrated prefix control** separates the two (NARR-01, NARR-02): the planner's first 9 actions are rendered as plain-text execution traces in the initial prompt, and the executor starts at **step 0 in a fresh environment**, matching the information of $m = 9$ without its state.

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

**This equivalence is measured at $m = 9$, and $m = 9$ is where the two curves are closest.** On the untailored receiver the narrated control was also run at $m = 6$ and $m = 11$ (NARR-03; exploratory): narrated versus executed `goal_pass` is 0.6128 against 0.6825 at $m = 6$, 0.7676 against 0.7845 at $m = 9$, and 0.7686 against 0.8345 at $m = 11$. At $m = 11$ execution beats narration on both metrics and both clusterings (`goal_pass` −6.58 pp, scenario [−9.98, −3.64]; TGC −11.40 pp, [−22.81, −2.63]). At $m = 6$ the gap resolves on TGC (−13.16 pp, scenario [−21.05, −5.26]) but not on `goal_pass` under the primary scenario clustering (−6.96 pp, [−13.67, +0.63]; task [−13.96, −0.09]). The narrated curve also saturates: narrated $m = 11$ minus narrated $m = 9$ is +0.10 pp (scenario [−4.75, +5.14]), while the executed curve climbs from 0.7845 to 0.8345. **Information, not state, carries the prefix benefit at moderate depth; beyond $m \approx 9$ the executed environment contributes something text does not.** Deeper narration is still worth more than shallower execution: narration at $m = 9$ and $m = 11$ beats *execution* at $m = 6$ (+8.52 pp [+2.32, +14.75] and +8.62 pp [+2.24, +15.02]). The tailored receiver shares neither the deep-end gap nor the saturation (§6.1).

Against the one-plan floor, text alone in a fresh environment captures nearly the entire gain of execution at $m = 9$ (NARR-02; the shares are specific to that depth). On the untailored receiver narration adds **+47.92 pp** `goal_pass` (scenario [+38.67, +56.27]) and **+43.86 pp** TGC ([+30.70, +56.14]) over the base floor (0.2885 / 0.0526), **97%** and **88%** of what execution adds. On the tailored receiver it adds **+13.16 pp** TGC ([+5.26, +21.93]) over the plan floor, **79%** of execution's TGC gain (its `goal_pass` lift, +4.86 pp [−0.56, +10.61], includes zero).

```
Figure F6: Narrated versus executed prefix at m = 9, both receivers, goal pass rate and TGC, each
against the one-plan floor with 95 percent intervals; asterisks mark lifts whose interval excludes zero.
The intervals overlap at this depth; other depths are in NARR-03 (untailored) and NARR-04 (tailored).
```

**At moderate depth, then, the prefix works as concrete, executable instructions rather than as an environment mutator**: prose critique under the registered correction prompt fails (CHAN-C1-02, −6.69 pp; against a neutral prompt an unresolved 2.40 pp remains, DEC-03), while the same actions delivered as text in a fresh environment succeed.

---

### 6.1 The Substitution Is Receiver-Dependent

The paragraph above is measured on the **untailored** receiver. The tailored narrated curve, run at all
three depths (NARR-04; exploratory), does not behave the same way.

Table 2b: Narrated minus executed `goal_pass`, by receiver and depth (n = 114 paired, scenario 95% CI).

| $m$ | Untailored | Tailored |
|---|---|---|
| 6 | −6.96 [−13.67, +0.63] | −2.51 [−8.68, +3.41] |
| 9 | −1.69 [−7.10, +4.16] | −1.84 [−6.76, +2.68] |
| 11 | **−6.58 [−9.98, −3.64]** | −0.49 [−4.10, +3.21] |

On the tailored receiver **every** same-depth contrast includes zero, on both metrics (TGC −2.63, −3.51,
+0.88 pp at $m = 6, 9, 11$). At the 7.00 pp margin, tailored narration is **non-inferior to execution at
$m = 9$ and $m = 11$** (`goal_pass` lower bounds −6.76 and −4.10) and fails only at $m = 6$ (−8.68); on
the untailored receiver NI fails at every depth (−13.67, −7.10, −9.98).

The narrated curves also differ in shape. The untailored one **saturates** after $m = 9$ (+0.10 pp from
$m = 9$ to $m = 11$, narrated $m = 11$ minus narrated $m = 9$, [−4.75, +5.14]); the tailored one does not: +6.82 pp from $m = 6$ to $m = 9$
([+0.63, +12.61]), a further **+3.81 pp** to $m = 11$ ([+0.79, +6.97]), and +10.63 pp across the span
([+4.91, +16.34]) — all excluding zero. The practical corollary from the untailored receiver holds here
too: tailored narration at $m = 11$ beats tailored *execution* at $m = 6$ by +8.12 pp ([+3.18, +13.67]).

**Figure F7** plots these six contrasts with their scenario-clustered intervals and the zero line.

The natural reading is that **receiver tailoring lets a description of the planner's actions substitute
for having executed them**: a receiver fine-tuned on the same planner's (train-split) trajectories
reconstructs from text what an untrained one cannot.

**The interaction is measured directly, and it resolves at the deep end only** (DID-01). Which of six
contrasts happens to exclude zero is not a test of an interaction, so we form the difference-in-differences

$$\mathrm{DiD}(m) = \big(\text{narrated} - \text{executed}\big)_{\text{tailored}} - \big(\text{narrated} - \text{executed}\big)_{\text{untailored}}$$

**per episode** and bootstrap clusters of that single series (10,000 resamples, seed 20260924, $n = 114$,
no episode dropped). Forming it per episode keeps the pairing that the four arms' shared
$(\text{task}, \text{seed})$ episodes provide, which two separately bootstrapped gaps would discard.

Table 2c: DiD by depth, `goal_pass`, scenario-clustered 95% CI (task-clustered in parentheses).

| $m$ | DiD | scenario CI | task CI |
|---|---|---|---|
| 6 | +4.45 | [−6.71, +14.25] | [−5.07, +13.98] |
| 9 | −0.16 | [−8.36, +7.11] | [−8.51, +8.04] |
| 11 | **+6.09** | **[+1.56, +11.00]** | **[+0.63, +11.85]** |

At $m = 11$ the interval excludes zero on **both** clusterings and survives an exact 19-scenario sign-flip
test ($p = 0.0235$; ROB-08). TGC points the same way at **+12.28 pp** (scenario [+0.88, +26.32], task
[+2.63, +22.81]), but its exact test does not reject ($p = 0.0996$), so it corroborates rather than
confirms. At $m = 11$ the tailored receiver closes the narration-execution gap by +6.09 pp more than the untailored
one (−0.49 pp against −6.58 pp); at $m = 6$ the point estimate has the same sign but spans zero, and at
$m = 9$ the DiD sits on zero. Three depths and two metrics were tested and one cell resolves, so this is
**exploratory, not confirmatory**: the interaction is resolved at $m = 11$, not shown to hold in general.
The receiver × depth grid was planned in advance, but this reading was formed after seeing it.

**Observations add nothing measurable.** Adding the planner's observations to the narrated actions at
$m = 9$ changes neither receiver detectably: all eight intervals include zero, and the point estimates
have opposite signs on the two receivers (NARR-05; Appendix B.3). What the prefix conveys is the
planner's sequence of actions, not the facts those actions returned.

---

## 7. Receiver Tailoring and Depth

Three receivers — untailored, tailored and handoff-suffix trained — were run on identical replayed
prefixes at $m \in \{6, 9, 11\}$ (HF-02; Appendix B.4). No within-depth receiver gap resolves, but the
spans differ: from $m = 6$ to $m = 11$ the
untailored receiver climbs 15.20 pp, the tailored one 8.61 pp and the suffix-trained one 5.53 pp, so the
registered hypothesis C3, that suffix training extends the upper end, is answered in the negative. On the
cap-25 sample the untailored-minus-tailored gap runs −4.12, −0.06, +2.46 pp at $m = 6, 9, 11$, which
suggested that depth substitutes for tailoring; on the independent cap-81 sample it runs −2.76, +0.31,
−1.80 pp and ends with the tailored receiver ahead (C81-02), while the depth span itself replicates on both
receivers. We therefore make no substitutability claim; intervals ±5–11 pp wide could not resolve effects of
2–4 pp in either direction.

---

## 8. Mechanism Decomposition: API Discovery and Compounding Error

Two mechanisms explain why deep prefixes help: front-loaded API discovery and suppressed error compounding (MECH-08, MECH-05, MECH-07).

```
Figure F4: Mechanism decomposition. Left (M1): cumulative share of first API uses by planner position.
Right (M3): decomposition of zero-shot depth rises into handoff-earned and silenced-episode contributions.
(Referenced from paper/figures/f4_mechanism.pdf).
```

### 8.1 Front-Loaded API Discovery (M1)

Interactive tasks require discovering valid endpoints, function names and argument schemas. In an audit of 673 first API invocations across 114 planner source episodes (mean 5.9 per episode; MECH-08), discovery is front-loaded: 16.9% of first uses have occurred by position $k = 1$, 35.5% by $k = 3$, 60.5% by $k = 6$, **78.3%** by $k = 9$ and **86.6%** by $k = 11$.

The per-position probability of introducing a novel API drops from 100% at step 1 to 48.2% at steps 5–6, 36.7% at steps 9–10, and 27.1% over steps 11–20. A prefix of depth $m = 9$ handles over three-quarters of the entire task's exploratory discovery, relieving the local executor of unconstrained search.

### 8.2 Compounding Error Suppression (M2)

Prefix depth sharply reduces how often the executor errors (MECH-05). For the tailored executor, the fraction of handoff episodes encountering at least one execution error falls from **85.09%** at $m = 2$ to **56.76%** at $m = 6$, **42.68%** at $m = 9$, and **40.85%** at $m = 10$. For the untailored executor, error incidence falls from **80.18%** at $m = 6$ to **64.63%** at $m = 9$ and **61.11%** at $m = 11$.

Conditional on erroring, the tailored executor's errors concentrate at the handoff seam (the share of first errors at step 1 rises from 20.62% at $m = 2$ to 40.00% at $m = 9$ and 51.72% at $m = 10$). Depth does not improve error recovery; it leaves fewer error-prone decisions to make.

### 8.3 Handoff-Earned vs. Silenced Decompositions (M3)

Deep prefixes can finish a task before any handoff. On the cap-25 source `handoff_occurred = false` holds for 32 episodes at $m = 9$ and 60 at $m = 11$, and the executor never acted in 31 and 56 of them; both counts are correct, and they differ by trajectories the prefix exhausted at the step limit in which the executor still acted (ROB-12). Decomposing the all-episodes gain on the first definition (MECH-07; intervals from ROB-13, ROB-14) separates the two receivers sharply. On the untailored transition $m = 6 \rightarrow 9$ (82 handoff episodes, 32 prefix-exhausted), **83.8% of the +10.21 pp rise is earned on the handoff subset** (scenario [55.7, 121.2]), where the executor improved from 0.6221 to 0.7410 (+11.89 pp). The tailored receiver rises +6.15 pp, only 36.0% of it on handoff episodes, and its handoff-subset gain (+3.08 pp [−5.38, +11.69]) does not resolve; over $m = 2 \rightarrow 11$ just 16.7% ([−7.1, +38.3]) of its +12.42 pp rise comes from handoff episodes (ROB-13). Depth improves the untailored executor on live handoffs, while most of the tailored receiver's gain comes from episodes the prefix itself completed.

---

## 9. Generalization Across Model Families: Qwen3-8B Evaluation

Replaying the identical trajectories into zero-shot `Qwen/Qwen3-8B` (QWEN-02 to QWEN-04), it improves monotonically across $m = 6, 9, 11$ on every recorded dimension: `goal_pass` 0.4491, 0.7017, **0.7306**; TGC 0.1491, 0.3772, **0.4912** (a +0.342 span); completed tasks 17, 43 and **56** of 114; mean episode steps 29.61, 21.47, **18.95**; step-limit exhaustions 74, 39 and **31** of 114.

Paired intervals (QWEN-05; the stored keys are signed `m_lower minus m11`, so these are their negation): m = 6 to m = 11 gives **+28.15 pp** on `goal_pass`, scenario [+19.63, +38.47], task [+20.96, +35.72], and **+34.21 pp** on TGC, scenario [+24.56, +44.74], task [+24.56, +43.86]; both exclude zero. The shorter m = 9 to m = 11 step excludes zero on TGC at **+11.40 pp** ([+3.51, +19.30]) but includes zero on `goal_pass` at **+2.90 pp** ([−1.61, +7.03]; task [−2.80, +8.13]). TGC is the more sensitive metric for this family, as the floor analysis below predicts: `goal_pass` carries per-task partial credit whether or not the model completes anything, and TGC does not.

```
Figure F5: Within-prefix depth curve for Qwen3-8B zero-shot at m = 6, 9 and 11. No floor is drawn,
because both Qwen floor arms score identically and complete no tasks.
```

### 9.1 The Qwen Floor Measures Format Acquisition, Not Task Competence

**No floor-relative lift may be claimed for this model** (QWEN-02, QWEN-03). The zero-shot floor arms `executor_alone` and `prompt_only` score an identical **0.2481** `goal_pass`, **0.0000** TGC and **0/114** successes, exhausting the step budget in 114/114 and 113/114 episodes (the remaining one ends in a parse error; mean 40.00 vs. 39.89 steps); an upfront plan moved the score in **zero of 114 episodes**. Qwen3-8B emits the terminal action (`COMPLETE`) **0 times in 114 executor-alone and 0 times in 80 prompt-only episodes**, but 32 times at $m = 6$ and 37 at $m = 9$ (QWEN-02), while Granite, under identical templates and stop tokens, completes 53 of 114 plan episodes. Qwen acquires the completion format only from in-context demonstrations, so the 0.2481 floor accompanies zero completed tasks; we did not audit the scorer and do not assert what produces it. The depth effect replicates *within prefix arms*, where the demonstrations are common to every arm; comparisons against the floor are uninterpretable.


### 9.2 Tailoring Does Not Transfer to the Second Family

A Qwen adapter trained on the identical 497-row dataset and recipe scores 0.2583 `goal_pass` on the
one-plan floor against the zero-shot 0.2481, where the same recipe lifts Granite's by roughly 43 pp, and
105 of 114 episodes end on the step limit (QWEN-06; Appendix B.5). The adapter is applied, and a
train/serve prompt mismatch is real but not the cause (QWEN-07). What survives is a thin, family-dependent training signal: the terminal action is 165 of 6,767
supervised targets (2.44%); Granite emits it in 3.00% of its actions and Qwen in 0–0.07%, rising to 1.46%
only when a replayed prefix is in context. Depth transfers to the second family; this fine-tuning recipe
does not, and neither Qwen floor is used as a denominator.

---

## 10. Related Work

**Large–small collaboration and cascades.** Pairing an expensive model with a cheap one is usually
treated as a per-query routing decision. FrugalGPT learns a cascade over LLM APIs that stops once an answer
is judged reliable [@frugalgpt_chen_2023], and Hybrid LLM and RouteLLM train routers that send each query
to a small or a large model [@hybrid_llm_ding_2024; @routellm_ong_2024]. More recent work moves the
decision inside the trajectory: per reasoning step with an RL-trained control policy
[@policy_stepwise_routing_2026], per turn from joint embeddings of history and candidate models
[@mtrouter_2026], or after a cheap model explores for a few turns [@swe_router_2026]; R2V escalates from a
distilled small model to a teacher LLM when a calibrated step-level router predicts failure
[@r2v_agent_2026]. SwiftSage is the closest agent design: a small model fine-tuned on oracle trajectories
acts by default, and a GPT-4 module for subgoal planning and grounding is invoked by heuristic rules
[@swiftsage_lin_2023]. In LATM a strong model writes tools a lightweight model applies [@latm_cai_2024],
and speculative decoding and speculative agent planning have a small model draft what a large one verifies
[@speculative_decoding_leviathan_2023; @dsp_guan_2025]. These methods decide *which* model acts, or verify
every step; we fix the schedule and vary the *form* in which the strong model's budget reaches the small one.

**Planner–executor and delegation architectures.** ReWOO writes a complete tool-use plan before any
observation and distils the planner into a 7B model [@rewoo_xu_2023]; Plan-and-Act trains a planner whose
structured plans an executor grounds into web actions [@plan_and_act_erdogan_2025]; AppWorld's baselines
include a plan-and-execute agent [@appworld_trivedi_2024]. Role-factorised systems give planner, executor
or critic roles to models of different sizes [@coda_liu_2025; @agentcard_jiang_2026; @three_roles_2026;
@think_big_search_small_2026]; switching models for a single turn shifts multi-turn outcomes
[@perf_drift_switching_2026], and handing over context cuts rediscovery when a coding agent takes over an
interrupted task [@handoff_debt_2026]. Reach-or-Solve hands states one checkpoint reaches to another,
and warns that restricting analysis to states both reach selects on outcome [@reach_or_solve_2026]; our
replayed prefixes use this protocol, with the planner as reacher and the 8B executor as solver, and the
ceiling exclusion in §5.5 is an instance of the selection they warn about. The closest work is Ganz et al. [-@handoff_tax_ganz_2026], who hand SWE-bench
Verified trajectories between Claude and GPT model pairs in both directions at seven switch points, compare
four trajectory-transfer interfaces with prompted receivers, and find that downshifting a stronger model's
trajectory to a cheaper one is a favourable cost–quality point; we do not claim that result. We differ in
who acts and in what is compared: the same planner either acts or advises at a matched trigger and
context, the receiver is a local 8B model tested with and without LoRA tailoring, and the central contrasts
are pre-registered. Their finding that dropping the stronger model's trajectory while keeping its edits
lowers quality complements our narrated control, which keeps the trajectory text and removes its execution.

**Feedback and critique channels.** Our advice arms descend from verbal-feedback methods: Self-Refine has a
model critique and revise its own output [@self_refine_madaan_2023], Reflexion keeps verbal reflections
across trials [@reflexion_shinn_2023], and CRITIC grounds critiques in tool interactions
[@critic_gou_2023]. Evidence on when feedback helps is mixed: LLMs struggle to self-correct without external feedback
[@llms_cannot_self_correct_huang_2024; @self_correction_survey_kamoi_2024], small models do better with a
strong verifier [@slm_need_strong_verifiers_2024], and simulated natural-language feedback yields gains
of 2–17% across 20 tool-using models [@mint_wang_2024]. Our advice is externally authored by a stronger model that sees the full transcript,
the regime this literature treats as favourable.

**Demonstrations and trajectory prefixes.** The action channel is closer to demonstration than to feedback.
ReAct steers agents with one or two in-context trajectories [@react_yao_2023], and Synapse prompts with
complete abstracted state–action trajectories [@synapse_zheng_2024]; our narrated control is the
task-specific case in which the exemplar is the planner's own opening on the current task. DAgger queries the expert on learner-visited states [@dagger_ross_bagnell_2011], reverse curricula start
episodes from demonstration states [@backplay_resnick_2018; @salimans_chen_2018], and agent tuning distils
teacher trajectories into smaller models [@fireact_chen_2023; @agentinstruct_zeng_2023;
@agentflan_chen_2024; @agent_distillation_2025]. ReOPD replays teacher trajectories as prefixes during
on-policy distillation and names a "prefix trap", where the teacher's targets become unreliable on
student-like histories [@reopd_liao_2026], and Guided-OPD mixes teacher and student turns under a schedule
that decays to zero [@guided_opd_2026]. In both the teacher prefix is withdrawn before deployment; in ours
it is present in every episode, so our suffix-trained receiver is trained for the condition it is served in.

**Benchmarks and positioning.** AppWorld's 750 tasks require code written against the APIs of nine everyday
apps [@appworld_trivedi_2024]; τ-bench adds a simulated user and domain policies [@tau_bench_yao_2025], and
BFCL scores function calls up to stateful multi-step settings [@bfcl_patil_2025]. The strongest AppWorld
results train or adapt a single agent, by RL [@loop_2025; @canopy_2026] or context optimisation
[@ace_2026], on the test splits; Appendix B.6 collects them and explains why our dev-split scores are not
comparable. To our knowledge, no prior work compares a stronger model's budget spent as executed actions
against the same budget spent as prose advice, at a matched trigger and context, with a small local
executor as the receiver. Prior work shows that a cheaper model can continue a stronger model's trajectory
[@handoff_tax_ganz_2026] and supplies the state-handoff protocol we use [@reach_or_solve_2026]; we add the
channel comparison, a prefix-depth curve for 8B receivers with and without tailoring, and a narrated
control that separates what a prefix conveys from its execution — paired contrasts on the AppWorld dev
split with one planner, not benchmark results.

---

## 11. Limitations

1. **Development Split Scope:** All experiments use the 57-task AppWorld development split ($n = 114$ paired episodes); the test splits (`test_normal`, `test_challenge`) remain untouched (`docs/prereg_j9_freeze_20260920.md`).
2. **Single Planner Family:** Every trajectory and critique comes from `gpt-5.6-luna` at `medium` reasoning effort; transfer to other planners is unmeasured.
3. **Cap-81 Ceiling Inversion (CEIL-07, CEIL-04, CEIL-06):** Raising the planner call cap from 25 to 81 lowered its score by 6.47 pp on `goal_pass` (scenario [−11.68, −1.37]), and five planner samples separate cleanly by cap, so every ceiling comparison names its cap (§5.5; detail in Appendix B.7).
4. **Second-Family Floors:** Both Qwen floors, zero-shot and tailored, measure termination-format acquisition rather than task competence (QWEN-02, QWEN-03, QWEN-06), so neither may serve as a denominator, and the tailored Qwen depth curve is reported as confounded rather than as a second-family tailoring result.
5. **Small-Cluster Inference:** With 19 clusters, exact sign-flip tests (ROB-01 to ROB-08) pass the matched-trigger `goal_pass` result only narrowly at 114 pairs and not at 171 ($p = 0.063$; DEC-02), reject neither TGC version of the channel and interaction claims, and leave one registered TGC non-inferiority (COST-03) marginal.
6. **Tailoring × Depth Is Unresolved, Not Absent (DID-02, POOL-03):** The interaction resolves on neither planner sample — cap-25 **−2.53 pp** (scenario [−7.66, +2.53]), cap-81 **+2.10 pp** ([−4.71, +9.01]) — nor when pooled to $n = 171$ (**+2.81 pp**, scenario [−2.57, +8.96], task [−2.05, +7.95]; the wider $m = 6 \rightarrow 11$ version +0.69 pp [−4.40, +5.92]). It is unmeasurable at this power, which is not evidence that it is absent.
7. **Deviation from a Frozen Pre-Registration (CHAN-PRICE-02):** H2's cost prediction P4 failed in the direction its attached remedy does not cover; we report the primary contrast as supported and flag the judgement (Appendix B.1). A reader who declines it can rely on the matched-trigger result in Section 3, which carries no budget question.
8. **Advice Prompt and an Unresolved Decomposition (DEC-01, DEC-03):** Every advice arm, the advice-at-price arm included, uses the registered correction prompt, so every advice comparison is conditional on it. At $k = 10$ a neutral prompt closes about three-fifths of the takeover−advice gap; neutral advice was not run at $k = 1$. The registered decomposition is unresolved, so we do not attribute the gap to the channel.

Analysis and test-suite defects found and repaired during the campaign are recorded in Appendix C.

---

## 12. Conclusion

On AppWorld, the benefit of a hosted planner's action prefix accumulates across a span of depths, with no threshold the data can localize. At a matched trigger and context, executed actions score higher than advice written under the registered correction prompt while costing no more on any of three cost axes as a point estimate, and that advice does not catch up when bought at 3.2× the token budget. A neutral advice prompt, however, recovers about three-fifths of that gap, and the registered decomposition is unresolved. At moderate depth the prefix works largely through information rather than environment state, and in an exploratory analysis how much narration recovers at $m = 11$ depends on whether the receiver was fine-tuned on that planner's trajectories.

Two boundaries stand beside the result. The depth effect replicates in a second executor family, but the fine-tuning recipe does not: the second family never acquires a terminal convention that is 2.44% of its training targets. And every number here is one environment, one planner model and the development split; the confirmatory read is registered and not yet run.

---

## Appendix A. Reproducibility

Every number in this paper is produced by a script from a campaign directory of per-episode
`result.json` files, and is recorded in `docs/claims_ledger.md` with the report path and the JSON key
it came from. `scripts/analysis/preprint_number_audit.sh` enforces this mechanically: it takes the set
difference between the figures printed here and the figures in the ledger, and fails if the paper
claims anything the ledger cannot source. It exits 0 on this draft over 97 distinct percentage-point figures
and 105 distinct four-decimal rates.

That check exists because of a real failure, recorded in Appendix C.3.

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

One configuration rule matters for anyone reproducing an untailored arm: it must be configured under the
`prompt_only` system, never under `sft_plan`.
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
| `docs/prereg_c1_decomposition_20260923.md` | B2, the decomposition of the matched-trigger gap (§3.1) |
| `docs/prereg_j10_amendment_20260924.md` | the registered confirmatory read, **not yet run** |

Registered text is amended by appending, never by editing what it already says; the amendment record
in each document is the audit trail. Where we departed from a frozen document we say so in
§11 (item 7) and Appendix B.1 rather than absorbing it — a prediction whose attached remedy did not fit the
direction in which it failed.

### A.4 Statistical protocol

Contrasts are paired on `(task_id, seed)` and bootstrapped over **clusters**, not episodes: 10,000
percentile draws, scenario-clustered as primary and task-clustered reported beside it, because the 57
dev tasks form only 19 scenario groups and tasks within a scenario are not independent. A crashed
episode scores 0 under the all-episodes population; `error_type == "limit"` is not a crash and keeps
its recorded score. Difference-in-differences contrasts are formed **per episode** before averaging,
so the pairing between the two gaps survives into the bootstrap (§6.1).

**Bootstrap stability for thin bounds.** At $B = 10{,}000$ the Monte Carlo error on a percentile
bound is itself a few tenths of a percentage point, so a bound that clears its threshold by less than
that is not a verdict. We therefore re-run any interval whose decision-relevant bound falls within
1 pp of zero or of the 7.00 pp non-inferiority margin at seven bootstrap seeds
$\{20260924, 1, 2, 3, 7, 101, 999\}$ and report the range; if the sign changes across seeds the
quantity is reported as unresolved. This rule was adopted mid-study after it changed one verdict
(§5.4; Appendix B.2) and was then applied retrospectively to the other thin bounds in the paper, which survived it.
Note that TGC is discrete, so a TGC percentile bound can be identical at every seed without being
precise — stability there reflects the attainable value grid, not resolution.

**Retrospective application.** Applied to the paper's other thin bounds, the rule leaves the $m = 11$
narration × receiver interaction of §6.1 intact: its lower bound is strictly positive at every seed on both
clusterings (scenario 1.46–1.56, task 0.45–0.63) and at 200,000 resamples (POOL-04). The task-clustered
upper bound of +0.01 pp on the H2 review-frequency contrast (§3.2), computed by a different script, was
probed the same way once that script accepted a seed: it is negative at six of the seven seeds and −0.1184
at 200,000 resamples (ROB-04), so the near-miss it appeared to be was a favourable draw.

**Small-cluster alternatives.** Alongside the percentile bootstrap, each headline contrast was re-tested
with a two-sided sign-flip randomization test that is exact on the 19 scenarios (all $2^{19}$ patterns) and
Monte Carlo on the 57 tasks (100,000 patterns), and with wild cluster bootstrap intervals (Rademacher and
Webb weights, 10,000 draws, seed 20260924); non-inferiority uses the one-sided sign-flip test against the
7.00 pp margin. All 31 published estimates in that set were first reproduced exactly (ROB-01 to ROB-08).

### A.5 Provenance and what is not yet automated

The results in this draft were produced at commit `8fcc848` of the analysis tree. Campaign-granularity
provenance for every campaign any report depends on is generated, not hand-maintained, by
`scripts/analysis/campaign_index.py` into `campaign/campaign_index.{json,md}`: episode count, tasks,
seeds, the full `error_type` distribution, the adapter, the replayed source campaign and the config
behind each of the 49 campaigns the reports read from. All 49 are present; nothing a report depends on
is missing.

Three gaps remain, and the first two are wider than earlier drafts of this appendix admitted.

1. **The run record stores less than the index reports.** An episode's `manifest.json` carries the
   campaign id, run id, host, environment, Python version and timestamp — but **no config path, no
   adapter, no replayed source campaign and no git SHA**. Every one of those fields in the index is
   therefore *reconstructed* from the repository by matching the `campaign_id` a config declares
   against the directory a run wrote to. The reconstruction is reliable, because the runner derives
   that directory from the same value, but it is not the same as the run having recorded it, and it
   would mislead for a campaign whose config was edited after the run.
2. **Ten campaigns ran under an id their config does not declare, including all eight dev prefix
   arms.** The runner resolves the id as `cid = campaign_id or cfg.get("campaign_id")`, so the
   `--campaign-id` command-line flag overrides the file, and our PBS wrapper passes it per arm.
   Concretely, `configs/hj12_prefix_m11.yaml` declares `hj12_prefix_m11_20260922` while the arm used
   throughout this paper is `hj12_prefix_m11_20260923`: **re-running that config verbatim writes to a
   different directory**, and a reproducer must pass the published id explicitly. The index flags
   every such case rather than matching it silently.
3. **Two dependencies have no committed config at all**, including the third planner sample behind the
   pooled analysis of §5.4 and Appendix B.2, which was produced by supplying both the campaign id and `--seeds 3` on
   the command line. We have deliberately not back-filled configs for them: a file that was never
   executed is not provenance.

None of this affects any number reported here — the index's per-campaign aggregates were cross-checked
against the published values and match exactly — but it is the part of the reproducibility story that
a reader should not take on trust.

The runner now stamps all of it at run time: each episode manifest carries a `provenance` block with
the git SHA, branch and a dirty flag, the config path and the campaign id that config declares, an
explicit flag when the command line overrode that id, the adapter, the executor model, the replayed
source campaign, and the split. **We state plainly that every campaign behind this paper predates that
change** and therefore still relies on the reconstruction described above; the stamping closes the gap
for the confirmatory read and for anything run afterwards, not retrospectively. Recording the split
matters most: it is a command-line argument that no config carries, so before this change nothing in
an episode's artifacts distinguished a development episode from a test one.

**Refills and live answers in replay arms.** Until commits 72899b5 / 5c331bf, resubmissions ran
`--purge-broken`, which also re-runs `timeout`, `parse_error` and `api_error` episodes. No published
campaign is proven to contain a second roll of a scored failure (PROV-01): the ceiling and planner
refills were exactly the prior job's crashes, and the two floors whose refill split cannot be recovered are bounded
(`hj1r_exec8b` at most +2.03 pp `goal_pass` and +0.88 pp TGC; `hj1r_prompt_only` at most +0.44 pp,
0 TGC), so gains measured over them (CHAN-ZS-01, TAILOR-06, NARR-02) can only be understated.
Separately, `prefix_handoff` honours an executor's ask with a live planner call, and in six published
prefix arms hosted luna answered (PROV-02; episodes/calls/bound on the arm-mean `goal_pass` lift):
the handoff-adapter arms of Appendix B.4, `hj13_prefix_hf_m6` 7/10/2.15 pp, `_m9` 3/3/0.88 pp
and `_m11` 4/31/0.85 pp; and three Qwen arms, `hj14_prefix_m9` 4/6/1.36 pp,
`hj15_prefix_zsq_m11` 1/1/0.18 pp and `hj19_prefix_m11_qwen_notk` 2/2/0.35 pp. Every other
prefix arm has none, including the headline depth curves. The run-time gate flagged
`hj13_prefix_hf_m6`; the arm was reported anyway.

## Appendix B. Supplementary Analyses

The material below was moved out of the main text to keep it short. Nothing has been removed, and each
subsection names the ledger rows it rests on.

### B.1 Handling of the Failed P4 Prediction (CHAN-PRICE-02)

**P4 failed, and we report the failure and our handling of it explicitly.** P4 predicted non-cached
tokens in [300k, 700k]; the observed 1,414,410 is roughly twice the top of that range. The prereg's remedy
for a P4 failure is written for the *opposite* case — an arm that lands below 300k and so was never
actually priced at the action channel's budget, in which case P2 must be reported as untested. That hazard
is excluded here *a fortiori*: advice was bought far above the action channel's budget, not below it. We
therefore report P2 as tested and supported, while flagging that this is a deviation from the literal text
of a frozen prereg. A reader who declines that judgement should treat P2 as untested at the registered
budget and rely on Section 3, which establishes the same ordering against the registered advice prompt at
**matched trigger and matched context**, where no budget question arises; a neutral prompt recovers about
three-fifths of that gap (§3.1).

### B.2 Third Planner Seed: Detail (POOL-01 to POOL-04)

Because prefix arms replay a *recorded* planner campaign, additional statistical power on the cap-81
sample is nearly free: a third planner seed costs one hosted ceiling run (CEIL-06), after which the six
replay arms — two receivers $\times$ three depths — spend no hosted calls at all. We ran them
(`hj18_prefix_c81s3_*`, 57/57 episodes each, zero crashes) and pooled them with their two-seed
counterparts. Episode keys are `(task_id, seed)`, so the campaigns cannot collide; every arm loads
**171** episodes across seeds $\{1, 2, 3\}$ and no episode is dropped from any contrast (POOL-01).

**The span survives and tightens.** Over $m = 6 \rightarrow 11$ the untailored receiver gains
**+7.70 pp** (scenario [+3.69, +12.06], task [+3.14, +12.30]) and the tailored receiver **+8.39 pp**
([+4.20, +12.63], task [+4.09, +12.96]). Both lower bounds sit three to four points clear of zero.
This is the depth claim the paper makes, and a 50 % increase in pair count leaves it intact.

**The adjacent step does not.** At two seeds the tailored $m = 9 \rightarrow 11$ step was +4.92 pp with
an interval that included zero; at three seeds the point estimate falls to **+4.25 pp** and the scenario
interval becomes [+0.15, +8.75] — nominally excluding zero, by fifteen hundredths of a point. We do
**not** report that as a resolution, for a reason we think generalises beyond this paper. At
$B = 10{,}000$ resamples the Monte Carlo error on a percentile bound is itself a few tenths of a point,
which is larger than the margin in question. Re-running the identical estimand on the identical
episodes at the seven bootstrap seeds 20260924, 1, 2, 3, 7, 101 and 999 gives lower bounds of +0.15, +0.08,
+0.05, **−0.01**, +0.15, +0.20 and +0.11 respectively (POOL-04): **the verdict flips on one seed in seven**
(seed 3). A 200,000-resample run puts the bound at +0.10.
The same fragility was visible before we probed it — two independent implementations of the *same*
two-seed estimand disagreed by 0.24 pp on this bound, a spread wider than the margin by which the
pooled interval clears zero. We therefore report the tailored $m = 9 \rightarrow 11$ step as
**unresolved, sitting on the decision boundary**, and the accurate description of what the third seed
bought is a narrower interval (width 10.57 $\rightarrow$ 8.59 pp) around a slightly smaller estimate,
not a null converted into a finding. The untailored step is unambiguously unresolved and its estimate
roughly halves under pooling (+2.82 $\rightarrow$ +1.44 pp, [−2.56, +5.52]), consistent with the
seed-3 untailored curve being non-monotone at the top (0.6963, 0.7942, 0.7811 at $m = 6, 9, 11$).

**Non-inferiority at 171 pairs.** Against the pooled cap-81 ceiling (0.7698), and reporting ceiling
minus arm so that non-inferiority requires the *upper* bound below +7.00 pp, all four `goal_pass`
verdicts hold and none is a boundary case: tailored $m = 11$ −4.41 [−10.66, **+0.74**], untailored
$m = 11$ −1.94 [−6.40, **+2.17**], tailored $m = 9$ −0.16 [−4.64, **+4.05**], untailored $m = 9$
−0.50 [−5.35, **+3.02**]. Pooling tightened every interval without changing a verdict. On TGC the
picture is unchanged from the two-seed analysis: non-inferiority holds at $m = 11$ tailored
(−0.58 [−7.60, +5.85]), and fails at $m = 9$ on both receivers. The untailored $m = 11$ TGC bound is
+7.0175 against a 7.00 margin — identical at every bootstrap seed, because TGC is discrete and the
percentile lands on an attainable value — which we record as *undetermined* rather than refuted; a
gap of 0.0175 pp is not something more resampling can adjudicate. We note one clustering disagreement
rather than rounding it away: the tailored $m = 11$ contrast excludes zero under task clustering
([−8.65, −0.33], stable across seeds) but not under scenario clustering, which is the registered
primary. The licensed statement is non-inferiority, never superiority (§5.3, §5.5).

**The tailoring $\times$ depth interaction remains unmeasured**, and now demonstrably so rather than
by assertion: at 171 pairs it is +2.81 pp, scenario [−2.57, +8.96], task [−2.05, +7.95], with the
wider $m = 6 \rightarrow 11$ contrast at +0.69 pp [−4.40, +5.92] (POOL-03). Both components of the
narrow contrast are themselves unresolved, so this is a difference between two quantities the data
cannot pin down. Fifty-seven additional episodes per arm at zero hosted cost moved the point estimate
by 0.7 pp and left an interval nearly six points wide in each direction.

### B.3 Observations in the Narrated Packet (NARR-05)

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

### B.4 Three-Receiver Evaluation and Its Replication (HF-02, C81-02)

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

Paired scenario-clustered contrasts follow (Figure F3, HF-02). The handoff-adapter arms are not pure replay: hosted luna answered executor asks live in 7, 3 and 4 of their episodes at $m = 6, 9, 11$, which bounds the lift on each arm mean at 2.15, 0.88 and 0.85 pp (PROV-02; Appendix A.5).
- **At $m = 6$:** base minus standard adapter is **−4.12 pp [−10.41, +1.64]**; base minus handoff adapter is **−6.55 pp [−13.92, +0.23]**; standard minus handoff is **−2.43 pp [−7.42, +2.97]**. We withdraw the handoff adapter's directional lead as a claim: its 2.15 pp bound is nearly the whole of its 2.43 pp lead over the standard adapter (HF-01).
- **At $m = 9$:** base minus standard is **−0.06 pp [−7.06, +6.77]**; base minus handoff is **+0.05 pp [−6.35, +6.17]**; standard minus handoff is **+0.12 pp [−3.08, +3.12]**. The earlier reading that the three receivers converge to within 0.12 pp does not survive the handoff arm's 0.88 pp bound and is withdrawn (HF-02).
- **At $m = 11$:** The ordering reverses, with the untailored receiver leading numerically: base minus standard is **+2.46 pp [−1.48, +6.43]**; base minus handoff is **+3.12 pp [−1.97, +8.15]**; standard minus handoff is **+0.65 pp [−4.21, +5.37]**.

While all individual paired intervals include zero at $n = 114$, overarching curve spans over $m = 6 \rightarrow 11$ differ substantially: untailored climbs **15.20 pp**, standard adapter climbs **8.61 pp**, and handoff-suffix adapter climbs only **5.53 pp**.

The pre-registered hypothesis C3—asking whether training specifically on handoff suffixes extends the upper ceiling—is answered in the **negative**, and every within-depth interval above includes zero. Handoff-suffix fine-tuning flattens the curve; whether it also raises shallow-depth performance cannot be separated from the live planner answers its $m = 6$ arm received (HF-01, PROV-02). Taken together with TAILOR-06 and MECH-07, **prefix depth, general executor tailoring, and suffix-specific training are partially substitutable and do not stack**. Each intervention provides the executor with domain syntax and API conventions; whichever is applied first captures the available gains, leaving the least specialized receiver with the greatest headroom to benefit from deep prefixes.

```
Figure F3: Receiver gap (untailored base minus tailored sft_b_plus) across handoff depths
m = 6, 9, 11 with scenario-clustered 95% bootstrap intervals. (paper/figures/f3_tailoring_gap.pdf).
```

**Replication on the cap-81 sample.**
The reading above — that depth substitutes for receiver tailoring, because the untailored receiver overtakes the tailored one by $m = 11$ — rests on the *shape* of a three-point sequence, since no individual within-depth receiver gap is resolved at $n = 114$ on either sample (HF-02). We tested that shape on the independent cap-81 trajectories, both receivers, all six arms complete (C81-02).

**It does not reproduce.** On cap-25 the untailored-minus-tailored gap runs −4.12, −0.06, +2.46 pp, monotone, ending with the untailored receiver ahead. On cap-81 it runs **−2.76, +0.31, −1.80 pp** on `goal_pass` (TGC 0.00, +1.75, −4.39): non-monotone, and ending with the **tailored** receiver ahead. All six cap-81 intervals include zero.

The depth effect itself replicates on both receivers of the second sample — the tailored span $m = 6 \rightarrow 11$ is +6.34 pp `goal_pass` (scenario [+0.28, +12.94]) and +14.04 pp TGC ([+3.51, +26.32]), both excluding zero. What fails to replicate is the ordering at the deep end.

We therefore demote "depth substitutes for tailoring" from a finding to **an observation made on one planner sample and not reproduced on a second**. What survives: both tailoring and depth raise the shallow end; no within-depth receiver gap is resolved on either sample; and the deep-end ordering is not stable across samples. This is equally not evidence *against* substitutability — the intervals are ±5–11 pp wide and would not resolve the 2–4 pp effects at issue. The claim is simply not robust enough to carry weight.

**Tailored arms on the cap-81 sample.** The tailored cap-81 arms score `goal_pass` 0.7477, 0.7619 and 0.8111 at $m = 6, 9, 11$. At $m = 11$ the tailored arm is essentially unchanged by the source swap (0.8111 against 0.8098 under cap-25 sourcing), while the untailored arm loses 4.13 pp. The depth step $m = 9 \rightarrow 11$ is +4.92 pp [−0.43, +10.36] tailored against +2.82 pp [−1.55, +7.16] untailored — the *reverse* of the ordering under cap-25 sourcing (+2.46 tailored against +4.99 untailored). Neither pair resolves and the ordering inverts with the trajectory source, a further reason we make no tailoring $\times$ depth claim.

### B.5 Tailored Second Family (QWEN-06, QWEN-07)

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

### B.6 External Benchmark Context

We situate our findings within published evaluations on AppWorld (`docs/external_comparison_20260923.md`):

- **AppWorld Baselines (Trivedi et al., ACL 2024) [@appworld_trivedi_2024]:** The benchmark introduction evaluates ReAct, Plan & Execute (PlanExec), Full Code + Reflexion, and Iterative Parallel Function Calling across GPT-4o, GPT-4-Turbo, and LLaMA-3-70B-Instruct. On `test_normal`, GPT-4o ReAct achieves 48.8% TGC / 32.1% SGC, while PlanExec achieves 44.6% TGC / 23.2% SGC. LLaMA-3-70B achieves 24.4% TGC (Full Code + Reflexion) and 20.8% TGC (ReAct). Smaller open models without specialization (Mistral-7B-CodeAct, ToolLLaMA-7B) score 0.0% TGC.
- **Scaffolding and Training Innovations:** LOOP (Chen et al., arXiv:2502.01600) [@loop_2025] achieves a +9.0 pp relative gain over o1 (~71% TGC) using a 32B open model. CANOPY (Pu et al., arXiv:2609.01245) [@canopy_2026] reports 86.9% TGC on `test_normal` and 67.6% on `test_challenge` with Qwen3-14B via outcome-only RL. ACE (Zhang et al., ICLR 2026 / arXiv:2510.04618) [@ace_2026] yields a +17.1% relative gain with DeepSeek-V3.1. ProST (Bijoy et al., IJCNLP-AACL 2025 / arXiv:2509.04508) [@prost_bijoy_2025] evaluates progressive sub-task training on ~8B open models (26.0–33.0% TGC). Three Roles, One Model (arXiv:2604.11465) [@three_roles_2026] evaluates Qwen3-8B under a 3-role scaffold (8.9% TGC FP16 / 5.9% AWQ). User-in-the-loop interactions are benchmarked by AppWorld-UL (ICML 2026 / arXiv:2607.20536 [@appworld_ul_2026]; 48.6% overall success with Claude Opus 4.7).
- **Public Leaderboard Anchor:** On the AppWorld leaderboard, the Kecaipan Capybara scaffold utilizing `gpt-5.6-luna` [@gpt_5_6_luna_2026] achieves 85.1% TGC / 73.2% SGC on `test_normal` and 73.4% TGC / 52.5% SGC on `test_challenge`.

#### Non-Comparability of Absolute Dev Scores

As detailed in `docs/limitations_external_20260923.md`, our dev-split pass rates (0.72–0.83) cannot be directly compared against published test-split leaderboard rankings due to four methodological differences: (1) we employ a minimal interaction loop (14.4 mean calls vs. 9.3 on complex scaffolds); (2) evaluations are strictly on the dev split; (3) our environment uses 57 pinned dev tasks (excluding 3 multi-party synchronization tasks); and (4) our planner uses frozen `medium` reasoning effort. Internal validity is maintained via paired bootstrap contrasts on identical task-seed initializations.

### B.7 Ceiling Inversion Detail (CEIL-07, CEIL-04, CEIL-06)

Extending planner call cap from 25 to 81 calls resulted in lower performance: `ceiling_cap81` scored **0.7637 `goal_pass` / 0.5702 TGC** vs. **0.8284 / 0.6842** for `ceiling_cap25` (paired difference **−6.47 pp `goal_pass`**, scenario [−11.68, −1.37], task [−12.48, −0.46]; TGC **−11.4 pp** [−21.05, −1.75]). Cap-81 episodes averaged 16.35 actions (max 40) vs. 13.42 for cap-25 (max 24), consistent with a larger budget letting the planner over-act in the tail and corrupt environment state. A third cap-81 planner sample (CEIL-06) closes the "one unlucky draw" reading: per-seed `goal_pass` is 0.8253 and 0.8315 at cap 25 against 0.7700, 0.7574 and 0.7819 at cap 81, so **the lowest cap-25 sample exceeds the highest cap-81 sample by 4.34 pp and the two families do not overlap across five samples**, with a within-cap spread of 0.62 pp and 2.45 pp respectively. Two and three samples are a spread across what we have, not a variance estimate.

## Appendix C. Defect and Process Record

Each item below is a failure a reader of a results paper could not otherwise see. Every number reported in
this paper comes from the repaired pipelines.

### C.1 Test-Suite Collection Defect

For six days the project's configured test command
(`pytest tests/`, via `testpaths`) aborted during collection: two directories contained a test
module of the same basename with no package marker, so the second import collided with the first.
Test runs during that period executed the unit directory alone, and the 34 integration tests were
silently outside every reported pass count. Repaired by renaming; the full tree now reports 625
passed, 1 skipped. No result in this paper depends on the integration tests, but the episode is
recorded because a green suite that is not running everything is exactly the failure mode this
project's analysis defects share.

### C.2 Analysis Defects Found and Repaired

- *Terminal Guard Defect (GUARD-01, MECH-01..03):* Early runs allowed actions following replayed completion tokens; resolved by adding a fatal post-prefix terminal check.
- *Handoff Flag Path (MECH-09, GUARD-03/X33d):* The mechanism script initially inspected an invalid JSON key; resolved by aligning paths and making zero-count populations fatal.
- *Error Scan Actor Filter (MECH-04, MECH-05):* Initial audits filtered observations on executor identity, yielding 0.00% error rates; repaired to scan observation return text.
- *Adapter Build Mismatch (ADV-FC-02):* Initial H1 advice contrasts paired against an older 0.7000 adapter build; corrected to use the standard 0.7181 `iaware` build.
- *Cost Token Pricing (COST-01):* Local executor tokens were initially passed to hosted pricing calculators; corrected to filter exclusively on hosted usage events.
- *Segmented Fit Float Tie-Breaking (TIEBREAK-01):* Exact RSS float comparisons in segmented regression produced spurious breakpoints on straight lines; resolved via scaled RSS tolerances.

### C.3 A Results Table Filled With Invented Values (QUAL-07)

The number audit of Appendix A exists because of a real failure. A worker drafting the cost table invented three of its
eleven TGC values — one a fill-down of the row above, one wrong by 10.52 pp — while reporting zero
outstanding work, and the entire `goal_pass` column beside them was correct, so nothing looked wrong
(QUAL-07). An instruction to flag uncertain values cannot catch that, because a model that does not
know it is guessing cannot comply with it. A set difference can, and did.
