# W-19 — is the frozen δ too conservative for a four-replicate Δ? (analysis only)

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Read-only analysis. Change no production code. Do not commit. Do not touch
`/scratch/.../results/` — write your outputs under `campaign/workers/`.**

## The question

The label rule is pre-registered as: `Δ = mean(treated) − mean(untreated)`, and

- `needed := Δ > δ`, `needless := Δ < −δ`, `ambiguous := |Δ| ≤ δ`

with **δ defined as a rule, not a number**: *the 75th percentile of
`|treated[101] − treated[102]|` over train points — the noise floor between two identically
configured runs.* It was frozen at **δ = 0.166** over 734 points.

That δ is the spread of a **difference between two single draws**. But Δ is a **difference of
two means**. Write σ² for the within-condition variance of one branch's score. Then:

- `Var(|t101 − t102|)` = 2σ²  → SD = σ·√2
- `Var(Δ)` at 2 replicates = σ²/2 + σ²/2 = σ²  → SD = σ
- `Var(Δ)` at 4 replicates = σ²/4 + σ²/4 = σ²/2 → SD = σ/√2

So the statistic being thresholded is **√2× less noisy than δ's yardstick at two replicates, and
2× less noisy at four**. Common random numbers (seeds are paired across conditions) make Δ less
noisy still, so those are upper bounds on the appropriate band.

If that reasoning holds, the frozen δ has always been conservative and is now roughly **twice**
as wide as the noise floor it is meant to represent — which mechanically inflates `ambiguous`
and suppresses both `needed` and `needless`. On four replicates we currently see
needed 25 / needless 46 / **ambiguous 326** out of 397 train points.

**Your job is to test that reasoning against the data, not to assume it.**

## Data

- train branch rows: `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl`
- dev branch rows: `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branch_runs.jsonl`

Row fields include `key` (`campaign/seed/task_id/i/condition/branch_seed`), `condition`
(`treated`/`untreated`), `branch_seed` (101/102/103/104), `branch_gpr` (null when the branch
crashed). A point is `key` truncated to its first four `/`-separated fields. A point is
complete on a seed set when every (condition, seed) pair in that set has a non-null
`branch_gpr`.

## What to produce

1. **Measure σ empirically.** From the four treated replicates at each complete point, compute
   the within-condition SD. Do the same for untreated. Report the distribution (median, IQR),
   and report the *observed* SD of Δ across replicate subsets. Do **not** take σ from theory.

2. **Measure the CRN correlation** between treated and untreated at the same branch seed. This
   determines how much the pairing actually reduces `Var(Δ)`, and the theory above ignores it.

3. **Derive the noise floor appropriate to a four-replicate Δ**, using the same *rule* that
   produced 0.166 — a 75th percentile of a null-difference distribution — but applied to the
   estimator actually being thresholded. The cleanest null: split the four treated replicates
   into two disjoint pairs and take `|mean(pair A) − mean(pair B)|`, which is a
   same-condition difference of two 2-replicate means. State clearly how your null relates to
   the 4-replicate Δ and whether it needs a further √2 adjustment. **Show the arithmetic.**

4. **Label sensitivity.** Recompute the label distribution on the complete four-replicate train
   and dev points across a δ grid: at least `0.166` (frozen), your derived value, `0.083`, and
   a sweep from 0.02 to 0.25. Report for each: n needed, n needless, n ambiguous, f, and 1−f.

5. **The two numbers that matter**, called out explicitly:
   - how many `needed` points exist at the derived δ (the training-signal count), and
   - what `f` and `1 − f` become (the headline).

6. **A stability check.** At the derived δ, how many labels flip between the two disjoint
   2-replicate halves? Compare against the 0.8388 agreement measured at δ = 0.166. A δ that
   buys positives by amplifying noise will show up here as worse agreement — report it either
   way.

## Interpretation rules — read these

- 🔺 **Do not recommend changing the pre-registration.** δ is frozen and only the user decides
  whether to amend it. Your output is the evidence for that decision, stated neutrally.
- 🔺 **Do not tune δ to any outcome.** You are deriving a noise floor from the null distribution,
  not searching for a δ that yields more positives. If your derived δ yields *fewer* positives,
  report that with the same prominence.
- If the theory in the first section is wrong, say so and show why. That is a valid result.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. All computation goes in a PBS job:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit a GPU job.** The quota is
  exhausted until 2026-09-19 ~21:13.
- 🔺 **Read-only on `/scratch`.** Put any script you write under
  `campaign/workers/scratch_W19/` and your report at `campaign/workers/W19_DELTA.md`.
- Other workers own `scripts/setup/branch_counterfactual.py`,
  `scripts/setup/fit_feature_verifier.py`, `src/sidekick/agents/planner.py` and
  `src/sidekick/training/matched_sft.py`. **Do not touch any of them.**
- **Do not commit.** Write `campaign/workers/STATUS_W_19.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The derived δ, with the arithmetic shown.
- The δ-grid table (needed / needless / ambiguous / f / 1−f).
- The measured σ, the CRN correlation, and the label-agreement check.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. A number you computed is
  INFERRED and you state the script and the job id that produced it.
