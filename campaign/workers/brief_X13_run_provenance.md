# Brief X13 — a run does not record which code produced it

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Check before you start:** two GPU jobs, `25596786` and `25596787`, may be RUNNING. Run
`timeout 30 qstat -u n12194778`. If either shows state `Q` (queued), **stop and write STATUS saying
so without changing anything** — a queued job picks up whatever is on disk when it starts, and this
edit must not reach a run that was validated against different code. If both are `R` or gone,
proceed: a running job's workers have already imported their modules and cannot see later edits.

Either way: do not `qsub`, do not touch a GPU, do not run any evaluation.

## The gap

Nothing in a run's recorded output says which revision of the code produced it. There is no
`git rev-parse` in `scripts/pbs/hj12_prefix.pbs` and no revision field written by
`src/sidekick/runner.py` [OBSERVED: `grep -n "git rev-parse\|GIT_SHA" scripts/pbs/hj12_prefix.pbs`
and `grep -n "git\|sha\|commit" src/sidekick/runner.py` both return nothing relevant].

That matters here more than it would elsewhere. Jobs sit in this queue for hours, and the code on
disk moves while they wait. The prefix jobs now queued were submitted and smoke-tested at one
revision and will execute at a later one. I checked by hand that the path they take is unchanged,
but nothing in the artifacts they produce would have told anyone that, and the next person reading
these numbers cannot repeat that check.

The remaining phases spend real money — roughly two thousand hosted calls, then a training run, then
a final read of the test split. A number in a thesis whose provenance cannot be established is worth
much less than one whose provenance can.

## What to build

**Capture in the shell, read in the runner.** Do not shell out to `git` from inside the episode
path. A subprocess that fails or hangs on a compute node must never be able to affect an episode,
and the cheapest way to guarantee that is for the runner never to call it.

1. In `scripts/pbs/hj12_prefix.pbs` and `scripts/pbs/hj12_live.pbs`, near the top where the campaign
   id is computed, capture the revision and the working-tree state, and export them:
   - `SIDEKICK_GIT_SHA` — full `git rev-parse HEAD`, run with a `timeout` and tolerant of failure
     (empty string if `git` is unavailable or the command fails; never abort the job for this).
   - `SIDEKICK_GIT_DIRTY` — `1` when `git status --porcelain` is non-empty, `0` when empty, empty
     string when it could not be determined.
   Echo both on the existing `[hj12]` banner line so they appear in the job log even if the manifest
   is never read.
2. In `src/sidekick/runner.py`, write both into the campaign manifest alongside `campaign_id` and
   the other run metadata. Read them **from the environment only**. A missing variable records
   `None`, never a crash and never a guess. Use whatever key naming the surrounding manifest fields
   already follow.
3. A dirty tree is recorded, not rejected. Refusing to run on uncommitted changes would block
   ordinary iteration; the honest move is to say so in the artifact so a reader can weigh it.

## Tests

- The manifest carries the revision and dirty flag when the environment provides them.
- Both are `None` when the environment does not, and nothing raises.
- A dirty flag of `1` is recorded rather than causing a failure.

Do not add a test that invokes `git`; set the environment variables directly.

## Do not touch

Any config, any `docs/prereg_*.md`, any `hj8_*` or `hj11_*` file, the episode loop
(`src/sidekick/systems/`), and anything under `/scratch/n12194778/sidekick/results/` (read-only).

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Suite via
  `timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
- The suite is at **498 passed, 1 skipped** and must not fall.
- `bash -n` both PBS scripts and paste the output.
- `timeout` on every command. Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X13.md`, under 400 words: the `qstat` states you saw and whether you
proceeded, the two variable names, the manifest keys, the banner line, the test names, both `bash -n`
results and the pasted suite line. Tag claims `[OBSERVED <path>:<line>]` or `[INFERRED]`.
