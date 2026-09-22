# STATUS X26 — registered shape test

Started 2026-09-22. Analysis only. No qsub, no GPU, no git.

## Current

- Amendment appended to `docs/prereg_hj13_shape_20260923.md` (file write, not git) **before** the test.
- Next: `scripts/analysis/hj12_shape.py` + `tests/unit/test_hj12_shape.py`, then pytest and the two reports via `hpc`.

## Missing

- Script, tests, both `campaign/results/hj13_shape_*_20260923.report.json`.
- S1–S3 verdicts, robustness, per-m deltas, SHAPE-04.

Do not treat this STATUS as a finished result.
