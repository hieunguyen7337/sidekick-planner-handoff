# STATUS UA1 — executor must see its own actions

**unit:** U-A1
**state:** done (code written; tests not run — login-node rule)

## done
- New `src/sidekick/protocols/prompts.py`: `EXECUTOR_SYSTEM_PROMPT`, `render_executor_messages`, helper `format_executor_action`.
- `loop.py` executor path now keeps `exec_turns` in parallel with frozen `transcript`; `_executor_messages` deleted.
- New `tests/unit/test_executor_prompt.py` covering the six brief cases.
- Did not touch `runner.py`, `planner.py`, `schemas.py`, `training/`, `scripts/`, `configs/`, or any existing test.

## next (orchestrator)
- Run `tests/unit/test_executor_prompt.py` plus the existing unit suite in a PBS/`hpc` job. Do not run pytest on aquarius01.

## how to resume
- Renderer: `src/sidekick/protocols/prompts.py`
- Wiring: `src/sidekick/systems/loop.py` (`exec_turns`, `render_executor_messages` at `action_from_executor`)
- Tests: `tests/unit/test_executor_prompt.py`
- Planner `transcript.append` strings and planner call sites are unchanged.

## return contract
See the worker's final message.
