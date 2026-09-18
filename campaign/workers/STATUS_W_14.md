# STATUS W-14 — pass the planner prompt on stdin, not in argv

**Unit:** W-14. **No live `codex` call. No GPU job. Do not commit.**
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Resume state

- **Milestone:** complete. Tests run. Waiting for orchestrator review/commit.
- **Old-code regression [OBSERVED]:** job `25422103.aqua` → `test_huge_prompt_round_trips_via_stdin` FAILED `OSError: [Errno 7] Argument list too long`. Log: `/home/n12194778/.hpc-spool/20260918-125458-2725950.out`
- **New-code named tests [OBSERVED]:** job `25422161.aqua` → 4 passed including `test_huge_prompt_round_trips_via_stdin`. Log: `/home/n12194778/.hpc-spool/20260918-130042-2794589.out`
- **Full suite [OBSERVED]:** job `25422149.aqua` → `339 passed, 1 skipped, 1 warning in 21.20s` (zero failures). Log: `/home/n12194778/.hpc-spool/20260918-125925-2779678.out`

## Owned files (this unit)

- `src/sidekick/agents/planner.py` — `build_codex_argv` dropped `prompt`; `_invoke` writes it with `input=prompt` at `:409`
- `tests/integration/test_codex_planner.py`
- `campaign/workers/STATUS_W_14.md` (this file)

## Notes

- stdin delivery: `src/sidekick/agents/planner.py:409` (`input=prompt`, `encoding="utf-8"`). [OBSERVED src/sidekick/agents/planner.py:409]
- Baseline to match or beat was 335 passed / 1 skipped; this unit added 4 tests. [OBSERVED campaign/workers/brief_W14_argv.md:79]
