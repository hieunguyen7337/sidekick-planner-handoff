# W-12 — record Gate B (train), the fired `harmful` flag, and the ×4 reliability result

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Formatting and filing only. **Do not recompute anything and do not change a number.** Every
figure below was produced by the repo's own `rebuild_derived` in a PBS job. Match the style
of the surrounding documents; read the existing Gate B (dev) block in `campaign/RUNS.md`
first, since this extends it.

## Task 1 — `campaign/RUNS.md`: Gate B (train)

- **Source**: `branch_runs.jsonl` of `hj6_branches_train_20260917`, 4188 rows at time of
  aggregation, re-aggregated on CPU with branch seeds 101/102.
- **Coverage**: 777 intervention points seen; **734 complete** on seeds 101/102; 43
  incomplete. (261 points were already complete on all four seeds at that moment; the ×4 job
  is still running.)
- **δ is now FROZEN on train**: `delta_band_delta = 0.166`, by the pre-registered rule, over
  the 734 complete points. ⚠ Record that this is **identical to the provisional value** used
  for the dev block, so no dev number computed against it moves. The dev block's
  "provisional" warning can be updated to say the band has since been confirmed.

| label | n | fraction |
|---|---:|---:|
| needed | 83 | 0.1131 |
| needless (= harmful) | 120 | 0.1635 |
| ambiguous | 531 | 0.7234 |

- **Mean Δ per point = −0.0206.** State plainly what this means: on train, the fixed review
  schedule's average effect on outcome is **negative**.
- **Validation**: factual outside `[min(treated), max(treated)]` for 0.16869 of 741 compared;
  mean signed difference +0.03529.

### Verdict against all three pre-registered Gate B thresholds

- `f_train < 0.10` → **does not fire** (0.1131). 83 needed points clears the "< 75 positives"
  concern, so **no fourth teacher/correction seed is required before J5b**.
- `f_dev > 0.85` → **does not fire** (0.158 at two replicates, 0.130 at four).
- `harmful > 0.15` → **🔺 FIRES** at **0.1635**. The pre-registered consequence is to flag the
  review format in FOLLOWUPS — see Task 3. Record here that it fired and that it changes the
  H3 reading, per the plan's own wording: *a reviewer that hurts one time in seven changes
  the H3 reading*.

## Task 2 — `campaign/RUNS.md`: the ×4 replicate result

The dev ×4 job completed: 3056 branch runs, 332 points complete on all four seeds × both
conditions. This was run specifically to test whether replicates lift label reliability, and
it is the direct measurement that last night's block could only predict.

| quantity | predicted from 2 seeds | measured at 4 seeds |
|---|---:|---:|
| mean single-replicate Pearson r | 0.164 | **0.1697** |
| reliability of the 2-replicate mean | 0.282 | **0.2902** |
| reliability of the 4-replicate mean | 0.440 | **0.4504** |

The 4-replicate figure is measured directly: three distinct 2-vs-2 splits of the four seeds,
each half-mean correlated with the other and Spearman-Brown corrected. The three splits give
0.5026, 0.3074 and 0.5412; the mean is 0.4504. ⚠ Record that spread — it is estimation noise
in r at n = 332 and it means 0.45 is a central estimate, not a tight one.

Mean single-replicate Spearman ρ = 0.1951.

**Label movement, same 332 points, band 0.166:**

- 2-seed mean: needed 50, needless 48, ambiguous 234
- 4-seed mean: needed 43, needless 43, ambiguous 246
- agreement 276/332 = **0.8313**; outright needed↔needless flips = **0**

State the reading: every disagreement is a borderline point crossing the band, never a sign
reversal, which is what noise reduction looks like rather than labels breaking. And the
consequence for the headline — **the two-replicate f was inflated by noise pushing borderline
points over the band**. At four replicates f_dev falls to 0.130 and **1 − f rises from 0.843
to 0.870**. The fixed schedule is *more* wasteful than the earlier figure suggested, not less.

## Task 3 — `docs/FOLLOWUPS.md`: a new OPEN entry for the fired flag

**OPEN — the timer's review format hurts often enough to fire the pre-registered flag.**

On train, `harmful` (= `needless`) is 0.1635, above the 0.15 flag threshold, and the mean Δ
per point is −0.0206. On dev the same quantities are 0.1417 and +0.0068. So a fixed five-step
expert review, in its current format, is at best a wash and on the training split is net
negative: it changes the outcome for the worse about one call in six.

Record the consequences:
- it changes the H3 reading, since "needless" is not merely wasted cost but active damage;
- it raises a question the campaign has not asked — whether the *format* of the review
  (the last 8 transcript lines plus an instruction) is what is at fault, rather than the
  timing;
- the plan's Gate A fallback already names "a larger-k / richer review format" as one branch
  of the decision, and this is direct evidence for that branch.

Do not propose a fix. Record the finding and the open question.

## Task 4 — `docs/FOLLOWUPS.md`: extend the wedged-branch entry

Add to the existing "a single wedged branch can idle a whole J6 job" entry: `rebuild_derived`
is **also called at startup** when `--resume` is set
(`scripts/setup/branch_counterfactual.py:1099-1100`), not only at the end. Observed
2026-09-18: the train ×4 job started at 04:58:37 and at 05:00:30 its startup rebuild — which
requires all four branch seeds per point — found no point complete and wrote an **empty**
`branches.jsonl`, `oracle_labels.json` and manifest over the 2-seed aggregation the previous
resume job had produced minutes earlier.

Nothing was lost, because `branch_runs.jsonl` is append-only and the 2-seed view rebuilds on
CPU in about 70 s. But record the trap: **the derived files are not a safe place to keep a
result while a job with a different `--branch-seeds` may start against the same tree**, and an
empty `branches.jsonl` beside a healthy `branch_runs.jsonl` is expected mid-campaign rather
than a sign of failure.

## Constraints

- `aquarius01` is a **login node for steering only** — you should not need to compute at all.
  No `python`, `pip`, `tar`, `rsync`, `ffmpeg` there.
- **Do not submit any job.** Two J6 jobs are live.
- **Do not commit.** Edit only `campaign/RUNS.md` and `docs/FOLLOWUPS.md`.
- Write `campaign/workers/STATUS_W_12.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

The diff, short. Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
