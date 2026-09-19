# A18 (U-B1PRE2) — correct the B1 prereg for the now-symmetric `suppress_next`

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `docs/prereg_b1_pilot.md` and a short report at
`campaign/workers/A18_PREREG_SYMMETRIC.md`.
**Do not touch** `src/`, `configs/`, `scripts/`, `campaign/RUNS.md`, or any other `docs/` file.

🔺 **Do not run any rollout, GPU job, branch or planner call. Do not invoke `codex`.** Quota is
exhausted until ~21:13 today and this pilot's own budget is what would be spent.

## What changed under the document

`docs/prereg_b1_pilot.md` was written against A8's `suppress_next`, which suppressed the next
scheduled review **in the untreated arm only**. That was a design defect — my specification error,
not A8's implementation — and A17 has now fixed it. The suppression is **symmetric**: both arms
skip the scheduled tick at `s` and the next tick the schedule would actually have fired after `s`.

```
skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT
```
[OBSERVED scripts/setup/branch_counterfactual.py:1022 — the `and job["condition"] == "untreated"`
gate is gone]

Why it mattered: under the asymmetric mode the treated arm kept a review the untreated arm lost,
so Δ measured *the intervention plus one extra review*. J8a measured reviews at **+27.19 pp** TGC,
CI [16.67, 37.72] [OBSERVED campaign/workers/A15_J8A.md], so B1a could have passed on that alone —
a confident false positive in a pre-registered test. Under the symmetric mode the substitute is
removed from both arms and the only remaining difference is the injected correction at `s`.

**Nothing has run under either semantics.** Zero manifests carry `untreated_mode: suppress_next`
[OBSERVED docs/prereg_b1_pilot.md:50, job 25463506.aqua]. So this is a correction made before the
data exists, which is the only kind that is free.

## The edits — surgical, not a rewrite

This document is good and its structure is settled. Change what is now false and **nothing else**.
Do not re-tune the hypotheses, the decision rule, the point list, δ, or the cost cap.

1. **§1, line 22** — "suppresses, in the untreated arm only … The treated arm is unchanged" is now
   false. State the symmetric behaviour and cite `:1022`.
2. **§1, line 24** — the recorded "specification clash" is now **two** clashes and the first one
   has been resolved by a code change rather than by a caveat. Rewrite so it records, in order:
   (a) the brief's `n_later = 0` "by construction" claim, still wrong, still handled by the
   manipulation check; (b) the arm-asymmetry defect, now **fixed** by A17. Keep the habit of
   recording rather than silently fixing — but say plainly that (b) was fixed in code.
3. **§7 item 4, line 142 — the manipulation check.** It is currently specified on the untreated
   arm alone. Under symmetric suppression it must also verify the **treated** arm lost its tick at
   `t`, because that is exactly the bug that was fixed and a regression would be invisible
   otherwise. Add: report the arms' later-review counts **separately**, and state that they should
   be equal in distribution. Keep it secondary; it still does not gate.
4. **§12 item 1, line 234** — update for the fix, keeping the true part: one future tick is
   suppressed, not every later review, so `n_later = 0` is still not guaranteed.
5. **§8, line 178** — "`suppress_next` can only *reduce* untreated live reviews relative to J6" now
   applies to **both** arms, so 6,118 is, if anything, a slightly more conservative centre than
   before. Adjust the sentence; **do not change the 6,118 figure or the 10,000 cap.**
6. **Add the residual `n_later` measurement**, which A17 produced from the frozen 200-point list
   and which the document currently lacks. Verbatim, from
   [OBSERVED campaign/workers/STATUS_A_17.md]:
   - point-level median of `max(0, n_later − 1)` on the frozen 200: **median 0.0**, mean 0.235,
     min 0, max 4; 161/200 points at 0;
   - replicate level (800 untreated rows): median 0.0, mean 0.47125, 607/800 at 0;
   - **if** a branch ran to `max_steps = 40`, the live schedule after `t` still has median **5**
     remaining ticks — that is the policy remainder, not what J6 lived long enough to receive.
   - ⚠ Mark this a **length-held-fixed proxy**: it is computed from J6 `schedule_live` replicates,
     and if skipping `t` changes when an episode ends the residual changes with it. No
     `suppress_next` data exists. A17 tagged this `[INFERRED]`; keep that honesty.
   Put it in §7 beside the manipulation check, or in §12; your judgement.
7. **The `Status:` line at the top** must remain accurate: still frozen-before-submission, but now
   note that it was corrected on 2026-09-19 for the symmetric fix, before any data existed.

## What must NOT change

- The primary hypotheses B1a and B1b, the decision rule including the inconclusive branch, δ =
  0.166, 10,000 permutations, the 200-point frozen list and its appendix, the primary population
  definition, the falsifier, and the submission command's flags other than any that are now wrong.
- The document must not become *more* confident because a defect was fixed. Removing a
  false-positive pathway improves the test's validity; it says nothing about whether the effect is
  real. If any sentence now reads as strengthened expectation, weaken it back.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. Any computation goes in a PBS job, **synchronously**:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread. A job
  that returns in ~1 second has crashed; read its output before believing it. Never background a
  job and exit.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **408 passed, 1 skipped**; a docs-only unit must not affect it.
- Write `campaign/workers/STATUS_A_18.md` in your first three actions.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff of `docs/prereg_b1_pilot.md` as applied.
- The corrected §1 paragraph and the corrected manipulation check, quoted.
- Confirmation that the hypotheses, decision rule, δ, cap and point list are byte-unchanged —
  and if any of them did change, say exactly which and why.
- Anything you believe is still wrong in the document: **say so rather than silently adjusting it.**
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
