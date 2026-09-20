# Brief E5 — analyse the intervention-aware adapter against the baseline

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Situation

Both evaluations are complete. Four dev arms were run twice, once on each adapter, with everything
else identical (same frozen `hj8_*` configs, same tasks, same two seeds, n=114 per arm, 0 broken).

| arm | baseline (`sft_b_plus`) | new (`sft_b_plus_iaware`) |
|---|---|---|
| sft_plan | `/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260919` | `…/hj8_sft_plan_bplus_20260921iaware` |
| fixed_k_10 | `…/hj8_fixed_k_10_20260920` | `…/hj8_fixed_k_10_20260921iaware` |
| fixed_k_3 | `…/hj8_fixed_k_3_20260920` | `…/hj8_fixed_k_3_20260921iaware` |
| oracle_escalation | `…/hj8_oracle_escalation_20260920` | `…/hj8_oracle_escalation_20260921iaware` |

Ignore any `*_20260919livesmoke_smoke` tree — those are discarded.

The two adapters differ in exactly one respect: the training data retained 267 `INTERVENTION:` turns
instead of stripping them to 0. Same 497 rows, same 479 sequences, identical hyperparameters.

## Task

Run `scripts/analysis/j8_frontier.py` over **all eight** arms in one invocation, labelling them so
base and iaware are distinguishable (e.g. `--arm fixed_k_10_base=<dir> --arm
fixed_k_10_iaware=<dir>`). Write the report to
`campaign/results/hj8_frontier_iaware_20260921.report.json`.

Run it in PBS (`hpc bash -c '...'`), BLAS pinned to 1 thread, `timeout` on everything. Do not run the
interpreter on the login node.

## Report these, each paired and task-clustered, with 95% CIs, in BOTH populations (all-episodes and survivors)

1. **The regression check.** `sft_plan_iaware − sft_plan_base`. Did unprompted plan-following survive?
   Baseline goal_pass was 0.700009, TGC 0.403509.
2. **The dose contrasts.** `fixed_k_10_iaware − fixed_k_10_base` and `fixed_k_3_iaware −
   fixed_k_3_base`.
3. **The dose-response slope on each adapter.** Baseline survivor goal_pass fell monotonically with
   planner calls per episode: 0.700 at 1.0 → 0.662 at 2.75 → 0.605 at 6.74. Report the same three
   points for the iaware adapter, with its own calls/episode. **Whether this slope flattens is the
   headline of this unit.**
4. **`oracle_escalation_iaware − sft_plan_iaware`** — is there now headroom above plan-only? On the
   baseline the oracle *lost* to plan-only (0.666 vs 0.700).
5. Per-arm planner calls/episode (live and replay-inclusive), `n`, `n_broken`, `n_crashed`.

Also report `oracle_escalation_iaware` escalation count: in the 3-task smoke it escalated **zero**
times where the baseline averaged 1.298 calls/episode. State what it does at n=114.

## Constraints

- **Read-only with respect to the results trees. Do not modify anything under
  `/scratch/n12194778/sidekick/results/`.**
- **Do not read, analyse or report any `test_normal` or `test_challenge` data. Dev only.**
- Do not re-run any evaluation, do not submit GPU jobs, do not retrain.
- Do not edit `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`, or any `hj8_*` config — FROZEN.
- `aquarius01` is a LOGIN NODE: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there.
- **Do not commit.** Claude reviews and commits.
- **Do not interpret the result or recommend next steps.** Report the numbers and what the script
  emitted. The judgement is not yours.

## Return contract

`campaign/workers/STATUS_E5.md`, under 700 words: every number above, the exact command run, the
report path, and each claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`. Quote the script's own
headline string verbatim. If `j8_frontier.py` refuses to emit a headline, say so and quote the refusal
rather than working around it.
