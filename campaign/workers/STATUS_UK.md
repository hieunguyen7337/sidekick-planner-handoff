# STATUS_UK — partial-credit SFT data (U-K)

## Done — all five items
- [x] Item 1: `min_goal_pass_rate` keyword-only param in `build_sft_dataset`
      (src/sidekick/training/sft_data.py:422); `DROP_BELOW_GOAL_PASS_RATE` (:34);
      None→`unsolved`, below-threshold→`below_goal_pass_rate` (:488-507).
- [x] Item 2: terminal-COMPLETE assistant turn removed for partials only
      (:516-536); solved trajectories untouched.
- [x] Item 3: manifest accounting (:616-625); record provenance in
      `meta.source`/`meta.goal_pass_rate` (:557-558); `--min-goal-pass-rate` CLI (:641).
- [x] Item 4: six tests appended to tests/unit/test_sft_data.py (lines 503-588).
- [x] Item 5: preview built → data/interim/sft_b_partial_preview.jsonl (+.manifest.json).

## Results
- Suite: `179 passed, 1 skipped in 8.19s` (baseline 168 + 6 new + 5 pre-existing
  additions from other units; PBS job 25401605.aqua).
- Preview @ 0.75 (PBS job 25401607.aqua): n_solved=163, n_partial=29,
  n_terminal_actions_removed=23, mean_goal_pass_rate_partial=0.8081,
  histogram unsolved {0.1:5, 0.2:1, 0.3:1, 0.4:5, 0.5:16, 0.7:14, 0.8:18, none:0}.
- Cross-check on the emitted file (PBS job 25401618.aqua): 0 partial records
  contain a COMPLETE-kind assistant turn; 117 solved records end in COMPLETE and
  all 117 have that turn supervised on the label arrays.
- Frozen sft_b.jsonl untouched (mtime 2026-09-16 20:17, before this unit).

## Decisions / notes
- `goal_pass_rate` None (unsolved, threshold set) drops as `unsolved` (no graded
  signal); numeric-but-below-threshold drops as `below_goal_pass_rate`.
- Provenance fields `source`/`goal_pass_rate` go inside each record's `meta`
  (top-level record keys would break the existing `set(line) == {"messages","meta"}` test).
- Histogram: ten 0.1-wide bins keyed "0.0".."0.9" (1.0 counts in "0.9") plus a
  `"none"` key for null rates; counts every in-split unsolved trajectory.
- Terminal detection: parse the last assistant turn with `parse_executor_action`,
  match `kind == "COMPLETE"`; scan backwards because a user OBS turn can follow
  the terminal action.
- [INFERRED] earlier session numbers (133/47/0.628) not re-measured by this unit.
- Preview build writes ONLY data/interim/sft_b_partial_preview.jsonl.

## Resume command
```
timeout 2400 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && PYTHONPATH=src:. APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld HF_HOME=/scratch/n12194778/hf OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python -m pytest tests/unit tests/reproducibility -q 2>&1 | tail -15'
```
(run with nohup + redirect; the tool call itself times out at 30s)

Preview build command:
```
timeout 2400 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && PYTHONPATH=src:. APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld HF_HOME=/scratch/n12194778/hf OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python -m sidekick.training.sft_data --campaign-root /scratch/n12194778/sidekick/results/hj2b_planner_train_20260916 --split train --out data/interim/sft_b_partial_preview.jsonl --min-goal-pass-rate 0.75'
```

## Blockers
- none
