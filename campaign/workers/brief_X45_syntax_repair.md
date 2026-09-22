# Brief X45 — one-line syntax repair in `j12_cost_axes.py` (it currently will not import)

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**ONE FILE, ONE LINE. Do NOT run `hpc`, `qsub`, `pytest`, `python`. Do not commit.** Make the edit in your
first action.

## The defect

`scripts/analysis/j12_cost_axes.py` fails to parse:

```
File ".../scripts/analysis/j12_cost_axes.py", line 588
    """Generate summary Markdown report."""
                                        ^
SyntaxError: unterminated triple-quoted string literal (detected at line 710)
```

Line 588 is **not** the real fault. The module docstring's **opening** `"""` was replaced by a `#`
comment, leaving its closing `"""` orphaned. Current lines 1-12:

```python
#!/usr/bin/env python3
# Cost axes analysis (Brief X40 Unit A / X44): noncached tokens, provider USD, hosted calls.

Evaluates whether the ordering of arms and non-inferiority conclusions survive
under three distinct cost currencies:
1. noncached_tokens_per_episode (standard non-cached token convention)
2. usd_per_episode (provider-priced dollars including cache billing)
3. hosted_calls_per_episode (n_planner_calls from result.json)

Also reports local_gpu_usd_per_episode as an assumption, not a measurement.
"""
from __future__ import annotations
```

Lines 4-10 are bare prose with no opening quote, and the `"""` on line 11 therefore *opens* a string
instead of closing one. That string runs to the next `"""` at line 90, which shifts every subsequent
docstring delimiter by one and leaves the one at 588 unterminated. A count confirms it: the file contains
**19** occurrences of `"""`, an odd number.

## The fix

Change line 2 from a comment into the docstring opener, so line 2 opens and line 11 closes:

```python
#!/usr/bin/env python3
"""Cost axes analysis (Brief X40 Unit A / X44): noncached tokens, provider USD, hosted calls.
```

Change nothing else. Do not touch line 11, the prose lines, or any other line. After the edit the file
must contain an **even** number of `"""` occurrences — check with `grep -o '\"\"\"' scripts/analysis/j12_cost_axes.py | wc -l`
and report the number.

## Constraints

`aquarius01` is a login node: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Do not edit any other file.
Never write under `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X45.md`, under 120 words: the before/after of line 2, and the triple-quote count
after your edit. `[OBSERVED path:line]` on every claim. **Do not claim the file parses** — you cannot run
Python.
