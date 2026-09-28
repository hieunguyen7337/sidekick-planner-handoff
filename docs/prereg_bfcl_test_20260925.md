# BFCL `multi_turn_base` test (Wave E, E4): preregistration (the E-prereg)

**Status**: DRAFT

Drafted 2026-09-25 by unit S3, before BFCL dev has run, for Claude's review. Filled from the BFCL dev read on
2026-09-28, with §9's decisions taken before freeze. It registers the one confirmatory BFCL read. Its predictions
mirror J10's P6, CF1, and P3 with its handoff-only B1 companion (`docs/plan_top_venue_20260924.md:85`, `:160-162`),
and J12's depth predictions D1–D4 (`docs/prereg_j12_depth_test_20260924.md:79-101`). Family D was added before
freeze (§9.5).

- **Freeze.** After the BFCL dev read and before any BFCL `test` episode, smokes included (dev §7). Freezing means
  replacing the status line with one that begins with FROZEN, and committing.
- **Dev values.** Every value that depends on dev is filled from the two dev-split reports, first committed at
  `1f1f991`: `campaign/results/bfcl_dev_20260924.report.json` ("dev report", `scripts/analysis/bfcl_dev_report.py`)
  and `campaign/results/bfcl_power_20260924.report.json` ("power report", `scripts/analysis/bfcl_power.py`). The D
  rows (D3 and D4's dev values, and D's power) were added to the same two reports before freeze (§9.5), with every
  earlier value unchanged. The D code is commit `660a69d`, and both reports were regenerated there (`meta.git_sha`).
  Each value names its key. No placeholder is left.
- **Citations.** "dev §n" is `docs/prereg_bfcl_dev_20260924.md`, cited by section because it is under revision.
  "J10 :n" is line n of `docs/prereg_j10_amendment_20260924.md`, which is A1 plus Amendments 1–5.

## 1. Split, seeds and scoring

- **Environment**, as in dev §1: gorilla @ `6ea5797` in `third_party/bfcl/`, through
  `src/sidekick/environments/bfcl_env.py`. `max_steps` is 40, plus upstream's 20 steps per user turn.
- **The 150 test entries** are the `test` list of `data/bfcl_split_20260924.json` (`n_test` 150).
  `scripts/setup/bfcl_split.py` built it with `build_split` (`bfcl_env.py:206-223`): the 200 ids of `load_entries`
  (`:181-183`), in numeric order, shuffled by `random.Random(20260924)`. Shuffle positions 51–200, re-sorted, are
  `test`. The split is unstratified, and `tests/unit/test_bfcl_env.py:106` pins the file to the builder. The runner
  calls `bfcl_task_ids("test", n)` (`bfcl_env.py:230-241`, `runner.py:451-453`), where `n` ≤ 0 gives all 150.
- **Seeds {1, 2}** give 300 `(entry, seed)` pairs per arm (`docs/plan_luna_reset_20260925.md:104`). Dev's seed 3
  stays on dev. **`test_challenge` does not apply**: BFCL has only `dev` and `test` (`BFCL_SPLITS`, `bfcl_env.py:62`),
  and no other category is read.
- **Scoring**, as dev §1. `goal_pass_rate` is primary; `success` (= `tgc`, binary per entry) is secondary. A non-crash
  `error_type` is an outcome and is scored as recorded (J10 :259-262). A `crash` left at analysis removes its pair
  (§7).

## 2. Arms: the zs design, with the bplus arms as secondary

Every `zs` and `bplus` arm of dev §4 runs on test. Only `campaign_id` changes, to `bfcl_<arm>_test_20260925`.

| arm | receiver | role on test | enters |
|---|---|---|---|
| planner_alone_cap81 | — | ceiling; the only plan and prefix source | P3, B1 |
| takeover_k5 | zs | replays the first plan; the planner acts every 5 steps | P6, CF3 |
| advise_k5_fullctx | zs | replays the first plan; correction advice every 5 steps | P6, CF1 |
| advise_k5_neutral | zs | as advise_k5_fullctx, with the neutral prompt | CF1, CF3 |
| prefix_zs_m6 | zs | replays the first 6 actions, then hands off | P3, B1, D2, D4 |
| prefix_zs_m2, _m4 | zs | the same at m = 2 and 4 | D2, D4 (m2; m4 is reported between, exploratory) |
| plan_zs (`prompt_only`) | zs | the first plan only | S5 |
| executor_alone_zs | zs | zero-shot floor | S4, S5 |
| prefix_bplus_m2, _m4, _m6 | bplus | secondary: J10's P3 receiver | D1, D3 (m2, m6), S3 (m6) |
| executor_alone_bplus | bplus | secondary: out-of-domain adapter floor | S4 |

- **P3 registers on `zs`**, a choice dev §6 leaves open. `zs` is BFCL's primary receiver (dev §4). `bplus` is the
  AppWorld adapter, run out of domain because BFCL has no train split. J10's P3 rests on in-domain tailoring, which
  no BFCL arm has; the untailored contrast is J10's own second B1 row (J10 :727). The choice is made on design
  grounds, before the dev read, so it cannot track the dev effect.
- **The bplus arms stay, as secondary.** They cost no hosted calls, S3 is the literal J10 P3 contrast, and D1 and D3
  rest on `prefix_bplus_m2` and `_m6` (§4). Dropping them would remove half of family D.
- **`qzs` stays dev-only.** The revised dev §4 and §6 add it "on dev only" (as X2), and no mirrored prediction uses
  it. A `qzs` test arm would need an amendment and a budget before freeze.

## 3. Hosted-call budget (300 episodes per arm)

The planning rates are those of scoping §3 (`docs/second_env_scoping_20260923.md:161-165`), as dev §5 uses them.
The measured column is the dev read, per episode over 150 episodes per arm (dev report
`arms.<arm>.calls_live_mean` / `calls_attributed_mean`). Expected live spend on test is that live mean × 300. The
ceilings are per-episode rates × 300, set as dev Amendment 1 set them (§9.9). They are launch guards, not expected
spend.

| arm | calls/ep | planning calls | measured on dev: `calls_live` / `calls_attributed` per ep | expected live = dev live/ep × 300 | ceiling = rate × 300 (§9.9) |
|---|---|---|---|---|---|
| planner_alone_cap81 | 12 | 12 × 300 = 3,600 | 13.08 / 13.08 | 3,924 | 20 × 300 = **6,000** |
| takeover_k5 | 3 | 3 × 300 = 900 | 2.57 / 3.57 | 772 | 8 × 300 = **2,400** |
| advise_k5_fullctx | 3 | 900 | 2.49 / 3.49 | 748 | 8 × 300 = **2,400** |
| advise_k5_neutral | 3 | 900 | 3.02 / 4.02 | 906 | 8 × 300 = **2,400** |
| plan_zs | 1 | 1 × 300 = 300 | 0.013 / 1.013 (2 live calls in 150 episodes) | 4 | 4 × 300 = **1,200** |
| prefix ×6, executor_alone ×2 | 0 | 0 (2,400 GPU episodes) | `calls_live`: prefix_zs_m2 0.04 (6 calls in 150 episodes), prefix_zs_m6 0.007 (1), prefix_zs_m4 0; prefix_bplus_m2, _m4, _m6, executor_alone_zs and executor_alone_bplus 0 | executor asks only (below) | none: no brake at `HOSTED=0` (below) |
| **arms** | | **6,600** | | **6,354** | **14,400** |
| smokes, never analysed (scoping §3's dry run) | | ≤ 100 | | | |
| retries, 10 % of 6,700 | | 670 | | | |
| **planning total**, hosted arms, from dev means | | | | **6,354** | |
| planless keys (§7), only if the case arises | ≤ 2 per key per arm | ≤ 2 × 15 × 4 = 120 | | | |

- **The planning total** is the five hosted arms' dev `calls_live_mean` × 300: 3,924 + 772 + 748 + 906 + 4 = 6,354.
  Smokes and retries come on top of it, at scoping's allowances above. The plan's ≈ 7,300 (`plan_luna_reset:104`)
  is this design at scoping's rates (6,600 arms + ≤ 100 smokes + 670 retries), to rounding. [Inferred: the plan does
  not derive it.]
- **Prefix and executor-alone arms** make no planned planner calls, but an executor ask is answered live. On dev,
  `prefix_zs_m2` made 6 live calls in 150 episodes, `prefix_zs_m6` 1, and the other six arms none. These arms run at
  `HOSTED=0`, which sets no `MAX_PLANNER_CALLS` brake (`bfcl_arm.pbs:506`) and no spend guard (`:827`, `:830`).
  Their `--gate` (`:491-494`) checks for zero live calls after a run: it catches an ask, and on the smoke it stops
  the launch (`:809-811`), but it does not prevent one. Asks are counted and reported per arm, as J10 Am1 §I does
  (§7).
- The caps that bind are the wrapper's per-arm `MAX_PLANNER_CALLS` (dev §5). Calls are reported under both J10 Am4
  conventions (J10 :1006-1015).

## 4. Registered predictions

**Mapping from J10.** k = 5 plays J10's k = 10 (dev §4). **m = 6 plays J10's m = 11**: the deepest registered depth,
where P3 and B1 sit (J10 :363, :722-727). m = 4 has no J10 analogue. On dev, the per-call handoff shares at m = 2, 4
and 6 are 1.00, 0.96 and 0.84 (dev §3).

**Common to every prediction.**
- The metric is `goal_pass_rate`.
- The estimand is the mean of left − right over the 300 pairs, in pp, less the keys §7 removes; D3 and D4 take
  Σd·h\*/Σh\* over those pairs instead (Family D). It is computed as written, never by negating a stored reverse
  (J10 :253-254).
- Intervals are 95 % percentile and entry-clustered (§5).
- An interval condition counts only if the unadjusted interval meets it **and** the adjusted p is ≤ 0.05
  (J10 :287-289).

| id | contrast (left − right) | family | rule; p | dev value |
|---|---|---|---|---|
| **P6**, primary | `takeover_k5 − advise_k5_fullctx` | H (m = 1) | positive, CI excluding 0; two-sided p at 0 | +11.12 pp [4.16, 18.22], per-pair SD 38.055 pp, two-sided p 0.0026 (dev report `contrasts.P6.goal_pass`) |
| **P3**, secondary | `prefix_zs_m6 − planner_alone_cap81`, all episodes | N (m = 1) | lower bound above **−7.00 pp**; p = 2 × share ≤ −7.00 (`direction="greater"`) | −6.58 pp [−10.99, −2.46], per-pair SD 19.646 pp; lower bound not above −7.00, `p_ni` 0.802 (dev report `contrasts.P3_zs_m6.goal_pass`) |
| **CF1** | `advise_k5_neutral − advise_k5_fullctx` | CF (m = 1) | positive, CI excluding 0; two-sided p at 0 | +4.38 pp [−0.29, 9.42], per-pair SD 30.419 pp, two-sided p 0.0658 (dev report `contrasts.CF1.goal_pass`) |

Dev values are 150 pairs in 50 entry clusters (seeds 1–3), 10,000 resamples at seed 20260925, and exploratory
(dev report `meta`; dev §6).

| id | supported | not supported | reversed (CI excludes 0 on the other side) |
|---|---|---|---|
| P6 | J10's H-A1b replicates on BFCL | fails to replicate; TGC and CF1 do not rescue it | a primary finding |
| P3 | non-inferior at −7.00 to the planner acting alone | fails non-inferiority; P6 and CF1 do not depend on P3 | none registered |
| CF1 | P6 is reported only as "actions beat correction-prompt advice" | the prompt effect does not replicate; P6 carries §8's qualification | a primary finding |

- **P3's margin** is J9's and J10's, unchanged (J10 :363), so both environments are read at one margin. It is not
  set from dev (§9.1).
- **P3's limit-excluded variant** is a sensitivity only, because it selects on the ceiling's own failures
  (J10 :378-382).
- **CF1** is printed beside P6. It has no bearing on whether P6 or P3 is complete (J10 :783).

**B1, P3's handoff-only companion.** Pre-specified, not decision-bearing (J10 :722-735, as corrected at :951-963).
- **Rows:** `prefix_zs_m6 − planner_alone_cap81` and `prefix_bplus_m6 − planner_alone_cap81`, on both metrics.
- **Estimand:** Σd·h\*/Σh\*, where h\* = 1 iff the loop ran its live phase after the replayed prefix.
  - h\* is read from the prefix episode's own events (`scripts/analysis/handoff_control.py`, `hstar_flags` `:278`).
  - A missing flag counts as 0, and is counted.
- **Reading:** it **holds** if the lower bound is above −7.00 pp, else it **fails**. §5's boundary rule applies.
- It is printed in P3's sentence and never changes P3. The `handoff_occurred` version is printed as `*_flag`.
- Dev: zs −7.71 pp [−12.68, −2.90], `n_handoff` 128 of 150 pairs (dev report `contrasts.B1_zs_m6_hstar.goal_pass`);
  bplus −11.46 pp [−18.40, −5.04], `n_handoff` 128 (`contrasts.B1_bplus_m6_hstar.goal_pass`). Both would fail at
  −7.00 (`lower_above_margin` false).

**Family D: depth.** Registered and decision-bearing: one Holm family of m = 4, its own, as J12's D1–D4
(`docs/prereg_j12_depth_test_20260924.md:79-101`). The span is m6 − m2, the S1/S2 depth span this draft fixed
before the BFCL dev read (§9.5). m4 is not a member.

| id | contrast (left − right) | population | rule | h from | dev value |
|---|---|---|---|---|---|
| **D1** | `prefix_bplus_m6 − prefix_bplus_m2` | all 300 pairs | **> 0**: lower bound above 0 | — | +12.38 pp [7.16, 17.73], per-pair SD 36.365 pp (dev report `contrasts.depth_bplus.goal_pass`) |
| **D2** | `prefix_zs_m6 − prefix_zs_m2` | all 300 pairs | **> 0** | — | +2.53 pp [−3.88, 8.48], per-pair SD 30.12 pp (`contrasts.depth_zs.goal_pass`) |
| **D3** | `prefix_bplus_m6 − prefix_bplus_m2` | handoff-only, Σd·h\*/Σh\* | **> 0** | h\* of `prefix_bplus_m6`, the left (deeper) arm | +14.24 pp [8.41, 20.22], per-pair SD 35.45 pp, `n_handoff` 128 of 150 pairs (`contrasts.depth_bplus_hstar.goal_pass`) |
| **D4** | `prefix_zs_m6 − prefix_zs_m2` | handoff-only, Σd·h\*/Σh\* | **> 0** | h\* of `prefix_zs_m6` | +4.14 pp [−2.54, 10.65], per-pair SD 30.923 pp, `n_handoff` 128 (`contrasts.depth_zs_hstar.goal_pass`) |

- **Rule.** Each member's p is A1 §5.3's `direction="greater"` form at 0, as J12's
  (`docs/prereg_j12_depth_test_20260924.md:81`): `bootstrap_pvalue(means, 0.0, "greater")`
  (`scripts/analysis/j10_report.py:2038`), 2 × the share of replicates ≤ 0. The four p are Holm-adjusted within D
  (m = 4) by `holm_adjust` (`:2061`). A D member is **supported** iff its unadjusted interval lies above 0 **and** its
  Holm-adjusted p is ≤ 0.05, the common rule above. Why not two-sided, as for P6 and CF1: §9.5.
- **h\*** is B1's (`handoff_control.hstar_flags`; a missing flag counts as 0 and is counted), read from the left, m6,
  arm. The `handoff_occurred` versions are printed as `D3_flag` and `D4_flag`, not decision-bearing (§8).
- **`success`** (TGC) is printed beside each D member, with no rule.
- **Divergent keys.** Each D member removes the union of its two arms' divergent keys (§7).
- **Dev.** Pairs, clusters and resamples as for P6, P3 and CF1 above. D3 and D4's dev rows (`h_arm` the m6 arm,
  `n_h_missing` 0) were added before freeze (§9.5); D1 and D2's are the dev report's existing depth rows.

| outcome | reading |
|---|---|
| D1 and D3 supported | on BFCL, a later handoff raises the out-of-domain adapter's quality, and not only through episodes the planner finishes itself |
| D1 supported, D3 not | the depth gain is not shown on real handoffs |
| D1 not supported | the dev depth span does not replicate on BFCL test for this receiver |
| D2 / D4 | the same readings for the zero-shot receiver |

A reversal (a member's unadjusted 95 % entry-clustered interval with its upper bound below 0) is reported as a
primary finding, as in J12 (`docs/prereg_j12_depth_test_20260924.md:103-106`). It is read from that interval alone,
with its one-sided `direction="less"` p at 0, `bootstrap_pvalue(means, 0.0, "less")`, printed unadjusted, because
D's Holm p tests the predicted direction only.

In every D1 and D3 sentence, `bplus` is "the AppWorld-tailored adapter, out of domain", never "tailored" to BFCL (§8).

**Supporting contrasts.** Pre-specified, not decision-bearing, unadjusted, and labelled.

| id | contrast | note |
|---|---|---|
| S1, S2 | promoted to D2 and D1 (§9.5) | the m4 arms are reported between them, exploratory (§8) |
| S3 | `prefix_bplus_m6 − planner_alone_cap81` at −7.00, with its B1 row | the literal J10 P3 receiver |
| S4 | `executor_alone_bplus − executor_alone_zs` | tailoring, out of domain |
| S5 | `plan_zs − executor_alone_zs` | one plan |
| CF3 | `takeover_k5 − advise_k5_neutral`, two-sided | readings as J10 Am1 §C (:795-801); never "execution adds nothing" |

## 5. Inference

- **Pairing** is on `(entry, seed)`: 150 × 2 = 300 pairs.
- **The cluster unit is the entry id**; both seeds of an entry form one cluster, so there are 150. An entry's seeds
  share its `initial_config`, scripted user turns and ground truth, and in replay arms its planner run. BFCL has no
  scenario grouping, and the split is unstratified over entries (`bfcl_env.py:207`). This is j10_report's `task`
  clustering (`_cluster_labels`, `scripts/analysis/j10_report.py:2099-2104`), as on dev (dev §6).
- ⚠ **Never use the `scenario` path on BFCL ids.** `scenario_of` (`scripts/setup/hj1_gate.py:45-47`) strips the last
  `_n`, so all 150 ids become one cluster, `multi_turn_base`, and every interval collapses to a point. The report
  must assert 150 clusters.
- **Sensitivity clustering**, not decision-bearing: by the entry's sorted `involved_classes` set, with the count
  reported as found (§9.3).
- **Bootstrap.** J10's paired percentile cluster bootstrap (`cluster_bootstrap_means` `:2001`): **10,000 resamples**
  at seed **20260925**. The seed is not J10's 20260924, because that seed drew the split; this keeps the resampling
  stream apart from the stream that chose the test entries (§9.4).
- **Holm.** Four families (§9.2, §9.5): **H = {P6}**, the primary; **N = {P3}**, non-inferiority at −7.00 pp;
  CF = {CF1}; and **D = {D1, D2, D3, D4}**, depth. H, N and CF have m = 1 each; D has m = 4, with Holm within D.
  Each family is tested at α = 0.05. With m = 1, `holm_adjust` (`:2061`) returns the unadjusted p, from
  `bootstrap_pvalue` (`:2038`) in §4's forms; in D it adjusts the four members' `direction="greater"` p at 0 (§4).
  Every other row is unadjusted, and none is promoted after the read (J10 :295-296).
- **Boundary rule** (J10 :300-308). A decision-bearing bound within 1.00 pp of its threshold is recomputed at seeds
  {20260925, 1, 2, 3, 7, 101, 999} and at 200,000 resamples. If any seed flips the verdict, the prediction is
  reported as **on the boundary**.
- **Sign-flip p** (J10 :312-318), not decision-bearing. It is Monte Carlo, 100,000 patterns at seed 20260925,
  because 150 > 20 clusters; for P3 it is one-sided at −7.00. A disagreement goes in the verdict's sentence.
- **BY-FDR companion** (J10 Am1 §F :837-849; `am1_by_fdr` `:3389`). Benjamini–Yekutieli over every printed paired
  `goal_pass_rate` contrast, each counted once: P6, P3, CF1, the two B1 rows, D1–D4, S3, S4, S5 and CF3, which is 13.
  Each uses its two-sided p at its threshold. A rejection that would not survive is flagged; no verdict changes.
- **`success`** gets the same intervals and no rule. A bound on its nearest atom is reported as such (J10 :275-277).

## 6. Power: what to run on BFCL dev before freeze

The script is `scripts/analysis/bfcl_power.py`. It mirrors `scripts/analysis/am1_power.py` function by function and
wrote `campaign/results/bfcl_power_20260924.report.json` (the power report; `bfcl_power.py:69`).

| am1_power.py | BFCL version |
|---|---|
| `ARMS` (:57-70) | `bfcl_<arm>_dev_20260924`, seeds 1–3 (dev §4) |
| `load_arm` (:98-114) | unchanged, except that h\* from `handoff_control.hstar_flags` replaces `_facts.handoff_occurred` |
| `paired_rows`, `index_by_scenario` (:117-140) | the cluster label is the entry id, not `scenario_of` |
| `draw_design` (:143-160) | 150 entries drawn with replacement from dev's 50, each taking 2 of seeds {1, 2, 3} without replacement |
| `cluster_sums` … `simulate` (:163-302) | unchanged |
| `CONTRASTS` (:73-94) | P6 and P3 in one family, H, as J10 has them (§9.2 splits it); CF1 in CF; CF3 two-sided, in no family; B1 for zs and bplus; S3; D1–D4 in D, in their own pass (§9.5) |
| `build` (:329-361) | power at the dev effect and at half of it (the half-shift at :336-340) |
| `refuse_heldout` (`j16_robustness.py:83`, `:136-140`) | ⚠ knows only `test_normal` and `test_challenge`, so the script must also refuse `_test_` |

- **Settings.** R = 1,000 reads, B = 2,000 each, `--seed` 20260924 (am1_power's default), α = 0.05. Power is
  reported, not used as a gate. First, the dev values are recomputed at 10,000 draws, entry-clustered, and matched
  to the dev report.
- **P6 alone.** P6's power is also given with P6 alone in its family, so the cost of adding P3 is visible before
  freeze (as J10 :779-780).
- **Rows and the registered design.** The simulation ran J10's family, H = {P6, P3}; §5 and §9.2 register
  H = {P6} and N = {P3}. The rows stay as computed. **P6 alone is P6's registered power.** The P3 row was
  simulated with P6 in its family. [Inferred: alone, its power can only be the same or higher, because Holm never
  lowers a p (`holm_adjust`, `j10_report.py:2061-2070`).]

| row | dev diff, entry CI | per-pair SD | power at dev effect | power at half effect |
|---|---|---|---|---|
| P6 with P3, as simulated | +11.12 [4.16, 18.22] | 38.055 | 0.992 | 0.563 |
| **P6 alone: registered (H)** | as above | as above | 0.995 | 0.662 |
| P3 with P6, as simulated | −6.58 [−10.99, −2.46] | 19.646 | 0.064 | 0.051 |
| CF1 | +4.38 [−0.29, 9.42] | 30.419 | 0.731 | 0.251 |
| B1, zs | −7.71 [−12.68, −2.90], `n_handoff` 128 | — | 0.009 | 0.029 |
| P6 and P3 both supported, as simulated | — | — | 0.064 | 0.043 |
| **D1**: bplus, all pairs | +12.38 [7.16, 17.73] | 36.365 | 1.000 | 0.773 |
| **D2**: zs, all pairs | +2.53 [−3.88, 8.48] | 30.12 | 0.268 | 0.090 |
| **D3**: bplus, handoff-only | +14.24 [8.41, 20.22], `n_handoff` 128 | 35.45 | 1.000 | 0.817 |
| **D4**: zs, handoff-only | +4.14 [−2.54, 10.65], `n_handoff` 128 | 30.923 | 0.391 | 0.116 |
| all four D supported | — | — | 0.268 | 0.087 |

- **Keys**, all in the power report. Dev columns: `dev.<row>.goal_pass` (`diff_pp`, `ci95_entry`, `sd_pp`,
  `n_handoff`), recomputed at 10,000 draws and equal to the dev report's `contrasts.<id>.goal_pass`. Power columns:
  `power_at_dev_effect.per_contrast.<row>.holm_supported` and the same under `power_at_half_effect`, for P6, P3 and
  CF1; `P6_alone` is the m = 1 run (its own family in the same report); B1, zs is `B1_zs.lower_above`; P6 and P3
  both supported is `families_all_supported.H.full` / `.half`, where the report's H is {P6, P3}. D rows: `dev.D1`
  to `dev.D4` `.goal_pass`, equal to the dev report's `contrasts.depth_bplus`, `depth_zs`, `depth_bplus_hstar` and
  `depth_zs_hstar` `.goal_pass`; `power_at_dev_effect.per_contrast.D<n>.holm_supported` and the same under
  `power_at_half_effect`; all four D supported is `families_all_supported.D.full` / `.half`. D's half effect moves
  each dev point half-way to 0 (`half_effect_shift_pp.D<n>`).
- **Family D is its own family**, simulated in a separate pass after the main one (power report
  `meta.separate_pass_families.D`), so it took no draw from the rows above and the P6, P3 and CF1 rows are
  unchanged: comparing both reports before and after D was added, 0 of 407 power-report leaves and 0 of 1,768
  dev-report leaves changed (stamps aside). D's simulated reads are independent of H's and CF's, so no joint rate
  across families is given.
- **D's p in the simulation** is the registered one: `am1_power.simulate` gives Holm each row's `direction` p
  (`am1_power.py:280`), and D's rows are `direction="greater"` at 0 (`bfcl_power.py:93`), as §4 registers.
- **Half effect** is the dev point shifted half-way to its threshold (`half_effect_shift_pp`; the report's
  `caveats`). B1, zs sits below −7.00 on dev, so its half effect is nearer the margin and its power rises.

## 7. Order, completeness, abort

**Order.** Live arms go first, because `gpt-5.6-luna` may be withdrawn and replay arms are immune (J10 :567-572).
1. `planner_alone_cap81`.
2. The planless check: more than **15** of 300 planless (5 %, J10 :234) means no replaying arm starts.
3. `takeover_k5` and `advise_k5_fullctx`, in consecutive windows.
4. `advise_k5_neutral`, then `plan_zs`.
5. The GPU-only arms.

**Completeness.** An arm is complete at **150 × 2 = 300 non-crashed pairs**.
- **Crash-only resumption** as J10 §8 (:543-545). It fills unwritten or crashed episodes, is not a re-read, and never
  overwrites a non-crash `result.json`.
- **Planless keys** (J10 :218-236) are planned live (`on_missing: call_if_planless`, as the BFCL configs set), and
  every pair stays. A key-exclusion sensitivity is run for P6, P3, CF1 and D1–D4; a verdict that moves is on the
  boundary.
- **Divergent replay keys** follow J10 Am5 §B (:1104-1126), with the cap at **15** keys (5 % of 300). BFCL hashes
  public state attributes, not printed output (`bfcl_env.py:369-377`, `:605-612`), and spike a matched 4,152 of
  4,152 prefix replays (dev §2).
- **Executor asks** (J10 Am1 §I :881-894). An ask answered live is part of the system. It is counted, bounded at
  count / 300 in pp, and never purged.

**Abort.** The test is **reported as not run**, never at reduced power, if `planner_alone_cap81`, `takeover_k5` or
`advise_k5_fullctx` cannot complete 300 pairs. If `advise_k5_neutral` cannot, CF1 and CF3 are not run, and P6 and
P3 stand. GPU arms are resumed until complete; a contrast on an incomplete arm is not read. If a prefix arm cannot
complete 300 pairs, each D member that uses it is not read; the others stand, and keep Holm at m = 4, with each
unread member's p counted as 1.

**One read** (J10 :536-547). There is no second read for a better number. A post-read fix is a disclosed re-run,
reported with both sets of numbers. No arm is added after freeze.

**Wrapper.** A test path goes into `bfcl_arm.pbs` before the first test job (dev §7), gated as `j10_arm.pbs` is
(J10 :5-8). It requires this file committed and unmodified, with a status line beginning with FROZEN; a confirm
variable (proposed `BFCL_CONFIRM=E_FROZEN`); §2's arms only; `SEEDS=1,2` only; and no `qzs` stem.

## 8. Exploratory items and reporting constraints

- **Reported regardless of outcome** (J10 §7):
  - each arm's means, pair count and `error_type` distribution, with the `limit` rate beside every mean and contrast;
  - for P6, CF1 and CF3, the split into pairs with and without a `limit` arm (post-treatment), and the limit-as-0
    sensitivity (J10 Am1 §D);
  - the cost table under both call conventions;
  - the counts of planless keys, divergent keys and live asks, including zero; and h\* counts per prefix arm;
  - for each D member, its `success` companion; and `D3_flag` and `D4_flag`, the `handoff_occurred` versions of D3
    and D4.
- **Exploratory, and labelled so:** results per turn and per `involved_classes` set; the code-block share of
  interventions and the copy rate (J10 Am1 §C); the m4 arms beyond D1–D4.

**Constraints.**
- **P6** is described as "actions beat the registered correction-prompt advice", with CF1 in the same paragraph
  (J10 :438-443).
- **P3** is described as non-inferiority to the **medium-effort** planner in this harness (J10 Am2 :914-918).
- Every all-episode non-inferiority or depth number is printed with its h\* companion (J10 Am1 §B4).
- `bplus` is "the AppWorld-tailored adapter, out of domain", never "tailored" to BFCL. D1 and D3 describe it so.
- BFCL and J10 are reported side by side, never pooled.

## 9. Decisions (resolved 2026-09-28, before freeze)

Taken by Claude after the dev read and before freeze. The Status line stays DRAFT until the user freezes.

1. **P3 margin: −7.00 pp, unchanged.** It is carried from J9 and J10 (J10 :363) and was fixed before the dev read. A
   margin set now would see the dev effect, which fails at −6.58 pp [−10.99, −2.46] on `zs` (dev report
   `contrasts.P3_zs_m6.goal_pass`, `lower_above_margin` false).
2. **Holm: H = {P6} (m = 1, α = 0.05, the primary) and N = {P3} (m = 1, non-inferiority at −7.00 pp).** Disclosed:
   - This differs from J10, where P6 and P3 sit in one Holm family (J10 :282-283).
   - It was chosen after the dev read, as dev §6 assigns: "The E-prereg fixes ... the Holm families"
     (`docs/prereg_bfcl_dev_20260924.md:170-174`).
   - The reason is P6's power (§6; power report `power_at_dev_effect` and `power_at_half_effect`,
     `per_contrast.<row>.holm_supported`). With P3 in its family, P6's power is 0.992 at the dev effect and 0.563 at
     half; alone it is 0.995 and 0.662. P3's power, simulated with P6 in its family, is 0.064 and 0.051; alone it can
     only be the same or higher (§6). Sharing a family would cost P6 0.099 of power at half the effect, for a member
     with little power of its own.
   - P3 is registered anyway, because it tests J10's non-inferiority claim in a second environment. Its failure is
     the expected outcome, given the dev estimate (−6.58 pp [−10.99, −2.46], dev report
     `contrasts.P3_zs_m6.goal_pass`).
   - BFCL and J10 are reported side by side, never pooled (§8), so no cross-environment multiplicity is claimed.
   - The form follows J10 Am1 §C, which gave CF one member after a power run and said why (J10 :779-780).
3. **Clustering by entry is primary**, as in the dev read and the power simulation (both reports' `meta.cluster_unit`
   is `entry`, over the 50 dev entries). On test the clusters are the design's 150 entries (§5). Class-set
   clustering (the entry's `involved_classes` set) is kept as a non-decision-bearing sensitivity (§5). Its cluster
   tally reads task definitions, not results.
4. **Bootstrap seed: 20260925**, as first drafted. It keeps the bootstrap stream apart from
   `random.Random(20260924)`, which drew the test split (`SPLIT_SEED`, `bfcl_env.py:63`; the shuffle at `:213`).
   §5's bootstrap, boundary-rule and sign-flip seeds all use it. The dev read used it too (dev report `meta.seed`).
   The power simulation's seed, 20260924 (`bfcl_power.py`'s `DEFAULT_SEED`, `:68`; power report `meta.seed`), belongs
   to a separate, pre-read computation and does not bind the read.
5. **Family D (depth), added 2026-09-28 before freeze, at the user's decision.** Disclosed:
   - **The user's words:** "yes, add the depth prediction to the BFCL prereg". Claude recommended it because prefix
     depth is the result that held on AppWorld's held-out split, while the draft made depth only supporting rows
     (S1, S2).
   - **What was known.** The BFCL dev read, including its m6 − m2 depth rows (dev report
     `contrasts.depth_<r>.goal_pass`): zs +2.53 pp [−3.88, 8.48], bplus +12.38 [7.16, 17.73], qzs +21.18
     [15.74, 26.63]. And the AppWorld test reads J10, J11 and J12, all read on 2026-09-28
     (`docs/claims_ledger.md:352`, `:314`, `:333`), with J12's D1–D4 all supported (`:337`).
   - **No BFCL test episode exists.** `ls /scratch/n12194778/sidekick/results | grep -c '^bfcl_.*_test_'` printed
     0 on 2026-09-28. It lists names only and opens nothing.
   - **Why these members.** They are J12's structure (`docs/prereg_j12_depth_test_20260924.md:79-101`): one span on
     each receiver, over all pairs and handoff-only, with h from the deeper arm. The span is S1 and S2's, fixed in
     this file's first commit, `08721ee` (2026-09-25), before the dev read: "`prefix_<r>_m6 − prefix_<r>_m2`, for
     r = zs and bplus, with m4 between" (`:126` there). The dev report was first committed at `1f1f991`, on
     2026-09-28.
   - **Why not qzs.** It has the largest dev depth effect, +21.18 pp, and adding it for that reason would select on
     the dev result. §2 keeps qzs dev-only.
   - **D's p is J12's `direction="greater"` form, not the two-sided p of P6 and CF1.** Family D mirrors J12, which
     registered that form (`docs/prereg_j12_depth_test_20260924.md:81`), and §6's power was simulated with it.
     A1 §5.3 gives the two-sided form to predictions that register a reversed outcome inside their Holm family, as
     P6 and CF1 do, and the `greater` form to those that do not (J10 :284-286). D registers its reversal as J12 does,
     outside the family: read from the unadjusted interval alone, with a `direction="less"` p printed unadjusted
     (§4). In a Holm family of four, a two-sided p would let a member that moves the wrong way (a depth effect
     significantly below 0) take the smallest rank and lower its siblings' adjusted p; in the `greater` form that
     member's p is 1, the cap. P6 and CF1 are each alone in their family (m = 1), where the forms cannot interact.
     This edit first drafted D two-sided. The form was changed before family D was first committed to this file;
     the code commit, `660a69d`, already used `greater`, so no commit has carried a two-sided D. The change was made
     on this reasoning and a verifier's finding, with no new data seen.
   - **D2 and D4 are registered although zs's dev interval includes 0** (+2.53 pp [−3.88, 8.48]): members are fixed
     by design, not by the dev effect. Their power is low: D2 0.268 at the dev effect and 0.090 at half, D4 0.391
     and 0.116, against 1.000 and 0.773 for D1 and 1.000 and 0.817 for D3. All four are supported together at
     0.268 and 0.087 (§6).
   - **H, N and CF are unchanged.** D is its own family, so their members, α and registered power stay as §5 and §6
     give them.
6. **`plan_zs` is kept.** On dev it replays `planner_alone_cap81`'s first plans (`arms.plan_zs.n_cached_plan_events`
   150 of 150) and made 0.013 live calls per episode (`arms.plan_zs.calls_live_mean`; 2 calls in 150 episodes), so
   its hosted cost is negligible. It feeds S5.
7. **Names.** These now exist:
   - `scripts/analysis/bfcl_dev_report.py` and `scripts/analysis/bfcl_power.py`, whose reports were first committed
     at `1f1f991` and regenerated with family D at `660a69d` (`meta.git_sha`; §9.5);
   - the per-pair SD, `contrasts.<id>.goal_pass.sd_pp` in the dev report and `dev.<row>.goal_pass.sd_pp` in the power
     report: the sample SD (n − 1) of the per-pair differences, in pp (dev report `meta.definitions.sd_pp`).

   **Pre-test build item.** The wrapper's test submission path (§7; dev §7) does not exist yet. It is to be gated on
   this document's FROZEN Status line and on `BFCL_CONFIRM`. Today `bfcl_arm.pbs` refuses any `SPLIT` but `dev`
   (`:216`), and `BFCL_CONFIRM` appears nowhere in `scripts/`, `src/` or `configs/`. It cannot be built while the
   week-A arms run from the plan worktree, under the code freeze on `src/`, `configs/` and `scripts/pbs/`. It is
   built before any test episode, smokes included.
8. **Force-quit.** Resolved for this harness; upstream's own label stays open.
   - The adapter force-quits on a user turn's 21st CODE step (`MAXIMUM_STEP_LIMIT` 20, `bfcl_env.py:68`, `:537-540`).
     It sets `done` and returns an observation with no `error_type` (`bfcl_env.py:553`; the field defaults to None,
     `src/sidekick/protocols/schemas.py:103`).
   - The loop ends on `done` without setting one (`src/sidekick/systems/loop.py:1191`). The episode's `error_type` is
     therefore None, tallied as `none` in the dev report's `error_types` (`bfcl_dev_report.py:388`).
   - **The `limit` rate does not count it**: it counts `error_type == "limit"` only (`bfcl_dev_report.py:386`).
   - The force-quit is recorded as `report.force_quit` in the evaluate payload (`bfcl_env.py:585`) and fails
     `success` (`:578`). Turns it never reached score as `multi_turn:empty_turn_model_response`
     (`bfcl_env.py:446-449`), upstream's label for an empty turn (`multi_turn_checker.py:88`).
   - Upstream's inference-side force-quit lives in its model handlers, which are not vendored
     (`third_party/bfcl/README.md`). A search of `third_party/bfcl/` for force-quit or force-terminate finds nothing,
     so which `error_type` upstream writes is not established here.
   - No analysis script reads `force_quit`. Whether §8 prints a force-quit count beside the `limit` rate is open for
     the freeze review.
9. **Ceilings.** Each hosted test arm's `MAX_PLANNER_CALLS` is a per-episode rate × 300 episodes. The channel and
   plan rates are dev Amendment 1's: **8** calls per episode for the channel arms and **4** for the plan arm
   (`docs/prereg_bfcl_dev_20260924.md:198-230`). Amendment 1 set them to escape the wrapper's smoke refusal, not
   from expected spend. `planner_alone_cap81` gets **20** per episode. On dev it ran at 2,400 for 150 episodes, 16
   per episode (dev prereg `:131`, `:205`), and its dev mean, 13.08, sat just under 13.33, the smoke rate at which
   it would have been refused; 20 leaves headroom.
   - planner_alone_cap81: 20 × 300 = **6,000**;
   - takeover_k5, advise_k5_fullctx and advise_k5_neutral: 8 × 300 = **2,400** each;
   - plan_zs: 4 × 300 = **1,200**.

   Together that is 14,400 (§3). The ceilings are launch guards, not expected spend: the expected live spend, from
   the dev means, is 6,354 (§3). The prefix and executor-alone arms run at `HOSTED=0`, with no `MAX_PLANNER_CALLS`
   brake (`bfcl_arm.pbs:506`); their executor asks are counted and reported per arm (§3, §7).

   ⚠ The wrapper's launch check projects the smoke's live rate × the missing episodes × `SAFETY` 1.2, rounded up
   (`bfcl_arm.pbs:71`, `:560-566`), and refuses the launch when that exceeds the ceiling. A first submission is
   therefore refused whenever its 2-episode smoke averages more than ceiling / (300 × 1.2) live calls per episode:
   - 16.67 for planner_alone_cap81 (dev 13.08);
   - 6.67 for takeover_k5 (dev 2.57), advise_k5_fullctx (dev 2.49) and advise_k5_neutral (dev 3.02);
   - 3.33 for plan_zs (dev 0.013), so 7 live asks in its two smoke episodes refuse it.

   The channel and plan thresholds equal those Amendment 1 gave the same arms over 150 dev episodes. They are
   recorded here for the freeze review. [Inferred: this assumes the test path keeps the dev wrapper's projection,
   with about 300 episodes missing at the smoke.]
