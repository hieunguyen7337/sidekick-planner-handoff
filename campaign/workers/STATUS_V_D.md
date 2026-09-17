# STATUS V-D — sft_b_plus correction dataset

Unit: V-D. NO TRAINING. Dataset + tests only.

## Resume state

- [x] Read brief, SEAM_CONTRACT, existing `sft_data.py` and tests
- [x] Implement `build_correction_dataset` + `build_sft_b_plus` in `src/sidekick/training/sft_data.py`
- [x] Unit tests in `tests/unit/test_sft_correction.py`
- [x] Write `vd_tests.sh` and `vd_build.sh`
- [x] pytest via PBS job 25402186.aqua: **243 passed, 1 skipped in 11.88s**
- [x] Dataset PBS job 25402187.aqua: `data/interim/sft_b_plus.jsonl` + `.jsonl.manifest.json`
- [x] Final STATUS + return contract

## Rebuild command

```
timeout 2400 env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-vd-spool hpc -c 4 -m 32gb -t 01:00:00 bash /home/n12194778/.claude/jobs/91578989/tmp/vd_build.sh
```

One-liner inside the job:

```
python -m sidekick.training.sft_data --mode sft_b_plus \
  --campaign-root /scratch/n12194778/sidekick/results/hj2b_planner_train_20260916 \
  --correction-campaign-root /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 \
  --split train --out data/interim/sft_b_plus.jsonl
```

## Measured (PBS 25402187)

- teacher 196, correction 495, combined 691 sequences
- unrepresentable 0; dropped 76 (74 teacher_unsolved + 2 correction_no_intervention)
- 495/495 interventions forced; 0 ask events; 0 ASK_PLANNER correction targets
- 0 `INTERVENTION:` substrings in the jsonl
- percentiles p50=17439 p90=27439 max=66700 (granite-4.2-8b)
- sha256 `0ba96a9a00705da977d6b37570ed5e59d24f2582c3e4ec4197e56acf884fa591`

## Notes / objections

- Manifest path follows the existing writer: `out_jsonl + ".manifest.json"` → `sft_b_plus.jsonl.manifest.json`, not `sft_b_plus.manifest.json`.
- `sft_lora.py` is outside this unit. It still labels every assistant turn. Correction rows set `meta.supervise_last_assistant_only`. Tests remask via `remask_to_message_index`.
- `_check_budget` uses one full encode when length ≤ 32768 (same first branch as `tokenize_and_mask`); over-budget still calls `tokenize_and_mask` / `fit_messages_to_budget`. First dataset job (25402070) hit `timeout 2400`.

Do not: train, YAML, PBS scripts, runner.py, git.
