# Brief X33b — finish the threshold-mechanism unit: correct populations, runtime arm discovery, tests

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`, or the script — I run everything
myself in PBS.** The previous three attempts at this unit all died the same way: the worker ran the
script or the tests itself, backgrounded them, and exited, so nothing reached disk although the log
printed "Wrote report". Read files, write files, stop. Make your first file edit within your first
three actions.

## What exists and what is wrong with it

`scripts/analysis/j13_mechanism.py` (661 lines) implements three measurements for the prefix curve
(quality versus handoff depth m): **M1** API-novelty by position in the planner's own trajectory
(`measure_m1_api_novelty`, :210), **M2** the executor's first post-handoff error step per arm
(`measure_m2_compounding_error`, :277), **M3** the prefix-exhausted population and the handoff-only
controlled curve with task- and scenario-clustered paired bootstrap CIs
(`measure_m3_prefix_exhausted`, :374; `paired_diff_task` :72, `paired_diff_scenario` :108). Its
report has never been written. Five defects, each to be fixed:

1. **Wrong population definition.** M2 and M3 define "silenced" / "handoff-only" from
   `totals.per_actor.executor.n_calls == 0` (:302-304, :404-407). The campaign's authoritative
   definition is the per-episode `handoff_occurred` flag, computed deterministically as
   `effective_m < n_source_actions` (`src/sidekick/prefix_source.py:150,184`) and used by
   `scripts/analysis/j8_frontier.py:456-468` (`row.get("handoff_occurred") is True`). Every other
   number in the ledger uses that flag. Switch M2 and M3 to it. Keep `n_calls == 0` as a
   **diagnostic**: for every arm report the count of episodes where the two disagree, and list their
   `(task_id, seed)` keys in the report when the count is non-zero. Never silently drop an episode.
2. **Hard-coded arm lists** (`post_guard_m` :606, `pre_guard_m` :614) omit the post-guard m=11 arm
   and cannot see new arms. Replace with discovery: for m in 2..11, include
   `hj12_prefix_m{m}_20260923/prefix_handoff` (post-guard) and `hj12_prefix_m{m}_20260922/prefix_handoff`
   (pre-guard) **only if the directory holds exactly 114 `result.json`**; print the included and
   excluded lists with their counts. Add `--receiver zeroshot` which instead discovers
   `hj13_prefix_zs_m{m}_20260923/prefix_handoff` (the untailored receiver; m ∈ {6, 9, 11} exist).
3. **Arm-independent key sets** use literal thresholds 9 and 10 (:454-470). Derive them from the
   largest and second-largest **discovered** m, so they cannot go stale.
4. **No CLI, no guard.** `argparse` is imported (:15) and unused; paths are literals (:55-58). Add
   `--results-dir`, `--source-dir`, `--out-report`, `--out-md`, `--n-boot` (default 10000),
   `--seed` (default 20260915, the campaign's bootstrap seed — check `j8_frontier.py` and match),
   `--receiver {tailored,zeroshot}`. Refuse any output path under
   `/scratch/n12194778/sidekick/results/` or containing `test_normal` / `test_challenge`.
5. **No tests.** None reference this module (`grep -rl j13_mechanism tests/` is empty).

Do not change what M1/M2/M3 *measure* beyond the population fix; do not add new mechanisms. If
`load_source_planner` (:167-186) already prefers `result.json`'s `task_id`/`seed` over the directory
names, leave it and cover it with the test below.

## Tests — `tests/unit/test_j13_mechanism.py`, scripted fixtures in `tmp_path`, no real data

1. `load_source_planner` on a fixture whose directory names disagree with the `result.json` fields
   returns the `result.json` values (this test must fail against a path-only implementation).
2. M1 on a three-episode synthetic source with known first-use positions returns the expected
   cumulative share table.
3. M2 on a synthetic arm with one executor error at a known step after handoff reports that step,
   and an episode with `handoff_occurred: false` is excluded from M2 but counted in the
   prefix-exhausted population.
4. M3: the handoff-only population equals the `handoff_occurred` set; when one episode has
   `n_calls == 0` but `handoff_occurred: true`, the divergence count is 1 and its key is listed.
5. Arm discovery includes only campaigns with exactly 114 result files and reports the excluded ones.
6. Output paths under `/scratch/n12194778/sidekick/results/` are refused before anything is written.
7. The bootstrap is deterministic under the default seed (two runs on the fixture give identical CIs).

Style: `tests/unit/test_hj12_shape.py` and `tests/unit/test_hj15_prefix_zsq.py`.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `tar`, `rsync`, `ffmpeg`, `pytest`, `hpc`,
  `qsub`. Never background a command. Read and write files only.
- Frozen, read-only: every `docs/prereg_*.md`, every `hj8_*`/`hj11_*`/`hj12_*`/`hj14_*` config. Do not
  edit `scripts/analysis/j8_frontier.py`, `scripts/analysis/hj12_shape.py`, `src/sidekick/**`.
- Read-only on `/scratch/n12194778/sidekick/results/`; you may `ls` one arm directory and `head` one
  `result.json` to confirm field names (`handoff_occurred`, `totals.per_actor.executor.n_calls`,
  `task_id`, `seed`). Never read or list `test_normal` / `test_challenge`.
- BLAS irrelevant (stdlib + the repo's own modules; if numpy is already imported keep it, else do not
  add it).
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X33b.md`, under 450 words: each of the five defects with the before/after
hunk (path:line); the discovery rule and the derived thresholds; the CLI; the seven test names; then,
unrun, the two `hpc` commands I should use (tailored receiver, zero-shot receiver) with
`--out-report campaign/results/hj13_mechanism_{tailored,zeroshot}_20260923.report.json`.

Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. **Do not claim any test passes —
you are not running them.** If you do not finish, say so in plain words at the top of STATUS.
