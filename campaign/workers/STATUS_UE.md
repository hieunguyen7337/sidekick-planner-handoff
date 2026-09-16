# STATUS_UE — goal-pass rate persistence

## Done

- Added normalized `goal_pass_rate` to AppWorld evaluation, mock evaluation,
  `RunResult`, loop fallbacks, and campaign summaries.
- Added `scripts/setup/backfill_goal_pass_rate.py` with file-order last-
  `run_start` selection, dry-run support, idempotence, and summary counters.
- Added `tests/unit/test_goal_pass_rate.py` covering evaluation normalization,
  `None` exclusion from summary means, and idempotent last-run backfill.
- Did not run the backfill script against any campaign directory.

## Verification blocker

The mandated unit-suite command was attempted twice through `hpc`; both attempts
failed before a PBS job started:

```
hpc: qsub failed: Unknown Host.
qsub: cannot connect to server aqua (errno=15008)
```

No pytest result is available because the scheduler was unreachable.
