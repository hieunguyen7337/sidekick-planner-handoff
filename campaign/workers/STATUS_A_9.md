# STATUS A9 / A9b — J7 threshold re-spec against attenuation ceiling

Unit: A9b (U-J7 re-issue)
Started: 2026-09-19
State: COMPLETE

## Resume state
- Analysis is in `campaign/workers/A9_THRESHOLD.md`.
- Numbers: `campaign/workers/scratch_A9b/a9_ceiling_out.json`.
- Job `25454021.aqua` exit 0 on `cpu1n040`. Log:
  `/home/n12194778/.hpc-spool/20260919-021228-2979767.out`.
- First job `25453926.aqua` crashed on float-band uniqueness; fixed; not used as a result.
- `docs/prereg_v1.md` was **not** edited. Proposed wording is in A9_THRESHOLD.md §5.
- No git. No GPU. No planner. No src/configs/scripts/RUNS.md/PLAN.md/HEAVY_JOBS.md edits.

## Finding (one line)
√0.45 ≈ 0.67 is a correlation, not an AUROC ceiling. Label-noise ceiling on J7's
tails is ~0.93–0.96. Fitted 0.5917 is genuinely weak against that ceiling (~0.21
of the gap), near the feature mush (~0.60 univariate), and a thin CI that still
covers 0.50–0.70. Do not lower 0.65/0.70 after seeing 0.59.

## Files owned
- `campaign/workers/STATUS_A_9.md` (this)
- `campaign/workers/A9_THRESHOLD.md`
- `campaign/workers/scratch_A9b/a9_ceiling.py`
- `campaign/workers/scratch_A9b/a9_ceiling_out.json`

## Blockers
- None. Orchestrator owns whether to apply §5 to `docs/prereg_v1.md`, and
  whether the written original is 0.70 or 0.65.
