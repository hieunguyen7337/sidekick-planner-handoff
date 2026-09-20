# J9b — a fabricated confidence interval in the J9 freeze

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own **`docs/prereg_j9_freeze_20260920.md` section 3.4 only**. Touch no other file and no other
section. **Do not commit, do not run git, do not `qsub`, do not run python, do not run the
analysis.** A live GPU job is running; leave it alone. `aquarius01` is a login node — steering only.

## The defect

Section 3.4 currently states, for the `sidekick_tau05` vs `fixed_k_10` goal-pass contrast:

> a 95% CI of **[-1.67, +6.74]**

citing `campaign/results/hj8_frontier_dev_20260920.report.json: lines 28269-28271`.

That interval **does not exist in the report**. A search of all 462 contrasts for a `ci95_pp` equal
to `[-1.67, 6.74]` returns zero matches. The citation points at line numbers rather than at a key,
which is how it passed review the first time.

The report stores this contrast in the opposite direction, as
`goal_pass_all_fixed_k_10_minus_sidekick_tau05`:

```
field=goal_pass_rate   diff_pp=-2.47   ci95_pp=[-9.85, 4.49]   n_pairs=114
```

Sign-flipped to `sidekick_tau05 − fixed_k_10`, the correct figures are:

**difference +2.47 pp, 95% CI [-4.49, +9.85], n_pairs 114.**

For comparison, the TGC contrast in the same direction is **0.00 pp, CI [-8.77, +9.65]**
(stored as `tgc_all_fixed_k_10_minus_sidekick_tau05`, `diff_pp=0.0`, `ci95_pp=[-9.65, 8.77]`).

## The fix

1. Replace `[-1.67, +6.74]` with `[-4.49, +9.85]`.
2. Replace the citation with
   `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "contrasts" → "goal_pass_all_fixed_k_10_minus_sidekick_tau05", sign-flipped]`.
   **Do not cite line numbers anywhere in this section** — cite keys.
3. The conclusion is unchanged and must stay: the lower bound −4.49 pp clears the −7.00 pp
   non-inferiority bound, whereas TGC's −8.77 pp does not. Do not weaken or restate that.
4. The closing sentence currently says `goal_pass_rate` "yields narrower uncertainty intervals that
   permit non-inferiority resolution". That is true but reads as a larger effect than it is. Make it
   quantitative: the goal-pass CI half-width is **7.17 pp** against TGC's **9.21 pp**, a narrowing of
   about **1.28×**. Add, in the same sentence or the next, that this is a much smaller ratio than the
   replicate-noise ratio of 3.5 pp to 0.9 pp might suggest, so the case for the metric switch rests
   on replicate stability rather than on a large gain in interval width. Tag that `[INFERRED]`.
5. Check every other number in section 3.4 against the report and say in STATUS whether each one
   checks out. The `sft_plan` vs `executor_alone` figures are correct and were verified
   independently (TGC −27.19 pp CI [−37.72, −16.67]; goal-pass −17.11 pp CI [−23.74, −10.36], both
   n_pairs 114) — confirm they are still written that way and leave them alone.

## Constraints

- Change nothing outside section 3.4.
- Do not adjust any decision, conclusion or the arm list.
- Do not introduce a number you have not read from
  `campaign/results/hj8_frontier_dev_20260920.report.json` under a named key. If a number you need
  is not there, say so in STATUS rather than supplying one.

## Return contract

Write `campaign/workers/STATUS_J9b.md`. Final report, five lines or fewer: the strings you replaced,
the per-number check from step 5, confirmation that no other section changed, and confirmation that
no citation in section 3.4 refers to a line number.
