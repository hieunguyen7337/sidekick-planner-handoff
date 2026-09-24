# Dev arms for the 2026-09-24 review (R2.4, D2, D3, R7.1)

**All four arms are exploratory and dev only.** None is registered, none is a J10 arm, and no
number from them may be quoted as a held-out result. They answer reviewer objections G3, G4 and G9
in `docs/plan_top_venue_20260924.md`. Each config's header carries its source, the keys that
differ from it, and the submit line; `tests/unit/test_dev_arms.py` pins all three. Expected
hosted calls are the plan's estimates, not measurements.

Submit only once these files are committed in the plan worktree: `hj12_live.pbs` and
`hj1b_planner_alone.pbs` both run from there (`REPO`).

| Arm | Objection | Config | Expected hosted calls |
|---|---|---|---|
| R2.4, neutral advice at k = 1 | G3: the advice arm is a strawman | `configs/dev_advise_neutral_fixed_k_1_fullctx.yaml` | ≈ 2,170 [INFERRED from plan] |
| D2, structured-direction advice at k = 10 | G3, G8: prior-work advice baseline | `configs/dev_advise_structured_fixed_k_10_fullctx.yaml` | ≈ 300 [INFERRED from plan] |
| D3, planner alone at high effort | G4: weak ceiling | `configs/dev_planner_alone_cap81_high.yaml` | ≈ 1,700 [INFERRED from plan] |
| R7.1, no-op floor | G9: partial credit for doing nothing | `configs/dev_noop_complete.yaml` | 0 (CPU only, no vLLM) |

## What each arm is for

- **R2.4.** The k = 1 full-context advise arm under the B2 `neutral` prompt. So far the dev
  k = 1 advice point rests on the terse "needs a correction" wording alone.
- **D2.** The k = 10 full-context advise arm under a new `structured` prompt
  (`src/sidekick/agents/advice_styles.py`). The planner directs the executor as a manager directs a
  worker: GOAL, STEPS, CHECK. This is the ManagerWorker/Minions-style baseline.
- **D3.** HJ-13's cap-81 planner-alone ceiling with codex at `reasoning_effort: high`. It asks how
  much of the gap to a scaffolded agent is effort. The per-call bound is raised from the source's
  120 s to 300 s (= `planner.timeout_s`), so that slow high-effort calls are not censored as
  timeouts. The medium-effort source had 0 timeouts in 114 episodes (18 `limit`, 96 clean), so
  120 s never bound there. Disclose the change beside any D3 number.
- **R7.1.** `executor_alone` with a mock executor that answers `COMPLETE` at step 1. Its scores are
  what AppWorld credits for doing nothing, the floor against which `goal_pass` is read.

## Submit lines (Claude runs these; workers never do)

R2.4. Run it alone in its job: the `MAX_PLANNER_CALLS` default of 3,780 (`hj12_live.pbs:72`)
covers R2.4 only if R2.4 runs alone in its job, and the plan's 2,700 leaves room for no second arm.

    qsub -v ARMS="dev_advise_neutral_fixed_k_1_fullctx",DATE=20260924,MAX_PLANNER_CALLS=2700 /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/scripts/pbs/hj12_live.pbs

D2, in its own job:

    qsub -v ARMS="dev_advise_structured_fixed_k_10_fullctx",DATE=20260924 /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/scripts/pbs/hj12_live.pbs

D3 has no job-level ceiling; 81 calls × 114 episodes bound it. Submit it once: a resubmission
purges and re-rolls timeouts and parse errors (`--purge-broken`).

    qsub -l walltime=10:00:00 -o /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/dev_planner_alone_cap81_high_20260924.out -v CONFIG="/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/configs/dev_planner_alone_cap81_high.yaml",CID="dev_planner_alone_cap81_high_20260924",SEEDS="1,2" /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/scripts/pbs/hj1b_planner_alone.pbs

R7.1. The full `hpc --cpus 8 --mem 32gb --time 04:00:00 bash -c '...'` line is the one comment
line in the header of `configs/dev_noop_complete.yaml` that starts with `#   hpc`. It runs 57
tasks × seeds 1, 2 = 114 episodes, then summarizes the campaign.
