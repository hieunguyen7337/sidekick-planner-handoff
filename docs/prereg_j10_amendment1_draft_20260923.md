<!-- DRAFT FILE. Everything below the "BEGIN APPENDED TEXT" marker is appended verbatim, after one blank
line, below A1's end marker (docs/prereg_j10_amendment_20260924.md:679) when the user freezes it. This
comment and the markers are not appended. The appended text contains no line that starts with the
Status field marker, so j10_arm.pbs's single-Status-line gate still passes. -->
<!-- BEGIN APPENDED TEXT -->
## Amendment 1 — pre-data additions after the adversarial review (2026-09-24, appended before any `test_normal` episode; no arm, no P1–P6 prediction, rule, threshold or Holm family, and no margin, bootstrap seed, order, budget or abort rule above the end marker changes)

Frozen on commit, 2026-09-24, by Claude on the user's instruction of that day ("The freeze should have been
approved"). Drafted 2026-09-23 as `docs/prereg_j10_amendment1_draft_20260923.md`; the text below is that draft,
appended verbatim. The `j10_report.py` code that computes every item below is committed with or before this
amendment and is tested on fixtures with hand-computed answers.

### A. Why, and what was known when this was written

- **Trigger.** An adversarial review of the dev paper (`docs/review_paperA_adversarial_20260923.md`, commit
  968fd7b) found three things this registration does not address:
  1. at m = 11, most prefix episodes never hand off, so an all-episode contrast of a prefix arm is largely the
     planner's own trajectory;
  2. the P6 gap sits mostly in episodes that hit the 40-step limit, and a neutral advice prompt recovers about
     three-fifths of it;
  3. H2's frozen rule for a failed P4 constrains how P1 may be described.

  The fix plan is `docs/plan_review_fixes_20260923.md` (commit 9b5ec6a).
- **No test data exist.** At the commit of this amendment, the only `j10_*` campaigns are the 13 dev dry-run
  campaigns ending `_dryrun` (3 dev tasks × seeds 1–2 each). No arm has run on `test_normal`.
- **Chosen in view of dev.** Everything below was chosen with the dev values it quotes already known. That is
  why each registered item states its dev value and its power at the test design.
  - Power comes from `campaign/results/am1_power_dev_20260923.report.json`, commit 9b5ec6a.
  - Method: dev scenarios resampled to 56 scenarios × 2 seeds; the registered analysis applied to each
    simulated read; 1,000 reads, 2,000 bootstrap draws each.
  - Power is reported at the dev effect and at half of it. Half is the honest planning value for an effect
    chosen after being seen.
- **Nothing above the end marker is edited.** Where this amendment extends §6's supporting table or §7, it adds
  rows; it does not replace any.

### B. The handoff-only population (pre-specified; not decision-bearing)

**Why.** On dev, `handoff_occurred = false` holds in 100 of the 171 pooled cap-81 tailored m = 11 episodes:
arm 3's trajectory finished inside the prefix. An all-episode non-inferiority contrast at m = 11 therefore
compares the planner with itself on most pairs.
- P3's all-episode power is 1.00.
- Restricted to the 71 episodes that hand off, P3's contrast on dev is **−0.94 pp [−9.51, +7.26]**, which
  already fails the −7.00 margin. Its power at the test design is 0.58.

Registered, in addition to §7 item 4:

- **B1. Handoff-only non-inferiority.** Two contrasts, both reported on both metrics:

  | contrast | handoff flag taken from |
  |---|---|
  | `prefix_m11 − planner_alone_cap81` (P3's contrast) | `prefix_m11` |
  | `prefix_zs_m11 − planner_alone_cap81` | `prefix_zs_m11` |

  - Estimand: Σd·h / Σh, where h is the prefix arm's `handoff_occurred`; a missing flag counts as h = 0
    and is counted. Whole scenarios are resampled, as in S6.
  - Scenario and task intervals, with `n_handoff` and the number of silenced episodes.
  - The reading on `goal_pass` at −7.00 pp: **holds** if the scenario lower bound is above −7.00 pp, else
    **fails**. §5.4 applies to that bound as it applies to P3: within 1.00 pp of −7.00, it is recomputed at
    the seven seeds, and any change of reading makes it **on the boundary**.
  - The reading is printed in the same sentence as P3's verdict. It never changes P3's verdict.
- **B2. Decomposition.** For S6, both receivers, m9 → m11: the all-episode rise split into its handoff and
  silenced contributions, and the share of the rise earned on handoff episodes, with its scenario interval
  (the `j16_robustness.decomposition` estimand).
- **B3. The chord test** (the dev prereg's claim C2, `docs/prereg_hj12_dev_20260922.md:38-40`), for
  `prefix_m9`, `prefix_m11`, `prefix_zs_m9` and `prefix_zs_m11`.
  - Residual, per paired `(task_id, seed)`: q_arm − [q_floor + f·(q_ref − q_floor)].
  - Floor: arm 2 `sft_plan`. Reference: arm 3.
  - f = (c̄_arm − c̄_floor) / (c̄_ref − c̄_floor), from each arm's mean non-cached planner tokens per episode in
    the P2 cost report. f is a plug-in; it is not resampled. The cost report must therefore cover arms 2, 3
    and 4–7 as well as P2's two arms; an arm without a cost row is reported as not computed.
  - Intervals: scenario primary, task secondary.
  - A positive residual means the arm lies above the straight line from the one-plan floor to the planner
    acting alone.
- **B4. Reporting rule.** Every all-episode depth or non-inferiority number from J10 is printed with its
  handoff-only companion beside it.

### C. Content family CF (registered; decision-bearing; its own family)

**Why.** B2 left P7 unregistered, and arms 11 and 12 are exploratory (§6). On dev:
- neutral-prompt advice recovered about three-fifths of the takeover−advice gap;
- neutral-prompt advice contained a fenced code block in 132 of 141 interventions, against 2 of 167 under the
  registered correction prompt.

This adds a registered test, before any test episode exists, of the one decomposition contrast whose power is
usable. It does not reopen P7. §5.3's "no exploratory contrast may be promoted to a claim after the read" is
respected because CF1 is registered before the read.

- **CF1 — the only decision-bearing member of family CF.**
  - Prediction: `advise_k10_neutral − advise_k10_fullctx` on `goal_pass` is **positive with a 95% scenario CI
    excluding zero**.
  - Rule: `positive_excludes_zero_with_reversal` (two-sided bootstrap p, as P6).
  - Dev, 171 pairs, seed 20260924: **+3.73 pp [−0.06, +8.24]** (`campaign/results/b2_decomposition_20260923.report.json`, key `contrasts.D3`).
  - Power: **0.72** at the dev effect, **0.21** at half of it.
  - Outcomes:
    - **Supported** → on test, advice written under a neutral prompt beats advice written under the registered
      correction prompt. P6 is then reported only as "actions beat correction-prompt advice", never as a
      channel effect.
    - **Not supported** → the prompt effect is reported as not replicating at 336 pairs. P6 is reported as
      built, with §6's qualification.
    - **Reversed** → reported as a primary finding.
- **Family and error control.**
  - CF has one member, so no adjustment is needed.
  - CF is not part of P1–P6's Holm family, so P1–P6's α is unchanged.
  - A first power run that placed CF1–CF3 in one Holm family gave CF1 a power of 0.58, and CF2 and CF3 at most
    0.29. That is why CF has one member.
  - §4.2 (the planless-key exclusion), §5.4 (POOL-04) and §5.5 (sign-flip sensitivity) apply to CF1 as they
    apply to P6.
  - CF1's verdict is printed beside the headline. It does not change whether P1–P6 are complete.
- **CF2, secondary** (pre-specified; not decision-bearing; unadjusted; fixed reading).
  - Contrast: `show_k10 − advise_k10_fullctx` (E3 / B2 D2).
  - Dev: +2.30 pp [−2.43, +7.31]. Power 0.29.
  - Readings: if the CI excludes 0 above, "the planner's action shown as text beats correction-prompt advice";
    if it excludes 0 below, "correction-prompt advice beats the planner's action shown as text"; otherwise
    "not resolved".
- **CF3, secondary** (same status).
  - Contrast: `takeover_k10 − advise_k10_neutral` (E5 / B2 D4).
  - Dev: +2.40 pp [−2.94, +8.89]. Power to exclude 0 on either side: 0.25.
  - Readings:

    | CI | reading |
    |---|---|
    | excludes 0 above | "executing the action adds to advice written under a neutral prompt" |
    | excludes 0 below | "neutral-prompt advice beats takeover" |
    | includes 0 | "the added effect of execution is not resolved at 336 pairs" |

  - The paper will **never** write that execution adds nothing.
- **Descriptive** (arms 9–12): share of interventions containing a fenced code block, median intervention
  length, and the executor's copy rate of shown or advised code (B2's definition).
- If arms 11 and 12 cannot complete (§9 abort rule), CF is reported as not run.

### D. Step-limit reporting (not decision-bearing)

**Why.** On dev, the 40-step limit was hit by 20 of 171 advice episodes against 2 of 171 takeover episodes.
Those pairs carried 4.36 of P6's 6.13 pp.

- **D1.** Each arm's `limit` rate is printed beside every arm mean and every contrast.
- **D2.** For P1, P6, CF1 and CF3, the mean paired difference is split over two sets of pairs: those where
  either arm hit `limit`, and those where neither did. Each part is reported with:
  - its n;
  - its mean;
  - its contribution to the whole, with scenario and task intervals. The two contributions sum to the whole.
  - It is labelled post-treatment, since hitting the limit is an outcome of the arm.
  - It is never offered as a corrected estimate.
- **D3.** A limit-as-0 sensitivity for the same contrasts: each `limit` episode's `goal_pass` is set to 0, in
  both arms, and the scenario interval is reported.

### E. P1 reporting constraint

- **The frozen rule.** The dev prereg for H2 (`docs/prereg_h2_advice_at_price_20260923.md` §5) says: *"If P4
  fails: report the arm as a higher-frequency advice result only, and state explicitly that advice remains
  unpriced at the action channel's budget."*
- **It applies.** H2's P4 failed on dev: 1,414,410 non-cached tokens per episode against the registered
  [300k, 700k].
- **What changes.** P1's decision rule is unchanged, and P2 remains the cost predicate. What changes is how P1
  may be described:
  - as "correction-prompt advice at every step, against the m = 11 prefix";
  - never as advice at matched budget;
  - never as ruling out a budget effect.

### F. Multiplicity sensitivity (not decision-bearing)

- **What is added.** Beside the registered verdicts, the report gives Benjamini–Yekutieli-adjusted p values
  across every paired `goal_pass` contrast it prints, each counted once:
  - P1, P3, P4, P5, P6 and CF1;
  - S1–S5 (S6 is a ratio row, and B2 reports it);
  - E1, E2, E3 and E5. E4 is CF1's contrast and is counted as CF1; E3 and E5 are CF2's and CF3's;
  - the two B1 contrasts.

  That is 17 contrasts when every arm runs. A contrast without a p (an absent arm, or no handoff episodes) is
  listed and left out of m.
- **Which p.** Each contrast's two-sided bootstrap p at its threshold (P3 and B1 at −7.00 pp).
- **Effect on verdicts.** A registered verdict that rests on a rejection (supported or reversed) and would not
  survive this adjustment is flagged in the same sentence. P5 is supported by a non-rejection, so there is
  nothing to withdraw. No verdict changes.

### G. Pointer corrections (no registered content)

- **G1.** §10 cites `src/sidekick/policies/sft_plan.py:18`. That path does not exist. The `SftPlan` defaults
  are at `src/sidekick/systems/sft_plan.py:11`.
- **G2.** `campaign/results/j10_a1_registered_dev_basis_20260924.report.json`, cited in §6, holds dev data only.
  It was written by `j8_frontier.py` over dev campaigns, and its `j10_` prefix names the amendment it serves,
  not a split.

### H. What this amendment does not do

- It adds no arm.
- It changes no P1–P6 prediction, rule, threshold or Holm family.
- It changes no margin, bootstrap seed, order, budget or abort rule.
- It changes no dev reference value.
- It promotes nothing after the read.

### I. Executor asks in the replay arms (operational; fixed before the read)

**Why.** Arms 2 and 4–7 replay arm 3's plan, and §9 budgets them at zero hosted calls outside §4.2's planless
keys. Their systems still honour an executor's `ASK_PLANNER`:
- `sft_plan` and `prefix_handoff` both set `allow_executor_ask=True` (`src/sidekick/systems/sft_plan.py:14`,
  `src/sidekick/systems/prefix_handoff.py:42`);
- the replaying planner answers such an ask live, through the codex planner
  (`src/sidekick/agents/planner.py:956-962`).

The dev arms ran the same way. On dev, the HJ-17 cap-81 prefix arms, the dev arms closest to arms 4–7, recorded
0 ask events (`docs/prereg_lp_planner_strength_20260923.md:171`); other dev prefix arms recorded a few (ledger
PROV-02).
`j10_arm.pbs` gives arms 4–7 `--gate` alone, which asserts zero live planner calls, so one ask fails that gate.

**Registered handling.**
- An ask answered live is part of the registered system, as on dev, and is not an error.
  - The episode is kept and scored.
  - It is never purged, rerun or excluded for that reason.
- Every live ask call is counted, per arm, and reported beside §9's registered total.
- A gate failure whose only cause is live ask calls is recorded in that arm's ledger row. It does not make the
  arm incomplete; completeness is decided by §9's 336-pair rule and the crash rule alone.
- If the smoke gate stops an arm for this reason alone, the smoke tree is kept (it is never analysed) and the arm
  is resubmitted unchanged.
- **Bound.** For each prefix or `sft_plan` contrast, the report gives the number of episodes that received a live
  answer, and the most that help could have moved the arm mean: that count / 336, in pp. This is the ledger
  PROV-02 bound.
  - If a bound reaches 1.00 pp, the contrast's verdict is printed with its bound in the same sentence.
  - No verdict changes.

*Amendment 1 ends.*
<!-- END APPENDED TEXT -->
