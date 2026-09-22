# STATUS_X33c

Fix applied with `_fmt` rendering `None` as `n/a` [OBSERVED scripts/analysis/j13_mechanism.py:692-698]:
```python
# Before [OBSERVED scripts/analysis/j13_mechanism.py:734-738]
f"{data.get('error_rate_on_handoff', 0.0):.2%} | {data.get('share_first_error_at_step_1', 0.0):.2%} | "
# After [OBSERVED scripts/analysis/j13_mechanism.py:743-747]
f"{_fmt(data.get('error_rate_on_handoff'), '.2%')} | {_fmt(data.get('share_first_error_at_step_1'), '.2%')} | "
```

Other formatted f-strings updated with `_fmt`:
- `scripts/analysis/j13_mechanism.py:726`
- `scripts/analysis/j13_mechanism.py:732`
- `scripts/analysis/j13_mechanism.py:743-747`
- `scripts/analysis/j13_mechanism.py:757-760`
- `scripts/analysis/j13_mechanism.py:897-903` (non-fatal try/except)

Added test `test_markdown_renders_none_as_na` [OBSERVED tests/unit/test_j13_mechanism.py:295-356].
