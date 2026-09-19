# Preregistration: B1 clean-counterfactual pilot (`suppress_next`)

**Status**: **FROZEN for submission** — this document is written before any `suppress_next` branch exists (corrected on 2026-09-19 for the symmetric `suppress_next` fix before any data existed). It is to be committed first; the job is submitted afterwards, by the orchestrator, after the planner quota resets (~21:13 on 2026-09-19). A prediction written after the numbers arrive is worth nothing.

**Date**: 2026-09-19  
**Study**: Sidekick / IAES, Gate-B estimand repair  
**Repository**: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`  
**Frozen on**: ____________________  

This document does not amend `docs/prereg_v1.md`. It is the analysis plan for one train-split pilot. H4 in `docs/prereg_v1.md` remains explicitly conditional on this pilot demonstrating trainable label signal [OBSERVED docs/prereg_v1.md:50-51].

---

## 1. The claim being tested

The J6 branch experiment claims to measure `Q(intervention present) − Q(intervention omitted)`. Until the `suppress_next` mode landed, both arms kept the reviewer live after the focal step, so the untreated arm received a near-substitute review about five steps later. The contrast measured **timing, not value**.

That is a measured claim, not a guess. On **train**, Spearman ρ(`n_later`, Δ) = **−0.1633780546**, permutation p = **0.000700** (7/10000) [OBSERVED campaign/workers/W25_SUBSTITUTION.md:139] [OBSERVED campaign/workers/scratch_W25/w25_out.txt:92-93]. On the post-hoc clean subset (`n_later = 0`, 175 complete train points) `needed` at δ = 0.166 clears its paired sign-flip null at **p = 0.005100** (51/10000), versus **p = 0.712400** (7124/10000) over all 397 complete train points [OBSERVED campaign/workers/W25_SUBSTITUTION.md:158] [OBSERVED campaign/workers/W24_PERMNULL.md:54].

Two reasons that is not yet a result: the `n_later = 0` cut is **doubly post-hoc**, and **dev does not reproduce** the dose-response (ρ = **+0.0948570700**, permutation p = **0.083800**) [OBSERVED campaign/workers/W25_SUBSTITUTION.md:140]. This pilot tests the substitution account **prospectively**.

`--untreated-mode suppress_next` (A8, corrected to symmetric suppression by A17) suppresses, in **both** arms, the scheduled tick at `s` **and the next scheduled tick the schedule would actually have fired after `s`** (`skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT`) [OBSERVED scripts/setup/branch_counterfactual.py:82-92, 1022] [OBSERVED campaign/workers/STATUS_A_17.md:24-29]. The treated arm injects the correction at `s` and skips the next scheduled tick; the untreated arm omits the review at `s` and skips the next scheduled tick. Later ticks after that stay live in both arms.

⚠ **Specification clashes, recorded rather than silently fixed.**
1. **Residual later reviews:** The original unit brief states that `suppress_next` makes `n_later = 0` **by construction**. The frozen estimand string and code do not do that: one future tick is suppressed, but later reviews after that suppressed tick remain live [OBSERVED scripts/setup/branch_counterfactual.py:82-92]. This pilot runs the mode as implemented. `n_later` on both arms is a **manipulation check**, reported as secondary, not a gate. A result in which the first substitute is gone but later ticks still fire is still the experiment that was built.
2. **Arm-asymmetry defect (fixed in code):** The initial A8 implementation suppressed the next review in the untreated arm only, leaving the treated arm with an extra review. Because reviews were measured at +27.19 pp TGC in J8a (CI [16.67, 37.72]) [OBSERVED campaign/workers/A15_J8A.md], an asymmetric design confounded the intervention with an extra review. A17 fixed this specification defect in code by making suppression symmetric across both arms [OBSERVED scripts/setup/branch_counterfactual.py:1022] [OBSERVED campaign/workers/STATUS_A_17.md:17-32].

The estimand this job actually runs, copied from the frozen strings:

> `Q(policy with intervention i present) - Q(policy with intervention i omitted); the next scheduled review after s is suppressed in both arms; later reviews after that stay live`
> [OBSERVED scripts/setup/branch_counterfactual.py:88-91]

---

## 2. Design (decided; do not reopen)

| Field | Frozen value | Why |
|---|---|---|
| Split | AppWorld `train` only | The substitution signal that licenses the pilot was measured on train; test splits stay untouched [OBSERVED AGENTS.md:64]. |
| Source campaign | `/scratch/n12194778/sidekick/results/hj4_correction_train_20260917` | Same prefix J6 branched from [OBSERVED campaign/workers/scratch_A16/enumerate_frame.py job 25463506.aqua; j6 manifest `source_campaign`]. |
| Config | `configs/hj4_correction.yaml` | Same executor, adapter alias `sft_b`, limits, and planner as J6 [OBSERVED configs/hj4_correction.yaml:11-42] [OBSERVED scripts/pbs/hj6_branches.pbs:76-77]. |
| Untreated mode | `suppress_next` | A8 clean-counterfactual mode [OBSERVED scripts/setup/branch_counterfactual.py:67, 1441-1448]. |
| Branch seeds | `101 102 103 104` | Four replicates per condition, matching J6/W-20/W-24 completeness. The script default is only `(101, 102)`; four seeds are passed explicitly [OBSERVED campaign/workers/W24_PERMNULL.md:28] [OBSERVED scripts/setup/branch_counterfactual.py:61] [OBSERVED scripts/pbs/hj6_branches.pbs:81]. |
| Temperature | 0.7 | Frozen branch sampling [OBSERVED scripts/setup/branch_counterfactual.py:60, 778]. |
| δ (primary labels) | **0.166** | Frozen train band: 75th percentile of \|treated[101] − treated[102]\| [OBSERVED scripts/setup/branch_counterfactual.py:298-303] [OBSERVED campaign/RUNS.md:1720, 1770]. The J6 train manifest stores `0.16599999999999993`; analysis treats that as 0.166, as A9 did [OBSERVED campaign/workers/scratch_A16 job 25463506.aqua; campaign/workers/A9_THRESHOLD.md:15-17]. |
| Points | **200** train intervention points, frozen list below | Brief: “~200 train points not previously used for a clean-mode branch”. |
| Conditions | treated, untreated | Unchanged [OBSERVED scripts/setup/branch_counterfactual.py:65]. |
| Permutations | **10,000** paired sign-flips | Same null as W-24/W-25 [OBSERVED campaign/workers/W24_PERMNULL.md:8, 18]. |
| Permutation RNG | `numpy.random.default_rng(20260918)` | Same seed as W-24/W-25; a **new** Generator used only on this pilot’s complete matrix (do not chain a second split) [OBSERVED campaign/workers/scratch_W24/permnull.py:25, 365]. |
| Point-selection RNG | `random.Random(20260916)` (stdlib, CPython 3.12.13) | Stated before the draw; not the W-24/W-25 permutation seed [OBSERVED job 25463680.aqua python=3.12.13]. |

Nothing in this table is tuned after looking at `suppress_next` outcomes. There are no `suppress_next` outcomes: zero manifests under `/scratch/n12194778/sidekick/results/*/manifest.json` currently carry `untreated_mode: suppress_next` [OBSERVED job 25463506.aqua `existing_suppress_next_manifests=[]`].

---

## 3. Point selection (deterministic, frozen before the run)

The frozen script enumerates **every** intervention point in `--campaign-root`. On this source that is **777** points × 2 conditions × 4 seeds = **6,216** branches [OBSERVED job 25463680.aqua `collect_jobs_unfiltered=6216`; campaign/workers/W24_PERMNULL.md:32]. Submitting that tree without a filter would repeat J6’s unbounded train rollout. The CLI has no `--points` flag [OBSERVED scripts/setup/branch_counterfactual.py:1395-1449]. `--limit 1600` would take the first 200 points in `iter_episode_dirs` order (sorted seed dir, sorted task dir, then `i`), which is an ordering **without** a seed and is not this sample [OBSERVED scripts/setup/branch_counterfactual.py:442-453, 1174-1212].

**Frame.** Every unique `(seed, task_id, i)` present in `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl` after last-row-wins. That file is the J6 enumeration of the J4 train interventions: **777** points, of which **397** complete under `schedule_live` [OBSERVED job 25463506.aqua; campaign/workers/W24_PERMNULL.md:32]. No point in that frame has a clean-mode branch.

**Exclusion.** Drop any `(seed, task_id, i)` that already appears in a `suppress_next` `branch_runs.jsonl`. The exclusion set is empty today [OBSERVED job 25463506.aqua].

**Why the frame is all 777, not the 397 J6-complete.** Restricting to J6-complete would select on success under the *contaminated* estimand. The brief asks for train points not previously used for a **clean-mode** branch, not for a new draw from the post-hoc `n_later = 0` subset. The seeded shuffle therefore runs over all 777. Consequence, stated in advance: of the 200 drawn, **100** were J6-complete and **100** were J6-incomplete [OBSERVED job 25463506.aqua `sample_j6_complete=100`]. Completeness under `suppress_next` is not known and is not imputed. Expected primary-population size, if the J6-complete half kept J6’s non-ceiling rate 266/397, is about 67 from that half plus an unknown contribution from the incomplete half [INFERRED from job 25463506.aqua and campaign/workers/W20_CEILING.md:53-56]. Low realised `n` reduces power; it is not a licence to redraw.

**Ordering + seed.**

1. Build the list of eligible `(seed, task_id, i)` tuples.
2. Sort lexicographically: `seed` ascending, then `task_id` ascending, then `i` ascending.
3. Shuffle in place with `random.Random(20260916)` (CPython 3.12 Fisher–Yates).
4. Take the first **200**.

The draw was executed once, before this document was frozen, in PBS job **25463506.aqua**, interpreter `/scratch/n12194778/sidekick/env/bin/python` (CPython 3.12.13). SHA-256 of the sorted lines `"{seed}\t{task_id}\t{i}\n"` is

`4ec6fa2733a141da4335240c215b605ff466e2d85a0a0f7ce55179a6ef5b1017`

[OBSERVED job 25463506.aqua]. The slash form `seed/task_id/i` is stored at `campaign/workers/scratch_A16/b1_pilot_points.txt` and copied in the appendix. Regenerating the shuffle on another Python must not replace this list; the appendix is the sample.

**How the frozen script sees only these 200.** The orchestrator does **not** edit `scripts/setup/branch_counterfactual.py`. It runs `campaign/workers/scratch_A16/run_b1_pilot.py`, which monkey-patches `collect_jobs` and refuses to start if the filter does not yield 200 unique points. A direct `python scripts/setup/branch_counterfactual.py ...` on this campaign-root would dispatch 6,216 branches and is a protocol violation.

---

## 4. Primary population

A point is **complete** when seeds `{101,102,103,104}` are present in both conditions with non-null `branch_gpr`. That is W-20 / W-24 `complete()` [OBSERVED campaign/workers/scratch_W24/permnull.py:46-51]. Incomplete points stay in the campaign file with their `error_type`; they are never imputed; they are excluded from Δ and from the permutation.

The **primary population** is the complete points with `mean(untreated) < 1.000`, where the mean is the arithmetic mean of the four untreated `branch_gpr` values. Ceiling points (`mean(untreated) ≥ 1.000`) are structurally incapable of expressing the `needed` label: GPR ≤ 1 implies `mean(treated) ≤ 1`, so Δ ≤ 0 and `help = 0` by construction [OBSERVED campaign/workers/W20_CEILING.md:21-25]. Including them moves a denominator without ever moving a `needed` numerator. On J6 train, excluding ceiling (and floor) did not change the `needed` count by a single point at δ = 0.166 [OBSERVED campaign/workers/W20_CEILING.md:27-28].

This exclusion is fixed in advance. The mask is computed **once** from the observed (unpermuted) replicate means of **this** pilot, then **held fixed** during permutation, as W-24 did [OBSERVED campaign/workers/scratch_W24/permnull.py:88-102, 361]. It is not re-derived after each sign-flip.

⚠ **Definition clash with W-20, recorded rather than silently merged.** W-20/W-24 “contestable” also drops floor points (`mean(untreated) ≤ 0` and `mean(treated) ≤ 0`). This document follows the A16 brief: primary = `mean(untreated) < 1.000`. Floors remain in the primary population. On J6 train that was a 3-point difference (266 vs 263) [OBSERVED job 25463506.aqua; campaign/workers/W20_CEILING.md:55-56]. Floor Δ is 0 by construction; keeping them is slightly conservative for B1a.

**All-points results** (every complete point, ceilings included) are reported **alongside**, always, whatever they show. They do not gate.

---

## 5. Primary hypotheses (both must hold)

Let Δ for a complete point be the mean of the four paired differences

`Δ = (1/4) Σ_s (treated_gpr[s] − untreated_gpr[s])`

which is `delta_crn` in `assemble_point_record` and `diffs.mean(axis=1)` in W-24 [OBSERVED scripts/setup/branch_counterfactual.py:601-619] [OBSERVED campaign/workers/scratch_W24/permnull.py:243-245]. Labels at the frozen band:

- `needed` iff `Δ > 0.166`
- `needless` iff `Δ < −0.166`
- `ambiguous` otherwise

[OBSERVED scripts/setup/branch_counterfactual.py:285-287]. `harmful` is `needless` at this band [OBSERVED scripts/setup/branch_counterfactual.py:293]. Missing any of the eight `branch_gpr` values → `label_status = incomplete`, no label, never imputed [OBSERVED scripts/setup/branch_counterfactual.py:266-282].

**B1a.** On the primary population, mean Δ (treated − untreated) **> 0** and is outside its paired sign-flip null at one-sided **p < 0.05**.

Operationalised: `p_one_sided = n(perm ≥ observed) / 10000 < 0.05`, and the observed mean Δ is strictly positive. “Outside the null” is that p-value, the same `p_one_sided_ge` W-24 reported [OBSERVED campaign/workers/scratch_W24/permnull.py:171-194, 22]. The 2.5th/97.5th null percentiles are printed; they do not replace the p-value as the gate.

**B1b.** On the same primary population, at δ = 0.166, asymmetry (`needed` − `needless`) **> 0** against the same null, two-sided **p < 0.05**.

Operationalised: observed (`needed` − `needless`) is strictly positive, and `p_two_sided = n(|perm| ≥ |observed|) / 10000 < 0.05` [OBSERVED campaign/workers/scratch_W24/permnull.py:22, 190].

The permutation itself is W-24’s paired sign-flip, not a pooled reshuffle: for each complete point and independently for each branch seed `s`, swap `treated[s]` with `untreated[s]` with probability 0.5; equivalent to multiplying the per-seed difference by ±1; then recompute Δ, labels, and every statistic [OBSERVED campaign/workers/scratch_W24/permnull.py:16-18, 273-277]. Implementation: `flips = rng.random((10000, n_complete, 4)) < 0.5` on the **full complete matrix**, then restrict statistics with the frozen primary-population mask [OBSERVED campaign/workers/scratch_W24/permnull.py:275-293]. Null 2.5th/97.5th = `numpy.percentile(..., [2.5, 97.5])` linear [OBSERVED campaign/workers/scratch_W24/permnull.py:27, 173].

The analysis is a rerun of `campaign/workers/scratch_W24/permnull.py` functions (`complete`, `matrices_from_complete`, `stats_from_delta`, `null_stats_from_perm_delta`, `summarize_null`) on the pilot `branch_runs.jsonl`, with the primary mask `mean(untreated) < 1.000` in place of W-20’s non-ceiling-and-non-floor mask. It is not a new test invented after seeing the numbers.

---

## 6. Decision rule (fixed now)

- **Both hold** → the substitution explanation is supported prospectively; `sft_c` becomes trainable and H4 returns to the plan.
- **Neither holds** → removing the first substitute does not recover the intervention’s value; H4 stays closed and the campaign reports a negative result **with a mechanism**. That is a publishable outcome, not a failure.
- **Exactly one holds** → **inconclusive**. Report B1a and B1b as measured. Spend no further quota on this estimand without a new plan.

The inconclusive branch is written here because it is the one most likely to be rationalised later (“B1a was close”, “needed recovered but mean Δ did not”). Close is not a pass. One of two is not both.

No other statistic — `needed` count alone, mean help, mean harm, δ = 0.100, `n_later`, the all-points table, or a mode-to-mode contrast — may be promoted into this rule after the data exist.

---

## 7. Secondary outcomes (reported, not gating)

Every item in this section is **secondary**. None of them can reopen H4, unpause `sft_c`, or convert an inconclusive primary into a pass.

1. **`needed` count** (and `f = needed / n`) against the same sign-flip null, one-sided, at δ = 0.166, on the primary population and on all complete points.
2. **Mean help** `mean(max(Δ, 0))` and **mean harm** `mean(max(−Δ, 0))` against the same null, one-sided, on both populations. These do not depend on δ [OBSERVED campaign/workers/W25_SUBSTITUTION.md:176].
3. **The δ = 0.100 band**: `needed`, `needless`, asymmetry, and `f` at 0.100, same null, both populations. Mean Δ / help / harm are not re-reported as a second finding; they are the same numbers as (2).
4. **Manipulation check, `n_later` (both arms).** For each complete point and condition (treated and untreated), `n_later` is the count of `event_type == "intervention"` events with `source == "live_policy"` and `step > s` on each replicate, then the median across the four replicates for that arm, following W-25 [OBSERVED campaign/workers/W25_SUBSTITUTION.md:21] [OBSERVED scripts/setup/branch_counterfactual.py:520-524]. Under symmetric suppression, the manipulation check must also verify that the **treated** arm lost its tick at `t` (guarding against a regression of the arm-asymmetry bug). Report later-review counts and histograms for treated and untreated arms **separately**; they should be equal in distribution. Report the fraction with median 0 and the fraction with *all four* replicates at 0 for each arm. The brief’s “zero by construction” claim is tested here; it is not assumed. If median `n_later` is not materially lower than the paired J6 `schedule_live` value on the overlapping complete points, or if the two arms diverge in later review counts, the instrument did not behave as intended and the primary tests are still reported but are not a clean test of substitution.

   **Residual `n_later` benchmark (frozen 200-point list):**
   From the frozen 200-point list and J6 untreated replicates [OBSERVED campaign/workers/STATUS_A_17.md:130-156]:
   - Point-level median of `max(0, n_later − 1)` on the frozen 200: **median 0.0**, mean 0.235, min 0, max 4; 161/200 points at 0.
   - Replicate level (800 untreated rows): **median 0.0**, mean 0.47125; 607/800 at 0.
   - **If** a branch ran to `max_steps = 40`, the live schedule after `t` still has median **5** remaining ticks (mean 4.51, 174/200 points at 3+) — that is the policy remainder, not what J6 lived long enough to receive.
   - ⚠ **Length-held-fixed proxy caveat:** This quantity is computed from J6 `schedule_live` replicates [INFERRED]. If skipping `t` changes when an episode ends, the residual changes with it. No `suppress_next` data exists yet.
5. **Mode-to-mode comparison**, only for points that have a complete J6 `schedule_live` result **and** a complete `suppress_next` result. 100 of the 200 frozen points are J6-complete today [OBSERVED job 25463506.aqua]. For those that complete in the pilot, report paired (Δ_suppress_next − Δ_schedule_live), mean Δ in each mode, and `needed`/`needless` at δ = 0.166 in each mode. Direction stated in advance: if substitution was the problem, mean Δ and (`needed` − `needless`) should be larger (more positive) under `suppress_next`. This contrast is descriptive. It does not gate.

Identity check, printed, not a hypothesis: `mean(treated) + mean(harm) = mean(untreated) + mean(help)` on every reported subset, absolute difference < 1e-12 [OBSERVED campaign/workers/W24_PERMNULL.md:37-44].

---

## 8. Cost: PREFLIGHT, expected spend, and the hard cap

The script prints, before any branch runs:

```
PREFLIGHT {
  "branches_to_run": <n_jobs>,
  "per_branch_planner_call_factor": <limits.max_planner_calls>,
  "projected_planner_calls": <n_jobs * factor>,
  "factor_source": "config limits.max_planner_calls (per-episode cap)",
  "max_planner_calls_total": <cap>
}
```

[OBSERVED scripts/setup/branch_counterfactual.py:1270-1288]. That projection is an **upper bound**: it assumes every branch spends the per-episode cap. In `configs/hj4_correction.yaml` that cap is **81** [OBSERVED configs/hj4_correction.yaml:42].

The filter was applied in PBS job **25463680.aqua** (read-only `collect_jobs`, zero branches executed, zero planner calls):

```
collect_jobs_unfiltered=6216
collect_jobs_filtered=1600
filtered_unique_points=200
frozen_keys_missing_from_collect=0
PREFLIGHT {"branches_to_run": 1600, "factor_source": "config limits.max_planner_calls (per-episode cap)", "max_planner_calls_total": 10000, "per_branch_planner_call_factor": 81, "projected_planner_calls": 129600}
no_branches_executed=True
```

[OBSERVED job 25463680.aqua]. So the script’s own projection for this sample is **129,600** planner calls. That number would not have stopped J6 (J6 spent 37,368 against a table that budgeted zero) [OBSERVED docs/FOLLOWUPS.md:684-690, 821]. It is recorded because it is what PREFLIGHT prints. It is not the campaign budget.

**Arithmetic expected spend**, not a planner call: J6 train ran 6,216 branches and spent **23,769** hosted planner calls [OBSERVED docs/FOLLOWUPS.md:688]. Mean = 23769/6216 = **3.823841698…** calls/branch. For 1,600 branches that is **6,118** calls [INFERRED 23769 × 1600 / 6216]. `suppress_next` can only *reduce* live reviews relative to J6 in both arms (as the next scheduled review is suppressed in both), so 6,118 is, if anything, a slightly more conservative centre than before [INFERRED]. Per-row `branch_planner_calls` was not present on the J6 jsonl rows this unit read (the field was added later); the FOLLOWUPS totals are the source [OBSERVED job 25463506.aqua: the calls list was empty, so no p95 is claimed].

**Hard cap, proposed: `--max-planner-calls-total 10000`.**

- About 1.63 × the J6-mean projection (10000/6118) [INFERRED].
- Allows a mean of 6.25 calls/branch (10000/1600) before the dispatcher stops [INFERRED].
- Well below J6 train-alone (23,769) and J6 total (37,368) [OBSERVED docs/FOLLOWUPS.md:688-690].
- The per-branch loop cap remains 81; unknown per-row cost is charged at 81, never silently 0 [OBSERVED scripts/setup/branch_counterfactual.py:1291-1295].
- When the running total crosses 10,000 the script stops dispatching new branches, aggregates, prints `PLANNER_BUDGET_STOPPED`, and exits 0; `--resume` continues [OBSERVED scripts/setup/branch_counterfactual.py:1365-1378, 1432-1439].

If 10,000 is exhausted before 1,600 branches have been dispatched, that is a **truncated run** (section 9). Do not raise the cap after seeing partial Δ.

---

## 9. Stopping, resume, and truncation

**Planned sample** = the 200 frozen points × 2 conditions × 4 seeds = 1,600 branches. The analysis population is the complete primary-population subset of those 200. We do not redraw, drop, or replace points after outcomes are visible.

**Infrastructure death** (PBS preemption, node loss, vLLM crash, network reset): resume with `--resume` (script default `True` [OBSERVED scripts/setup/branch_counterfactual.py:1407]) against the **same** `--out-root`. Resume keys on `(point, condition, branch_seed)` [OBSERVED scripts/setup/branch_counterfactual.py:14]. Derived files are rebuilt from `branch_runs.jsonl`; a kill never drops a finished branch [OBSERVED scripts/setup/branch_counterfactual.py:14-15]. Crashed/error rows are retried (`retry_errors=True` default) [OBSERVED scripts/setup/branch_counterfactual.py:1431].

**Budget stop** (`PLANNER_BUDGET_STOPPED`): do **not** analyse the dispatched prefix as if it were the planned 200. The remaining jobs are the later keys in `collect_jobs` order after the filter, i.e. not a random subsample of the frozen 200. Either resume after quota (same out-root, same cap or a newly preregistered cap) until 1,600 have been dispatched, or declare the run truncated and **do not evaluate B1a/B1b**. Report n dispatched, n complete, and spend. Truncation is inconclusive by stopping, not by mixed hypotheses.

**Behavioural failures** (parse errors, AppWorld exceptions, context overflow): logged with `error_type`, scored as incomplete for that branch, **never retried as a new point**. Failed, crashed, and timed-out runs stay in `branch_runs.jsonl`. The denominator of completeness is part of the claim [OBSERVED AGENTS.md:66].

**When analysis may run.** Only when (a) all 1,600 branches have been dispatched and resume has no remaining retryable errors, or (b) the run has been declared truncated under the budget rule above, in which case B1a/B1b are **not** evaluated. Looking at a live `branches.jsonl` before that point in order to decide whether to continue is a protocol violation.

**Quota-stall.** If cumulative `api_error + timeout` among dispatched branches exceeds 5% of dispatched branches, pause and resume after quota rather than interpreting the labels [OBSERVED docs/prereg_v1.md:207, adapted to this pilot’s branch as the unit].

---

## 10. What would falsify it

A prediction with no falsifier is not a prediction.

**The effect is absent** if, on the primary population of this `suppress_next` sample, **neither** B1a nor B1b holds: mean Δ is not significantly positive (one-sided p ≥ 0.05, or mean Δ ≤ 0), **and** (`needed` − `needless`) at δ = 0.166 is not significantly positive (two-sided p ≥ 0.05, or asymmetry ≤ 0). That is the “neither holds” branch of section 6. It means: suppressing the next scheduled review after `s` does not recover a positive mean contrast or a `needed` > `needless` asymmetry. H4 stays closed. The campaign reports a negative result with a mechanism.

Also falsifying as a *test of substitution*, but not recoded as a primary pass: if the manipulation check shows untreated median `n_later` indistinguishable from the paired J6 `schedule_live` values, the instrument failed and the primary tests are not a clean counterfactual. That is reported; it does not get a second, quieter estimand.

What is **not** a falsifier: a miss at δ = 0.100, a miss on all-complete (ceilings in), a miss on mean help/harm, a miss on the mode-to-mode contrast, or a small realised `n`. Those are secondary or power.

---

## 11. What this licenses (and what it does not)

Copied from the decision rule, so it cannot drift:

- Both hold → `sft_c` becomes trainable; H4 returns to the plan.
- Neither holds → `sft_c` stays paused; H4 stays closed; the negative is reported with the substitution mechanism.
- Exactly one holds → inconclusive; no further quota on this estimand without a new plan.

This pilot does not touch `test_normal` or `test_challenge`. It does not retune δ. It does not relabel J6. It does not authorise mass J6 recovery.

---

## 12. Threats, and clashes with the unit brief

1. **`n_later = 0` is not guaranteed.** `suppress_next` suppresses one future scheduled tick (`t`) in both arms, not every later review [OBSERVED scripts/setup/branch_counterfactual.py:82-92, 1022]. The brief’s “by construction” sentence remains wrong of the code. The manipulation check exists because of this. The primary hypotheses are still B1a and B1b as specified; they were not rewritten into “test only the `n_later = 0` subset of the pilot”.
2. **The train path recomputes δ.** `run_branches` sets `freeze_from_train=(split == "train")`, and `rebuild_derived` then replaces `--delta-band-delta` with the 75th percentile of \|treated[101] − treated[102]\| **on this 200-point run** whenever that percentile is computable [OBSERVED scripts/setup/branch_counterfactual.py:816-818, 1350-1358]. The frozen band is 0.166 over J6 train, not over this subsample. **Labels for B1a/B1b are computed at 0.166 from the raw `branch_gpr` vectors, ignoring whatever `manifest.json` writes.** The script is not edited to change that behaviour.
3. **No `--points` flag.** Unfiltered submission is 6,216 branches / PREFLIGHT 503,496. The wrapper in section 13 is mandatory.
4. **Contestable definitions.** Primary here is `mean(untreated) < 1.000`. W-20 also dropped floors. All-points is always printed.
5. **Power.** A 200-point draw from 777, half J6-incomplete, may yield a primary `n` well below W-25’s post-hoc 78 contestable `n_later = 0` points. Failure to reject is then ambiguous between “no effect” and “not enough complete contestable points”. That ambiguity is still “neither holds” or “inconclusive” under section 6; it is not a reason to peek and enlarge the sample.
6. **Mode-to-mode is not randomised.** The 100 J6-complete points in the draw are a property of the shuffle, frozen now, not chosen to maximise overlap with W-25’s clean subset.
7. **Router/oracle ticks are not suppressed.** A8 left those live on purpose [OBSERVED campaign/workers/STATUS_A_8.md:22-27, 74-81]. Branch runs set `planner_drives=False` and `allow_executor_ask=False`, so the scheduled tick is the live path in practice [OBSERVED campaign/workers/STATUS_A_8.md:24-27].

---

## 13. Submission command (for the orchestrator; not this unit)

Do not submit before the quota reset (~21:13 local, 2026-09-19). Do not write into `hj6_branches_train_20260917`. Do not invoke this from `aquarius01` except as `qsub`.

Copy `scripts/pbs/hj6_branches.pbs` to a new file the orchestrator owns (this unit must not touch `scripts/pbs/`). Keep the vLLM block, LoRA aliases, and preflight-auth checks. Replace only the campaign id, out-root, and the Python invocation:

```bash
# After quota reset. Orchestrator only.
SPLIT=train
DATE=20260919
CID=b1_pilot_train_${DATE}
REPO=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
CAMPAIGN_ROOT=/scratch/n12194778/sidekick/results/hj4_correction_train_20260917
CFG=${REPO}/configs/hj4_correction.yaml
OUT=/scratch/n12194778/sidekick/results/${CID}
ADAPTER_SFT_B=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_s123_granite8b
ALIAS_SFT_B=sft_b
PY=/scratch/n12194778/sidekick/env/bin/python

# qsub the PBS copy, with vLLM as in hj6_branches.pbs, then:
export PYTHONPATH="${REPO}/src:${REPO}/scripts/setup:${PYTHONPATH:-}"
timeout 35100 "${PY}" "${REPO}/campaign/workers/scratch_A16/run_b1_pilot.py" \
  --campaign-root "${CAMPAIGN_ROOT}" \
  --split train \
  --out-root "${OUT}" \
  --branch-seeds 101 102 103 104 \
  --workers 10 \
  --resume \
  --env appworld \
  --config "${CFG}" \
  --delta-band-delta 0.166 \
  --untreated-mode suppress_next \
  --max-planner-calls-total 10000
```

Confirm the job’s stdout begins with `PREFLIGHT {"branches_to_run": 1600, ..., "projected_planner_calls": 129600, "max_planner_calls_total": 10000}` before leaving it running. If `branches_to_run` is 6216, kill the job; the wrapper was not used.

---

## Appendix. Frozen 200-point list

Format `seed/task_id/i`. Sorted. SHA-256 of the tab-separated equivalent is `4ec6fa2733a141da4335240c215b605ff466e2d85a0a0f7ce55179a6ef5b1017` [OBSERVED job 25463506.aqua]. Machine-readable copy: `campaign/workers/scratch_A16/b1_pilot_points.txt`.

```
1/07b42fd_3/3
1/07b42fd_3/5
1/229360a_2/1
1/229360a_3/2
1/229360a_3/3
1/22cc237_1/1
1/22cc237_2/1
1/27e1026_3/0
1/287e338_3/1
1/29caf6f_2/1
1/2a163ab_1/0
1/2a163ab_2/1
1/2a163ab_3/0
1/2a163ab_3/2
1/302c169_1/0
1/302c169_3/0
1/34d9492_2/1
1/34d9492_2/2
1/3c13f5a_1/2
1/3c13f5a_1/4
1/3c13f5a_1/5
1/3c13f5a_3/1
1/3c13f5a_3/3
1/60d0b5b_1/0
1/60d0b5b_3/1
1/6104387_1/0
1/6104387_1/3
1/6104387_1/5
1/6104387_1/6
1/692c77d_1/0
1/692c77d_3/2
1/7d7fbf6_1/2
1/7d7fbf6_1/4
1/7d7fbf6_2/0
1/7d7fbf6_3/2
1/82e2fac_2/1
1/82e2fac_3/0
1/aa8502b_1/0
1/aa8502b_1/1
1/afc0fce_2/1
1/b0a8eae_2/1
1/b0a8eae_2/2
1/b0a8eae_3/5
1/c901732_1/1
1/c901732_2/2
1/c901732_3/2
1/ccb4494_1/1
1/ccb4494_2/0
1/ce359b5_2/1
1/cf6abd2_2/2
1/cf6abd2_3/0
1/d0b1f43_2/2
1/d0b1f43_3/1
1/d0b1f43_3/2
1/e3d6c94_2/0
1/e3d6c94_3/0
1/e7a10f8_2/0
1/e85d92a_1/0
2/229360a_2/6
2/229360a_2/7
2/22cc237_1/1
2/27e1026_1/0
2/27e1026_1/1
2/27e1026_3/0
2/287e338_3/0
2/29caf6f_1/0
2/29caf6f_1/1
2/2a163ab_2/3
2/2a163ab_3/1
2/2a163ab_3/4
2/2a163ab_3/5
2/2a163ab_3/7
2/302c169_2/1
2/34d9492_1/0
2/34d9492_1/1
2/34d9492_3/1
2/3c13f5a_1/0
2/3c13f5a_2/0
2/3c13f5a_2/1
2/3c13f5a_3/1
2/3c13f5a_3/2
2/60d0b5b_1/0
2/60d0b5b_2/1
2/60d0b5b_3/1
2/6104387_1/3
2/6104387_2/0
2/6104387_2/2
2/692c77d_1/1
2/692c77d_1/2
2/692c77d_2/1
2/692c77d_3/1
2/6ea6792_1/1
2/6ea6792_2/1
2/6ea6792_3/1
2/76f2c72_2/1
2/76f2c72_3/1
2/771d8fc_1/1
2/771d8fc_2/0
2/7d7fbf6_1/0
2/7d7fbf6_1/1
2/7d7fbf6_2/0
2/7d7fbf6_3/1
2/82e2fac_1/1
2/82e2fac_3/1
2/aa8502b_1/2
2/afc0fce_2/1
2/b0a8eae_1/5
2/b0a8eae_1/7
2/b0a8eae_3/2
2/b7a9ee9_3/1
2/c901732_1/0
2/c901732_1/1
2/c901732_2/0
2/c901732_2/1
2/ccb4494_1/0
2/ccb4494_2/0
2/ce359b5_1/0
2/ce359b5_2/0
2/ce359b5_2/2
2/ce359b5_3/0
2/e3d6c94_2/0
3/07b42fd_2/2
3/229360a_1/0
3/229360a_1/6
3/229360a_2/0
3/229360a_3/1
3/22cc237_1/0
3/22cc237_1/4
3/22cc237_1/6
3/287e338_2/0
3/287e338_3/0
3/287e338_3/1
3/287e338_3/7
3/2a163ab_1/0
3/2a163ab_1/1
3/2a163ab_2/0
3/2a163ab_2/2
3/2a163ab_2/3
3/2a163ab_3/4
3/302c169_1/0
3/302c169_2/0
3/302c169_2/1
3/302c169_3/0
3/34d9492_1/0
3/34d9492_1/1
3/34d9492_1/2
3/34d9492_3/1
3/3c13f5a_1/0
3/3c13f5a_1/1
3/3c13f5a_2/2
3/3c13f5a_3/1
3/60d0b5b_2/3
3/60d0b5b_3/0
3/60d0b5b_3/1
3/6104387_2/0
3/6104387_2/2
3/6104387_2/3
3/6104387_3/0
3/6104387_3/3
3/692c77d_2/0
3/692c77d_2/2
3/6ea6792_1/6
3/6ea6792_1/7
3/6ea6792_2/0
3/6ea6792_3/0
3/76f2c72_2/0
3/76f2c72_3/0
3/771d8fc_3/0
3/7d7fbf6_3/0
3/7d7fbf6_3/3
3/82e2fac_1/0
3/82e2fac_1/1
3/aa8502b_2/0
3/afc0fce_2/7
3/afc0fce_3/1
3/b0a8eae_1/2
3/b0a8eae_2/0
3/b0a8eae_2/2
3/b0a8eae_3/1
3/b7a9ee9_1/1
3/b7a9ee9_3/1
3/b7a9ee9_3/2
3/c901732_1/1
3/c901732_2/0
3/c901732_2/2
3/c901732_2/5
3/c901732_2/6
3/c901732_3/0
3/ccb4494_1/1
3/ccb4494_1/2
3/ccb4494_2/0
3/ce359b5_3/1
3/ce359b5_3/2
3/d0b1f43_2/2
3/d0b1f43_2/4
3/d0b1f43_3/5
3/e3d6c94_2/1
3/e3d6c94_3/2
3/e7a10f8_2/0
3/e85d92a_1/0
```
