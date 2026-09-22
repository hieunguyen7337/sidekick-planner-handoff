# Brief X19 — two statistical repairs: the cluster unit, and a comparator that hit its cap

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis only. **Do not `qsub`, do not touch a GPU, do not run any evaluation.** Do not edit `src/`,
`configs/`, or anything under `scripts/pbs/`.

## Repair 1 — the bootstrap resamples the wrong unit

`scripts/analysis/j8_frontier.py` runs a paired percentile bootstrap clustered on **task**. But the
57 dev tasks are **19 scenarios × 3 variants**: AppWorld task ids are `<scenario>_<n>`, and
`50e1ac9_1`, `_2`, `_3` are one scenario [OBSERVED `scripts/setup/hj1_gate.py:45-46`, which already
has a `scenario_of(task_id)` helper — **reuse it, do not write a second one**].

Three variants of one scenario share a world, a user and an app set, so their outcomes are
correlated. Clustering on task treats them as independent and makes every interval too narrow. The
campaign's one non-inferiority "hold" has a lower bound of −5.27 against a −7.00 margin, so this is
not an academic point: it may be the difference between a result and no result.

**Build**: a `--cluster {task,scenario}` flag, default `task` so existing output is unchanged. When
`scenario`, the resample unit is the scenario. **Every report must carry both**: add a
`ci95_pp_scenario` (and the matching `deficit_ci_upper_pp_scenario` and `holds_scenario`) beside each
existing field rather than replacing it, so a reader sees both intervals side by side. Record the
number of clusters used for each.

Apply it everywhere the existing CI is computed: the non-inferiority table and the chord test, for
`goal_pass_rate` and TGC, across all four populations.

## Repair 2 — the comparator ran under a tighter cap than everything it is compared to

`planner_alone` ran with `max_planner_calls: 25` [OBSERVED `configs/pilot_planner_alone.yaml:25`].
Every later arm uses 81 [OBSERVED `configs/hj8_fixed_k_3.yaml:39-41`, whose comment records that the
inherited 25 cap ended **11 of 12** `limit` episodes in HJ-1]. So every non-inferiority statement in
the campaign is against an understated ceiling.

The re-run at cap 81 is a hosted job and is not yours. What **is** yours is the honest interim
figure, which costs nothing:

**Build**: a `--exclude-reference-limit` flag. When set, every contrast is computed on the subset of
pairs where the **reference arm** did not terminate with `error_type == "limit"`. Report the
excluded count and the resulting `n_pairs`. This is a sensitivity analysis, not a replacement —
default off.

## Verification run (write JSONs to `campaign/results/`, never to `/tmp`)

`/tmp` on a compute node is not visible afterwards. Use these exact output paths.

Run the unified 14-arm frontier three ways, with the arm list and flags exactly as in
`campaign/results/hj12_unified_frontier_20260922.report.json` (read its `arms` block for the paths):

1. unchanged → `campaign/results/x19_check_default.report.json` — must match the committed
   `hj12_unified_frontier_20260922.report.json` field-for-field on every existing key.
2. `--cluster scenario` → `campaign/results/hj12_unified_frontier_scenario_20260923.report.json`
3. `--cluster scenario --exclude-reference-limit` →
   `campaign/results/hj12_unified_frontier_scenario_nolimit_20260923.report.json`

Python lives at `/scratch/n12194778/sidekick/env/bin/python`; set `PYTHONPATH=src:.` and pin
`OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`. Run it through `hpc`, not on the login
node.

## Report the numbers that matter

In STATUS, paste a small table with, for `prefix_m9`, `prefix_m11`, `advise_fixed_k_3` and
`sft_plan`, the `goal_pass_rate` contrast against `planner_alone`: point estimate, task-clustered CI,
scenario-clustered CI, and the same under `--exclude-reference-limit`. State plainly:

- how many scenarios there are and how many clusters each mode used;
- whether `prefix_m11`'s non-inferiority still holds under scenario clustering;
- how many reference episodes were excluded as `limit`, and whether any verdict flips.

Do not interpret beyond those statements; I draw the conclusions.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout`
  on every command. Compute through `hpc`.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read `test_normal` or
  `test_challenge`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- The suite is at **506 passed, 1 skipped** and must not fall. Add unit tests: scenario grouping maps
  `x_1/x_2/x_3` to one cluster; default output is unchanged; the limit-exclusion subset has the
  expected `n_pairs`.
- **Do not commit.** I review and commit.
- Create your files within your first three actions, then iterate with tests.

## Return contract

`campaign/workers/STATUS_X19.md`, under 500 words: the flag names, the new JSON keys, the pasted
table, the three statements above, the test names, and the pasted suite line. Tag every claim
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
