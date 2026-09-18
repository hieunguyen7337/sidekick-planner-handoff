# W-25 — the substitution test: does a later review cancel the withheld one?

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Analysis only. CPU only. Zero planner calls. No GPU jobs. Do not modify production code.
Do not commit.**

## The hypothesis this unit tests

The branch definition was amended on 2026-09-17 so that **in both arms the reviewer stays live on
its normal 5-step schedule after the branch point**. The treated arm receives correction `i`; the
untreated arm omits it — but then, five steps later, the live reviewer speaks anyway.

If that later review delivers roughly the same guidance, the untreated arm **recovers**, and Δ
stops measuring "was this intervention worth anything" and starts measuring "did it matter
whether this guidance arrived now or five steps from now". Timing is plausibly a coin flip even
when the guidance itself is valuable — which would produce exactly what W-24 measured: a real but
**symmetric** per-point effect, an asymmetry of 0, and `needed` indistinguishable from a null.

**The test:** if substitution is the cause, Δ and the `needed` rate must rise as the number of
*later* review opportunities in the untreated arm falls — and must be largest where there are
none at all.

If instead Δ is flat in the number of later reviews, substitution is **not** the explanation and
the near-zero effect is a property of the intervention itself. Both outcomes are informative.
**Do not prefer either one.**

## Data

- Train: `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/`
- Dev: `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/`

`branch_runs.jsonl` in each holds the rows. The per-branch event logs are in the campaign-shaped
tree under `fixed_k/<seed>/<task_id>__b<i>_s<bseed>/events.jsonl`.

🔺 **Read-only. Do not write anything under `/scratch/.../results/`.**

Reuse the loading, point-grouping and completeness logic from
`campaign/workers/scratch_W24/permnull.py` so the population matches W-24 exactly (complete =
all four branch seeds 101–104 present with non-null `branch_gpr` in both conditions). Put your
script in `campaign/workers/scratch_W25/`.

## Step 1 — count the later reviews, from the event logs

For every **untreated** branch of every complete point, count the `intervention` events that
occur **after** the branch step `s`. Call this `n_later`.

Do this from `events.jsonl`, which is ground truth. Report how many branch directories you could
open and how many were missing or unreadable — do not silently drop them.

Cross-check against the arithmetic proxy `floor((branch_steps − s) / 5)` and report the
correlation and the disagreement rate between the two. If they disagree badly, say so and
**trust the event logs**, but report both.

Per point, `n_later` may differ across the four replicate seeds. Use the **median across the
four untreated replicates** as the point's `n_later`, and also report how often the four
replicates disagree.

## Step 2 — the dose-response table

Bucket complete points by `n_later` ∈ {0, 1, 2, 3+}. For **train** and **dev** separately, and at
δ = 0.166 and δ = 0.100, report per bucket:

| bucket | n points | mean Δ | mean help | mean harm | needed | needless | f = needed/n | asymmetry needed−needless |
|---|---|---|---|---|---|---|---|---|

⚠ **`f` = needed / n_bucket.** Print the literal numerator and denominator. An earlier unit
reported the needless fraction in a column labelled `f`; do not repeat it.

Also report **Spearman correlation between `n_later` and Δ** across all complete points, with a
p-value, for each split.

## Step 3 — the clean-counterfactual subset

Points with `n_later = 0` are the subset where **no substitution was possible** — the untreated
arm never received a later review, so Δ there estimates the quantity the campaign actually
wanted. This is the most important single number in the unit.

For that subset, on each split and at each δ, run the **same paired sign-flip permutation null
as W-24** (within each point, independently per branch seed, swap treated[s] with untreated[s]
with probability 0.5; 10,000 permutations; report the seed). Report observed vs null mean, null
2.5th/97.5th, and one-sided p for: `needed`/`f`, `needless`, mean Δ, mean help, mean harm, and
the two-sided p for the asymmetry.

State plainly whether each observed value falls inside or outside its null interval.

🔺 If the `n_later = 0` subset is small, **say so and report the achieved power honestly** — a
null result on 20 points is not evidence of absence. Report the subset size prominently.

## Step 4 — a confound you must check, not assume away

`n_later = 0` is not randomly assigned: it happens when the episode **ends soon after** the
branch point, which correlates with being near the end of a task, and with the trajectory already
having succeeded or already having failed. So the `n_later = 0` subset is enriched for a
different kind of point.

Report, per `n_later` bucket: mean `step` (branch depth), mean untreated score, the **ceiling
fraction** (mean(untreated) = 1.000) and the **floor fraction**. If the `n_later = 0` bucket has a
very different ceiling fraction, say so — a Δ difference across buckets could be a composition
effect rather than substitution.

As a partial control, repeat the Step 2 table **restricted to contestable points only** (W-20's
definition: non-ceiling, non-floor) and label it post-hoc.

## Interpretation you must NOT do

Report the numbers and the interval statements. **Do not recommend a course of action, do not
declare the thesis supported or refuted, do not propose amending δ, the branch definition or the
pre-registration, and do not re-run any rollout.**

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- Reading a few thousand small event logs is the heavy part; read them once and cache what you
  need in memory rather than re-walking the tree per statistic.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job.** Quota is exhausted
  until 2026-09-19 ~21:13.
- **Do not commit.** Suite stays at **349 passed, 1 skipped** if you touch anything importable
  (you should not need to).
- Write `campaign/workers/STATUS_W_25.md` with resume state.
- Report to `campaign/workers/W25_SUBSTITUTION.md`; raw output in
  `campaign/workers/scratch_W25/w25_out.txt`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The tables above, filled, with literal numerators and denominators.
- The PBS job id and the permutation seed.
- The count of branch directories opened, missing, unreadable.
- The event-log vs proxy agreement rate for `n_later`.
- The size of the `n_later = 0` subset, stated prominently.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
