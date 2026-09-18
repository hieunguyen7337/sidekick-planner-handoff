# W-16 — run J7: fit and calibrate the feature verifier (CPU only, zero planner calls)

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

This unit **runs an existing script and reports its numbers**. It is not a coding unit. Only
fix the script if it errors, and if you do, report exactly what you changed and why.

## What J7 is

Fit the `feature_lr` verifier (logistic regression over `trajectory_state` features) on the J6
**train** labels, temperature-scale it on the J6 **dev** labels, and report dev AUROC, Brier
and ECE. It is the router used by the `router_seq` arm, and its AUROC is one of the
pre-registered H3 numbers.

The script is `scripts/setup/fit_feature_verifier.py`. Its data paths were fixed by a previous
unit, so it takes four explicit inputs [OBSERVED scripts/setup/fit_feature_verifier.py:519-541].

## The command

Run it in a PBS job — **never on the login node**:

```
timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python scripts/setup/fit_feature_verifier.py --train-branches /scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branches.jsonl --dev-branches /scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branches.jsonl --train-campaign /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 --dev-campaign /scratch/n12194778/sidekick/results/hj4b_fixed_k_dev_20260917 --out artifacts/verifiers --date 20260918'
```

All four inputs were confirmed to exist at 2026-09-18:
train branches 777 rows, dev branches 382 rows.

## 🔺 The thing you must not gloss over — this fit is thin

`branches.jsonl` was rebuilt from **four** branch replicates, which cut the positive class
sharply. On train: 397 of 777 points are label-complete, and only **25** of them are `needed`.
That is the positive class this logistic regression has to learn from.

So the headline number is not AUROC alone. **Report, prominently and before any AUROC:**

- n points used for the fit, and n positives, for train and for dev separately;
- how many points were dropped, and why (incomplete labels, missing features, ambiguous);
- whether ambiguous points were excluded (they should be — check and confirm, do not assume).

If train positives are under ~30, say plainly that the fit is **underpowered**, and report dev
AUROC **with a confidence interval** (bootstrap over dev points). Do **not** simply compare a
point estimate against the 0.65 threshold as though it settled anything — with this few
positives the interval will be wide, and a naive pass/fail would be a false result. If the
script does not emit a CI, compute one and say that you did.

## Also report, if the script emits them

Feature weights (which features carry signal), and anything the script says about calibration
before and after temperature scaling.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Everything that computes goes in a PBS job, as in the command above. BLAS is
  pinned to one thread in that command — keep it that way.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit a GPU job.** This is CPU only,
  and the Codex quota is exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Those are frozen evidence.
- **Do not modify** `scripts/setup/branch_counterfactual.py` or `src/sidekick/agents/planner.py`
  — other workers own them right now.
- **Do not commit.**
- Write the numbers to `campaign/workers/W16_J7_FIT.md`, and a resume state to
  `campaign/workers/STATUS_W_16.md`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The command you ran and its exit status.
- The counts first (points, positives, drops), then AUROC / Brier / ECE with the CI.
- The path of every artifact written.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. A number you read out of
  a file is OBSERVED with that file's path; a number you computed yourself is INFERRED and you
  say how you computed it.
