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

## W-1b — focal estimand (2026-09-17)

**No campaign runs. Do not submit `hj6_branches.pbs`. Do not commit.**

### Resume state

- **Milestone:** code+tests done. Waiting for orchestrator review/commit.
- **PBS pytest [OBSERVED]:** job `25405174.aqua` → `2 failed, 284 passed, 1 skipped in 12.45s`.
- Log: `/tmp/hpc-w1b-spool/20260917-111025-3036935.out`
- Both failures are W-3 `tests/unit/test_matched_sft.py` (not owned; not edited). Every W-1b test in `test_branch_counterfactual.py` passed on that run.

### Owned files (W-1b)

- `src/sidekick/systems/loop.py` — `EpisodePrefix.inject_correction` / `skip_review_at_start` / `local_eval_step`; `sampling_seed`
- `src/sidekick/agents/executor.py` — vLLM `seed` payload; `MockExecutor.last_seed`
- `scripts/setup/branch_counterfactual.py` — 4-arm focal design, δ-band, CRN, resume key
- `scripts/pbs/hj6_branches.pbs` — walltime 10:00, codex preflight, resume `(point, condition, branch_seed)`. Not submitted.
- `tests/unit/test_branch_counterfactual.py`
- `/home/n12194778/.claude/jobs/91578989/tmp/w1b_tests.sh`

### Objections (implemented anyway where noted)

- `allow_executor_ask=False` kept: the brief named the scheduled reviewer, not ASK. ASK would add unbudgeted hosted calls.
- Injected treated correction is not charged as a planner call (no `correct()`).
- Local GPR if the episode ends before the next tick reuses the terminal evaluate rather than a second call.
- W-3's failing remask tests were left untouched (file ownership).
