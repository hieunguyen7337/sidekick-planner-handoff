# Brief E4b — action-reviewing planner (RETRY of E4)

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Read this first

**The full specification is in `campaign/workers/brief_E4_action_review.md`. Read it and execute it.**
This file is an addendum: why the previous attempt failed, and what it had discovered before it died.

## Why there is a retry

The first attempt (Cline, `z-ai/glm-5.3-flash`) exited with code 0 having written **zero files**. It
spent its entire turn reading and reasoning, produced no `STATUS_E4.md`, and left the tree clean. Its
analysis was sound; it simply never wrote anything.

**Therefore: create the files within your first three actions.** Write a first version of every file
the spec calls for — verifier kind, system module, two configs, test file — before you refine
anything. Then iterate with tests. Do not spend the turn exploring first. If you run short on time, a
working partial implementation with a STATUS file beats a perfect plan with nothing on disk.

## What the previous attempt had already found

These are **unverified claims from a worker log**, not established facts. They are offered to save
you rediscovery time. **Verify each one before relying on it**, and cite what you actually observe.

- `MockPlanner`, `MockExecutor` and `MockEnv` already exist and are the right basis for the tests —
  reportedly around `src/sidekick/agents/planner.py` and the existing loop test harness. Reuse them;
  do not write new mocks.
- `PlannerResponse` reportedly has fields including `code` and `correction`. The action-review
  verdict needs to fit this type or extend it.
- **`EventType` in the schemas module is reportedly a `Literal`**, and `"action_review"` is not one of
  its members. If so, emitting a new event type requires extending that Literal — check this early,
  because it determines whether the verdict can be recorded in the event stream at all.
- `run_episode` reportedly does not accept an `action_reviewer` argument, and `ConfigurableSystem.run`
  does not pass one. Threading it through is part of the work.
- The `run_start` payload carries a `policy` dict, and **existing tests may assert its exact
  contents**. If you add review flags to it, run the full suite and fix what you break — do not
  silently change an asserted payload.

## Non-negotiable constraints (repeated from the main brief)

- **Build and unit tests ONLY. No GPU. No planner API calls. No evaluation. No `qsub` of any eval
  job.** Another unit is training on the GPU right now; do not submit GPU work.
- New config prefix `hj11_action_review_*` only. **Do not edit any `hj8_*` config** — those are frozen
  inputs to a completed campaign.
- `aquarius01` is a LOGIN NODE: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Run the suite
  via `hpc bash -c '<cmd>'`, BLAS pinned to 1 thread, `timeout` on everything.
- The suite must end at **>= 447 passed, 1 skipped, 0 failed** plus your new tests. It needs
  `--import-mode=importlib`. Note the baseline is now 447, not 442 — unit E1 landed five new tests.
- Do not edit `docs/prereg_v1.md` or `docs/prereg_b1_pilot.md` — FROZEN.
- Do not touch `/scratch/n12194778/sidekick/results/`, `.git/`, or `.claude/worktrees/`.
- **Do not commit.** Claude reviews the diff and commits.
- Another worker is concurrently editing `campaign/workers/STATUS_E2.md` and building datasets under
  `/scratch/n12194778/sidekick/artifacts/`. Stay out of both.

## Return contract

Write `campaign/workers/STATUS_E4.md` (that name, not E4b), under 500 words: files added and changed
with line numbers, the exact test command and its verbatim final summary line, every claim tagged
`[OBSERVED <path>:<line>]` or `[INFERRED]`, and anything you could not finish stated plainly with
resume instructions.
