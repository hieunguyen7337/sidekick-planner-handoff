# Preregistration Amendment A1 to the J9 Freeze — J10 on `test_normal`

**Status**: **DRAFT, revision 2, pending user review — not freezable until B2 has landed and §6 P7 is completed.**

Amends, and does not edit, `docs/prereg_j9_freeze_20260920.md`. Freezing means replacing the status line above
with one that **begins** `**Status**: FROZEN`, and committing. `scripts/pbs/j10_arm.pbs` refuses a
`test_normal` run unless exactly that holds, the file is committed and unmodified, and the submission carries
`J10_CONFIRM=A1_FROZEN`.

**Revisions** (git commit timestamps are the authoritative record of when each was written):

- **r1** (header date 2026-09-24): the original draft — nine arms, P1–P5.
- **r2** (2026-09-23, calendar date): the seven revisions R1–R7 of the approved plan
  (`docs/plan_two_papers_20260923.md` §3) and the review fixes F1–F9 listed in Appendix A. In one line:
  - the dev headline (the matched-trigger pair) is now registered on test as **P6, primary**, with its
    decomposition as **P7**;
  - every planner-involving arm replays **arm 3's** first plan packet, as every dev arm did;
  - multiplicity, seeds, crash handling and the boundary-stability rule are specified exactly.

**Gate assertion at time of writing**: the AppWorld `test_normal` split has **not** been read, loaded,
listed, or evaluated by this project, and no file under any `test_normal` or `test_challenge` path has
been opened. Every number in this document is a dev measurement.

**Authorisation**: the user authorised the J10 test read and signed off J9 §8.1 explicitly (r1, header date
2026-09-24), in response to a cost and irreversibility statement quoting r1's figures. r2 raises the registered
hosted budget (§9); the user's freeze of r2 is the authorisation of that budget.

**Dev basis**: `campaign/results/j10_a1_registered_dev_basis_20260924.report.json` (seven arms, `n_pairs = 114`,
`dropped_crash = 0`) for P1–P3 and P5; the pooled three-seed report
`campaign/results/j15_pooled_cap81_3seed_20260924.report.json` (171 pairs) where it exists; the C1 and B2
reports for P6–P7. Every dev value below names its report key **in the orientation the key stores**, and says
so when the registered orientation is the reverse (F4).

---

## 1. Why this amendment exists

The J9 freeze registered a five-arm J10 built around **Claim F1: selective escalation** — does a learned
self-gate or sequential router spend planner calls better than a fixed review schedule? Its arm list was
`executor_alone`, `sft_plan`, `fixed_k_10`, `fixed_k_5`, `sidekick_tau05`
[OBSERVED docs/prereg_j9_freeze_20260920.md:136-144].

Two things happened after that freeze.

**First, J9 itself already recorded the null.** Its §6 claim 4 states that neither the linear verifier head
nor the sequential router discriminates outcome-critical intervention points (scored AUROC 0.3867–0.5082),
and that the executor self-gate's $p_{\text{ask}}$ never exceeds 0.0347 against thresholds of 0.3, 0.5 and
0.7. `sidekick_tau05` was registered only as a "pre-registered check that the self-gate remains
degenerate" [OBSERVED docs/prereg_j9_freeze_20260920.md:143]. The paper reports this null (§7 item 5).

**Second, dev work established a different and much larger effect.** The project's reportable finding is
now a **channel** result: help delivered to the executor as an *executed action* outperforms the same
planner's help delivered as *prose advice*. It appears in two forms on dev:
- **at a matched trigger:** the planner reviews every 10 steps and either takes over or advises — CHAN-C1-02;
- **at adverse budget:** a replayed action prefix beats advice given at every step — CHAN-PRICE-01.

None of the five registered J10 arms measures either. `planner_alone` — needed both as the ceiling and as the
source of the prefix trajectories — was explicitly **dropped** from J10 to protect quota
[OBSERVED docs/prereg_j9_freeze_20260920.md:§5.2 item 1].

Running the registered arm list would spend the project's single, non-repeatable test read on a hypothesis
already known to be null on dev, and would not test the effect the paper reports.

**This amendment is honest about its own timing.** It is written *after* the dev results were known and
*before* any test observation exists. That is the only sense in which any preregistration is ever "pre":
it binds the analysis to a specification fixed before the data are seen. Readers should judge it on
whether the predictions below are falsifiable and were fixed before the read — not on whether the
hypothesis was chosen in ignorance of dev. It was not, and no preregistration claims otherwise.

---

## 2. What this amendment supersedes

| J9 section | Status under A1 |
|---|---|
| §4, Claim F1 (selective escalation) as the J10 primary | **Superseded.** Demoted to a dev-only negative result, reported as such. |
| §5.1, the five-arm J10 list | **Superseded** by §4 below. |
| §5.2 item 1, dropping `planner_alone` | **Reversed.** Reinstated as ceiling, trajectory source and plan-packet source. |
| §9.1, three seeds | **Amended** to two seeds; rationale in §5.1. |
| §9.2, task-clustered bootstrap, 10,000 resamples | **Retained**, extended with scenario clustering (primary). |
| §6, the dev-evidence claim ordering | **Retained** as a record of what was believed at J9. |
| §8.1, the sign-off gate | **Satisfied**; see the authorisation note above. |

Everything in J9 not listed here stands unchanged. J9 is not edited.

---

## 3. The hypotheses

**H-A1 (primary, at adverse budget).** For a fixed frozen hosted planner and a fixed local executor, the
*channel* through which planner help reaches the executor determines outcome quality, and the advantage of
the action channel is not explained by the amount of planner compute spent. An executor given the planner's
first 11 recorded actions as an executed prefix outperforms the same executor advised in prose by the same
planner at every step, **despite the advice arm spending strictly more hosted budget**.

**H-A1b (primary, at a matched trigger).** At the same review schedule (every 10 steps) and the same
context, the planner's help delivered as an **executed action** (takeover) beats the same planner's help
delivered as **prose advice**.

**H-A1c (the decomposition, registered in P7 once B2 lands).** H-A1b's contrast bundles three
differences:
- the prompt wording (the advice prompt presumes an error and asks for concise text);
- the content (code vs prose);
- the delivery (executed vs shown).

`docs/prereg_c1_decomposition_20260923.md` (frozen, dev) separates them. A1 registers on test whichever
separation B2 shows to be decisive.

These are claims about *form*, not *quantity*: H-A1's budget asymmetry favours the advice arm, and H-A1b holds
the trigger and the context fixed.

---

## 4. Registered arm list for J10

Split: AppWorld **`test_normal`**, 168 tasks [OBSERVED docs/prereg_j9_freeze_20260920.md:208].
Seeds: $s \in \{1, 2\}$. **336 paired episodes per arm.**

| # | Arm | Receiver | Planner role | Live hosted calls/ep (dev) | On test |
|---|---|---|---|---:|---:|
| 1 | `executor_alone` | base granite, `lora_name: null` | none | 0 | **0** |
| 1b | `executor_alone_bplus` | `sft_b_plus` | none | 0 | **0** |
| 2 | `sft_plan` | `sft_b_plus` | arm 3's first plan packet, replayed | 0 | **0** |
| 3 | `planner_alone` cap-81 | n/a (planner drives) | acts every step to completion | 17.35 | **5,830** |
| 4 | `prefix_m9` | `sft_b_plus` | replay of arm 3, first 9 actions | 9.77 attributed | **0 marginal** |
| 5 | `prefix_m11` | `sft_b_plus` | replay of arm 3, first 11 actions | 11.25 attributed | **0 marginal** |
| 6 | `prefix_zs_m9` | base granite | replay of arm 3, first 9 actions | 9.77 attributed | **0 marginal** |
| 7 | `prefix_zs_m11` | base granite | replay of arm 3, first 11 actions | 11.25 attributed | **0 marginal** |
| 8 | `advise_k1_fullctx` | `sft_b_plus` | arm 3's plan, then full-context prose advice every step | 19.02 | **6,391** |
| 9 | `advise_k10_fullctx` | `sft_b_plus` | arm 3's plan, then full-context prose advice every 10 steps | 2.46 | **827** |
| 10 | `takeover_k10` | `sft_b_plus` | arm 3's plan, then the planner executes its own action every 10 steps | 2.32 | **780** |
| 11 | `show_k10` *(P7; confirmed at freeze)* | `sft_b_plus` | as arm 10, but the action is shown as advice text, never executed | ≈2.32 (B2) | **≈780** |
| 12 | `advise_k10_neutral` *(P7; confirmed at freeze)* | `sft_b_plus` | as arm 9, with the neutral advice prompt | ≈2.46 (B2) | **≈827** |

**Arm 9 is no longer droppable** (R1). It is one half of the P6 pair.

**Arms 11 and 12** are registered, or struck, at freeze by the rule in §6 P7. A struck arm is removed from this
table before the status line changes. No arm may be added after freeze.

**Receivers.** Every `sft_b_plus` arm serves one adapter:
`/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b`, launched as
`--lora-modules sft_b_plus=<that path>` and pinned by `j10_arm.pbs` (F8).

It is the adapter every tailored dev arm behind P1, P3, P5 and P6 actually loaded. That includes the
`sft_plan` floor, whose script default names a different adapter but whose submission overrode it:
- [OBSERVED campaign/workers/logs/hj8_frontier_live_20260921iaware.25580034.aqua.out:106];
- [OBSERVED campaign/workers/logs/hj12_live_live_20260923.25699995.aqua.out:226];
- and the H2 and prefix launch lines (adapter trace, 2026-09-23).

No dev contrast registered here paired arms with different adapters.

Arms 1 and 1b differ only in the adapter. Arm 1 is the zero-shot floor and arm 1b the tailored floor, so "no
plan" and "no tailoring" are separated (R4).

### 4.1 One planner run feeds every arm

Arm 3 is the only arm that generates plans. Every other planner-involving arm **replays its artifacts**:

- **Arms 4–7** re-execute the first $m$ of arm 3's recorded actions on a fresh world, then hand off.
- **Arms 2 and 8–12** replay arm 3's **first plan packet** for the same `(task_id, seed)`
  (`planner.packet_source` = arm 3's campaign, `on_missing: fail`). Their live hosted calls are only
  reviews, advice, takeovers or shown actions.

This is the dev design, carried to test **(F1)**. Every dev arm behind P1, P5 and P6 replayed one recorded
plan per `(task_id, seed)`, so plan-sampling noise cancelled out of every paired contrast
[OBSERVED configs/hj12_prefix_m11.yaml:22-24, campaign/results/hj13_advice_at_price_20260923.report.json
`packet_source`]. r1's live-arm configs drew a fresh plan per arm on test, which would have reintroduced that
noise into P1 and P5 on test only. A first plan packet does not depend on the call cap, so arm 3's cap-81 run
serves as the source exactly as the cap-25 campaign `hj1b_planner_20260915` did for seeds 1–2 on dev, and the
cap-81 seed-3 campaign did for seed 3.

⚠ **Prefix sourcing is a deliberate change from the headline dev prefix arms.** The first published dev prefix
curve replays the **cap-25** planner campaign [OBSERVED configs/hj12_prefix_m11.yaml:7]. On test, one planner run
must be generated, and using the **same** run for both the ceiling and the prefix source is the only way the
non-inferiority comparison is like-for-like. Re-measured on dev with cap-81-sourced prefixes:

| contrast | cap-25 sourced | cap-81 sourced, 114 pairs | cap-81 sourced, 171 pairs |
|---|---|---|---|
| untailored m11 vs the cap-81 ceiling | −7.08 pp, CI **excludes** zero | ceiling − zs_m11 −2.95 pp, [−8.65, +1.91] | ceiling − zs_m11 −1.94 pp, [−6.40, +2.17] |
| untailored depth m9 → m11 | +4.99 pp | +2.82 pp, [−1.55, +7.16] (negated key, F4) | **+1.44 pp, [−2.56, +5.52]** |
| tailored m11 arm mean | 0.809825 | 0.811149 | — |

The 171-pair values come from `j15_pooled_cap81_3seed_20260924.report.json`
(`contrasts.ni_ceiling_minus_zs_m11`, `contrasts.zs_depth_m9_m11`; scenario-clustered, seed 20260924).

So the striking dev claim that an untailored prefix *significantly beats the planner that would have produced
it* is **sourcing-dependent**. A1 registers the conservative, like-for-like design and states this correction
in the paper.

---

## 5. Statistical protocol

### 5.1 Design and power

- 168 tasks × 2 seeds = **336 paired episodes per arm**, against 114 (or 171) on dev.
- **Two seeds, not J9's three.** This is a deliberate registered deviation from J9 §9.1, taken for cost and
  disclosed in the paper.
  - 336 pairs already narrows intervals by roughly $\sqrt{336/114} \approx 1.7\times$ relative to dev.
  - A third seed would cost a further ~50% of hosted budget to narrow them by a further $\sqrt{3/2} \approx 1.22\times$.
- All contrasts are **paired** on `(task_id, seed)`, and every contrast is computed **in its registered
  orientation** (left − right as written), never by negating a stored reverse contrast (F4).
- **Scoring.** An episode's score is the environment's evaluation as recorded in `result.json`:
  - `goal_pass` = the fraction of AppWorld's checks passed;
  - TGC = 1 if all passed.

  Every `error_type` other than `crash` (`limit`, `timeout`, `parse_error`, `api_error`) is an outcome of
  the arm and is scored as recorded. A `crash` still present at analysis removes that pair from every
  contrast, and the arm is then **incomplete** (§9 F6). A `timeout` is a permanent scored failure under this
  rule, and per-arm counts of every error type are reported (§7).

### 5.2 Estimation

- Paired percentile bootstrap, **10,000 resamples**, through `scripts/analysis/j10_report.py` (the A1
  protocol, matching `j8_frontier.py`/`hj1_gate.py` draw for draw).
- **Two clusterings for every contrast.** Scenario clustering (`scenario_of(task_id)`) is primary and
  governs every decision rule; task clustering is secondary. The number of scenario clusters on
  `test_normal` is reported as found.
- Bootstrap seed **20260924**, fixed here before the read.
  - The dev reference values quoted in §6 were computed at the dev reports' own seed (20260915, `hj1_gate.SEED`)
    unless marked, and are descriptive only (F2).
  - Example: P1's dev scenario interval is [−21.20, −7.96] at 20260915 and [−21.11, −7.88] at 20260924.
- Primary metric **`goal_pass`**; secondary metric **TGC**. TGC is binary per episode, so its percentile bounds
  sit on discrete atoms. A TGC bound that equals its threshold's nearest atom is reported as such, not as a pass
  or fail by a hair.
- **Marginal per-arm intervals are not reported beside paired contrasts** and appear in no decision rule.

### 5.3 Multiplicity (F3)

- **The Holm family** is every registered `goal_pass` prediction whose *support* requires rejecting a null:
  **P1, P3, P4, P6**, plus each registered component of **P7** — at most $m = 6$.
- Each member's p-value is the **two-sided-equivalent percentile-bootstrap p** at its threshold, from the same scenario-clustered bootstrap as its interval (`j10_report.bootstrap_pvalue`). **P3, P4 and P7's components**, which register no reversed outcome, use $2 \times$ the share of resampled means on the wrong side of the threshold (`direction="greater"`).
  **P1 and P6** register a *reversed* outcome, so they use $2 \times$ the smaller tail at 0 (`direction="two-sided"`). One p then serves both readings, and a reversal enters the Holm family with the same evidence standard as a confirmation.
  The two forms are equal whenever the point estimate lies on the predicted side. They differ only for an effect that points the wrong way, and for such an effect only the two-sided form can support claiming a reversal.
- Holm step-down is applied at family-wise $\alpha = 0.05$. An interval condition in a decision rule
  ("CI excludes zero", "lower bound above −7.00") counts as met only if the unadjusted 95% interval meets it
  **and** the Holm-adjusted p is ≤ 0.05. Both verdicts are reported.
- **P2 is not in the family.** It is a cost predicate, evaluated on point values, with the ratio's
  scenario-clustered interval reported beside it.
- **P5 is not in the family.** Its *support* is the absence of a significantly positive effect, so a Holm
  adjustment would make it **easier** to support. P5's "significantly positive" event is evaluated on the
  **unadjusted** 95% interval, which is the conservative direction for P5.
- Exploratory contrasts are reported unadjusted and labelled exploratory. **No exploratory contrast may be
  promoted to a claim after the read.**

### 5.4 Boundary stability (R3 — the POOL-04 rule)

Any decision-bearing interval bound within **1.00 pp** of its threshold (0 or −7.00) is recomputed with the
identical estimand, episodes and B = 10,000 at bootstrap seeds **{20260924, 1, 2, 3, 7, 101, 999}**, and at
200,000 resamples at 20260924.

- **If the verdict differs on any of the seven seeds**, the prediction is reported as **"on the boundary"** with
  the seven bounds and the 200k bound, and is **never** reported as supported or not supported.
- This rule was adopted on dev, where a 0.15 pp lower bound flipped on 1 of 7 seeds (`docs/claims_ledger.md`
  POOL-04), and a published +0.01 pp bound was negative on 6 of 7 (ROB-04). It is registered here so that
  applying it after the read cannot look like a rescue. It applies in both directions.

### 5.5 Small-cluster sensitivity (R7)

Beside every P-verdict, the report gives the **cluster sign-flip permutation p**:
- exact if the scenario count gives ≤ $2^{20}$ sign patterns;
- otherwise Monte Carlo over 100,000 patterns at seed 20260924;
- one-sided at the threshold for P3.

It is **not decision-bearing**. A disagreement between it and the bootstrap verdict is reported in the same
sentence as the verdict.

---

## 6. Registered predictions and decision rules

All intervals are 95% and scenario-clustered unless marked.

### P1 — PRIMARY. The channel effect survives at adverse budget.

`advise_k1_fullctx − prefix_m11` on `goal_pass` is **negative with a CI excluding zero** (Holm family).

Dev (114 pairs): **−14.81 pp**, scenario **[−21.20, −7.96]**, task [−21.73, −8.02]; TGC −14.91, scenario
[−27.19, −2.63] [key `contrasts.goal_pass_all_advise_k1_minus_c81_bp_m11`, registered orientation].

- **Supported** — negative, excluding zero → H-A1 holds on test.
- **Not supported** — the CI includes zero → the at-price claim is withdrawn and reported as failing to
  replicate at $n = 336$. No reinterpretation, no subgroup rescue, no switch to TGC as the primary.
- **Reversed** — positive, excluding zero → withdrawn outright; the reversal is reported as a primary finding.

### P2 — PRIMARY. The budget asymmetry is real and runs against the prefix arm.

`advise_k1_fullctx` spends **at least 2× the non-cached planner tokens** of `prefix_m11` per episode, and
strictly more hosted calls per episode. Point values; not in the Holm family.

Dev: **3.19×** tokens (1,414,410 vs 443,361 per episode), with scenario interval **[2.47, 4.06]** (ROB/F-f), and
**19.02 vs 11.25** hosted calls/ep [OBSERVED campaign/results/hj13_advice_at_price_cost_20260923.report.json:
`arms.advise_k1_fullctx.noncached_tokens_per_episode`, `arms.prefix_m11.noncached_tokens_per_episode`].

The prefix arm is charged **the planner calls required to produce its prefix** — the replayed plan and actions
(11.25 calls/ep at m = 11) — not zero and not arm 3's full 17.35. The cost report is run with
`j12_cost_axes.py --packet-source` pointed at arm 3's campaign (F9).

⚠ **Registered correction to a dev mis-specification.** The dev prereg
(`docs/prereg_h2_advice_at_price_20260923.md`) specified this predicate as an absolute band of [300k, 700k]
non-cached tokens. The observed 1.41M failed it *upward*: advice was even more expensive than registered
(CHAN-PRICE-02). A1 replaces the band with the **relative** predicate above, which is what the hypothesis
requires.

- **Supported** → the "it just bought more compute" objection is closed on test.
- **Not supported** — under 2× → P1 is **uninterpretable as a channel result** and is reported as a
  budget-confounded comparison, whatever its sign.

### P3 — SECONDARY. The tailored prefix is non-inferior to the hosted planner acting alone.

`prefix_m11 − planner_alone_cap81` on `goal_pass` has a **lower bound above −7.00 pp**, the margin carried
unchanged from J9 (Holm family; p one-sided at −7.00, two-sided-equivalent). Computed on **all** episodes of
both arms.

Dev, stored as **ceiling − arm** (the registered orientation is the reverse):
- 114 pairs: −4.75 pp, [−11.75, +1.16] [key `contrasts.goal_pass_all_ceiling_c81_minus_c81_bp_m11`];
- 171 pairs: **−4.41 pp, [−10.66, +0.74]** [`j15_pooled_cap81_3seed_20260924.report.json`
  `contrasts.ni_ceiling_minus_t_m11`, seed 20260924].

The dev upper bounds (+1.16, +0.74) sit 5.8 and 6.3 pp inside the +7.00 margin.

- **Supported** → an 8B local executor replaying 11 recorded actions matches a hosted planner that acts every
  step to completion at up to 81 calls.
- **Not supported** → reported as a failure of non-inferiority at the registered margin. **P1 and P6 do not
  depend on P3.**
- The **limit-excluded** variant (dropping episodes where the ceiling hit its call cap) is reported only as a
  sensitivity, with the caveat measured on dev: exclusion selects on the reference arm's own failures. On the
  cap-81 ceiling, the 18 dropped episodes scored 0.179 against 0.873 for the 96 kept [OBSERVED
  campaign/results/j16_robustness_20260923.report.json
  `F_e_ni_both_ceilings.selection_induced_by_limit_exclusion.cap81.per_arm.ceiling_cap81`].

### P4 — SECONDARY, registered as unresolved on dev. Depth helps an untailored receiver.

`prefix_zs_m11 − prefix_zs_m9` on `goal_pass` is **positive** (Holm family for "supported").

Dev:
- 171 pairs, registered orientation: **+1.44 pp, [−2.56, +5.52]** [`j15_pooled_cap81_3seed_20260924.report.json`
  `contrasts.zs_depth_m9_m11`, seed 20260924];
- 114 pairs, stored reversed: `c81_zs_m9 − c81_zs_m11` = −2.82 pp, [−7.16, +1.55]
  [key `contrasts.goal_pass_all_c81_zs_m9_minus_c81_zs_m11`] (F4: r1 quoted its negation without saying so).

The 171-pair point is half the 114-pair one, so this prediction is registered **knowing dev does not resolve it
and that the effect may be small**. Test carries about 1.4× the 171-pair power.

- **Supported** — positive, excluding zero → depth helps a receiver with no tailoring confound.
- **Directionally consistent** — positive, CI includes zero → unresolved at 171 and 336 pairs; no claim.
- **Not supported** — a point estimate ≤ 0 (F7: exactly 0 is not positive) → the depth effect is not shown
  for an untailored receiver.

### P5 — SECONDARY. Prose advice does not beat a single up-front plan.

`advise_k1_fullctx − sft_plan` on `goal_pass` is **not positive with a CI excluding zero**, judged on the
unadjusted interval (§5.3). On test both arms replay arm 3's plan packet, so the contrast is advice versus
no advice on an identical plan.

Dev: **−5.51 pp**, [−13.15, +2.51]; exact sign-flip p = 0.196 [OBSERVED
campaign/results/hj13_advice_at_price_20260923.report.json:
`contrasts.goal_pass_all_advise_k1_fullctx_minus_plan_floor`; ROB-03].

- **Supported** → the advice channel is flat in its own budget.
- **Not supported** — advice significantly beats the plan floor → P1's interpretation narrows to "the action
  channel is better at equal budget", not "prose advice does not convert budget into quality".

### P6 — PRIMARY. The action channel beats prose advice at a matched trigger (R1).

`takeover_k10 − advise_k10_fullctx` on `goal_pass` is **positive with a CI excluding zero** (Holm family).
Both arms replay arm 3's plan packet, review at the same steps, and see the same context. They differ in what
the planner is asked for and what the executor receives.

Dev (114 pairs, CHAN-C1-02, registered orientation): **+6.69 pp, [+1.29, +13.49]**. The ledger's 13.48 is the
reversed contrast's bound negated; one order statistic apart (F4). Exact scenario sign-flip p = 0.047; wild
cluster bootstrap [+0.88, +12.48] (ROB-02). **[171-pair value from B1 inserted at freeze.]**

- **Supported** → H-A1b holds on test. With P1 this is the paper's headline: the channel result holds at a
  matched trigger and at adverse budget.
- **Not supported** — the CI includes zero → the matched-trigger claim is reported as failing to replicate.
  It is **not** rescued by P7 or by TGC.
- **Reversed** → withdrawn; the reversal is reported as a primary finding.

⚠ P6 tests the dev contrast **as built**, including its prompt asymmetry. What P6 means is settled by P7.
Without P7, a supported P6 licenses "the takeover arm beats the advice arm", not "execution beats prose".

### P7 — the decomposition of P6 (R6). **Completed at freeze from B2; until then this section is a template.**

B2 (`docs/prereg_c1_decomposition_20260923.md`, frozen before any B2 episode) runs four arms on dev at
171 pairs:
- T = takeover;
- A = advice;
- S = shown action (arm 11): the byte-identical act prompt, output shown and never executed;
- N = neutral-prompt advice (arm 12).

Its outcome rules, evaluated in order:
1. **prompt artefact** — N closes the gap to T;
2. **execution matters** — T − S > 0, excluding zero;
3. **content, not execution** — T − S includes zero and S − A > 0, excluding zero;
4. otherwise **unresolved**.

At freeze, the user and orchestrator complete P7 from the B2 outcome, by this rule fixed now:

| B2 dev outcome | arms registered on test | P7 prediction(s), in the Holm family |
|---|---|---|
| execution matters | 11 | **P7a**: `takeover_k10 − show_k10` > 0, CI excluding zero |
| content, not execution | 11 | **P7b**: `show_k10 − advise_k10_fullctx` > 0, excluding zero; **P7a** reported as a registered secondary with "includes zero" as its predicted outcome |
| prompt artefact | 11, 12 | **P7c**: `takeover_k10 − advise_k10_neutral` includes zero (support = non-rejection, so evaluated like P5 and outside Holm); **P7a** as above |
| unresolved | 11, 12 | **none registered**; arms 11 and 12 run as exploratory, and the paper says the decomposition was unresolved on dev |

Each P7 prediction's dev value and interval are written into this section at freeze, from the B2 report, with
its key.

---

### Supporting contrasts, registered but not decision-bearing

| contrast | dev | scenario CI | source |
|---|---:|---|---|
| `advise_k1 − prefix_m9` | −9.89 pp | [−17.79, −1.99] | dev basis |
| `advise_k10 − prefix_m11` | −7.73 pp | [−12.60, −3.12] | dev basis |
| `prefix_m11 − prefix_m9` (tailored depth) | +4.25 pp (171) | [+0.15, +8.75], **on the boundary** (POOL-04) | j15 `t_depth_m9_m11` |
| `(m11 − m9)_tailored − (m11 − m9)_untailored` (R2) | +2.81 pp (171) | [−2.57, +8.96] | POOL-03 |
| `prefix_m11 − executor_alone_bplus` (tailored floor → m11) | new arm | — | arm 1b |
| handoff-only depth: m9 → m11 restricted to episodes where a handoff occurs at m = 11 | reported for both receivers | — | F-c |

R2: the tailoring × depth interaction is **pre-specified** here, so reporting it after the read is not
exploratory. It is **not decision-bearing**. The dev evidence is a sign disagreement between planner samples at
114 pairs (DID-02: cap-25 −2.53, cap-81 +2.10) and a null at 171. r1 said no difference-in-differences had been
run; that was true when r1 was written and is not true now (DID-01/02, POOL-03).

---

## 7. What is reported regardless of outcome

1. All arms' means with pair counts, both metrics, and every arm's `error_type` distribution.
2. All pairwise contrasts among registered arms, both clusterings, Holm-adjusted within the family and
   unadjusted elsewhere with the label attached.
3. The cost table: hosted calls, non-cached tokens and USD per episode per arm, each paired difference with
   its interval. The prefix arms' attributed source cost is shown explicitly, not as zero.
4. Every arm that crashed, was silenced, or lost pairs, with counts. Separately, the number of prefix episodes
   in which **no handoff occurred** (arm 3 finished within m actions), per depth. At m = 11 on dev this was
   about half the episodes, so the depth result is reported both over all episodes and over handoff-occurred
   episodes.
5. The J9 Claim F1 negative, as a dev-only result, with its AUROC range.
6. The sourcing correction in §4.1, whether or not it helps the paper.
7. SGC (a scenario-seed unit passes only if all its variants pass) for P1 and P6, descriptive.
8. The provenance statement of §9.1: the model id requested, the CLI version, and the fact that the served
   model is not observable.

---

## 8. One read, and what happens if it goes wrong

This is the project's **single** test evaluation. Registered now, so that no post-read judgement call is
unconstrained:

- **No second read for a better number.** If the campaign completes, its numbers are the reported numbers.
- **A bug discovered after the read** does not license a silent re-run. Any re-run is disclosed in the
  paper as a post-read re-run, with the defect, the date and both sets of numbers. A re-run result is
  **not** reported as a clean preregistered outcome.
- **A crashed or quota-truncated campaign may be resumed** to completion. Resumption fills unwritten or
  crashed episodes and is not a re-read. It never overwrites a `result.json` whose `error_type` is anything
  other than `crash` (F5).
- **`test_challenge` is not read.** It remains unread and out of scope under this amendment.
- **No arm is added after freeze.** Arms 1–12, as finalised at freeze, are the complete list.

---

## 9. Cost, order, and authorisation record

| item | value |
|---|---|
| Arm 3 (`planner_alone` cap-81) | **5,830** |
| Arm 8 (`advise_k1_fullctx`) | **6,391** |
| Arms 9 + 10 (the P6 pair) | **1,607** |
| Arms 11 + 12 (P7), if registered | **≤ 1,607** |
| Arm 2 and every other arm | 0 (replay) |
| **Registered total** | **13,828**, and **≤ 15,435** with arms 11 and 12 |
| Measured basis | dev live-call rates per episode with the plan packet replayed, as on test |
| Quota observed | ~5,000 calls per plan window (§10.1), so **≥ 3 windows** |
| Billing | ChatGPT-plan subscription, `gpt-5.6-luna`, no per-token billing |
| Authorised by | user: r1's read and J9 §8.1 (r1, header date 2026-09-24); r2's budget by freezing r2 |

**Order (R5; luna-6 deprecation risk).** A newer luna exists, and `gpt-5.6-luna` may be withdrawn during the
read. Replay arms are immune; live arms are not. So:
1. arm 3 first;
2. then arms 8, 9 and 10 in consecutive windows;
3. then arms 11 and 12;
4. then the GPU-only arms 1, 1b, 2 and 4–7.

**Abort rule.** J10 is **reported as not run** — never at reduced power — if arms 3, 8, 9 or 10 cannot
complete 336 non-crashed pairs (for example because the model is withdrawn or quota never returns). P7's arms
are abandoned only as a pair and then reported as not run, while P1–P6 stand.

### 9.1 The planner is pinned, and what that can and cannot guarantee (R5)

- **Pinned model.** Every hosted arm requests `gpt-5.6-luna` and nothing else: the config pins it, and the
  wrapper refuses any other model and any codex planner without it.
- **Pinned CLI.** The codex CLI version is pinned at **0.153.4** (as measured 2026-09-23); it is written here
  at freeze and passed to `j10_arm.pbs` as `EXPECTED_CODEX_VERSION`. No CLI upgrade between the dev dry run and
  the last hosted arm.
- **No substitution.** If `gpt-5.6-luna` is withdrawn, J10 is not run on a later model.
- **Recorded in provenance.** Every episode records `planner_model_requested` and `planner_cli_version`.
- ⚠ **The model that actually served a call is not observable.** Neither the `codex exec --json` stream nor the
  session transcript carries a server-reported model id
  (`campaign/results/a5_served_model_probe_20260923.md`). The no-substitution rule is therefore enforced on
  the request side only. This is stated in the paper's limitations.

---

## 10. Implementation notes (not part of the registration)

- **Wrapper.** Submit every arm through `scripts/pbs/j10_arm.pbs` (the configs' comments pointing to a
  `j10_test.pbs` are stale; F9). The wrapper:
  - passes `--split test_normal` itself;
  - resumes with `campaign_summarize.py --purge-crashed-only` — **never `--purge-broken`**, which also deletes
    scored `timeout`/`parse_error`/`api_error` episodes (F5);
  - checks the split with `--expect-split` on the first arm, before the others start.
- **Configs.** Every arm needs a config with campaign id `j10_<arm>_20260924` and no `split:` key.
  - Arms 2 and 8–12 carry `planner.packet_source` = arm 3's campaign, with `on_missing: fail` and a
    `packet_source_pending` note until arm 3 exists (F1).
  - Arms 4–7 carry `handoff.source_campaign` = arm 3's campaign.
  - `j10_prefix_m9.yaml` and `j10_prefix_m11.yaml` gain `env: appworld` (F9).
  - Arms 1b, 10, 11 and 12 need new configs derived from `hj8_executor_alone_bplus`, `hj12_takeover_fixed_k_10`
    and the two B2 configs.
- **Phantom alias.** Any arm without a tailored adapter must set `lora_name: null`, and never inherit an alias
  that is not served [OBSERVED src/sidekick/policies/sft_plan.py:18].
- **Ordering.** Arm 3 must complete before any other planner-involving arm starts, since all of them replay
  it. Arm 3 needs no GPU; the others need a vLLM server.

### 10.1 ⚠ The campaign cannot run as a single job

Measured 2026-09-22. The hosted planner authenticates through a ChatGPT plan whose quota window is
**invisible to a batch job**: `codex exec` reports no `rate_limits`. When the window is exhausted, episodes
fail at **step 0** as `CodexExecError` (recorded as `crash`) with `planner_tokens_total: 0`, and **the PBS job
still exits 0**. Job 25713123 wrote 57 result files, 47 of them crashed this way, and reported `rc_full=0`.

About 5,000 planner calls exhausted a window that day. Consequences for the run, none of which touch the
registration:

- Each arm is submitted **repeatedly**. `--purge-crashed-only` plus the runner's skip-if-`result.json`-exists
  behaviour fill only crashed or unwritten episodes. Under §8 this is **resumption, not a re-read**. The
  wrapper exits 3 while crashes or missing episodes remain.
- **No arm is scored from a job's exit code.** An arm is complete only at 336 non-crashed pairs, checked by
  count and `error_type`.
- A cheap interactive codex call shows the current limit state and reset time. Check it before each
  submission, and record each window's reset time so the weekly cap becomes a measured number.
- Budget wall-clock in **days, not hours**.

### 10.2 ⚠ Correction to §10, appended 2026-09-23 (r1): the split is a CLI argument, not a config field

r1's §10 stated that each registered arm "needs a config with `split: test_normal`". **That was wrong. Acting
on it would have run the entire confirmatory campaign on the dev split while every campaign id, log line and
report said test.**

`--split` is a command-line argument of `src/sidekick/runner.py`, with `default="dev"`, and it reaches the task
loader only through the runner's arguments. No configuration file carries a `split:` key, and the runner never
reads one. A `split: test_normal` line in a YAML config is **inert**: the campaign silently evaluates the first
*n* **dev** tasks.

**What is registered does not change.** Required instead:
1. Every runner invocation of J10 passes `--split test_normal` explicitly, including the smoke slice. A J10
   config must **not** contain a `split:` key.
2. Before any arm is analysed, its observed `task_id` set is intersected with the dev task list; **any overlap
   is fatal**.
3. That check runs as a gate on the first arm submitted, so a mistake costs one arm, not the campaign.

---

## Appendix A — what r2 changed, and why

| id | change | source |
|---|---|---|
| R1 | Arm 10 `takeover_k10` added; arm 9 made non-droppable; **P6** registered, primary | plan §3; the dev headline was not on test |
| R2 | The tailoring × depth DiD registered as a supporting contrast, with its 171-pair value | plan §3; DID-01/02, POOL-03 |
| R3 | The POOL-04 boundary-stability rule registered (§5.4) | POOL-04, ROB-04 |
| R4 | Arm 1b, the tailored floor, added | plan §3 |
| R5 | Model pin, CLI pin, no substitution, hosted-first order, served-model limitation (§9, §9.1) | plan §2; A5 probe |
| R6 | P7 template and the rule that completes it from B2 | plan §1.1; prereg_c1_decomposition |
| R7 | The cluster sign-flip p as a sensitivity (§5.5) | plan §1.4; ROB-01..08 |
| F1 | All planner-involving arms replay arm 3's first plan packet (as on dev); arm 2 costs 0 | found drafting r2: r1's live configs broke the dev design |
| F2 | Dev reference seed stated (20260915) against the test seed (20260924) | A4 review |
| F3 | Holm family defined exactly; P2 and P5 outside it, and why; how p and CI rules combine | A4 review |
| F4 | Every dev value quoted with its stored orientation; P6's upper bound 13.49 not 13.48; P4's silent negation fixed | A4 review |
| F5 | `--purge-crashed-only` replaces `--purge-broken`; resumption never overwrites a scored episode | A4 review |
| F6 | A residual crash drops the pair and leaves the arm incomplete | A4 review |
| F7 | P4 with a point estimate of exactly 0 is "not supported" | A4 review |
| F8 | The adapter directory is named and pinned at freeze | A4 review; adapter trace |
| F9 | Stale `j10_test.pbs` pointers; missing `env:` keys; the P2 cost report's packet source | A4 review |

*Amendment A1 ends. J9 remains frozen and unedited.*
