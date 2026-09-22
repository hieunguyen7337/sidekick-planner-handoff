# X49 — two new figures for the two results that landed tonight

## Goal

Add **F7** and **F8** to `scripts/analysis/figures.py`, with tests, following exactly the
conventions the existing F1–F6 already establish. Done means: both figures render to PNG and PDF
under `paper/figures/`, both appear in `paper/figures/figures_manifest.json`, and
`tests/unit/test_figures.py` passes with new tests covering both.

Do **not** change F1–F6, `F1_DRAW_MARGINAL_BANDS`, `PALETTE`, `apply_style`, `save_figure`,
`load_report_json`, `get_nested_key` or `validate_output_path`. Read them and reuse them.

## Files in scope

- `scripts/analysis/figures.py` — add two generator functions and register them in `run_figures`
- `tests/unit/test_figures.py` — add tests
- nothing else

## F7 — the narrated control depends on the receiver

**What it shows.** Narrated minus executed `goal_pass`, in pp, as a function of prefix depth
m ∈ {6, 9, 11}, one series per receiver, with scenario-clustered 95% CI error bars, and a
horizontal dashed line at 0. This is the figure for the claim that receiver tailoring is what lets
a *description* of the planner's actions substitute for having *executed* them.

**Data — untailored series**, from `campaign/results/hj16_narrated_curve_zs_20260923.report.json`:

| m | key under `contrasts` |
|---|---|
| 6 | `goal_pass_all_narrated_m6_minus_executed_m6` |
| 9 | `goal_pass_all_narrated_m9_minus_executed_m9` |
| 11 | `goal_pass_all_narrated_m11_minus_executed_m11` |

**Data — tailored series**, from `campaign/results/hj16_narrated_curve_bplus_20260923.report.json`:

| m | key under `contrasts` |
|---|---|
| 6 | `goal_pass_all_narrated_t_m6_minus_executed_t_m6` |
| 9 | `goal_pass_all_narrated_t_m9_minus_executed_t_m9` |
| 11 | `goal_pass_all_narrated_t_m11_minus_executed_t_m11` |

From each contrast object read `diff_pp` (float) and `ci95_pp_scenario` (a two-element
`[lo, hi]` list). Error bars are `diff_pp - lo` and `hi - diff_pp`. **Do not recompute anything.**
Every number on this figure must come from these keys via `get_nested_key`.

**Expected values, for your own sanity check** — if what you read disagrees with these, stop and
say so in STATUS rather than drawing it:

- untailored: −6.96 [−13.67, +0.63], −1.69 [−7.10, +4.16], −6.58 [−9.98, −3.64]
- tailored: −2.51 [−8.68, +3.41], −1.84 [−6.76, +2.68], −0.49 [−4.10, +3.21]

**Caption must say**, in your own words but carrying all of it: values below zero mean execution
beat narration; the only contrast whose interval excludes zero is the untailored receiver at
m = 11; and the difference *between* the two series is **not** tested here, because six paired
contrasts are not a difference-in-differences.

## F8 — advice does not reach the action channel even when bought above its price

**What it shows.** A cost/quality scatter: x = non-cached planner tokens per episode (log scale),
y = `goal_pass`, one labelled point per arm, with the two advice arms visually distinguished from
the two prefix arms (use `PALETTE`; do not invent a new colour scheme).

**Quality**, from `campaign/results/hj13_advice_at_price_20260923.report.json`, key
`arms.<arm>.goal_pass_all` for arms `advise_k1_fullctx`, `advise_k10_fullctx`, `prefix_m9`,
`prefix_m11`.

**Cost**, from `campaign/results/hj13_advice_at_price_cost_20260923.report.json`, keys
`arms.<arm>.noncached_tokens_per_episode` and `arms.<arm>.hosted_calls_per_episode`, same four
arm names.

**Expected values** — again, stop if they disagree:

| arm | goal_pass | tokens/ep | calls/ep |
|---|---|---|---|
| `advise_k10_fullctx` | 0.7339 | 49,819 | 2.46 |
| `advise_k1_fullctx` | 0.6630 | 1,414,410 | 19.02 |
| `prefix_m9` | 0.7852 | 357,448 | 9.77 |
| `prefix_m11` | 0.8098 | 443,361 | 11.25 |

Annotate each point with its hosted calls per episode. **Caption must say** that advice reviewed
at every step spends 3.2× the tokens and 1.7× the hosted calls of `prefix_m11` and still scores
14.68 pp lower, and that this was the registered H2 test
(`docs/prereg_h2_advice_at_price_20260923.md`).

## Constraints

- Match the surrounding code: same typing style, same `Fatal [FX]:` error idiom, same manifest
  entry shape as F1–F6 (look at what `generate_f6_narrated_vs_executed` returns and mirror it).
- A missing report file or a missing key is a **fatal error**, never a silently skipped figure or
  a drawn zero. Reuse `load_report_json` and `get_nested_key` exactly as F1–F6 do.
- Figures are read at full size by a human. Legends must not cover data points; F4's left panel
  and F6's right panel both currently have that defect, so do not reproduce it.
- BLAS pinned to one thread. Prefix every command with `timeout`.
- **No `python`, `pip`, `pytest`, `tar`, `rsync` or `ffmpeg` directly on `aquarius01`** — it is a
  login node. Run compute in a job:
  `env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-x49-spool timeout 1800 hpc -c 8 -m 32gb -t 00:25:00 bash -lc '<cmd>'`
  with `PYTHONPATH=src:.` and the venv python at
  `/scratch/n12194778/sidekick/env/bin/python`.
- **Do NOT submit any `qsub` job.** Claude submits those.
- Do not touch anything under `/scratch/.../results/`, any `docs/prereg_*.md`, or
  `docs/claims_ledger.md`.
- Do not read, list or load any `test_normal` or `test_challenge` data.

## Return contract

Write `campaign/workers/STATUS_X49.md` containing:

1. What you changed, file by file, with line numbers.
2. The **exact** command you ran for the tests and its **verbatim** last 10 lines of output.
3. Every number you put on either figure, each tagged `[OBSERVED <report path>: <key>]`.
   A number you could not source from a key is a defect — say so rather than drawing it.
4. Anything you could not finish, explicitly. **If you did not run the tests, say "TESTS NOT RUN"**
   — do not describe what you expect them to do.

Keep the report under 40 lines.
