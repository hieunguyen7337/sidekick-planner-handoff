# STATUS_A_19 — U-J10B j10_report partial-matrix + goal_pass_rate

**Unit:** A19b / U-J10B
**Worker files:** `scripts/analysis/j10_report.py`, `tests/unit/test_j10_report.py`
**Do not commit.** Done. No rollouts, GPU, planner, or `codex`.

## Resume state

Complete. Fresh session should not re-implement.

- `goal_pass_rate` is read from each `result.json` via `optional_float(row, "goal_pass_rate")`.
  Missing/null: drop from the GPR contrast, count `pairs_dropped_missing_field` and
  `n_goal_pass_rate_missing`. Never coerced to 0.0.
- `--partial-matrix`: inventory named `--arm`s only; pairwise TGC + GPR with
  `paired_diff(..., resample="task")`; always stamps `PLUMBING CHECK, NOT A RESULT`;
  skips `missing_arm` / `k_matched_not_supplied` / `fixed_k_k5` alias.
- Full-J10 path still refuses incomplete matrix and missing `k_matched`; contrasts stay `{}`.
- `grep -c goal_pass scripts/analysis/j10_report.py` is 25 (was 0).

## pytest (verbatim)

Job `25481520.aqua` (`tests/unit/test_j10_report.py`):

```
.....................                                                    [100%]
21 passed in 12.38s
```

Job `25481585.aqua` (`tests -q --import-mode=importlib`):

```
413 passed, 1 skipped, 1 warning in 42.39s
```

Baseline was 408 passed, 1 skipped; +5 new tests; never fewer; zero failures.

Spool: `/home/n12194778/.hpc-spool/20260919-115323-3665863.out`
and `/home/n12194778/.hpc-spool/20260919-115528-3697006.out`.

## Notes

- Did not alias `sft_plan` as `sidekick`.
- Did not run `git`.
- `paired_diff` zips unfiltered keys against diffs that skipped Nones
  [OBSERVED scripts/setup/hj1_gate.py:180-207]. `contrast_goal_pass_rate` filters
  to recorded values before calling it. Did not edit `hj1_gate.py`.
- Partial mode is opt-in. Default J10 refusals are unchanged. Passing
  `--partial-matrix` on a complete matrix would skip H1/H2; that is the
  separate mode, not a relaxation of the default.
