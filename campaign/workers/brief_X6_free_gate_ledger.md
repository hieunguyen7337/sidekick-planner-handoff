# Brief X6 — the free-arm gate counts replayed planner calls as spend

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

This is a small, surgical fix on the critical path. A GPU experiment is blocked behind it.

## What happened

The new `prefix_handoff` arms replay the hosted planner's first `m` recorded steps into a fresh
environment, then let the local executor finish. They make **no hosted planner calls at all**. The
smoke run confirms that: every arm's `ledger_totals` reported

```
"planner_calls_total": 0,
"planner_tokens_total": 0,
```

and the job's own live-planner guard passed on all four configs.

The smoke gate failed all four arms anyway:

```
[gate] FAIL
  - expected zero planner calls but saw 9 (models={}) -- this arm was supposed to be free
```

Nine is exactly right for what it measured: 3 smoke episodes × (2 replayed planner actions + 1
replayed plan) at `m=2`, and 15 at `m=4` for the same reason. **It is counting replayed history as
spend.**

## Cause, already traced — do not re-investigate, verify and fix

`scripts/setup/campaign_summarize.py` reports two different quantities:

- `summary["planner_calls_total"]` (`:142`) comes from `planner_calls`, derived from each run's
  `n_planner_calls`, which `counters_from_events` computes over the episode's events **including a
  replayed prefix** [OBSERVED src/sidekick/systems/loop.py, `counters_from_events`]. It is
  replay-inclusive.
- `summary["ledger_totals"]["planner_calls_total"]` (`:148`) is the `CostLedger` total: **actual
  hosted spend**.

The free-arm branch of `gate_fails` (`:186-191`) checks the first. It should check the second.

This is not a new class of problem in this project. The same conflation was found in the B1
counterfactual cap, where the budget summed replay-inclusive tick counts instead of live calls, and
would have stopped a run at roughly 6,000 live calls believing it had spent 10,000. The analysis
side already gets this right: `scripts/analysis/j8_frontier.py` `attach_ledger_fields` (`:505-520`)
takes `planner_calls_live` from `totals.planner_calls_total` and keeps the replay-inclusive figure
separately as `planner_calls_replay_inclusive`. **Follow that precedent's naming.**

## The change

In `scripts/setup/campaign_summarize.py`:

1. Add the live figure to the summary dict as its own named key, e.g. `planner_calls_live_total`,
   read from the ledger totals, alongside the existing `planner_calls_total`. Rename nothing that
   already exists — other scripts and every prior campaign log read these keys.
2. Make the **free-arm** check (`expect_planner` false) test the **live** figure. When it fails, the
   message must report both numbers, so a reader can tell replay from spend at a glance. Suggested
   wording: `expected zero live planner calls but saw N (replay-inclusive count M, models=...)`.
3. When the live figure is 0 but the replay-inclusive figure is > 0, that is the **normal and
   correct** state for a prefix arm. Do not warn, do not fail. Add a one-line comment saying so and
   naming `prefix_handoff`, because the next person to read this will assume the mismatch is a bug.
4. **Leave the `expect_planner` (non-free) branch alone.** It currently passes for every existing
   arm, including cached-packet arms such as `sft_plan` where the ledger records 1 call per episode.
   Changing it risks arms this brief has not reasoned about. If you believe it is also wrong, say so
   in STATUS and do not change it.

## Tests

Add to the existing test file for this module if one exists; otherwise create
`tests/unit/test_campaign_summarize_gate.py`.

1. A free arm with ledger `planner_calls_total = 0` and a replay-inclusive count of 9 **passes**.
   This is the prefix-handoff case and the reason for the fix.
2. A free arm with ledger `planner_calls_total = 4` **fails**, and the message contains both
   numbers.
3. A non-free arm with ledger 0 still fails the `expect_planner` check exactly as it does today
   (guards the MockPlanner-fallback detection that check exists for).
4. The summary dict still contains the original `planner_calls_total` key with its original
   replay-inclusive meaning.

## Constraints

- You own `scripts/setup/campaign_summarize.py` and the one test file. **Touch nothing else** — in
  particular not `src/`, not `scripts/pbs/`, not `scripts/analysis/`, not any config.
- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync` or `ffmpeg` there. Run the
  suite in a job:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
- The suite is at **463 passed, 1 skipped** and must not fall.
- `timeout` on every command.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Do not re-run any evaluation, do not
  `qsub`, do not touch a GPU. I submit jobs.
- **Do not commit.** I review and commit.
- Dev only; never read `test_normal` or `test_challenge`.

## Return contract

`campaign/workers/STATUS_X6.md`, under 400 words: the diff summary, the new key name, the exact
failure message text, the four test names, and the pasted suite result line. Tag claims
`[OBSERVED <path>:<line>]` or `[INFERRED]`. If the cause described above is wrong, say so plainly
rather than working around it.
