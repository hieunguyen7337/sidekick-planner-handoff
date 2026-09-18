# A12 (U-A10) — the J10 analysis script, written and validated before J10 exists

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files are new: `scripts/analysis/j10_report.py` (name it as fits the tree's
convention — check whether `scripts/analysis/` exists first and follow the existing layout) and its
tests under `tests/unit/`.
**Do not touch** `src/`, `configs/`, `scripts/pbs/`, `scripts/setup/branch_counterfactual.py`,
`scripts/setup/state_probe.py`, `scripts/setup/hj1_gate.py`, `scripts/setup/verify_configs.py`,
`src/sidekick/systems/loop.py`, `docs/prereg_v1.md` — other units own every one of those this cycle.

## Why this is written now, months before the data

J10 is the **single** evaluation on `test_normal`. It runs **once**. Re-running an arm after
inspecting test results is a fatal protocol violation
[OBSERVED docs/prereg_v1.md:193, :70].

An analysis script written *after* seeing the test numbers is, in effect, a chance to choose the
analysis that flatters them — and a script debugged *against* the test set has already spent the
one look. So the script is written now and **validated end-to-end on dev archives**, which are
already fully inspected and carry no contamination cost. When J10 lands, the script runs once,
unmodified, and its output is the result.

🔺 **This is the deliverable: a script that is finished before the data exists.** If it needs
editing when it first meets real test data, this unit has failed at its actual purpose. Design for
that — validate on dev hard enough that the test run is uneventful.

## What it must compute

**Implement exactly what `docs/prereg_v1.md` specifies. Do not design the analysis.**

Read §2.2 (arms), §3 (hypotheses and decision rules), §7.2 (parameters frozen at J9), and the
contrast definitions. J10 is 168 `test_normal` tasks × the pinned arm list × **3 seeds**
[OBSERVED docs/prereg_v1.md:76]. Implement the pre-registered contrasts, the paired comparison
structure, the confidence intervals and the decision rules **as written**.

🔺 **Where the prereg is ambiguous, underspecified, or internally inconsistent, STOP and report
it. Do not resolve it yourself.** An ambiguity resolved silently in code is an unregistered
analysis decision, which is the thing the pre-registration exists to prevent. A list of such
ambiguities is a **more valuable** deliverable than a script that papers over them — several of
them may need to be settled at the J9 freeze, which has not happened yet. Expect to find some.

Match the conventions of the existing analysis code in the tree (`scripts/setup/hj1_gate.py`, the
bootstrap in `scripts/setup/branch_counterfactual.py`) rather than inventing new ones —
particularly the **clustering** of confidence intervals. Branch analysis clusters bootstrap
resamples by **task** [OBSERVED scripts/setup/branch_counterfactual.py:735-738]; paired seeds
within a task are not independent samples, and treating them as such would understate every
interval in the final report. State explicitly what your unit of resampling is and why.

## Two properties that must hold

1. **Missing data must not become zero.** This campaign's recurring defect is a harness that
   returns a believable number rather than failing: a run whose metric was never recorded gets
   coerced to 0 and averaged in as if it had scored zero. The project convention is that `None`
   means "not measured" and must never be coerced
   [OBSERVED src/sidekick/protocols/schemas.py:37]. Your script must **count and report** missing
   or crashed runs per arm, and must refuse to silently substitute. If an arm is incomplete, the
   report says so at the top, not in a footnote.

2. **It must be impossible to run this on `test_normal` by accident.** Require the split as an
   explicit argument and refuse to run on a test split without an explicit confirmation flag.
   Cheap to add; the failure it prevents is unrecoverable.

## Validation — this is the majority of the unit

Dry-run against the existing **dev** archives under
`/scratch/n12194778/sidekick/results/` (read-only; `hj3_*`, `hj4b_*` are dev campaigns with the
paired-seed structure J10 will have). Demonstrate:

- it produces a complete report from real archives, with no hand-editing;
- it handles a **missing arm**, a **crashed episode** and a **missing metric** correctly, each
  shown;
- unit tests on synthetic inputs where the right answer is known by construction — including at
  least one where the correct behaviour is to **refuse** rather than to compute.

Report the dev numbers it produces. ⚠ They are a **plumbing check, not a result** — dev has been
looked at many times and nothing there is evidence about the thesis. Label them that way so no
one later mistakes them for findings.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job** — a training job is
  running and the GPU queue is congested.
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Read archives; never write them.
- 🔺 **Do not read, analyse or report any `test_normal` or `test_challenge` data.** Dev only.
- **Do not commit.** Suite baseline **365 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_12.md` with resume state per milestone.
- Report → `campaign/workers/A12_J10_ANALYSIS.md`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The script, its tests, and the dev dry-run output as emitted.
- 🔺 **The list of prereg ambiguities you found and did NOT resolve** — with the `path:line` of
  each. Explicitly say "none" if none, but look properly first.
- Your resampling unit for confidence intervals, and the justification.
- How missing/crashed runs are counted and surfaced.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
