# A8 (U-CF) — a clean-counterfactual branch mode

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `scripts/setup/branch_counterfactual.py`,
`src/sidekick/systems/loop.py`, and tests under `tests/unit/`.
**Do not touch** `configs/`, `scripts/pbs/`, `scripts/setup/verify_configs.py`,
`scripts/setup/state_probe.py`, `scripts/setup/hj1_gate.py` — other units own those this cycle.

🔺 **Do not run any rollout, any GPU job, or any planner call.** This unit ends at code plus unit
tests on synthetic episodes. The job that uses it is submitted later, by the orchestrator, after
the quota resets.

## Why — this is the campaign's most load-bearing open question

The branch experiment measures
`Q(policy with intervention i present) − Q(policy with intervention i omitted)`
[OBSERVED scripts/setup/branch_counterfactual.py:758-760].

It does not currently measure that. Both arms set `skip_review_at_start=True`
[OBSERVED scripts/setup/branch_counterfactual.py:1029], which suppresses **only** the scheduled
review at the focal step `s` [OBSERVED src/sidekick/systems/loop.py:680-682]. Afterwards the
schedule runs live in both arms [OBSERVED scripts/setup/branch_counterfactual.py:748-752], so the
untreated arm receives a **near-substitute review ~5 steps later**. The contrast is therefore
*timing*, not *value*.

This was measured, not guessed. Train Spearman ρ(`n_later`, Δ) = **−0.163, permutation p = 0.0007**:
the more later reviews the untreated arm gets, the more the measured effect collapses. On the
clean subset (`n_later = 0`, 175 train points) the `needed` count clears its sign-flip null at
**p = 0.0051**, against **p = 0.712** on all points. ⚠ That subset is doubly post-hoc and **dev does
not reproduce the dose-response** (ρ = +0.095, n.s.). So this licenses a prospective pilot, which
is what your code makes possible — it does not license a claim.

## What to build

Add `--untreated-mode {schedule_live, suppress_next}` to `branch_counterfactual.py`.

- **`schedule_live`** — today's behaviour exactly. **It must remain the default**, and existing
  runs must be bit-identical under it. This is the frozen estimand; do not perturb it.
- **`suppress_next`** — in the **untreated arm only**, suppress the focal tick at `s` *and* the
  next scheduled review after it, isolating the intervention from its substitute. The treated arm
  is unchanged in both modes.

🔺 **The existing hook is not sufficient and you will have to extend the loop.**
`skip_scheduled` is `prefix.skip_review_at_start and step == start_step`
[OBSERVED src/sidekick/systems/loop.py:680-682] — it fires at the start step only. Suppressing
*the next one as well* needs a new field on the prefix dataclass
[OBSERVED src/sidekick/systems/loop.py:75-86]. Design it yourself, but:

- it must be **backward compatible** — default value reproduces today's behaviour, and
  `tests/unit/test_branch_counterfactual.py:335` must keep passing unchanged;
- prefer an explicit, readable field over overloading the existing boolean;
- **"the next scheduled review" means the next tick the schedule would actually have fired**, not
  "the step `s + review_every_k`". If the episode ends first, or the schedule would not have
  fired again, suppressing nothing is the correct behaviour. Make that explicit in a test.
- a router- or oracle-triggered review is **not** a scheduled review
  [OBSERVED src/sidekick/systems/loop.py:690-693]. State in your report whether your
  implementation suppresses those too, and why you chose that. Branch runs set
  `planner_drives: False` and `allow_executor_ask: False`
  [OBSERVED scripts/setup/branch_counterfactual.py:753-754], so in practice the scheduled tick is
  the live path — but say what you did rather than leaving it implicit.

## Record the mode in the output

`branch_config` is the provenance block written into every result
[OBSERVED scripts/setup/branch_counterfactual.py:739-765]. It currently hard-codes the
`review_every_k` and `estimand` strings describing the *live* behaviour. Both must become
mode-dependent and accurate, and `untreated_mode` must appear in the block.

🔺 A result file whose `estimand` string describes a contrast it did not run is exactly the class
of defect catalogued in `campaign/RUNS.md`. Getting this string right matters as much as the code.

## Tests

On **synthetic / mock** episodes only — no AppWorld, no rollouts:

1. `schedule_live` reproduces today's behaviour exactly (the existing test still passes untouched).
2. Under `suppress_next`, the untreated arm receives **zero** reviews after the focal step in a
   case where `schedule_live` would have given it one; the treated arm is identical between modes.
3. The end-of-episode case: schedule would not fire again → nothing suppressed, no crash.
4. `branch_config.untreated_mode` and the `estimand` string match the mode actually run.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Frozen inputs stay frozen.
- **Do not commit.** Suite baseline **365 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_8.md` with resume state per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- The new prefix field, its default, and why that default is backward compatible.
- Your decision on router/oracle-triggered reviews, and the reasoning.
- The exact `branch_config` block produced under each mode.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
