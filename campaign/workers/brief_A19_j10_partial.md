# A19 (U-J10B) — `j10_report.py`: a partial-matrix mode, and `goal_pass_rate` as a first-class metric

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `scripts/analysis/j10_report.py` and
`tests/unit/test_j10_report.py`.
**Do not touch** `src/`, `configs/`, `scripts/pbs/`, `scripts/setup/`, `docs/`, `campaign/RUNS.md`.

🔺 **Create both files' edits within your first three actions, then iterate with tests.** Write
`campaign/workers/STATUS_A_19.md` first, updated per milestone, with enough resume state that a
fresh session could continue.

🔺 **Do not run any rollout, GPU job, branch or planner call. Do not invoke `codex`.** Quota is
exhausted until ~21:13 today. This unit is CPU-only: read archives, compute, test.

## Why this unit exists

`j10_report.py` was written before J10's data exists, which was right. It has now had its first
contact with real data — the two J8a arms — and A15 used it successfully but found two limits
[OBSERVED campaign/workers/A15_J8A.md:55-88]:

1. **It never reads `goal_pass_rate`.** `grep -n 'goal_pass' scripts/analysis/j10_report.py`
   returns **zero matches** — I verified this myself. Yet goal-pass-rate is a headline outcome:
   on J8a it moved **+17.11 pp**, CI [10.36, 23.74], alongside TGC's +27.19 pp
   [OBSERVED campaign/workers/A15_J8A.md]. A J10 report that cannot express it is incomplete.
2. **It only emits contrasts once the full J10 arm matrix is present**, and only as `sidekick − *`
   [OBSERVED scripts/analysis/j10_report.py:55-62, 967-969, 1045-1063]. So a two-arm or
   partial look — J8a, and every B2 staging look — cannot use it, and A15 had to write a
   throwaway helper.

A15's own recommendation is the design here [OBSERVED campaign/workers/A15_J8A.md:75-88].

## What to build

**1 · `goal_pass_rate` as a first-class metric, everywhere TGC already is.** Per-arm summary,
per-cell inventory, and every contrast. Source it the same way the existing code sources its
per-episode fields; do not invent a new loader. ⚠ `goal_pass_rate` is **missing from older
campaign `runs.jsonl` but present per-episode in `result.json`** — that trap is already recorded
[OBSERVED docs/PLAN.md, A7's loader notes]. Handle a missing value by **dropping the cell from the
goal-pass contrast and counting the drop**, never by coercing to 0.0. Silent zeros via
`float(... or 0.0)` are a defect this campaign has already fixed once in `hj1_gate.py`.

**2 · An explicit partial-matrix mode.** When the caller names the arms, inventory exactly those
and emit **pairwise** contrasts between them, each with a task-clustered bootstrap CI, for both
TGC and `goal_pass_rate`. Use the existing `paired_diff(..., resample="task")` — resampling by
task, because paired seeds within a task are not independent.

🔺 **Two hard constraints on this mode:**

- **Do not fabricate or alias arms.** Specifically, never alias `sft_plan` as `sidekick` to satisfy
  the matrix. That is the A12 stand-in trick and it would mislabel the contrast as the thesis's
  headline result [OBSERVED campaign/workers/A15_J8A.md:87-88].
- **The full-J10 path must keep refusing an incomplete matrix.** Its `INCOMPLETE ... missing_arm`
  refusal and its `k_matched_not_supplied` refusal are **correct behaviour** and are why the script
  can be trusted on the test set — it declined to invent `k_matched` rather than guess
  [OBSERVED campaign/workers/A15_J8A.md:51-55]. Partial mode is an explicitly-requested
  *separate* mode, not a relaxation of the default. A caller who asks for the J10 report and
  supplies an incomplete matrix must still be refused, with the same message.

**3 · Label partial output as what it is.** Anything emitted in partial mode carries a marker that
it is not the J10 result — follow the existing `PLUMBING CHECK, NOT A RESULT` convention the script
already uses rather than inventing a new one.

## Tests

Extend `tests/unit/test_j10_report.py`, matching its existing fixture style:

1. Partial mode on two synthetic arms emits both a TGC and a `goal_pass_rate` contrast, with CIs.
2. Full-J10 mode **still refuses** an incomplete matrix, and still refuses when `k_matched` is
   absent — assert the existing refusals have not regressed. This is the important one.
3. A cell missing `goal_pass_rate` is **dropped and counted**, not read as 0.0; assert the count is
   reported.
4. Partial mode never emits an arm the caller did not name.
5. The existing tests pass untouched.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, **synchronously**:
  `timeout 1500 hpc -c 4 -m 16gb -t 00:25:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`. A job returning in ~1s has crashed;
  read its output before believing it. Never background a job and exit.
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Read the campaigns; never write them.
- 🔺 **Do not read, analyse or report any `test_normal` or `test_challenge` data.** J10 is the
  test-set analysis and its data must be read exactly once, later, not by this unit.
- **Do not commit.** Suite baseline **408 passed, 1 skipped** — never fewer, never a failure.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff and the full test output as emitted.
- The refusal test quoted — the one asserting full-J10 mode still refuses an incomplete matrix.
- How a missing `goal_pass_rate` is handled, and the field you read it from.
- If you think the partial mode weakens the script's J10 guarantees, **say so** and implement it as
  specified anyway.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
