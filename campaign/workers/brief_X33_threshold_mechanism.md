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

## Addendum 2026-09-22 16:30 — M3 partially measured already; your job is to do it properly

I ran a first pass on M3. Build on it; do not just reproduce it.

**Post-guard arms, all episodes vs a fixed common key set** (the 83 episodes where the post-guard m9
prefix did *not* already finish the task, so every arm with m ≤ 9 genuinely hands off):

| m | all episodes | common-83 set |
|---|---|---|
| 2 | 0.6856 | 0.7051 |
| 4 | 0.7190 | 0.6925 |
| 6 | 0.7237 | 0.7025 |
| 7 | 0.7544 | 0.7122 |
| 8 | 0.7627 | 0.7081 |
| 9 | 0.7852 | 0.7390 |

m2→m9 is **+9.96 pp** on all episodes and **+3.39 pp** on the common set, against a replicate noise
floor of 3.31 pp (NOISE-01). Silenced-episode counts rise 0, 0, 3, 8, 20, 31 across that range.

**The key-set choice matters and you must handle it explicitly.** Pinning to m8's set (94 episodes)
instead gives m6→m9 = +6.04 pp rather than +3.65 pp, because m8's set contains ~11 episodes that the
m9 prefix auto-completes, so m9 collects credit for them. Whether a prefix already finished the task is
**deterministic given (source trajectory, m)** — it is not a stochastic property of the arm — so the
correct control is to pin to the set defined by the **largest m under comparison**, which makes the
sets nested. State which set you used for every number and report at least two pinnings.

**What I need from you, precisely:**

1. The common-key-set curve for every completed post-guard arm including m10 and m11 once they land,
   pinned to the largest available m, with paired bootstrap CIs (task- and scenario-clustered) on each
   adjacent contrast — not just point estimates. My pass has no intervals; that is the gap.
2. An **arm-independent** key set as a cross-check: episodes whose source planner trajectory required
   more executed actions than the largest m in the grid, so no prefix in the grid could complete them.
   Derive it from the source campaign, not from any arm's outcome, and say where you got it.
3. The decomposition: of the all-episodes rise from m=2 to the largest m, how many percentage points
   are attributable to the growing silenced share versus to improvement on genuinely-handed-off
   episodes. Give the arithmetic explicitly.

**Do not soften the result.** If conditional on a genuine handoff the curve is flat within noise, that
is the finding, and it reframes the thesis rather than sinking it — the system-level curve is still
real and still the deployable claim. What must not happen is a rise reported as a handoff effect when
it is a population-mix effect. Equally, do not overcorrect: if the rise does survive on the controlled
set with intervals that exclude zero, say that plainly too.
