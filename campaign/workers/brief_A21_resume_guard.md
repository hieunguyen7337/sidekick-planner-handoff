# A21 (U-B1PBS2) — the 1600-branch guard must permit the resume the prereg requires

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `scripts/pbs/b1_pilot.pbs`, its guard harness under
`campaign/workers/scratch_A20/`, and a report at `campaign/workers/A21_RESUME_GUARD.md`.
**Do not touch** `docs/prereg_b1_pilot.md` (committed, frozen — it is the pre-registration),
`scripts/setup/branch_counterfactual.py`, `campaign/workers/scratch_A16/run_b1_pilot.py`, `src/`,
`configs/`, or any other `scripts/pbs/` file.

🔺 **Zero planner calls. Do not invoke `codex`. Do not submit this job or any GPU job.** Quota is
exhausted until ~21:13 today and B1's whole budget is what would be spent.

## The conflict, which your predecessor found and correctly refused to paper over

A20 built `scripts/pbs/b1_pilot.pbs` with a guard that aborts unless PREFLIGHT reports exactly
1600 branches. It then reported the clash rather than silently widening it
[OBSERVED campaign/workers/A20_B1_PBS.md:163] — that was the right call, and this unit is the
resolution, not a correction of it.

The clash is real. I verified it myself:

```
if resume and key in done:
    continue
```
[OBSERVED scripts/setup/branch_counterfactual.py:1177-1178]

So on a resume `branches_to_run` is the **remainder**, not 1600. But the committed prereg requires
resume to work: §13's command carries `--resume` [OBSERVED docs/prereg_b1_pilot.md:280], and §9's
budget-stop rule says to "resume after quota (same out-root, same cap or a newly preregistered cap)
until 1,600 have been dispatched" [OBSERVED docs/prereg_b1_pilot.md:207]. With a strict `== 1600`
guard, a budget-stopped run can never be resumed and the prereg's own stopping rule is
unexecutable. Since B1 is expected to cost ~6,118 calls against a 10,000 cap, a budget stop is not
a remote possibility.

## The fix — guard the sample's identity, not the count

The property actually worth protecting is **"this run is the frozen 200-point sample, not the 6,216
J6 train frame."** The count 1600 was a proxy for that, and the proxy breaks on resume. Replace it
with a check that holds in both cases:

- **Fresh out-root** (no `branch_runs.jsonl`, or it holds zero completed branch keys):
  `branches_to_run` must be **exactly 1600**. Unchanged from A20.
- **Resume** (a non-empty `branch_runs.jsonl` exists): `branches_to_run` must be **< 1600**, and
  `completed + branches_to_run` must be **exactly 1600**. Read the completed count the same way the
  script does — `completed_branch_keys(load_jsonl(out_root / "branch_runs.jsonl"), ...)`
  [OBSERVED scripts/setup/branch_counterfactual.py:1142-1147] — do not re-implement the key logic
  or count raw lines, because retried errors are not completions.
- **Either way**, `max_planner_calls_total` must still be exactly 10000, and 6216 must still be
  fatal. Those do not change.

🔺 **This must not become "anything that isn't 6216 is fine."** The arithmetic identity
`completed + to_run == 1600` is the whole point: it is what proves the resumed run is finishing the
*same* frozen sample rather than a different one. A guard that only excludes 6216 would pass a run
against any other campaign root, which is exactly the failure it exists to prevent.

⚠ If `completed + branches_to_run` is **more** than 1600, that is a different and worse condition
than a resume — it means the out-root already holds branches that are not from this sample. Abort
with a message that says so specifically, not with the generic mismatch message.

## Also fix, while you are here

A20 reported that the job's stdout does **not** begin with `PREFLIGHT` because the vLLM block runs
first, so the prereg's §13 confirmation instruction reads oddly
[OBSERVED campaign/workers/A20_B1_PBS.md]. The guard already greps for the line rather than
requiring it first, which is correct behaviour — **leave the guard alone**. Instead make the script
**echo the parsed PREFLIGHT values in a single clearly-marked line** so an operator following §13
can confirm them at a glance without reading the vLLM output. Do not edit the prereg to match.

## Tests

Extend the existing guard harness under `campaign/workers/scratch_A20/`, matching how A20 built it —
each case feeds the guard an input and asserts it aborts or passes:

1. Fresh tree, `branches_to_run: 1600` → passes.
2. Fresh tree, `branches_to_run: 6216` → aborts (unchanged).
3. Fresh tree, `branches_to_run: 1400` → aborts. A short *fresh* run is not a resume.
4. Resume with 200 completed and `branches_to_run: 1400` → passes.
5. Resume with 200 completed and `branches_to_run: 1500` → aborts (1700 ≠ 1600).
6. Resume where `completed + to_run` exceeds 1600 → aborts with the **specific** foreign-branches
   message, and assert on that message, not just on the abort.
7. `max_planner_calls_total` ≠ 10000 → aborts, in both fresh and resume paths.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, **synchronously**:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`. A job returning in ~1s has crashed;
  read its output before believing it. **Never background a job and exit.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **413 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_21.md` as your first action, updated per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff to `scripts/pbs/b1_pilot.pbs`, and `bash -n` rc.
- All seven guard cases, with the abort/pass line each produced — quoted.
- The foreign-branches message, verbatim.
- Confirmation that 6216 and a wrong cap are still fatal on both paths.
- If you think identity-by-arithmetic is the wrong invariant, **say so with your reasoning and
  implement it as specified anyway.**
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
