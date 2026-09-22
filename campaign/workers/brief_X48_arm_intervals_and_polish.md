# Brief X48 — per-arm intervals for F1's bands, plus two figure collisions

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Files in scope: `scripts/analysis/hj12_shape.py`, `tests/unit/test_hj12_shape.py`,
`scripts/analysis/figures.py`, `tests/unit/test_figures.py`. Nothing else.

**Do NOT run `hpc`, `qsub`, `pip`, `tar`, `rsync` or `ffmpeg`, and do not submit any job.** `aquarius01`
is a login node. Claude submits the analysis re-run and the figure regeneration afterwards; your job is
the code and the unit tests only. Run tests through `/scratch/n12194778/sidekick/env/bin/python` with
`timeout 600` in front. Do not commit. IGNORE `.claude/worktrees/` and `.git/`.

## Unit 1 — the real one: per-arm bootstrap intervals in the shape report

F1 was asked for 95 % confidence bands and could not get them, because the shape report's per-arm block
carries only `complete_n, error_types, goal_pass_all, label, m, n, n_handoff_occurred,
n_silenced_executor_n_calls_eq_0, tgc_all` — **no interval fields at all**. Verified against
`campaign/results/hj13_shape_post_guard_holm_20260923.report.json`.

Add a **one-sample** clustered percentile bootstrap per arm, and write it into each arm's block as
`goal_pass_all_ci95` and `tgc_all_ci95`, each a two-element `[low, high]` on the **rate** scale, plus
`goal_pass_all_ci95_pp` / `tgc_all_ci95_pp` on the percentage-point scale.

Match the conventions the paired contrasts in this repo already use, and read them out of the existing
code rather than guessing: **10,000 draws, seed 20260915, resample by scenario cluster** with the task
clustering also recorded if the existing helper makes that cheap. Reuse whatever bootstrap helper
`hj12_shape.py` or its neighbours already provide — **do not write a second bootstrap implementation.**

⚠ These are **per-arm** intervals for plotting. They are *not* a significance test and must not be used
as one: MULT-01 established that no adjacent-depth step is significant, and two overlapping per-arm
bands are not evidence about a paired contrast. Put that warning in the function's docstring.

Tests: that every arm block gains all four keys; that the interval brackets the point estimate; that the
seed makes it reproducible across two calls; and that an arm with a single cluster does not crash.

## Unit 2 — F1 bands

With Unit 1's keys present, draw the shaded 95 % band per receiver in `f1_depth_curve` from
`arms.<arm>.goal_pass_all_ci95`. Keep the existing honest fallback: if the keys are missing, draw the
point without a band and record that in the manifest. **`test_no_breakpoint_marker_in_depth_curve` must
keep passing** — no breakpoint marker, ever.

F1's legend currently also sits over the executor-alone floor line on the right-hand side. Move it clear.

## Unit 3 — two collisions I can see and you cannot

- **F4, left panel.** The annotations `m = 9 (78.3%)` and `m = 11 (86.6%)` are drawn on top of the curve
  and the line strikes through the text. Offset the labels so no text touches the plotted line.
- **F6, right panel.** The legend box covers the grey "One-plan floor" triangle at TGC (it sits near
  y = 0.05, behind the legend). Move the legend, or place it outside the axes as F4 now does, so every
  plotted marker is visible.

Change no value in either figure.

## Return contract

`campaign/workers/STATUS_X48.md`, under 200 words: the new key names, the bootstrap helper you reused
and where it lives, the new test names and the pass count for `tests/unit/test_hj12_shape.py` and
`tests/unit/test_figures.py`, and what you moved on F1/F4/F6. Tag claims `[OBSERVED path:line]` or
`[INFERRED]`. **Do not claim any figure looks right — you cannot see it.** If you regenerate figures,
say so; the bands will be absent until Claude re-runs the shape analysis, and that is expected.
