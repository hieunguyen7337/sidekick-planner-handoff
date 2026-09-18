# STATUS_A_11.md — A11 (U-DOC) Status

- **Status**: DONE
- **Worker**: A11 (U-DOC)
- **Files Owned & Modified**:
  - `campaign/workers/STATUS_A_11.md` (this status file)
  - `src/sidekick/agents/verifier.py` (comment reference update only: `loop.py:492-500` -> `loop.py:541-550`)
  - `campaign/RUNS.md` (fixed stale ASK gate citation to `loop.py:816-820`; folded in W-24, W-25, A7, A9, A10, A4-A13 findings)
  - `docs/PLAN.md` (§8 roadmap reordering with paused J5b/`sft_c`, unblocked H2/H3 path, value function dropped from J8 live arms, feature representation diagnosis)
  - `docs/HEAVY_JOBS.md` (J5b paused, J6 recovery demoted, J8 unblocked with 12 configs)
  - `docs/prereg_v1.md` (H2/H3 reachable without `sft_c`, H4 conditional, J7 mathematical retraction of $\sqrt{\rho}$ AUROC bound, resolution of 0.65 vs 0.70 registered value, mandatory reporting rule added with disclosure)
  - `docs/FOLLOWUPS.md` (`hash_match` resolved with A10 off-by-one diagnosis and v3 warning, `verify_configs.py` marked resolved exit 0, feature representation synthesis)

## Milestones & Checklist
- [x] Initialized STATUS_A_11.md
- [x] Inspected source reports (W24, W25, A7, A9, A10, A4-A13) and checked line references
- [x] Updated `src/sidekick/agents/verifier.py` stale comment reference (`loop.py:541-550`)
- [x] Updated `campaign/RUNS.md` (stale citation to `loop.py:816-820`, full results section for W-24, W-25, A7, A9, A10, A4-A13)
- [x] Updated `docs/PLAN.md` (§8 roadmap reordering, value function escalator scope change, representation limit diagnosis)
- [x] Updated `docs/HEAVY_JOBS.md` (J6 recovery demoted, J5b paused, J8 prioritized and unblocked)
- [x] Updated `docs/prereg_v1.md` (H2/H3 reachable without `sft_c`, H4 conditional, J7 mathematical retraction, 0.65 vs 0.70 registered value resolved as 0.70, reporting rule with disclosure)
- [x] Updated `docs/FOLLOWUPS.md` (`verify_configs.py` exit 0, `hash_match` off-by-one resolution and v3 warning, representation synthesis)
- [x] Verified all cross-references (`path:line`) directly in target files

## Constraints Checked
- Zero planner calls invoked.
- Zero PBS jobs submitted.
- No files modified outside ownership list (`campaign/RUNS.md`, `docs/PLAN.md`, `docs/HEAVY_JOBS.md`, `docs/prereg_v1.md`, `docs/FOLLOWUPS.md`, `src/sidekick/agents/verifier.py` (comment only), `campaign/workers/STATUS_A_11.md`).
- No git commands run.
