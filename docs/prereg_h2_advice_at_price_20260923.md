# Pre-registration — H2: advice priced at the budget where the action channel wins

**Status: FROZEN on writing. Append-only. Amended by appending a dated section, never by editing.**

Written 2026-09-22, before the arm `hj13_advise_fixed_k_1_fullctx` is submitted and before any of its
episodes exist on disk. Registered by: Claude (orchestrator), on the standing plan
`docs/plan_publishable_then_top_venue_20260922.md` §3 wave 2.

## 1. Why this arm, now

The registered channel claim — that the *channel* into which hosted budget is spent matters, not just the
amount — has never been tested at matched budget. Red-team attack 4 states it plainly: at 30 % of the
planner's budget, prose advice (`advise_fixed_k_3`, 0.7012) and replayed action prefix (`prefix_m6`,
0.7237) are indistinguishable, and the action channel only wins at 52–65 % of budget, where advice has
never been priced. Until advice is run at that budget, "channel, not budget" is a slogan.

Two results since have sharpened what this arm decides.

**H1 (ADV-FC-01) removed the confound.** Full-context advice at k=10 scores 0.7339, which is +1.57 pp over
the adapter-matched plan-only floor (0.7181) with scenario-clustered 95 % CI [−2.91, +5.91] and
task-clustered [−3.04, +6.30], and +3.74 pp over the starved-critic control [−1.39, +9.13]. Every interval
includes zero. So advice being flat is not an artefact of a reviewer that could only see eight transcript
lines.

**The narrated-prefix control (X38) changed what the mechanism is believed to be.** Rendering the
planner's first nine recorded actions as *text* in the plan slot, with the executor starting from step 0
in a **fresh** environment, scores **0.7665** on the tailored receiver against the executed prefix's
0.7852 and the plan-only floor's 0.7181 (preliminary, n=113 of 114 at the time of writing; the CI is
computed before this prereg is acted on). Most of the depth effect therefore travels as **information**,
not as replayed environment state. That makes H2 decisive rather than confirmatory: if what the prefix
buys is information, then prose advice carrying comparable information at comparable cost ought to buy it
too — and if it does not, the channel claim survives in its strongest form.

## 2. The arm

`configs/hj13_advise_fixed_k_1_fullctx.yaml` (already written and registered at
`scripts/pbs/hj12_live.pbs:158`; unchanged by this document): `correct_context: full`, `fixed_k: 1`
(the planner reviews after every executor step), cached up-front plan from `hj1b_planner_20260915` so the
plan itself costs nothing and only the reviews spend hosted calls. Executor `ibm-granite/granite-4.2-8b`
under alias `sft_b_plus` (which resolves to `sft_b_plus_iaware_granite8b`), dev split, seeds 1 and 2,
57 tasks, 114 pairs. Planner `gpt-5.6-luna`, `reasoning_effort: medium`. Estimated ~1,600 hosted calls.

## 3. Comparators, fixed now

| role | arm | goal_pass |
|---|---|---|
| plan-only floor | `hj8_sft_plan_bplus_20260921iaware/sft_plan` | 0.7181 |
| advice at k=10, full context | `hj12_advise_fixed_k_10_fullctx_20260923/fixed_k` | 0.7339 |
| action prefix at m=9 | `hj12_prefix_m9_20260923/prefix_handoff` | 0.7852 |
| action prefix at m=11 | `hj12_prefix_m11_20260923/prefix_handoff` | 0.8098 |
| narrated prefix at m=9 | `hj16_narrated_m9_bplus_20260923/sft_plan` | 0.7665 (preliminary) |
| ceiling, named by cap | cap-25 0.8284; cap-81 0.7637 | — |

Primary metric `goal_pass_rate`, all-episodes population, crash counted as 0. Secondary TGC. Paired by
(task, seed), task- **and** scenario-clustered percentile bootstrap, 10,000 resamples, seed 20260915,
reported both ways as the project standard requires. Non-inferiority margin 7.00 pp where an NI statement
is made.

## 4. Predictions, committed before the data exists

**P1 (primary).** `advise_fixed_k_1_fullctx` minus the plan-only floor will have a scenario-clustered
95 % CI that **includes zero**. Point estimate predicted in [−2, +5] pp. Confidence: ~60 %.

**P2.** `advise_fixed_k_1_fullctx` minus `prefix_m11` will be **negative with the interval excluding
zero**, i.e. the action channel beats prose advice at comparable or higher advice spend. Confidence: ~60 %.

**P3.** `advise_fixed_k_1_fullctx` minus `advise_fixed_k_10_fullctx` will **include zero**: ten times the
review frequency does not buy quality. Confidence: ~70 %.

**P4 (cost).** The arm's non-cached planner tokens per episode will exceed `prefix_m9`'s ~357k and land in
[300k, 700k], i.e. at or above the budget at which the action channel wins. If it lands **below** 300k the
arm has not achieved matched pricing and P2 must be reported as **not tested**, not as supporting.

## 5. Decision rules, committed before the data exists

- **If P1 and P2 both hold:** the channel claim is established at matched budget. Wording becomes
  *"advice does not reach the action channel's quality even when priced at or above it; the difference is
  the channel, not the budget."* Attack 4 is closed.
- **If P1 fails (advice rises above the floor with the interval excluding zero) but P2 holds:** the claim
  is reframed and weakened to *"advice improves with budget but less efficiently than actions at equal
  spend"*, and the frontier figure must show the advice curve, not a single flat advice point.
- **If P2 fails (advice matches or beats the prefix at matched budget):** the channel claim is
  **withdrawn**. The thesis headline becomes the depth/shape result plus the tailoring and second-family
  results, and the channel section is rewritten as a negative result. This outcome is to be reported as
  prominently as a positive one.
- **If P4 fails:** report the arm as a *higher-frequency advice* result only, and state explicitly that
  advice remains unpriced at the action channel's budget.
- The `executor_alone` floor (0.5289) exists in one adapter build only
  (`hj8_executor_alone_bplus_20260919`); any contrast against it is cross-build and must say so
  (ADV-FC-02).

## 6. What this document does not authorise

No test-split (`test_normal` / `test_challenge`) data is read, listed or loaded. That remains gated on the
explicit authorisation in `docs/prereg_j9_freeze_20260920.md` §8.1. This arm runs on dev only.

## 7. Analysis script and outputs, named before the run

`scripts/analysis/j8_frontier.py` with `--cluster scenario`, output
`campaign/results/hj13_advice_at_price_20260923.report.json`. The ledger rows will be `CHAN-PRICE-01` and
following. No other analysis of this arm is registered; anything further is exploratory and labelled so.
