# Brief X32 — is the cost ordering robust, or an artefact of one cost definition?

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis and code. **Do NOT `qsub` an evaluation, do not touch a GPU, do not run training.** I submit
every job myself. Run your analysis through `hpc`.

## Why this matters more than it did yesterday

Non-inferiority against the planner is now **unresolved**: `prefix_m11 − planner_alone` is +0.23 pp
against the ceiling as run, but −5.92 pp [−9.80, −2.57] against a ceiling with its 12 cap-censored
episodes removed [OBSERVED `campaign/results/hj12_unified_frontier_scenario_nolimit_20260923.report.json`:
`exclude_reference_limit_sensitivity.noninferiority.arms.prefix_m11.goal_pass_all`].

So the campaign's claim is shifting from "as good as the planner" to "this much quality for this much
hosted spend". That makes the **cost axis load-bearing**, and right now every cost statement rests on a
single definition: non-cached planner tokens.

If the arm ordering changes under a different but equally defensible cost definition, the frontier
claim is an artefact of a measurement choice and we must say so.

## Your job

1. Read `scripts/analysis/j8_noncached_cost.py` and establish exactly what it counts — which token
   fields, whether cached input is included, and where the per-arm totals in the unified frontier come
   from. Quote it with `[OBSERVED path:line]`.
2. Create `configs/cost/prices_2026-09.yaml` holding published list prices for the planner model, with
   **separate** rates for input, cached input and output. Record the source and date for each number
   as a comment. If you cannot establish a published rate from material already in the repo, **leave
   it null and say so in STATUS** — do not invent a price, and do not fetch anything.
3. Extend the cost analysis to emit **three axes** per arm, side by side:
   - **A. non-cached planner tokens** — the current definition, unchanged, so nothing already published
     moves;
   - **B. provider-priced dollars**, counting cached input at its own rate;
   - **C. hosted planner calls** — the unit that actually binds here, because the planner runs on a
     plan subscription and the real constraint is quota, not tokens.
4. Emit `campaign/results/hj13_cost_axes_20260923.report.json`: per arm, all three axes, plus the arm
   ordering under each. Then report **any arm pair whose ordering differs between axes**, and whether
   any non-inferiority or frontier verdict would change.

## The specific thing to check

`docs/PLAN.md` and the unified frontier describe the advice arms as expensive and the prefix arms as
expensive-but-better. Under axis **C** that framing may inverto: an advice arm making many small calls
can cost more *calls* than a prefix arm that replays recorded actions and makes none. Report the
per-arm call counts plainly, including the fact that prefix arms make **zero** hosted calls at serving
time, and say what that does to the frontier.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run through `hpc`; BLAS pinned to one thread.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read or list `test_normal`
  or `test_challenge`.
- Do not edit `scripts/analysis/j8_frontier.py`, `src/sidekick/training/handoff_sft.py`, any
  `docs/prereg_*.md`, any `hj8_*`/`hj11_*` config, or anything under `scripts/pbs/`.
- **Axis A output must not change.** Anything already published rests on it; if your refactor moves an
  axis-A number by any amount, stop and report it rather than accepting it.
- Unit tests on a scripted fixture for each axis, including one where axes A and C disagree on ordering.
- Run the full suite; it must stay at 531 passed, 1 skipped or better.
- **Make your first edit within your first three actions. Never background a command and exit.**
- **Write `campaign/workers/STATUS_X32.md` even if you finish only part of this.**
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X32.md`, under 500 words: what axis A counts, quoted; the price card as
written, with any null rates named; the three-axis table for `sft_plan`, `advise_fixed_k_3`,
`advise_fixed_k_10`, `prefix_m6`, `prefix_m9`, `prefix_m11`, `planner_alone`; every ordering
disagreement between axes; confirmation that axis A is unchanged and how you checked; and the suite
line.

Then answer in one line: **does any frontier or non-inferiority verdict change under any axis?**

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
