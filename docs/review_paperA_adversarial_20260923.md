# Adversarial review of Paper A (`paper/preprint_dev_20260923.md`), 2026-09-23 evening

Asked by the user: *"the freeze results and any additional result needed are enough for a full paper right? do we
have that yet? what else is remaining for it? if it is there, review it adversarially in detail"*.

Method: Claude read the whole paper. Three independent read-only Opus reviewers each took one line of attack:
claims against artifacts, novelty (with web search), and design/statistics. **Every finding below marked ✔ was
re-checked by Claude against the files, the episode logs or the cited paper before being written here.** Findings
the reviewers reported that Claude did not re-check are marked (unverified).

## 0. Answer in one paragraph

- **A1 is a protocol, not a result.** A1 is frozen (142e947). Its registered test read (J10) has not started. Only
  the dev dry run has run (clean, 2026-09-23 18:31–19:00). There is no held-out result yet.
- **A full paper exists:** Paper A, dev only, 14,068 words. As it stands it is a workshop / Findings / TMLR paper
  after fixes, not a top-venue main-track paper.
- **The key strategic point:** even if every J10 prediction is supported, J10 as frozen confirms two things only:
  - P6: "takeover beats advice written under the registered correction prompt";
  - P1: "advice at every step loses at 3× the tokens".

  B2 already showed the first is largely a prompt effect, and the second breaks the H2 prereg's own rule (§2 F3).
  So J10 cannot, by itself, make the channel claim a top-venue claim.

## 1. What is solid (keep)

- No adapter leakage: 0 of the 19 dev scenario ids appear in the adapter's training data or manifests, and a code
  guard forbids it (design reviewer; `src/sidekick/training/sft_data.py:29`) (unverified by Claude).
- The paired replay design: prefixes are byte-identical across receivers, and replicate noise is small at m = 6/9.
- The pre-registration discipline and the ledger. The arithmetic is clean: of about 50 numbers checked there are
  no sign flips, no interval that excludes its own point, and no n mismatch in the headlines (number auditor).
- The narrated control (prefix as text in a fresh environment) and the B2 decomposition design are genuinely good
  designs.

## 2. Findings, most severe first

### F1 ✔ FATAL (top venue). The depth result is mostly the planner finishing the task, and the paper omits its own registered safeguards
- **Episodes with no handoff.** In the pooled cap-81 tailored arms, `handoff_occurred = false` holds in:
  - **4/171 episodes at m = 6**;
  - **54/171 at m = 9**;
  - **100/171 (58 %) at m = 11**.

  Recounted by Claude from `events.jsonl` (`hj17_prefix_c81_bplus_m*`, `hj18_prefix_c81s3_bplus_m*`).
- **Where the tailored gain comes from.** Of the tailored m = 2 → 11 rise of +12.42 pp, only +2.08 pp
  [−0.69, +4.91] (16.7 %) comes from episodes that handed off (ROB-13).
- **A registered rule is broken.** `docs/prereg_hj12_dev_20260922.md:336-341` says: *"The honest population for
  any prefix arm is handoff-only … quoting a pooled number without the handoff-only number beside it repeats the
  m=9 contamination."* The abstract and §5 quote pooled numbers only.
- **A registered test is missing.** The chord test (C2, prereg_hj12:40) failed. The word "chord" appears 0 times
  in the paper ✔.
- **Cost at m = 11.** Against the cap-25 ceiling, m = 11 uses **78 % of the planner's hosted calls** (11.25 vs
  14.43) and keeps only **~25 % of its dollar saving** ($0.0265 vs $0.0355) (Table 1 arithmetic).
- **It replicates prior work.** Ganz et al. (arXiv 2608.24358, App. B.2) ✔: *"Later downshift generally improves
  quality while retaining less savings"* (raw GPT downshift quality recovery 61 % early → 77 % late). **The depth
  curve is a replication of a published finding in a new setting, not a new finding.**
- **J10 does not fix it:** P3/P4 are all-episodes, and there is no handoff-only rule and no chord test.

### F2 ✔ FATAL (top venue). The channel headline is fragile and concentrated in step-limit failures
- **Significance depends on the test.** D0 = +6.13 pp at 171 pairs, but the exact 19-scenario test gives
  p = 0.063, the TGC interval includes zero, and SGC does not resolve.
- **Where the gap comes from** (recounted by Claude, 171 pairs):
  - registered advice hits the 40-step limit in **20/171** episodes, takeover in **2/171**;
  - those 20 pairs contribute **4.36 of the 6.13 pp** (advice 0.361 vs takeover 0.734 on them);
  - on the other 151 pairs the gap is **2.00 pp**.
- **This is not a scoring artefact.** Scoring `limit` as 0 would widen the gap. It is a termination mechanism:
  under a terse correction prompt, the advised executor runs out the clock ten times as often. **Required by
  prereg_hj12:183-187 and not reported:** the per-arm limit rate beside every quality number.
- **Neutral advice is mostly code.** Neutral-prompt advice contains a fenced code block in **132/141**
  interventions (registered prompt: 2/167), and its median length is about 4.5× longer ✔. The neutral prompt
  explicitly allows code (`planner.py:139-140`). "Fair" advice is the planner writing code as text, and it
  recovers about three-fifths of the gap (D3 +3.73 [−0.06, +8.24]); T − N is +2.40 [−2.94, +8.89].
- **Honest reading (exploratory):** what helps the 8B executor is *concrete code from the planner*, whether it is
  executed or shown. A terse "correction" leaves it stuck.

### F3 ✔ FATAL (credibility). The paper does not follow a frozen registration's decision rule
- **The rule.** `docs/prereg_h2_advice_at_price_20260923.md` §5: *"If P4 fails: report the arm as a
  higher-frequency advice result only, and state explicitly that advice remains unpriced at the action channel's
  budget."*
- **What happened.** P4 failed (1,414,410 tokens vs the registered [300k, 700k]). The paper still headlines
  "registered primary H2" and "establishes the claim at matched budget … the gap is not a budget effect"
  (L21, L140-142, L519). App. B.1 argues around the rule.
- **It is also unsupported on substance.** P3 shows that more advice does *worse*, so k = 1 changes the dose of an
  error-presuming prompt; it does not match the budget. The only near-matched pair (advise_k3 204k vs prefix_m6
  221k) is null: −2.25 [−9.05, +5.15] (ROB-20; number auditor, unverified by Claude).

### F4 ✔ MAJOR. Registration outcomes are missing and the exploratory status is blurred
- **Two registered outcomes are never mentioned.** Gate G1 FAILED on both clauses (prereg_hj12:295-310 ✔; the
  registered consequence is "the flat-curve branch is in force"). Registered C2's non-inferiority fails at every
  registered depth; at m = 9 it is −1.50 [−8.10, +5.62], `holds: false` ✔.
- **The depths behind every headline are post hoc.** m ∈ {7, 8, 10, 11} were "chosen after seeing the data"
  (prereg_hj12:318-322), yet m = 11 carries the abstract's non-inferiority, span, DiD and CHAN-C1-03 claims.
- **One test is mislabelled.** L192 calls the segmented test "pre-registered"; HJ-13 itself labels it exploratory
  because the curve was already seen.
- **Multiplicity is controlled only within families.** Across the paper there are about 86 exploratory ledger
  rows against about 32 registered ones (design reviewer's tally, unverified).

### F5 ✔ MAJOR. The non-inferiority claims rest on a margin of convenience, a diluted comparison and a weak ceiling
- **The margin.** δ = 7.00 pp was the smallest margin detectable at 80 % power, for **TGC**, on the **168 test
  tasks** (prereg_v1:88-95 ✔). J9 later moved it to `goal_pass` and itself calls it "only twice TGC's replicate
  noise floor". It is not a substantive margin.
- **Dilution.** At m = 11, 58 % of episodes are the ceiling's own trajectory (F1), so the effective margin on the
  steered episodes is about 17 pp (inferred).
- **A weak ceiling.**
  - cap-81 scores 6.47 pp *below* cap-25 (more budget, lower score).
  - Planner-alone TGC here is 0.57–0.68 on dev, against **85.1 % TGC on test_normal for the same `gpt-5.6-luna`
    in a proper scaffold** (paper B.6 L847 ✔).
  - The ceiling is therefore harness-limited.
- **The abstract's "three of four m = 11 arms NI on both metrics" omits three things:**
  - the exact test fails prefix_m11 TGC (p = 0.0264, `conclusion_changes_on_primary: true`);
  - two of the three passing arms are only task-paired with cap-81;
  - one of the two trajectory-paired arms fails TGC (number auditor).
- **J10 makes the dilution worse:** P3 uses the cap-81 ceiling as both the reference and the prefix source.

### F6 ✔ MAJOR. Novelty and positioning
- **Ganz is described too narrowly.** Ganz et al. ✔ uses **3 benchmarks** (SWE-bench Verified, Lost in
  Conversation, BrowseComp) and **both** the Claude and GPT families, and **uses GPT-5.6 Luna as its *low-cost*
  model**. §10 mentions only SWE-bench, and the paper calls luna "a strong hosted planner".
- **The Intro contradicts §10.** L13 says "Existing approaches typically use the hosted model as a critic or
  upfront planner"; §10 itself lists SwiftSage, R2V, step routers and Ganz, all of which have the strong model act.
- **Missing must-cites** ✔ (checked exist):
  - Minions (Narayan et al., ICML 2025; local–cloud collaboration, where protocol design dominates);
  - ManagerWorker (Liu, arXiv 2603.26458): a text-only strong manager directing a cheap worker scores 62 %
    against 60 % for the strong agent alone, and structured direction adds 11 pp while review-only adds 2 pp.
    That is published evidence that advice works when the protocol is good.
- **Should cite** (unverified): Torrey & Taylor 2013 (action advising on a budget); Sumers et al. 2023 "Show or
  tell?"; TACIT-Switch 2608.27911; Prefix-GRPO 2607.19395; COTA 2608.21027; Sinha et al. ICLR 2026. 17 of the 65
  bibliography entries are never cited.
- **Correction to the novelty reviewer:** "Do Not Restart" (2609.13800) exists, but its abstract does not
  compare state and transcript interfaces.

### F7 MAJOR. Metric and reporting choices
- **`goal_pass` gives partial credit for doing nothing.** Qwen scores 0.2481 with 0/114 successes ✔. The official
  TGC/SGC do not resolve for the channel headline.
- **The clustering reported is chosen selectively.**
  - L201 quotes the untailored m9→11 rise with only the task CI; the primary scenario CI is **[−0.23, +9.74]**,
    which includes zero ✔.
  - L211 says "no single adjacent step significant", but a cap-81 TGC step resolves (number auditor).
- **Equivalence is claimed from nulls:** "matches oracle replay" (L22), "matches execution at every depth" (L24;
  NI fails at m = 6), "sequence of actions, not the facts" (L354).
- **Replicate noise is understated.** The m = 2 re-run moved 0.7187 → 0.6856 (**3.31 pp**, limit 18 → 24) ✔. The
  paper quotes 0.04 and 1.82 pp.
- **Mechanism is stated causally** ("Two mechanisms explain", L376) from descriptive analyses. The tailored 36.0 %
  share has CI [−254 %, +77 %] (number auditor).
- **Internal inconsistencies** (number auditor):
  - prefix_m9 TGC vs cap-81: +7.89 (L174) vs +8.77 (L244);
  - CEIL-05 orientation flips between sections;
  - L172's −1.33 uses the pre-guard m6;
  - the "partially substitutable" reading survives at L801-803 after being withdrawn at L369.
- **Ledger errors** (the paper is right in both): QWEN-05 and NARR-04.
- **The audit script is weaker than claimed.** It checks only unsigned magnitudes, never CI endpoints, signs or
  pairings, and its stated counts are stale (97/105 vs 109/114).

### F8 MINOR
- **Length.** 14,068 words against about 7,300 for 8 pages.
- **Privacy.** The privacy motivation (L13) is not delivered: the hosted planner sees the task and the first m
  observations.
- **Unsupported explanation.** L851's "excluding 3 multi-party synchronization tasks" is unsupported (the pinned
  release ships 57 dev tasks; design reviewer, unverified).
- **Misleading file name.** CEIL-05 is sourced from a file named `j10_a1_registered_dev_basis_…`. It is dev data,
  but the name invites a contamination question; rename it.

## 3. What J10 (as frozen) will and will not fix

| issue | J10 as frozen |
|---|---|
| dev-only / forking paths | fixes it for P1, P3, P4, P6 (fresh data, Holm over 4) |
| 19 clusters | improves it (~56 test scenarios, 336 pairs) |
| channel = prompt? (F2) | **no**: P6 tests the contrast as built; arms 11/12 are exploratory E2–E5, and T − N (dev +2.40) is likely underpowered (inferred CI half-width ~3.5–4 pp) |
| H2 rule (F3) | **no**: P1 keeps the same k = 1 error-presuming design |
| depth = planner finishing (F1) | **no**: no handoff-only rule, no chord test |
| NI dilution and weak ceiling (F5) | **no**, and it makes the dilution worse |
| one planner / one environment | **no** (LP-2 and Wave E address it) |

## 4. What remains for a full top-venue paper

1. **A decision before any test data exists:** whether to append an A1 amendment. Append-only and pre-data are
   both allowed by A1; appending does not shift j10_report's line citations. It would register:
   - (a) handoff-only companions for P3/P4 and the chord test as registered secondaries;
   - (b) a separate family for the *content* reading: N − A > 0 (code-bearing advice beats correction prose)
     and T − N non-inferior within the margin;
   - (c) per-arm limit rates and a non-limit sensitivity for P6;
   - (d) P1 reported under H2's rule as higher-frequency advice.
2. **J10** (≈15.6k luna calls, 3–4 windows, then GPU replays), then j10_report.
3. **LP-2 chain** (running) and lp_report: the planner-strength axis.
4. **Stronger advice baselines.** Neutral advice at k = 1 (~2.2k calls, dev), and optionally a ManagerWorker- or
   Minions-style structured-direction arm, to answer "strawman".
5. **A second environment** (Wave E). This is the literature norm: Ganz has 3 benchmarks, Reach-or-Solve 2
   environments. Engineering is 2–3 weeks.
6. **A rewrite** (writing only, days):
   - follow H2's rule;
   - add a registration-outcome table (G1, C2, the post-hoc depths);
   - add handoff-only numbers, limit rates, and TGC plus both clusterings beside every headline;
   - equivalence language → "not distinguishable";
   - describe Ganz correctly and add the must-cites;
   - cut to 8 pages;
   - fix the ledger rows QWEN-05 and NARR-04;
   - harden the number audit to check signed endpoints.
