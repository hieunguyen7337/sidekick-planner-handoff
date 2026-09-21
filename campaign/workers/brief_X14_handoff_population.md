# Brief X14 — the longest prefix arm contains episodes where no handoff happened

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis only. **One GPU job is still running** (`25596786`, the six-step arm). Do not `qsub`, do
not touch a GPU, do not run any evaluation, and do not edit `src/`, `configs/` or `scripts/pbs/`.
`scripts/analysis/j8_frontier.py` is not imported by the running job, so editing it is safe.

## The problem

The nine-step prefix arm replays up to nine of the planner's recorded actions and lets the local
executor finish. In **28% of episodes it never hands off**, because the source planner episode had
fewer than nine actions in total [OBSERVED frontier output: `prefix_m9 ... hand_all 0.7193`,
`m_all 8.70` against a requested nine].

In those episodes the replay reproduces the planner's entire trajectory and the executor contributes
little or nothing. They are, in effect, `planner_alone` episodes wearing the prefix arm's name. They
are pooled into the arm's headline number, which currently reads `goal_pass_rate` 0.8134 against the
planner's 0.8284.

**This biases the arm upward, and it biases it in the direction that flatters the hypothesis.** It is
probably worse than a simple dilution: the source episodes that ended in under nine actions are the
ones the planner finished quickly, which are plausibly the easier tasks. So the pooled figure may be
mixing the planner's score on easy tasks with the hybrid's score on hard ones and presenting the
average as the hybrid's performance.

The existing `survivors` population does **not** address this. It drops pairs where either side
crashed, and there were no crashes, so `survivors` and `all-episodes` are identical here.

## What to build

Add a **third population**, reported alongside `all-episodes` and `survivors`, restricted to
episodes where the prefix arm actually handed off (`handoff_occurred` true in the arm's `report`
event). Name it clearly, for example `handoff-only`.

Requirements:

1. **Pairing must stay honest.** The subset is defined by the prefix arm's episodes, but the
   contrast is against `planner_alone` and `sft_plan` on the **same** task and seed. Restrict every
   arm in the contrast to that same set of (task, seed) keys, never to each arm's own subset. Report
   the resulting `n_pairs` for every contrast so the reduced power is visible.
2. Apply it to **both** the non-inferiority table and the chord test, for `goal_pass_rate` and TGC.
3. **Also report the complement** — the episodes where no handoff occurred — as its own row, with
   the reference arm's score on those same tasks beside it. That is what shows whether the
   no-handoff episodes were the easy ones. If the reference scores far higher on the complement than
   on the handoff subset, say so in the emitted JSON.
4. An arm where every episode handed off (the two, four and six step arms all report a handoff rate
   of 1.0) must produce a `handoff-only` population identical to `all-episodes`. That is a useful
   self-check: if it does not, the subsetting is wrong.
5. Keep the existing populations and every existing key working unchanged. This is an addition.
   Other reports read this output.

## Tests

- A synthetic arm where half the episodes handed off yields a `handoff-only` population of exactly
  those episodes, with the reference restricted to the same keys.
- An arm with a handoff rate of 1.0 yields a population identical to `all-episodes`.
- `n_pairs` is reported and equals the subset size.
- The complement row is present and carries the reference arm's score on the complement keys.

## Verification

Run the frontier over the four arms that exist and paste, for the nine-step arm, the `goal_pass_rate`
row under all three populations plus the complement row:

```
timeout 1800 hpc -c 4 -m 16gb -t 00:25:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python scripts/analysis/j8_frontier.py --arm planner_alone=/scratch/n12194778/sidekick/results/hj1b_planner_20260915 --arm sft_plan=/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware --arm prefix_m2=/scratch/n12194778/sidekick/results/hj12_prefix_m2_20260922 --arm prefix_m4=/scratch/n12194778/sidekick/results/hj12_prefix_m4_20260922 --arm prefix_m9=/scratch/n12194778/sidekick/results/hj12_prefix_m9_20260922 --reference-arm planner_alone --floor-arm sft_plan --cost-key planner_tokens_noncached --out /tmp/x14.json'
```

Write the JSON to `/tmp`, not to `campaign/results/`. **Do not add the six-step arm** — it is still
running and the tool refuses an incomplete arm, which is correct.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Dev only; never read `test_normal` or `test_challenge`.
- The suite is at **498 passed, 1 skipped** and must not fall.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X14.md`, under 500 words: the population's name and exact definition, how
you restricted the reference arms, the nine-step arm's `goal_pass_rate` under all three populations
with `n_pairs`, the complement row, whether the reference scores higher on the complement, the test
names and the pasted suite line. Tag claims `[OBSERVED <path>:<line>]` or `[INFERRED]`.
