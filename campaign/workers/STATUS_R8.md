# STATUS R8 — crash denominator / mixed populations

**Unit:** R8 — `scripts/analysis/j8_frontier.py`, `tests/unit/test_j8_frontier.py`
**State:** done
**Last update:** 2026-09-20

## Owned files

- `scripts/analysis/j8_frontier.py`
- `tests/unit/test_j8_frontier.py`
- this STATUS

No `.pbs`, no `qsub` of campaign jobs, no git, no writes under `/scratch/.../results/`.

## What changed

Table columns are now `n`, `n_crashed`, `tgc_all`, `tgc_surv`, `gp_all`, `gp_surv`, `calls`, `crash/call%`. [OBSERVED scripts/analysis/j8_frontier.py:954-957]

Headline quality contrast is **all-episodes** (crash scores 0) for every metric. Survivor columns/contrasts use `error_type != 'crash'`. Stated in `POPULATION_PREAMBLE`. [OBSERVED scripts/analysis/j8_frontier.py:61-65, 1020-1024]

Survivor paired contrasts drop a `(task_id, seed)` pair if either side crashed and print `n_pairs_dropped_crash` / `dropped_crash=`. [OBSERVED scripts/analysis/j8_frontier.py:586-588, 616-618, 432-444]

Sign or CI-excludes-zero disagreement prints `CONTRAST DISAGREEMENT`. [OBSERVED scripts/analysis/j8_frontier.py:420]

Zero-crash arms get `all-episodes and survivor populations coincide`. [OBSERVED scripts/analysis/j8_frontier.py:386]
Per-call crash rates are printed; if they differ across arms the report notes they are not constant, without a cause. [OBSERVED scripts/analysis/j8_frontier.py:391-395]

Unlabelled `tgc` / `goal_pass` aliases equal the all-episodes values when the arm is complete (no mixed denominator). [OBSERVED scripts/analysis/j8_frontier.py:545-546]

## Tests (four required)

1. `test_crashed_episodes_split_tgc_all_and_survivors` — 2/8 crash: `tgc_all=0.75`, `tgc_survivors=1.0`, counts and crash/call rate. [OBSERVED tests/unit/test_j8_frontier.py:292-316]
2. `test_survivor_contrast_drops_pairs_where_either_side_crashed` — all-episodes `n_pairs=8` dropped 0; survivors `n_pairs=6` dropped 2. [OBSERVED tests/unit/test_j8_frontier.py:318-339]
3. `test_zero_crashes_populations_coincide` — metrics equal; report says `0 crashes` / `coincide`. [OBSERVED tests/unit/test_j8_frontier.py:342-356]
4. `test_all_vs_survivor_sign_disagreement_is_flagged` — all-episodes diff < 0, survivors > 0, `CONTRAST DISAGREEMENT` in stdout. [OBSERVED tests/unit/test_j8_frontier.py:359-394]

## Suite [OBSERVED hpc job 25564858.aqua]

Command: `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '... python -m pytest tests -q --import-mode=importlib'`

First J8-only pass (25564823.aqua) failed one assertion (`crash_per_call_pct` expected 12.5, obtained 10.0 = 2/20). Assertion corrected to 10.0. [OBSERVED that job's pytest output]

Full suite verbatim final line:

```
437 passed, 1 skipped, 1 warning in 36.16s
```

433 + 4 new tests = 437. [INFERRED]
