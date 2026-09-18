# STATUS_W_24

**Task:** brief_W24_permnull — paired sign-flip permutation null for `f` and oracle-gain statistics
**Status:** DONE (2026-09-18)
**Ownership:** only `campaign/workers/scratch_W24/`, `campaign/workers/W24_PERMNULL.md`, this file.

**Analysis only. CPU only. Zero planner calls. Do not modify production code. Do not commit.**

## Resume state

Nothing pending. Report is in `campaign/workers/W24_PERMNULL.md`. Raw log is `campaign/workers/scratch_W24/w24_out.txt`.

## Execution

- Script: `campaign/workers/scratch_W24/permnull.py` (W-20 `load`/`complete`/`SEEDS`; vectorised paired sign-flip).
- PBS job **25443463.aqua** on `cpu1n040`, exit 0, walltime 5s, 2s CPU, ngpus=0 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:1]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:181-192]`.
- Permutation seed **20260918**, N_PERM=10000 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:6-7]`.
- Interpreter `/scratch/n12194778/sidekick/env/bin/python` (numpy 2.3.5) inside `timeout 900 hpc -c 4 -m 16gb -t 00:20:00`.
- Replicate seeds actually present: **101, 102, 103, 104** for treated and untreated on both splits `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:23-24]` `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:102-103]`.
- Identity `mean(treated)+mean(harm) = mean(untreated)+mean(help)` holds (abs_diff ≤ 3.331e-16) `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:38-41]`.
- No production/importable code touched; pytest not run. No `/scratch/.../results/` writes. No `codex`. No git.

## Pointers

- Train all-complete δ=0.166: `f` = 25/397 inside null; `needless` = 46 above null (0/10000); asymmetry −21, two-sided 52/10000 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:52-59]`.
- Dev all-complete δ=0.166: `f` = 43/332 just above null 97.5th (42), p=204/10000; asymmetry 0, two-sided 10000/10000 `[OBSERVED campaign/workers/scratch_W24/w24_out.txt:131-138]`.
- Contestable tables are labelled post-hoc in the report.
