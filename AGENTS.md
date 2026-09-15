# AGENTS.md — rules for every agent working in this repository

This is a research repository on a **shared HPC cluster**. The rules below are not style preferences.
Two of them exist because someone already broke the machine for other users.

## 1. The login node is for steering, never for work

`aquarius01` is shared by the whole cluster. **Never run Python, `pytest`, package installs, model
downloads, `tar`, `rsync` or `ffmpeg` on it.** Those run inside a PBS job:

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 <command>          # one command in a job
timeout 900 hpc --gpu -c 12 -m 64gb -t 02:00:00 <command>   # with a GPU
qsub scripts/pbs/<template>.pbs                             # a real batch job
```

`hpc` takes an argv; for a compound command use `hpc bash -lc '<command>'`.

**Put `timeout <seconds>` in front of every command you run, without exception.** On the login node
also export `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.

A reaper (`hpc-guard`) kills login-node processes at 25% sustained CPU for 30 minutes, 12 hours of CPU,
or 12 hours of wall time. **Size any unit to under 10 hours** and write a STATUS file so it can resume.

## 2. Never run git

Commits are made by the orchestrating session, not by workers. Do not run `git` at all, and never touch
`.git/` or `.claude/worktrees/`.

## 3. Stay inside your file ownership

Several agents work in this tree at once. Your brief lists the files you own. Editing a file another
unit owns will lose someone's work. If you need something outside your list, say so in your STATUS file
and work around it.

## 4. The seam contract is law

`campaign/briefs/SEAM_CONTRACT.md` defines the shared types and signatures. Use the names in it exactly.
If a field looks wrong, record the objection in your STATUS file and implement the contract anyway — a
rename breaks whatever another agent is building against it right now.

## 5. Never invent a result

Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. A number you did not measure is
`[INFERRED]` and must say so.

**Running the tests is not optional, and reporting that they pass without running them is the one
unforgivable error here.** It has already happened once in this repo: a unit reported "54 tests" and 13
of them failed on first execution, including one that let negative token counts into the cost ledger.
Paste the real output, verbatim, including failures.

## 6. Secrets

Never print the value of a token, key or credential. Names only. The planner is authenticated through
the user's existing Codex login; no key belongs in this repository, in a config file, or in a log.

## 7. Experiment hygiene

- `data/raw/` is **append-only**. Never rewrite or delete an event log.
- Frozen means frozen: a model id, revision, prompt hash and sampling setting recorded in a manifest is
  not to be "improved" mid-campaign. A new configuration is a new run prefix.
- Anything touching the planner costs real money. Use `MockPlanner` in tests. Never call the live
  planner in a loop you have not bounded.
- Test splits (`test_normal`, `test_challenge`) are for the final run only. No prompt tuning, no error
  analysis, no peeking. AppWorld's own licence requires this too.
- Failed, crashed and timed-out runs stay in the results with an `error_type`. Never drop them — the
  denominator is part of the claim.

## 8. Worker-specific notes

- **Codex/luna on the login node is currently broken** (`bwrap: Creating new namespace failed`). The
  planner path is unaffected because it passes `--disable shell_tool`, so no sandbox is created.
- **Cline** is the least stable lane: write your files within the first three actions, then iterate, and
  keep STATUS current so a dead session can be resumed rather than restarted.
- **The Codex config defaults to a different, more expensive model** (`gpt-5.6-sol` at `xhigh`). Any
  script that calls the planner must pass `-m gpt-5.6-luna -c model_reasoning_effort=medium` explicitly.
