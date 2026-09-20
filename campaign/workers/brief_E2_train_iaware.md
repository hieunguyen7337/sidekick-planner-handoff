# Brief E2 — build the intervention-retaining dataset and train the variant adapter

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**PREREQUISITE: unit E1 must have landed first.** E1 makes `--no-strip-interventions` able to write
a dataset at all. Before you start, confirm `campaign/workers/STATUS_E1.md` exists and reports a
passing suite. If it does not, STOP and write `campaign/workers/STATUS_E2.md` saying you are blocked
on E1. Do not attempt the build without it.

## Why this unit exists

The executor is served `INTERVENTION: {correction}` user turns at runtime
[`src/sidekick/systems/loop.py:748`, `:775`] but every trained adapter had those turns stripped from
its training data. We are training ONE variant adapter that retains them, as a one-variable ablation
against `sft_b_plus_granite8b`. Everything else — base model, hyperparameters, seed, teacher rows,
split — must be identical.

## Step 1 — build the dataset

Mirror the original build exactly, changing only the flag and the output path. The original was
[OBSERVED `/home/n12194778/.hpc-spool/20260918-131609-2993281.pbs:8-11`]:

- `--mode sft_b_plus`
- `--campaign-root /scratch/n12194778/sidekick/results/hj4_correction_train_20260917`
- `--split train`
- `--out /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl`

Your build changes exactly two things:
- add `--no-strip-interventions`
- `--out /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl`

Run it through PBS (it is a login node — never run the interpreter directly there), with BLAS pinned
to one thread and a `timeout`, in the same shape as the original spool file.

**Do NOT overwrite** `sft_b_plus_20260918.jsonl` or any existing adapter. New prefix only.

### Report these numbers before training (all required)

1. Row count of the new jsonl (`wc -l`). The original is **497**.
2. `grep -c 'INTERVENTION:'` on the new jsonl — must be **> 0**. If it is 0, STOP: the build silently
   stripped anyway and training would be pointless.
3. `grep -c 'INTERVENTION:'` on the ORIGINAL `sft_b_plus_20260918.jsonl` — expected 0. Report it.
4. From the build summary/manifest: the count of episodes dropped as `intervention_in_context`
   (`DROP_INTERVENTION_LEAK`) in the ORIGINAL build vs the new one. **This matters**: retaining
   interventions also stops those episodes being dropped, so the new dataset may have MORE episodes
   than 497. We need the size of that difference to know whether it is a second variable. Report it
   explicitly, do not hand-wave it.

## Step 2 — train

Submit `scripts/pbs/train_sft.pbs` with:
- `DATA=/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl`
- `OUT=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b`
- `BASE_MODEL=ibm-granite/granite-4.2-8b`

Do **not** edit `train_sft.pbs`. Its hyperparameters are hardcoded (`--epochs 2 --lr 1e-4 --rank 64
--seed 42` [OBSERVED `scripts/pbs/train_sft.pbs:53-78`]) which is exactly what makes this a clean
ablation. It runs a 20-step dry run first and aborts if that fails — let it.

Report the job id, exit code, wall time, and the contents of the written
`OUT/manifest.json` (`hyperparameters`, `n_sequences`, `data_sha256`, `base_model`).

## Constraints

- **Do NOT run any evaluation and do NOT submit any HJ8/J10 eval job.** Build and train only.
- **Do not read, analyse or report any `test_normal` or `test_challenge` data.**
- **Do not modify anything under `/scratch/n12194778/sidekick/results/`.** Never write under
  `hj6_branches_train_20260917`.
- `aquarius01` is a LOGIN NODE: no interpreter, `pip`, `tar`, `rsync` or `ffmpeg` there. All compute
  via `qsub` / `hpc`. `timeout` on everything. BLAS pinned to 1 thread.
- GPU queue limits: `max_run=2`, `max_queued=2`. One training job only.
- Do not edit `docs/prereg_v1.md` or `docs/prereg_b1_pilot.md` — FROZEN.
- **Do not commit.** Claude reviews and commits.
- Size the unit to under 10 hours; `hpc-guard` kills at 12 h wall.

## Return contract

`campaign/workers/STATUS_E2.md`, under 500 words:
- the exact build command and the exact `qsub` line, verbatim
- all four numbers from Step 1
- the training job id, exit code, wall time, and manifest contents
- every claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`
- resume instructions if you are interrupted mid-unit
