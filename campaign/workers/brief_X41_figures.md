# Brief X41 — the paper's figures, generated from report JSON only (F6)

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Create your files within your first three actions, then iterate with tests.** Write a STATUS file at
every milestone so a fresh session can resume. **Do NOT commit. Do NOT submit jobs.** Claude runs the
generator in PBS; you write the code and its unit tests.

## Why

Every number in the thesis has a row in `docs/claims_ledger.md` naming a report JSON and a key. The
figures must be generated **from those same JSON files, by key**, never from numbers retyped into the
plotting code. A figure whose value was transcribed by hand is a number without a ledger row, and the
project's rule is that no such number may appear. The generator therefore takes the ledger's paths and
keys as its input contract, and a manifest records which key fed which mark.

## The file

`scripts/analysis/figures.py`, matplotlib, **`matplotlib.use("Agg")` before any pyplot import** — this
runs headless in a PBS job with no display. No seaborn, no network, no font downloads.

**CLI:** `--results-dir campaign/results --out-dir paper/figures --manifest paper/figures/figures_manifest.json
[--only <fig_id>] [--dpi 200]`. Vector `.pdf` for every figure plus a `.png` at `--dpi` for quick viewing.

**Refuse to run** if `--out-dir` resolves under `/scratch/n12194778/sidekick/results/` or contains
`test_normal` / `test_challenge`. Copy `validate_output_path()` from `scripts/analysis/j13_mechanism.py`.

**Fatal, not silent** — this is the project's standing failure mode: if a named report file is missing, or
a named key is absent, or a series ends up with zero points, `raise SystemExit` naming the figure, the
file and the key. Never draw an empty axis and never substitute a default. `--only` may skip a figure, but
a figure that runs must be complete.

## The figures

**F1 · The depth curve, both receivers.** `goal_pass` against handoff depth m for the tailored receiver
(`hj12_prefix_m{2,4,6,7,8,9,10,11}_20260923`) and the untailored receiver
(`hj13_prefix_zs_m{6,9,11}_20260923`), with clustered CI bands. Horizontal reference lines for the
**two ceilings, each labelled with its cap**: cap-25 0.8284 and cap-81 0.7637 (CEIL-07/CEIL-08 require the
cap to be named wherever a ceiling appears). Mark the plan-only floor 0.7181 and the executor-alone floor
0.5289. Shade the registered 7.00 pp non-inferiority margin below the ceiling being compared against.
**Do not draw a breakpoint marker**: the registered threshold test S3 did not pass and no threshold
location is claimed (F1-RESULT-04). A caption line must carry that wording.

**F2 · The two channels at matched budget.** `goal_pass` against non-cached planner tokens per episode,
one point per arm, advice arms and prefix arms in different marks: `executor_alone`, `plan_only`,
`advise_fixed_k_{3,10}`, `advise_fixed_k_10_fullctx`, `takeover_fixed_k_10`, and the prefix curve. This is
the figure that carries the channel claim, so every advice point must be visibly priced against the prefix
point at the same budget.

**F3 · Tailoring.** The receiver gap (untailored minus tailored) against depth: −4.12 pp at m=6, −0.06 at
m=9, +2.46 at m=11 (TAILOR-01/04/07), with CIs. Add the suffix-adapter arms
(`hj13_prefix_hf_m{6,9,11}_20260923`) as a third receiver once those reports exist; if they do not, skip
them and say so in the manifest rather than failing.

**F4 · Mechanism, two panels.** Left: M1, the cumulative share of the planner's first API uses by position
(MECH-08), with the m=6/9/11 depths marked. Right: M3, the decomposition of each rise into its
handoff-earned and silenced-episode parts as a stacked bar (MECH-10: at m6→m9, 8.55 pp handoff and 1.65 pp
silenced; at m6→m11, 9.19 and 6.00). The right panel is the figure that answers "the rise is by
construction", so label the handoff share as a percentage on the bar.

**F5 · The second family.** Qwen3-8B zero-shot against granite zero-shot over depth, each against its own
floor. Read the Qwen floors from the `hj15_executor_alone_zsq` / `hj15_prompt_only_zsq` reports; if those
are absent, **skip this figure and record the reason in the manifest** — the Qwen rise must never be drawn
without its floor.

## Style, so the figures read as one set

One module-level `PALETTE` dict and one `apply_style()` called by every figure. Colour-blind-safe,
distinguishable in greyscale (vary marker and linestyle too, not only hue). Serif font family, 9–10 pt
tick labels, no chartjunk, no title inside the axes (the caption carries it), axis labels with units
("goal pass rate", "non-cached planner tokens per episode"). CI bands at 20 % alpha in the series colour.
Legends inside the axes when they fit. Figure width 3.4 in for single-column, 7.0 in for two-column; say
which each figure is in the manifest.

## The manifest

`paper/figures/figures_manifest.json`: one entry per figure with `{figure_id, file_pdf, file_png,
width_in, column, caption, series: [{label, report_path, json_keys: [...], n_points}], skipped_reason}`.
A reader must be able to go from any mark on any figure back to a report key without opening the code.

## Tests — `tests/unit/test_figures.py`

Use `tmp_path` and scripted minimal report JSON. Do not read real campaign data in tests.

- `test_missing_report_file_is_fatal` — `SystemExit`, no file written.
- `test_missing_json_key_is_fatal` — names the figure and the key.
- `test_empty_series_is_fatal`.
- `test_manifest_lists_every_generated_figure_and_its_keys`.
- `test_skipped_figure_records_a_reason_and_does_not_fail`.
- `test_validate_output_path_refuses_forbidden_locations`.
- `test_no_breakpoint_marker_in_depth_curve` — assert the depth-curve code path draws no vertical
  breakpoint line (guard against re-introducing an unclaimed threshold).

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`, no font or package
  downloads. `timeout` in front of anything you do run. Never background a process.
- Do not edit `src/sidekick/**`, any `scripts/analysis/j8_frontier.py` / `j13_mechanism.py` /
  `hj12_shape.py`, any frozen config, or anything under `docs/prereg_*`. Never read or list
  `test_normal` / `test_challenge`. Never write under `/scratch/.../results/`. **Do not commit.**
- Read `docs/claims_ledger.md` for the report paths and keys. Where a number in this brief disagrees with
  the ledger, **the ledger wins** — and say so in STATUS.

## Return contract

`campaign/workers/STATUS_X41.md`, under 500 words, with a milestone line per figure: the CLI signature;
for each figure the report files and keys it reads; the fatal conditions implemented; the test names; and
the exact `hpc` command Claude should run to generate everything. `[OBSERVED path:line]` / `[INFERRED]` on
every claim. **Do not claim any test passes** — you cannot run them.
