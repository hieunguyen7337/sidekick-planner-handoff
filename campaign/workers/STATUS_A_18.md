# STATUS A18 (U-B1PRE2) — Symmetric `suppress_next` B1 Prereg Correction

- **Unit:** A18 / U-B1PRE2
- **State:** done (2026-09-19)
- **Files Owned:**
  - `docs/prereg_b1_pilot.md`
  - `campaign/workers/A18_PREREG_SYMMETRIC.md`
  - `campaign/workers/STATUS_A_18.md`
- **Untouched:** `src/`, `configs/`, `scripts/`, `campaign/RUNS.md`, all other `docs/` files.
- **Constraints Maintained:**
  - Zero git operations.
  - Zero rollout / GPU jobs / planner calls / `codex` invocations.
  - No writes to `/scratch/.../results/`.
- **Changes Completed:**
  - Updated `Status:` line in `docs/prereg_b1_pilot.md` to record the 2026-09-19 symmetric fix correction.
  - Updated §1 to specify symmetric suppression across both arms (`scripts/setup/branch_counterfactual.py:1022`), documented the two specification clashes in order (residual ticks and arm asymmetry defect fixed by A17), and synced the estimand quote verbatim with `scripts/setup/branch_counterfactual.py:88-91`.
  - Updated §7 item 4 manipulation check to test both arms separately for loss of tick `t` and verify equal distribution of later reviews, and integrated the A17 empirical residual `n_later` benchmark with length-held-fixed caveat.
  - Updated §8 to reflect that live reviews are reduced in both arms under symmetric suppression.
  - Updated §12 item 1 to reflect symmetric suppression while noting `n_later = 0` is not guaranteed.
  - Hypotheses, decision rule, δ (0.166), hard cap (10,000), spend estimate (6,118), and frozen 200-point list remain byte-unchanged.
