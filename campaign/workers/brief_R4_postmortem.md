# R4 — the 2026-09-19 collision: post-mortem, discard record, and the B1 budget amendment

Repo (absolute, a git worktree — work here, do not cd elsewhere):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

This is a **documentation unit**. You write prose from facts supplied below and verified by you
in the tree. You change no code, run no jobs, and submit nothing.

## Files you own — and only these

- `docs/FOLLOWUPS.md` — append one entry
- `campaign/RUNS.md` — append a discard record
- `README.md` — fix the stale lines at `:30-31`
- `docs/prereg_b1_pilot_amendment_20260920.md` — **new file**

**Out of scope, owned by other workers running in parallel right now — do not touch:**
`scripts/pbs/*`, `src/sidekick/*`, `scripts/setup/*`, `scripts/analysis/*`, `tests/*`.
**`docs/prereg_b1_pilot.md` is FROZEN. Read it; never edit it.** That is the entire point of the
amendment file: the pre-registration was committed before the data existed so the experiment
could not be renegotiated afterwards, and editing it now would spend exactly that.

## The facts (verify each against the tree before you write it)

Two GPU jobs were submitted in parallel on 2026-09-19 and both were destroyed by one
infrastructure defect.

- Job `25519712` (B1 pilot smoke) and job `25519749` (J8 live smoke) both started at 23:45:45 on
  node `gpu0n007`. Logs: `campaign/workers/logs/b1_pilot_train_20260919.25519712.aqua.out`,
  `campaign/workers/logs/hj8_frontier_live_20260919livesmoke.25519749.aqua.out`.
- Every GPU PBS script pins vLLM to `--host 127.0.0.1 --port 8000`, and the health check only
  probes the port. vLLM 0.29 does not hard-fail the bind loser — both servers printed
  `Application startup complete`; J8's owned the socket, B1's served nothing. B1's own vLLM log
  (`/scratch/n12194778/sidekick/logs/b1_pilot_train_20260919.25519712.aqua_vllm.log`, around
  line 111) names the winning process as the port owner, and that line was ignored.
- B1's branches requested LoRA alias `sft_b`; the server they actually reached had only
  `sft_b_plus` registered. Result: 20 × `404 The model 'sft_b' does not exist`, and
  `branch_error_type: "crash"` on 20 of 20 rows with zero planner tokens.
- B1's cleanup ran `pkill -f "vllm serve"` and `pkill -f "EngineCore"` — **node-wide** — which
  killed J8's server at 23:48:18, mid arm 1. J8 arm 1 had by then completed 5 executor calls and
  2 live planner interventions with recorded usage and `returncode: 0`, so the J8 live path
  itself is sound. Arms 2 through 10 ran after the server was dead and failed at step 1.
- The same `pkill` pair exists in `scripts/pbs/hj6_branches.pbs:131-132` and
  `scripts/pbs/hj3_eval.pbs:125-126`, and the hardcoded port 8000 appears in `hj4_correction.pbs`,
  `hj4b_fixed_k_dev.pbs`, the `hj1*` scripts and `hj15_state_probe.pbs`. **These are deliberately
  not being fixed** — they are not being resubmitted — so the hazard must be recorded as a live
  one that any future resubmission of those scripts has to clear first.

Second defect, independent of the collision:

- The B1 smoke gate counted rows and summed a field, never reading `branch_error_type`. It
  printed `n_rows=20 branch_planner_calls_sum=88 unknown_call_rows=0` and **exited 0** on a run
  in which every branch had crashed and no live planner call had been made. The 88 were replayed
  cached review ticks.

Third defect, found from those rows:

- `--max-planner-calls-total` sums `branch_planner_calls`
  [`scripts/setup/branch_counterfactual.py:1291`, `:1297-1318`], which is `RunResult.n_planner_calls`
  [`:883-905`], which `counters_from_events` [`src/sidekick/systems/loop.py:119-133`] computes
  over the prefix **including replayed interventions**. The pre-registration's budget is live
  hosted-planner spend: expected 6,118 against a cap of 10,000
  [`docs/prereg_b1_pilot.md:158-199`; the unknown-call charge of 81 is at `:194`]. With roughly
  2–3 replayed ticks per branch over 1,600 branches, the cap would have fired at around 6,000
  live calls — at or below the expected spend — producing a budget stop the pilot had not earned.

## What to write

**`docs/FOLLOWUPS.md`** — one entry covering all three defects, what was repaired on
2026-09-20 (per-job port derived from the job id, `SIDEKICK_VLLM_BASE_URL` env override,
identity-verified health check that requires the expected LoRA alias in `/v1/models`,
process-group shutdown with `pkill -f` removed, `trap ... EXIT`), and — as its own standing
item — the legacy scripts above that still carry the hazard.

**`campaign/RUNS.md`** — a discard record: the tree
`/scratch/n12194778/sidekick/results/b1_pilot_train_20260919_smoke` and every
`hj8_*_20260919livesmoke_smoke` tree contain **no valid data** and must never be analysed or
resumed from. Say why in one sentence so a future reader does not rediscover it.

**`README.md:30-31`** — read those lines and correct whatever is stale there. Report what they
said and what you changed them to.

**`docs/prereg_b1_pilot_amendment_20260920.md`** — the amendment. It must state:
- the date, and that it is an amendment to a frozen document, which is not edited
- what was found: the cap was counting replayed ticks, not live calls
- the change: `spent` now sums the ledger's live planner-call count, with an unknown row still
  charged 81 exactly as §8 specifies
- **why this is a correction rather than a renegotiation**: §8 already defines the budget as
  live hosted-planner spend against a 10,000 cap. The implementation was measuring a different
  quantity than the document specified; the number 10,000 and the 6,118 expectation are
  unchanged and are not being loosened after seeing data.
- the decisive fact for the record: **no valid B1 data existed when this amendment was written.**
  The only B1 run to date produced 20 crashed rows and zero live planner calls. Nothing about
  the outcome could have informed this change. Say so plainly — it is what makes the amendment
  credible.
- that §9's resume conditions and the 5% quota-stall rule are unchanged

Write it as a scientist writing for a sceptical reviewer, not as a changelog. Short.

## Constraints (these are not optional)

- `aquarius01` is a **login node — steering only**. Never run python, pip, tar, rsync, ffmpeg, or
  any multi-minute command there. You should not need to run anything heavier than `grep`,
  `sed -n` and `ls`; put `timeout` on each.
- Do **not** commit and do **not** run git. The orchestrator reads the diff and commits.
- Read result trees read-only. Never write under `/scratch/.../results/` or
  `hj6_branches_train_20260917`. Do not read `test_normal` or `test_challenge` data.
- Change no code and no test.

## Return contract

Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`, and reproduce any log string
you quote with a literal `grep -c` in the same run. Several facts above are given to you second
hand — if one does not hold up in the tree, **say so instead of writing it**. That is more
valuable than a tidy document.

Write `campaign/workers/STATUS_R4.md` with what you verified and what you could not. Final
report, ten lines or fewer: the four files, any fact above that failed verification, and what
`README.md:30-31` said before you changed it.
