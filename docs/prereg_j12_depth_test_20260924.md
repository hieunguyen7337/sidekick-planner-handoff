# J12 — prefix depth m = 6 → m = 11 on held-out `test_normal`: the dev depth span, registered

**Status**: **FROZEN** on commit, 2026-09-24, together with J11 (`docs/prereg_j11_lp2_test_20260924.md`), on the user's decision of 2026-09-24 to register the m = 6 arms and freeze J12 with J11. Checked at freeze: `/scratch/n12194778/sidekick/results` holds 13 `j10_*` campaigns, all `_dryrun`, and no `j11_*` or `j12_*` campaign; `test_normal` unread by any J12 script; `test_challenge` sealed. Amendments are appended below the end marker, never edited in.

Written 2026-09-24. The user decided on 2026-09-24 to register it. It runs on J10's test protocol,
`docs/prereg_j10_amendment_20260924.md` ("A1", with its Amendment 1), and cites that protocol instead of
restating it.

## 1. Why, and what was known

- **The question.** On held-out tasks, does handing control to the executor after 11 replayed planner actions
  instead of 6 raise quality, over all episodes and over the episodes that actually hand off?
- **Why J10 does not answer it.**
  - J10 runs prefix arms at m = 9 and m = 11 only (arms 4–7).
  - Its one depth prediction, P4 (untailored m9 → m11), has power 0.182 (Holm) at the dev effect
    (`campaign/results/am1_power_dev_20260923.report.json`, `power_at_dev_effect.per_contrast.P4.holm_supported`).
  - The dev result that survives multiplicity is the m6 → m11 span, and it has no held-out test.
- **What was known when this was written.** All values below are dev and exploratory. Source:
  `campaign/results/j17_depth_fixes_20260924.report.json`, keys
  `handoff_only_contrasts.{bplus,zs}.m6_to_m11.goal_pass.{all,handoff_only}`, ledger HO-04 and HO-06.
  Cap-81 prefix family, seeds 1–3, 171 pairs.

  | receiver | all episodes (171 pairs) | handoff-only (71 pairs) |
  |---|---|---|
  | tailored (`sft_b_plus`) | +8.39 pp, scenario [+4.20, +12.63] | +12.03 pp, scenario [+5.49, +18.57] |
  | untailored (base) | +7.70 pp, scenario [+3.69, +12.06] | +13.93 pp, scenario [+5.12, +21.22] |

  - All four survive Benjamini–Yekutieli across 28 dev `goal_pass` contrasts (ledger FDR-01).
  - At m = 11, 100 of 171 dev episodes never hand off (ledger HO-01).
- **The other planner points the other way.** With the open-weight planner P27, the same span on dev is flat:
  - tailored +0.16 pp [−7.03, +7.70];
  - untailored −0.12 pp [−8.86, +8.19];
  - both over all episodes, 112 pairs, provisional before the LP-2 refill (LP Amendments 6 and 7; J11 L3 and L5).

  J12 tests the depth span only for the prefixes of J10's planner (`gpt-5.6-luna`, arm 3). A J12 result says
  nothing about other planners, and J11 L3 / L5 carry that question.
- **Chosen in view of dev.** The contrast, the direction and the two populations were chosen after seeing the
  table above, and after J10 froze. Nothing else was chosen from dev:
  - the estimation, multiplicity, completeness and crash rules are A1's;
  - the handoff-only estimand is A1 Amendment 1 §B's.
- **Also known when this was written, and not a J12 question.** On dev, the same planner alone at `high` reasoning
  effort scores well above the medium-effort planner every J10/J12 prefix replays (dev arm
  `dev_planner_alone_cap81_high_20260924`; exploratory). J12 compares two depths of the same medium-effort prefixes
  and makes no comparison with any planner-alone arm, so this bears on no D.

## 2. Arms

| code | arm | config | campaign |
|---|---|---|---|
| **M^bplus_6** | tailored executor (`sft_b_plus`, the adapter A1 §4 pins) replays arm 3's first 6 actions, then continues | `configs/j12_prefix_m6.yaml` | `j12_prefix_m6_20260924` |
| **M^zs_6** | the same with the untailored base executor | `configs/j12_prefix_zs_m6.yaml` | `j12_prefix_zs_m6_20260924` |
| M^bplus_11 | **not a J12 arm**: J10 arm `prefix_m11` | `configs/j10_prefix_m11.yaml` | `j10_prefix_m11_20260924` |
| M^zs_11 | **not a J12 arm**: J10 arm `prefix_zs_m11` | `configs/j10_prefix_zs_m11.yaml` | `j10_prefix_zs_m11_20260924` |

- **Configs.** Each J12 config is its J10 m = 9 source with only `campaign_id` and the prefix depth changed. The
  file header lists the changed keys, and `tests/unit/test_j12_configs.py` checks them.
- **Pairs.** AppWorld `test_normal`: 168 tasks × seeds 1, 2 = **336 pairs** per contrast, paired by
  `(task_id, seed)`.
- **Hosted calls.** Both J12 arms replay J10 arm 3 (`j10_planner_alone_cap81_20260924`). Their only possible
  hosted calls are live answers to executor asks, handled exactly as A1 Amendment 1 §I handles arms 4–7: kept,
  counted and bounded.
- **Planless keys.** Handled as A1 §4.2 item 2 handles arms 4–7: a planless key replays an empty prefix. A1
  §4.2 item 5's cap of 16 applies; above it, no J12 arm starts.

## 3. Estimation

A1 §5.2–§5.5 applies unchanged:
- paired percentile bootstrap, 10,000 resamples, seed **20260924**;
- scenario clustering primary and governing every rule, task clustering secondary;
- `goal_pass` primary, TGC secondary;
- POOL-04 (§5.4) and the sign-flip sensitivity (§5.5), neither decision-bearing;
- A1 §4.2 item 4's key-exclusion sensitivity.

Specific to J12:
- **Handoff-only estimand** (A1 Amendment 1 §B): Σ d·h / Σ h over pairs, with d = m11 − m6 and h = 1 when the
  **m = 11 arm's** episode handed off (`handoff_occurred`). Whole clusters are resampled.
- **Completeness and crashes** (A1 §9). A contrast whose two arms lack 336 non-crashed pairs is **incomplete**
  and draws no reading. Only `error_type == "crash"` is dropped and refilled.
- **Multiplicity.** D1–D4 form **one Holm family of m = 4**, J12's own.
  - It does not enter A1's P-family or Amendment 1's CF family, so neither's α changes.
  - Each member's p is A1 §5.3's `direction="greater"` form at threshold 0.
  - An interval condition is met only if the unadjusted 95 % scenario interval meets it **and** the Holm-adjusted
    p ≤ 0.05 (A1 §5.3).

## 4. Predictions

| id | contrast (`goal_pass`) | population | predicted | dev value (§1) |
|---|---|---|---|---|
| **D1** | M^bplus_11 − M^bplus_6 | all 336 pairs | **> 0**: lower bound above 0 | +8.39 pp |
| **D2** | M^zs_11 − M^zs_6 | all 336 pairs | **> 0** | +7.70 pp |
| **D3** | M^bplus_11 − M^bplus_6 | handoff-only (h from M^bplus_11) | **> 0** | +12.03 pp |
| **D4** | M^zs_11 − M^zs_6 | handoff-only (h from M^zs_11) | **> 0** | +13.93 pp |

**Readings, fixed now:**

| outcome | reading |
|---|---|
| D1 and D3 supported | on held-out tasks, a later handoff raises the tailored executor's quality, and not only through episodes the planner finishes itself |
| D1 supported, D3 not | the held-out depth gain is not shown on real handoffs; it may rest on the planner finishing |
| D1 not supported | the dev depth span does not replicate on held-out tasks for the tailored executor |
| D2 / D4 | the same readings for the untailored executor |

A prediction that is not supported is reported as **not replicated**, never as evidence of no effect. A reversal
(the unadjusted 95 % scenario interval's upper bound below 0) is reported as a primary finding. It is read from that
interval alone, with its one-sided `direction="less"` p printed unadjusted, because the family's Holm p tests the
predicted direction only.

**Reported beside the predictions (not decision-bearing):**
- TGC for each of D1–D4;
- the silenced count of each arm (episodes with no handoff);
- the decomposition of each all-episode span into handoff and silenced contributions;
- per-arm `limit` rates;
- Amendment 1 §I's live-ask count and bound for each J12 arm.

## 5. Power at the test design

Source: `campaign/results/j12_power_dev_20260924.report.json`, key `power_table`, built by
`scripts/analysis/j12_power.py`.
- **Method.** Dev pairs (§1's family: 171 pairs, 71 handoff pairs, 19 scenarios, 0 crashes) were resampled by
  scenario to 56 scenarios × 2 seeds. §3–§4's analysis was applied to each of 1,000 simulated reads, at 2,000
  draws each, seed 20260924.
- **Half effect.** Each D's per-pair differences shifted down by half its dev value (key `half_effect_shift_pp`).
- **What "power" counts.** A read supports a D only if its registered condition holds under Holm (m = 4).
- **Check.** The dev values the script reproduced match §1's table (key `dev_check_against_j17`).

| item | power at the dev effect | at half the dev effect |
|---|---|---|
| D1 | 1.000 | 0.672 |
| D2 | 0.999 | 0.601 |
| D3 | 0.998 | 0.604 |
| D4 | 0.987 | 0.515 |
| all four supported | 0.985 | 0.328 |

At the dev effect J12 is near-certain to support all four. At half of it, each D is roughly a coin flip or
better, and a "not replicated" reading is then a statement about effect size, not evidence of no effect (§4).

## 6. Order, compute, abort rule and freeze gate

- **Order.**
  - J12's arms start only after J10 arm 3 is complete: 336 non-crashed pairs and 0 crashed.
  - They start after A1 §4.2's planless-key cap has been checked.
  - They may run in parallel with J10's GPU arms.
- **Compute.** GPU only: 1 × H100 per arm, one arm per job, through `scripts/pbs/j12_arm.pbs`.
  - That wrapper checks this file's freeze gate and, on `test_normal`, that arm 3 is complete and within the
    planless-key cap (the order rule above). It refuses otherwise, before any server starts.
  - It then hands the job to `scripts/pbs/j10_arm.pbs`, whose A1 gates, smoke, crash-only refill and tally then
    apply. `j10_arm.pbs` accepts a `j12_prefix_*` config only from `j12_arm.pbs`, after that gate.
- **Abort rule.** J12 is reported as **not run** if arm 3 cannot complete, or if the planless-key cap is
  exceeded. A single D is reported **incomplete** if its arms cannot reach 336 non-crashed pairs.
- **Pinned checkout.** J12 arms run from a checkout pinned at a commit, with a clean `src/`, `scripts/` and
  `configs/`, as J10 does.
  - That commit is not J10's pin (a8b63f0), from which J10's m = 11 arms run.
  - Checked at freeze: the `src/` changes between the two pins are a `structured` advice style that no J10 or J12
    arm uses, and a configurable script for the mock executor (`MockExecutor.from_config`, used only by
    `type: mock` executors).
  - The prefix replay, the vLLM executor and the correction and neutral prompts are identical at both pins.
- **Dry run after freeze.** A `DRYRUN=1` plumbing run on dev (3 tasks, `_dryrun` ids) precedes the test arms but
  follows this freeze. A fault that would change anything registered here is handled by an appended amendment,
  before any J12 `test_normal` episode exists.
- **Freeze gate.** `j12_arm.pbs` refuses `test_normal` unless all of these hold:
  - this file has exactly one `**Status**` line, beginning FROZEN;
  - it is committed and unmodified;
  - `J12_CONFIRM=J12_FROZEN` is set.
- **Read.** `scripts/analysis/j12_report.py --split test_normal --confirm-heldout-test-split`, once both J12 arms
  and J10's `prefix_m11` and `prefix_zs_m11` are complete. Output:
  `campaign/results/j12_depth_test_normal.report.json`.

## 7. Not claimed

- **Non-inferiority to the planner alone.** That is A1's P3, with Amendment 1 §B's handoff-only companion
  reported beside it. J12 adds no margin.
- **The shape of the depth curve**, including any breakpoint. J12 has two depths per receiver.
- **Anything about a planner other than `gpt-5.6-luna`** (see §1).
- Nothing about `test_challenge`, which stays sealed.

*J12 ends.*

## Amendment 1 — the handoff indicator of D3 and D4 (2026-09-24, appended under §6's fault clause before any J12 `test_normal` episode, and before any episode of J10's prefix arms, exists; D3/D4's population is corrected to the one §1 names; no arm, depth, receiver, direction, Holm family, estimation rule, seed, order or abort rule changes)

**Why.** §1 asks whether a later handoff raises quality "over the episodes that actually hand off". §3 implements
that with h = the m = 11 episode's `handoff_occurred`.
- That flag is `effective_m < n_source_actions` (`src/sidekick/prefix_source.py:184`), counting only the source's
  executed actions.
- The loop, however, skips the executor only when the replayed prefix is terminal (`src/sidekick/systems/loop.py:743-756`).
- So the flag is false for live handoffs in two cases:
  - a source that made at most m executed actions and did not finish;
  - a planless key.
- The flag therefore does not measure what §1 names. J10 A1 Amendment 3 records the finding and its dev evidence.

**Change.**
- In §3's handoff-only estimand and in D3 and D4, h is **h\***: h = 1 iff the m = 11 episode's loop ran its live
  phase after the replayed prefix (the executor took control).
  - It is read from that episode's own events by `scripts/analysis/handoff_control.py`.
  - On dev it agrees with `prefix_is_terminal` recomputed on the source in 171 of 171 episodes in each of the six
    cap-81 arms (ledger HSTAR-01).
- The `handoff_occurred` versions are reported beside them as a flag sensitivity (`D3_flag`, `D4_flag`), in their
  own Holm re-read of four. They are not decision-bearing.
- D1, D2, the readings table and every other rule are unchanged.
- `scripts/analysis/j12_report.py` implements this.

**What was known when this was written (dev, exploratory; `campaign/results/j17_hstar_20260924.report.json`, key
`handoff_only_contrasts.{bplus,zs}.m6_to_m11.goal_pass.handoff_only`; ledger HSTAR-15).** It replaces §1's
handoff-only column and §4's dev values for D3 and D4.

| | flag (§1 as frozen) | h* |
|---|---|---|
| D3, tailored, handoff-only | +12.03 pp, 71 pairs | **+7.66 pp**, 88 pairs, scenario [+1.19, +14.06], task [+0.80, +14.69] |
| D4, untailored, handoff-only | +13.93 pp, 71 pairs | **+7.81 pp**, 88 pairs, scenario [+0.79, +13.95], task [−0.02, +15.57] |

**Power at the test design, re-run with h\*** (`campaign/results/j12_power_dev_hstar_20260924.report.json`, key
`power_table`).
- Same method, settings and seed as §5.
- The frozen §5 file is reproduced exactly when the script is run with the flag.

| item | at the dev effect | at half the dev effect |
|---|---|---|
| D1 | 0.999 | 0.643 |
| D2 | 0.997 | 0.566 |
| D3 | 0.866 | 0.299 |
| D4 | 0.819 | 0.242 |
| all four supported | 0.733 | 0.125 |

- D1 and D2 move only through Holm.
- D3 and D4 are now less than certain at the dev effect, and weak at half of it. §4's rule stands: a D that is
  not supported is reported as **not replicated**, never as evidence of no effect.

**Runtime.** Nothing the arms execute changes. J12's arms run from the checkout pinned at 6f40fec. The read uses
`j12_report.py` as committed with this amendment.

**Checked at commit.**
- The only non-`_dryrun` `j10_*` / `j11_*` / `j12_*` campaigns under `/scratch/n12194778/sidekick/results` are J10
  arm 3 (`j10_planner_alone_cap81_20260924`, incomplete, 81 of 336 non-crashed) and its smoke.
- No arm-3 result was read beyond the disclosure in A1 Amendment 3.

*Amendment 1 ends.*

## Amendment 2 — a replay that cannot pass its own check (2026-09-25, appended before any J12 `test_normal` episode exists; one completeness rule for one named crash class; no arm, prediction, rule, threshold, Holm family, seed, order or abort rule above any end marker changes)

- J10 A1 Amendment 5 (committed with this amendment) registers how a `replay_divergence` crash is handled: what
  a divergent key is, the exclusion from both arms of a contrast, the 16-key completeness cap, and what is
  reported. **It applies to J12 unchanged**, to J12's arms M^bplus_6 and M^zs_6 and to the J10 arms J12 reads
  (`prefix_m11`, `prefix_zs_m11`).
- D1–D4 each pair two prefix arms, so each removes the union of its two arms' divergent keys. D3's and D4's
  handoff-only populations, their h* companions (Amendment 1) and the planless-key sensitivity are computed on
  the remaining pairs.
- §3's completeness rule ("a contrast whose two arms lack 336 non-crashed pairs is incomplete") and §6's "a
  single D is reported incomplete if its arms cannot reach 336 non-crashed pairs" are read with divergent keys
  removed, up to 16 per contrast. Above 16 the D is incomplete.
- Exposure is expected to be small. Both J12 arms replay J10 arm 3, a `gpt-5.6-luna` source. On dev no luna
  source printed process-varying text within its first 11 steps (0 of 285 episodes), and no luna-sourced replay
  kept a divergence (DIV-01, LP-06).
- Code: `scripts/analysis/j12_report.py`.
  - `j12_apply_pair_rule` (:274) counts a D's pairs against 336 minus its removed keys.
  - The handoff-only view in `j12_evaluate_handoff_only` drops the same keys.
  - `j12_am2_block` (:510) is reported under the key `j12_am2_divergence` (:739).
  - With no divergent key, the dev report from this code matches f690b6a's once the new block is removed (PBS
    25852148, 25852149).
- Tests in `tests/unit/test_j12_report.py`: `test_am2_no_divergent_key_changes_nothing_but_adds_the_block`,
  `test_am2_one_divergent_key_in_a_j10_arm_reads_d1_d3_on_23_pairs`, `test_am2_two_arms_of_a_d_remove_the_union`,
  `test_am2_more_than_16_divergent_keys_leave_the_d_incomplete`,
  `test_am2_a_divergent_key_plus_an_ordinary_crash_is_incomplete`.

*Amendment 2 ends.*

## Pointer update after Amendment 2 (2026-09-25, before any J12 read; pointers only, no rule changes)

The pre-read audit of `scripts/analysis/j12_report.py` against this document found every registered statistic,
rule and family implemented as written. The fixes it led to added report-level checks and printed text only,
and moved code lines. Amendment 2's line pointers now read:
- `j12_apply_pair_rule`: `:311` (was `:274`);
- `j12_am2_block`: `:705` (was `:510`);
- the report key `j12_am2_divergence`: `:1003` (was `:739`).

Names, rules and tests are unchanged. §6's read command (line 164) lists the J12 arms and J10's two m = 11
arms. The key-exclusion sensitivity of §3, which follows A1 §4.2, also needs J10 arm 3 (`planner_alone_cap81`)
as the plan source. The report now refuses a registered read without that arm, and prints the full command. It
also refuses a registered read without seeds {1, 2} and 168 tasks, or with an arm directory that is not the
arm's registered campaign. As in J11, `--divergent-refill-confirmed` records the Amendment 2 §B.1 resumption
condition.

*Pointer update ends.*
