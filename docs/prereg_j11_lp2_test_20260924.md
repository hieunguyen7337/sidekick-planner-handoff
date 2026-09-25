# J11 — the LP-2 local planner on held-out `test_normal`: a registered replication of the LP family

**Status**: **FROZEN** on commit, 2026-09-24, together with J12 (`docs/prereg_j12_depth_test_20260924.md`), on the user's decision of 2026-09-24 to freeze J11 now, on the provisional LP-2 dev read. Checked at freeze: `/scratch/n12194778/sidekick/results` holds 13 `j10_*` campaigns, all `_dryrun`, and no `j11_*` or `j12_*` campaign; `test_normal` unread by any J11 script; `test_challenge` sealed. Amendments are appended below the end marker, never edited in.

Written 2026-09-24. Plan: `docs/plan_top_venue_20260924.md` §3 and §6 DA.
Dev registration it replicates: `docs/prereg_lp_planner_strength_20260923.md` ("LP"), whose §2–§4 this file
mirrors and cites instead of restating.

## 1. Why

- **The question.** J10 (A1 + Amendment 1) tests the channel and depth predictions on `test_normal` with one
  planner, the hosted `gpt-5.6-luna`. LP tested the same channel contrast on dev with two local planners:
  - P8 (Qwen3-8B) failed LP's informativeness gate (LP Amendment 4);
  - P27 (Qwen/Qwen3.8-27B-FP8) passed it.

  J11 asks whether P27's result holds on held-out data. If it does, "the action channel beats advice" is a
  held-out result for two planners, one of them open-weight.
- **What was known when this was written** (disclosed in full in LP Amendment 6). A provisional `lp_report.py` run,
  before the refill of two m11 prefix arms, showed:
  - the P27 gate passing, C − E = +5.18 pp, scenario [−6.24, +15.74];
  - L1 with an unadjusted T − A = +8.93 pp, scenario [+2.37, +16.58].

- **Also seen, on 112 pairs before the refill** (LP Amendment 7, through `j11_power.py`): L2–L5's provisional
  values, quoted in §4. L2 points the opposite way. L3 and L5 are near zero: on dev, P27's m6 → m11 depth span
  is flat.
- **Frozen on the provisional read.** J11 is frozen on that provisional read, by the user's decision of 2026-09-24,
  before the refill lands. GPU queueing would otherwise hold every `test_normal` run for days.
  - The refill (PBS 25832832) touches only the two M^r_11 arms (4 crashed episodes).
  - The gate (C − E) and L1 (T − A) use none of those arms, so the two values this decision rests on are final.
  - The registered LP-2 dev read (`lp_report.py` after the refill) will be appended below the end marker as an
    information-only note once it exists. It changes nothing registered here.
- **Chosen in view of dev.** Every prediction below is LP §4's, unchanged, and was registered before any LP-2
  arm ran. The only choices made after seeing LP-2 dev are to run J11 at all, and which arms to carry (§2). Power
  is quoted at the dev effect and at half of it (§5).

## 2. Planner, harness and arms

- **Planner:** P27, served by vLLM with LP §2's settings (context handling, structured plan call, temperature).
  In C it has one H100 to itself, as on dev; in every replay arm it sits on a second H100 beside the executor.
- **Executor:** `ibm-granite/granite-4.2-8b`, receivers `sft_b_plus` (tailored, the adapter J10 A1 §4 pins) and
  base (untailored).
- **Split and pairing:** AppWorld `test_normal`, all 168 tasks × seeds 1, 2 = **336 pairs** per arm, paired by
  `(task_id, seed)`, 56 scenario clusters.

| code | arm | config | campaign |
|---|---|---|---|
| **C** | P27 acting alone, cap 81; the source of every other arm's plan and prefix | `configs/j11_planner_alone_cap81_qwen38_27b.yaml` | `j11_planner_alone_cap81_qwen38_27b_20260924` |
| **T** | takeover at k = 10; replays C's first plan | `configs/j11_takeover_fixed_k_10.yaml` | `j11_takeover_fixed_k_10_20260924` |
| **A** | prose advice at k = 10, full context | `configs/j11_advise_fixed_k_10_fullctx.yaml` | `j11_advise_fixed_k_10_fullctx_20260924` |
| **A1** | prose advice at every step, full context | `configs/j11_advise_fixed_k_1_fullctx.yaml` | `j11_advise_fixed_k_1_fullctx_20260924` |
| **M^r_m** | the executor re-runs C's first m actions, then continues; r ∈ {bplus, zs}, m ∈ {6, 11} | `configs/j11_prefix_{bplus,zs}_m{6,11}.yaml` | `j11_prefix_{bplus,zs}_m{6,11}_20260924` |
| **E** | the tailored executor alone. **Not a J11 arm**: J10's arm 1b on the same split | `configs/j10_executor_alone_bplus.yaml` | `j10_executor_alone_bplus_20260924` |

- **Not run on test:**
  - LP's F (plan only), which is descriptive in LP;
  - m = 9, which no L contrast uses.
- **Planless keys** (C episodes scored without a plan, as LP Amendment 4's `2/6171bbc_3`):
  - T, A and A1 take a live first plan from the same served planner for exactly those keys
    (`on_missing: call_if_planless`, J10 A1 §4.2's mechanism).
  - Prefix arms replay an empty prefix for them (LP Amendment 4, rule for the prefix arms).
  - If more than 16 of C's 336 episodes (5 %) are planless, no replay arm starts, and J11 is reported as not
    run.
- **Executor asks.** Answered by the served planner, as on dev (LP Amendment 2). They are counted and bounded as
  J10 A1 Amendment 1 §I bounds live asks:
  - an answered ask is a planner `intervention` event with `forced` false, in the attempt that wrote the result;
  - each arm's bound is its episodes with an answered ask, divided by 336;
  - a contrast side at 1.00 pp or more is stated in the same sentence as that contrast's reading.

  Reporting only; no reading changes.

## 3. Estimation

As LP §3, with these changes of scale:
- 336 pairs and 56 scenario clusters.
- **Sign-flip sensitivity:** `cluster_inference.registered_signflip` as J10 A1 §5.5 applies it at 56 clusters.
  Not decision-bearing.
- **Crashes:** only `error_type == "crash"` is dropped and refilled (resumption, not re-reading). A contrast
  whose arms lack 336 non-crashed pairs is **incomplete** and draws no reading.
- **Holm:** across L1–L5, a single family of m = 5.
- **POOL-04:** as LP §3.
- **Planless-key sensitivity** (not decision-bearing): every contrast and the gate are also reported with C's
  planless keys excluded. A reading that differs between the two is **on the boundary**.

## 4. Gate, contrasts and predictions

LP §4 applies verbatim, with E read from J10's arm 1b.

| id | contrast | predicted | LP-2 dev value (P27; provisional, LP Amendments 6 and 7) |
|---|---|---|---|
| gate | C − E | point > 0, or P27 is **too weak to test the channel** on test, and no reading is drawn | +5.18 pp, scenario [−6.24, +15.74] (114 pairs) |
| **L1** | T − A | **> 0** | +8.93 pp, scenario [+2.37, +16.58] (114 pairs; unadjusted, because the Holm family was incomplete) |
| **L2** | A1 − M^bplus_11 | **< 0** | +10.11 pp, scenario [+2.41, +18.20] (112 pairs, incomplete): **the opposite side** |
| **L3** | M^bplus_11 − M^bplus_6 | **> 0** | +0.16 pp, scenario [−7.03, +7.70] (112 pairs, incomplete) |
| **L4** | C − M^bplus_11 | **upper bound < +7.00 pp** | −1.05 pp, scenario [−10.52, +8.97] (112 pairs, incomplete) |
| **L5** | M^zs_11 − M^zs_6 | **> 0** | −0.12 pp, scenario [−8.86, +8.19] (112 pairs, incomplete) |

The L2–L5 values were seen through `j11_power.py`, which reads P27 only through `lp_report.py`'s functions (LP
Amendment 7). The predictions stand as LP §4 registered them, although dev points against L2 and gives L3 and
L5 almost nothing. J11 is a replication, so a prediction the dev data does not favour is carried, not dropped.
§5 gives its power.

**Readings: LP §4 applies verbatim.**
- **L1 replicates**, **fails to replicate**, or is **reversed** (a reversal is reported as a primary finding).
- L2–L5 qualify the L1 reading but do not rescue a failed L1.
- **The combined statement with J10:**
  - If J10's P6 (takeover − correction advice at k = 10, luna) is supported and J11's L1 replicates, the paper
    states that the channel result holds on held-out data for two planners.
  - If exactly one holds, the paper says which.
  - If neither holds, that is the generality result.

**Reported beside the predictions (not decision-bearing).** These follow J10 Amendment 1 §B and §D.
- L3, L4 and L5 each get a handoff-only companion: Σd·h / Σh, with h from the prefix arm.
- L1 is reported with:
  - each arm's `limit` rate;
  - the split into pairs where either arm hit `limit` and pairs where neither did (post-treatment);
  - a limit-as-0 sensitivity.

## 5. Power at the test design

Source: `campaign/results/j11_power_dev_20260924.report.json`, key `power_table`, built by
`scripts/analysis/j11_power.py`.
- **Method.** LP-2 dev pairs were resampled by scenario to 56 scenarios × 2 seeds, and the §3–§4 analysis was
  applied to each of 1,000 simulated reads, at 2,000 draws each.
- **Inputs.** 114 pairs for the gate and L1; 112 for L2–L5 (before the refill).
- **What "power" counts.** An L row counts a read only if the gate passes **and** the registered supporting reading
  holds under Holm (m = 5).
- **Not simulated.** POOL-04 and the planless-key sensitivity. Both can only withhold a reading, so the table is an
  upper bound in that respect.

| item | power at the dev effect | at half the dev effect |
|---|---|---|
| gate passes | 0.951 | 0.781 |
| L1 replicates | 0.948 | 0.317 |
| L2 supported | 0.000 | 0.000 |
| L3 supported | 0.017 | 0.005 |
| L4 supported | 0.579 | 0.058 |
| L5 supported | 0.010 | 0.010 |
| gate and all five supported | 0.000 | 0.000 |

- **L1** is the question J11 exists for, and it is well powered at the dev effect.
- **L2–L5.** Their support is not expected at the dev values. A reading against them (for example L2 reversed)
  is reported under LP §4's readings. It qualifies the L1 statement and never rescues or sinks it.

## 6. Order, compute and abort rule

- **Order.** C first. When C has 336 non-crashed episodes and 0 crashed, T, A, A1 and the four prefix arms run in
  any order.
- **Compute.** GPU only, one arm per job, `scripts/pbs/j11_arm.pbs`: 1 × H100 for C (the planner alone), 2 × H100
  for every replay arm (executor and planner). The wrapper refuses a replay arm that sees fewer than two cards.
  **Zero hosted calls.**
- **Abort rule.** J11 is reported as **not run** if C cannot reach 336 non-crashed episodes, or if more than 16
  C episodes are planless.
- **Pinned checkout.** Every J11 arm runs from a checkout pinned at a commit, with a clean `src/`, `scripts/`
  and `configs/`, as J10 does.
  - That commit is not J10's pin (a8b63f0), from which E (J10 arm 1b) runs.
  - Checked at freeze: the `src/` changes between the two pins are a `structured` advice style that no J10 or J11
    arm uses, and a configurable script for the mock executor (`MockExecutor.from_config`, used only by
    `type: mock` executors).
  - The executor, the prefix replay and the correction prompt are identical at both pins.
- **Dry run after freeze.** A `DRYRUN=1` plumbing run on dev (3 tasks, `_dryrun` campaign ids) precedes C on
  `test_normal`, but follows this freeze.
  - A plumbing fault it finds is fixed in code, and the fixed commit becomes the pinned checkout.
  - A fault that would change anything registered here is handled by an appended amendment, before any J11
    `test_normal` episode exists.
- **Freeze gate.** `j11_arm.pbs` refuses `test_normal` unless this file has exactly one `**Status**` line beginning
  FROZEN, is committed and unmodified, and `J11_CONFIRM=J11_FROZEN` is set.
- **Read.** `scripts/analysis/j11_report.py --split test_normal --confirm-heldout-test-split`, run once all of
  C, T, A, A1, the prefix arms and J10's arm 1b are complete. Its output is
  `campaign/results/j11_lp2_test_normal.report.json`.

## 7. Not claimed

- No cost or token comparison between P27 and luna (LP §2).
- Nothing about `test_challenge`, which stays sealed.
- No claim about any planner other than P27 and luna.

*J11 ends.*

## Amendment 1 — the handoff indicator of L3–L5's companions (2026-09-24, appended before any J11 `test_normal` episode exists; reporting only: no arm, prediction, rule, threshold, Holm family, seed, order or abort rule changes)

**Why.** §4's handoff-only companions for L3, L4 and L5 take h from the prefix arm. The only such indicator the
runner records is `handoff_occurred`.
- That flag is `effective_m < n_source_actions` (`src/sidekick/prefix_source.py:184`).
- It is false whenever the replayed source made at most m executed actions, including a planless key, even though
  the loop then hands the executor control (`src/sidekick/systems/loop.py:743-756`).
- J10 A1 Amendment 3 records the finding and its dev evidence.
- It matters more for this planner than for luna. On dev the LP-2 planner alone ended at the step limit in 35 of
  114 episodes (PBS 25724763), and those are exactly the sources the flag misclassifies.

**Change.**
- In L3–L5's handoff-only companions, h is **h\***: the prefix episode's loop ran its live phase after the replayed
  prefix.
  - It is read from that episode's own events by `scripts/analysis/handoff_control.py`.
  - It is validated on dev against `prefix_is_terminal` (ledger HSTAR-01).
- The `handoff_occurred` version is printed beside each as a flag sensitivity.
- The companions stay reporting-only. `scripts/analysis/j11_report.py` implements this.

**Runtime.** Nothing the arms execute changes. J11's arms run from the checkout pinned at 6f40fec.

**Checked at commit.** No `j11_*` campaign exists under `/scratch/n12194778/sidekick/results`.

*Amendment 1 ends.*

## Amendment 2 — a replay that cannot pass its own check (2026-09-25, appended after C's `test_normal` episodes began and before any episode of a replay arm (T, A, A1, M^r_m) exists; one completeness rule for one named crash class; no arm, prediction, rule, threshold, Holm family, seed, order or abort rule above any end marker changes)

### §A What was found, and what had been seen
- J10 A1 Amendment 5 §A (committed with this amendment) records the mechanism. A prefix replay is checked by a
  hash of the printed execute output, not of the database. Printed text that varies between processes, such as
  an object's memory address or the order of a printed `set`, therefore fails the check on every attempt,
  although the world is identical.
- **It is the reason LP's registered read is incomplete.** Two P27-sourced dev keys, `68ee2c9_2` and
  `df61dc5_2`, fail both m = 11 replay arms deterministically, which left M^bplus_11 and M^zs_11 at 112/114
  (LP-05, DIV-01). J11's §4 dev values for L2–L5 are those 112-pair values, disclosed in LP Amendment 7.
- **J11 is more exposed than J10.** C is a P27 source, and on dev 2 of 114 P27 episodes printed such text within
  their first 11 steps, against 0 of 285 luna episodes (DIV-01). At that rate an m = 11 arm would lose about 6 of
  336 keys. No dev P27 episode printed such text within its first 6 steps.
- **Test contact at commit.** C (PBS 25845109) has written `test_normal` episodes. Only the wrapper's tally lines
  have been read: counts of non-crashed, crashed and missing episodes, and no episode's content, output or
  score. No replay arm has run on `test_normal`, and the rule below depends only on the source's printed output
  and on process state, never on any arm's outcome.

### §B The rule (the same rule as J10 A1 Amendment 5 §B, applied to J11)
1. **Divergent key.** For a prefix replay arm M^r_m, a `(task_id, seed)` whose episode, after at least one
   crash-only resumption run after the crash was first recorded, still has `error_type == "crash"` and, in its
   last attempt's events, an `error` event whose `payload.reason` is `replay_divergence`. No other crash
   qualifies. T, A and A1 replay only C's first plan, not the environment, and cannot produce one.
2. **Exclusion.** A divergent key is removed from both arms of every paired contrast, companion and sensitivity
   in which that arm is one of the two arms (L2–L5, their h* companions under Amendment 1, and the planless-key
   sensitivity). A contrast between two prefix arms (L3, L5) removes the union of their divergent keys. The gate
   and L1 use no prefix arm and keep all 336 pairs.
3. **Completeness.** A prefix arm whose only residual crashes are divergent keys is complete. §3's rule ("a
   contrast whose arms lack 336 non-crashed pairs is incomplete") is read with divergent keys removed. A contrast
   that removes **at most 16** keys (a fixed number: 5 % of 336, as §6's planless cap) is read on its remaining
   pairs; above that it is **incomplete**. Any other residual crash still makes it incomplete. L1–L5 are one Holm
   family (§3), so one incomplete member leaves every L without a reading, as it did in LP.
4. **Unchanged.** The bootstrap, the Holm family and its m, thresholds, POOL-04 and the sign-flip test run as
   registered, on the remaining pairs. The estimand of an affected contrast is over the keys whose prefix
   replays.
5. **Reported regardless of outcome:** each prefix arm's divergent keys, listed, and their count, including zero,
   and for each affected contrast its number of pairs.
6. **Not retroactive.** LP's registered read stays as reported (INCOMPLETE; LP-04, LP-05). This rule is
   registered for J11 only.

### §C Code
- The definition is J10 A1 Amendment 5 §D's `scripts/analysis/replay_divergence.py`, and the arm-level
  completeness rule is `j10_report.a1_am5_arms`.
- `scripts/analysis/j11_report.py`: `am2_evaluate_contrast` (:356-381) reads a contrast with its divergent keys
  removed, against 336 minus their number, using lp_report's statistics unchanged. `am2_block` (:384-430) is
  reported under the key `j11_am2_divergence` (:630).
- With no divergent key, `lp_report.evaluate_contrast` is called exactly as before.
- Tests in `tests/unit/test_j11_report.py`: `test_am2_no_divergent_key_changes_nothing_but_adds_the_block`,
  `test_am2_one_divergent_key_reads_its_contrasts_on_335_pairs`, `test_am2_two_prefix_arms_remove_the_union`,
  `test_am2_more_than_16_divergent_keys_leave_the_contrast_incomplete`,
  `test_am2_a_divergent_key_plus_an_ordinary_crash_is_incomplete`.

*Amendment 2 ends.*

## Pointer update after Amendment 2 (2026-09-25, before any J11 read; pointers only, no rule changes)

The pre-read audit of `scripts/analysis/j11_report.py` against this document found every registered rule
implemented as written. The fixes it led to added report-level checks and printed text only, and moved code
lines. Amendment 2 §C's line pointers now read:
- `am2_evaluate_contrast`: `:400` (was `:356-381`);
- `am2_block`: `:428` (was `:384-430`);
- the report key `j11_am2_divergence`: `:887` (was `:630`).

Names, rules and tests are unchanged. The fixes also add `--divergent-refill-confirmed`. A registered read that
finds a divergent key and does not carry that flag is INCOMPLETE until an operator has confirmed the §B.1
condition from the wrapper's tally lines: at least one crash-only resumption run after the crash.

*Pointer update ends.*

## Read log: a premature invocation (2026-09-25, disclosed before the registered read)

- **What happened.** At 18:33 AEST on 2026-09-25 (HEAD 2accc53), `j11_report.py --split test_normal
  --confirm-heldout-test-split` was invoked before J10's arm 1b (`j10_executor_alone_bplus_20260924`, this
  document's E) existed. §6 (:167-168) runs the read only once all arms are complete. At the time C, T, A, A1 and
  the four prefix arms were each complete at 336/336 non-crashed.
- **What the report did.** It stopped with status `MISSING_CAMPAIGNS`, exit 3. The gate and L1 were not
  evaluable. It still computed the contrast rows that do not involve E and wrote them to the default output path.
- **What was seen.** Only the status and the headline line. No contrast value was viewed.
- **What was done.**
  - The two output files were moved, unread, out of `campaign/results/` into the gitignored
    `campaign/workers/logs/quarantine_j11_premature_20260925/`, with a note.
  - The report is being changed so that a registered read with a missing campaign stops before computing anything.
- **Effect.** The registered read runs once, after J10 arm 1b is complete, with the analysis as frozen here. The
  contrasts that do not involve E are deterministic functions of complete arms at fixed seeds. The premature run
  therefore offered no choice to make, and its unseen numbers will be reproduced exactly.

*Read log ends.*
