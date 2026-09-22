# Brief X33 — why is there a threshold? Three candidate mechanisms, measured

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis and code. **Do NOT `qsub` an evaluation, do not touch a GPU, do not run training.** I submit
every job myself. Run analysis through `hpc`.

## The question

Quality is flat across roughly the first third of a planner episode and then rises: `goal_pass_rate`
sits near the plan-only floor at m = 2–6 and climbs at m = 7–11. The shape test (X26) establishes
*whether* that threshold is real. This unit asks **why**, which is what turns a curve into a finding.

Three candidate mechanisms. Measure all three; do not pick a favourite in advance.

### M1 — API novelty is front-loaded

If the planner's early actions are where unfamiliar API calls are discovered, a prefix that stops
before those steps leaves the executor to rediscover them, and one that includes them does not.

Measure, per episode, the position of each **first use of a given API** in the planner's action
sequence, and build the distribution of those positions. Then ask whether the threshold lands where
the cumulative share of first-uses crosses some level. Report the cumulative curve and the breakpoint
together; do not fit anything to make them agree.

### M2 — compounding error after handoff

If the executor's errors compound, what matters is not what the prefix contains but how many steps the
executor must still take alone.

Measure, per arm and per episode, the **step index of the executor's first error** after handoff, and
the number of executor steps remaining. If M2 dominates, first-error step should be roughly constant
in absolute terms after handoff regardless of m, and the arms that win are simply those with fewer
remaining steps.

### M3 — the prefix-exhausted population

At large m many episodes are already finished by the replayed prefix. Post-guard, the executor never
acts in 3, 8, 20, 30 episodes at m = 6, 7, 8, 9 (0 at m = 2 and 4)
[OBSERVED `/scratch/n12194778/sidekick/results/hj12_prefix_m*_20260923` `result.json`
`totals.per_actor.executor.n_calls`]. If the rise is *only* the growing share of such episodes, the
threshold is an artefact of the population mix rather than a statement about handoff.

**This is the mechanism most likely to be true and least flattering to us, so measure it first and
most carefully.** Recompute the curve on the **handoff-only** population at every m — episodes where
the executor actually acted — and report whether the rise survives. If it does not, say so plainly.

## Data

Use the **post-guard** arms `hj12_prefix_m*_20260923` as primary (m = 2, 4, 6, 7, 8, 9, and 10/11 when
they land — check for 114 episodes per arm before using one) and the pre-guard `*_20260922` arms as
comparison. Never pool them: they are different configurations at m ≥ 6.

Output `campaign/results/hj13_mechanism_20260923.report.json` plus a short
`campaign/results/hj13_mechanism_20260923.md` with one table per mechanism.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run through `hpc`; BLAS pinned to one thread.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read or list `test_normal`
  or `test_challenge`.
- Do not edit `scripts/analysis/j8_frontier.py`, `src/sidekick/training/handoff_sft.py`,
  `src/sidekick/training/matched_sft.py`, `src/sidekick/training/sft_data.py`, `scripts/pbs/*`, any
  `docs/prereg_*.md`, or any `hj8_*`/`hj11_*` config — other units own several of these.
- Reuse the existing failure-anatomy code where it already does part of this rather than writing a
  second implementation; say what you reused.
- Unit tests on scripted fixtures for each of the three measurements.
- Full suite must stay at 531 passed, 1 skipped or better.
- **Make your first edit within your first three actions. Never background a command and exit.**
- **Write `campaign/workers/STATUS_X33.md` even if you finish only part of this.**
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X33.md`, under 600 words: one table per mechanism; which arms you used and
which were incomplete; what you reused; the test names; the suite line.

Then answer in one line each:

- **Does the rise survive on the handoff-only population?** (M3 — the one that matters most.)
- Is the executor's first-error step after handoff roughly constant in m, or does it move? (M2)
- Where do API first-uses concentrate, and does that location coincide with the breakpoint? (M1)

Report a mechanism as unsupported if that is what you find. A clean negative on all three is a real
result and must not be dressed up. Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
