# Unit J-stat — how many seeds does the final run need?

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why

HJ-7 (the final test-split run) is run-once and preregistered: its seed count and its
non-inferiority margin ε cannot be chosen after seeing the result. The written plan assumed 3 seeds
and ε = 5 pp, but HJ-1 measured **7.0 pp of pure seed-to-seed noise on identical tasks** — larger
than the margin it is supposed to resolve. So the design has to be computed before it is frozen.

## Goal

Write **one new file**, `scripts/setup/hj7_power.py`, that estimates the per-task seed noise from the
HJ-1 data and reports what each candidate design can resolve. **Do not run it** — Claude runs it in a
PBS job.

## Input (already in the repo, do not modify)

`campaign/results/hj1b_planner_20260915.runs.jsonl` — one JSON object per run. Relevant keys, as
actually present:

```
{"task_id": "0d8a4ee_1", "seed": 1, "system": "planner_alone", "success": false, "tgc": 0.0,
 "error_type": null, "steps": 10, ...}
```

Also available for cross-checking: `hj1a_exec8b_20260915.runs.jsonl`,
`hj1c_fixed_k_20260916.runs.jsonl`, `hj1c_prompt_only_20260916.runs.jsonl` (these three are all-zero
arms, so they carry no usable variance — mention that rather than averaging them in).

## What the script must do

1. **Measure the noise.** Pair `planner_alone` runs by `task_id` across seed 1 and seed 2. Report:
   the number of pairs; how many are concordant-success, concordant-fail, and **discordant**; and the
   discordance rate. That rate is the per-task disagreement probability — the thing that sets the
   floor on what any number of seeds can resolve. Report the per-seed marginal TGC too, so the
   headline 7.0 pp seed gap is visible in the output.
2. **Simulate the HJ-7 design.** For a paired, one-sided 95% non-inferiority test on
   **168 tasks** (test_normal) × N seeds for N in {1, 2, 3, 4, 5}: simulate `sidekick` true success
   rates {0.60, 0.64, 0.68} against a `planner_alone` rate of 0.68, using a per-task Bernoulli model
   whose within-task seed correlation reproduces the discordance rate measured in step 1. Aggregate
   each system's per-task score as the mean over its N seeds (that is how TGC is reported), then
   bootstrap the paired difference the way `scripts/setup/hj1_gate.py` already does — **read that
   file and reuse its bootstrap rather than writing a second one**; import it if it is importable,
   and say in your report which you did.
3. **Report, for each (N, true-rate) cell**: mean CI half-width in percentage points, and the
   probability the design declares non-inferiority at margins ε ∈ {3, 5, 7, 10} pp. Then state the
   **smallest ε that each N can resolve with ≥ 80% power** when the two systems are genuinely equal.
4. Print a compact table to stdout and write the same content as JSON to a path given by
   `--out` (default `campaign/results/hj7_power.json`). Number of bootstrap / simulation replicates
   is a `--reps` flag defaulting to something that finishes in **under 5 minutes single-threaded**
   (BLAS must stay at 1 thread; do not add a parallel backend). Seed the RNG from a `--seed` flag so
   the output is reproducible, and record the seed and the input file's sha256 in the JSON.

## Constraints

- `aquarius01` is a login node: **do not execute the script**, do not run `python`, `pip`, `tar`,
  `rsync`, `qsub`, or any multi-minute command. Write the file and report.
- Depend only on the standard library plus numpy (available in the scratch venv). No pandas, no scipy,
  no matplotlib.
- Do not modify anything under `campaign/results/`, `src/`, or `configs/`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract (under 20 lines)

- The path you wrote and its CLI flags.
- Whether you reused `hj1_gate.py`'s bootstrap and how (quote the import or the copied function's
  name and line).
- The exact keys of the JSON it writes.
- Your stated model for within-task seed correlation, in one or two sentences — this is the load-bearing
  assumption and Claude will check it.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
