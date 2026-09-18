# STATUS_W_25

**Task:** brief_W25_substitution — dose-response of Δ / `needed` on later untreated reviews
**Status:** DONE (2026-09-18)
**Ownership:** only `campaign/workers/scratch_W25/`, `campaign/workers/W25_SUBSTITUTION.md`, this file.

**Analysis only. CPU only. Zero planner calls. Do not modify production code. Do not commit.**

## Resume state

Nothing pending. Report is in `campaign/workers/W25_SUBSTITUTION.md`. Raw log is `campaign/workers/scratch_W25/w25_out.txt`.

## Execution

- Script: `campaign/workers/scratch_W25/substitution.py` (W-24 `load`/`complete`/`SEEDS`; event-log `n_later`; paired sign-flip on `n_later = 0`).
- PBS job **25447958.aqua** on `cpu1n040`, finished after 70s, ngpus=0 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:1-12]`.
- Permutation seed **20260918**, N_PERM=10000 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:13]`.
- Interpreter `/scratch/n12194778/sidekick/env/bin/python` (numpy 2.3.5) inside `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00`.
- Untreated logs: train 1588/1588 opened, 0 missing, 0 unreadable; dev 1328/1328 opened, 0 missing, 0 unreadable `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:469-470]`.
- No production/importable code touched; pytest not run. No `/scratch/.../results/` writes. No `codex`. No git.

## Pointers

- **`n_later = 0` subset: train 175/397, dev 91/332** `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:89]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:310]`.
- Event vs proxy: train 1588/1588 agree; dev 1327/1328 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:78]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:299]`.
- Train `n_later = 0` ceiling fraction 95/175; `3+` is 1/47 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:116]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:122]`.
- Train Spearman `n_later` vs Δ: ρ = −0.1634, perm p = 7/10000; dev ρ = +0.0949, perm p = 838/10000 `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:92-93]` `[OBSERVED campaign/workers/scratch_W25/w25_out.txt:313-314]`.
