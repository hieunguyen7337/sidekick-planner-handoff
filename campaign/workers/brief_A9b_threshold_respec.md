# A9b (U-J7, re-issue) — re-specify the verifier threshold against the attenuation ceiling

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Read the original brief first

**The analysis specification is in `campaign/workers/brief_A9_threshold_respec.md`. Read it now
and follow it in full.** This file adds only the mechanics that killed the first attempt, plus one
update. Everything in the original brief still applies: the scope limits, the file ownership, the
"do not resolve the prereg ambiguity yourself" rule, and the return contract.

## Why this is a re-issue — and what to do differently

The first attempt **produced nothing at all**. It submitted a PBS job, then reported "root agent
idle; waiting up to 5s for 1 background task(s)" and exited. The job itself failed too:
`25451920.aqua` ended `Exit_status = 1` after `resources_used.walltime = 00:00:01`
[OBSERVED qstat -fx 25451920.aqua] — it died on startup, almost certainly a script error rather
than anything about the analysis.

So, three mechanics rules:

1. 🔺 **Run jobs synchronously. Never background one and exit.** `hpc` waits for the job and
   returns its output:
   `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`
   Use exactly that shape. Do not submit with `qsub` and poll; do not detach anything.
2. 🔺 **A job that finishes in ~1 second has crashed, not succeeded.** Always read the job's
   output before using its results. If it exits non-zero, print the traceback and fix it — do not
   proceed as though the numbers arrived.
3. **Write your output files incrementally.** Write `campaign/workers/STATUS_A_9.md` in your first
   three actions and update it at each milestone, and save partial analysis to
   `campaign/workers/A9_THRESHOLD.md` as you go. The first attempt lost everything because both
   files only existed at the end. If you die halfway, the next worker should be able to resume.

A likely cause of the 1-second crash, worth checking before you re-run anything: the interpreter
must be `/scratch/n12194778/sidekick/env/bin/python` and imports need
`PYTHONPATH=src:.` from the repo root. A script that assumes the ambient interpreter fails
instantly. ⚠ Note also that a diagnostic run by a sibling unit hit
`AttributeError: module 'inspect' has no attribute 'signature'` when a **local scratch file was
named in a way that shadowed a stdlib module** — do not name a scratch script `inspect.py`,
`types.py`, `json.py` or similar, and run it from a directory that contains no such shadowing file.

## One update since the original brief was written

The sibling value-function unit has **landed** and is committed (`b6af8f4`). Its worked precedent
is now real and inspectable, not prospective:
`artifacts/verifiers/value_fn_20260919/metrics.json` reports dev AUROC **0.6212** against a
feature-blind step-prior floor of **0.6245** and a k-NN ceiling proxy of **0.6356**, with the
reasoning in `campaign/workers/A7_VALUE_FUNCTION.md`. Read both. **Reporting a floor alongside the
ceiling is the part to copy** — that pairing is what turned an uninterpretable 0.62 into a
finding, and J7's 0.59 needs the same treatment.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, synchronously, per rule 1 above.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job** — a training job is
  running and the GPU queue is congested.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Analysis and documentation only: no refit, no retraining, no new artifact.
- **Do not touch** `src/`, `configs/`, `scripts/`, `campaign/RUNS.md`, `docs/PLAN.md`,
  `docs/HEAVY_JOBS.md` — other units own those. Your only proposed code/doc change is the J7
  threshold wording in `docs/prereg_v1.md`, and even that is a **proposal in your report**, not a
  silent edit.
- Suite baseline is **365 passed, 1 skipped** and you should not affect it.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

As in the original brief. Restated briefly so it cannot be missed:

- The ceiling derivation, assumptions stated, and my √0.45 ≈ 0.67 heuristic **explicitly checked**
  rather than repeated — AUROC is not a correlation, so justify the scale translation or replace it.
- J7's 0.59 restated against ceiling **and floor**, with an interval.
- The plain-language corrected reading, one paragraph: near-ceiling, mid-range, or genuinely weak?
- Proposed prereg wording that **discloses** it was revised with knowledge of the result.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
