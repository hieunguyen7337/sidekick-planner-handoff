# Brief X40 — three cost axes (F2) and a multiplicity control over the m grid (F1/T7)

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Create your files within your first three actions, then iterate with tests.** Write a STATUS file at
every milestone so a fresh session can resume. **Do NOT commit. Do NOT submit jobs** — Claude submits
everything; you write code and unit tests only.

## Why these two units

Two reviewer attacks are still open and both are answerable from data already on disk, at zero hosted cost.

**Attack 10:** the cost story is told in one currency (non-cached planner tokens). A reviewer will ask
whether the ordering of the arms survives provider-priced dollars (where cached input is 10× cheaper than
fresh input) and whether GPU time for the local executor changes the picture. If the ordering flips under
any axis, we must say so; if it holds under all three, that is a much stronger claim than we currently make.

**Attack 6:** the prefix grid m ∈ {2,4,6,7,8,9,10,11} was explored post hoc and every interval is reported
uncorrected. A reviewer will point out that with eight comparisons, one "significant" rise is expected by
chance. We need family-wise adjusted intervals beside the raw ones.

---

## Unit A — `scripts/analysis/j12_cost_axes.py` (new file)

Extend, do not rewrite: **reuse** `usage_noncached_tokens`, `last_plan_event_noncached_tokens`,
`attach_sft_plan_source_plan_tokens` and `noncached_episode_cost` from
`scripts/analysis/j8_noncached_cost.py` by importing them [OBSERVED scripts/analysis/j8_noncached_cost.py:16,27,76,150].
Reuse the arm-loading and clustered paired bootstrap from `scripts/analysis/j8_frontier.py` — do **not**
re-implement a bootstrap; find the existing function and call it, and cite its `path:line` in STATUS.

Price card: `configs/cost/prices_2026-09.yaml` [OBSERVED], which already carries
`models.gpt-5.6-luna.{input, cached_input, output}` in USD per 1M tokens and `local.usd_per_gpu_hour: 2.50`.

**CLI:** `--arm label=<abs results dir>` (repeatable), `--prices configs/cost/prices_2026-09.yaml`,
`--out <report.json>`, `--out-md <report.md>`, `--n-boot 10000`, `--seed 20260915`, `--cluster scenario`.

**Three axes, one row per arm:**

1. **`noncached_tokens_per_episode`** — the current convention. Mean over episodes.
2. **`usd_per_episode`** — provider-priced, **including cache billing**: fresh input at `input`, cached
   input at `cached_input`, generated tokens at `output`. Take the cached/uncached split from the usage
   records; if a usage record does not distinguish them, count it as fresh input and **record the count of
   such records in the report** under `n_usage_without_cache_split`. Do not silently assume.
3. **`hosted_calls_per_episode`** — `n_planner_calls` from `result.json`.

Also report, but keep clearly separate as an *assumption* not a measurement: `local_gpu_usd_per_episode`
using `local.usd_per_gpu_hour` and the episode wall time if wall time is recorded; if it is not recorded,
write `null` and say so — **never** invent a duration.

**The load-bearing output:** for each axis, rank the arms, and emit `ordering_by_axis` plus a boolean
`ordering_is_stable_across_axes`. If any pair of arms swaps rank between axes, list the swapped pairs in
`ordering_flips`. Also re-run the non-inferiority statement for each prefix arm against the ceiling on each
axis's *cost* (quality is unchanged; what changes is the cost at which the quality is bought) and emit
`ni_unchanged_across_axes`.

**Guard:** a `validate_output_path()` that refuses any `--out` under `/scratch/n12194778/sidekick/results/`
or containing `test_normal` / `test_challenge`. Copy the one in `scripts/analysis/j13_mechanism.py`.

**Fatal, not silent:** if an arm yields zero priced episodes, or if more than 5 % of episodes lack usage
records, raise `SystemExit` naming the arm and the counts. Do not write a report. (A diagnostic that only
records is how `MECH-02` happened; see `docs/claims_ledger.md`.)

---

## Unit B — multiplicity control inside `scripts/analysis/hj12_shape.py`

Add, do not restructure. The file already has `percentile_interval` (`:269`), `onesided_lower` (`:279`),
`cluster_keys` (`:286`) and `bootstrap_segmented` (`:309`) [OBSERVED].

1. New function `holm_adjusted_intervals(contrasts: dict[str, list[float]], alpha: float = 0.05) -> dict`
   taking the per-contrast bootstrap sample vectors already produced for the m grid, and returning, per
   contrast, the Holm-adjusted two-sided interval and the adjusted p-value. Holm, not Bonferroni: it is
   uniformly more powerful at the same family-wise error rate, and it is the standard a reviewer expects.
2. Wire it so the report gains a `multiplicity` block: `{method: "holm", alpha: 0.05, family: [<contrast
   names>], n_comparisons: <int>, adjusted: {<contrast>: {ci95_pp_adjusted, p_adjusted, survives}}}`.
   **Leave every existing raw interval exactly where it is** — the registered analysis is unchanged; this
   is an addition reported beside it.
3. The family is the set of adjacent-m contrasts on the primary population, listed explicitly in the
   report so it cannot be redefined after the fact.

---

## Tests — `tests/unit/test_j12_cost_axes.py` and additions to the shape tests

- `test_cached_input_is_billed_at_the_cached_rate` — a scripted usage record with a known cached/fresh
  split prices to a hand-computed dollar figure.
- `test_usage_without_cache_split_is_counted_not_assumed` — the count appears in the report.
- `test_ordering_flip_is_detected` — two scripted arms that swap rank between token and dollar axes produce
  a non-empty `ordering_flips`.
- `test_zero_priced_episodes_is_fatal` — `SystemExit`, no report written.
- `test_validate_output_path_refuses_forbidden_locations`.
- `test_holm_is_monotone_and_at_least_as_wide_as_raw` — every adjusted interval contains the raw interval.
- `test_holm_matches_a_hand_worked_example` — four p-values with a known Holm result.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`, `tar`, `rsync`, no model
  downloads. `timeout` in front of anything you do run. BLAS pinned to one thread. Never background a
  process.
- Do not edit `src/sidekick/**`, `scripts/analysis/j8_frontier.py`, `scripts/analysis/j13_mechanism.py`,
  any `configs/hj8_*` / `hj11_*` / `hj12_prefix_m*.yaml`, or anything under `docs/prereg_*` (those are
  frozen; registered text is amended by appending, never editing). Never read or list `test_normal` /
  `test_challenge`. Never write under `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X40.md`, under 500 words, with a milestone line per unit so a fresh session can
resume: the functions you imported from `j8_noncached_cost.py` and `j8_frontier.py` with `path:line`; the
new CLI signature; the report schema for `ordering_by_axis`, `ordering_flips` and `multiplicity`; the test
names; and the exact `hpc` command Claude should run for each unit. `[OBSERVED path:line]` / `[INFERRED]`
on every claim. **Do not claim any test passes** — you cannot run them.
