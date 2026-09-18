# STATUS A15 (U-J8A)

**Unit:** A15 — analyse J8a baselines (`executor_alone`, `sft_plan`)
**State:** done
**Last update:** 2026-09-19

## Progress
- STATUS written.
- `j10_report.py` run **unmodified** on the two real J8 campaigns (job `25463395.aqua`).
  Exit 1: missing J10 arms + no `k_matched`. Both provided arms inventoried complete.
  `contrasts: {}`.
- Helper `campaign/workers/scratch_A15/paired_j8a.py` computed
  `sft_plan − executor_alone` via `paired_diff(resample="task")`.
- `executor_alone` planner calls exactly zero (result.json + events). `n_broken=0`
  independently on both arms.
- Report: `campaign/workers/A15_J8A.md`. Ledger: `campaign/RUNS.md` §7 J8a.

## Blockers
- none

## Notes
- Analysis only. No GPU jobs, no arm re-runs, no planner calls, no writes under
  `/scratch/.../results/`, no edit to `j10_report.py`.
- Did not commit.
