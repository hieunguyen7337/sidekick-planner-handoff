# Brief X33c — the mechanism markdown renderer crashes on a None value

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** One small fix and one test. Make
your first file edit within your first three actions.

## What happened

`scripts/analysis/j13_mechanism.py` (X33b) ran to completion in PBS for both receivers and wrote
`campaign/results/hj13_mechanism_{tailored,zeroshot}_20260923.report.json`, then crashed while
rendering the markdown:

```
File ".../scripts/analysis/j13_mechanism.py", line 736, in generate_markdown_report
    f"{data.get('error_rate_on_handoff', 0.0):.2%} | {data.get('share_first_error_at_step_1', 0.0):.2%} | "
TypeError: unsupported format string passed to NoneType.__format__
```

`dict.get(key, 0.0)` returns the stored `None` when the key is present with value `None`, so the
default never applies. That happens for an arm whose M2 population is empty (no handoff episode
recorded an error, or no handoff episodes at all), where the measurement stores `None` on purpose.

## Fix

1. In `generate_markdown_report` (and anywhere else in that file that formats a value with `:.2%`,
   `:.3f`, `:.1f` etc. — grep for `:.` inside f-strings), render `None` as the literal string `n/a`
   rather than substituting 0.0, which would misreport an empty population as a zero rate. A tiny
   helper `_fmt(value, spec)` returning `"n/a"` for `None` is the right shape. Do not change what the
   measurements compute or what the JSON contains.
2. Make the markdown step non-fatal to the JSON: it already writes the JSON first; keep that order.
3. Add `test_markdown_renders_none_as_na` to `tests/unit/test_j13_mechanism.py`: build a minimal
   report dict in which one arm's M2 entry has `error_rate_on_handoff: None` and
   `share_first_error_at_step_1: None`, call `generate_markdown_report`, assert it returns a string
   containing `n/a` and does not raise.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Never background a
  command. Do not edit anything except `scripts/analysis/j13_mechanism.py` and
  `tests/unit/test_j13_mechanism.py`. Read-only on `/scratch/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X33c.md`, under 150 words: the hunk before/after with line numbers, every
other f-string you changed (path:line), the test name. `[OBSERVED path:line]` / `[INFERRED]` tags.
**Do not claim any test passes.**
