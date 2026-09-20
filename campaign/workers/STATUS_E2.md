# STATUS E2 — intervention-retaining dataset + variant adapter

**Unit:** E2 / E2b resume
**State:** complete
**Last update:** 2026-09-21 ~01:18 AEST

## Owned files

- this STATUS
- `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl` (+ `.manifest.json`)
- `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b` (+ `_dryrun`)
- `campaign/workers/logs/train_sft_sft_b_plus_20260918.out`

Did not overwrite `sft_b_plus_20260918.jsonl` or `sft_b_plus_granite8b` (mtime Sep 18 / Sep 19 still). [OBSERVED ls] No eval, no HJ8/J10, no test-split reads, no git, no edits to `train_sft.pbs`.

## Step 2 numbers (all four, before GPU)

1. `wc -l` = **497** (original 497; not below). [OBSERVED wc]
2. `grep -c 'INTERVENTION:'` = **267** (not 0). [OBSERVED grep]
3. `dropped_counts` = `{"correction_no_intervention": 3}`; `intervention_mode` = `"retain"`; no `intervention_in_context` key. [OBSERVED jsonl.manifest.json:440-443]
4. Truncation: `n_truncated` = **22** (original jsonl was 21); token_length_percentiles max=102646 p50=18906 p90=29705. Row count stayed 497 so truncation did **not** drop episodes. [OBSERVED jsonl.manifest.json:453-455,1054-1058; original jsonl.manifest.json:452]

## Build

`25574101.aqua` Exit_status=0, walltime 01:23:32. [OBSERVED qstat -x; spool 20260920-213856-1565089.out:1063,1098]

## qsub (verbatim; not issued by E2b)

Did **not** `qsub`: a GPU job with the exact vars was already queued (`25576173.aqua`, ctime 23:04:00). One-GPU rule. Submit_arguments [OBSERVED `qstat -f 25576173.aqua`]:

```
qsub -v DATA_JSONL=/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl,ADAPTER_OUT=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b,BASE_MODEL=ibm-granite/granite-4.2-8b scripts/pbs/train_sft.pbs
```

Copied `campaign/workers/logs/train_sft.out` → `train_sft_sft_b_plus_20260918.out` (55719 bytes; data=`sft_b_plus_20260918.jsonl`) while still Q. [OBSERVED ls/cmp; backup log:3]

## Train

- Job **`25576173.aqua`**, Exit_status **0**, walltime **02:11:15** (stime 23:05:30, obit 01:16:49). [OBSERVED train_sft.out:199-200,231; qstat -x]
- Log data path is the **iaware** jsonl. [OBSERVED train_sft.out:2-3]
- Dry-run exit=0 at 23:08:22; full training exit=0 at 01:16:45. [OBSERVED train_sft.out:59,195]

`OUT/manifest.json` [OBSERVED `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b/manifest.json`]:
- `base_model`: `ibm-granite/granite-4.2-8b` (:2)
- `data`: iaware jsonl (:4)
- `data_sha256`: `f2f439d9a24df8e1ac3ca5f94a4f0360aeb23e7564597a082f26dbaf5c77d066` (:5)
- `n_sequences`: **479** (= original adapter 479; `n_rows_in` 497; dropped 18 truncated-past-labels). [OBSERVED :84-90; original adapter manifest:43]
- `hyperparameters`: epochs 2.0, lr 0.0001, r 64, seed 42, effective_batch 8, max_length 32768, max_steps null (:48-63,100)
- `n_truncated_kept`: 18 (:90)

## Resume

Done. Adapter is at `.../adapters/sft_b_plus_iaware_granite8b`. Do not resubmit. Do not eval from this unit.
