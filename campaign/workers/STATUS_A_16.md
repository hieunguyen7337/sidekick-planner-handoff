# STATUS A16 (U-B1PRE)

- Unit: A16 / U-B1PRE
- State: DONE (2026-09-19)
- Started: 2026-09-19
- Milestone: Prereg frozen. No planner calls. No pilot submission. No edits under src/, configs/, scripts/setup/branch_counterfactual.py, docs/prereg_v1.md, campaign/RUNS.md.
- Owned files:
  - docs/prereg_b1_pilot.md
  - campaign/workers/A16_B1_PREREG.md
  - campaign/workers/STATUS_A_16.md (this file)
  - campaign/workers/scratch_A16/ (point list, PREFLIGHT helper, orchestrator wrapper — not executed as a rollout)
- PREFLIGHT (job 25463680.aqua, collect_jobs only): 1600 branches × 81 = 129600 projected; cap proposed 10000.
- Point sample: 200 keys, seed 20260916, sha256 4ec6fa2733a141da4335240c215b605ff466e2d85a0a0f7ce55179a6ef5b1017 (job 25463506.aqua).
- pytest (job 25463681.aqua): 406 passed, 1 skipped, 1 warning in 38.76s.
- Do not commit. Do not submit. Orchestrator runs after quota reset (~21:13).
