# STATUS A-6 — J8 frontier PBS harness

**Task:** brief_A6_j8_harness — `scripts/pbs/hj8_frontier.pbs`
**Status:** DONE (2026-09-19)
**Ownership:** only `scripts/pbs/hj8_frontier.pbs` and this file. Did not touch `configs/`, `src/sidekick/runner.py`, or `scripts/pbs/hj3_eval.pbs`.

**Do not submit. Do not commit. Zero planner calls. No GPU job.**

## Resume state

Nothing pending. Script written; `bash -n` passed; `shellcheck` was not on PATH.

## Checks

```
bash -n scripts/pbs/hj8_frontier.pbs
# bash -n exit=0
# shellcheck: not available
```

Did not run pytest (nothing importable touched). Did not qsub. Did not invoke `codex`. Did not write under `/scratch/.../results/`.

## Blockers for a future submitter (not this unit)

- J8 YAML files are still absent (`configs/hj8_*.yaml` glob was empty). Another unit owns them.
- `sft_b_plus` adapter dir is not present yet; only `sft_b_plus_granite8b_dryrun` exists under `/scratch/n12194778/sidekick/artifacts/adapters/` [OBSERVED ls 2026-09-19]. Default `ADAPTER_SFT_B_PLUS` is `.../sft_b_plus_granite8b`; `register_lora` will hard-fail until that directory exists.
- `scripts/setup/verify_configs.py` is wired as a job-start gate and currently exits non-zero on this repo (another unit is fixing it). The FATAL line names that script.
- train-sft `25449628.aqua` was running on `gpu_batch_exec` at 00:20 2026-09-19 [OBSERVED qstat]; this unit did not submit against it.
