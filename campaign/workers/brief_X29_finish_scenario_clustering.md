# Brief X29 — finish the statistics repair a dead unit left three tests short

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis only. **Do NOT `qsub` an evaluation, do not touch a GPU.** Two GPU jobs are running; they do
not import the file you are editing. Do not edit `src/`, `configs/` or anything under `scripts/pbs/`.

## What happened

Unit X19 was implementing `campaign/workers/brief_X19_scenario_cluster_and_honest_ceiling.md` — **read
that brief first, it is the specification and it still stands.** The worker's session died partway
through when its model hit a daily quota; it is unavailable for ~22 hours. It left
`scripts/analysis/j8_frontier.py` and `tests/unit/test_j8_frontier.py` in a mostly-working state.

Measured now [OBSERVED `hpc` job, `pytest tests/unit/test_j8_frontier.py`]:

```
3 failed, 42 passed in 11.96s
FAILED tests/unit/test_j8_frontier.py::test_chord_row_reports_scenario_interval
FAILED tests/unit/test_j8_frontier.py::test_exclude_reference_limit_cli_writes_sensitivity_block
FAILED tests/unit/test_j8_frontier.py::test_exclude_reference_limit_without_reference_arm_records_reason
```

Earlier the whole suite failed with `NameError: _attach_scenario_ci`, so treat the file as
half-finished rather than as a clean design you should extend without reading.

## Your job

1. **Read X19's brief and its partial diff** before changing anything. Work out what the previous
   worker intended; the three failing tests describe behaviour that was specified and not delivered.
2. Make those three tests pass **by completing the implementation**, not by weakening the tests. If a
   test encodes a misunderstanding of the spec, say so in STATUS and quote both the test and the
   brief clause — do not silently relax an assertion.
3. Re-check the two requirements X19's brief calls non-negotiable:
   - **Default output is unchanged.** Omitting `--cluster` and `--exclude-reference-limit` must
     reproduce the committed `campaign/results/hj12_unified_frontier_20260922.report.json`
     field-for-field on every pre-existing key. Other reports read this file.
   - Scenario grouping reuses `scenario_of` from `scripts/setup/hj1_gate.py:45-46` (AppWorld ids are
     `<scenario>_<n>`; `x_1`, `x_2`, `x_3` are one scenario). Do not write a second implementation.
4. Run the verification the X19 brief specifies, writing to the paths it names under
   `campaign/results/` — **never `/tmp`**, which is invisible from the login node afterwards.

## Why this matters

The campaign's 57 dev tasks are 19 scenarios of 3 variants. Every interval published so far clusters
on task and therefore treats correlated variants as independent, which makes intervals too narrow.
The one non-inferiority result that "holds" has a lower bound of −5.27 against a −7.00 margin, so
whether it survives scenario clustering is not a formality — it may be the difference between a
result and no result. Report the answer plainly either way; a negative here is a finding, not a
failure.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run analysis and tests through `hpc`.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read `test_normal` or
  `test_challenge`.
- Frozen, read only: every `docs/prereg_*.md`, every `hj8_*` and `hj11_*` config.
- The full suite must end green apart from anything another in-flight unit owns; say which files you
  excluded and why.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X29.md`, under 500 words: what each of the three tests required and what was
missing; the pasted `tests/unit/test_j8_frontier.py` result; the pasted full-suite line; confirmation
that default output is byte-identical on pre-existing keys and how you checked; and the table X19's
brief asks for — `prefix_m9`, `prefix_m11`, `advise_fixed_k_3`, `sft_plan` against `planner_alone` on
`goal_pass_rate`, with task-clustered CI, scenario-clustered CI, and the same under
`--exclude-reference-limit`.

Then answer, in one line each:

- how many scenarios there are, and how many clusters each mode used;
- **whether `prefix_m11`'s non-inferiority still holds under scenario clustering**;
- how many reference episodes were excluded as `limit`, and whether any verdict flips.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. Do not interpret beyond those answers.
