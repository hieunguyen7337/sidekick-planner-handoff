# W-9 — parameterise the branch seeds in the J6 PBS script

## Goal (one change, nothing else)

`scripts/pbs/hj6_branches.pbs` hardcodes `--branch-seeds 101 102`. Make that a job
variable so a later submission can add replicates to an existing campaign tree without
editing the script. Default must reproduce today's behaviour **exactly**.

## The single file in scope

`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/scripts/pbs/hj6_branches.pbs`

Nothing else is in scope. Do not touch `scripts/setup/branch_counterfactual.py`, any
config, any test, or any other PBS script.

## What to change

1. Beside the other job-variable defaults (near `SPLIT=`, `DATE=`, `CAMPAIGN_ROOT=`,
   `DELTA_BAND_DELTA=`, `TRAIN_MANIFEST=`), add:

   ```
   BRANCH_SEEDS="${BRANCH_SEEDS:-101 102}"
   ```

2. Replace the hardcoded line in the branch invocation

   ```
     --branch-seeds 101 102 \
   ```

   with a form that word-splits `BRANCH_SEEDS` into separate argv entries, e.g.

   ```
     --branch-seeds ${BRANCH_SEEDS} \
   ```

   ⚠ This one **must not** be double-quoted: `--branch-seeds "101 102"` passes a single
   argument `101 102` and the parser will reject it or, worse, take it as one seed.
   Word splitting is the point here. The script runs under `set -uo pipefail` and
   **not** under `set -e`, so confirm that is still true after your edit.

3. Add `BRANCH_SEEDS` to the `# Job variables (override at qsub time):` comment block
   at the top, in the same style as the entries already listed there.

4. Echo the value once before the invocation so the job log records which seeds it ran,
   matching the style of the existing `[hj6] ...` echo lines.

## Constraints

- **Do not run anything.** No `qsub`, no job submission, no test suite, no evaluation,
  no multi-minute command. Read and edit only. A job built from this script is currently
  queued and two more are running; a submission from you would corrupt a live campaign.
- **Do not commit.** Leave the change in the working tree; the orchestrator reads the
  diff and commits.
- `aquarius01` is a login node for steering only: no python, pip, tar, rsync or ffmpeg,
  and `timeout` on anything you do run. You are **not** covered by the login-node guard,
  so this rule is yours to keep.
- Ignore `.claude/worktrees/` and `.git/`.

## Why the default matters more than usual

Job `25412609` is already queued and held on a dependency. It reads this script at
**start** time, not at submit time, so it will execute whatever this file says when it
begins at roughly 01:37. It passes no `BRANCH_SEEDS`. If your default is not exactly the
two seeds `101` and `102`, that job silently runs the wrong experiment on a campaign that
already holds ~2,000 finished branches keyed on those seeds.

## Return contract (short)

- The diff, as applied.
- One line confirming the default expands to two separate argv entries, `101` and `102`,
  with the `path:line` of the changed invocation.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
- No prose beyond that.
