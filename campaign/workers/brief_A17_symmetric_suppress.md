# A17 (U-CF2) — `suppress_next` must suppress in BOTH arms, not just the untreated one

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `scripts/setup/branch_counterfactual.py`,
`src/sidekick/systems/loop.py` if needed, and `tests/unit/test_branch_counterfactual.py`.
**Do not touch** `configs/`, `scripts/pbs/`, `scripts/analysis/`, `docs/prereg_b1_pilot.md`,
`campaign/RUNS.md` — another unit updates the prereg after you land.

🔺 **Do not run any rollout, GPU job or planner call.** Code and unit tests only. Nothing has been
submitted under the current semantics, so there is **no data to preserve** and no reproducibility
break.

## The defect — my specification was wrong, not your predecessor's implementation

A8 implemented exactly what its brief said, and the brief was wrong.

```python
skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT and job["condition"] == "untreated"
```
[OBSERVED scripts/setup/branch_counterfactual.py:1022]

The suppression fires **only in the untreated arm**. Work through what the two arms then receive,
with the focal step `s` and the next scheduled tick `t`:

| mode | treated | untreated | difference |
|---|---|---|---|
| `schedule_live` | inject at `s`, review at `t` | nothing at `s`, review at `t` | intervention `i`, **partly substituted by `t`** |
| `suppress_next` (current) | inject at `s`, **review at `t`** | nothing at `s`, **no review at `t`** | intervention `i` **plus a whole extra review** |

So the current mode does not isolate the intervention — it hands the treated arm one more review
than the untreated arm. Δ becomes "the value of an intervention *and* a review" rather than "the
value of an intervention".

🔺 **Why this would have produced a false positive.** J8a measured `sft_plan` beating
`executor_alone` by **+27.19 pp** TGC, CI [16.67, 37.72]
[OBSERVED campaign/workers/A15_J8A.md]. That reviews help is therefore already established and
large. Under the asymmetric mode, the pre-registered B1a test (mean Δ > 0) could pass on that
effect alone, while saying nothing whatever about intervention `i`. In a pre-registered experiment
that is the worst kind of bug: it produces a confident, wrong, *positive* result.

## The fix

**Suppress the next scheduled review in BOTH arms.** Then:

| mode | treated | untreated | difference |
|---|---|---|---|
| `suppress_next` (fixed) | inject at `s`, no review at `t` | nothing at `s`, no review at `t` | **intervention `i` alone** |

The substitute is removed from both arms, so it cannot stand in for the missed intervention, and
the arms stay otherwise identical. Ticks after `t` remain live in both — that is intended and
symmetric, so it does not confound the contrast.

**Redefine `suppress_next` in place rather than adding a third mode.** No campaign has ever run
under the current semantics, and leaving an asymmetric variant in the tree is a footgun for
exactly the reason above. `schedule_live` remains the default and must stay **bit-identical**.

## What must follow the change

- The `_REVIEW_EVERY_K_SUPPRESS_NEXT` and `_ESTIMAND_SUPPRESS_NEXT` provenance strings
  [OBSERVED scripts/setup/branch_counterfactual.py:75-87] currently describe the untreated-only
  behaviour. They must describe what the code now does. 🔺 A result file whose `estimand` string
  describes a contrast it did not run is the defect class this campaign catalogues — get these
  exactly right.
- The module docstring [OBSERVED scripts/setup/branch_counterfactual.py:5-15] and the
  `EpisodePrefix` docstring in `loop.py` [OBSERVED src/sidekick/systems/loop.py:75-91] both say the
  suppression is untreated-only. Fix both.
- Keep `schedule_live` frozen: its strings are quoted by existing manifests and must not change.

## Tests

Extend `tests/unit/test_branch_counterfactual.py`:

1. Under fixed `suppress_next`, **both** arms skip the tick at `t`; assert it for the treated arm
   specifically, since that is the bug.
2. The treated and untreated arms differ **only** by the injected correction at `s` — no
   difference in the set of scheduled reviews either receives.
3. Ticks after `t` still fire, in both arms.
4. `schedule_live` is unchanged and the existing test still passes untouched.
5. The `branch_config` `estimand` string matches the mode actually run.

## One thing to check and report, not fix

A sibling unit established that `suppress_next` does **not** make `n_later = 0` by construction:
later ticks after `t` stay live, so an untreated branch can still receive reviews at `t + k`,
`t + 2k`, … [OBSERVED campaign/workers/A16_B1_PREREG.md:118]. That is expected and, once the fix
above is in, **symmetric** between arms — so it no longer contaminates the contrast, though it
does mean the pilot is not reproducing W-25's `n_later = 0` selection exactly.

**Report how many later ticks a typical branch would still receive** under the fixed mode, from
the frozen inputs, so the prereg can state the residual honestly. Do not change the design to
chase `n_later = 0` — suppressing the whole remaining schedule would confound the intervention
with the entire rest of the review policy.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, **synchronously**:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any job.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **406 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_17.md` in your first three actions.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff and the test output as emitted.
- The test that specifically asserts the **treated** arm skips `t` — quote it.
- The corrected provenance strings, verbatim.
- The typical residual `n_later` under the fixed mode.
- If you believe the symmetric design is wrong, say so with your reasoning and implement it as
  specified anyway.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
