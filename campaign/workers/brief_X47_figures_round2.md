# Brief X47 — figure round 2: fix two defects, add the mechanism figure, unblock F5 safely

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Files in scope: `scripts/analysis/figures.py`, `tests/unit/test_figures.py`, and the regenerated outputs
under `paper/figures/`. Nothing else.

**Every value drawn must be read from a report JSON by key and recorded in
`paper/figures/figures_manifest.json`.** Never retype a number into the source. If a key you need is
absent, skip that series and record the reason in the manifest — that behaviour already exists and is
correct; keep it.

**Do NOT run `pip`, `tar`, `rsync`, `ffmpeg`, `qsub` or `hpc`.** `aquarius01` is a login node.
`matplotlib` is already installed in `/scratch/n12194778/sidekick/env` with the `Agg` backend. Run the
generator and the tests **only** through the interpreter at
`/scratch/n12194778/sidekick/env/bin/python`, and put `timeout 600` in front of every invocation. Do not
commit. IGNORE `.claude/worktrees/` and `.git/`.

## The five units

### 1. F4 right panel — legend overlaps the total label
The stacked decomposition panel draws a total label reading `+15.20 pp` that the legend sits on top of.
Move the legend out of the data area (below the axes, or outside on the right with the figure widened)
so neither the label nor any bar is occluded. Do not change any value.

### 2. F1 — add the confidence bands the brief originally specified
`f1_depth_curve` draws both receivers with no interval shading. Add a shaded 95 % band per receiver from
the per-arm interval keys in the same report the points come from. If a given arm has no interval key,
draw its point without a band rather than dropping the arm, and note it in the manifest.
⚠ **The existing `test_no_breakpoint_marker_in_depth_curve` regression test must keep passing.** No
breakpoint marker, ever — MULT-01 established that no single adjacent-depth step is significant.

### 3. F5 — draw the Qwen curve, and invert the guard that currently blocks it
F5 is presently skipped because the Qwen floor reports were absent. They now exist and are **degenerate**:
both floor arms score 0.2481 with TGC exactly 0 and zero successes, and supplying a plan changed the
outcome in no episode. So the floor is a constant of the task set, not a competence baseline (ledger row
QWEN-03).

Therefore **invert the guard**: instead of refusing to draw the curve when the floor is missing, the
generator must refuse to draw a **Qwen floor point or floor line at all**, and must refuse to draw the
curve unless an explanatory annotation is present. Draw:

- the three prefix points m = 6, 9, 11 from `campaign/results/hj15_qwen_curve_20260923.report.json`,
  with 95 % bands if interval keys are present;
- **no floor line, no floor point, no floor-relative arrow or delta label**;
- a mandatory in-figure annotation, wired so the figure cannot render without it, reading substantially:
  *"Floor not shown: both Qwen floor arms score identically and complete no tasks, so no floor-relative
  lift is measurable (QWEN-03)."*
- axis label and title making clear this is a **within-prefix** depth curve for a second executor family.

Add two tests: one asserting no floor series is drawn for F5, one asserting the annotation text is
present. Keep the manifest entry recording which keys fed the three points.

### 4. F6 (new) — the mechanism figure: narrated versus executed
Sources: `campaign/results/hj16_narrated_tailored_complete_20260923.report.json` and
`campaign/results/hj16_narrated_untailored_complete_20260923.report.json`.

Two panels, one per receiver (tailored, untailored). Each shows three arms — one-plan floor, **narrated**
m = 9, **executed** m = 9 — on `goal_pass` and TGC, with 95 % intervals. The point of the figure is that
narrated and executed are indistinguishable while both sit well above the floor, so draw it so a reader
sees the overlap of the narrated and executed intervals immediately.

⚠ On the tailored receiver the narrated-minus-floor `goal_pass` interval **includes zero**. Do not draw
a significance marker on that comparison. Mark significance only where the ledger row (NARR-02) states
the interval excludes zero.

### 5. Regenerate and report
Regenerate every figure to `paper/figures/` at 200 dpi, PNG and PDF, refresh
`paper/figures/figures_manifest.json`, and run the figure tests. Report the pass count.

## Return contract

`campaign/workers/STATUS_X47.md`, under 200 words: which figures regenerated, the new test names and the
pass count, the exact annotation string you put on F5, and anything you skipped with its recorded reason.
Tag every claim `[OBSERVED path:line]` or `[INFERRED]`. **Do not claim a figure looks correct — you
cannot see it.** Report only what the code does and what the tests assert.
