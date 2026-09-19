# A20 (U-B1PBS) — the B1 pilot PBS harness, built before the quota returns

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: a new `scripts/pbs/b1_pilot.pbs`, and a report at
`campaign/workers/A20_B1_PBS.md`.
**Do not touch** `docs/prereg_b1_pilot.md` (committed and frozen — it is the pre-registration),
`scripts/setup/branch_counterfactual.py`, `campaign/workers/scratch_A16/run_b1_pilot.py`,
`src/`, `configs/`, or any other `scripts/pbs/` file.

🔺 **Zero planner calls. Do not invoke `codex`. Do not submit this job or any GPU job.** The
planner quota is exhausted until ~21:13 today and B1's entire budget is what would be spent. You
are building and statically validating the harness, not running it.

## Why this unit exists

`docs/prereg_b1_pilot.md` §13 specifies the submission but deliberately does not build it: A16 was
forbidden from touching `scripts/pbs/`. So the pre-registration is committed (`a4fc75d`) and there
is **no script to submit** [OBSERVED: `ls scripts/pbs/` has no B1 entry]. That is the last gap
between the quota reset and the pilot.

## What to build

`scripts/pbs/b1_pilot.pbs`, modelled on `scripts/pbs/hj6_branches.pbs`. **Read that script first
and keep its structure**: the vLLM block, the LoRA alias registration, and the preflight auth
checks. Match its idiom rather than inventing a new one.

The invocation is fixed by the committed prereg §13 and **must be reproduced exactly** — the flags,
the branch seeds `101 102 103 104`, `--delta-band-delta 0.166`, `--untreated-mode suppress_next`,
`--max-planner-calls-total 10000`, and the wrapper
`campaign/workers/scratch_A16/run_b1_pilot.py`. Do not "improve" any of them. If you believe one is
wrong, **report it and implement as specified anyway** — that document is the experiment's
integrity and changing it after commit would destroy the value of having committed it first.

Parameters, from §13: `CID=b1_pilot_train_20260919`,
`CAMPAIGN_ROOT=/scratch/n12194778/sidekick/results/hj4_correction_train_20260917`,
`CFG=configs/hj4_correction.yaml`, `OUT=/scratch/n12194778/sidekick/results/${CID}`,
adapter `sft_b_s123_granite8b` aliased `sft_b`, `--workers 10`, `--resume`.

### Three guards, each of which has already caught a real defect here

1. 🔺 **FATAL if `PREFLIGHT`'s `branches_to_run` is not 1600.** The prereg says so explicitly: "If
   `branches_to_run` is 6216, kill the job; the wrapper was not used"
   [OBSERVED docs/prereg_b1_pilot.md:288]. 6,216 is the *whole* J6 train frame; launching that
   instead of the frozen 200-point sample would spend the cap in minutes on the wrong population.
   Parse the `PREFLIGHT` JSON line, assert `branches_to_run == 1600` and
   `max_planner_calls_total == 10000`, and abort before any branch dispatches if either differs.
   Do not merely print them.
2. 🔺 **FATAL if the out-root is, or is inside, `hj6_branches_train_20260917`.** That tree holds the
   frozen J6 `schedule_live` data the mode-to-mode comparison depends on. Writing into it would
   destroy the comparison silently.
3. 🔺 **FATAL if `--untreated-mode suppress_next` is absent from the assembled command.** Defaulting
   to `schedule_live` would run the *contaminated* estimand under the clean estimand's campaign id,
   and the manifest would then name a contrast it did not run. That is the exact defect class this
   campaign catalogues.

Write these as independent checks on the assembled command and on the job's own output — not as
comments, and not as assumptions that the wrapper does it. A13 added precisely this kind of
independent guard to `hj8_frontier.pbs` and it caught a weightless LoRA that the previous check
had waved through.

### `SMOKE_ONLY`

Support `SMOKE_ONLY=1`, as `scripts/pbs/hj8_frontier.pbs` does. It runs a **very small** number of
branches (2 points is enough), confirms the live planner path works end to end, prints the spend,
and **stops before the full campaign** without purging or writing into the real campaign tree. The
plan requires a live smoke before B1 commits its budget: everything built since the quota ran out
is unverified against a live planner [OBSERVED docs/PLAN.md open risk 4]. This is how that gets
done for a handful of calls rather than 6,118.

### Sizing

The wrapper carries `timeout 35100` (~9.75 h), so PBS walltime must exceed it — size it at
`10:00:00` or above and say what you chose. Take the GPU/cpu/mem shape from `hj6_branches.pbs`;
do **not** pin `qlist=gpu_inter_exec` in `select`, which makes a job Can Never Run under site
policy.

## Validation — without running it

- `qsub -h` is **not** acceptable as a check, and neither is submitting it. Validate statically:
  shell-parse the script (`bash -n`), confirm every referenced path exists, and confirm the
  assembled command string matches prereg §13 flag for flag. Show that comparison in your report.
- Exercise the three guards with a **harness test** that feeds each one a bad input (a `PREFLIGHT`
  line with `branches_to_run: 6216`, an out-root under `hj6_branches_train_20260917`, a command
  missing `--untreated-mode`) and asserts it aborts. A guard that has never been shown to fire is
  not a guard. Put this under `campaign/workers/scratch_A20/` if a unit test does not fit the
  suite's shape; say which you chose and why.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, **synchronously**:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`. A job returning in ~1s has crashed;
  read its output before believing it. **Never background a job and exit.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **413 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_20.md` as your first action, updated per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- `scripts/pbs/b1_pilot.pbs` as written, and the `bash -n` result.
- The flag-for-flag comparison against committed prereg §13.
- Each of the three guards firing on a bad input — quote the assertions.
- The walltime and resource shape you chose, and why.
- Anything in §13 you believe is wrong: **report it, implement as specified anyway.**
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
