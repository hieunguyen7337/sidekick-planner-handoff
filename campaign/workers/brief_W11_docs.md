# W-11 — record Gate B's dev result and two new campaign hazards

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You are formatting and filing material that is already settled. **Do not recompute
anything, do not run any analysis, and do not change a single number below.** Every figure
here has been produced twice by two independent implementations and cross-checked. Your job
is placement, wording and consistency with the surrounding documents.

## Task 1 — `campaign/RUNS.md`: a Gate B (dev) result block

Add it beside the existing Gate A block, in whatever row/section style that file already
uses. Read the Gate A block first and match it.

Content to record:

- **Job**: `25412541.aqua`, campaign `hj6_branches_dev_20260917`, split dev, adapter `sft_b`,
  branch seeds 101/102, commit `dc92a25`.
- **Coverage**: 1527 of 1528 branches. 382 intervention points; 374 complete; 8 dropped
  (1 missing every sample, 7 with a null `branch_gpr`).
- **δ (delta band)** = 0.166, computed by the pre-registered rule — the 75th percentile of
  |treated[101] − treated[102]| over train points — on train's *partial* data as of
  2026-09-17 22:44. ⚠ Flag it clearly as **provisional**: δ is frozen from train and train is
  still running, so this value can move and every label below moves with it.
- **Labels** over the 374 complete points:

  | label | n | fraction | mean Δ |
  |---|---:|---:|---:|
  | needed | 59 | 0.157754 | +0.342686 |
  | needless (= harmful) | 53 | 0.141711 | −0.356472 |
  | ambiguous | 262 | 0.700535 | +0.004672 |

- **Mean Δ per point** = +0.006817. **1 − f = 0.8422** — the paper figure.
- **Validation**: factual outcome outside `[min(treated), max(treated)]` for 81 of 374 =
  0.216578.
- **Oracle allocation** (fire only at `needed`): +0.0541 per point against +0.0068 always-on,
  at 84.2 % fewer planner calls. ⚠ Record immediately beside it that this is **inflated by
  regression to the mean** and is not an achievable figure — see Task 2.
- **Cross-check**: recomputed from raw columns by a second worker type (luna, W-10) which was
  instructed not to read `scripts/setup/branch_counterfactual.py`. Agreement to ≥ 4 decimals
  on every statistic. Report: `campaign/workers/W10_RECOUNT.md`.
- **Negative control**: with δ unfrozen, all 381 rows return `label_status: incomplete`
  rather than a fabricated label.

Against the pre-registered Gate B thresholds: f_dev = 0.158 is **not** > 0.85, so the timer
is not almost-always-useful. `harmful` = 0.1417 is **just under** the 0.15 flag threshold —
record that it is close but did not fire. f_train is not yet final and is not reported here.

## Task 2 — `campaign/RUNS.md`: the label-reliability threat

This is the important one and it has no pre-registered home, which is itself the finding.
Record, in the Gate B block or immediately after it:

Split-half agreement between branch seeds 101 and 102 over the 374 complete dev points:
Pearson r = 0.163962, Spearman ρ = 0.222022, sign agreement 0.7024 over the 84 points where
both per-seed deltas are nonzero, and 56 points above band on both halves against 35.81
expected under independence (**1.56× chance**). Spearman-Brown on r = 0.164 gives the
two-replicate mean that the labels are cut from a reliability of **0.282**; four replicates
would give **0.440**.

State the reading plainly: the heterogeneity is **real** — 70 % sign agreement against a 50 %
null is not noise — but **weak**, with roughly 72 % of Δ's variance being sampling error.
Note that **Gate B's three pre-registered thresholds all concern f and none of them would
have caught this**, and that a reliability criterion is proposed for Gate B but has not yet
been approved by the user, so it is recorded as a proposal, not as a gate.

⚠ Earlier notes in the campaign quoted this co-occurrence as **2.3× chance** from partial
data. The full-dev figure is 1.56×. If you find the 2.3× figure written anywhere in
`campaign/` or `docs/`, correct it and note that it was superseded.

## Task 3 — `docs/FOLLOWUPS.md`: two new OPEN entries

Match the file's existing entry style.

**(a) A single wedged branch can idle a whole J6 job.** In `hj6_branches_dev_20260917`,
branch `fixed_k/2/37a8675_1__b2_untreated_s102` stopped writing events at 19:17 at step 34
and never returned. The other nine workers drained the queue by 20:59, so the job then held a
GPU for hours to accomplish nothing, and `rebuild_derived` — which only runs at the end —
never wrote `branches.jsonl`. There is no per-branch timeout. Note the two consequences:
aggregation is all-or-nothing at job end, and a wedged worker is invisible without comparing
`branch_runs.jsonl` line count against branch directory count. Suggested fixes to record (do
not implement): a per-branch wall-clock timeout that records an error row and moves on, and
a periodic incremental aggregation so a killed job still yields labels.

**(b) The J6 PBS stdout path also carries no campaign id.** There is already an OPEN entry
for the server log (`VLOG` → `${LOGDIR}/hj6_branches_vllm.log`). The same defect applies to
the job's `Output_Path`, which is
`campaign/workers/logs/hj6_branches.out` for every split. Both dev and train write it.
Add this to the existing entry rather than opening a second one if that reads better.
Record the concrete consequence observed: because both vLLM servers wrote the same log with
`>`, they overwrote each other at overlapping offsets, and the dev server's output appears to
stop at 19:33 when it had not — **the log was unusable for diagnosing the wedged branch
above**, and a reader could easily have concluded the server died.

## Constraints — read these, you are not covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. You should not need to compute at all for this unit.
- **Do not submit any job.** Three J6 jobs are live.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- Edit only `campaign/RUNS.md` and `docs/FOLLOWUPS.md`, plus any file carrying the superseded
  2.3× figure. Touch no code and no config.
- Write `campaign/workers/STATUS_W_11.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff.
- One line confirming whether the 2.3× figure existed anywhere and what you did about it.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
