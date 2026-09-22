# Brief X17 — the two arms being compared are scored on different task sets

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis only. **Two GPU jobs (`25634800`, `25634820`) are queued or running.** They run the
evaluation harness and never import `scripts/analysis/j8_frontier.py`, so editing that file is safe.
Do **not** `qsub`, do not touch a GPU, do not run any evaluation, and do not edit `src/`, `configs/`
or anything under `scripts/pbs/`.

## The problem

`restrict_to_defining_handoff` [OBSERVED `scripts/analysis/j8_frontier.py:432-448`] builds the
`handoff-only` population from **the arm under test's own** `handoff_occurred` flag. The docstring's
promise — that pairing stays honest — holds *within* one contrast: the arm and its reference are
scored on the same keys. It does **not** hold *between* arms.

Consequence, on the current report:

| arm | handoff-only n | arm score | reference score | deficit pp |
|---|---:|---:|---:|---:|
| prefix_m6 | 111 | 0.7068 | 0.8238 | −11.70 |
| prefix_m9 | 82 | 0.7812 | 0.8020 | −2.08 |

[OBSERVED `campaign/results/hj12_prefix_frontier_20260922.report.json`, `noninferiority.arms.<arm>.handoff_ease.fields.goal_pass_rate` and `.goal_pass_handoff_only`]

Those two deficits are computed on **different task sets**, so the 9.6-point gap between them cannot
be read as the effect of a longer prefix. The 82 episodes where the nine-step arm hands off are the
harder ones — the reference scores 0.8020 on them against 0.8961 on the 32 it skips. The six-step
arm's 111 keys are nearly the whole set. A longer prefix mechanically hands off on fewer, harder
episodes, so part or all of the apparent improvement could be population composition rather than
prefix length.

This is the single question that decides whether the campaign's one positive result survives, so it
must be measured rather than argued.

## What to build

Add a CLI flag, `--handoff-keys-from <arm-name>`. When given, **every** arm's `handoff-only` and
`no-handoff` populations are built from that one named arm's `handoff_occurred` flags, instead of
each arm using its own. The reference and floor arms are restricted to the same keys, exactly as now.

Requirements:

1. **Default behaviour is unchanged.** Omitting the flag must reproduce the current output
   byte-for-byte on the same inputs. Other reports read this file.
2. Name the pinned arm in the emitted JSON so a reader cannot mistake which key set produced a row.
   Record the key-set size too.
3. An unknown arm name is a **fatal error naming the valid arms**, never a silent fall-back to
   per-arm keys. A silent fall-back here would produce exactly the misreading this flag exists to
   prevent.
4. Pinning to arm X must leave arm X's own rows identical to what it reports today. That is the
   self-check.
5. Apply to the non-inferiority table and the chord test, for `goal_pass_rate` and TGC, as the
   existing population does.

## Tests

- With the flag pointing at an arm, a second arm's `handoff-only` key set equals the first arm's, not
  its own.
- The pinned arm's own rows are unchanged versus the unpinned run.
- Omitting the flag reproduces current behaviour.
- An unknown arm name raises with the valid names in the message.
- `n_pairs` equals the pinned key-set size on every restricted row.

## Verification run

Run the frontier over the four existing prefix arms pinned to `prefix_m9`, and paste the
`goal_pass_rate` handoff-only row (arm score, reference score, deficit, CI, `n_pairs`) for
**`prefix_m2`, `prefix_m4`, `prefix_m6` and `prefix_m9`**:

```
timeout 1800 hpc -c 4 -m 16gb -t 00:25:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python scripts/analysis/j8_frontier.py --arm planner_alone=/scratch/n12194778/sidekick/results/hj1b_planner_20260915 --arm sft_plan=/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware --arm prefix_m2=/scratch/n12194778/sidekick/results/hj12_prefix_m2_20260922 --arm prefix_m4=/scratch/n12194778/sidekick/results/hj12_prefix_m4_20260922 --arm prefix_m6=/scratch/n12194778/sidekick/results/hj12_prefix_m6_20260922 --arm prefix_m9=/scratch/n12194778/sidekick/results/hj12_prefix_m9_20260922 --reference-arm planner_alone --floor-arm sft_plan --cost-key planner_tokens_noncached --handoff-keys-from prefix_m9 --out /tmp/x17_pinned.json'
```

Then run the identical command **without** `--handoff-keys-from` to `/tmp/x17_default.json` and paste
the result of comparing the two files' `prefix_m9` handoff-only rows — they must match.

Write both JSONs to `/tmp`, never to `campaign/results/`.

## Report the number that matters

In STATUS, state plainly whether the six-step arm's deficit **on the nine-step arm's 82 keys** is
close to its −11.70 on its own 111 keys, or close to the nine-step arm's −2.08. Do not interpret
beyond that; I draw the conclusion.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Dev only; never read `test_normal` or `test_challenge`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- The suite is at **501 passed, 1 skipped** and must not fall.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X17.md`, under 500 words: the flag name, how the pinned keys are recorded in
the JSON, the four pasted `goal_pass_rate` handoff-only rows under the pinned run, the unpinned-vs-
pinned equality check for `prefix_m9`, the test names, and the pasted suite line. Tag every claim
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
