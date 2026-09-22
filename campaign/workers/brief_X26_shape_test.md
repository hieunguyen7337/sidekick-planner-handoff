# Brief X26 — the registered shape test: is the curve really flat then rising?

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis only. **Do NOT `qsub` an evaluation, do not touch a GPU, do not edit `src/`, `configs/` or
anything under `scripts/pbs/`.** Run your own analysis through `hpc` as described below.

## Read this first — it is a registered protocol, not a free choice

`docs/prereg_hj13_shape_20260923.md` §3 specifies this test **in advance and in full**: the model,
the breakpoint candidates, the bootstrap, the three hypotheses S1–S3, the robustness set, and the
condition under which the shape claim is withdrawn. That document is **frozen**. Your job is to
implement exactly what it says — not a better test, not a simpler one, not one that fits the data
more gracefully.

If you believe the registered specification is wrong or cannot be implemented as written, **stop and
say so in STATUS**. Do not silently substitute an alternative. A test chosen after seeing the data is
worth nothing here, and the whole value of this unit is that the specification predates the result.

Read §1.1 too: it records that the curve was already seen, so this test is **exploratory** on the
existing arms and confirmatory only on data that does not yet exist. Your output must carry that
label.

## What to build

`scripts/analysis/hj12_shape.py`.

Reuse the bootstrap machinery in `scripts/analysis/j8_frontier.py` — do not write a second
resampler. **Note that file is being modified by another unit right now** to add `--cluster
{task,scenario}`; build against its public helpers and re-run once it settles. If its scenario
clustering has landed, use it; if not, say so and implement task clustering only, leaving a clean
seam for scenario clustering.

Implement, per §3:

- **Primary**: segmented linear regression of `goal_pass_rate` on $m$ over
  $m \in \{0, 2, 4, 6, 7, 8, 9, 10, 11\}$, where $m = 0$ is `sft_plan`. One breakpoint $\tau$,
  profiled over integer candidates $\{4, 6, 7, 8, 9\}$, selected by minimum residual sum of squares.
- **Intervals**: the campaign's paired percentile bootstrap — 10,000 resamples, seed 20260915 —
  resampling **scenarios** (and reporting task-clustered alongside). **Refit the entire segmented
  model inside every resample**, including re-selecting $\tau$. Conditioning on a $\tau$ chosen once
  on the full sample would understate the uncertainty, which is the specific error this design
  exists to avoid.
- **S1**: interval for $\beta_1$ (pre-threshold slope); report whether it excludes zero.
- **S2**: one-sided 95% test that $\beta_1 + \beta_2 > 0$.
- **S3**: bootstrap interval for $\tau$; report whether it excludes $m \le 4$.
- **Verdict**: the shape claim is supported **only** if S1 is not rejected **and** S2 holds **and**
  S3 holds. Emit that verdict as a single boolean plus the three components. Any other combination
  emits "no threshold established".

**Robustness, all pre-specified, reported whether or not they agree with the primary**: (a) isotonic
monotone fit, reporting where it first exceeds the `sft_plan` floor by more than 5 pp; (b) the same
segmented fit on TGC; (c) the same fit on each population defined in
`docs/prereg_hj12_dev_20260922.md` §3.4 and on the pinned key sets from `--handoff-keys-from`;
(d) the same fit with $m$ re-expressed as a **percentile of the planner's own step-count
distribution** — this makes our result directly comparable to studies that parameterise the switch
point that way, so get the percentile mapping right and document it.

Mark the robustness analyses descriptive and uncorrected; S1–S3 are one family.

## Which data to run it on

Run it **twice** and emit two reports:

1. `campaign/results/hj13_shape_pre_guard_20260923.report.json` — the original arms
   `hj12_prefix_m*_20260922`, which is what the campaign has reported so far.
2. `campaign/results/hj13_shape_post_guard_20260923.report.json` — the re-run arms
   `hj12_prefix_m*_20260923`, produced under the terminal-guard fix (jobs 25681670 and 25681998).
   **These may still be running when you start.** Check for 114 episodes per arm before analysing;
   if an arm is incomplete, say so and analyse only the complete ones, naming the gaps.

The difference between the two is itself a result: the prereg §2.1 predicts the large-$m$ arms fall.
Report the per-$m$ delta between the two runs in STATUS.

Python: `/scratch/n12194778/sidekick/env/bin/python`, `PYTHONPATH=src:.`, BLAS pinned
(`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`). Run through `hpc`, never on the login
node. Write reports to `campaign/results/`, never to `/tmp` — `/tmp` on a compute node is invisible
afterwards.

## Tests

- a synthetic curve with a known breakpoint at 7 recovers $\tau = 7$;
- a synthetic straight line yields an S3 interval that does **not** exclude $m \le 4$, i.e. the test
  can fail to find a threshold that is not there — this is the most important test in the unit;
- the bootstrap re-selects $\tau$ within resamples (assert on observed variation in $\tau$ across
  resamples, not on the point estimate);
- the percentile remapping is monotone and matches a hand-computed case.

The suite must not fall. It currently reports failures in `scripts/analysis/j8_frontier.py` from
another unit in flight — ignore that file when you measure and say so.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read `test_normal` or
  `test_challenge`.
- Frozen, read only: every `docs/prereg_*.md`, every `hj8_*` and `hj11_*` config.
- **Do not commit.** I review and commit.
- Create your files within your first three actions, then iterate with tests.

## Return contract

`campaign/workers/STATUS_X26.md`, under 600 words: the script path; $\hat{\tau}$ with its interval;
$\beta_1$ and $\beta_1 + \beta_2$ with intervals; the S1/S2/S3 verdicts and the single combined
verdict, **for both the pre-guard and post-guard data**; the per-$m$ delta between them; the four
robustness results; which arms were incomplete if any; the test names; and the suite line.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. Do not interpret beyond reporting the
registered verdicts — I draw the conclusions.

## Addendum 2026-09-22 — the measured replicate noise floor, and the post-guard arms

`docs/prereg_hj13_shape_20260923.md` §3 registers a withdrawal condition against the replicate noise
floor. That floor is now measured, so use these numbers rather than assuming one.

**Two clean replicate pairs.** The 20260923 prefix re-runs carry the post-prefix terminal guard, but at
m=2 and m=4 the guard provably never fires — `executor_silent` is 0 in both the 20260922 and the
20260923 runs at those depths [OBSERVED result.json `totals.per_actor.executor.n_calls` across
114 episodes per arm]. Those two pairs are therefore pure replicates of the same configuration,
differing only in sampling (`sampling_seed` is null and temperature is 0.7, so no arm is deterministic):

| m | 20260922 | 20260923 | Δ goal_pass |
|---|---|---|---|
| 2 | 0.7187 | 0.6856 | **−3.31 pp** |
| 4 | 0.7340 | 0.7190 | **−1.50 pp** |

Treat **3.31 pp** as the observed maximum single-arm replicate deviation on `goal_pass_rate` at n=114,
and say so explicitly wherever the shape test compares two arms. Two pairs is a floor estimate from a
very small sample, not a variance estimate — report it as "observed spread across the two available
replicate pairs", never as a standard error, and do not convert it into a CI.

**Consequence to state in the report:** the pre-guard m6→m9 rise is +9.89 pp and the post-guard rise is
+8.77 pp, both roughly 2.6–3× that maximum deviation, whereas the advice-channel contrast (−0.48 pp) is
well inside it. The shape test must report both comparisons against the same floor.

**Use the post-guard (20260923) arms as the primary series** and the 20260922 arms as the pre-guard
comparison, reporting both. Do not pool them: they are different configurations at m ≥ 6.


**The guard delta so far, as data — draw no verdict from it, that is my job.** The guard's reach grows
with m (episodes where the executor never acted, post-guard: 0, 0, 3, 8, 20, 30 at m = 2, 4, 6, 7, 8, 9;
pre-guard it is 0 at every m). The measured per-arm delta:

| m | pre-guard | post-guard | Δ pp | episodes silenced |
|---|---|---|---|---|
| 2 | 0.7187 | 0.6856 | −3.31 | 0 |
| 4 | 0.7340 | 0.7190 | −1.50 | 0 |
| 6 | 0.7145 | 0.7237 | +0.92 | 3 |
| 7 | 0.7514 | 0.7544 | +0.30 | 8 |
| 8 | 0.7733 | 0.7627 | −1.06 | 20 |
| 9 | 0.8134 | 0.7904 | −2.30 | 30 |

m=10 and m=11 were still running when this was written; **fill them in from the artifacts and do not
infer them**. `docs/prereg_hj13_shape_20260923.md` §2.1 predicted these arms would fall, most at large
m. Report the observed deltas at every m together with the silenced counts and the replicate floor, and
state whether the registered prediction is met **at each m separately**. Do not summarise it as a single
pass/fail across the curve, and do not soften or restate the prereg language.
