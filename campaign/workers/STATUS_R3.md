# STATUS_R3 — j8_frontier.py

Updated: 2026-09-20 DONE

## Resume here

Unit is complete. No further work unless the orchestrator wants a follow-up.

## Owned files

- `scripts/analysis/j8_frontier.py` (new). Did **not** modify `j10_report.py`; pairing/bootstrap imported from it.
- `tests/unit/test_j8_frontier.py` (new)
- `campaign/workers/scratch_R3/free_arms.json`, `smoke.json` (dry-run JSON; not under `/scratch/.../results/`)
- `campaign/workers/STATUS_R3.md` (this file)

## Observed

- Oracle semantics: **runs free**. Citation: `src/sidekick/runner.py:284`; `src/sidekick/systems/loop.py:623,727`; `src/sidekick/systems/oracle_escalation.py:9-18`; `configs/hj8_oracle_escalation.yaml:37-38`. [OBSERVED campaign/workers/scratch_R3/free_arms.json:5]
- Free-arm dry run (exit 0): executor_alone n=114 TGC 0.1316 goal_pass 0.5289 calls_live 0; sft_plan n=114 TGC 0.4035 goal_pass 0.7000 calls_live 1. [OBSERVED campaign/workers/scratch_R3/free_arms.json:17-49]
- Smoke trees: all 10 `hj8_*_20260919livesmoke_smoke` arms refused (3 rows each, n_broken=3); no quality/calls numbers emitted; exit 1. [OBSERVED campaign/workers/scratch_R3/smoke.json:2-14]
- Unit tests: `11 passed in 0.71s` (job 25558317.aqua).
- Full suite: `433 passed, 1 skipped, 1 warning in 34.98s` (job 25558334.aqua). Brief baseline was 413 passed, 1 skipped; this tree also contains other workers' new tests plus 11 from this unit.

## Blockers

- None. Gated/oracle/fixed_k complete 114-row trees do not exist yet, so F1/headroom/H3 have nothing live to score; the script is ready when those arms finish.
