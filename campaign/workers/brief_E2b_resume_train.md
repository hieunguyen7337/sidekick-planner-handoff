# Brief E2b — RESUME unit E2: verify the built dataset, then train

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Situation

Unit E2's agent exited without finishing. Its PBS **build** job is still running independently and
must be left alone. Read `campaign/workers/STATUS_E2.md` first — it holds the prior state.

- Build job **`25574101.aqua`** is building
  `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl`.
- **DO NOT resubmit the build.** A first attempt (`25573230`) died on a 30-minute walltime; this one
  has 2 hours. If the jsonl already exists when you start, skip to Step 2.

## Step 1 — wait for the build

Poll `qstat 25574101.aqua` about once a minute until the job leaves the queue. Bound your waiting at
~75 minutes. Do not busy-loop; sleep between checks.

If the job failed or produced no jsonl, **STOP**, write STATUS explaining what the spool log says, and
do not submit any GPU job.

## Step 2 — verify the dataset (all four numbers required, before any GPU)

1. `wc -l` on the new jsonl. The original `sft_b_plus_20260918.jsonl` is **497**.
2. `grep -c 'INTERVENTION:'` on the new jsonl. **If this is 0, STOP.** The build stripped anyway and
   training would measure nothing.
3. From the new `.manifest.json`: the `dropped_counts` map, and `intervention_mode` (must be
   `"retain"`). The original had `correction_no_intervention` = 3 and **no** `intervention_in_context`
   key.
4. Any truncation statistic the manifest reports. Retained turns make sequences longer and
   `_check_budget` truncates against a 32,768 max length. **If the row count is materially below 497,
   say so loudly in STATUS** — it means truncation dropped episodes and the ablation gained a second
   variable. Report it; do not decide alone whether it is acceptable.

## Step 3 — protect the existing training log, then train

🔺 `scripts/pbs/train_sft.pbs:7` writes `#PBS -o
.../campaign/workers/logs/train_sft.out` — a **fixed path**. Submitting will **overwrite the existing
log of the `sft_b_plus_granite8b` training run**, which is that adapter's provenance. Before
submitting, copy it aside:

```
cp campaign/workers/logs/train_sft.out campaign/workers/logs/train_sft_sft_b_plus_20260918.out
```

🔺 The variable names are `DATA_JSONL` and `ADAPTER_OUT` [OBSERVED scripts/pbs/train_sft.pbs:39-40],
**not** `DATA`/`OUT`. An earlier brief of mine said `DATA`/`OUT`; that was wrong. Passing the wrong
names silently falls through to the defaults and trains on `sft_b.jsonl` into `sft_b_granite8b` —
the wrong data, clobbering another adapter's name, with entirely plausible-looking output.

Submit **exactly** this, and paste the command you actually ran into STATUS:

```
qsub -v DATA_JSONL=/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl,ADAPTER_OUT=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b,BASE_MODEL=ibm-granite/granite-4.2-8b scripts/pbs/train_sft.pbs
```

Do not edit `train_sft.pbs`. Its hyperparameters are hardcoded (`--epochs 2 --lr 1e-4 --rank 64
--seed 42`), which is what makes this a clean one-variable ablation against `sft_b_plus_granite8b`.
It runs a 20-step dry run first and aborts if that fails — let it.

After it finishes, confirm from the new job log that the data path it trained on is the **iaware**
jsonl, and report `OUT/manifest.json` (`hyperparameters`, `n_sequences`, `data_sha256`, `base_model`).

## Constraints

- **One GPU job only.** If a `gpu_inter` job of yours is already queued or running, wait; never submit
  a second.
- **No evaluation. No HJ8/J10. Do not read `test_normal` or `test_challenge`.**
- Do not overwrite `sft_b_plus_20260918.jsonl` or the `sft_b_plus_granite8b` adapter.
- Do not modify anything under `/scratch/n12194778/sidekick/results/`; never write under
  `hj6_branches_train_20260917`.
- `aquarius01` is a LOGIN NODE: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Compute via
  `qsub`/`hpc`. `timeout` on everything. BLAS pinned to 1 thread.
- Do not edit `docs/prereg_v1.md` or `docs/prereg_b1_pilot.md` — FROZEN.
- **Do not commit.**
- Update `campaign/workers/STATUS_E2.md` in place as you go, so a further resume is possible. Write
  resume state after every milestone — your predecessor died silently and left a running job behind.

## Return contract

Update `campaign/workers/STATUS_E2.md`, under 600 words: the four Step 2 numbers, the verbatim `qsub`
line, the training job id / exit code / wall time, the manifest contents, and every claim tagged
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
