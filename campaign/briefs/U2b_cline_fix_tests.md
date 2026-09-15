# U2b — fix the 13 failing unit tests (owner: Cline, fresh session)

A previous unit wrote these files and reported "54 tests" **without ever running them**. They were then
run on compute node `cpu1n040` (job 25383482) and the real result is:

```
13 failed, 52 passed in 0.79s
```

Your whole job is to make that line read `65 passed` (or whatever the count is once fixed) with **no
failures**, and to have actually run it and pasted the real output.

## The failures, verbatim

```
FAILED tests/unit/test_cost.py::test_fcd_zero_baseline_is_nan - NameError
FAILED tests/unit/test_eventlog.py::test_parse_fenced_code - NameError
FAILED tests/unit/test_eventlog.py::test_parse_code_block_with_nested_fence
FAILED tests/unit/test_eventlog.py::test_parse_ask_planner - NameError
FAILED tests/unit/test_eventlog.py::test_parse_report - NameError
FAILED tests/unit/test_eventlog.py::test_parse_complete - NameError
FAILED tests/unit/test_eventlog.py::test_parse_priority_code_over_ask - NameError
FAILED tests/unit/test_eventlog.py::test_parse_raw_output_untouched_whitespace
FAILED tests/unit/test_eventlog.py::test_parse_error_raises_with_raw - NameError
FAILED tests/unit/test_eventlog.py::test_parse_empty_raises - NameError
FAILED tests/unit/test_eventlog.py::test_parse_ask_planner_empty_reason_ok - NameError
FAILED tests/unit/test_eventlog.py::test_parsed_action_passes_model_validator
FAILED tests/unit/test_schemas.py::test_usage_negative_tokens_rejected - DID NOT RAISE
```

Two distinct causes:

**Cause 1 — missing import (12 of the 13).**
```
    def test_parsed_action_passes_model_validator():
>       a = parse_executor_action("```python\nx = 1\n```")
E       NameError: name 'parse_executor_action' is not defined
tests/unit/test_eventlog.py:188: NameError
```
`tests/unit/test_eventlog.py` and `tests/unit/test_cost.py` use names they never imported
(`parse_executor_action`, and in test_cost.py the one used by `test_fcd_zero_baseline_is_nan`).
Add the imports. **Also move the `parse_executor_action` tests out of `test_eventlog.py` and into
`test_schemas.py`**, where that function lives — they are in the wrong file.

**Cause 2 — a real gap in the schema (1 of the 13).**
```
    def test_usage_negative_tokens_rejected():
>       with pytest.raises(ValidationError):
E       Failed: DID NOT RAISE ValidationError
tests/unit/test_schemas.py:47
```
The test is right and the schema is wrong: `Usage` accepts negative token counts. Negative tokens are
always a bug, and they would silently corrupt every cost total and every displacement ratio. Fix
`src/sidekick/protocols/schemas.py` so all token-count and `n_calls` fields are non-negative
(`Field(ge=0)`), and `latency_s` / `gpu_seconds` likewise. Do not weaken the test.

## Also do these two small things

1. Add a `.gitignore` at the repo root ignoring `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.venv/`,
   `*.egg-info/`. Compiled files are currently landing in the source tree.
2. Re-check the one contract deviation the previous unit recorded: `Usage` and `Event` use
   `extra="ignore"`. Leave the behaviour as it is, but add a one-line comment in the code saying why,
   so a later reader does not "fix" it into `forbid` and break the free-form `raw`/`payload` fields.

## Files you may touch

`src/sidekick/protocols/schemas.py`, `tests/unit/*.py`, `.gitignore`,
`campaign/workers/logs/U2b_STATUS.md`. **Nothing else** — other workers are editing
`src/sidekick/agents/`, `src/sidekick/environments/`, `src/sidekick/systems/`, `scripts/` and `docs/`
right now.

## Constraints

- **Never run Python or pytest on the login node `aquarius01`.** Run tests inside a job:
  ```
  timeout 900 hpc -c 4 -m 16gb -t 00:20:00 /home/n12194778/.claude/jobs/91578989/tmp/run_unit_tests.sh
  ```
  That script already exists and runs the suite with `uv`. Use it.
- Put `timeout <seconds>` in front of every command.
- **Do not run any `git` command.**
- Never print the value of a token or credential.

## Return contract

Finish with at most 12 lines containing **the verbatim final pytest line from a real run** (for example
`65 passed in 0.81s`), the list of files you changed, and the schema change you made. If any test still
fails, say which and why rather than deleting or skipping it. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
