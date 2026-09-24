# Rules that bind every 2026-09-24 build unit (read before anything else)

Context: `docs/plan_top_venue_20260924.md` (the plan) and `docs/plan_review_fixes_20260923.md` (the fix register
with R-item ids). Both are committed on the plan branch and are present in your worktree.

## Where you work
- Work ONLY inside your own worktree (named in your brief). Never edit another worktree, and never the plan
  worktree `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`.
- `IGNORE .claude/worktrees/ and .git/` in every search.

## The login node (aquarius01) is for steering only
- Never run `python`, `pytest`, `pip`, `tar`, `rsync` or `ffmpeg` directly. Run them in a PBS job via `hpc`
  (about 2 minutes of queue):

  ```
  hpc bash -c 'cd <WT> && export PYTHONPATH=src:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 && timeout 3000 /scratch/n12194778/sidekick/env/bin/python -m pytest -q -p no:cacheprovider <tests>'
  ```

- Prefix cheap shell commands (grep, sed, ls, wc, jq, git) with `timeout 60`. The shell is zsh: quote globs.
- The tool guard refuses complex compound commands and long heredocs. Write multi-step shell into a script under
  `/home/n12194778/.claude/jobs/91578989/tmp/<your-unit>/` and run it with `bash <script>`.

## Data you may and may not touch
- Read only **dev** campaigns under `/scratch/n12194778/sidekick/results/`.
- Never read `test_normal` or `test_challenge` data. Never open any `j10_*` campaign that does not end in
  `_dryrun`.
- Never edit anything under `/scratch/.../results/` by hand. Never write under `hj6_branches_train_20260917`.
- Never modify the shared Python env `/scratch/n12194778/sidekick/env`.

## Frozen or protected files: do not edit
- `docs/prereg_*.md`.
- `configs/j10_*.yaml`, `scripts/pbs/j10_arm.pbs`, `scripts/analysis/j10_report.py`.
- The line numbers that frozen text cites must not move:
  - `src/sidekick/systems/sft_plan.py:11` and `:14`;
  - `src/sidekick/systems/prefix_handoff.py:42`;
  - `src/sidekick/agents/planner.py:956-962`.

  If you must touch one of these files, make the edit line-count-neutral above those lines, and show
  `git diff --stat` in your report.

## What you may not spend
- No hosted, luna or codex calls. No vLLM servers.
- No `qsub` of experiment runs, unless your brief explicitly allows one.
- Unit tests and CPU analyses run through `hpc` only.

## Code standard
- Match the surrounding code: its comment density, naming and idiom.
- Every new function gets a fixture test whose expected value is computed by hand in the test.
- Numbers go into report JSON keys. Nothing is hand-typed into docs.

## Git
- When your tests pass, commit on your branch inside your worktree. Stage specific files (`git add <paths>`).
- Never use `git stash`. Never push, merge or rebase.
- End every commit message with these two lines:

  ```
  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01WAcXxoXWcJdXBPnbnHPek8
  ```

## Report back (≤ 450 words)
- Files changed and the commit sha.
- The exact test command, with the pass count quoted from its output.
- Every deviation from the brief, and every open question.
- Tag each factual claim `[OBSERVED path:line]` or `[INFERRED]`.
