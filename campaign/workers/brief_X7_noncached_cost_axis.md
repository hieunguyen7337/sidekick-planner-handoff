# Brief X7 — the token cost axis compares two different quantities

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis-only. Do not touch `src/`, `scripts/pbs/`, `scripts/setup/` or any config. **Two GPU jobs
are running right now**; `scripts/analysis/j8_frontier.py` is not imported by them, which is why
this unit is safe to run concurrently. Do not `qsub` anything and do not touch a GPU.

## The defect

`j8_frontier.py` offers `--cost-key replayed_planner_tokens` for the prefix-handoff frontier. It
resolves per arm like this [OBSERVED scripts/analysis/j8_frontier.py:629-633]: use the row's
`replayed_planner_tokens` when present, otherwise fall back to `planner_tokens_live`.

Those two quantities are **not on the same scale**.

- `replayed_planner_tokens` is built by `src/sidekick/prefix_source.py` as
  `input + output + reasoning`, deliberately **excluding `cached_input_tokens`**.
- `planner_tokens_live` comes from the ledger's `planner_tokens_total`, and `CostLedger._tokens`
  **adds `cached_input_tokens`** [OBSERVED src/sidekick/cost/ledger.py:48-54].

Measured on one real `planner_alone` dev episode
(`/scratch/n12194778/sidekick/results/hj1b_planner_20260915/planner_alone/1/0d8a4ee_1/result.json`):
`planner_tokens_total` = 676,946, of which `cached_input_tokens` = 310,528 — **46% of the reported
cost is cached context**.

Consequence: a prefix arm at ~85,190 replayed tokens would be charged 12.6% of the planner's cost
when the honest figure on a common basis is 23.2%. **The error is roughly a factor of two and it
runs in the direction that flatters the hypothesis**, against a pre-registered threshold of "no more
than about half the planner's tokens". It must not survive into the report.

## The fix

Cached input is re-sent context billed at a tenth of the rate; it is not new work, and every token
budget in this project is specified to exclude it. So make the axis **non-cached planner tokens,
computed identically for every arm**.

1. Add a cost key `planner_tokens_noncached` and make it the one used for the prefix frontier.
   For each episode row compute:

   `live_noncached = per_actor.planner.input_tokens + output_tokens + reasoning_output_tokens`

   reading `totals.per_actor.planner` from the episode's `result.json`, which records all four
   fields separately [OBSERVED result.json `totals.per_actor.planner`]. Then:

   `cost = live_noncached + (replayed_planner_tokens or 0)`

   `replayed_planner_tokens` already excludes cached, so the two addends agree. A prefix arm has
   `live_noncached == 0`; `planner_alone` has no replayed component. **Never mix the old
   cached-inclusive total into this key.**
2. Keep the existing `replayed_planner_tokens` and `planner_tokens_live` keys working exactly as
   they do now. Other reports read them; this is an addition, not a rename.
3. Report, per arm, alongside the cost: `cached_input_tokens` per episode and the cached share of
   the cached-inclusive total. A reader must be able to see how much of the old number was cache.
4. In the emitted JSON, add a short `cost_key_note` stating in one sentence what the active cost key
   counts and that cached input is excluded. The next person to read this report should not have to
   rediscover any of the above.

## An honesty item you must implement, not just mention

On this axis `sft_plan` will show **zero** planner tokens, because it replays a cached plan packet
and the ledger records no tokens for it [OBSERVED
/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware/sft_plan/1/0d8a4ee_1/result.json,
`totals.per_actor.planner` all-zero with `n_calls: 1`].

That is misleading as a frontier floor: the plan it replays was produced by the hosted planner once
and is not free in any deployable sense, whereas the prefix arms **are** charged for the plan they
replay (their `replayed_planner_tokens` includes the `plan` event).

So the floor and the prefix arms are currently charged on different terms. Fix it the honest way:
compute `sft_plan`'s replayed plan cost from the same source recording it replays
(`/scratch/n12194778/sidekick/results/hj1b_planner_20260915`, matched by `task_id`/`seed`), summing
the **non-cached** usage on that episode's `plan` event only, and include it in the arm's cost.
Report the mean value you derive.

If you cannot do this reliably — say, because the packet cache does not map one-to-one onto a source
episode — then **do not fake it**: leave `sft_plan` at zero, and emit a top-level
`known_cost_understatements` entry naming the arm, the reason, and your best estimate of the
magnitude, so the floor's position is not silently wrong. Say which of the two routes you took.

## Verification

- Re-run the existing dry run and paste the per-arm cost line for `planner_alone` and `sft_plan`
  under both the old and new cost keys, so the size of the correction is visible:
  ```
  timeout 1800 hpc -c 4 -m 16gb -t 00:25:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python scripts/analysis/j8_frontier.py --arm planner_alone=/scratch/n12194778/sidekick/results/hj1b_planner_20260915 --arm sft_plan=/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware --reference-arm planner_alone --floor-arm sft_plan --cost-key planner_tokens_noncached --out /tmp/x7_dryrun.json'
  ```
  Write the JSON to `/tmp`, not to `campaign/results/`.
- Add unit tests: a row with cached tokens present is costed excluding them; a prefix row
  (live 0, replayed > 0) and a live row (live > 0, replayed absent) land on the same scale; the old
  keys are unchanged.
- The suite is at **467 passed, 1 skipped** and must not fall.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Use
  `timeout ... hpc bash -lc '...'` with BLAS pinned to 1 thread.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X7.md`, under 500 words: the new cost key's exact formula, the before/after
cost numbers for `planner_alone` and `sft_plan`, which route you took on the `sft_plan` floor and
why, the test names, and the pasted suite line. Tag every claim `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
