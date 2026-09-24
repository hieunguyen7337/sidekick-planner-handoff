# Pre-registration: the channel result across planner strength (LP-1, LP-2)

**Status**: **FROZEN on commit** (dev split only; no test data is read or touched). Frozen by Claude on the
rationale the user accepted for B2 in the approved plan of 2026-09-23 07:30 (§8.2: a dev-only registration that
touches no test data may be frozen on commit). This is a different registration from B2. **The user may void it
by saying so before the first LP channel or replay arm runs**; after that it stands. Amendments are appended below
the end marker, never edited in.

**Written**: 2026-09-23 ~10:40 AEST. At the time of writing:
- **No LP channel arm** (takeover, advice, advice-at-price, plan-only) and **no LP replay arm** has run.
- **The LP-1 ceiling** `lp1_planner_alone_cap81_qwen8b_v2_20260923` (job 25724729) is running. Only its episode
  count, error types, plan parse path and planner-thread statistics have been read, to check the harness; no
  score of it has been inspected.
- **The LP-2 ceiling** has not started.
- **The first LP-1 campaign** `lp1_planner_alone_cap81_qwen8b_20260923` is **VOID**: its plan call had no
  structured output, so every episode ended `parse_error` at step 0 (commit 4d225cf). It is never analysed.

---

## 1. Why

Every channel and depth result in this project drives one hosted planner, `gpt-5.6-luna`. The obvious objection is
that "spend the planner's budget as actions, not advice" is a fact about that planner. The planner-strength axis tests it:
the same executor, tasks, arms and analysis, with the planner replaced by two open-weight models of
different strength, served locally at zero hosted cost.

## 2. Planners, harness and arms

| planner | model | serving |
|---|---|---|
| **luna** (reference) | `gpt-5.6-luna`, reasoning effort medium | hosted, `codex exec`; the existing dev arms |
| **P8** | `Qwen/Qwen3-8B` | vLLM 0.29.0, bf16, 1 H100 |
| **P27** | `Qwen/Qwen3.8-27B-FP8` | vLLM 0.29.0, FP8 (Cutlass block-scaled kernel; DeepGEMM off), 1 H100 for the ceiling |

The local-planner harness differs from the hosted one in these ways. They are disclosed here, not corrected:
- **Decoding:** temperature 0.7, `max_tokens` 2048, thinking disabled (`enable_thinking: false`). The hosted
  planner uses the service's decoding at medium reasoning effort.
- **Memory:** one conversation per episode, reproducing the hosted planner's resumed codex thread, with the same
  prompts and the planner's own replies in between. The served window is 32,768 tokens.
  - When the conversation outgrows it, the oldest exchange that is not the anchor is dropped. The anchor is the
    plan exchange, or the first live exchange when the plan is replayed.
  - An episode whose anchor and current prompt alone do not fit ends as a scored `limit` / `planner_context`
    (commit fe719e9). The hosted planner compacts in its own, unobserved way.
- **Plan call:** structured output against `DELEGATION_PACKET_SCHEMA`, as the hosted `--output-schema` call. The
  fallback prompt is byte-identical (commit 4d225cf).
- **Cost:** GPU seconds, not dollars. **No cost or token comparison between a local planner and luna is made**;
  this registration concerns quality contrasts only.

Arms per local planner p ∈ {P8, P27}: seeds 1–2, the 57 dev tasks, granite-4.2-8b executor. Every arm is paired to
the others by `(task_id, seed)`, **114 pairs**.

| code | arm | config (p = 1 for P8, 2 for P27) |
|---|---|---|
| **C_p** | planner acting alone, cap 81: the ceiling, and the source of every other arm's plan packet and prefix | `lp{p}_planner_alone_cap81_*` |
| **T_p** | takeover at k = 10; replays C_p's first plan packet | `lp{p}_hj12_takeover_fixed_k_10` |
| **A_p** | prose advice at k = 10, full context | `lp{p}_hj12_advise_fixed_k_10_fullctx` |
| **A1_p** | prose advice at every step, full context (advice at price) | `lp{p}_hj13_advise_fixed_k_1_fullctx` |
| **F_p** | plan only, tailored receiver | `lp{p}_hj8_sft_plan_bplus` |
| **M^r_{p,m}** | the executor re-runs C_p's first m actions, then continues; receiver r ∈ {bplus (tailored), zs (untailored)}, m ∈ {6, 9, 11} | `lp{p}_prefix_{r}_m{m}` |

**Luna reference arms (dev, existing):**
- the CHAN-C1-02 pair (`hj12_takeover_fixed_k_10_20260923`, `hj12_advise_fixed_k_10_fullctx_20260923`);
- H2's `hj13_advise_fixed_k_1_fullctx`;
- the HJ-17 cap-81 prefix arms and their ceiling `hj13_planner_alone_cap81_20260923`.

Luna's T/A arms replay the cap-25 plan packets (`hj1b`), while the LP arms replay their own cap-81 ceiling's. A
plan packet is produced before any action, so the cap cannot affect it. The difference is disclosed, not corrected.

## 3. Estimation

- **Metric:** `goal_pass` is primary; TGC is secondary (reported, not decision-bearing).
- **Pairing and intervals:** paired by `(task_id, seed)`. The percentile bootstrap is scenario-clustered (primary,
  19 clusters) and task-clustered (secondary), with B = 10,000 at seed 20260924.
- **POOL-04:** any decision-bearing bound within 1.00 pp of its threshold is re-run at seeds
  {20260924, 1, 2, 3, 7, 101, 999}. A verdict that differs on any seed is **on the boundary**, never resolved.
- **Sensitivity (not decision-bearing):** the cluster sign-flip p, by exact enumeration (2^19 patterns), through the
  shared routine `cluster_inference.registered_signflip`.
- **Crashes:** only `error_type == "crash"` is dropped and refilled. `limit` (including `planner_context`),
  `parse_error` and `timeout` are scored. A contrast whose arms lack 114 non-crashed pairs is reported as
  **incomplete**, with its counts, and no reading is drawn from it.
- **Multiplicity:** Holm across L1–L5, **within each planner** (two families of m = 5). Each planner is a separate
  replication of the luna result, so no correction is made across planners.
- **p-values:** the two-sided-equivalent percentile p from the same bootstrap. L1 registers a reversed outcome, so
  its p is two-sided. The others use 2 × the share on the wrong side of their threshold (A1 r2 §5.3's rule).
- **Reading "excludes zero":** an interval condition holds only if the unadjusted scenario interval meets it
  **and** the Holm-adjusted p ≤ 0.05. "Includes zero" is judged on the unadjusted interval (B2 Amendment 1 §2–3).

## 4. Contrasts and predictions (each local planner separately)

| id | contrast | predicted | luna dev reference |
|---|---|---|---|
| **L1** | T_p − A_p | **> 0** (action beats advice at a matched trigger) | CHAN-C1-02: +6.69 pp, scenario [+1.29, +13.49], 114 pairs |
| **L2** | A1_p − M^bplus_{p,11} | **< 0** (advice at every step does not reach the 11-action prefix) | CHAN-PRICE-01: −14.68 pp, [−22.09, −7.04] |
| **L3** | M^bplus_{p,11} − M^bplus_{p,6} | **> 0** (depth span, tailored receiver) | POOL-01 (span holds on both receivers at 171 pairs) |
| **L4** | C_p − M^bplus_{p,11}, ceiling minus arm | **upper bound < +7.00 pp** (non-inferiority at the J9 margin) | POOL-02: −4.41 pp, [−10.66, +0.74], 171 pairs |
| **L5** | M^zs_{p,11} − M^zs_{p,6} | **> 0** (depth span, untailored receiver) | POOL-01 |

**Informativeness gate, evaluated first.** Let E be the tailored executor acting alone on dev,
`hj8_executor_alone_bplus_20260919`. If C_p − E has a point estimate ≤ 0, the planner is no better than the executor
it would help. Planner p is then registered as **too weak to test the channel**: L1–L5 are reported, and no
reading is drawn from them.

**Readings for a planner that passes the gate:**
- **L1 replicates:** > 0 with the interval excluding zero (per §3).
- **L1 fails to replicate:** its interval includes zero.
- **L1 reversed:** < 0 with the interval excluding zero; reported as a primary finding.
- L2–L5 are each supported or not by their own rule. They qualify the reading but do not rescue a failed L1.

**The overall claim:**
- **The channel claim generalises across planner strength** if L1 replicates for both local planners that pass
  the gate.
- **It is bounded** if L1 replicates for exactly one of them, and the paper says which.
- **It is luna-specific** if L1 replicates for neither. That is reported as the generality result, not as a failure
  to be explained away.

**Descriptive only; not a prediction and not decision-bearing:**
- **The channel margin against planner strength.** For each local planner, Δ_p = (T_p − A_p) − (T_luna − A_luna)
  on the shared `(task_id, seed)` keys, with its scenario interval.
- **Planner strength itself.** It is indexed by each ceiling's mean `goal_pass`.

Three planners cannot establish a trend, so no direction is registered for Δ_p. Stated so that surprise is
visible: we expect L1 > 0 for both local planners, and have no expectation for the sign of Δ_p.

## 5. Order and budget

- **Hosted calls: zero.** Every arm is local.
- **Sequence:** the ceilings (LP-1 1 H100; LP-2 1 H100) come first. Each channel arm needs its ceiling complete at
  114 non-crashed episodes, and `lp_live.pbs` refuses otherwise. Each replay arm needs the same, and
  `hj12_prefix.pbs` refuses otherwise.
- **Analysis:** `j8_frontier.py` / the pooled-contrast code with the settings in §3. The ledger rows are LP-01 onward.

## 6. Not claimed

- No cost or token comparison with luna.
- No claim about either Qwen model as a planner in general.
- Nothing on the test split.
- No decomposition of the local planners' channel contrast. B2 is luna-only.

<!-- end of registration; amendments below -->

## Amendment 1 — disclosure of a harness check (2026-09-23 ~10:45 AEST; no registered item changes)

While LP-1 v2 was running, 16 of its first 24 episodes ended `limit` (`max_steps`, 40), none of them
`planner_context`. To rule out a harness defect before any LP arm consumes the ceiling, the following was read.
**Nothing above the end marker is changed.**

- **Read:** the action kinds, planner code and observations of two `limit` episodes (`50e1ac9_1` and
  `fac291d_2`, seed 2), and their `goal_pass_rate`: **0.5 each**. These are the only LP scores seen. No mean,
  no arm-level score and no contrast has been computed.
- **Found:** the planner guesses placeholder credentials (`username="your_spotify_username"`, …), receives
  `401 Invalid credentials`, and then emits the non-terminal `REPORT:` action until the step cap. `REPORT` is
  offered to every planner by the same act prompt (`src/sidekick/agents/planner.py:152`) and handled identically
  (`src/sidekick/systems/loop.py:1129-1139`).
- **Comparison with the luna reference, counted by `grep -l` over `events.jsonl`:**
  - `apis.supervisor.show_account_passwords` appears in 0 of the first 29 LP-1 episodes and in all 114 episodes
    of `hj13_planner_alone_cap81_20260923`.
  - `apis.api_docs` appears in 3 of the 29 and in 113 of the 114.
  - No prompt builder in `src/sidekick` mentions the supervisor app. Luna reaches the password route through the
    environment's own documentation endpoints, which the local planner mostly does not call.
- **Reading:** a capability difference, not a harness defect. The harness is unchanged and LP-1 v2 continues
  under this registration. Whether P8 is informative is decided by the §4 gate, as registered.

## Amendment 2 — the replay arms answer executor asks with the local planner; first attempt void (2026-09-23 ~11:50 AEST)

The registered arms and contrasts are unchanged. This amendment fixes how M^r_{p,m} is run so that it matches the system
the luna reference arms ran.

- **What the system does.** `prefix_handoff` honours executor asks (`src/sidekick/systems/prefix_handoff.py:42`,
  `allow_executor_ask=True`). A stuck executor's `ASK_PLANNER` calls the replaying planner's `correct()` live
  (`src/sidekick/systems/loop.py:1042-1085`). In the published luna prefix arms such asks were answered by hosted luna.
  - Among the luna reference arms named in §2, the HJ-17 cap-81 prefix arms recorded **0** ask events.
  - Other published prefix arms recorded a few, e.g. `hj13_prefix_hf_m6_20260923` with 7 episodes and 10 live calls.
    Those are audited separately (ledger PROV-02).
- **What went wrong.** The LP replay arms were first submitted through `scripts/pbs/hj12_prefix.pbs` (PBS 25725094).
  That job starts only the executor server, so every honoured ask hit a closed planner port and ended `crash`
  (`ConnectError`, connection refused). Refilling those crashes would re-draw exactly the episodes whose executor got
  stuck enough to ask, which is selection on outcome. The job was stopped.
- **Rule from here.**
  - M^r_{p,m} runs with the local planner p served, through `scripts/pbs/lp_live.pbs` (`ARMSET=lp{n}_prefix`), so
    asks are answered as luna answered them.
  - All 12 LP prefix configs move to new campaign ids `lp{n}_prefix_{r}_m{m}_v2_20260923`, and each arm is run
    **whole**.
  - The old ids `lp{n}_prefix_{r}_m{m}_20260923` are **VOID** and never analysed. Only
    `lp1_prefix_zs_m6_20260923` has any episodes: 114 written before the stop, 24 of them crashes. Only its episode
    count, error types and crash payloads were read; no score of it has been computed or inspected.
- **Reported, not corrected:** the number of honoured asks per LP prefix arm, beside the arm's mean. That lets a reader
  see how much of the arm is live planner help, as PROV-02 does for the luna arms.

## Amendment 3 — correction to Amendment 2's crash attribution, and a disclosure (2026-09-23 ~12:35 AEST; no registered item changes)

- **Correction.** Amendment 2 reasoned as if the 24 crashes in the void `lp1_prefix_zs_m6_20260923` were episodes
  whose executor asked. Only **3** were. Result-file mtimes and event logs show:
  - 3 crashes before the stop, at 11:36:24, 11:39:04 and 11:39:09 AEST, are exactly the 3 episodes with an `ask`
    event (`2/d4e9306_2`, `2/383cbac_2`, `2/23cf851_1`). They are the outcome-linked ones Amendment 2 describes.
  - The other **21** were written in a 9-second burst, 11:42:21–11:42:30, when job 25725094 was stopped. They are
    in-flight episodes whose executor server went down under them (`ConnectError` at the next executor call, e.g.
    step 7 = the first post-handoff call at m = 6). That is an infrastructure artefact.

  The decision is unchanged. The arm had to be re-run with the planner served in any case, so that asks are
  answered, and it was re-run whole under the v2 id.
- **Disclosure.** Checking the v2 harness, one v2 episode's `goal_pass_rate` was displayed:
  `lp1_prefix_zs_m6_v2_20260923`, seed 1, `6171bbc_3`. `scripts/analysis/lp_report.py` was committed before it
  (c474a5c, ea7e775), and no aggregate of any LP arm has been computed.
- **v2 check.** `lp1_prefix_zs_m6_v2_20260923` completed 114/114 episodes with 0 crash. It recorded **0** `ask` and
  **0** `intervention` events, so its honoured-ask count is 0. The rate matches the void run's 3/114 asks, and the
  HJ-17 luna reference arms' 0.

## Amendment 4 — one LP-2 ceiling key has no plan to replay; LP-1 complete (2026-09-23 ~17:20 AEST; no registered prediction changes)

Written before any LP-2 arm has run: at 17:15 AEST the results root holds only the LP-2 ceiling and its smoke run.

- **What happened.** LP-2 jobs 25739215 (live arms) and 25739216 (prefix arms) both exited 2 at start, before any
  server came up or any episode ran. `lp_live.pbs` counts `plan` events in the ceiling, per seed, and found 57/57
  at seed 1 but **56/57 at seed 2**.
  - The missing plan is `lp2_planner_alone_cap81_qwen38_27b_20260923`, seed 2, `6171bbc_3`. Its one planner call
    returned an unparseable first plan, and the episode ended at step 0 as `parse_error` (`steps` 0,
    `n_planner_calls` 1). It is one of the ceiling's four parse errors.
  - The episode is scored, not a crash, so §3 does not refill it.
  - No other replay source used by an LP arm or a published arm has a step-0 episode. Checked: the LP-1 ceiling,
    and luna's `hj13_planner_alone_cap81` (seeds 1–2 and seed 3) and `hj1b_planner_20260915`.
- **Rule for the live arms (T, A, A1, F).**
  - Each arm still replays the ceiling's first plan for every key that has one.
  - For `2/6171bbc_3` only, the arm asks the same served planner (`Qwen/Qwen3.8-27B-FP8`, same settings) for its
    first plan live. The four LP-2 live configs carry `planner.live_plan_keys: ["2/6171bbc_3"]`
    (`CachedPacketPlanner`, `src/sidekick/agents/planner.py`).
  - `on_missing: fail` still holds for every other key.
  - The planner samples at temperature 0.7, so the four arms draw independent first plans for this key. That adds
    noise to 1 key of 114. It adds no systematic difference between arms.
- **Rule for the prefix arms.**
  - A prefix arm never calls `plan()`; it takes the plan from the replayed prefix
    (`src/sidekick/systems/loop.py:697`).
  - For this key the source has no plan and no executed action. The replayed prefix is therefore empty
    (`effective_m` = 0, `handoff_occurred` = false), and the receiver starts at step 1 with no plan. This replays
    faithfully what the planner produced.
  - `prefix_is_terminal` is false (the initial observation is not `done`, and there is no action), so the episode
    runs.
  - The plan-count check in `lp_live.pbs` no longer applies to prefix arms. Their source is checked by
    `lp_require_complete_sources`.
- **Sensitivity (not decision-bearing).** One key moves any paired mean by at most 1/114 = 0.88 pp.
  - Every LP-2 contrast and the gate are also reported with `2/6171bbc_3` excluded (113 pairs), by
    `lp_report.py`, before any LP-2 aggregate is read.
  - A reading that differs between the 114-pair and 113-pair versions is reported as **on the boundary**.
- **LP-1 complete (disclosure).**
  - All ten LP-1 arms have 114/114 episodes and 0 crashes. The zero-shot m9 arm's one crash (`2/4fab96f_1`, a
    `UnicodeEncodeError`) was refilled by job 25743506.
  - A subset run, `lp_report.py --planners P8` (labelled non-registered; `campaign/results/lp1_only_subset/`),
    was read before this amendment was written.
  - Result: **P8 (Qwen3-8B) fails the informativeness gate.** C − E = −26.23 pp, scenario [−34.73, −17.67], and
    its ceiling hit the 40-step limit in 89/114 episodes. None of these was a context overflow.
  - Per §4, P8's L1–L5 are reported and no reading is drawn from them.
  - With fewer than two planners passing the gate, `lp_report.py`'s committed reading of §4
    (`overall_claim_scope`) gives **no registered overall claim**. That reading is left unchanged. P27's L1–L5
    are read on their own rules.
  - Nothing in this amendment is chosen from P8's contrasts. The rule above concerns a key of the LP-2 ceiling
    only.

## Amendment 5 — disclosure: process statistics of the LP-2 ceiling were computed (2026-09-23 ~18:15 AEST; no registered item changes)

- **Why.** To explain P8's gate failure, `scripts/analysis/lp_planner_diagnostic.py` computed process statistics
  for the luna, P8 and P27 ceilings, the tailored executor alone, and P8's prefix arms (run ~17:56 and again
  ~18:14 AEST; `campaign/results/lp_planner_diagnostic_20260923.json`; ledger LP-MECH-01/02).
- **What was seen of LP-2.** For the P27 ceiling the script prints no outcome: no `goal_pass`, TGC, `error_type`
  or step count. Its process statistics were seen:
  - credential look-up (`apis.supervisor.show_account_passwords`) in 106/114 episodes;
  - a placeholder-like credential in 14;
  - 57.1 % of CODE observations failed;
  - COMPLETE in 74;
  - 5 episodes whose last ten actions executed nothing, and 36 that repeat one action ≥ 5 times;
  - 88.9 % of its actions are CODE.

  Its 35 step-limit episodes were already known from the completeness check (job 25724763).
- Amendment 4 asks for the 113-pair sensitivity "before any LP-2 aggregate is read". These are aggregates of the
  LP-2 ceiling, though none is the gate quantity or an L-contrast, so they are disclosed here.
- **Nothing was chosen after them.** LP-2 live job 25748167 was running and prefix job 25748168 was queued, both
  submitted under Amendment 4 before the diagnostic ran. No rule, arm, key or threshold changes. P27's gate and
  L1–L5 are read only from `lp_report.py`, as registered.

## Amendment 6 — disclosure: a provisional `lp_report.py` run before the m11 refill (2026-09-24 ~18:10 AEST; no registered item changes)

- **What ran.** `lp_report.py --date 20260924` (both planners, the registered defaults), in PBS job 25837120, output to
  the job's scratch directory, not to `campaign/results/`.
  - At that time `lp2_prefix_zs_m11_v2_20260923` and `lp2_prefix_bplus_m11_v2_20260923` held 112/114 non-crashed
    episodes each (2 crashed each), with the refill (PBS 25832832) still queued.
  - The script reported `INCOMPLETE` (exit 1), as §3 requires. L2–L5 carried no reading, and L1 carried "none
    (Holm family incomplete)".
- **What was seen:**
  - The P27 gate passes: C − E = +5.18 pp, scenario [−6.24, +15.74].
  - L1's unadjusted interval: T − A = +8.93 pp, scenario [+2.37, +16.58], task [+3.00, +15.22].
- **Why it was run.** To decide whether to register J11, a `test_normal` replication of this family with P27
  (`docs/plan_top_venue_20260924.md` §6 DA), before any `test_normal` episode exists. Nothing in this registration
  was chosen from it.
- **What does not change.** The registered read is the rerun after the refill. L1–L5 and their readings come only
  from that run. The P27 L1 verdict is taken from the full Holm family, never from the unadjusted interval above.
