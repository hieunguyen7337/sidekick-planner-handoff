# STATUS W-1 — counterfactual branching

**Unit:** W-1. **No campaign runs. No PBS branch job submit.**
**Do not commit.**

## Resume state

- **Milestone:** complete. Tests run. Waiting for orchestrator review/commit.
- **PBS pytest [OBSERVED]:** job `25404879.aqua` → `258 passed, 1 skipped in 10.41s` (zero failures).
- Log: `/tmp/hpc-w1-spool/20260917-103426-1796664.out`

## Owned files (written)

- `src/sidekick/systems/loop.py` — additive `EpisodePrefix`; default path unchanged
- `scripts/setup/branch_counterfactual.py` — resume JSONL, labels, oracle_labels.json
- `src/sidekick/runner.py` — oracle key `"task_id/seed"` + adapter_name for oracle_escalation
- `scripts/pbs/hj6_branches.pbs` — not submitted
- `tests/unit/test_branch_counterfactual.py`
- `campaign/workers/STATUS_W_1.md`
- `/home/n12194778/.claude/jobs/91578989/tmp/w1_tests.sh`

## Notes

- `replay_prefix` k = executed CODE/COMPLETE `[OBSERVED replay.py:66,102]`.
- PYTHONPATH had to include repo root as well as `src` so `tests/unit/test_goal_pass_rate.py` can import `scripts.setup` (collection error otherwise).
