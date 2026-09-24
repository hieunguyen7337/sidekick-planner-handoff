---
title: "Concrete Code, Executed or Shown: How a Hosted Planner's Help Reaches an 8B Local Executor on AppWorld (Exploratory, Dev Split)"
date: "2026-09-24"
author: "Sidekick Research Group"
abstract: |
  We study how a hosted planner (`gpt-5.6-luna`) should deliver help to a local 8B executor (IBM Granite 4.2) on AppWorld, with paired, cluster-bootstrapped contrasts on the 57-task dev split only; the held-out tests that will judge each claim (J10, J11, J12) are under way or pending, and no held-out result is read or reported here. Our headline is exploratory: the executor benefits from the planner's concrete code, executed or shown, while terse correction prose leaves it stuck. At a matched trigger, executing the planner's action beats advice written under a correction prompt by +6.13 pp `goal_pass` over 171 pairs (scenario 95% CI [+0.75, +12.71]); the contrast was registered and resolves at 114 pairs, but at 171 an exact 19-cluster randomization test gives p = 0.063, and neither TGC nor scenario goal completion resolves. Exploratory analyses find 20 of 171 correction-advice episodes ending at the 40-step limit against 2 of 171 for takeover, and neutral-prompt advice that is mostly fenced code (207 of 221 interventions, against 3 of 260) and recovers +3.73 pp of the gap ([−0.06, +8.24]); the registered decomposition is unresolved. The registered advice-at-every-step arm failed its cost prediction, so we report it only as higher-frequency correction advice: advice remains unpriced at the action channel's budget. In exploratory depth analyses, handing off after m replayed planner actions raises `goal_pass` from m = 6 to m = 11 by +8.39 pp (tailored executor) and +7.70 pp (untailored) over all episodes, and by +7.66 and +7.81 pp over the 88 episodes in which the executor took control, about as much as over those the prefix finished, although the untailored handoff rise resolves on the scenario bootstrap only (exact sign-flip p 0.0645) and on TGC neither handoff rise resolves; at m = 11 the replayed prefix ends 83 of 171 episodes, no breakpoint can be localized, the registered chord test failed, and the effect replicates a downshift-timing result Ganz et al. report. Against the planner acting alone in the same minimal harness, at a 7.00 pp margin taken from a held-out power analysis, the m = 11 prefix is non-inferior on `goal_pass` to the medium-effort planner at cap 81; over the episodes the executor took over, that holds only because the executor rescues the planner's step-limit stalls, and it fails over the rest. Against the cap-25 planner alone the tailored m = 11 prefix fails (−1.86 pp, [−8.51, +6.09]), and no m = 11 prefix is non-inferior to the planner at high effort, which scores +11.97 pp higher than the medium-effort planner alone. On TGC non-inferiority holds only for the tailored executor over all episodes, which an exact test did not support in an earlier 114-pair comparison (p = 0.0264). All of this is exploratory.
---

# Concrete Code, Executed or Shown: How a Hosted Planner's Help Reaches an 8B Local Executor on AppWorld

## 1. Introduction

Small open-weight models are cheap to run locally but compound errors when they act alone in software environments [@slm_agentic_belcak_2025; @where_agents_fail_2025; @long_horizon_mirage_2026; @sinha_illusion_2026]; hosted frontier models act better and cost more per call. Hybrid systems differ in who acts and in what crosses between the models: routers choose which model acts, planner–executor systems pass a plan, critics pass feedback, and handoff studies let the stronger model act first and pass its trajectory to a cheaper one [@handoff_tax_ganz_2026; @reach_or_solve_2026] (§7). What outside help buys depends on the receiver: in a controlled study of coding-agent harnesses, planning raised the weakest model's success by 11.6 percentage points on SWE-Bench Verified and mainly cut cost for the strongest [@harness_design_fan_2026]. We take a local 8B executor to sit in the first regime, where help changes success; this paper says nothing about planning for frontier executors. What has not been compared for such an executor is the *form* of the stronger model's help with the trigger and the context held fixed: an executed action, the same action shown as text, advice that may contain code, and terse correction prose.

We ask two questions on AppWorld [@appworld_trivedi_2024], with `gpt-5.6-luna` as the planner and IBM Granite 4.2 8B [@granite_4_2_ibm_2026] as the executor. **Channel:** at a matched trigger, does the planner's help land better as an executed action, as the same action shown, or as advice? **Depth:** if the planner acts for the first m steps and then hands off, how does quality change with m, and on which episodes?

All evidence is paired and from the dev split. Held-out runs have begun (J10's arm 3 ran once and is being refilled after a quota crash; J11's arm C is running), but no held-out result is read or reported here; A1 Amendment 3 discloses the `success_rate` lines seen while tallying J10 (`docs/prereg_j10_amendment_20260924.md`). Every number traces to a claims ledger (`docs/claims_ledger.md`) recording the report, the JSON key, and whether the contrast was registered before its data existed. The claims, each labelled:

- **Concrete code, executed or shown (exploratory; DEC-06, LIM-02).** Neutral-prompt advice carries fenced code in 207 of 221 interventions, correction-prompt advice in 3 of 260, and pairs where either arm hit the step limit carry +4.07 pp of the +6.13 pp gap. Test: J10 CF1 and limit reporting (Amendment 1 §C, §D).
- **Actions beat correction-prompt advice at a matched trigger (registered, C1; CHAN-C1-02, DEC-02).** The gap is +6.69 pp at 114 pairs on both clusterings and +6.13 pp at 171, where an exact randomization test gives p = 0.063. On TGC the 171-pair gap does not resolve (METRIC-01). Tests: J10 P6; J11 L1 with an open-weight planner.
- **The decomposition is unresolved (registered, B2; DEC-01).** Neither show nor neutral advice separates from correction-prompt advice or takeover.
- **Advice at every step is higher-frequency correction advice (registered H2; CHAN-PRICE-01, CHAN-PRICE-02).** Its cost prediction failed, so by the registration's rule we report it only as such, 14.68 pp below the m = 11 prefix: advice remains unpriced at the action channel's budget. Test: J10 P1 (Amendment 1 §E).
- **Depth (exploratory; HO-04, HSTAR-02, HSTAR-05, HSTAR-07).** The m = 6 → 11 `goal_pass` rise resolves over all episodes and over the 88 in which the executor took control (untailored: scenario bootstrap only), where it is about as large as over the 83 the replayed prefix finished; this replicates and extends Ganz et al. Tests: J12 D1–D4; J10 P4 for the untailored m = 9 → 11 step.
- **Non-inferiority to the planner acting alone (exploratory; HSTAR-11, HSTAR-14, HO-NI-01, ROB-21, CEILHI-03).** On `goal_pass` the m = 9 and 11 prefixes are non-inferior to the medium-effort planner at cap 81 in this harness. Over handoff episodes at m = 11 this holds because the executor rescues the planner's stalls, and fails over the episodes in which the planner had not stalled (§4.6). Against the cap-25 planner alone the tailored m = 11 prefix fails (−1.86 pp, [−8.51, +6.09]; Table D1), and no m = 11 prefix is non-inferior to the planner at high effort. Test: J10 P3 with a handoff-only companion (Amendment 1 §B1).
- **What a prefix conveys depends on depth and receiver.** At m = 9 narration and execution are not distinguishable at n = 114 (registered; NARR-01). Elsewhere the pattern is exploratory (NARR-03, NARR-04, DID-01).
- **What did not hold (registered).** Learned selective escalation is a null on dev (ESC-01); gate G1 (QUAL-06), chord test C2 (UF-07) and threshold test S3 (F1-RESULT-01) failed.

**Held-out tests (begun; nothing read).** **J10** (A1 with Amendments 1–3) tests P1–P6, content family CF1, and handoff-only, chord and step-limit companions; **J11** tests L1–L5 with the open-weight LP-2 planner; **J12** tests the m = 6 → 11 span over all and over handoff episodes (D1–D4). Their documents, freezes, h* amendments and power are in Appendix C.3. All three run on `test_normal`; until their reports are read, every number below is a dev estimate.

**What is new, and what is not.** The depth effect is not new: Ganz et al. report that a later downshift improves quality and retains less of the saving [@handoff_tax_ganz_2026]. New here, with a local 8B receiver tailored and untailored, are (i) a matched-trigger decomposition of act, show, neutral advice and correction advice, with every intervention's content measured; (ii) a narrated control that keeps a prefix's information and removes its execution; (iii) handoff-only companions beside the pooled depth and NI numbers, and a chord test; and (iv) registered nulls for learned escalation gates.

---

## 2. Setup

### 2.1 Environment, split and harness

AppWorld has nine everyday apps reached through APIs; the agent writes Python that reads and changes their state [@appworld_trivedi_2024]. We use a minimal harness that isolates the channel from scaffold effects: each action is a code block executed against the environment, its output or error is appended to the transcript, and an episode ends on `COMPLETE` or at the 40-step limit. Every experiment uses the dev split of the pinned release, which ships 57 dev tasks in 19 scenarios, run at seeds 1–2 (114 paired episodes) or 1–3 (171). Arms are paired on `(task_id, seed)`.

### 2.2 Planner, executors, and the planner acting alone

- **Planner.** `gpt-5.6-luna` at `medium` reasoning effort, with frozen prompts. Ganz et al. use this model as the *low-cost* model of their GPT pair [@handoff_tax_ganz_2026]; it is not a strong model in absolute terms.
- **Executors.** `ibm-granite/granite-4.2-8b`, either untailored (base weights) or tailored (the LoRA adapter `sft_b_plus_iaware_granite8b`, trained on 497 rows from the same planner's solved train-split trajectories; Appendix A.3). A handoff-suffix adapter and a second family, `Qwen/Qwen3-8B`, are in Appendix D.
- **The planner acting alone in the same harness.** Our reference, capped at 25 or 81 planner calls, is not a ceiling: raising the cap to 81 *lowered* `goal_pass` by 6.47 pp (scenario [−11.68, −1.37], task [−12.48, −0.46]; CEIL-07). It is limited by the harness, far below the same model's leaderboard score (Appendix D.8; CEIL-10), and by the planner's reasoning effort: at high effort it scores +11.97 pp higher on `goal_pass` (§4.7; CEILHI-01); every comparison with it names its cap.

### 2.3 Channels

Floors: the executor alone, and one plan (`sft_plan`: a planner plan at step 0, then the executor alone); Table D8 (Appendix D.11) places every arm. At a trigger of k = 10 steps, with the full transcript, the planner either writes **advice**, under the correction prompt "The executor needs a correction. Reply with concise correction text only." (**A**; `src/sidekick/agents/planner.py:118`) or the neutral prompt "Advise the executor on how to proceed with this task: say what it should do next. You may include code." (**N**; `:139-140`), which differ in their first line only; or writes an action the executor receives as text and never executes (**show, S**); or acts, its action executed before control returns (**takeover, T**). A **replayed prefix** (`prefix_m`) replays the first m actions of a recorded planner trajectory before the executor continues; if that trajectory already finished the task, a terminal guard ends the episode (GUARD-01). A **narrated prefix** gives the same m actions as text to an executor starting at step 0 in a fresh environment (§5). Every trigger is fixed: learned gates to call the planner selectively are a registered null on dev (ESC-01).

### 2.4 Metrics, and the floor of `goal_pass`

- **`goal_pass`** (`goal_pass_rate`) is the fraction of a task's required assertions that pass, and it has a floor: an executor that answers `COMPLETE` at step 1 scores 0.3569 mean `goal_pass` on dev (35.69 %, scenario [30.03, 41.29]), with every one of its 114 episodes above zero, and 0 on TGC and SGC (NOOP-01). It shifts arm means, not paired differences, but matters for ratio metrics (§4.5) and for how large a pp margin is relative to the usable range.
- **TGC** (task goal completion) is 1 only when every requirement of the task passes. We give it beside every `goal_pass` headline.
- **SGC** (scenario goal completion) scores a (scenario, seed) unit 1 only when all its tasks pass; it has no task clustering (METRIC-02).
- **Step limit.** An episode that reaches 40 steps is scored (`error_type == "limit"`); only crashes are dropped. Each arm's limit rate is printed beside its quality numbers or in Appendix D.10 (LIM-01).

### 2.5 Statistics

Contrasts are paired and bootstrapped over clusters, 10,000 percentile draws at seed 20260924 unless the ledger row states 20260915, as it does for 13 printed intervals (FDR-02; listed in Appendix A.4) [@koehn_bootstrap_2004; @clustered_eval_2026]. Scenario clustering (19 clusters) is primary and task clustering (57) is printed beside it (one-clustering companions: Appendix A.4). Because 19 clusters are few, headline contrasts also get an exact sign-flip test over all 2^19 scenario sign patterns (ROB-01), and a decision-relevant bound within 1 pp of its threshold is re-drawn at seven bootstrap seeds and called unresolved if its verdict changes (POOL-04). An interval that includes zero is reported as "not distinguishable at n = …", never as equivalence.

**The non-inferiority margin, and where it comes from.** δ = 7.00 pp. It is a margin of convenience, not a substantive one: the original registration derived it from a power analysis as the smallest TGC margin its held-out test could resolve, at ≥ 80 % power (simulated 0.86) with 3 seeds over 168 held-out tasks (NOISE-06), and the J9 freeze moved it to `goal_pass`. Non-inferiority (NI) holds when the scenario lower bound of arm minus reference is at least −7.00 pp.

### 2.6 What was registered, and what happened

Table 1 lists every registered item, its outcome, and whether its data had been seen when it was registered; Appendix C.2 counts campaigns, ledger rows and contrasts. A Benjamini–Yekutieli adjustment over the 60 paired-contrast intervals the main text printed keeps 13 at 0.05 with the earlier handoff flag, and 17 with h*; D0, C1, CEIL-07 and the m = 11 DiD survive neither (FDR-02, FDR-03; Appendix C.1).

Table 1: Registration outcomes. "Seen?" is whether the data the item is judged on existed when it was written; Appendix C.3 names each item's document.

| Item | Seen? | Outcome |
|---|---|---|
| v1 H2: selective escalation, conjunctive primary | Pilot figures yes; escalating arms no | Null on dev: no gate discriminates needed help, and the self-gate never fires (ESC-01). Demoted to a dev-only negative result (A1 §2) |
| v1 H1: TGC NI of the escalating system to the planner alone | As above | Not tested: the system it names never escalated (ESC-01); A1 replaced the J10 arm list |
| hj12 gate G1 | No | Failed on both clauses; the flat-curve branch is in force (QUAL-06) |
| hj12 C1: action vs advice at a matched trigger, made context-matched by the amendment of 2026-09-21 | Takeover and full-context advice arms no | Resolves at 114 pairs on both clusterings (CHAN-C1-02); extended to 171 pairs, exact test p = 0.063 (DEC-02) |
| hj12 C2: chord and NI of the prefix frontier | No | Failed: m = 9 chord residual +3.96 pp [−0.49, +8.88] (UF-07); the NI limb fails at m = 2, 4, 6 and 9 (UF-09) |
| hj12 C3: suffix-trained adapter extends the upper end | No | Negative (HF-02) |
| Depths m ∈ {7, 8, 10, 11} | Yes: chosen after the first grid | Exploratory by construction (QUAL-06); every m = 11 result is post hoc |
| hj13 S1–S3, segmented threshold test | Yes: written after the curve was seen | S1 and S2 hold and S3 fails in 8/8 configurations; no threshold is claimed (F1-RESULT-01) |
| hj13 replicate floor | Rise yes; replicates no | Withdrawal condition does not fire (NOISE-03). It would under NOISE-01's substitute floor |
| H2 P1–P4: advice at every step | No | P1–P3 hold; P4 fails (1,438,316 tokens per episode against 300k–700k), so §5's reporting rule applies (CHAN-PRICE-01, CHAN-PRICE-02) |
| B2 decomposition D1–D4 | C1 gap yes; B2 arms no | Unresolved: no decision rule fires (DEC-01) |
| J10: A1 + Amendment 1 | Dev yes; `test_normal` no | Under way (arm 3 being refilled); nothing read |
| J11: LP-2 planner, L1–L5 | Provisional LP-2 dev read yes; `test_normal` no | Under way (arm C); nothing read |
| J12: depth span, D1–D4 | Dev span yes; `test_normal` no | Pending |

---

## 3. How the planner's help reaches the executor

### 3.1 The matched-trigger contrast

Takeover and correction-prompt advice share the trigger (k = 10), the cached initial plan, the executor and its adapter, and the full transcript given to the planner; their configs differ in one field (CHAN-C1-00). At 114 pairs the registered contrast C1 gives takeover 0.8007 against advice 0.7339 `goal_pass` (TGC 0.5175 against 0.4386), a paired difference of **+6.69 pp** (scenario [+1.29, +13.48], task [+1.47, +12.35]; CHAN-C1-02) that passes an exact 19-scenario sign-flip test only narrowly (p = 0.0469). Its TGC companion, +7.89 pp (scenario [+1.75, +15.79], task [−0.88, +16.67]; ROB-22), does not pass it (p = 0.0781; ROB-02; SGC: Appendix A.4). At 114 pairs correction-prompt advice ends at the step limit in 13 episodes (ADV-FC-01), and takeover in 1 (CHAN-C1-01).

A third seed extends C1 to 171 pairs; the added 57 take their plan packets from the cap-81 planner campaign, so this is an extension, not a replication (DEC-02). The gap is **+6.13 pp** (scenario [+0.75, +12.71], task [+0.97, +11.73]), stable across seven bootstrap seeds, with exact randomization p = 0.063 (DEC-02). On TGC and SGC it does not resolve (Table 3; METRIC-01, METRIC-02), and on `goal_pass` it fails every BY adjustment (FDR-01, FDR-02, FDR-03; Appendix C.1). Live takeover and oracle prefix replay: Appendix D.4.

### 3.2 Decomposing the gap (registered, B2)

Takeover differs from correction-prompt advice in its prompt, its content (an action, not prose) and its delivery (executed, not shown). B2 separates them with two more arms at the same trigger and context, S and N (§2.3). All four arms have 171 pairs over seeds 1–3 and no crashes (DEC-01).

Table 2: The four channel arms at 171 pairs. Means from DEC-01 and METRIC-02; step-limit episodes from LIM-01.

| Arm | `goal_pass` | TGC | SGC | Step-limit episodes |
|---|---|---|---|---|
| T, takeover | 0.7899 | 0.4971 | 0.3158 | 2 of 171 (0.0117) |
| A, correction-prompt advice | 0.7285 | 0.4444 | 0.2807 | 20 of 171 (0.1170) |
| S, action shown, not executed | 0.7516 | 0.4561 | 0.3158 | 11 of 171 (0.0643) |
| N, neutral advice | 0.7658 | 0.5029 | 0.2982 | 14 of 171 (0.0819) |

Table 3: The B2 contrasts, 171 pairs, in pp; point, scenario interval, task interval. Holm over D1–D4 (DEC-01..04, DEC-07, METRIC-01, METRIC-02, LIM-03..05).

| Contrast | `goal_pass` | Holm p | TGC | SGC (scenario) |
|---|---|---|---|---|
| D0 = T − A | +6.13 [+0.75, +12.71] [+0.97, +11.73] | — | +5.26 [−0.58, +12.28] [−2.34, +13.45] | +3.51 [−3.51, +10.53] |
| D1 = T − S (execution) | +3.83 [−1.56, +10.81] [−0.94, +8.89] | 0.5976 | +4.09 [−2.34, +10.53] [−4.09, +12.28] | 0.00 [−10.53, +10.53] |
| D2 = S − A (prompt and content) | +2.30 [−2.43, +7.31] [−1.58, +6.28] | 0.7208 | +1.17 [−4.68, +8.19] [−5.26, +7.60] | +3.51 [−5.26, +12.28] |
| D3 = N − A (prompt) | +3.73 [−0.06, +8.24] [+0.04, +7.66] | 0.2192 | +5.85 [−1.17, +14.04] [−0.58, +12.87] | +1.75 [−5.26, +8.77] |
| D4 = T − N | +2.40 [−2.94, +8.89] [−1.97, +7.05] | 0.7208 | −0.58 [−8.77, +7.02] [−7.60, +6.43] | +1.75 [−5.26, +8.77] |

No registered decision rule fires (DEC-01). *Prompt artefact* needed D4's interval to include zero, which held, and D3's to exclude it, which missed at a lower bound of −0.06; *execution matters* and *content, not execution* needed D1's and D2's to exclude zero (−1.56, −2.43). We make no decomposition claim. D3's near miss is stable at all seven bootstrap seeds, with exact sign-flip p 0.1089 (DEC-03).

### 3.3 Where the gap sits: the step limit (exploratory)

Correction-prompt advice ends at the 40-step limit in 20 of 171 episodes, takeover in 2 (LIM-01; Figure 1). Splitting each contrast by whether either arm hit the limit conditions on an outcome of treatment, so the split describes a mechanism and is never a corrected estimate (LIM-02). For D0, the 22 pairs where either arm hit the limit contribute +4.07 pp of the +6.13 pp (scenario [+0.93, +7.72], task [+1.52, +7.12]); over the 149 where neither did, the mean difference is +2.37 pp (scenario [−0.59, +6.34], task [−1.67, +6.86]), unresolved. T − N shows the same pattern, and for N − A and S − A neither part resolves (LIM-03..05; Appendix D.10).

Scoring every limit episode as 0 widens all four gaps, so the concentration does not flatter takeover (LIM-06): D0 becomes +9.77 pp (scenario [+2.60, +17.97], task [+3.51, +16.41]), which does not survive the BY adjustment (FDR-01, FDR-02; the other three: Appendix D.10). Advised by terse correction prose, the executor more often runs out of steps; unlike Fan et al.'s weak coding agents, ours never stop before acting (TERM-01, TERM-02; Appendix D.10).

![Figure 1. The k = 10 arms, 171 pairs. (a) `goal_pass` against step-limit rate (DEC-01, LIM-01). (b) D0 = T − A (DEC-02) split by whether either arm hit the limit (n = 22) or neither (n = 149); scenario 95 % CIs, descriptive (LIM-02).](figures/f9_channel_limit.png)

### 3.4 What the advice contains (exploratory)

The two advice prompts differ in one line (§2.3); what they elicit differs sharply (DEC-06; 171 episodes per arm).

Table 4: Content of the planner's interventions (DEC-06). Shares with scenario and task intervals.

| | A, correction-prompt advice | N, neutral advice | S, shown action |
|---|---|---|---|
| Interventions | 260 | 221 | 228 |
| With a fenced code block | 3; share 0.0115 [0.0000, 0.0263] [0.0000, 0.0264] | 207; 0.9367 [0.8844, 0.9804] [0.9019, 0.9704] | 213; 0.9342 [0.9020, 0.9646] [0.9015, 0.9639] |
| Median length, characters | 242.0 | 1098 | 107.0 |
| Executor copy rate | 0.0115 | 0.1991 | 0.1667 |

The two copy rates differ in definition: advice counts its text or any fenced Python block in it, a shown action uses B2's definition (DEC-06).

**Reading (exploratory).** What helps the 8B executor is the planner's concrete code, executed (T) or shown (S, and N, which is mostly code); correction prose that almost never carries code leaves it stuck, more often at the step limit. The neutral prompt alone recovers +3.73 of the +6.13 pp; takeover's remaining lead over neutral advice (+2.40 pp) does not resolve, and on TGC it is −0.58 pp (DEC-03).

**Information, not structure (exploratory).** What the planner contributes looks like instance-specific information: the helpful advice is code (DEC-06), at m = 9 the planner's actions given as text are not distinguishable from the same actions executed (NARR-01; §5), and API discovery is front-loaded in the planner's trajectories (MECH-08). This reading came after the data; J10 tests it with CF1 and two unadjusted secondaries (Amendment 1 §C; Appendix D.5).

### 3.5 Advice at every step: higher-frequency correction advice (registered H2)

The registered H2 arm, `advise_fixed_k_1_fullctx`, requests correction-prompt advice at every step with full context. Its prediction P4 put its cost at 300k to 700k non-cached planner tokens per episode; it spent 1,438,316 and made 19.02 hosted calls per episode (CHAN-PRICE-02, ATTRIB-04). The registration's rule for a failed P4 reads: *"report the arm as a higher-frequency advice result only, and state explicitly that advice remains unpriced at the action channel's budget."* We follow it: **advice remains unpriced at the action channel's budget**.

As such it scores 0.6630 `goal_pass` (TGC 0.4474; CHAN-PRICE-01), with 12 of 114 episodes at the step limit (0.1053; LIM-01), 14.68 pp below the m = 11 prefix (scenario [−22.09, −7.04], task [−21.56, −7.79]; CHAN-PRICE-01) at 3.24× its non-cached tokens ([2.52, 4.11]; ROB-19, ATTRIB-04). P1 and P3 hold: the arm is not distinguishable from the one-plan floor and does no better than advice every ten steps, so ten times the review frequency does not buy quality (Appendix B, with P4's failure as a declared deviation). J10 P1 tests the contrast on held-out data under the same constraint (Amendment 1 §E).

### 3.6 Pending dev arms and controls

*Placeholder, to be filled when the ledger rows exist.* Four exploratory dev arms are built and not yet read: neutral-prompt advice at every step (k = 1), code-bearing advice at §3.5's frequency and a budget comparable to the prefix arms'; structured direction in the style of ManagerWorker and Minions at k = 10, a text-only protocol without §3.4's instance-specific content; the executor's own step-0 plan, for how much of the one-plan lift (Table D8) needs the planner; and a length-matched plan for a different task, separating task-specific content from plan-shaped text.

---

## 4. Handoff depth

A prefix arm replays the first m actions of a recorded planner trajectory; unless they end the episode, the executor then takes control. Our depth curve replicates and extends Ganz et al.'s downshift-timing result (§7) [@handoff_tax_ganz_2026]. Unless noted, §4.1–§4.6 use the pooled cap-81 prefix family: 171 pairs over seeds 1–3, prefix arms and the planner alone paired on the same trajectories. Every result in §4 is exploratory.

### 4.1 At m = 11 the prefix ends about half the episodes

A handoff means that the executor took control after the replayed prefix (h*), read from each episode's own events; h* agrees with the loop's terminal rule on all 1,026 prefix episodes (HSTAR-01). In the pooled cap-81 family the replayed prefix ends the episode in 4, 43 and 83 of 171 episodes at m = 6, 9 and 11, on both receivers, and there the executor never acts (HSTAR-02; cap-25 source: Appendix D.4). In 17 more at m = 11 the source planner had stopped executing and run out of steps without finishing; the executor took over and scored +48.29 pp `goal_pass` above that planner on the same (task, seed) (tailored; +37.74 pp untailored; descriptive and selected on the source's failure; HSTAR-14). An earlier indicator counted these 17 as no handoff (Appendix E.1). Every pooled depth or NI number in §4.2 and §4.6 carries its handoff-only companion, as the dev registration required (`docs/prereg_hj12_dev_20260922.md:336-341`); §4.7 and Table D1 have none.

Because h* is an outcome of the arm (estimator in Appendix A.4), handoff and silenced episodes are different tasks: the split describes which episodes the prefix finishes, not an effect of handing off (HSTAR-03). Step-limit counts for these arms are in Appendix D.10.

### 4.2 The span, pooled and handoff-only

Table 5: The m = 6 → 11 span, pooled cap-81 family, in pp; point, scenario interval, task interval. All episodes from HO-04..07; handoff-only (h* = 1, n = 88) and silenced (n = 83) from HSTAR-05..08. The split by the earlier flag is Table D2b.

| Receiver, metric | All episodes (171) | Handoff-only | Silenced |
|---|---|---|---|
| tailored, `goal_pass` | +8.39 [+4.20, +12.63] [+4.09, +12.96] | +7.66 [+1.19, +14.06] [+0.80, +14.69] | +9.17 [+5.12, +13.86] [+4.90, +13.83] |
| tailored, TGC | +15.79 [+8.19, +23.98] [+8.77, +23.39] | +10.23 [0.00, +23.53] [0.00, +21.13] | +21.69 [+12.50, +31.25] [+12.50, +31.43] |
| untailored, `goal_pass` | +7.70 [+3.69, +12.06] [+3.14, +12.30] | +7.81 [+0.79, +13.95] [−0.02, +15.57] | +7.59 [+3.28, +12.44] [+2.92, +12.89] |
| untailored, TGC | +11.70 [+6.43, +16.96] [+4.68, +18.71] | +9.09 [0.00, +17.65] [−1.25, +20.00] | +14.46 [+6.59, +22.67] [+5.68, +24.00] |

Over m = 6 → 11 the rise resolves over all episodes for both receivers and metrics. On `goal_pass` it also resolves over the episodes the executor took over, +7.66 pp tailored and +7.81 pp untailored (the latter on the scenario clustering only), and over those the prefix finished, +9.17 and +7.59 pp: handoff and silenced rises are of similar size (HSTAR-05, HSTAR-07). On TGC the handoff-only rise does not resolve on either receiver (HSTAR-06, HSTAR-08). On `goal_pass` the m = 9 → 11 step is weaker: no population resolves it on both clusterings at every bootstrap seed (Table D2, Appendix D.2; HO-04, POOL-01, HSTAR-05, HSTAR-07). J12 tests the four m = 6 → 11 `goal_pass` contrasts (D1–D4); J10's P4 tests the untailored m = 9 → 11 step.

**Where the rise is earned.** The depth effect is part planner finishing, part better handoffs, in proportions that vary with source and span; the handoff shares and their intervals are in Appendices D.2 and D.4 (HSTAR-10). Figure 2 shows each arm's mean over its own h* populations.

![Figure 2. `goal_pass` at m = 6, 9 and 11, pooled cap-81 family (171 pairs), by receiver: all, h* handoff and prefix-finished (silenced) episodes, with population sizes. Each arm has its own populations, so points are not paired contrasts (HSTAR-02..04).](figures/f10_depth_hstar.png)

### 4.3 No localizable breakpoint, and replicate noise

On the cap-25 grid m ∈ {2, 4, 6, 7, 8, 9, 10, 11}, all-episode `goal_pass` is non-decreasing in its point estimates, from 0.6856 at m = 2 to 0.8098 at m = 11 (SHAPE-06), and no adjacent step resolves (Holm-adjusted p = 1.0 for all eight; MULT-01). The segmented test, written after the curve was seen, holds S1 and S2 and fails S3 in 8/8 configurations, so no threshold is claimed (F1-RESULT-01); hinge and linear fits are in Appendix D.2 (ROB-15, ROB-24).

Run-to-run noise is not negligible: one arm's replicates differ by **3.31 pp** (NOISE-01). The replicate test's withdrawal condition does not fire at its own floor, but would at that one (NOISE-03; Appendix D.2).

### 4.4 The chord test

The dev frontier's claim C2 asked whether the prefix arms lie above the straight line (chord) from the one-plan floor to the planner acting alone, placed at each arm's share of hosted tokens. It failed: at m = 9 the residual was +3.96 pp ([−0.49, +8.88], task-clustered; UF-07), and its NI limb failed at every depth it named (Table 1). Re-run post hoc against the cap-81 planner alone (114 pairs), tailored m = 11 lies above the chord and tailored m = 9 is not resolved above it, on `goal_pass` and TGC (CHORD-01; Appendix D.4). J10 carries the chord test for m = 9 and m = 11 on both receivers (Amendment 1 §B3).

### 4.5 Ganz-comparable metrics and the cost share

Quality recovery, QRec = (arm − floor) / (reference − floor), with the one-plan floor (0.7181) and the cap-81 planner alone (0.7637) as anchors over 114 triples, is not resolved at any depth on either receiver (GANZ-01, GANZ-02), because the anchors are close. Savings retained fall with depth and every interval excludes zero: at m = 11, 0.3605 of the hosted-call saving and 0.4780 of the dollar saving are retained against the cap-81 planner (GANZ-03; intervals, all depths and the cap-25 ratios in Appendix D.9). Only the cost half of Ganz et al.'s trade-off is resolved: a deep prefix buys its gain by spending most of the planner's budget, 0.6550 of its hosted calls against the pooled cap-81 planner alone (COST-04).

### 4.6 Non-inferiority to the planner acting alone

The reference is the planner acting alone at cap 81 in the same harness, 0.7697 `goal_pass` and 0.5906 TGC over the 171 pairs (seeds 1–3); δ = 7.00 pp (§2.5).

Table 6: Arm minus the planner alone at cap 81, pooled, trajectory-paired, in pp; point, scenario interval, task interval; H = NI holds, F = fails. All episodes from HO-NI-01..03; handoff-only (h* = 1, n = 128 at m = 9 and 88 at m = 11) from HSTAR-11..13.

| Arm (mean `goal_pass`) | `goal_pass`, all 171 | `goal_pass`, handoff-only | TGC, all 171 | TGC, handoff-only |
|---|---|---|---|---|
| tailored m = 9 (0.7714) | +0.16 [−4.05, +4.65] [−4.29, +4.71] H | +0.21 [−5.28, +6.31] [−5.76, +6.29] H | −6.43 [−12.28, −0.58] [−12.87, −0.58] F | −8.59 [−16.00, −0.76] [−17.14, −0.71] F |
| tailored m = 11 (0.8139) | +4.41 [−0.74, +10.67] [+0.34, +8.65] H | +8.57 [−1.63, +18.25] [+0.67, +16.30] H | +0.58 [−5.85, +7.60] [−4.68, +5.85] H | +1.14 [−11.84, +13.68] [−8.97, +11.58] F |
| untailored m = 9 (0.7747) | +0.50 [−3.02, +5.36] [−3.50, +4.80] H | +0.67 [−4.14, +6.93] [−4.70, +6.33] H | −5.26 [−9.94, −0.58] [−10.53, +0.58] F | −7.03 [−13.28, −0.75] [−14.29, +0.71] F |
| untailored m = 11 (0.7892) | +1.94 [−2.17, +6.40] [−1.66, +5.75] H | +3.77 [−4.78, +10.98] [−3.33, +10.85] H | −2.92 [−7.02, +1.17] [−7.60, +1.75] F | −5.68 [−14.12, +2.63] [−15.28, +3.75] F |

On `goal_pass` every arm is non-inferior over all episodes and over the episodes the executor took over, at m = 9 and 11 on both receivers (HSTAR-11, HSTAR-12; Figure 3). At m = 11 the handoff-only reading holds because the executor rescues the planner's stalls, and fails over the episodes in which the planner had not stalled: the 17 rescues of §4.1 score +48.29 pp above the planner (HSTAR-14) and the 71 in which the planner was still acting after the prefix −0.94 pp ([−9.53, +7.45]; HO-NI-01, Table D2b), together Table 6's +8.57 pp (HSTAR-18); untailored, +37.74 and −4.36 pp (HO-NI-02). On TGC only the tailored m = 11 arm is non-inferior, and only over all episodes (HO-NI-03, HSTAR-13); with cap-25-sourced prefixes (114 pairs) the same TGC pass fails an exact one-sided sign-flip test (p = 0.0264; ROB-05). Against the cap-25 planner alone the tailored m = 11 prefix fails on both metrics (`goal_pass` −1.86 pp, [−8.51, +6.09]; ROB-21, Appendix D.1), and against the cap-81 planner at high effort neither m = 11 prefix is non-inferior (§4.7). NI here means "not distinguishable from the planner alone within δ at n = 171", not equivalence. J10's P3 tests the tailored m = 11 all-episode contrast with a handoff-only companion (Amendment 1 §B1).

![Figure 3. Arm minus the planner alone, `goal_pass`, pp, scenario 95 % CIs; dashed: δ = −7.00 pp. Rows: HSTAR-11, HSTAR-12; tailored m = 11 h* handoff split into flag-true (n = 71; HO-NI-01) and rescued (n = 17; HSTAR-14) (HSTAR-18); references ROB-21, CEILHI-03.](figures/f11_ni_forest.png)

### 4.7 The planner alone at high reasoning effort

This dev arm is exploratory: the planner acting alone at `reasoning_effort: high`, cap 81, seeds 1–2. On the same 114 keys it scores 0.8834 `goal_pass` and 0.7632 TGC against 0.7637 and 0.5702 at medium effort, +11.97 pp (scenario [+6.14, +18.43], task [+5.95, +18.25]) and +19.30 pp ([+9.65, +28.07]; [+10.53, +28.07]), and it hits the step limit in 4 episodes against 18 (CEILHI-01; cost and timeouts: Appendix D.8). Against it neither cap-81-sourced m = 11 prefix is non-inferior on either metric: the high-effort planner leads the tailored arm by +7.22 pp `goal_pass` ([+3.21, +11.47]; [+0.96, +13.41]) and the untailored by +9.02 pp ([+3.96, +14.06]; [+4.02, +13.97]), while on the same keys both hold on `goal_pass` against medium effort (CEILHI-03). The prefixes replay the medium-effort planner's trajectories, so this measures how far §4.6's reading depends on which effort defines the reference, not what a high-effort prefix would do.

---

## 5. What a prefix conveys: the narrated control

The narrated control puts the planner's first m actions as text in the executor's prompt and starts it at step 0 in a fresh environment: the prefix's information without its state (NARR-00). At m = 9, the registered contrast, executed minus narrated is +1.84 pp on the tailored receiver and +1.69 pp on the untailored, and all eight intervals over receivers and metrics include zero: narration and execution are not distinguishable at n = 114 (NARR-01; Table D3).

Elsewhere the receivers part (Appendix D.5). On the untailored receiver execution beats narration at m = 11 on both metrics and clusterings (`goal_pass`, narrated minus executed, −6.58 pp, [−9.98, −3.64], [−10.95, −2.71]) and the narrated curve is flat past m = 9 (NARR-03); on the tailored receiver no same-depth gap resolves (NARR-04; its narrated curve: Appendix D.5). The per-episode difference-in-differences between receivers at m = 11 is +6.09 pp (scenario [+1.56, +11.00], task [+0.63, +11.85]; exact sign-flip p = 0.0235); of three depths and two metrics, only this cell resolves under both tests, so it is exploratory (DID-01, ROB-08).

**Reading (exploratory).** At moderate depth a prefix's value travels as information; at the deep end an untailored receiver needs the execution, while a tailored one recovers it from the text. That the planner's observations add nothing detectable at m = 9 (NARR-05; Appendix D.5) does not show that the facts the actions returned carry no benefit.

---

## 6. Mechanism: descriptive correlates

Two correlates go with depth; neither is a causal test.

- **API discovery is front-loaded in the planner's trajectories.** Of 673 first uses of an API across 114 source episodes, 78.3 % occur by position 9 and 86.6 % by position 11 (MECH-08). This describes the source trajectories, not the executor.
- **The executor errors less after a deeper prefix.** The share of handoff episodes with at least one failed observation falls from 85.09 % at m = 2 to 42.59 % at m = 11 on the tailored receiver, and from 80.18 % at m = 6 to 61.11 % at m = 11 on the untailored (MECH-05). Handoff here is the flag: the tailored 42.59 % is 23 of 54, and h* counts 58, over which the rate was not recomputed (MECH-12; HSTAR-17). These rates are conditional on handing off, over populations that shrink with m, so they are not paired contrasts and carry no interval.

Our correlates are consistent with a deeper prefix lowering error incidence by leaving the executor less exploration and fewer steps, not by improving its planning: a description, not a mechanism shown.

---

## 7. Related work and positioning

**Handoffs between models.** Ganz et al. hand trajectories between low- and high-cost Claude and GPT models, in both directions and at several switch points, on SWE-bench Verified, Lost in Conversation and BrowseComp [@handoff_tax_ganz_2026] (their GPT low-cost model is our planner, §2.2). Escalation pays a "handoff tax", downshifting is a favourable cost–quality point, and "Later downshift generally improves quality while retaining less savings" (their App. B.2). Our depth curve replicates that result in AppWorld with a local 8B receiver (§1). Their finding that removing the stronger model's trajectory lowers downshift quality is the counterpart of our narrated control, which keeps the trajectory's text and removes its execution. Reach-or-Solve hands states between checkpoints and warns that analysing only states both reach selects on outcome [@reach_or_solve_2026]; our handoff-only populations carry that caution. Other handoff studies (Appendix F) do not compare the forms help takes either.

**Local–cloud collaboration and direction in text.** Minions pairs an on-device model with a cloud model and finds that the protocol decides the outcome: naive chat recovers less than a protocol in which the cloud model decomposes the task into subtasks for the local one [@minions_narayan_2025]. In ManagerWorker a text-only strong manager directs a cheap worker that holds the repository to the strong single agent's score, with structured exploration and planning adding far more than a review-only loop [@managerworker_liu_2026]. There text-only help works because the protocol is good; our correction prompt is a weak protocol, and the structured-direction arm (§3.6) is the prior-work baseline.

**Routing, escalation and demonstrations.** Cascades, routers, handoff policies learned or set by rule, speculative drafting and tool-making choose which model acts or drafts; our learned gates were a null (§2.3), so we vary the form of the help instead. Imitation, reverse curricula, agent tuning and prefix-based distillation use expert prefixes in training; ours is present at deployment (Appendix F).

**Planners, critics and advisors.** ReWOO and Plan-and-Act pass plans to executors [@rewoo_xu_2023; @plan_and_act_erdogan_2025], and role-factorised systems assign planner, executor or critic roles to models of different size [@coda_liu_2025; @agentcard_jiang_2026; @three_roles_2026; @think_big_search_small_2026]; we hold the planner frozen and vary the channel and the receiver (trained planners: Appendix F). Our tailored receiver is the plan-following fine-tune Liu et al. call for [@plan_to_action_liu_2026]; plan following, verbal feedback, self-correction and teaching by advice are in Appendix F.

**Where our arms sit.** Table D8 (Appendix D.11) places our arms in the slots above, with its caveats. On the same 114 keys, one plan lifts the tailored executor by +18.93 pp `goal_pass` and the base one by +9.82 pp (PLANTAX-02); the difference, +9.11 pp, does not resolve, while on TGC (+22.81 pp) it does (PLANTAX-03). Given a plan, tailoring is worth +42.97 pp; given m executed planner actions, no tailoring effect is detectable at m = 6, 9 or 11, so the difference-in-differences runs from +38.85 to +45.43 pp, every interval excluding zero (PLANTAX-04, PLANTAX-05; Qwen: Appendix D.11). Read together, and exploratory, this is the paper's best evidence that following a plan is learned, and it is consistent with the action channel bypassing the need to learn it. The two channels carry different content, one plan against m executed actions, and the tailored arms span adapter builds with no recorded git SHA (PLANTAX-01).

---

## 8. Limitations

1. **Dev only, one environment, one regime.** All results are on the 57-task dev split; J10 and J11 have begun but no held-out result is read here, `test_challenge` is sealed, and a second environment is still being built. The executor is in the weak regime (§1); nothing here speaks to frontier executors.
2. **One planner on dev.** A Qwen3-8B planner fails LP's informativeness gate (−26.23 pp against the tailored executor alone; LP-01); J11 tests an LP-2 planner on held-out data.
3. **A weak reference.** The planner alone scores lower with a larger call cap (CEIL-07), below its leaderboard score with learned context assets (Appendix D.8), and higher at high effort, against which no m = 11 prefix is non-inferior (§4.7).
4. **Few clusters and many contrasts.** Exact tests pass the 114-pair channel result only narrowly and not the 171-pair one; BY over the main text's 60 paired intervals keeps 13, or 17 under h*; the dev reports hold at least 2,164 distinct paired contrasts; and the ledger's exploratory rows outnumber its registered ones by 86 to 32. Sources: FDR-02, FDR-03, CENSUS-02, CENSUS-01.
5. **Forking paths.** The headline reading, the depths m ∈ {7, 8, 10, 11}, the handoff-only and limit analyses and the chord re-run were all chosen after data (Table 1).
6. **A declared deviation.** H2's arm follows its registration's rule; the counter-argument is in Appendix B.
7. **Pending arms.** Only one arm (N) uses the neutral prompt; §3.6's four arms are pending.
8. **Metric floors and the second family.** `goal_pass` awards about a third of its scale for doing nothing (NOOP-01), and the Qwen family's floors measure format acquisition rather than competence (Appendix D.7).
9. **Privacy and latency.** Privacy, a common reason to keep the executor local, is not delivered: the hosted planner sees the task in every arm, writes the prefix and reads the transcript at each trigger. Per-call latency was not recorded (LAT-01).

---

## 9. Conclusion

On the AppWorld dev split, a local 8B executor does better when the hosted planner's help arrives as concrete code, executed or shown, than as terse correction prose; that reading is exploratory. The registered matched-trigger contrast resolves at 114 pairs and weakens at 171, most of its gap sits where the correction-advised executor runs out of steps, and a neutral prompt that elicits code recovers +3.73 of its +6.13 pp without quite resolving. Handing off later raises quality over all episodes and, on `goal_pass`, over the episodes the executor took over, by about as much as over those the prefix finished; the effect replicates a published downshift-timing result. On `goal_pass` the deep prefix is non-inferior to the medium-effort planner at cap 81 in this harness, over handoff episodes only through the executor's rescues of the planner's stalls; not to the cap-25 planner (tailored executor) or to the same planner at high effort. J10, J11 and J12 test these claims on held-out data.

---

## Appendix A. Reproducibility and statistics

### A.1 The ledger and the number audit

Every number in this paper is produced by a script from per-episode `result.json` files and recorded in `docs/claims_ledger.md` with its report path and JSON key. `scripts/analysis/preprint_number_audit.sh` checks the draft against the ledger mechanically: unsigned percentage-point figures and four-decimal rates as set differences, signed figures with their sign, intervals as ordered pairs, forbidden wording, and registration wording beside exploratory ledger ids; it fails on any violation. A NEEDS-LEDGER marker in double square brackets names a number that has no ledger row yet and is not printed. The check exists because of a real failure (Appendix E.2).

The report `campaign/results/j10_a1_registered_dev_basis_20260924.report.json`, which sources the like-for-like cap-81 contrasts of Appendix D.4, holds **dev data only**. Its name records that the A1 registration cites it as its dev basis; it contains no `test_normal` episode.

### A.2 Figures

No figure is drawn from retyped numbers: `scripts/analysis/figures.py` reads each series from a report by key and refuses to render a panel whose key is missing (FIG-01); `paper/figures/figures_manifest.json` records every figure's source reports and keys. The main text cites three figures:

- **Figure 1** (`f9_channel_limit`, §3.3): arm means and D0 from `campaign/results/b2_decomposition_20260923.report.json` (`arms.{T,S,N,A}.goal_pass_mean`, `contrasts.D0.scenario`); step-limit rates and the D0 split from `campaign/results/j17_channel_fixes_20260924.report.json` (`limits.per_arm`, `limits.split.D0`). The script refuses to draw it if an arm's limit rate is over other pairs than its mean, or if the two parts do not sum to D0.
- **Figure 2** (`f10_depth_hstar`, §4.2): `handoff_only.{bplus,zs}.m{6,9,11}.goal_pass` and `handoff_control_counts` in `campaign/results/j17_hstar_20260924.report.json`. The per-depth means by population are in that report, so no contrast is drawn in their place. Each population is the arm's own h* split, so no line is a paired contrast (Table 5 holds those), and no marginal band is drawn.
- **Figure 3** (`f11_ni_forest`, §4.6): `ni.{bplus,zs}.{m9,m11}.goal_pass` and `rescued_m11.bplus.summary` in the same h* report; the flag-true part from `campaign/results/j17_depth_fixes_20260924.report.json`; ROB-21 from `campaign/results/j16_robustness_20260923.report.json`; CEILHI-03 from `campaign/results/j17_planning_lit_20260924.report.json`. CEILHI-03 is stored as planner minus arm and is drawn with its sign reversed, as arm minus planner like every other row. The rescued row lies beyond the axis and is drawn as an arrow with its value and interval printed. The script refuses to draw the figure unless the flag-true and rescued parts, weighted by count, reproduce the h* handoff contrast (HSTAR-18).

### A.3 Models, adapters and decoding

| Role | Model | Adapter |
|---|---|---|
| Planner | `gpt-5.6-luna`, `reasoning_effort: medium`, frozen for the campaign | — |
| Executor, tailored | `ibm-granite/granite-4.2-8b` | `sft_b_plus_iaware_granite8b` |
| Executor, untailored | `ibm-granite/granite-4.2-8b` | none (`lora_name: null`) |
| Executor, suffix-trained | `ibm-granite/granite-4.2-8b` | `sft_b_plus_handoff_granite8b` |
| Second family, tailored | `Qwen/Qwen3-8B` | `sft_b_plus_iaware_qwen8b` |
| Second family, untailored | `Qwen/Qwen3-8B` | none |

Both tailored adapters were trained on the same 497-row file (`sft_b_plus_iaware_20260920.jsonl`) with the same LoRA recipe; the training and decoding hyperparameters are in the committed training and evaluation configs. Executor decoding samples at temperature 0.7 with no fixed sampling seed (NOISE-01).

One configuration rule matters for anyone reproducing an untailored arm: configure it under the `prompt_only` system, never under `sft_plan`. `SftPlan.policy_defaults` sets `adapter_name: "sft_plan"` (`src/sidekick/systems/sft_plan.py:11`, the field at `:18`), and a config whose `lora_name` is null falls through to that default (`src/sidekick/runner.py:308-310`), so an untailored config placed under `sft_plan` runs a configuration no one intended while its logs name the alias. (An earlier draft cited a `src/sidekick/policies/` path that does not exist; A1's Amendment 1 §G records the same correction.)

### A.4 Statistical protocol

Contrasts are paired on `(task_id, seed)` and bootstrapped over clusters, not episodes: 10,000 percentile draws, scenario-clustered as primary and task-clustered beside it, because the 57 dev tasks form only 19 scenario groups. A crashed episode scores 0 under the all-episodes population; `limit` is not a crash and keeps its score. Difference-in-differences contrasts are formed per episode before averaging, so the pairing survives into the bootstrap. The handoff-only estimate is Σd·h / Σh over pairs, with h = h* of the deeper (m = 11) arm, 1 when the executor took control after the replayed prefix (HSTAR-01), and whole clusters resampled. The earlier indicator, the arm's `handoff_occurred` flag, is kept as a sensitivity (Table D2b; HO-04, HSTAR-16).

**Seed 20260915.** Thirteen printed intervals come from reports that bootstrap at seed 20260915, the j8_frontier default, not 20260924 (FDR-02): the cap-81 change in `goal_pass` (CEIL-07); C1 at 114 pairs, `goal_pass` and TGC (CHAN-C1-02, ROB-02); advice at every step against `prefix_m11` on `goal_pass` and TGC, against the one-plan floor and against advice every ten steps (CHAN-PRICE-01, ROB-04); the m = 9 chord residual (UF-07); executed minus narrated at m = 9 on both receivers (NARR-01); untailored narrated minus executed at m = 11 and the untailored narrated m = 9 → 11 step (NARR-03); and tailored narrated minus executed at m = 11 (NARR-04). The Appendix D.5 intervals taken from the same two narrated-curve reports are drawn at 20260915 too, on both clusterings (NARR-03, NARR-04, NARR-06): Table D4's other cells, the TGC narrated-minus-executed gaps, the tailored and untailored narrated curves' depth steps, and tailored narration at m = 11 against execution at m = 6. Every p value that FDR-02 adjusts is drawn at 20260924.

**Boundary stability (POOL-04).** At B = 10,000 the Monte Carlo error on a percentile bound is a few tenths of a point, so any decision-relevant bound within 1 pp of zero or of the margin is re-drawn at the seven seeds 20260924, 1, 2, 3, 7, 101 and 999, and the quantity is unresolved if the verdict changes. TGC is discrete, so a TGC bound can be identical at every seed without being precise.

**Small-cluster alternatives.** Headline contrasts were re-tested with a two-sided sign-flip randomization test, exact on the 19 scenarios and Monte Carlo on the 57 tasks, and with wild cluster bootstrap intervals; NI uses the one-sided sign-flip test against the margin (ROB-01).

**Rows with one clustering.** CHAN-C1-02's TGC companion (ROB-02), ROB-11, ROB-13 to ROB-21, NARR-04, UF-07 (whose single interval is task-clustered) and the ratio intervals of ROB-19 and ROB-20 were printed with one clustering; their companions are ROB-22 to ROB-27, NARR-06 and UF-10. ROB-11's SGC has no task clustering (ROB-22); for C1 at 114 pairs, SGC advice minus takeover is −7.89 pp [−21.05, +2.63] (ROB-02, ROB-11). Four readings change on tasks. C1's 114-pair TGC companion, which already fails the exact test, includes zero (task [−0.88, +16.67]; ROB-22). The hinge's preference over a line has p 0.054 (ROB-24). Tailored narration fails NI at m = 9 (task lower bound −7.75), while its m = 9 → 11 rise includes zero ([−0.40, +8.20]) (NARR-06). And takeover's dollar saving over correction-prompt advice, the one cost difference that resolved on scenarios, includes zero on tasks (Appendix D.9; ROB-18, ROB-27). Otherwise every verdict is the same on tasks: all 32 NI cells of Table D1 and its cap-81 companions (ROB-25), the reference's kept-minus-dropped gap, which resolves (cap 25: +75.95 pp, task [+62.93, +86.66]; ROB-26), and every cost ratio of ROB-19 and ROB-20 (ROB-27). UF-07's chord residual has scenario interval [−0.41, +8.81] (UF-10), and the cap-25 decompositions keep their verdicts (ROB-23).

### A.5 Provenance

Campaign-granularity provenance for every campaign a report reads is generated by `scripts/analysis/campaign_index.py` into `campaign/campaign_index.{json,md}`. Three gaps remain. The run record stores less than the index reports: the index's config, adapter and source-campaign fields are reconstructed from the repository, not recorded by the run. Several campaigns, including the dev prefix arms, ran under a campaign id passed on the command line rather than the one their config declares, so re-running such a config verbatim writes to a different directory. And two dependencies, including the third planner sample, have no committed config. The runner now stamps git SHA, config, adapter, source campaign and split into every episode manifest; every campaign behind this paper predates that change.

No published campaign is proven to contain a second roll of a scored failure (PROV-01). In six published prefix arms, all outside the headline depth curves, hosted luna answered an executor's ask live, which bounds each arm-mean lift (PROV-02; Appendix D.6).

---

## Appendix B. Declared deviation: H2's failed cost prediction (CHAN-PRICE-02)

**What was registered.** P4 predicted that advice at every step would spend 300k to 700k non-cached planner tokens per episode, and §5 of the H2 registration says that if P4 fails, the arm is reported "as a higher-frequency advice result only", stating "that advice remains unpriced at the action channel's budget". The main text (§3.5) follows that rule.

**The argument we set aside.** An earlier draft argued that the rule was written for the opposite case: an arm that lands below 300k was never priced at the action channel's budget, so a win over it could be a budget win, while this arm spent 1,438,316 tokens, far above the prefix arms, and so the hazard the rule guards against was excluded *a fortiori*. On that argument the draft reported P2 as a test of advice at matched budget. We record the argument as a deviation discussion and do not rely on it, for two reasons. The registration's text does not distinguish the directions of failure. And the argument is weak on substance: P3 shows that more correction advice does not do better, so moving from k = 10 to k = 1 changes the dose of an error-presuming prompt; it does not match the budget.

Table B1: Advice at every step beside the arms it was compared with (114 pairs; CHAN-PRICE-01, CHAN-PRICE-02, COST-01; each advice arm's replayed plan is charged its source plan's tokens, ATTRIB-01, ATTRIB-04).

| Arm | `goal_pass` | Non-cached planner tokens / episode | Hosted calls / episode | Step-limit episodes |
|---|---|---|---|---|
| `advise_fixed_k_10_fullctx` | 0.7339 | 73,725 | 2.46 | 13 of 114 (ADV-FC-01) |
| `advise_fixed_k_1_fullctx` | 0.6630 | 1,438,316 | 19.02 | 12 of 114 (0.1053; LIM-01) |
| `prefix_m9` | 0.7852 | 357,448 | 9.77 | 10 of 114 (LIM-08) |
| `prefix_m11` | 0.8098 | 443,361 | 11.25 | 9 of 114 (LIM-08) |

Against the m = 11 prefix the arm's TGC is −15.79 pp ([−28.07, −3.51]; [−25.44, −5.26]; CHAN-PRICE-01), and it makes 1.69× the prefix's hosted calls ([1.51, 1.89]; ROB-19). Against the one-plan floor the arm is −5.51 pp (scenario [−13.15, +2.51], task [−12.63, +1.72]), so P1 holds as an interval that includes zero (CHAN-PRICE-01); against advice every ten steps it is −7.08 pp (scenario [−14.78, +0.67]), so P3 holds on the scenario clustering, and on the task clustering the upper bound is negative at six of seven bootstrap seeds (ROB-04). Against the cap-81-sourced tailored m = 11 prefix, advice at every step is −14.81 pp [−21.20, −7.96] (CEIL-05), and on SGC against `prefix_m11` it is −23.68 pp [−42.11, −7.89] (ROB-11). The one advice arm near the prefix arms' budget, `advise_fixed_k_3`, ran with an 8-line context and is −2.25 pp against the m = 6 prefix ([−9.05, +5.15]), confounding depth with context starvation (ROB-20).

---

## Appendix C. Multiplicity and census

### C.1 Benjamini–Yekutieli over what the main text prints (FDR-02) and over the re-analysis contrasts (FDR-01)

**Over every printed paired-contrast interval (FDR-02).** The family is every paired-contrast interval the abstract and §1–§9 printed on 2026-09-24, one per distinct contrast, population and metric: 60 intervals (33 `goal_pass`, 21 TGC, 6 SGC). Ratios, shares, slopes, arm means and the appendices are excluded; the NI cells of Table 6 are tested at −7.00 pp and everything else at 0. With the two-sided scenario-clustered bootstrap p, 13 survive at 0.05; with the exact sign-flip p, 4. The 13: advice at every step against `prefix_m11`; the m = 6 → 11 span over all episodes on both receivers and both metrics; the tailored `goal_pass` span over handoff episodes and the tailored TGC span over silenced ones, both split by the flag; the tailored m = 11 chord residual against cap 81; the four all-episode `goal_pass` NI tests; and untailored narrated minus executed at m = 11. Not surviving, among others: D0 (raw 0.0202), C1 at 114 pairs, CEIL-07, the limit-as-0 D0, the m = 11 DiD and the untailored handoff-only span. FDR-02 was computed on the draft before §4 moved to h*, so its handoff-only and silenced members are the flag-based values of Table D2b.

**The same set with the handoff split read by h\* (FDR-03).** Every handoff-only and silenced member is swapped for its h* value and p (HSTAR-05..08, HSTAR-11..13) and every other member is kept. On the bootstrap p 17 of the 60 survive, and on the sign-flip p 7. Among the handoff members, the four silenced spans (Table 5) and the handoff-only `goal_pass` NI tests at tailored m = 11 and untailored m = 9 (Table 6) survive on the bootstrap p. The tailored `goal_pass` span over handoff episodes, which survived under the flag, no longer does, and no other handoff-only span or NI test survives. On the sign-flip p no handoff-only member survives; the tailored silenced spans on both metrics do. D0, C1, CEIL-07, the limit-as-0 D0 and the m = 11 DiD still fail. The swap is valid only if the two reports' p are the same statistic, and every swapped member's all-episode sibling has the same point and p in both.

**Over the re-analysis contrasts (FDR-01).** This narrower family is every `goal_pass` contrast in the two dev re-analysis reports, 28 in all (8 channel, 20 depth), mixing superiority tests with the NI tests of Table 6, with handoff-only members also split by the flag. At 0.05, 9 survive. FDR-01 was not re-run under h*; for the handoff members read by h*, FDR-03 above is the adjustment to use.

Table C1: Survivors (raw p → BY-adjusted p; FDR-01).

| Contrast | Raw p | BY p |
|---|---|---|
| tailored m6 → m11, all episodes | 0.0002 | 0.0044 |
| tailored m6 → m11, handoff-only | 0.001 | 0.0183 |
| tailored m9 → m11, handoff-only | 0.0034 | 0.0440 |
| untailored m6 → m11, all episodes | 0.0 | 0.0 |
| untailored m6 → m11, handoff-only | 0.0036 | 0.0440 |
| NI tailored m9, all episodes | 0.0012 | 0.0189 |
| NI tailored m11, all episodes | 0.0 | 0.0 |
| NI untailored m9, all episodes | 0.0 | 0.0 |
| NI untailored m11, all episodes | 0.0 | 0.0 |

Not surviving, among others: the 171-pair channel gap D0 (raw 0.0202, BY 0.1587), the limit-as-0 D0 (BY 0.0528), every handoff-only NI test, including the untailored m = 9 one that holds by its interval (BY 0.0696), and the tailored all-episode m = 9 → 11 rise (BY 0.3006).

### C.2 Census (CENSUS-01)

The campaign index lists 70 campaigns; 47 are dev campaigns, and they form 39 distinct dev arms. When the census report was built, the ledger held 149 rows, of which 32 were registered, 86 exploratory and 31 of other status (amended, correction, method, pending and similar). Those counts predate the re-analysis rows. Source: CENSUS-01. The dev report JSONs hold at least 2,164 distinct paired contrasts with an interval, 8,917 contrast objects in 68 dev report files; shares, ratios and tests printed without an interval are not counted, so this is a lower bound (CENSUS-02).

### C.3 Registration documents for Table 1

- v1 H2 and H1: `docs/prereg_v1.md` §1.1; for H2, also the J9 freeze.
- hj12 G1, C1, C2, C3: `docs/prereg_hj12_dev_20260922.md` (G1 §5, with the flat-curve branch at lines 295-310; C2 at lines 38-40), with the amendments of 2026-09-21 (C1 context matching) and 2026-09-22 (depths m ∈ {7, 8, 10, 11}).
- hj13 S1–S3 and the replicate floor: `docs/prereg_hj13_shape_20260923.md` §3.
- H2 P1–P4: `docs/prereg_h2_advice_at_price_20260923.md` §4–§5.
- B2: `docs/prereg_c1_decomposition_20260923.md`.
- J10: `docs/prereg_j10_amendment_20260924.md` (A1 at 142e947, Amendment 1 at 138c285; Amendment 2, 3a97543, confines P3 to non-inferiority to the medium-effort planner at cap 81; Amendment 3 reads §B's handoff-only companions with the indicator h* of §4.1).
- J11: `docs/prereg_j11_lp2_test_20260924.md`, frozen at 6f40fec; Amendment 1 reads L3–L5's handoff companions with h*. The LP-2 planner is `Qwen/Qwen3.8-27B-FP8`.
- J12: `docs/prereg_j12_depth_test_20260924.md`, frozen at 6f40fec; Amendment 1 reads D3–D4 with h*, and at the dev effect its simulated power is then 0.866 (D3), 0.819 (D4) and 0.733 for all four (HSTAR-15). Under the flag, simulated power at the dev effect was 0.998 (D3), 0.987 (D4) and 0.985 (all four).

---

## Appendix D. Supplementary analyses

### D.1 Non-inferiority against both planner-alone references (ROB-21)

Table D1: Arm minus the planner acting alone, scenario 95 % CI, n = 114; H = NI holds (lower bound ≥ −7.00 pp), F = fails (ROB-21). Cap-25-sourced arms are trajectory-paired with the cap-25 reference and only task-paired with cap-81; cap-81-sourced arms the reverse.

| Arm | `goal_pass` vs cap-25 | `goal_pass` vs cap-81 | TGC vs cap-25 | TGC vs cap-81 |
|---|---|---|---|---|
| tailored m = 11 (`prefix_m11`) | −1.86 [−8.51, +6.09] F | +4.61 [−1.42, +11.92] H | −7.89 [−17.54, +2.63] F | +3.51 [−6.14, +13.16] H |
| untailored m = 11 | +0.61 [−3.66, +5.58] H | +7.08 [+1.82, +12.78] H | −6.14 [−13.16, +0.88] F | +5.26 [−4.39, +14.91] H |
| tailored m = 9 | −4.32 [−12.48, +4.51] F | +2.15 [−4.08, +9.77] H | −12.28 [−23.68, −0.88] F | −0.88 [−9.65, +8.77] F |
| untailored m = 9 | −4.39 [−9.52, +0.94] F | +2.08 [−4.39, +9.19] H | −13.16 [−21.05, −5.26] F | −1.75 [−11.40, +8.77] F |
| tailored m = 11, cap-81 source | −1.72 [−8.95, +6.47] F | +4.75 [−1.16, +11.81] H | −8.77 [−21.05, +3.51] F | +2.63 [−5.26, +11.40] H |
| untailored m = 11, cap-81 source | −3.52 [−9.78, +3.43] F | +2.95 [−1.91, +8.69] H | −13.16 [−23.68, −1.75] F | −1.75 [−7.02, +4.39] F |
| `takeover_fixed_k_10` | −2.77 [−12.34, +7.42] F | +3.70 [−5.17, +13.60] H | −16.67 [−30.70, −1.75] F | −5.26 [−15.79, +5.26] F |

**Orientation and keys.** Every NI number in this paper is arm minus reference. CEIL-05 and POOL-02 store reference minus arm; we print their contrasts from ROB-21, HO-NI-01..03 and HSTAR-11..13, which use arm minus reference. The one exception is labelled where it is printed: §4.7 gives CEILHI-03's high-effort planner minus arm, as stored. For tailored m = 9 TGC against cap 81 we print ROB-21's key (`F_e_ni_both_ceilings.ni_table.t_m9.cap81_tgc`, [−9.65, +8.77]); COST-03's separate run of the same contrast gives [−9.65, +7.89], and the two runs use different bootstrap seeds (ROB-05 names COST-03's as 20260915).

**The v1 abstract's claim, qualified.** Against cap 81, three of the four m = 11 arms hold on both metrics. Two of those three are cap-25-sourced and so only task-paired with the reference, and of the two trajectory-paired (cap-81-sourced) arms one fails TGC. The tailored `prefix_m11` TGC pass fails an exact one-sided sign-flip test (p = 0.0264; ROB-05). Against the trajectory-paired cap-25 reference only the untailored m = 11 arm holds, on `goal_pass` alone; the +0.23 pp NI in UF-06 belongs to the pre-guard arm (ROB-16).

**Excluding the reference's limit episodes.** Restricting the cap-25 reference to the 102 episodes in which it did not hit its call cap makes `prefix_m11` fail (−5.92 pp, scenario [−9.80, −2.57]; CEIL-01), but that exclusion selects on the reference's own failures: on cap-25 the 12 dropped episodes score 0.1488 against 0.9083 on those kept, on cap-81 the 18 dropped score 0.1786 against 0.8734, and the reference-free difficulty proxies do not resolve (ROB-17, ROB-21). We treat −5.92 pp as a bound under that selection.

### D.2 The third planner seed and the boundary (POOL-01, POOL-04, ROB-06)

A third planner seed plus six replay arms that make no hosted calls pool the cap-81 sample to 171 pairs, none dropped (POOL-01). The m = 6 → 11 spans survive exact sign-flip tests (p = 0.0019 untailored, 0.0014 tailored; ROB-06). The tailored m = 9 → 11 step does not resolve: its scenario interval [+0.15, +8.75] clears zero by 0.15 pp, and re-running the identical estimand at the seven bootstrap seeds 20260924, 1, 2, 3, 7, 101 and 999 gives lower bounds of +0.1526, +0.0801, +0.0544, −0.0140, +0.1468, +0.1953 and +0.1088, with +0.1041 at 200,000 resamples (POOL-01). The verdict flips at one seed in seven, the exact test gives p = 0.0749 (ROB-06), and pooling narrowed the interval by 1.98 pp of width (10.57 → 8.59) without converting a null into a finding. The untailored step, +2.82 pp at two seeds (CEIL-05), is +1.44 pp at three (HO-06).

Curve shape (§4.3): a hinge beats a line (p = 0.036 on scenarios) only because of the plan-only m = 0 anchor, and not under task clustering (p = 0.054; ROB-24); the prefix arms alone fit a line at +1.43 pp per step ([+0.80, +2.04]; ROB-15).

Replicate noise (§4.3): the largest single-arm replicate deviation is 3.31 pp (`prefix_m2`, 0.7187 then 0.6856, across a code change that does not fire at m = 2; NOISE-01). The registered replicate floor, re-running m = 6 and m = 9, gave 0.04 and 1.82 pp and does not trigger its withdrawal condition (NOISE-03). Under NOISE-01's 3.31 pp as the floor, it would.

Table D2: The m = 9 → 11 step, pooled cap-81 family, in pp; point, scenario interval, task interval. All episodes from HO-04..07; handoff-only (h* = 1, n = 88) and silenced (n = 83) from HSTAR-05..08. The m = 6 → 11 span is Table 5.

| Receiver, metric | All episodes (171) | Handoff-only | Silenced |
|---|---|---|---|
| tailored, `goal_pass` | +4.25 [+0.15, +8.75] [+0.90, +7.87] | +6.82 [−0.34, +13.03] [+0.96, +12.46] | +1.53 [−1.00, +4.69] [−0.69, +4.14] |
| tailored, TGC | +7.02 [+1.17, +13.45] [+1.75, +12.87] | +9.09 [+1.00, +18.75] [+1.22, +17.39] | +4.82 [−1.16, +11.54] [0.00, +10.96] |
| untailored, `goal_pass` | +1.44 [−2.56, +5.52] [−2.60, +5.64] | +3.75 [−4.01, +11.38] [−3.99, +11.47] | −1.00 [−3.26, +1.37] [−3.37, +1.41] |
| untailored, TGC | +2.34 [−2.34, +7.02] [−2.92, +8.19] | +6.82 [−2.47, +16.67] [−3.66, +17.65] | −2.41 [−6.74, +2.35] [−7.06, +2.41] |

The tailored all-episode TGC rise resolves on the bootstrap but has exact sign-flip p 0.0586 (HO-05); over handoff episodes it resolves on both clusterings, with sign-flip p 0.1172 (HSTAR-06). Over the m = 6 → 11 span (§4.2), handoff episodes earn a share of 0.4699 of the tailored `goal_pass` rise (scenario [0.13, 0.66], task [0.08, 0.68]) and 0.5218 of the untailored ([0.09, 0.76]; [0.00, 0.79]) (HSTAR-10). On the tailored step the handoff share of the `goal_pass` rise is 0.8255 ([0.28, 1.24]; [0.41, 1.14]) and of the TGC rise 0.6667; the untailored step does not resolve, so its shares are not read (HSTAR-09).

**The flag sensitivity (HO-02..HO-NI-03, HSTAR-16).** Before h*, the split used the prefix arm's `handoff_occurred` flag, which is false whenever the source made no more than m executed actions, finished or not (Appendix E.1). Switching to h* moves no all-episode value; it moves 11 (m = 9) and 17 (m = 11) episodes from silenced to handoff (HSTAR-02, HSTAR-16). Table D2b gives the flag-based values the earlier draft printed.

Table D2b: The split by the `handoff_occurred` flag, pooled cap-81 family, in pp; handoff-only n = 71 and silenced n = 100 for the spans, handoff-only n = 117 at m = 9 and 71 at m = 11 for NI (HO-04..07, HO-NI-01..03).

| Receiver, quantity | Handoff-only (flag) | Silenced (flag) |
|---|---|---|
| tailored, `goal_pass`, m = 6 → 11 | +12.03 [+5.49, +18.57] [+5.07, +19.19] | +5.81 [+1.00, +11.17] [+0.51, +11.28] |
| tailored, TGC, m = 6 → 11 | +15.49 [+3.03, +30.16] [+4.69, +27.40] | +16.00 [+7.45, +24.55] [+7.14, +25.49] |
| untailored, `goal_pass`, m = 6 → 11 | +13.93 [+5.12, +21.22] [+5.48, +22.42] | +3.27 [−1.71, +8.10] [−1.81, +8.51] |
| untailored, TGC, m = 6 → 11 | +15.49 [+4.29, +26.47] [+4.41, +26.92] | +9.00 [+1.05, +16.67] [0.00, +17.78] |
| tailored, `goal_pass`, m = 9 → 11 | +7.73 [+2.51, +13.05] [+2.48, +13.00] | +1.78 [−2.03, +6.58] [−2.09, +6.12] |
| tailored, TGC, m = 9 → 11 | +9.86 [+2.60, +20.00] [+2.99, +18.03] | +5.00 [−0.96, +11.63] [−1.05, +11.76] |
| untailored, `goal_pass`, m = 9 → 11 | +0.27 [−6.57, +6.96] [−7.59, +7.83] | +2.27 [−1.77, +6.98] [−1.71, +6.64] |
| untailored, TGC, m = 9 → 11 | +2.82 [−7.14, +13.56] [−8.11, +14.06] | +2.00 [−3.30, +7.78] [−3.19, +7.84] |
| NI `goal_pass`, tailored m = 9 / m = 11 | −4.21 [−8.83, +1.29] [−9.43, +0.93] F / −0.94 [−9.53, +7.45] [−7.87, +5.97] F | — |
| NI `goal_pass`, untailored m = 9 / m = 11 | −0.31 [−5.54, +6.72] [−6.02, +5.69] H / −4.36 [−11.89, +3.21] [−10.68, +2.43] F | — |
| NI TGC, tailored m = 9 / m = 11 | −12.82 [−20.83, −4.35] [−21.14, −4.88] F / −8.45 [−21.54, +3.53] [−18.46, +1.52] F | — |
| NI TGC, untailored m = 9 / m = 11 | −8.55 [−15.79, −0.94] [−16.81, 0.00] F / −15.49 [−25.76, −5.80] [−24.64, −6.85] F | — |

The two splits differ only in those 11 and 17 episodes, in which the executor took over from a source planner that had stopped without finishing (HSTAR-02, HSTAR-14); under the flag, the handoff-only `goal_pass` rise looked larger than the all-episode one and handoff-only NI failed at m = 11. Under h* that NI holds only through those 17 (§4.6). Flag-based shares of the m = 6 → 11 rise were 0.5952 tailored and 0.7514 untailored (HO-09), and of the tailored m = 9 → 11 step 0.7552 (HO-08).

### D.3 The tailoring × depth interaction (POOL-03, DID-02)

The interaction does not resolve on either planner sample (cap-25 −2.53 pp, scenario [−7.66, +2.53]; cap-81 +2.10 pp, [−4.71, +9.01]; DID-02) nor pooled to 171 pairs: `(m11 − m9)_tailored − (m11 − m9)_untailored` is +2.8064 pp, scenario [−2.5661, +8.9649], task [−2.0544, +7.9491], and over m = 6 → 11 it is +0.6924 pp [−4.3971, +5.9164] (POOL-03). It is unmeasured at this power, which is not evidence that it is absent.

### D.4 The cap-25 depth curve, the untailored span and the source swap

On the cap-25 source, the untailored receiver gains +10.21 pp `goal_pass` from m = 6 to m = 9 (scenario [+2.60, +18.20], task [+3.80, +16.81]) and +16.67 pp on TGC ([+5.26, +28.07]; [+7.02, +26.32]) (SHAPE-10). From m = 9 to m = 11 it gains +4.99 pp `goal_pass`, scenario [−0.23, +9.74], task [+0.26, +9.31]: the scenario interval includes zero, so the step is unresolved on the primary clustering; TGC gains +7.02 pp ([+0.88, +14.04]; [+0.88, +13.16]) (CHAN-ZS-04).

Replaying the independent cap-81 trajectories instead, the untailored span m = 6 → 11 is +7.31 pp `goal_pass` (scenario [+2.07, +12.80]) and +9.65 pp TGC ([+2.63, +16.67]) (C81-01). At m = 11 the cap-81 prefix differs from the cap-25 prefix by −4.13 pp (scenario [−8.84, +0.50], task [−9.74, +1.44]): not distinguishable at n = 114, although the cap-81 planner scores 6.47 pp below the cap-25 one. Paired on the same trajectories, the untailored m = 11 arm is +2.95 pp against the cap-81 planner alone ([−1.91, +8.69]) and the tailored +4.75 pp ([−1.16, +11.81]) (ROB-21); under the mismatched pairing the untailored arm had appeared significantly above it (+7.08 pp, [+1.82, +12.78]), and that statement is withdrawn (CEIL-05).

Where the cap-25 rise is earned: on the untailored receiver 83.8 % of the m = 6 → 9 rise is earned on handoff episodes (scenario [55.7, 121.2]; ROB-14); on the tailored receiver the corresponding share is 36.0 % (MECH-07), with scenario interval [−254.2, +76.9] %, since 1.97 % of resamples have a non-positive total rise (MECH-11), and its handoff-subset gain (+3.08 pp, [−5.38, +11.69]) does not resolve (ROB-13). A share without a usable interval is not read as a receiver difference. On this source the replayed prefix ends 56 of 114 episodes at m = 11, exactly the episodes in which the executor never acted (SHAPE-06; HSTAR-17). Over m = 2 → 11 on the same source the tailored receiver earned only 16.7 % of its +12.42 pp rise on handoff episodes ([−7.1, +38.3]; ROB-13). These cap-25 decompositions split on the `handoff_occurred` flag, which on this source counts as silenced 1 episode at m = 9 and 4 at m = 11 in which the executor took control; they were not recomputed with h* (HSTAR-17).

The chord re-run (§4.4) places tailored m = 9 at cost fraction f = 0.2984 and m = 11 at f = 0.3819; their `goal_pass` residuals are +3.02 pp (scenario [−1.48, +7.21], task [−1.28, +7.26]) and +7.56 pp ([+2.96, +12.35]; [+3.30, +11.98]) (CHORD-01). The untailored m = 11 residual is +5.76 pp ([+2.15, +9.44]; [+2.17, +9.55]), measured against the tailored floor, so it mixes in the receiver difference (CHORD-02).

Chord residuals on TGC against the cap-81 planner alone (§4.4): tailored m = 9 +6.17 pp ([−2.08, +13.63]; [−1.46, +13.99]) and tailored m = 11 +13.48 pp ([+5.17, +22.20]; [+5.84, +21.45]) (CHORD-01).

Live takeover against oracle prefix replay (§3.1) is not distinguishable at n = 114 (CHAN-C1-03): takeover minus `prefix_m9` is +1.55 pp (scenario [−3.46, +7.04], task [−4.41, +8.01]) and minus `prefix_m11` −0.91 pp ([−6.74, +5.94]; [−6.90, +5.16]) (CHAN-C1-03).

### D.5 Narration detail (NARR-01..05, DID-01)

**The information reading of §3.4.** At m = 9 the planner's actions given as text also lift the untailored receiver far above the one-plan floor (NARR-02), while their observations add nothing detectable (NARR-05); both are detailed below. J10 tests the reading with CF1 (neutral minus correction advice, decision-bearing) and the unadjusted secondaries CF2 and CF3 (Amendment 1 §C).

Table D3: Executed minus narrated at m = 9 (n = 114 paired; NARR-01).

| Receiver, metric | Executed | Narrated | Difference, pp | Scenario 95% CI | Task 95% CI |
|---|---|---|---|---|---|
| tailored, `goal_pass` | 0.7852 | 0.7667 | +1.84 | [−2.67, +6.76] | [−3.70, +7.75] |
| tailored, TGC | 0.5614 | 0.5263 | +3.51 | [−5.26, +11.40] | [−4.39, +11.40] |
| untailored, `goal_pass` | 0.7845 | 0.7676 | +1.69 | [−4.16, +7.11] | [−3.70, +7.38] |
| untailored, TGC | 0.5526 | 0.4912 | +6.14 | [−2.63, +14.91] | [−1.75, +14.91] |

Table D4: Narrated minus executed `goal_pass` by receiver and depth, scenario 95 % CI (NARR-03, NARR-04).

| m | Untailored | Tailored |
|---|---|---|
| 6 | −6.96 [−13.67, +0.63] | −2.51 [−8.68, +3.41] |
| 9 | −1.69 [−7.10, +4.16] | −1.84 [−6.76, +2.68] |
| 11 | −6.58 [−9.98, −3.64] | −0.49 [−4.10, +3.21] |

The untailored m = 6 gap resolves on the task clustering ([−13.96, −0.09]) but not on the scenario clustering (NARR-03). On TGC, untailored narrated minus executed is −11.40 pp at m = 11 ([−22.81, −2.63]; [−20.18, −3.51]) and −13.16 pp at m = 6 ([−21.05, −5.26] on both clusterings), and the untailored narrated curve is flat past m = 9 (+0.10 pp, [−4.75, +5.14]) (NARR-03). The TGC difference-in-differences at m = 11 is +12.28 pp ([+0.88, +26.32]; [+2.63, +22.81]) and does not pass the exact test (p = 0.0996; ROB-08). Tailored narration is non-inferior to execution at m = 11 on both clusterings (`goal_pass` lower bounds −4.10 scenario, −4.42 task), at m = 9 only on the scenario clustering (−6.76; task −7.75), and not at m = 6 (−8.68); untailored narration fails NI at every depth (NARR-04, NARR-06). The tailored narrated curve rises +6.82 pp from m = 6 to 9 ([+0.63, +12.61]; task [+1.94, +11.77]) and +3.81 pp to m = 11, where the scenario interval [+0.79, +6.97] excludes zero and the task interval [−0.40, +8.20] does not, and tailored narration at m = 11 beats tailored execution at m = 6 by +8.12 pp ([+3.18, +13.67]) (NARR-04, NARR-06).

Table D5: Difference-in-differences, `goal_pass`, (narrated − executed)_tailored − (narrated − executed)_untailored, per episode (DID-01).

| m | DiD, pp | Scenario CI | Task CI |
|---|---|---|---|
| 6 | +4.45 | [−6.71, +14.25] | [−5.07, +13.98] |
| 9 | −0.16 | [−8.36, +7.11] | [−8.51, +8.04] |
| 11 | +6.09 | [+1.56, +11.00] | [+0.63, +11.85] |

Against the one-plan floor at m = 9, untailored narration adds +47.92 pp `goal_pass` (scenario [+38.67, +56.27], task [+39.78, +55.79]) and +43.86 pp TGC ([+30.70, +56.14]; [+32.46, +55.26]); tailored narration adds +13.16 pp TGC (scenario [+5.26, +21.93]) and +4.86 pp `goal_pass` (scenario [−0.56, +10.61], task [−0.56, +10.44]), the last including zero (NARR-02).

Adding the planner's observations to the narration at m = 9 (NARR-05): plain minus with-observations `goal_pass` is −1.64 pp [−6.46, +2.97] untailored and +2.67 pp [−1.62, +7.49] tailored, and all eight intervals over both receivers and metrics include zero, with opposite-signed point estimates. Observations add nothing detectable at n = 114.

### D.6 Three receivers and the replication of their ordering (HF-02, C81-02)

Table D6: `goal_pass` by receiver and depth on identical cap-25 prefixes (n = 114; HF-02).

| Receiver | m = 6 | m = 9 | m = 11 |
|---|---|---|---|
| untailored | 0.6825 | 0.7845 | 0.8345 |
| tailored (`sft_b_plus`) | 0.7237 | 0.7852 | 0.8098 |
| suffix-trained (`sft_b_plus_handoff`) | 0.7480 | 0.7840 | 0.8033 |

No within-depth receiver gap resolves; at m = 6 untailored minus tailored is −4.12 pp [−10.41, +1.64] and at m = 11 +2.46 pp [−1.48, +6.43]. The registered hypothesis C3, that suffix training extends the upper end, is answered in the negative (HF-02). The suffix-trained arms are not pure replay: hosted luna answered executor asks in 7, 3 and 4 of their episodes at m = 6, 9, 11, which bounds the lift on each arm mean at 2.15, 0.88 and 0.85 pp (PROV-02). On the independent cap-81 sample the untailored-minus-tailored gap runs −2.76, +0.31 and −1.80 pp at m = 6, 9, 11 rather than −4.12, −0.06 and +2.46, all six intervals including zero (C81-02). These receiver gaps alone neither show nor rule out that depth substitutes for tailoring. The plan-against-actions difference-in-differences of §7, in which tailoring is worth +42.97 pp given a plan and nothing detectable given executed planner actions, is consistent with that substitution, and like §7's reading it is exploratory and descriptive (PLANTAX-04, PLANTAX-05).

### D.7 A second executor family (QWEN-02..07)

Replaying the same trajectories into zero-shot `Qwen/Qwen3-8B`, `goal_pass` is 0.4491, 0.7017 and 0.7306 at m = 6, 9, 11 (QWEN-04). From m = 6 to m = 11 the rise is +28.15 pp `goal_pass` (scenario [+19.63, +38.47], task [+20.96, +35.72]) and +34.21 pp TGC ([+24.56, +44.74]; [+24.56, +43.86]); the m = 9 → 11 step resolves on TGC (+11.40 pp, [+3.51, +19.30]) and not on `goal_pass` (+2.90 pp, [−1.61, +7.03]; task [−2.80, +8.13]) (QWEN-05). Depth replicates within prefix arms.

Neither Qwen floor may be used as a denominator. The zero-shot floor arms score 0.2481 `goal_pass` with 0 of 114 tasks completed (QWEN-02, QWEN-03); the no-op arm shows that `goal_pass` awards partial credit without any task completed (NOOP-01), which is what that floor also shows, although the two floors are different numbers and we do not assert the mechanism behind either. The tailored Qwen one-plan floor scores 0.2583 and ends 105 of 114 episodes on the step limit (QWEN-06). The adapter is applied, and a train/serve template mismatch is real but not the cause: with the template corrected the floor scores 0.2484 (QWEN-07). What survives is a thin, family-dependent training signal: the terminal action is 165 of 6,767 supervised targets (2.44 %); Granite emits it in 64 of 2,130 executor actions (3.00 %), Qwen in 0 of 4,385, and 3 of 4,431 with the corrected template, rising to 13 in 891 (1.46 %) with a replayed prefix in context (QWEN-06, QWEN-07). Qwen does not acquire the terminal action by fine-tuning at this data scale, but emits it once a prefix demonstrates it in context. The tailoring recipe does not transfer to this family; depth does.

### D.8 The planner-alone reference and external context (CEIL-07, CEIL-06)

Raising the planner's call cap from 25 to 81 lowered its `goal_pass` from 0.8284 to 0.7637 (−6.47 pp; TGC −11.4 pp, [−21.05, −1.75] on both clusterings), with more calls per episode (17.35 against 14.43) and more episodes reaching the step limit (CEIL-07). Across five planner samples the two cap families do not overlap: the lowest cap-25 seed exceeds the highest cap-81 seed by 4.34 pp (CEIL-06). Two samples and three are a spread across what we have, not a variance estimate. The reference's TGC here is 0.5702 at cap 81 and 0.6842 at cap 25 (114 episodes each, seeds 1–2), against 85.1 % on `test_normal` for the same model in a leaderboard entry whose method learns context assets on train (CEIL-10; below). The high-effort planner of §4.7 makes fewer hosted calls, 0.7867× medium's ([0.69, 0.89]), and its dollar cost is not distinguishable from medium's (CEILHI-02). The high-effort run of §4.7 and the medium-effort run it is compared with also differ in per-step timeout, which never fired at medium effort (CEILHI-01).

AppWorld [@appworld_trivedi_2024], τ-bench [@tau_bench_yao_2025] and BFCL [@bfcl_patil_2025] evaluate tool-using agents, and the strongest AppWorld results train or adapt one agent on the test splits [@loop_2025; @canopy_2026; @ace_2026]. Published AppWorld results are on the test splits, with scaffolds or training that this harness omits [@appworld_trivedi_2024; @loop_2025; @canopy_2026; @ace_2026; @prost_bijoy_2025; @three_roles_2026; @appworld_ul_2026], and the public leaderboard's one `gpt-5.6-luna` entry, whose method learns context assets on train and freezes them for closed-book evaluation, reports 85.1 % TGC and 73.2 % SGC on `test_normal` (73.4 % and 52.5 % on `test_challenge`), retrieved 2026-09-24 [@gpt_5_6_luna_2026] (CEIL-10). Our dev scores are paired contrasts in a minimal harness on the dev split and are not comparable with any of them. The pinned release ships 57 dev tasks.

### D.9 Cost frontier (COST-01..03, ROB-18, DEC-05, LAT-01)

```
Table D7: Cost and quality, AppWorld dev split, n = 114 (COST-01; TGC from the same arms; channel arms charged their replayed plan, ATTRIB-01; plan_only priced on the plan it replays, COSTFIX-01).
---------------------------------------------------------------------------------------------
Arm                                Goal Pass    TGC     Non-Cached Tokens   USD / Ep.   Calls / Ep.
---------------------------------------------------------------------------------------------
executor_alone (granite 8B)          0.5289    0.1316                   0   $0.000000          0.00
plan_only (sft_plan iaware)          0.7181    0.3947              23,906   $0.003921          1.00
advise_fixed_k_10 (8-line ctx)       0.6964    0.4123              67,729   $0.008308          2.42
advise_fixed_k_10_fullctx            0.7339    0.4386              73,725   $0.009416          2.46
takeover_fixed_k_10                  0.8007    0.5175              65,369   $0.008742          2.32
advise_fixed_k_3 (8-line ctx)        0.7012    0.4561             228,405   $0.016125          6.82
prefix_m6                            0.7237    0.4298             221,043   $0.016268          6.98
prefix_m9                            0.7852    0.5614             357,448   $0.022740          9.77
prefix_m11                           0.8098    0.6053             443,361   $0.026475         11.25
planner alone, cap 25                0.8284    0.6842             684,453   $0.035479         14.43
planner alone, cap 81                0.7637    0.5702           1,160,215   $0.048208         17.35
---------------------------------------------------------------------------------------------
```

On the matched-trigger pair, takeover is cheaper than correction-prompt advice as point estimates on all three axes, but paired intervals resolve only the dollar difference, and only on the scenario clustering: −8,356 non-cached tokens [−17,744, +617], −$0.000674 [−0.001361, −0.000024] (task [−0.001539, +0.000161]) and −0.149 hosted calls [−0.368, +0.070] (ROB-18). At 171 pairs takeover is still the cheapest of the four channel arms in non-cached tokens (65.4k against 76.9k for correction-prompt advice) and dollars ($0.00880 against $0.00980), point estimates only (DEC-05, ATTRIB-07). The replayed plan is the same source plan in both arms of every matched pair, so it cancels in the ROB-18 differences above (ATTRIB-05). Median wall clock per episode is 41.161 s for takeover, 40.307 s for correction-prompt advice, 45.61 s for neutral advice, 42.301 s for show and 230.402 s for advice at every step; no per-call planner timing was recorded and node load was not controlled, so these are descriptive (LAT-01). Against the cap-25 planner alone, the m = 11 prefix costs 0.746× its dollars ([0.661, 0.831]) and 0.648× its non-cached tokens ([0.550, 0.756]) (ROB-19), and makes 0.78× its hosted calls, 3.18 fewer per episode ([−4.54, −1.94]; ROB-19, ROB-27).

Ganz-comparable metrics at every depth (§4.5): tailored QRec is 0.6491, 0.9607 and 2.0420 at m = 6, 9, 11 (GANZ-01), with scenario interval [−14.29, +17.77] and task interval [−8.59, +14.74] at m = 11 (GANZ-01, GANZ-02); hosted-call savings retained against the cap-81 planner are 0.6325, 0.4528 and 0.3605, and dollar savings retained 0.7202, 0.5658 and 0.4780 (GANZ-03, COSTFIX-01; the cap-25 comparison is in the paragraph above), at m = 11 with intervals [0.23, 0.47] and [0.27, 0.43] (calls) and [0.28, 0.62] and [0.35, 0.58] (dollars), scenario then task. Against the pooled cap-81 planner alone (171 pairs) the m = 11 arms use 0.6550 of its hosted calls (scenario [0.56, 0.76], task [0.59, 0.73]; COST-04). Against the pooled cap-81 planner alone the m = 11 arms retain 0.4292 of its dollar cost as saving ([0.26, 0.57]; [0.32, 0.52]); at m = 6 the call share and dollar saving are 0.4048 and 0.6508 (COST-04).

### D.10 Step-limit counts, the step-limit split, and the termination census (LIM-01, LIM-03..08, TERM-01..04)

**Pooled cap-81 prefix family (§4.1).** Step-limit episodes, seeds 1–2 (of 114): tailored 9, 8 and 8 and untailored 18, 7 and 9 at m = 6, 9, 11, and 18 for the planner alone at cap 81 (LIM-01); seed 3 (of 57): tailored 11, 7 and 3, untailored 10, 3 and 1 (POOL-01), and 9 for the planner alone (LIM-07).

**The step-limit split.**

For T − N the 16 pairs with a limit contribute +3.55 pp ([+1.00, +7.03]; [+1.34, +6.19]), and over the other 155 takeover is −1.26 pp against neutral advice ([−6.04, +3.61]; [−5.04, +2.59]), unresolved and not evidence that takeover is worse when no one hits the limit (LIM-05). For N − A and S − A neither part resolves (LIM-03, LIM-04). Scoring limit episodes as 0 makes N − A +5.72 pp ([+1.26, +10.74]; [+0.87, +10.70]) and leaves S − A (+4.38) and T − N (+4.05 pp) unresolved (LIM-06).

**Termination census (TERM-01..04).** Following Fan et al.'s categories [@harness_design_fan_2026], an episode *stops before acting* when it ends cleanly with no executed code action by the acting model; prefix arms count only actions after the handoff. The no-op arm validates the classifier: all 114 of its episodes fall in that category (TERM-01). No executor arm without a prefix stops before acting: 0 of 114 for the base and tailored executors alone and with one plan, and 0 in the advice, takeover, show and Qwen arms (TERM-02). Step-limit shares, scenario intervals: base executor alone 37 of 114, 0.3246 [0.2105, 0.4561]; tailored executor alone 31 of 114, 0.2719 [0.1667, 0.3860]; base with a plan 40 of 114, 0.3509 [0.2456, 0.4649]; tailored with a plan 18 of 114, 0.1579 [0.0965, 0.2193]; zero-shot Qwen3-8B alone 114 of 114 (TERM-02). After a cap-81 prefix hands off, the executor stops before acting in at most 11 of 171 episodes on either receiver (TERM-03). The planner acting alone never stops before acting either, and high effort cuts its step-limit share from 27 of 171 at medium effort (seeds 1–3) to 4 of 114 (TERM-04). Weak coding agents in Fan et al. fail the other way: without planning, 68.6 % of the weakest model's runs end without an edit, 27.8 % with it [@harness_design_fan_2026]. Ours never stop before acting without a prefix, with or without a plan, advice or takeover; a weak executor runs to the step limit instead, the base executor alone in 37 of 114 episodes (TERM-01, TERM-02; §3.3).

### D.11 Our arms in the literature's slots (Table D8)

Table D8 places our arms in the slots of §7 without contrasting them: campaigns differ in date, and the tailored executor-alone value comes from an older adapter build (ADV-FC-01). The base executor alone scores below the no-op. The zero-shot Qwen floor gives no third point for §7's plan-against-actions difference-in-differences: its plan gain is exactly zero (PLANTAX-06).

Table D8: Our arms in the literature's slots; `goal_pass` (TGC), 114 episodes per arm.

| Slot | Our arm | Base executor | Tailored executor | Source |
|---|---|---|---|---|
| Nothing | no-op, `COMPLETE` at step 1 | 0.3569 (0) | same arm | NOOP-01 |
| Executor alone | `executor_alone` | 0.1903 (0.0175) | 0.5289 (0.1316) | CHAN-ZS-01, COST-01 |
| One external plan | `prompt_only` / `sft_plan` | 0.2885 (0.0526) | 0.7181 (0.3947) | CHAN-ZS-01, ADV-FC-01 |
| Plan and periodic feedback | correction advice, k = 10 / every step | — | 0.7339 (0.4386) / 0.6630 (0.4474) | ADV-FC-01, CHAN-PRICE-01 |
| The planner's actions, executed | prefix m = 9 / takeover, k = 10 | 0.7845 (0.5526) / — | 0.7852 (0.5614) / 0.8007 (0.5175) | CHAN-ZS-01, COST-01, CHAN-C1-02 |
| The same actions as text | narrated prefix, m = 9 | 0.7676 (0.4912) | 0.7667 (0.5263) | NARR-01 |
| The planner alone | cap 25 / cap 81 | 0.8284 (0.6842) / 0.7637 (0.5702), no executor | same arm | CEIL-07 |
| The executor's own plan; a wrong-task plan | pending (§3.6) | — | — | — |

---

## Appendix E. Defect and process record

### E.1 Analysis defects found and repaired

- *Terminal guard (GUARD-01):* early prefix runs let the executor act after a replayed completion; a post-prefix terminal guard now ends such episodes.
- *Handoff indicator (HO-01, HSTAR-01, HSTAR-14):* the handoff-only analyses split episodes on the prefix arm's `handoff_occurred` flag, which is `effective_m < n_source_actions` and so reads "no handoff" whenever the source made no more than m executed actions, while the loop skips the executor only when the replayed prefix ends the episode; at m = 11 it counted as silenced 17 episodes whose source planner had stopped executing and run out of steps, and in which the executor took control. The indicator is now h*, read from each episode's own events, and the flag is reported as a sensitivity (Table D2b); the cap-25 source carries the same error in 1 episode at m = 9 and 4 at m = 11 (HSTAR-17).
- *Handoff flag path (MECH-09, GUARD-03):* the mechanism script read an invalid key; paths were aligned and zero-count populations made fatal.
- *Error-scan actor filter (MECH-04, MECH-05):* early audits filtered observations on executor identity and found no errors; repaired to scan observation text.
- *Adapter build mismatch (ADV-FC-02):* early advice contrasts were paired against an older adapter build.
- *Cost pricing (COST-01):* local executor tokens were at first priced as hosted tokens.
- *Segmented-fit tie-breaking (TIEBREAK-01):* exact float comparisons produced spurious breakpoints on straight lines.
- *Test collection:* for six days the configured test command aborted during collection, leaving the integration tests outside every reported pass count; repaired by renaming.

### E.2 A results table filled with invented values (QUAL-07)

A worker drafting the cost table invented three of its eleven TGC values, one a fill-down of the row above and one wrong by 10.52 pp, while reporting no outstanding work; the `goal_pass` column beside them was correct, so nothing looked wrong. An instruction to flag uncertain values cannot catch that, because a model that does not know it is guessing cannot comply with it. A set difference against the ledger can, and did; that is why the number audit of Appendix A.1 exists.

---

## Appendix F. Further related work

**Other handoff studies (§7).** Do Not Restart treats a stateful handoff as residual completion [@do_not_restart_2026], handed-over context reduces rediscovery in coding agents [@handoff_debt_2026], and a one-turn model switch shifts later outcomes [@perf_drift_switching_2026]; none compares the forms help takes.

**Trained planners (§7).** EAGLET trains a global planner with an executor-capability-gain reward and gains more with a Llama-3.1-8B executor than with GPT-5 [@eaglet_si_2026]; we hold the planner frozen and vary the channel and the receiver.

**Plan following (§7).** Liu et al. find that a standard plan improves resolution, periodic plan reminders reduce violations and a subpar plan hurts more than none, and call for fine-tuning models to follow plans [@plan_to_action_liu_2026]; our tailored receiver is such a fine-tune, and on it periodic correction advice is not distinguishable from the first plan alone (ADV-FC-01, QUAL-04).

**Plans and execution context (§3.4, §7).** COPE exchanges plans between small and large models in a cascade [@cope_lee_2025], and execution context missing from a planning state changes what frontier models produce [@substrate_aware_agrawal_2026]. A planning scaffold leaves per-constraint instruction-following reliability unchanged [@constraints_vasileva_2026], which fits §6's reading that a deeper prefix lowers error incidence without improving the executor's planning.

**Teaching by advice (§7).** In reinforcement learning the timing of a budgeted teacher's advice matters [@torrey_taylor_2013], and in human teaching telling outperforms showing for complex concepts [@sumers_show_or_tell_2023]; here the telling that helps carries code, which speaks to this receiver and these prompts only.

**Verbal feedback and self-correction (§7).** Verbal feedback critiques and revises [@self_refine_madaan_2023; @reflexion_shinn_2023; @critic_gou_2023], self-correction without external feedback is weak [@llms_cannot_self_correct_huang_2024; @self_correction_survey_kamoi_2024; @slm_need_strong_verifiers_2024], and simulated language feedback helps tool users [@mint_wang_2024]; COTA returns a comparator's preferred alternative as non-binding advice [@cota_jiang_2026].

**Routing and escalation (§7).** Cascades and routers choose which model acts, per query or within a trajectory [@frugalgpt_chen_2023; @hybrid_llm_ding_2024; @routellm_ong_2024; @learning_to_defer_mozannar_2020; @policy_stepwise_routing_2026; @agentic_routing_2026; @mtrouter_2026; @swe_router_2026; @r2v_agent_2026]; TACIT-Switch learns when to hand off [@tacit_switch_2026], SwiftSage escalates by rule [@swiftsage_lin_2023], speculative methods let a small model draft what a large one verifies [@speculative_decoding_leviathan_2023; @speculative_sampling_chen_2023; @bild_kim_2023; @dsp_guan_2025; @isp_2024], and in LATM a strong model writes tools a weak one applies [@latm_cai_2024].

**Demonstrations, prefixes and distillation (§7).** ReAct and Synapse steer agents with in-context trajectories [@react_yao_2023; @synapse_zheng_2024]; our narrated control is the task-specific case whose exemplar is the planner's own opening. DAgger [@dagger_ross_bagnell_2011], reverse curricula [@backplay_resnick_2018; @salimans_chen_2018; @rfcl_2024], agent tuning [@fireact_chen_2023; @agentinstruct_zeng_2023; @agentflan_chen_2024; @agent_distillation_2025] and ReOPD, Guided-OPD and Prefix-GRPO [@reopd_liao_2026; @guided_opd_2026; @prefix_grpo_wang_2026] use expert states, trajectories or prefixes in training; here the prefix is present at deployment. Models err more when their context holds their own earlier errors [@sinha_illusion_2026], an account consistent with, but not tested by, our error-incidence correlate (§6). On AppWorld, with a planner–executor–summarizer agent and Qwen3-8B among its models, Feng et al. find that skills induced from completed tasks transfer to later tasks better as text notes than as code functions [@skill_transfer_feng_2026]. Their code is a function reused on another task, ours is advice for the current episode (DEC-06), so the results do not conflict.
