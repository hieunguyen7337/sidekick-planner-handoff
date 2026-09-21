# Brief X13 — record the P1 prefix curve result and the G1 verdict

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation only. No GPU, no `qsub`, no evaluation, no edits to `src/`, `scripts/` or `configs/`.
The report JSON is `campaign/results/hj12_prefix_frontier_20260922.report.json` (committed alongside
this work). **Invent nothing.** Every figure you need is below, copied from that file. If you want a
number that is not here, read it from that JSON with `jq` and cite the key, or leave a `[GAP]`.

## The numbers

All dev, 114 pairs, task-clustered paired percentile bootstrap, 10,000 resamples, `goal_pass_rate`
primary. Zero crashes in every arm. Zero hosted calls spent: the prefixes are replayed.

Per-arm, all-episodes population. Cost is `planner_tokens_noncached` per episode, and the fraction is
of `planner_alone`'s 684,453.

| arm | goal_pass | TGC | tokens/ep | % of planner | handoff rate |
|---|---:|---:|---:|---:|---:|
| `sft_plan` (floor) | 0.7181 | 0.3947 | 23,906 | 3.5% | — |
| `prefix_m2` | 0.7187 | 0.4211 | 78,346 | 11.4% | 114/114 |
| `prefix_m4` | 0.7340 | 0.4298 | 143,753 | 21.0% | 114/114 |
| `prefix_m6` | 0.7145 | 0.4298 | 221,043 | 32.3% | 111/114 |
| `prefix_m9` | 0.8134 | 0.5877 | 357,448 | 52.2% | 82/114 |
| `planner_alone` (ceiling) | 0.8284 | 0.6842 | 684,453 | 100% | — |

Prefix minus the plan-only floor, `goal_pass`, positive means the prefix is better:

| m | diff pp | CI95 pp | excludes zero |
|---:|---:|---|---|
| 2 | +0.06 | [−5.34, +5.58] | no |
| 4 | +1.58 | [−3.50, +6.69] | no |
| 6 | −0.37 | [−5.96, +5.05] | no |
| 9 | **+9.53** | **[+5.37, +14.14]** | **yes** |

Same against the floor on TGC: m=2 +2.63, m=4 +3.51, m=6 +3.51, all with intervals containing zero;
m=9 **+19.30 [+10.53, +28.07]**, excluding zero.

Arm minus `planner_alone`, `goal_pass`, non-inferiority margin −7 pp:

| arm | diff pp | CI95 pp | non-inferior |
|---|---:|---|---|
| `sft_plan` | −11.02 | [−17.88, −4.27] | no |
| `prefix_m2` | −10.97 | [−18.53, −3.14] | no |
| `prefix_m4` | −9.44 | [−17.46, −1.13] | no |
| `prefix_m6` | −11.39 | [−19.08, −3.39] | no |
| `prefix_m9` | −1.50 | [−8.10, +5.62] | **no — misses by 1.10 pp on the lower bound** |

Chord test, arm minus the straight line between floor and ceiling at equal cost: m=2 −0.85
[−6.13, +4.57]; m=4 −0.42 [−5.63, +4.82]; m=6 −3.66 [−9.22, +1.71]; m=9 +3.96 [−0.49, +8.88]. No arm
sits significantly above the chord.

## The contamination, which must be stated wherever m=9 is

At m=9, 32 of 114 episodes never handed off: the planner's recorded episode ended before step 9, so
those episodes are `planner_alone` replayed, not a hybrid. The report's `handoff_ease` diagnostic
records that the reference scores 0.8961 on those 32 and 0.8020 on the other 82, a gap of 9.41 pp, so
the no-handoff episodes are the **easier** ones. The pooled all-episodes figure therefore mixes
planner-identical scores on easy tasks with genuine hybrid scores on the rest.

On the honest handoff-only population (n=82), `prefix_m9 − planner_alone` is **−2.08 pp
[−11.25, +7.51]**: still not non-inferior, and now too wide to conclude much either way.

## The G1 verdict — record it as FAILED

Gate G1, as pre-registered, passes if **either**:

(a) some m ≤ 6 reaches non-inferiority to `planner_alone`. **It does not.** The three lower bounds are
−18.53, −17.46 and −19.08 against a −7 margin. This is not a near miss.

(b) the curve is monotone with `prefix_m6 − sft_plan` ≥ +5 pp on `goal_pass`. **It is not.** That
difference is **−0.37 pp**, and the curve is not monotone, since m=4 scores above m=6.

So **G1 FAILED**, and the plan's flat-curve branch applies: the live phase shrinks to the channel
arms, and tailoring becomes the central experiment rather than a refinement.

## The mechanism claim, which is the actual finding

Write this up as the result, not as an apology for one.

The failure-anatomy analysis established that executor failures begin early: the first environment
error falls in the first third of the episode in 67.2% of plan-only failures and 73.3% of the
periodic-review arm's, at a median relative position of 0.2143. A prefix of 4 to 6 planner steps
therefore **covers the region where executors first go wrong**. It changes nothing: every interval
against the floor contains zero at m=2, 4 and 6, on both metrics.

The benefit appears only at m=9, and `planner_alone` episodes run a median of 12 actions, so m=9 means
the planner has already done roughly three quarters of the median episode and the executor is
finishing a tail.

The honest conclusion is therefore: **a correct opening does not make this executor finish
correctly.** Its failures are not caused by a bad start and are not localised to the opening. That is
a substantive negative with a clear mechanism, it refutes the premise the protocol was designed
around, and it strengthens the case that the remaining lever is the model rather than the protocol.

## What to write

1. **`campaign/RUNS.md`** — a new section for P1, in the file's existing style. Everything above:
   the table, the three contrast tables, the contamination at m=9, the G1 verdict, the mechanism
   claim. State plainly that zero hosted calls were spent and that jobs `25596786` and `25596787`
   produced it.
2. **`docs/FOLLOWUPS.md`** — one entry: the m=9 arm cannot be reported on the all-episodes population
   without the handoff-only figure beside it, because 32 episodes are the reference replayed. Anyone
   quoting −1.50 pp without −2.08 pp alongside is quoting a contaminated number.
3. **`docs/prereg_hj12_dev_20260922.md`** — a dated amendment recording that G1 failed on both
   clauses, with the two numbers that decided it, and that the flat-curve branch is therefore in
   force. Do not rewrite the registered gate text; record the verdict against it.

Do **not** state any P2 result, any channel finding, or any decision about what runs next. None
exists, and the spend decision is not yours.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `jq` on the
  report JSON is fine.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X13.md`, under 400 words: the RUNS.md heading, the FOLLOWUPS entry title,
the prereg amendment heading, and any `[GAP]` markers. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
