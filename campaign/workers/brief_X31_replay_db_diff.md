# Brief X31 — does a replayed prefix reproduce the source episode's database state?

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Analysis and a test. **Do NOT `qsub` an evaluation, do not touch a GPU, do not run training.**
I submit every job myself. Run analysis through `hpc`.

## Why this exists

Every action-channel number in this campaign rests on replay: `prefix_handoff` re-executes the first
`m` recorded planner actions in a fresh AppWorld environment and hands the resulting state to the
executor. If replay does not faithfully reproduce the source episode's state, the whole channel
comparison is measuring something other than what it claims.

`src/sidekick/replay.py:16-21` verifies **visible state only** — the observation text the environment
returned. Two database states that print the same observation would pass that check while differing in
rows the executor's later actions depend on. This is reviewer attack #12 in the plan, and it is
currently undefended.

## Your job

1. Read `src/sidekick/replay.py` and establish exactly what `replay_prefix` compares, and what it does
   not. Quote the comparison with `[OBSERVED path:line]`.
2. Establish whether AppWorld exposes a way to read database state directly after a sequence of
   actions — look for anything the harness already uses to snapshot, dump or diff the task database.
   **Do not add a dependency and do not modify the AppWorld installation.** If no such affordance
   exists, say so plainly and stop at step 4; a well-evidenced "this cannot be checked with what is
   installed" is an acceptable and useful result.
3. If a direct read is available, take a **sample of 12 episodes** spanning small and large `m`
   (include at least three from `m = 11`) and compare, for each, the database state after replaying
   the prefix against the state the source episode reached at the same point. Report how many match
   exactly, how many differ, and for each difference which table and field diverged.
4. Write a unit test on a scripted fixture that would catch a replay which reproduces the observation
   text but not the underlying state — even if step 3 finds no real divergence. The test documents the
   property we rely on.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run everything through `hpc`, prefixing each job with
  `env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-X31-spool`. BLAS pinned to one thread.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Never write under it. Dev only; never read
  or list `test_normal` or `test_challenge`.
- Do not edit `configs/`, `scripts/pbs/`, `scripts/analysis/j8_frontier.py`,
  `tests/unit/test_j8_frontier.py`, `src/sidekick/training/handoff_sft.py`, or any `docs/prereg_*.md`.
- Run the full suite with `--ignore=tests/unit/test_j8_frontier.py` — another unit owns that file.
- **Make your first source edit within your first three actions. Never background a command and exit.**
  Run every command in the foreground with `timeout` and wait for it.
- **Write `campaign/workers/STATUS_X31.md` even if you finish only part of this.** A partial STATUS
  naming what is done and what is not is worth far more than no file.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X31.md`, under 400 words: what `replay.py` actually compares, quoted; whether
a direct database read is available and how you established that; the 12-episode table if you got one;
the test you added; and the pasted suite line.

Then answer in one line: **is there any evidence that replay diverges from the source episode's state,
and if so at which `m`?** A clean negative result is the expected outcome and is worth reporting as
such — do not manufacture a divergence.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
