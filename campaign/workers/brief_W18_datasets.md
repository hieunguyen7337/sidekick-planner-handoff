# W-18 — build the J5a/J5b datasets and report what they actually contain

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**This is a build-and-measure unit, not a training unit. You will not train anything.**
Other workers own `scripts/setup/branch_counterfactual.py`, `scripts/setup/fit_feature_verifier.py`
and `src/sidekick/agents/planner.py` — **do not touch any of them.**

## Why this runs now

The counterfactual branches (J6) are finished and relabelled on four replicates. The training
runs themselves are paused by the user pending a separate question, but the **datasets** cost
nothing but CPU and they answer a question we need before any GPU is committed: **how many ASK
targets does `sft_c` actually get?**

On the four-replicate train labels there are only **25 `needed` points** out of 397
label-complete ones. `sft_c`'s ASK supervision comes entirely from those. If the built dataset
confirms ~25 ASK targets, J5b is not trainable as designed, and it is far better to learn that
from a CPU job today than from a GPU run later.

## The builders already exist — do not write new ones

`src/sidekick/training/matched_sft.py` has `build_sft_b_plus` [OBSERVED :704],
`build_ask_dataset` [OBSERVED :740] and a CLI `main` [OBSERVED :790-828] with
`--mode {sft_b_plus,sft_c}`. `--mode sft_c` requires `--labels-jsonl` [OBSERVED :807-808].
Defaults: teacher `/scratch/n12194778/sidekick/artifacts/sft/sft_b_s123_p075.jsonl`
[OBSERVED src/sidekick/training/sft_data.py:52-54], correction campaign
`/scratch/n12194778/sidekick/results/hj4_correction_train_20260917`
[OBSERVED src/sidekick/training/sft_data.py:58-60].

## The two builds

Run each in its own PBS job — **never on the login node**. Output goes to
`/scratch/n12194778/sidekick/artifacts/sft/`, which is where the teacher set already lives.

**J5a control (`sft_b_plus`, no ASK targets):**

```
timeout 1800 hpc -c 4 -m 32gb -t 00:30:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m sidekick.training.matched_sft --mode sft_b_plus --campaign-root /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 --split train --out /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl'
```

**J5b policy (`sft_c`, ASK at `needed` points):** same, with
`--mode sft_c --labels-jsonl /scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branches.jsonl --out /scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl`.

Both builders return a summary dict. **Capture it** — print it and save it. If the CLI discards
it, write a tiny wrapper that calls the function and dumps the summary as JSON; do not modify
`matched_sft.py` to achieve that.

## The invariants to check — these are pre-registered, report each as pass/fail

From the campaign plan, the two datasets must differ **only** at the needed points:

1. **Same episode set** in both files.
2. **Same number of supervised action targets** in both.
3. **ASK targets in `sft_c` == n_needed exactly**, and **zero** ASK targets in `sft_b_plus`.
4. **No sequence in either file contains the substring `INTERVENTION:`** (interventions are
   stripped; a leak here would invalidate the whole matched-pair design).
5. Record the count of records dropped as unrepresentable, from each summary, with the reason.

Check these by reading the two output files, not by trusting the summary dicts alone. Where a
summary and the file disagree, **report the disagreement** — do not reconcile it silently.

## Report, prominently

- n sequences, n supervised action targets, n ASK targets, n drops — for each file.
- The five invariants, each pass/fail with the number that settles it.
- `delta_band_delta` and `labels_sha256` as recorded in the `sft_c` summary (provenance: the
  label file this was cut from).
- Your own one-line read of whether 25-ish ASK targets is what materialised.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Everything that computes goes in a PBS job as shown, BLAS pinned to one thread.
- 🔺 **Do not train. Do not submit a GPU job.** This unit is CPU only.
- 🔺 **Zero planner calls. Do not invoke `codex`.** The quota is exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`** — frozen evidence. Writing new files
  under `/scratch/.../artifacts/sft/` is expected and fine; do not overwrite
  `sft_b_s123_p075.jsonl`, which is the frozen teacher set.
- **Do not commit.**
- If you change any code at all, say so explicitly and show the diff. The expectation is that
  you change none.
- Suite if you touch code: `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`,
  currently **339 passed, 1 skipped**.
- Write `campaign/workers/W18_DATASETS.md` with the numbers and
  `campaign/workers/STATUS_W_18.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The two commands and their exit statuses.
- The counts table and the five invariant verdicts.
- Absolute paths of both output files and their sha256.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
