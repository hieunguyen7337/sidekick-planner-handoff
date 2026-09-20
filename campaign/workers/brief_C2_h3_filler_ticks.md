# C2 — H3 manufactures AUROC from ticks that never happened

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own `scripts/analysis/j8_frontier.py` and `tests/unit/test_j8_frontier.py`. **Touch nothing
else** — in particular do not edit `campaign/RUNS.md` (I will correct it myself once I have your
numbers), do not edit any `.pbs`, do not `qsub`, do not run git, and do not commit.

A live GPU job (`25560367`, B1) is running. Result trees under `/scratch/n12194778/sidekick/results`
are **read-only** to you.

`aquarius01` is a login node — steering only. No python, pip, tar, rsync there. Everything runs in a
PBS job via `hpc bash -c '...'`. `timeout` on every command. BLAS pinned to 1 thread.

## The defect

`collect_h3_for_arm` [scripts/analysis/j8_frontier.py:860-904] walks a fixed tick grid
`range(TICK_K, TICK_MAX + 1, TICK_K)` = 5,10,…,40 for **every** episode, and at :894-900 does:

```python
slot = by_step.get(tick)
if slot is None:
    score = 0.0
elif slot.get("score") is not None:
    score = float(slot["score"])
else:
    score = 1.0 if slot.get("escalated") else 0.0
```

Episodes average about 20 steps (`steps_mean` 19.91 on these arms) against `TICK_MAX` 40, so roughly
half the grid lies **past the end of the episode**. Those ticks are not decisions the gate declined
to make — they do not exist. Each contributes a `(score = 0.0, label = 0)` pair, and AUROC rewards
exactly that.

Measured on the 2026-09-20 dev arms (this is the observed result, reproduce it as a test fixture
shape, not as a literal expectation):

```
arm              total ticks   real p_ask    filler 0.0   pos in real   pos in filler   AUROC all   AUROC real-only
sidekick_tau07           848    393 (46.3%)   455 (53.7%)        36/393           7/455      0.6759            0.4407
sidekick_tau05           848    396 (46.7%)   452 (53.3%)        34/396           9/452      0.6311            0.3867
sidekick_tau03           848    400 (47.2%)   448 (52.8%)        30/400          13/448      0.5983            0.4332
```

The reported AUROC is above chance; on the ticks the gate actually scored, every arm is **below**
chance. The published number is a property of episode length, not of the gate.

## What to do

### 1. Verify the cause before fixing it

Do not take my explanation on trust. Establish, from the artifacts, whether a missing slot at tick
`t` corresponds to the episode having ended before step `t` — cross-reference the episode's step
count in its `result.json` against the ticks that have no entry in
`gate_scores_from_events` [:820-858]. Report the agreement rate. If a material fraction of missing
slots occur at ticks *within* the episode's lifetime, say so: that is a different defect and the fix
below is then incomplete. Tag the finding `[OBSERVED <path>:<line>]`.

### 2. Fix the computation

H3 must be computed over decision points that exist. Report **two populations**, following the
same idiom R8 introduced for the quality metrics:

- `scored`: ticks where the gate produced a score (the **primary**; this is what H3 is asking about)
- `grid`: the current all-ticks behaviour, retained for comparability with what was published

For each gate report, per population: `auroc`, `ece`, `n`, `n_positive`, and the count of ticks
excluded from `scored` with the reason. Keep `n_escalations` and `degenerate` as they are.

Label the primary explicitly in the printed output and in the JSON, the way
`headline_population` / `quality_populations` already do for quality [:1121 and nearby]. **If the two
populations disagree in whether AUROC exceeds 0.5, flag it loudly in the printed output**, reusing
the existing `CONTRAST DISAGREEMENT` idiom [:349-427]. A gate that is above chance on the grid and
below chance on scored ticks is the finding, not a footnote.

Leave the `else: score = 1.0 if escalated else 0.0` branch alone for ticks that exist but carry no
`p_ask` — that is a real decision point for a gate kind that emits no probability.

### 3. Also report the score distribution

Add, per gated arm, the quantiles of the real scores (min, median, p90, p95, p99, max) and the mean.
This exists because the operative fact about the `sidekick` arms is that `p_ask` never exceeds
0.0240 while τ was set at 0.3/0.5/0.7 — a reader cannot see that from AUROC alone, and it is the
reason the arms are degenerate. Print it as a small table.

### 4. Tests

Extend `tests/unit/test_j8_frontier.py` with synthetic arms covering:

1. an episode that ends early: ticks past its final step are excluded from `scored` and counted in
   the exclusion tally, and present in `grid`
2. a gate whose `grid` AUROC is above 0.5 while its `scored` AUROC is below 0.5: both are reported
   and the disagreement is flagged
3. an arm where every episode runs the full grid: the two populations coincide and the report says
   so rather than printing a spurious difference
4. a tick that exists but has no `p_ask`: still counted in `scored`, scored by the escalated flag
5. the score-quantile table on a known distribution

Every currently-passing test must keep passing.

### 5. Re-run and report

Re-run the report over the twelve arms and give me the corrected H3 table plus the quantile table.
The durable input paths:

```
R=/scratch/n12194778/sidekick/results
--arm executor_alone=$R/hj8_executor_alone_bplus_20260919
--arm sft_plan=$R/hj8_sft_plan_bplus_20260919
--arm fixed_k_3=$R/hj8_fixed_k_3_20260920
--arm fixed_k_5=$R/hj8_fixed_k_5_20260920
--arm fixed_k_10=$R/hj8_fixed_k_10_20260920
--arm oracle_escalation=$R/hj8_oracle_escalation_20260920
--arm router_seq_tau03=$R/hj8_router_seq_tau03_20260920
--arm router_seq_tau05=$R/hj8_router_seq_tau05_20260920
--arm router_seq_tau07=$R/hj8_router_seq_tau07_20260920
--arm sidekick_tau03=$R/hj8_sidekick_tau03_20260920
--arm sidekick_tau05=$R/hj8_sidekick_tau05_20260920
--arm sidekick_tau07=$R/hj8_sidekick_tau07_20260920
--oracle-labels $R/hj6_branches_dev_20260917/oracle_labels.json
```

Write the new report to `campaign/results/hj8_frontier_dev_20260920.report.json`, replacing the
current file — it is the record §10 cites, and it must match the corrected code. **Every quality
number in it must be unchanged**; only the H3 block and the new quantile block should differ.
Confirm that explicitly, by comparing against the committed copy (`git show HEAD:` is a git command
— instead, note that the committed values are the ones in the table in §10 of `campaign/RUNS.md`,
which you may **read**).

## Constraints

- Suite must stay at **437 passed, 1 skipped** plus your new tests:
  `-m pytest tests -q --import-mode=importlib`. Report the exact final line.
- Do not change any quality metric, contrast, F1 or headroom computation.
- Do not "fix" the numbers to look better. If the corrected AUROC is below chance for every gate,
  that is the result.

## Return contract

Write `campaign/workers/STATUS_C2.md` as you go. Tag every claim `[OBSERVED <path>:<line>]` or
`[INFERRED]`. Final report, ten lines or fewer: the verification result from step 1 (agreement rate),
the corrected H3 table for all six gates in both populations, the score-quantile table, confirmation
that no quality number moved, the five test cases with evidence, and the suite's final line.
