# STATUS E2 — intervention-retaining dataset + variant adapter

**Unit:** E2 **State:** done **Last update:** 2026-09-21 01:17 AEST

No eval, no HJ8/J10, no test-split reads, no writes under `/scratch/.../results/`, no git, `train_sft.pbs` unedited. Original jsonl/adapter left in place.

## Build command (verbatim, successful)

```
timeout 7800 hpc -c 4 -m 32gb -t 02:00:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld HF_HOME=/scratch/n12194778/hf PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -u -m sidekick.training.matched_sft --mode sft_b_plus --campaign-root /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 --split train --out /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl --no-strip-interventions'
```

Job `25574101.aqua` Exit_status 0, walltime 01:23:32. [OBSERVED `/home/n12194778/.hpc-spool/20260920-213856-1565089.out` resources_used / Exit_status]

First attempt `25573230.aqua` used original `-t 00:30:00`, killed walltime 1813>1800, no jsonl. [OBSERVED `/home/n12194778/.hpc-spool/20260920-210700-1073700.out`] Retry added `-u` and 02:00:00 only.

## Step 1 numbers

1. New `wc -l` = **497**. [OBSERVED `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl`]
2. New `grep -c INTERVENTION:` = **267** (>0). [OBSERVED same]
3. Original `grep -c INTERVENTION:` = **0**. [OBSERVED `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl`]
4. `intervention_in_context` (`DROP_INTERVENTION_LEAK`): original **0** (key absent; only `correction_no_intervention`: 3); new **0** (same). Episode difference **0**; both `n_sequences`=497, `n_correction_sequences`=267. [OBSERVED both `*.jsonl.manifest.json` dropped_counts / n_sequences] New `intervention_mode`=`retain`. [OBSERVED iaware `.manifest.json`] Leak drop is `if strip_interventions and mark`; strip already left 0 leaks, so retain did not add episodes. [OBSERVED `src/sidekick/training/matched_sft.py:445-447`]

## qsub (verbatim)

```
qsub -v DATA_JSONL=/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_iaware_20260920.jsonl,ADAPTER_OUT=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b,BASE_MODEL=ibm-granite/granite-4.2-8b scripts/pbs/train_sft.pbs
```

## Train

- job **25576173.aqua**, Exit_status **0**, walltime **02:11:15** (stime 23:05:30, mtime 01:16:49, gpu1n009). [OBSERVED `qstat -xf 25576173`]
- dry-run exit=0 23:08:22; full training exit=0 01:16:45. [OBSERVED `campaign/workers/logs/train_sft.out:59,:195`]
- `OUT/manifest.json`: hyperparameters epochs=2.0 lr=0.0001 r=64 seed=42 (file-level) max_length=32768 effective_batch=8 bf16=true; `n_sequences`=479; `n_rows_in`=497; `data_sha256`=`f2f439d9a24df8e1ac3ca5f94a4f0360aeb23e7564597a082f26dbaf5c77d066` (matches jsonl `sha256`); `base_model`=`ibm-granite/granite-4.2-8b`. [OBSERVED `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b/manifest.json`] Original adapter still `n_sequences`=479 `data_sha256`=`e557657e…`. [OBSERVED `…/sft_b_plus_granite8b/manifest.json`]

## Resume

Done. Do not resubmit. If STATUS is the only missing piece, rewrite this file from the artifacts above; do not retrain.
