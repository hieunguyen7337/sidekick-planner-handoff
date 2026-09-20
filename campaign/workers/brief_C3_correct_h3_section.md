# C3 — §10's H3 conclusion is wrong; replace it with the corrected one

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own **`campaign/RUNS.md` section 10 only**. Touch no other file. **Do not commit, do not run git,
do not `qsub`, do not run python.** A live GPU job (`25560367`) is running; leave it alone.
`aquarius01` is a login node — steering only.

## What happened

§10 was written and committed (`e096b0d`) reporting an H3 table whose AUROC was computed over a
fixed tick grid of 5,10,…,40 for every episode, with ticks **after the episode ended** scored 0.0.
Episodes average about 20 steps, so roughly half of every arm's sample was ticks that never
happened, and those manufactured `(score 0.0, label 0)` pairs inflate AUROC.

This was verified, not assumed: across all six gated arms the missing grid slots agree with
`tick > steps` at rate **1.0** (579, 463, 443, 448, 452, 455 slots), with **zero** missing slots
inside an episode's lifetime.

`scripts/analysis/j8_frontier.py` has been corrected to report two H3 populations — `scored`
(ticks at or before the episode's final step; the primary) and `grid` (the published behaviour) —
and `campaign/results/hj8_frontier_dev_20260920.report.json` has been regenerated. **Every quality
number, contrast, F1 verdict and headroom figure is unchanged** and was confirmed identical by
hash; only the H3 block changed.

## The correction to make

Replace the **"### H3 — Gate calibration against dev oracle labels"** subsection of §10 with the
corrected reading. Leave every other subsection of §10 exactly as it is — the arm table, F1, oracle
headroom, replicate noise and cost subsections are all unaffected and must not be touched.

The corrected table:

```
gate              scored_auroc  grid_auroc  n_scored  n_pos_scored  excluded  n_escalations
router_seq_tau03        0.5082      0.6294       269            24       579           1533
router_seq_tau05        0.4971      0.4988       385            36       463             12
router_seq_tau07        0.5000      0.5000       405            33       443              0
sidekick_tau03          0.4332      0.5983       400            30       448              0
sidekick_tau05          0.3867      0.6311       396            34       452              0
sidekick_tau07          0.4407      0.6759       393            36       455              0
```

`scored` is the primary population. Every exclusion is `past_episode_end`; `within_episode_missing_slot`
is 0 for all six arms. The three `sidekick` arms are flagged `auroc_chance_disagreement` — above 0.5
on the grid, below 0.5 on real decision points.

The `sidekick` gate's real `p_ask` scores:

```
arm                n   mean     median     p90      p95      p99      max
sidekick_tau03   400  0.00407  0.000924  0.01268  0.01674  0.02715  0.03470
sidekick_tau05   396  0.00411  0.001315  0.01305  0.01641  0.01942  0.02341
sidekick_tau07   393  0.00416  0.001262  0.01286  0.01848  0.02351  0.02400
```

`router_seq` emits no `p_ask` at all (`n = 0` in the quantile table); its H3 scores fall back to a
binary escalated / not-escalated indicator, so its "AUROC" measures agreement between its decisions
and the oracle labels, not a ranking. Say this explicitly — it changes how the router numbers
should be read. `router_seq_tau03`'s scored ECE is 0.896, consistent with escalating on nearly every
tick while roughly 9 % of ticks carry a positive label.

## What the section must now conclude

State these plainly, and do not soften them:

1. **No gate measured here discriminates.** On real decision points every gate sits at or below
   chance. `router_seq_tau03`, the only one that appeared to carry signal, falls from 0.6294 to
   0.5082.
2. **The `sidekick` self-gate is a discrimination failure, not a calibration failure.** Its `p_ask`
   never exceeds 0.0347 across any arm while τ was set at 0.3 / 0.5 / 0.7, so it could not fire; but
   lowering τ would not rescue it, because its ranking is below chance. At τ = 0.01 it would fire on
   about 16 % of ticks at precision 0.082 against a base rate of 0.092 — worse than escalating at
   random.
3. **There is therefore no τ\* worth freezing for this gate on this adapter**, and no
   corrected-threshold re-run is justified.
4. The oracle labels remain the contaminated J6 dev `schedule_live` estimand with 43 positives over
   106 labelled episodes; that caveat applies to every number in this subsection.

## Two things to remove

- The earlier claim that the sidekick gate "reaches AUROC 0.6759, the highest of any gate measured
  in this project" and that this represents "a calibration failure, not a discrimination failure".
  It is wrong and must not survive anywhere in §10.
- The comparison against A7's value-function router (0.6212) and its feature-blind floor (0.6245).
  Those were measured on a different sample under a different extraction and are **not comparable**
  to these numbers. Delete the comparison rather than re-pointing it; do not replace it with a new
  comparison.

## Record the correction, do not hide it

Add a short closing paragraph to the subsection stating that the first committed version of §10
(commit `e096b0d`) reported the grid population as the headline and drew the opposite conclusion,
that the defect was in the analysis script's tick sampling rather than in any run, and that no
episode data was re-run — only the analysis changed. A ledger that silently overwrites a wrong
conclusion is worth less than one that carries the correction.

## Citations

Cite `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]` for the table,
`[... key "h3_score_quantiles"]` for the quantiles, and
`[OBSERVED scripts/analysis/j8_frontier.py]` for the two-population change. Judgements — points 1
through 3 above — are `[INFERRED]`. Do not cite any brief file as evidence.

## Return contract

Write `campaign/workers/STATUS_C3.md`. Final report, five lines or fewer: the line range you
replaced, confirmation that no other subsection of §10 changed, that the A7 comparison and the
"calibration failure" claim are both gone, and that the correction paragraph is present.
