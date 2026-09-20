# R8 — the frontier script mixes denominators, and planner crashes confound the cost axis

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own `scripts/analysis/j8_frontier.py` and `tests/unit/test_j8_frontier.py`. Touch nothing
else. Live GPU jobs are running from `scripts/pbs/*` right now — do not edit any `.pbs`, do not
`qsub`, do not run git, do not commit, and do not write under `/scratch/.../results/`.

## What was found (observed, four completed dev arms, 114 episodes each)

```
arm          n  crash  calls  per_call%  tgc_all  tgc_ok  gp_all  gp_ok
fixed_k_3  114     17    768       2.21   0.2982  0.3505  0.5149  0.6051
fixed_k_5  114     10    566       1.77   0.3772  0.4135  0.6238  0.6838
fixed_k_10 114      3    314       0.96   0.3860  0.3964  0.6447  0.6621
oracle     114      0    148       0.00   0.3772  0.3772  0.6660  0.6660
```

Two separate problems.

### Problem 1 — the script's two headline metrics use different denominators

The report currently prints, for `fixed_k_3`, `tgc = 0.2982` and `goal_pass = 0.6051`. Those are
`tgc_all` (all 114 episodes, a crash scored as 0) and `gp_ok` (the 97 surviving episodes) in the
table above. **TGC is averaged over all episodes while goal-pass is averaged over survivors.**
Two headline quality metrics on different populations cannot both be right, and the difference is
large: `gp_all` for that arm is 0.5149, not 0.6051.

Fix: compute every quality metric over **both** populations and report both explicitly, with the
counts. Never let a single unlabelled column mix them. Suggested columns:
`n`, `n_crashed`, `tgc_all`, `tgc_survivors`, `goal_pass_all`, `goal_pass_survivors`.
State in the output which population the headline contrast uses, and use the same one for every
metric in that contrast.

### Problem 2 — planner crashes scale with the number of planner calls, confounding the cost axis

All 17 crashes in `fixed_k_3` are the planner invocation failing: 16 carry `exc_type`
`CodexExecError` with detail `codex exec exited 1`, 1 has no error event. An episode dies when a
call fails, so an arm that makes more calls loses more episodes, and a crashed episode scores 0.

That mechanically penalises exactly the arms the frontier is meant to place on the expensive end,
which is the difference between "frequent planner review reduces quality" (a claim about the
method) and "frequent planner review hits a flaky planner more often" (a claim about the harness).
With crashes excluded the monotone trend disappears and becomes an interior optimum at k=5.

Requirements:
- Report **crashes per arm, and crashes per planner call**, as first-class columns. They are a
  property of the measurement and belong in the table, not in a footnote.
- Compute the paired contrasts on the survivor population **and** on the all-episodes population,
  and print both. If they disagree in sign or in whether the CI excludes zero, say so loudly in
  the output. That disagreement is a finding.
- Do not silently drop crashed episodes from a paired comparison. Pairing is by `(task_id, seed)`;
  if either side of a pair crashed, that pair is unusable for the survivor contrast. Report how
  many pairs were dropped for that reason, per contrast. A pair count that quietly shrinks is how
  a previous result here went wrong.
- Note, without asserting a cause, that the per-call crash rate is **not constant** across arms
  (2.21%, 1.77%, 0.96%, 0.00%). A fixed independent per-call failure probability would be flat.
  Print the per-call rate so a reader can see this; do not claim an explanation the data does not
  support.

## Tests

Extend `tests/unit/test_j8_frontier.py` with synthetic arms covering:
1. an arm with crashed episodes: `tgc_all` and `tgc_survivors` differ, both reported, counts right
2. a paired contrast where one side crashed on some pairs: dropped-pair count reported, and the
   survivor contrast uses only pairs where both sides survived
3. an arm with zero crashes: the two populations coincide and the report says so rather than
   printing a spurious difference
4. the all-episodes and survivor contrasts disagreeing in sign: the disagreement is flagged in
   the output

Keep every currently-passing test passing.

## Constraints

- `aquarius01` is a login node — steering only. No python, pip, tar, rsync there. Everything runs
  in a PBS job via `hpc bash -c '...'`. `timeout` on every command. BLAS 1 thread.
- Read result trees read-only. The trees under
  `/scratch/n12194778/sidekick/results/hj8_*_20260920` are being written by live jobs; read them,
  never write them, and expect arms that are still filling.
- Suite must stay at **433 passed, 1 skipped** plus your new tests:
  `-m pytest tests -q --import-mode=importlib`. Report the exact final line.

## Return contract

Write `campaign/workers/STATUS_R8.md` as you go. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`. Final report, eight lines or fewer: the columns the report now prints, how the two
populations are labelled, the dropped-pair accounting, the four test cases with evidence, and the
suite's final line.
