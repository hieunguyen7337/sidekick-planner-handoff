# BFCL `multi_turn_base` test (Wave E, E4): preregistration (the E-prereg)

**Status**: DRAFT

Drafted 2026-09-25 by unit S3, before BFCL dev has run, for Claude's review. It registers the one confirmatory BFCL
read. Its predictions mirror J10's P6, CF1, and P3 with its handoff-only B1 companion
(`docs/plan_top_venue_20260924.md:85`, `:160-162`).

- **Freeze.** After the BFCL dev read and before any BFCL `test` episode, smokes included (dev §7). Freezing means
  replacing the status line with one that begins with FROZEN, and committing.
- **Placeholders.** Every value that depends on dev is `[FROM BFCL DEV: …]`, naming the script and key that fill it.
  Any placeholder left blocks the freeze.
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
| prefix_zs_m6 | zs | replays the first 6 actions, then hands off | P3, B1 |
| prefix_zs_m2, _m4 | zs | the same at m = 2 and 4 | S1 |
| plan_zs (`prompt_only`) | zs | the first plan only | S5 |
| executor_alone_zs | zs | zero-shot floor | S4, S5 |
| prefix_bplus_m2, _m4, _m6 | bplus | secondary: J10's P3 receiver | S2, S3 |
| executor_alone_bplus | bplus | secondary: out-of-domain adapter floor | S4 |

- **P3 registers on `zs`**, a choice dev §6 leaves open. `zs` is BFCL's primary receiver (dev §4). `bplus` is the
  AppWorld adapter, run out of domain because BFCL has no train split. J10's P3 rests on in-domain tailoring, which
  no BFCL arm has; the untailored contrast is J10's own second B1 row (J10 :727). The choice is made on design
  grounds, before the dev read, so it cannot track the dev effect.
- **The bplus arms stay, as secondary.** They cost no hosted calls, and S3 is the literal J10 P3 contrast. Dropping
  them would save only GPU hours.
- **`qzs` stays dev-only.** The revised dev §4 and §6 add it "on dev only" (as X2), and no mirrored prediction uses
  it. A `qzs` test arm would need an amendment and a budget before freeze.

## 3. Hosted-call budget (300 episodes per arm)

The planning rates are those of scoping §3 (`docs/second_env_scoping_20260923.md:161-165`), as dev §5 uses them.
The measured column replaces them before freeze.

| arm | calls/ep | planning calls | ceiling = high end × 300 | measured on dev: `calls_live` / `calls_attributed` per ep |
|---|---|---|---|---|
| planner_alone_cap81 | 12 | 12 × 300 = 3,600 | 16 × 300 = 4,800 | [FROM BFCL DEV: bfcl_dev_report `arms.planner_alone_cap81.calls_*_mean`] |
| takeover_k5 | 3 | 3 × 300 = 900 | 4 × 300 = 1,200 | [FROM BFCL DEV: same keys, takeover_k5] |
| advise_k5_fullctx | 3 | 900 | 1,200 | [FROM BFCL DEV: same keys, advise_k5_fullctx] |
| advise_k5_neutral | 3 | 900 | 1,200 | [FROM BFCL DEV: same keys, advise_k5_neutral] |
| plan_zs | 1 | 1 × 300 = 300 | 2 × 300 = 600 | [FROM BFCL DEV: same keys, plan_zs] |
| prefix ×6, executor_alone ×2 | 0 | 0 (2,400 GPU episodes) | gated on 0 live calls | [FROM BFCL DEV: live ask calls per arm] |
| **arms** | | **6,600** | **9,000** | |
| smokes, never analysed (scoping §3's dry run) | | ≤ 100 | | |
| retries, 10 % of 6,700 | | 670 | | |
| **planning total** | | **≈ 7,370** | | |
| planless keys (§7), only if the case arises | ≤ 2 per key per arm | ≤ 2 × 15 × 4 = 120 | | |

The plan's ≈ 7,300 (`plan_luna_reset:104`) is this design, to rounding. [Inferred: the plan does not derive it.] The
caps that bind are the wrapper's per-arm `MAX_PLANNER_CALLS` (dev §5). Calls are reported under both J10 Am4
conventions (J10 :1006-1015).

## 4. Registered predictions

**Mapping from J10.** k = 5 plays J10's k = 10 (dev §4). **m = 6 plays J10's m = 11**: the deepest registered depth,
where P3 and B1 sit (J10 :363, :722-727). m = 4 has no J10 analogue. On dev, the per-call handoff shares at m = 2, 4
and 6 are 1.00, 0.96 and 0.84 (dev §3).

**Common to every prediction.**
- The metric is `goal_pass_rate`.
- The estimand is the mean of left − right over the 300 pairs, in pp, less the keys §7 removes. It is computed as
  written, never by negating a stored reverse (J10 :253-254).
- Intervals are 95 % percentile and entry-clustered (§5).
- An interval condition counts only if the unadjusted interval meets it **and** the adjusted p is ≤ 0.05
  (J10 :287-289).

| id | contrast (left − right) | family | rule; p | dev value |
|---|---|---|---|---|
| **P6**, primary | `takeover_k5 − advise_k5_fullctx` | H (Holm, m = 2) | positive, CI excluding 0; two-sided p at 0 | [FROM BFCL DEV: diff_pp, entry CI, per-pair SD; bfcl_dev_report `contrasts.P6`] |
| **P3**, secondary | `prefix_zs_m6 − planner_alone_cap81`, all episodes | H | lower bound above **−7.00 pp**; p = 2 × share ≤ −7.00 (`direction="greater"`) | [FROM BFCL DEV: bfcl_dev_report `contrasts.P3_zs_m6`] |
| **CF1** | `advise_k5_neutral − advise_k5_fullctx` | CF (m = 1) | positive, CI excluding 0; two-sided p at 0 | [FROM BFCL DEV: bfcl_dev_report `contrasts.CF1`] |

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
- Dev: [FROM BFCL DEV: diff_pp, CI, n_handoff; bfcl_dev_report `contrasts.B1_zs_m6_hstar`, `B1_bplus_m6_hstar`].

**Supporting contrasts.** Pre-specified, not decision-bearing, unadjusted, and labelled.

| id | contrast | note |
|---|---|---|
| S1, S2 | `prefix_<r>_m6 − prefix_<r>_m2`, for r = zs and bplus, with m4 between | depth span |
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
  stream apart from the stream that chose the test entries.
- **Holm.** Step-down at α = 0.05 within H = {P6, P3} (`holm_adjust` `:2061`), with `bootstrap_pvalue` (`:2038`) in
  §4's forms. CF has one member. Every other row is unadjusted, and none is promoted after the read (J10 :295-296).
- **Boundary rule** (J10 :300-308). A decision-bearing bound within 1.00 pp of its threshold is recomputed at seeds
  {20260925, 1, 2, 3, 7, 101, 999} and at 200,000 resamples. If any seed flips the verdict, the prediction is
  reported as **on the boundary**.
- **Sign-flip p** (J10 :312-318), not decision-bearing. It is Monte Carlo, 100,000 patterns at seed 20260925,
  because 150 > 20 clusters; for P3 it is one-sided at −7.00. A disagreement goes in the verdict's sentence.
- **BY-FDR companion** (J10 Am1 §F :837-849; `am1_by_fdr` `:3389`). Benjamini–Yekutieli over every printed paired
  `goal_pass_rate` contrast, each counted once: P6, P3, CF1, the two B1 rows, S1–S5 and CF3, which is 11. Each uses
  its two-sided p at its threshold. A rejection that would not survive is flagged; no verdict changes.
- **`success`** gets the same intervals and no rule. A bound on its nearest atom is reported as such (J10 :275-277).

## 6. Power: what to run on BFCL dev before freeze

This is a new script, `scripts/analysis/bfcl_power.py`. It mirrors `scripts/analysis/am1_power.py` function by
function and writes `campaign/results/bfcl_power_dev_<date>.report.json`.

| am1_power.py | BFCL version |
|---|---|
| `ARMS` (:57-70) | `bfcl_<arm>_dev_20260924`, seeds 1–3 (dev §4) |
| `load_arm` (:98-114) | unchanged, except that h\* from `handoff_control.hstar_flags` replaces `_facts.handoff_occurred` |
| `paired_rows`, `index_by_scenario` (:117-140) | the cluster label is the entry id, not `scenario_of` |
| `draw_design` (:143-160) | 150 entries drawn with replacement from dev's 50, each taking 2 of seeds {1, 2, 3} without replacement |
| `cluster_sums` … `simulate` (:163-302) | unchanged |
| `CONTRASTS` (:73-94) | P6 and P3 in H; CF1 in CF; CF3 two-sided, in no family; B1 for zs and bplus; S3 |
| `build` (:329-361) | power at the dev effect and at half of it (the half-shift at :336-340) |
| `refuse_heldout` (`j16_robustness.py:83`, `:136-140`) | ⚠ knows only `test_normal` and `test_challenge`, so the script must also refuse `_test_` |

- **Settings.** R = 1,000 reads, B = 2,000 each, `--seed` 20260924 (am1_power's default), α = 0.05. Power is
  reported, not used as a gate. First, the dev values are recomputed at 10,000 draws, entry-clustered, and matched
  to the dev report.
- **P6 alone.** P6's power is also given with P6 alone in its family, so the cost of adding P3 is visible before
  freeze (as J10 :779-780).

| row | dev diff, entry CI | per-pair SD | power at dev effect | power at half effect |
|---|---|---|---|---|
| P6 in H | [FROM BFCL DEV: `dev.P6`] | [FROM BFCL DEV: bfcl_dev_report `contrasts.P6.sd_pp`] | [FROM BFCL DEV: `power_at_dev_effect.per_contrast.P6.holm_supported`] | [FROM BFCL DEV: `power_at_half_effect…P6.holm_supported`] |
| P6 alone | as above | as above | [FROM BFCL DEV: the m = 1 run, same key] | [FROM BFCL DEV: the m = 1 run, half] |
| P3 in H | [FROM BFCL DEV: `dev.P3`] | [FROM BFCL DEV: `contrasts.P3_zs_m6.sd_pp`] | [FROM BFCL DEV: `…P3.holm_supported`] | [FROM BFCL DEV: same, half] |
| CF1 | [FROM BFCL DEV: `dev.CF1`] | [FROM BFCL DEV: `contrasts.CF1.sd_pp`] | [FROM BFCL DEV: `…CF1.holm_supported`] | [FROM BFCL DEV: same, half] |
| B1, zs | [FROM BFCL DEV: `dev.P3_handoff_only`, `n_handoff`] | — | [FROM BFCL DEV: `…P3_handoff_only.lower_above`] | [FROM BFCL DEV: same, half] |
| all of H | — | — | [FROM BFCL DEV: `families_all_supported.H`] | [FROM BFCL DEV: same, half] |

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
  every pair stays. A key-exclusion sensitivity is run for P6, P3 and CF1; a verdict that moves is on the boundary.
- **Divergent replay keys** follow J10 Am5 §B (:1104-1126), with the cap at **15** keys (5 % of 300). BFCL hashes
  public state attributes, not printed output (`bfcl_env.py:369-377`, `:605-612`), and spike a matched 4,152 of
  4,152 prefix replays (dev §2).
- **Executor asks** (J10 Am1 §I :881-894). An ask answered live is part of the system. It is counted, bounded at
  count / 300 in pp, and never purged.

**Abort.** The test is **reported as not run**, never at reduced power, if `planner_alone_cap81`, `takeover_k5` or
`advise_k5_fullctx` cannot complete 300 pairs. If `advise_k5_neutral` cannot, CF1 and CF3 are not run, and P6 and
P3 stand. GPU arms are resumed until complete; a contrast on an incomplete arm is not read.

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
  - the counts of planless keys, divergent keys and live asks, including zero; and h\* counts per prefix arm.
- **Exploratory, and labelled so:** results per turn and per `involved_classes` set; the code-block share of
  interventions and the copy rate (J10 Am1 §C); the m4 arms beyond S1 and S2.

**Constraints.**
- **P6** is described as "actions beat the registered correction-prompt advice", with CF1 in the same paragraph
  (J10 :438-443).
- **P3** is described as non-inferiority to the **medium-effort** planner in this harness (J10 Am2 :914-918).
- Every all-episode non-inferiority or depth number is printed with its h\* companion (J10 Am1 §B4).
- `bplus` is "the AppWorld-tailored adapter, out of domain", never "tailored" to BFCL.
- BFCL and J10 are reported side by side, never pooled.

## 9. Open decisions for Claude

1. **P3 margin.** −7.00 pp is carried from J9 and J10; a BFCL margin set after the dev read would see the dev effect.
2. **Holm H = {P6, P3}** mirrors J10. Splitting it, if §6 shows P3 costs P6 materially, needs a J10 Am1 §C disclosure.
3. **Class-set clustering as primary?** It is more conservative, but its cluster count needs a tally of
   `involved_classes` over the test entries. That tally reads task definitions, not results.
4. **Bootstrap seed**: 20260925 here, or J10's 20260924 (`A1_BOOTSTRAP_SEED`, `j10_report.py:1471`).
5. **`plan_zs`** costs ≈ 330 calls with retries, and feeds S5, not a prediction. Keep it?
6. **Names.** `bfcl_dev_report.py`, `bfcl_power.py`, the `sd_pp` keys and `BFCL_CONFIRM` do not exist yet.
7. **Force-quit.** Which `error_type` records upstream's per-turn force-quit, and does the `limit` rate count it?
8. **Ceilings.** How far a ceiling rises if a measured rate exceeds scoping's high end.
