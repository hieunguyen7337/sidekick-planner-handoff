---
title: "Concrete Code, Executed or Shown: How a Hosted Planner's Help Reaches an 8B Local Executor on AppWorld (Exploratory, Dev Split)"
date: "2026-09-24"
author: "Sidekick Research Group"
abstract: |
  We study how a hosted planner (`gpt-5.6-luna`) should deliver help to a local 8B executor (IBM Granite 4.2) on AppWorld, with paired, cluster-bootstrapped contrasts on the 57-task dev split only; the held-out tests that will judge each claim (J10, J11, J12) have not run. Our headline is exploratory: the executor benefits from the planner's concrete code, executed or shown, while terse correction prose leaves it stuck. At a matched trigger, executing the planner's action beats advice written under a correction prompt by +6.13 pp `goal_pass` over 171 pairs (scenario 95% CI [+0.75, +12.71]); the contrast was registered and resolves at 114 pairs, but at 171 an exact 19-cluster randomization test gives p = 0.063, and neither TGC nor scenario goal completion resolves. Exploratory analyses find 20 of 171 correction-advice episodes ending at the 40-step limit against 2 of 171 for takeover, and neutral-prompt advice that is mostly fenced code (207 of 221 interventions, against 3 of 260) and recovers +3.73 pp of the gap ([−0.06, +8.24]); the registered decomposition is unresolved. The registered advice-at-every-step arm failed its cost prediction, so we report it only as higher-frequency correction advice: advice remains unpriced at the action channel's budget. In exploratory depth analyses, handing off after m replayed planner actions raises `goal_pass` from m = 6 to m = 11 by +8.39 pp (tailored executor) and +7.70 pp (untailored) over all episodes and by +12.03 and +13.93 pp over the 71 episodes that hand off, but at m = 11, 100 of 171 episodes never hand off, no breakpoint can be localized, the registered chord test failed, and the effect replicates a downshift-timing result Ganz et al. report. Against the planner acting alone in the same minimal harness, at a 7.00 pp margin taken from a held-out power analysis, the m = 11 prefix is non-inferior on `goal_pass` over all episodes but not over handoff episodes, and on TGC only for the tailored executor, which an exact test did not support in an earlier 114-pair comparison (p = 0.0264); this too is exploratory.
---

# Concrete Code, Executed or Shown: How a Hosted Planner's Help Reaches an 8B Local Executor on AppWorld

## 1. Introduction

Small open-weight models are cheap to run locally but compound errors when they act alone in software environments [@slm_agentic_belcak_2025; @where_agents_fail_2025; @long_horizon_mirage_2026; @sinha_illusion_2026]; hosted frontier models act better and cost more per call. Hybrid systems differ in who acts and in what crosses between the two models. Routers and cascades choose which model acts for a query, a turn or a step; planner–executor systems pass a plan; critic systems pass feedback; and handoff studies let the stronger model act first and then pass its trajectory to a cheaper one [@handoff_tax_ganz_2026; @reach_or_solve_2026] (§7). What has not been compared for a small local executor is the *form* of the stronger model's help with the trigger and the context held fixed: an executed action, the same action shown as text, advice that may contain code, and terse correction prose.

Privacy is often given as a reason to keep the executor local. These designs do not deliver it: in every arm the hosted planner sees the task; in the prefix arms it has produced the first m actions and their observations; and in the advice and takeover arms it reads the full transcript at each trigger.

We ask two questions on AppWorld [@appworld_trivedi_2024], with `gpt-5.6-luna` as the planner and IBM Granite 4.2 8B [@granite_4_2_ibm_2026] as the executor. **Channel:** at a matched trigger, does the planner's help land better as an executed action, as the same action shown, or as advice? **Depth:** if the planner acts for the first m steps and then hands off, how does quality change with m, and on which episodes?

All evidence here is paired and comes from the dev split; nothing has touched held-out data. Every number traces to a claims ledger (`docs/claims_ledger.md`) that records the report, the JSON key, and whether the contrast was registered before its data existed. The claims, each labelled:

- **Concrete code, executed or shown (exploratory; DEC-06, LIM-02).** Neutral-prompt advice carries fenced code in 207 of 221 interventions and correction-prompt advice in 3 of 260; the pairs where either arm hit the step limit carry +4.07 pp of the +6.13 pp gap. Held-out test: J10's content family CF1 and step-limit reporting (Amendment 1 §C, §D).
- **Actions beat correction-prompt advice at a matched trigger (registered, C1; CHAN-C1-02, DEC-02).** The gap is +6.69 pp at 114 pairs, resolved on both clusterings, and +6.13 pp at 171, where the bootstrap resolves it and an exact randomization test gives p = 0.063. On TGC the 171-pair gap does not resolve (METRIC-01). Held-out tests: J10 P6; with an open-weight planner, J11 L1.
- **The decomposition is unresolved (registered, B2; DEC-01).** Neither showing the action without executing it nor neutral advice separates from correction-prompt advice or takeover.
- **Advice at every step is higher-frequency correction advice (registered H2; CHAN-PRICE-01, CHAN-PRICE-02).** Its cost prediction failed, so under the registration's rule we report it only as such, 14.68 pp below the m = 11 prefix, and state that advice remains unpriced at the action channel's budget. Held-out test: J10 P1, under Amendment 1 §E.
- **Depth, over all episodes and over handoff episodes (exploratory; HO-01, HO-04, HO-06).** The m = 6 → 11 rise resolves in both populations, yet at m = 11, 100 of 171 episodes never hand off. This replicates and extends Ganz et al.'s downshift-timing finding. Held-out tests: J12 D1–D4; J10 P4 for the untailored m = 9 → 11 step.
- **Non-inferiority to the planner acting alone (exploratory; HO-NI-01, HO-NI-03).** It holds on `goal_pass` over all episodes and fails over handoff episodes at m = 11. Held-out test: J10 P3 with Amendment 1 §B1's handoff-only companion.
- **What a prefix conveys depends on depth and receiver.** At m = 9, narration and execution are not distinguishable at n = 114 (registered; NARR-01). The pattern at other depths and across receivers is exploratory (NARR-03, NARR-04, DID-01).
- **What did not hold (registered).** Learned selective escalation is a null on dev (ESC-01); the dev frontier's gate G1 (QUAL-06), its chord test C2 (UF-07) and the segmented threshold test S3 (F1-RESULT-01) failed.

**Held-out tests (none has run).** **J10** is A1 with Amendment 1 (`docs/prereg_j10_amendment_20260924.md`; A1 frozen at 142e947, Amendment 1 at 138c285): predictions P1–P6 on `test_normal`, the content family CF1, and handoff-only, chord and step-limit companions. **J11** (`docs/prereg_j11_lp2_test_20260924.md`, [[FREEZE: J11]]) tests L1–L5 with the open-weight LP-2 planner (`Qwen/Qwen3.8-27B-FP8`) on `test_normal`. **J12** (`docs/prereg_j12_depth_test_20260924.md`, [[FREEZE: J12]]) tests the m = 6 → 11 span on `test_normal`, over all episodes and over handoff episodes (D1–D4). Until they run, every number below is a dev estimate.

**What is new, and what is not.** The depth effect is not new: Ganz et al. already report that a later downshift improves quality and retains less of the saving [@handoff_tax_ganz_2026]. What this paper adds is (i) a matched-trigger decomposition of act, show, neutral advice and correction advice, with the content of every intervention measured; (ii) a narrated control that keeps a prefix's information and removes its execution; (iii) a handoff-only companion beside every depth number, and a chord test; and (iv) registered nulls for learned escalation gates, all with a local 8B receiver, tailored and untailored.

---

## 2. Setup

### 2.1 Environment, split and harness

AppWorld has nine everyday apps reached through APIs; the agent writes Python that reads and changes their state [@appworld_trivedi_2024]. We use a minimal harness that isolates the channel from scaffold effects: each action is a code block executed against the environment, its output or error is appended to the transcript, and an episode ends on `COMPLETE` or at the 40-step limit. Every experiment uses the dev split of the pinned release, which ships 57 dev tasks in 19 scenarios, run at seeds 1–2 (114 paired episodes) or 1–3 (171). Arms are paired on `(task_id, seed)`.

### 2.2 Planner, executors, and the planner acting alone

- **Planner.** `gpt-5.6-luna` at `medium` reasoning effort, with frozen prompts. Ganz et al. use this model as the *low-cost* model of their GPT pair [@handoff_tax_ganz_2026]; it is our planner, not a strong model in absolute terms.
- **Executors.** `ibm-granite/granite-4.2-8b`, either untailored (base weights) or tailored (the LoRA adapter `sft_b_plus_iaware_granite8b`, trained on 497 rows from the same planner's solved train-split trajectories; Appendix A.3). A handoff-suffix adapter and a second family, `Qwen/Qwen3-8B`, are in Appendix D.
- **The planner acting alone in the same harness.** This is our reference, capped at 25 or 81 planner calls; it is not a ceiling. Raising the cap from 25 to 81 *lowered* `goal_pass` by 6.47 pp (scenario [−11.68, −1.37], task [−12.48, −0.46]; CEIL-07). Its TGC in this harness is 0.5702 at cap 81 and 0.6842 at cap 25, against the AppWorld leaderboard's TGC on the test split for the same model under a full scaffold, [[NEEDS LEDGER: leaderboard TGC for `gpt-5.6-luna` with the Capybara scaffold on `test_normal` (v1 L847)]]. The reference is therefore harness-limited, and every comparison with it names its cap.

### 2.3 Channels

Floors: the executor alone, and one plan (`sft_plan`: a planner plan at step 0, then the executor alone). At a trigger of k = 10 steps, with the full transcript, the planner either writes **advice**, under the correction prompt "The executor needs a correction. Reply with concise correction text only." (**A**; `src/sidekick/agents/planner.py:118`) or the neutral prompt "Advise the executor on how to proceed with this task: say what it should do next. You may include code." (**N**; `:139-140`), which differ in their first line only; or is asked for an action that the executor receives as text and never executes (**show, S**); or acts, its action executed before control returns (**takeover, T**, `takeover_fixed_k_10`). A **replayed prefix** (`prefix_m`) replays the first m actions of a recorded planner trajectory before the executor continues; if that trajectory already finished the task, a terminal guard ends the episode (GUARD-01). A **narrated prefix** gives the same m actions as text to an executor starting at step 0 in a fresh environment (§5). Every trigger is fixed: learned gates that were to call the planner selectively are a registered null on dev, and the executor's own ask probability never crossed its thresholds (ESC-01).

### 2.4 Metrics, and the floor of `goal_pass`

- **`goal_pass`** (`goal_pass_rate`) is the fraction of a task's required assertions that pass. It has a floor. An executor that does nothing, answering `COMPLETE` at step 1, scores 0.3569 mean `goal_pass` on dev (35.69 %, scenario [30.03, 41.29]), with every one of its 114 episodes above zero, and 0 on TGC and SGC (NOOP-01). The floor shifts arm means but not paired differences between two arms on the same tasks; it matters for ratio metrics (§4.5) and for how large a margin in pp is relative to the usable range.
- **TGC** (task goal completion) is 1 only when every requirement of the task passes. We give it beside every `goal_pass` headline.
- **SGC** (scenario goal completion) scores a (scenario, seed) unit 1 only when all its tasks pass; it has no task clustering (METRIC-02).
- **Step limit.** An episode that reaches 40 steps is scored (`error_type == "limit"`); only crashes are dropped. Each arm's limit rate is printed beside its quality numbers (LIM-01).

### 2.5 Statistics

Contrasts are paired and bootstrapped over clusters, 10,000 percentile draws at seed 20260924 unless noted [@koehn_bootstrap_2004; @clustered_eval_2026]. Scenario clustering (19 clusters) is primary and task clustering (57) is reported beside it, scenario first. Some ledger rows carry the scenario interval only (Appendix A.4). Because 19 clusters are few, headline contrasts also get an exact sign-flip randomization test over all 2^19 scenario sign patterns (ROB-01). A decision-relevant bound within 1 pp of its threshold is re-drawn at seven bootstrap seeds and called unresolved if its verdict changes (POOL-04). An interval that includes zero is reported as "not distinguishable at n = …", never as equivalence.

**The non-inferiority margin, and where it comes from.** δ = 7.00 pp. It is a margin of convenience, not a substantive one: the original registration derived it from a power analysis as the smallest TGC margin its held-out test could resolve [[NEEDS LEDGER: `docs/prereg_v1.md:88-95` power figures — power level and held-out task count]], and the J9 freeze moved it to `goal_pass`. Non-inferiority (NI) holds when the scenario lower bound of arm minus reference is at least −7.00 pp.

### 2.6 What was registered, and what happened

Table 1 lists every registered item behind this paper, its outcome, and whether its data had been seen when it was registered. The campaign index behind the paper's reports lists 47 dev campaigns forming 39 distinct dev arms. When that census was taken the ledger held 32 registered rows, 86 exploratory rows and 31 of other status. Source: CENSUS-01, Appendix C.2. A Benjamini–Yekutieli adjustment over the 28 dev `goal_pass` contrasts of the two re-analysis reports keeps 9, and the 171-pair channel gap is not among them (FDR-01; Appendix C.1).

Table 1: Registration outcomes. "Seen?" is whether the data the item is judged on existed when it was written.

| Item | Document | Seen? | Outcome |
|---|---|---|---|
| v1 H2: selective escalation, conjunctive primary | `docs/prereg_v1.md` §1.1; J9 freeze | Pilot figures yes; escalating arms no | Null on dev: no gate discriminates needed help, and the self-gate never fires (ESC-01). Demoted to a dev-only negative result (A1 §2) |
| v1 H1: TGC NI of the escalating system to the planner alone | `docs/prereg_v1.md` §1.1 | As above | Not tested: the system it names never escalated (ESC-01); A1 replaced the J10 arm list |
| hj12 gate G1 | `docs/prereg_hj12_dev_20260922.md` §5 | No | Failed on both clauses; the flat-curve branch is in force (prereg lines 295-310; QUAL-06) |
| hj12 C1: action vs advice at a matched trigger, made context-matched by the amendment of 2026-09-21 | same, Claim C1 and amendment | Takeover and full-context advice arms no | Resolves at 114 pairs on both clusterings (CHAN-C1-02); extended to 171 pairs, exact test p = 0.063 (DEC-02) |
| hj12 C2: chord and NI of the prefix frontier | same, lines 38-40 | No | Failed: m = 9 chord residual +3.96 pp [−0.49, +8.88] (UF-07); the NI limb fails at every depth it names [[NEEDS LEDGER: C2 NI contrasts at m ∈ {2, 4, 6, 9}]] |
| hj12 C3: suffix-trained adapter extends the upper end | same, Claim C3 | No | Negative (HF-02) |
| Depths m ∈ {7, 8, 10, 11} | hj12 amendment of 2026-09-22 | Yes: chosen after the first grid | Exploratory by construction (QUAL-06); every m = 11 result is post hoc |
| hj13 S1–S3, segmented threshold test | `docs/prereg_hj13_shape_20260923.md` §3 | Yes: written after the curve was seen | S1 and S2 hold and S3 fails in 8/8 configurations; no threshold is claimed (F1-RESULT-01) |
| hj13 replicate floor | same, §3 | Rise yes; replicates no | Withdrawal condition does not fire (NOISE-03). It would under NOISE-01's substitute floor |
| H2 P1–P4: advice at every step | `docs/prereg_h2_advice_at_price_20260923.md` §4–§5 | No | P1–P3 hold; P4 fails (1,414,410 tokens per episode against 300k–700k), so §5's reporting rule applies (CHAN-PRICE-01, CHAN-PRICE-02) |
| B2 decomposition D1–D4 | `docs/prereg_c1_decomposition_20260923.md` | C1 gap yes; B2 arms no | Unresolved: no decision rule fires (DEC-01) |
| J10: A1 + Amendment 1 | `docs/prereg_j10_amendment_20260924.md`, 142e947 / 138c285 | Dev yes; `test_normal` no | Pending: not run |
| J11: LP-2 planner, L1–L5 | `docs/prereg_j11_lp2_test_20260924.md`, [[FREEZE: J11]] | Provisional LP-2 dev read yes; `test_normal` no | Pending: not run |
| J12: depth span, D1–D4 | `docs/prereg_j12_depth_test_20260924.md`, [[FREEZE: J12]] | Dev span yes; `test_normal` no | Pending: not run |

---

## 3. How the planner's help reaches the executor

### 3.1 The matched-trigger contrast

Takeover and correction-prompt advice share the trigger (k = 10), the cached initial plan, the executor and its adapter, and the full transcript given to the planner; their configs differ in one field (CHAN-C1-00). At 114 pairs the registered contrast C1 gives takeover 0.8007 against advice 0.7339 `goal_pass` (TGC 0.5175 against 0.4386), a paired difference of **+6.69 pp** (scenario [+1.29, +13.48], task [+1.47, +12.35]; CHAN-C1-02). The `goal_pass` result passes an exact 19-scenario sign-flip test only narrowly (p = 0.0469). Its TGC companion, +7.89 pp (scenario [+1.75, +15.79]), does not pass it (p = 0.0781), and on SGC advice minus takeover is −7.89 pp [−21.05, +2.63] (ROB-02, ROB-11). At 114 pairs correction-prompt advice ends at the step limit in 13 episodes (ADV-FC-01), and takeover in [[NEEDS LEDGER: `takeover_k10` limit count, seeds 1–2]].

A third seed extends C1 to 171 pairs; the added 57 take their plan packets from the cap-81 planner campaign, so this is an extension, not a replication (DEC-02). The gap is **+6.13 pp** (scenario [+0.75, +12.71], task [+0.97, +11.73]), significant under the percentile bootstrap and stable across seven bootstrap seeds, and an exact cluster randomization test gives p = 0.063 (DEC-02). On the stricter metrics it does not resolve: TGC +5.26 pp (scenario [−0.58, +12.28], task [−2.34, +13.45]) and SGC +3.51 pp (scenario [−3.51, +10.53]) (METRIC-01, METRIC-02). Its bootstrap p of 0.0202 becomes 0.1587 under the BY adjustment (FDR-01).

Live takeover and oracle prefix replay, which needs a recorded trajectory, are not distinguishable at n = 114 (CHAN-C1-03; Appendix D.4).

### 3.2 Decomposing the gap (registered, B2)

Takeover differs from correction-prompt advice in its prompt, its content (an action, not prose) and its delivery (executed, not shown). B2 separates them with two more arms at the same trigger and context, S and N (§2.3). All four arms have 171 pairs over seeds 1–3 and no crashes (DEC-01).

Table 2: The four channel arms at 171 pairs. Means from DEC-01 and METRIC-02; step-limit episodes from LIM-01.

| Arm | `goal_pass` | TGC | SGC | Step-limit episodes |
|---|---|---|---|---|
| T, takeover | 0.7899 | 0.4971 | 0.3158 | 2 of 171 (0.0117) |
| A, correction-prompt advice | 0.7285 | 0.4444 | 0.2807 | 20 of 171 (0.1170) |
| S, action shown, not executed | 0.7516 | 0.4561 | 0.3158 | 11 of 171 (0.0643) |
| N, neutral advice | 0.7658 | 0.5029 | 0.2982 | 14 of 171 (0.0819) |

Table 3: The B2 contrasts, 171 pairs, in pp; each cell gives the point, the scenario interval, then the task interval. Holm over D1–D4 (DEC-01..04, METRIC-01, METRIC-02, LIM-03..05).

| Contrast | `goal_pass` | Holm p | TGC | SGC (scenario) |
|---|---|---|---|---|
| D0 = T − A | +6.13 [+0.75, +12.71] [+0.97, +11.73] | — | +5.26 [−0.58, +12.28] [−2.34, +13.45] | +3.51 [−3.51, +10.53] |
| D1 = T − S (execution) | +3.83 [−1.56, +10.81] [[NEEDS LEDGER: D1 task CI]] | 0.5976 | +4.09 [−2.34, +10.53] [[NEEDS LEDGER: D1 TGC task CI]] | [[NEEDS LEDGER: D1 SGC]] |
| D2 = S − A (prompt and content) | +2.30 [−2.43, +7.31] [−1.58, +6.28] | 0.7208 | +1.17 [−4.68, +8.19] [−5.26, +7.60] | +3.51 [−5.26, +12.28] |
| D3 = N − A (prompt) | +3.73 [−0.06, +8.24] [+0.04, +7.66] | 0.2192 | +5.85 [−1.17, +14.04] [−0.58, +12.87] | +1.75 [−5.26, +8.77] |
| D4 = T − N | +2.40 [−2.94, +8.89] [−1.97, +7.05] | 0.7208 | −0.58 [−8.77, +7.02] [−7.60, +6.43] | +1.75 [−5.26, +8.77] |

No registered decision rule fires (DEC-01). *Prompt artefact* needed D4's interval to include zero, which held, and D3's to exclude it, which missed at a lower bound of −0.06; *execution matters* and *content, not execution* needed D1's and D2's intervals to exclude zero (−1.56, −2.43). The outcome is unresolved and we make no decomposition claim. D3's near miss is stable at all seven bootstrap seeds, and its exact sign-flip p is 0.1089 (DEC-03).

### 3.3 Where the gap sits: the step limit (exploratory)

Correction-prompt advice ends at the 40-step limit in 20 of 171 episodes, takeover in 2 of 171 (LIM-01). We split each contrast by whether either arm hit the limit. That split conditions on an outcome of treatment, so it describes a mechanism and is never a corrected estimate (LIM-02). For D0, the 22 pairs where either arm hit the limit contribute +4.07 pp of the +6.13 pp (scenario [+0.93, +7.72], task [+1.52, +7.12]); over the 149 pairs where neither did, the mean difference is +2.37 pp (scenario [−0.59, +6.34], task [−1.67, +6.86]) and does not resolve. Takeover against neutral advice shows the same pattern: the 16 pairs with a limit contribute +3.55 pp ([+1.00, +7.03]; [+1.34, +6.19]), and over the other 155 takeover is −1.26 pp against neutral advice ([−6.04, +3.61]; [−5.04, +2.59]), unresolved (LIM-05); this is not evidence that takeover is worse when no one hits the limit. For N − A and S − A neither part resolves (LIM-03, LIM-04).

The concentration is not a scoring artefact that flatters takeover. Scoring every limit episode as 0 widens all four gaps (LIM-06): D0 becomes +9.77 pp (scenario [+2.60, +17.97], task [+3.51, +16.41]) and N − A +5.72 pp ([+1.26, +10.74]; [+0.87, +10.70]), while S − A (+4.38) and T − N (+4.05 pp) stay unresolved; the limit-as-0 D0 does not survive the BY adjustment (FDR-01). What the split shows is a termination mechanism: advised by terse correction prose, the executor more often runs out of steps.

### 3.4 What the advice contains (exploratory)

The two advice prompts differ in one line (§2.3). What they elicit differs sharply (DEC-06; seeds 1–3, 171 episodes per arm).

Table 4: Content of the planner's interventions (DEC-06). Shares with scenario and task intervals.

| | A, correction-prompt advice | N, neutral advice | S, shown action |
|---|---|---|---|
| Interventions | 260 | 221 | 228 |
| With a fenced code block | 3; share 0.0115 [0.0000, 0.0263] [0.0000, 0.0264] | 207; 0.9367 [0.8844, 0.9804] [0.9019, 0.9704] | 213; 0.9342 [0.9020, 0.9646] [0.9015, 0.9639] |
| Median length, characters | 242.0 | 1098 | 107.0 |
| Executor copy rate | 0.0115 | 0.1991 | 0.1667 |

The copy rate for advice counts the advice text or any fenced Python block inside it, and the copy rate for a shown action is B2's definition, so the two are not the same measure (DEC-06).

**Reading (exploratory).** What helps the 8B executor is the planner's concrete code, executed (T) or shown (S, and N, which is mostly code). Correction prose that almost never carries code leaves it stuck, and more often at the step limit. The neutral prompt alone recovers +3.73 of the +6.13 pp; takeover's remaining lead over neutral advice (+2.40 pp) does not resolve, and on TGC it is −0.58 pp (DEC-03). This reading was formed after the data. J10's content family tests it on held-out data: CF1 (neutral minus correction advice) is decision-bearing, and CF2 (show minus correction advice) and CF3 (takeover minus neutral advice) are unadjusted secondaries (Amendment 1 §C).

### 3.5 Advice at every step: higher-frequency correction advice (registered H2)

The registered H2 arm, `advise_fixed_k_1_fullctx`, requests correction-prompt advice at every step with full context. Its prediction P4 put its cost at 300k to 700k non-cached planner tokens per episode; it spent 1,414,410 and made 19.02 hosted calls per episode (CHAN-PRICE-02). The registration's rule for a failed P4 reads: *"report the arm as a higher-frequency advice result only, and state explicitly that advice remains unpriced at the action channel's budget."* We follow it: **advice remains unpriced at the action channel's budget**, and this arm is reported only as higher-frequency correction advice.

As such it scores 0.6630 `goal_pass` (TGC 0.4474; CHAN-PRICE-01), with 12 of 114 episodes at the step limit (0.1053; LIM-01). It is 14.68 pp below the m = 11 prefix (scenario [−22.09, −7.04], task [−21.56, −7.79]; TGC −15.79 pp, [−28.07, −3.51] and [−25.44, −5.26]; CHAN-PRICE-01) and spends 3.19× the prefix's non-cached tokens ([2.47, 4.06]) and 1.69× its hosted calls ([1.51, 1.89]) (ROB-19). Against the one-plan floor it is −5.51 pp (scenario [−13.15, +2.51], task [−12.63, +1.72]), so P1 holds as an interval that includes zero (CHAN-PRICE-01). Against advice every ten steps it is −7.08 pp (scenario [−14.78, +0.67]), so P3 holds on the scenario clustering, and on the task clustering the upper bound is negative at six of seven bootstrap seeds (ROB-04): ten times the review frequency does not buy quality.

An argument that P4 failed in the direction its rule was not written for is a declared deviation discussion in Appendix B, not a result. J10 P1 tests the same contrast on held-out data, and Amendment 1 §E constrains its description the same way.

### 3.6 Neutral advice at every step (pending dev arm)

*Placeholder, to be filled when the ledger rows exist.* This dev arm is exploratory: it requests advice under the neutral prompt at every step (k = 1), and it will show whether code-bearing advice, bought at the frequency of §3.5, reaches the prefix arms' quality at a comparable budget, the comparison §3.5's arm cannot give.

### 3.7 Structured direction (pending dev arm)

*Placeholder, to be filled when the ledger rows exist.* This dev arm is exploratory: the planner gives structured direction in the style of ManagerWorker and Minions at k = 10, and it will show whether a text-only protocol of the kind prior work finds effective closes the gap to takeover.

---

## 4. Handoff depth

A prefix arm replays the first m actions of a recorded planner trajectory and then hands control to the executor. Ganz et al. report, in their App. B.2: *"Later downshift generally improves quality while retaining less savings."* [@handoff_tax_ganz_2026]. Our depth curve replicates and extends that finding (§1, §7). Unless noted, §4.1–§4.6 use the pooled cap-81 prefix family: 171 pairs over seeds 1–3, with prefix arms and the planner acting alone paired on the same trajectories. Every result in §4 is exploratory.

### 4.1 At m = 11 most episodes never hand off

In the pooled cap-81 family the prefix leaves the executor no handoff in 4 of 171 episodes at m = 6, 54 of 171 at m = 9 and 100 of 171 at m = 11, on both receivers (HO-01). **At m = 11 most episodes never hand off**: the replayed trajectory finishes the task inside the prefix, and on those episodes the arm scores what the planner scored. On the cap-25 source of earlier analyses the executor never acted in 56 of 114 episodes at m = 11 (SHAPE-06). So every pooled depth or NI number below carries its handoff-only companion beside it, as the dev registration required (`docs/prereg_hj12_dev_20260922.md:336-341`).

The handoff-only estimate is Σd·h / Σh over pairs, with h the deeper (m = 11) arm's own handoff flag and whole clusters resampled (HO-04). Because h is an outcome of the arm, handoff and silenced episodes are different tasks: the split describes which episodes the prefix exhausts, not an effect of handing off (HO-02). Step-limit episodes, seeds 1–2 (of 114): tailored 9, 8 and 8 and untailored 18, 7 and 9 at m = 6, 9, 11, and 18 for the planner alone at cap 81 (LIM-01); seed 3 (of 57): tailored 11, 7 and 3 and untailored 10, 3 and 1 (POOL-01); the planner alone's seed-3 count is [[NEEDS LEDGER: `planner_alone_cap81` seed-3 limit count]].

### 4.2 The span, pooled and handoff-only

Table 5: The m = 6 → 11 span, pooled cap-81 family, in pp; each cell gives the point, the scenario interval, then the task interval. Handoff-only n = 71, silenced n = 100 (HO-04..07). The m = 9 → 11 rows are Table D2.

| Receiver, metric | All episodes (171) | Handoff-only | Silenced |
|---|---|---|---|
| tailored, `goal_pass` | +8.39 [+4.20, +12.63] [+4.09, +12.96] | +12.03 [+5.49, +18.57] [+5.07, +19.19] | +5.81 [+1.00, +11.17] [+0.51, +11.28] |
| tailored, TGC | +15.79 [+8.19, +23.98] [+8.77, +23.39] | +15.49 [+3.03, +30.16] [+4.69, +27.40] | +16.00 [+7.45, +24.55] [+7.14, +25.49] |
| untailored, `goal_pass` | +7.70 [+3.69, +12.06] [+3.14, +12.30] | +13.93 [+5.12, +21.22] [+5.48, +22.42] | +3.27 [−1.71, +8.10] [−1.81, +8.51] |
| untailored, TGC | +11.70 [+6.43, +16.96] [+4.68, +18.71] | +15.49 [+4.29, +26.47] [+4.41, +26.92] | +9.00 [+1.05, +16.67] [0.00, +17.78] |

Over m = 6 → 11 the rise resolves over all episodes and over handoff episodes, for both receivers and both metrics, and on `goal_pass` it is larger over handoff episodes: tailored +8.39 pp against +12.03 pp, untailored +7.70 against +13.93 (HO-04, HO-06). The tailored handoff-only TGC rise has an exact sign-flip p of 0.0571 (HO-05). The m = 9 → 11 step is weaker: on the tailored receiver it is +7.73 pp over handoff episodes (sign-flip p 0.0186) and +4.25 pp over all episodes, where the sign-flip p is 0.0749 and the lower bound turns negative at one of seven bootstrap seeds (HO-04, POOL-01); on the untailored receiver it resolves in no population (+1.44 pp all, +0.27 pp handoff-only; HO-06). J12 tests the four m = 6 → 11 `goal_pass` contrasts (D1–D4); J10's P4 tests the untailored m = 9 → 11 step.

**Where the rise is earned.** Over m = 6 → 11 the handoff episodes earn a share of 0.5952 of the tailored `goal_pass` rise (scenario [0.37, 0.89], task [0.33, 0.94]) and 0.7514 of the untailored ([0.35, 1.16]; [0.42, 1.24]) (HO-09). On the tailored m = 9 → 11 step the handoff share is 0.7552 ([0.50, 2.17]; [0.37, 1.78]); the untailored step does not resolve, so its share is not read (HO-08). On the cap-25 source over m = 2 → 11, by contrast, the tailored receiver earned only 16.7 % of its +12.42 pp rise on handoff episodes ([−7.1, +38.3]; ROB-13). The depth effect is part planner finishing and part better handoffs, in proportions that depend on the source and the span.

### 4.3 No localizable breakpoint, and replicate noise

On the cap-25 grid m ∈ {2, 4, 6, 7, 8, 9, 10, 11}, all-episode `goal_pass` is non-decreasing in its point estimates, from 0.6856 at m = 2 to 0.8098 at m = 11 (SHAPE-06), and no adjacent step resolves: the Holm-adjusted p is 1.0 for all eight adjacent steps (MULT-01). The registered segmented test holds S1 and S2 and fails S3 in 8/8 configurations, so no threshold location is claimed; it was written after the curve had been seen and is exploratory in force (F1-RESULT-01). A hinge beats a line only because of the plan-only m = 0 anchor; the prefix arms alone fit a line at +1.43 pp per step ([+0.80, +2.04]; ROB-15).

Executor run-to-run noise is not negligible. The largest single-arm replicate deviation observed is **3.31 pp**: `prefix_m2` scored 0.7187 and then 0.6856, across two runs that straddle the terminal-guard code change, which provably does not fire at m = 2 or 4 (NOISE-01). The registered replicate floor, re-running m = 6 and m = 9, gave 0.04 and 1.82 pp and does not trigger its withdrawal condition (NOISE-03). Under NOISE-01's 3.31 pp as the floor, it would.

### 4.4 The chord test

The dev frontier's claim C2 asked whether the prefix arms lie above the straight line (chord) from the one-plan floor to the planner acting alone, placed at each arm's share of hosted tokens. It failed: at m = 9 the residual was +3.96 pp ([−0.49, +8.88], task-clustered; UF-07), and its NI limb failed at every depth it named (Table 1).

Re-run against the cap-81 planner alone (114 pairs, seeds 1–2), tailored m = 9 is not resolved above the chord (`goal_pass` +3.02 pp, [−1.48, +7.21], [−1.28, +7.26]; cost fraction f = 0.2984), and tailored m = 11 lies above it (`goal_pass` +7.56 pp, [+2.96, +12.35], [+3.30, +11.98]; f = 0.3819), with TGC agreeing at both depths (CHORD-01; Appendix D.4). The untailored m = 11 residual is +5.76 pp ([+2.15, +9.44]; [+2.17, +9.55]), measured against the tailored floor, so it mixes in the receiver difference (CHORD-02). This re-run is not the registered test, and m = 11 is post hoc. J10 carries the chord test for m = 9 and m = 11 on both receivers (Amendment 1 §B3).

### 4.5 Ganz-comparable metrics and the cost share

Quality recovery, QRec = (arm − floor) / (reference − floor), with the one-plan floor (0.7181) and the cap-81 planner alone (0.7637) as anchors over 114 triples, is not resolved at any depth on either receiver. Tailored QRec is 0.6491, 0.9607 and 2.0420 at m = 6, 9, 11, and the m = 11 interval is [−14.29, +17.77] (task [−8.59, +14.74]) (GANZ-01, GANZ-02); the two anchors' means are close, and §2.4's floor makes such a ratio fragile. Savings retained do fall with depth, and every interval excludes zero (GANZ-03): hosted-call savings retained are 0.6325, 0.4528 and 0.3605 (m = 11: [0.23, 0.47]; [0.27, 0.43]), and dollar savings retained 0.7058, 0.5545 and 0.4684 (m = 11: [0.27, 0.62]; [0.34, 0.57]). Only the cost half of Ganz et al.'s trade-off is resolved here.

Against the pooled cap-81 planner alone (171 pairs), the m = 11 arms use 0.6550 of its hosted calls (scenario [0.56, 0.76], task [0.59, 0.73]) and retain 0.4292 of its dollar cost as saving ([0.26, 0.57]; [0.32, 0.52]); at m = 6 the figures are 0.4048 and 0.6508 (COST-04; cap-25 ratios in Appendix D.9). A deep prefix buys its gain by spending most of the planner's budget.

### 4.6 Non-inferiority to the planner acting alone

The reference is the planner acting alone at cap 81 in the same harness, 0.7697 `goal_pass` and 0.5906 TGC over the 171 pairs; δ = 7.00 pp (§2.5).

Table 6: Arm minus the planner alone at cap 81, pooled, trajectory-paired, in pp; point, scenario interval, task interval; H = NI holds, F = fails (HO-NI-01..03). Handoff-only n = 117 at m = 9 and 71 at m = 11.

| Arm (mean `goal_pass`) | `goal_pass`, all 171 | `goal_pass`, handoff-only | TGC, all 171 | TGC, handoff-only |
|---|---|---|---|---|
| tailored m = 9 (0.7714) | +0.16 [−4.05, +4.65] [−4.29, +4.71] H | −4.21 [−8.83, +1.29] [−9.43, +0.93] F | −6.43 [−12.28, −0.58] [−12.87, −0.58] F | −12.82 [−20.83, −4.35] [−21.14, −4.88] F |
| tailored m = 11 (0.8139) | +4.41 [−0.74, +10.67] [+0.34, +8.65] H | −0.94 [−9.53, +7.45] [−7.87, +5.97] F | +0.58 [−5.85, +7.60] [−4.68, +5.85] H | −8.45 [−21.54, +3.53] [−18.46, +1.52] F |
| untailored m = 9 (0.7747) | +0.50 [−3.02, +5.36] [−3.50, +4.80] H | −0.31 [−5.54, +6.72] [−6.02, +5.69] H | −5.26 [−9.94, −0.58] [−10.53, +0.58] F | −8.55 [−15.79, −0.94] [−16.81, 0.00] F |
| untailored m = 11 (0.7892) | +1.94 [−2.17, +6.40] [−1.66, +5.75] H | −4.36 [−11.89, +3.21] [−10.68, +2.43] F | −2.92 [−7.02, +1.17] [−7.60, +1.75] F | −15.49 [−25.76, −5.80] [−24.64, −6.85] F |

Over all episodes every arm is non-inferior on `goal_pass`. Over the episodes that hand off only the untailored m = 9 arm is, and that test does not survive the BY adjustment (FDR-01). On TGC only the tailored m = 11 arm is non-inferior, and only over all episodes (HO-NI-03). At m = 11, 100 of the 171 all-episode pairs compare the planner with its own replayed trajectory, which is why the all-episode and handoff-only verdicts part (HO-01). In the earlier 114-pair comparison with cap-25-sourced prefixes, the tailored m = 11 TGC verdict holds under the percentile interval but not under an exact one-sided sign-flip test (p = 0.0264, above its 2.5 % level; ROB-05), and fails against the cap-25 planner alone (ROB-21; two-reference table in Appendix D.1). We read NI here as "not distinguishable from the planner alone within δ at n = 171", not as equivalence, and the reference is harness-limited (§2.2), so none of this says the executor reaches the planner's quality in a proper scaffold. J10's P3 tests the tailored m = 11 all-episode contrast, with a handoff-only companion printed beside it (Amendment 1 §B1).

### 4.7 The planner alone at high reasoning effort (pending dev arm)

*Placeholder, to be filled when the ledger rows exist.* This dev arm is exploratory: it runs the planner acting alone in the same harness at high reasoning effort, and it will show how much of the reference's weakness (§2.2) is the harness and effort setting rather than the model, and so how far the NI readings of §4.6 depend on a weak reference.

---

## 5. What a prefix conveys: the narrated control

The narrated control renders the planner's first m actions as text in the executor's prompt and starts the executor at step 0 in a fresh environment: the prefix's information without its state (NARR-00). At m = 9, the registered contrast, executed minus narrated is +1.84 pp on the tailored receiver (scenario [−2.67, +6.76], task [−3.70, +7.75]) and +1.69 pp on the untailored ([−4.16, +7.11]; [−3.70, +7.38]); all eight intervals over both receivers and both metrics include zero, so at this depth narration and execution are not distinguishable at n = 114 (NARR-01).

m = 9 is where the two curves are closest. On the untailored receiver execution beats narration at m = 11 on both metrics and both clusterings (`goal_pass`, narrated minus executed, −6.58 pp, [−9.98, −3.64], [−10.95, −2.71]; TGC −11.40 pp) and on TGC at m = 6 (−13.16 pp), and the narrated curve is flat past m = 9 (+0.10 pp, [−4.75, +5.14]) (NARR-03). On the tailored receiver no same-depth gap resolves (−2.51, −1.84 and −0.49 pp at m = 6, 9, 11; at m = 11 [−4.10, +3.21]), and its narrated curve keeps rising (NARR-04). We measure the receiver difference directly as a per-episode difference-in-differences. At m = 11 it is +6.09 pp (scenario [+1.56, +11.00], task [+0.63, +11.85]; exact sign-flip p = 0.0235), its TGC counterpart +12.28 pp ([+0.88, +26.32]; [+2.63, +22.81]) does not pass the exact test (p = 0.0996), and at m = 6 and m = 9 it does not resolve (DID-01, ROB-08). Three depths and two metrics were tested and one cell resolves, so this is exploratory.

**Reading (exploratory).** At moderate depth a prefix's value travels as information. At the deep end, and on an untailored receiver, execution adds something the text does not, while a tailored receiver recovers it from the text. Both fit the headline: the executor uses the planner's concrete actions, and whether seeing them suffices depends on the receiver. Adding the planner's observations to the narration changes neither receiver detectably at m = 9 (NARR-05; Appendix D.5); that null does not show that the facts the actions returned carry no benefit.

---

## 6. Mechanism: descriptive correlates

Two correlates go with depth. Neither is a causal test, and we do not claim that either causes the rise.

- **API discovery is front-loaded in the planner's trajectories.** Of 673 first uses of an API across 114 source episodes, 78.3 % occur by position 9 and 86.6 % by position 11 (MECH-08). This describes the source trajectories, not the executor.
- **The executor errors less after a deeper prefix.** On the tailored receiver the share of handoff episodes with at least one failed observation is 85.09 % at m = 2, 56.76 % at m = 6, 42.68 % at m = 9 and 42.59 % at m = 11; on the untailored receiver it is 80.18 %, 64.63 % and 61.11 % at m = 6, 9, 11 (MECH-05). These rates are conditional on handing off at each depth, over populations that shrink with m, so they are not paired contrasts and carry no interval.

On the cap-25 source, the share of the m = 6 → 9 rise earned on handoff episodes differs by receiver (ROB-14, MECH-07; Appendix D.4). Depth coincides with less exploration left to the executor and fewer chances to err; that is a description, not a mechanism shown.

---

## 7. Related work and positioning

**Handoffs between models.** Ganz et al. hand trajectories between low- and high-cost Claude and GPT models, in both directions and at several switch points, on SWE-bench Verified, Lost in Conversation and BrowseComp, comparing raw transfer, compaction and trajectory removal [@handoff_tax_ganz_2026]. Their GPT low-cost model is `gpt-5.6-luna`, our planner. Escalation pays a "handoff tax", downshifting is a favourable cost–quality point, and "Later downshift generally improves quality while retaining less savings" (their App. B.2). Our depth curve replicates that downshift-timing result in AppWorld with a local 8B receiver; ours are the handoff-only accounting, the chord and narrated controls, and the receiver comparison. Their finding that removing the stronger model's trajectory lowers downshift quality is the counterpart of our narrated control, which keeps the trajectory's text and removes its execution. Reach-or-Solve hands states between checkpoints and warns that analysing only states both reach selects on outcome [@reach_or_solve_2026]; our replayed prefixes use that protocol, and our handoff-only populations carry that caution. Do Not Restart treats a stateful handoff as residual completion under commitments [@do_not_restart_2026] without comparing the forms help takes. Handed-over context reduces rediscovery in coding agents [@handoff_debt_2026], and a one-turn model switch shifts multi-turn outcomes [@perf_drift_switching_2026].

**Local–cloud collaboration and direction in text.** Minions pairs an on-device model with a cloud model and finds that the protocol decides the outcome: naive back-and-forth chat recovers less than a protocol in which the cloud model decomposes the task into subtasks for the local one [@minions_narayan_2025]. In ManagerWorker a text-only strong manager directs a cheap worker that holds the repository and reaches the strong single agent's score, with structured exploration and planning adding far more than a review-only loop [@managerworker_liu_2026]. COPE exchanges plans between small and large models in a cascade [@cope_lee_2025]. These are published cases in which text-only help works because the protocol is good. Our correction prompt is a weak protocol, and the neutral prompt, which elicits code, is where our advice recovers; the pending structured-direction arm (§3.7) is the prior-work baseline.

**Routing and escalation.** Cascades and routers choose which model answers or acts [@frugalgpt_chen_2023; @hybrid_llm_ding_2024; @routellm_ong_2024; @learning_to_defer_mozannar_2020], increasingly within a trajectory: per step [@policy_stepwise_routing_2026; @agentic_routing_2026], per turn [@mtrouter_2026], after cheap exploration [@swe_router_2026], or on predicted failure [@r2v_agent_2026]. TACIT-Switch learns when to hand off permanently to a larger backbone [@tacit_switch_2026], and SwiftSage calls a large model by rule [@swiftsage_lin_2023]. In speculative decoding, sampling and planning a small model drafts what a large one verifies [@speculative_decoding_leviathan_2023; @speculative_sampling_chen_2023; @bild_kim_2023; @dsp_guan_2025; @isp_2024]; in LATM a strong model writes tools a weak one applies [@latm_cai_2024]. These methods decide which model acts. Our learned gates for that decision were a registered null (ESC-01), so we fix the schedule and vary the form of the help.

**Planners, critics and advisors.** ReWOO and Plan-and-Act pass plans to executors [@rewoo_xu_2023; @plan_and_act_erdogan_2025], and role-factorised systems assign planner, executor or critic roles to models of different size [@coda_liu_2025; @agentcard_jiang_2026; @three_roles_2026; @think_big_search_small_2026]. Verbal feedback critiques and revises [@self_refine_madaan_2023; @reflexion_shinn_2023; @critic_gou_2023], self-correction without external feedback is weak [@llms_cannot_self_correct_huang_2024; @self_correction_survey_kamoi_2024], small models need strong verifiers [@slm_need_strong_verifiers_2024], and simulated language feedback helps tool users [@mint_wang_2024]. COTA returns a tiny comparator's preferred alternative as non-binding advice [@cota_jiang_2026]. In reinforcement learning, when a budgeted teacher advises a student matters [@torrey_taylor_2013]; in human teaching, telling outperforms showing for complex concepts [@sumers_show_or_tell_2023]. Here the telling that helps is advice carrying code, a statement about this receiver and these prompts, not about teaching.

**Demonstrations, prefixes and distillation.** ReAct and Synapse steer agents with in-context trajectories [@react_yao_2023; @synapse_zheng_2024]; our narrated control is the task-specific case whose exemplar is the planner's own opening. DAgger queries the expert on learner-visited states [@dagger_ross_bagnell_2011], reverse curricula start from demonstration states [@backplay_resnick_2018; @salimans_chen_2018; @rfcl_2024], agent tuning distils teacher trajectories [@fireact_chen_2023; @agentinstruct_zeng_2023; @agentflan_chen_2024; @agent_distillation_2025], and ReOPD, Guided-OPD and Prefix-GRPO use teacher prefixes in training [@reopd_liao_2026; @guided_opd_2026; @prefix_grpo_wang_2026]; here the prefix is present at deployment. Models err more when their context holds their own earlier errors [@sinha_illusion_2026], an account consistent with, but not tested by, our error-incidence correlate (§6).

**Benchmarks.** AppWorld [@appworld_trivedi_2024], τ-bench [@tau_bench_yao_2025] and BFCL [@bfcl_patil_2025] evaluate tool-using agents; the strongest AppWorld results train or adapt a single agent on the test splits [@loop_2025; @canopy_2026; @ace_2026], and Appendix D.8 says why our dev scores are not comparable.

---

## 8. Limitations

1. **Dev only.** Every result is on the 57-task dev split. J10, J11 and J12 have not run; `test_challenge` is sealed.
2. **One planner on dev.** A Qwen3-8B planner fails LP's informativeness gate: acting alone it scores below the tailored executor acting alone by −26.23 pp (LP-01), and the LP-2 dev read is not yet in the ledger. J11 tests the channel with the LP-2 planner on held-out data.
3. **One environment.** A second environment is being built and is not reported here.
4. **A harness-limited reference.** The planner acting alone scores lower with a larger call cap (CEIL-07) and well below its leaderboard score under a scaffold (§2.2); NI to it is NI to a weak reference (§4.7 is pending).
5. **Few clusters and many contrasts.** With 19 scenarios, exact tests pass the 114-pair channel result only narrowly and not the 171-pair one; the BY adjustment covers the 28 re-analysis contrasts only, not every interval printed here ([[NEEDS LEDGER: BY adjustment over every interval the paper prints (R4.3)]]); and the ledger's exploratory rows outnumber its registered ones by 86 to 32. Source: CENSUS-01.
6. **Forking paths.** The headline reading, the depths m ∈ {7, 8, 10, 11}, the handoff-only and limit analyses and the chord re-run were all chosen after data (Table 1).
7. **A declared deviation.** H2's arm is reported under its registration's rule; the argument we once made against applying that rule is in Appendix B.
8. **The advice prompts.** Only one arm (N) uses the neutral prompt, at k = 10; the neutral and structured arms of §3.6–§3.7 are pending.
9. **Metric floors and the second family.** `goal_pass` awards about a third of its scale for doing nothing (NOOP-01), and the Qwen family's floors measure format acquisition rather than competence (Appendix D.7).
10. **Privacy and latency.** The hosted planner sees the task and the transcript (§1), and per-call latency was not recorded (LAT-01).

---

## 9. Conclusion

On the AppWorld dev split, a local 8B executor does better when the hosted planner's help arrives as concrete code, executed or shown, than as terse correction prose. That reading is exploratory. The registered matched-trigger contrast resolves at 114 pairs and weakens at 171, most of its gap sits in episodes where the correction-advised executor runs out of steps, and a neutral prompt that elicits code recovers +3.73 of its +6.13 pp without quite resolving. Handing off later raises quality over all episodes and over the episodes that still hand off, but at m = 11 most episodes never hand off, and the effect replicates a downshift-timing result already published. Non-inferiority to the planner acting alone holds over all episodes and not over handoff episodes, against a reference its own harness limits. J10, J11 and J12 test these claims on held-out data; until they run, this paper reports dev estimates and says which were registered.

---

## Appendix A. Reproducibility and statistics

### A.1 The ledger and the number audit

Every number in this paper is produced by a script from per-episode `result.json` files and recorded in `docs/claims_ledger.md` with its report path and JSON key. `scripts/analysis/preprint_number_audit.sh` checks the draft against the ledger mechanically: unsigned percentage-point figures and four-decimal rates as set differences, signed figures with their sign, intervals as ordered pairs, forbidden wording, and registration wording beside exploratory ledger ids; it fails on any violation. A NEEDS-LEDGER marker in double square brackets names a number that has no ledger row yet and is not printed. The check exists because of a real failure (Appendix E.2).

The report `campaign/results/j10_a1_registered_dev_basis_20260924.report.json`, which sources the like-for-like cap-81 contrasts of Appendix D.4, holds **dev data only**. Its name records that the A1 registration cites it as its dev basis; it contains no `test_normal` episode.

### A.2 Figures

No figure is drawn from retyped numbers: `scripts/analysis/figures.py` reads each series from a report by key and refuses to render a panel whose key is missing (FIG-01); `paper/figures/figures_manifest.json` records every figure's source reports and keys.

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

Contrasts are paired on `(task_id, seed)` and bootstrapped over clusters, not episodes: 10,000 percentile draws, scenario-clustered as primary and task-clustered beside it, because the 57 dev tasks form only 19 scenario groups. A crashed episode scores 0 under the all-episodes population; `limit` is not a crash and keeps its score. Difference-in-differences contrasts are formed per episode before averaging, so the pairing survives into the bootstrap.

**Boundary stability (POOL-04).** At B = 10,000 the Monte Carlo error on a percentile bound is a few tenths of a point, so any decision-relevant bound within 1 pp of zero or of the margin is re-drawn at the seven seeds 20260924, 1, 2, 3, 7, 101 and 999, and the quantity is unresolved if the verdict changes. TGC is discrete, so a TGC bound can be identical at every seed without being precise.

**Small-cluster alternatives.** Headline contrasts were re-tested with a two-sided sign-flip randomization test, exact on the 19 scenarios and Monte Carlo on the 57 tasks, and with wild cluster bootstrap intervals; NI uses the one-sided sign-flip test against the margin (ROB-01).

**Rows with one clustering.** The following ledger rows carry scenario intervals only, and their task-clustered companions are one marker: CHAN-C1-02's TGC companion (ROB-02), ROB-11 and ROB-13 to ROB-21, NARR-04, UF-07 (whose single interval is task-clustered), and the ratio intervals of ROB-19 and ROB-20 [[NEEDS LEDGER: task-clustered companions of the scenario-only rows listed in Appendix A.4]].

### A.5 Provenance

Campaign-granularity provenance for every campaign a report reads is generated by `scripts/analysis/campaign_index.py` into `campaign/campaign_index.{json,md}`. Three gaps remain. The run record stores less than the index reports: the index's config, adapter and source-campaign fields are reconstructed from the repository, not recorded by the run. Several campaigns, including the dev prefix arms, ran under a campaign id passed on the command line rather than the one their config declares, so re-running such a config verbatim writes to a different directory. And two dependencies, including the third planner sample, have no committed config. The runner now stamps git SHA, config, adapter, source campaign and split into every episode manifest; every campaign behind this paper predates that change.

No published campaign is proven to contain a second roll of a scored failure (PROV-01). In six published prefix arms, all outside the headline depth curves, hosted luna answered an executor's ask live, which bounds each arm-mean lift (PROV-02; Appendix D.6).

---

## Appendix B. Declared deviation: H2's failed cost prediction (CHAN-PRICE-02)

**What was registered.** P4 predicted that advice at every step would spend 300k to 700k non-cached planner tokens per episode, and §5 of the H2 registration says that if P4 fails, the arm is reported "as a higher-frequency advice result only", stating "that advice remains unpriced at the action channel's budget". The main text (§3.5) follows that rule.

**The argument we set aside.** An earlier draft argued that the rule was written for the opposite case: an arm that lands below 300k was never priced at the action channel's budget, so a win over it could be a budget win, while this arm spent 1,414,410 tokens, far above the prefix arms, and so the hazard the rule guards against was excluded *a fortiori*. On that argument the draft reported P2 as a test of advice at matched budget. We record the argument as a deviation discussion and do not rely on it, for two reasons. The registration's text does not distinguish the directions of failure. And the argument is weak on substance: P3 shows that more correction advice does not do better, so moving from k = 10 to k = 1 changes the dose of an error-presuming prompt; it does not match the budget.

Table B1: Advice at every step beside the arms it was compared with (114 pairs; CHAN-PRICE-01, CHAN-PRICE-02, COST-01).

| Arm | `goal_pass` | Non-cached planner tokens / episode | Hosted calls / episode | Step-limit episodes |
|---|---|---|---|---|
| `advise_fixed_k_10_fullctx` | 0.7339 | 49,819 | 2.46 | 13 of 114 (ADV-FC-01) |
| `advise_fixed_k_1_fullctx` | 0.6630 | 1,414,410 | 19.02 | 12 of 114 (0.1053; LIM-01) |
| `prefix_m9` | 0.7852 | 357,448 | 9.77 | [[NEEDS LEDGER: `hj12_prefix_m9` limit count]] |
| `prefix_m11` | 0.8098 | 443,361 | 11.25 | [[NEEDS LEDGER: `hj12_prefix_m11` limit count]] |

Against the cap-81-sourced tailored m = 11 prefix, advice at every step is −14.81 pp [−21.20, −7.96] (CEIL-05), and on SGC against `prefix_m11` it is −23.68 pp [−42.11, −7.89] (ROB-11). The one advice arm near the prefix arms' budget, `advise_fixed_k_3`, ran with an 8-line context and is −2.25 pp against the m = 6 prefix ([−9.05, +5.15]), confounding depth with context starvation (ROB-20).

---

## Appendix C. Multiplicity and census

### C.1 Benjamini–Yekutieli over the re-analysis contrasts (FDR-01)

The family is every `goal_pass` contrast in the two dev re-analysis reports, 28 in all (8 channel, 20 depth), mixing superiority tests with the NI tests of Table 6; it is not the adjustment over every interval the paper prints that R4.3 asks for ([[NEEDS LEDGER: BY adjustment over every interval the paper prints (R4.3)]]). At 0.05, 9 survive.

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

The campaign index lists 70 campaigns; 47 are dev campaigns, and they form 39 distinct dev arms. When the census report was built, the ledger held 149 rows, of which 32 were registered, 86 exploratory and 31 of other status (amended, correction, method, pending and similar). Those counts predate the re-analysis rows. The census does not count contrasts run [[NEEDS LEDGER: number of dev contrasts run (R4.4)]]. Source: CENSUS-01.

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

**Orientation and keys.** Every NI number in this paper is arm minus reference. CEIL-05 and POOL-02 store reference minus arm; we print their contrasts from ROB-21 and HO-NI-01..03, which use arm minus reference. For tailored m = 9 TGC against cap 81 we print ROB-21's key (`F_e_ni_both_ceilings.ni_table.t_m9.cap81_tgc`, [−9.65, +8.77]); COST-03's separate run of the same contrast gives [−9.65, +7.89], and the two runs use different bootstrap seeds (ROB-05 names COST-03's as 20260915).

**The v1 abstract's claim, qualified.** Against cap 81, three of the four m = 11 arms hold on both metrics. Two of those three are cap-25-sourced and so only task-paired with the reference, and of the two trajectory-paired (cap-81-sourced) arms one fails TGC. The tailored `prefix_m11` TGC pass fails an exact one-sided sign-flip test (p = 0.0264; ROB-05). Against the trajectory-paired cap-25 reference only the untailored m = 11 arm holds, on `goal_pass` alone; the +0.23 pp NI in UF-06 belongs to the pre-guard arm (ROB-16).

**Excluding the reference's limit episodes.** Restricting the cap-25 reference to the 102 episodes in which it did not hit its call cap makes `prefix_m11` fail (−5.92 pp, scenario [−9.80, −2.57]; CEIL-01), but that exclusion selects on the reference's own failures: on cap-25 the 12 dropped episodes score 0.1488 against 0.9083 on those kept, on cap-81 the 18 dropped score 0.1786 against 0.8734, and the reference-free difficulty proxies do not resolve (ROB-17, ROB-21). We treat −5.92 pp as a bound under that selection.

### D.2 The third planner seed and the boundary (POOL-01, POOL-04, ROB-06)

A third planner seed plus six replay arms that make no hosted calls pool the cap-81 sample to 171 pairs, none dropped (POOL-01). The m = 6 → 11 spans survive exact sign-flip tests (p = 0.0019 untailored, 0.0014 tailored; ROB-06). The tailored m = 9 → 11 step does not resolve: its scenario interval [+0.15, +8.75] clears zero by 0.15 pp, and re-running the identical estimand at the seven bootstrap seeds 20260924, 1, 2, 3, 7, 101 and 999 gives lower bounds of +0.1526, +0.0801, +0.0544, −0.0140, +0.1468, +0.1953 and +0.1088, with +0.1041 at 200,000 resamples (POOL-01). The verdict flips at one seed in seven, the exact test gives p = 0.0749 (ROB-06), and pooling narrowed the interval by 1.98 pp of width (10.57 → 8.59) without converting a null into a finding. The untailored step, +2.82 pp at two seeds (CEIL-05), is +1.44 pp at three (HO-06).

Table D2: The m = 9 → 11 step, pooled cap-81 family, in pp; point, scenario interval, task interval (HO-04..07). The m = 6 → 11 span is Table 5.

| Receiver, metric | All episodes (171) | Handoff-only | Silenced |
|---|---|---|---|
| tailored, `goal_pass` | +4.25 [+0.15, +8.75] [+0.90, +7.87] | +7.73 [+2.51, +13.05] [+2.48, +13.00] | +1.78 [−2.03, +6.58] [−2.09, +6.12] |
| tailored, TGC | +7.02 [+1.17, +13.45] [+1.75, +12.87] | +9.86 [+2.60, +20.00] [+2.99, +18.03] | +5.00 [−0.96, +11.63] [−1.05, +11.76] |
| untailored, `goal_pass` | +1.44 [−2.56, +5.52] [−2.60, +5.64] | +0.27 [−6.57, +6.96] [−7.59, +7.83] | +2.27 [−1.77, +6.98] [−1.71, +6.64] |
| untailored, TGC | +2.34 [−2.34, +7.02] [−2.92, +8.19] | +2.82 [−7.14, +13.56] [−8.11, +14.06] | +2.00 [−3.30, +7.78] [−3.19, +7.84] |

The two tailored TGC rises resolve on the bootstrap but have exact sign-flip p above 0.05: 0.0586 over all episodes and 0.0625 over handoff episodes (HO-05).

### D.3 The tailoring × depth interaction (POOL-03, DID-02)

The interaction does not resolve on either planner sample (cap-25 −2.53 pp, scenario [−7.66, +2.53]; cap-81 +2.10 pp, [−4.71, +9.01]; DID-02) nor pooled to 171 pairs: `(m11 − m9)_tailored − (m11 − m9)_untailored` is +2.8064 pp, scenario [−2.5661, +8.9649], task [−2.0544, +7.9491], and over m = 6 → 11 it is +0.6924 pp [−4.3971, +5.9164] (POOL-03). It is unmeasured at this power, which is not evidence that it is absent.

### D.4 The cap-25 depth curve, the untailored span and the source swap

On the cap-25 source, the untailored receiver gains +10.21 pp `goal_pass` from m = 6 to m = 9 (scenario [+2.60, +18.20], task [+3.80, +16.81]) and +16.67 pp on TGC ([+5.26, +28.07]; [+7.02, +26.32]) (SHAPE-10). From m = 9 to m = 11 it gains +4.99 pp `goal_pass`, scenario [−0.23, +9.74], task [+0.26, +9.31]: the scenario interval includes zero, so the step is unresolved on the primary clustering; TGC gains +7.02 pp ([+0.88, +14.04]; [+0.88, +13.16]) (CHAN-ZS-04).

Replaying the independent cap-81 trajectories instead, the untailored span m = 6 → 11 is +7.31 pp `goal_pass` (scenario [+2.07, +12.80]) and +9.65 pp TGC ([+2.63, +16.67]) (C81-01). At m = 11 the cap-81 prefix differs from the cap-25 prefix by −4.13 pp (scenario [−8.84, +0.50], task [−9.74, +1.44]): not distinguishable at n = 114, although the cap-81 planner scores 6.47 pp below the cap-25 one. Paired on the same trajectories, the untailored m = 11 arm is +2.95 pp against the cap-81 planner alone ([−1.91, +8.69]) and the tailored +4.75 pp ([−1.16, +11.81]) (ROB-21); under the mismatched pairing the untailored arm had appeared significantly above it (+7.08 pp, [+1.82, +12.78]), and that statement is withdrawn (CEIL-05).

Where the cap-25 rise is earned (§6): on the untailored receiver 83.8 % of the m = 6 → 9 rise is earned on handoff episodes (scenario [55.7, 121.2]; ROB-14); on the tailored receiver the corresponding share is 36.0 % (MECH-07) [[NEEDS LEDGER: interval on the tailored m = 6 → 9 handoff share]], and its handoff-subset gain (+3.08 pp, [−5.38, +11.69]) does not resolve (ROB-13). A descriptive share without an interval is not read as a receiver difference.

Chord residuals on TGC against the cap-81 planner alone (§4.4): tailored m = 9 +6.17 pp ([−2.08, +13.63]; [−1.46, +13.99]) and tailored m = 11 +13.48 pp ([+5.17, +22.20]; [+5.84, +21.45]) (CHORD-01).

Live takeover against oracle prefix replay (§3.1): takeover minus `prefix_m9` is +1.55 pp (scenario [−3.46, +7.04], task [−4.41, +8.01]) and minus `prefix_m11` −0.91 pp ([−6.74, +5.94]; [−6.90, +5.16]) (CHAN-C1-03).

### D.5 Narration detail (NARR-01..05, DID-01)

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

The untailored m = 6 gap resolves on the task clustering ([−13.96, −0.09]) but not on the scenario clustering (NARR-03). On TGC, untailored narrated minus executed is −11.40 pp at m = 11 ([−22.81, −2.63]; [−20.18, −3.51]) and −13.16 pp at m = 6 ([−21.05, −5.26] on both clusterings) (NARR-03). Tailored narration is non-inferior to execution at m = 9 and m = 11 (`goal_pass` lower bounds −6.76 and −4.10) and not at m = 6 (−8.68); untailored narration fails NI at every depth (NARR-04). The tailored narrated curve keeps rising, +6.82 pp from m = 6 to 9 ([+0.63, +12.61]) and +3.81 pp to m = 11 ([+0.79, +6.97]), and tailored narration at m = 11 beats tailored execution at m = 6 by +8.12 pp ([+3.18, +13.67]) (NARR-04).

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

No within-depth receiver gap resolves; at m = 6 untailored minus tailored is −4.12 pp [−10.41, +1.64] and at m = 11 +2.46 pp [−1.48, +6.43]. The registered hypothesis C3, that suffix training extends the upper end, is answered in the negative (HF-02). The suffix-trained arms are not pure replay: hosted luna answered executor asks in 7, 3 and 4 of their episodes at m = 6, 9, 11, which bounds the lift on each arm mean at 2.15, 0.88 and 0.85 pp (PROV-02). On the independent cap-81 sample the untailored-minus-tailored gap runs −2.76, +0.31 and −1.80 pp at m = 6, 9, 11 rather than −4.12, −0.06 and +2.46, all six intervals including zero (C81-02), so we make no claim that depth substitutes for tailoring, or that it does not.

### D.7 A second executor family (QWEN-02..07)

Replaying the same trajectories into zero-shot `Qwen/Qwen3-8B`, `goal_pass` is 0.4491, 0.7017 and 0.7306 at m = 6, 9, 11 (QWEN-04). From m = 6 to m = 11 the rise is +28.15 pp `goal_pass` (scenario [+19.63, +38.47], task [+20.96, +35.72]) and +34.21 pp TGC ([+24.56, +44.74]; [+24.56, +43.86]); the m = 9 → 11 step resolves on TGC (+11.40 pp, [+3.51, +19.30]) and not on `goal_pass` (+2.90 pp, [−1.61, +7.03]; task [−2.80, +8.13]) (QWEN-05). Depth replicates within prefix arms.

Neither Qwen floor may be used as a denominator. The zero-shot floor arms score 0.2481 `goal_pass` with 0 of 114 tasks completed (QWEN-02, QWEN-03); the no-op arm shows that `goal_pass` awards partial credit without any task completed (NOOP-01), which is what that floor also shows, although the two floors are different numbers and we do not assert the mechanism behind either. The tailored Qwen one-plan floor scores 0.2583 and ends 105 of 114 episodes on the step limit (QWEN-06). The adapter is applied, and a train/serve template mismatch is real but not the cause: with the template corrected the floor scores 0.2484 (QWEN-07). What survives is a thin, family-dependent training signal: the terminal action is 165 of 6,767 supervised targets (2.44 %); Granite emits it in 64 of 2,130 executor actions (3.00 %), Qwen in 0 of 4,385, and 3 of 4,431 with the corrected template, rising to 13 in 891 (1.46 %) with a replayed prefix in context (QWEN-06, QWEN-07). Qwen does not acquire the terminal action by fine-tuning at this data scale, but emits it once a prefix demonstrates it in context. The tailoring recipe does not transfer to this family; depth does.

### D.8 The planner-alone reference and external context (CEIL-07, CEIL-06)

Raising the planner's call cap from 25 to 81 lowered its `goal_pass` from 0.8284 to 0.7637 (−6.47 pp; TGC −11.4 pp, [−21.05, −1.75] on both clusterings), with more calls per episode (17.35 against 14.43) and more episodes reaching the step limit (CEIL-07). Across five planner samples the two cap families do not overlap: the lowest cap-25 seed exceeds the highest cap-81 seed by 4.34 pp (CEIL-06). Two samples and three are a spread across what we have, not a variance estimate.

Published AppWorld results are on the test splits, with scaffolds or training that this harness omits [@appworld_trivedi_2024; @loop_2025; @canopy_2026; @ace_2026; @prost_bijoy_2025; @three_roles_2026; @appworld_ul_2026], and the leaderboard lists `gpt-5.6-luna` under a full scaffold [@gpt_5_6_luna_2026] at [[NEEDS LEDGER: leaderboard TGC for `gpt-5.6-luna` with the Capybara scaffold on `test_normal` (v1 L847)]]. Our dev scores are paired contrasts in a minimal harness on the dev split and are not comparable with any of them. The pinned release ships 57 dev tasks.

### D.9 Cost frontier (COST-01..03, ROB-18, DEC-05, LAT-01)

```
Table D7: Cost and quality, AppWorld dev split, n = 114 (COST-01; TGC from the same arms).
---------------------------------------------------------------------------------------------
Arm                                Goal Pass    TGC     Non-Cached Tokens   USD / Ep.   Calls / Ep.
---------------------------------------------------------------------------------------------
executor_alone (granite 8B)          0.5289    0.1316                   0   $0.000000          0.00
plan_only (sft_plan iaware)          0.7181    0.3947              23,906   $0.003015          1.00
advise_fixed_k_10 (8-line ctx)       0.6964    0.4123              43,823   $0.004386          2.42
advise_fixed_k_10_fullctx            0.7339    0.4386              49,819   $0.005494          2.46
takeover_fixed_k_10                  0.8007    0.5175              41,464   $0.004820          2.32
advise_fixed_k_3 (8-line ctx)        0.7012    0.4561             204,500   $0.012203          6.82
prefix_m6                            0.7237    0.4298             221,043   $0.016268          6.98
prefix_m9                            0.7852    0.5614             357,448   $0.022740          9.77
prefix_m11                           0.8098    0.6053             443,361   $0.026475         11.25
planner alone, cap 25                0.8284    0.6842             684,453   $0.035479         14.43
planner alone, cap 81                0.7637    0.5702           1,160,215   $0.048208         17.35
---------------------------------------------------------------------------------------------
```

On the matched-trigger pair, takeover is cheaper than correction-prompt advice as point estimates on all three axes, but paired intervals resolve only the dollar difference, and only on the scenario clustering: −8,356 non-cached tokens [−17,744, +617], −$0.000674 [−0.001361, −0.000024] (task [−0.001539, +0.000161]) and −0.149 hosted calls [−0.368, +0.070] (ROB-18). At 171 pairs takeover is still the cheapest of the four channel arms in non-cached tokens (41.8k against 53.2k for correction-prompt advice) and dollars ($0.00478 against $0.00578), point estimates only (DEC-05). Median wall clock per episode is 41.161 s for takeover, 40.307 s for correction-prompt advice, 45.61 s for neutral advice, 42.301 s for show and 230.402 s for advice at every step; no per-call planner timing was recorded and node load was not controlled, so these are descriptive (LAT-01). Against the cap-25 planner alone, the m = 11 prefix costs 0.746× its dollars ([0.661, 0.831]) and 0.648× its non-cached tokens ([0.550, 0.756]) (ROB-19).

---

## Appendix E. Defect and process record

### E.1 Analysis defects found and repaired

- *Terminal guard (GUARD-01):* early prefix runs let the executor act after a replayed completion; a post-prefix terminal guard now ends such episodes.
- *Handoff flag path (MECH-09, GUARD-03):* the mechanism script read an invalid key; paths were aligned and zero-count populations made fatal.
- *Error-scan actor filter (MECH-04, MECH-05):* early audits filtered observations on executor identity and found no errors; repaired to scan observation text.
- *Adapter build mismatch (ADV-FC-02):* early advice contrasts were paired against an older adapter build.
- *Cost pricing (COST-01):* local executor tokens were at first priced as hosted tokens.
- *Segmented-fit tie-breaking (TIEBREAK-01):* exact float comparisons produced spurious breakpoints on straight lines.
- *Test collection:* for six days the configured test command aborted during collection, leaving the integration tests outside every reported pass count; repaired by renaming.

### E.2 A results table filled with invented values (QUAL-07)

A worker drafting the cost table invented three of its eleven TGC values, one a fill-down of the row above and one wrong by 10.52 pp, while reporting no outstanding work; the `goal_pass` column beside them was correct, so nothing looked wrong. An instruction to flag uncertain values cannot catch that, because a model that does not know it is guessing cannot comply with it. A set difference against the ledger can, and did; that is why the number audit of Appendix A.1 exists.
