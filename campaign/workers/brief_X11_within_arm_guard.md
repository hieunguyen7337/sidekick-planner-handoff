# Brief X11 — the spend ceiling cannot stop a single runaway arm

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Edits `scripts/pbs/hj12_live.pbs` only, plus tests if any are natural. **Two GPU jobs are queued.**
Do not `qsub`, do not touch a GPU, do not run any evaluation. Do not edit `configs/` or `src/`.

## The gap

`MAX_PLANNER_CALLS` is checked **after an arm finishes**, before the next one starts
[OBSERVED scripts/pbs/hj12_live.pbs, the spend block around line 627]. Within one arm nothing bounds
the total. The only live cap is per episode: `max_planner_calls: 81`
[OBSERVED src/sidekick/systems/loop.py:323 and configs/hj12_planner_handoff.yaml].

So the worst case for `hj12_planner_handoff` is a planner that never emits HANDOFF: it drives all 40
steps, about 41 calls per episode, 114 episodes, roughly **4,700 hosted calls in a single arm**. The
ceiling would notice only once that arm had already finished. The phase was planned at 1,500 to
2,000 calls in total.

That failure mode is not hypothetical — "the planner never hands off" is listed as an open risk in
the campaign plan, and in that case `planner_handoff` degenerates to `planner_alone`, the most
expensive arm in the campaign.

## What to build

### 1. A projected-spend check between an arm's smoke and its full run

`run_arm` already runs a 3-task smoke before the full 114-episode run. After the smoke summary is
read and before the full run is launched:

- Take realised live calls per episode from the smoke, using the same key the spend block already
  uses: `ledger_totals.planner_calls_total` divided by the smoke's episode count. Do **not** use the
  replay-inclusive `planner_calls_total`; that conflation has already produced a false gate failure
  in this campaign.
- Project the full run: `ceil(calls_per_episode × N_FULL_TASKS × n_seeds × SAFETY)`. Pick `SAFETY`
  yourself in the range 1.1 to 1.3 and say what you picked and why.
- If `RUNNING_PLANNER_CALLS + projection > MAX_PLANNER_CALLS`, **FATAL before the full run**, naming
  the arm, the smoke's calls per episode, the projection, the running total and the ceiling. Skipping
  to the next arm is not acceptable: the operator must see a stop, decide, and re-launch with a
  raised ceiling or a narrower `ARMS`.
- Print the projection on **every** arm, not only when it trips, so a passing arm still shows what it
  is about to spend.

Three episodes is a noisy estimator. That is fine here because the check only has to catch an
order-of-magnitude overrun, and the safety factor biases it toward stopping. Say so in a comment so
the next reader does not mistake it for a precise budget.

### 2. Tighten the zero-takeover check on the smoke

Today a takeover arm with zero planner-authored `action` events WARNs on the smoke and FATALs only
on the full run [OBSERVED STATUS_X9.md]. That spends roughly 280 calls to learn something the smoke
already showed.

The WARN exists because at `fixed_k: 10` three short episodes can legitimately trigger no review.
Make the check precise instead of lenient: on the smoke, **FATAL** when there were zero
planner-authored actions **and** at least one smoke episode ran long enough to trigger the arm's
gate — for a `fixed_k` arm that means `steps >= k`; for a `router_seq` exception arm it means at
least one episode contained the exception marker `Execution failed. Traceback:`
[OBSERVED src/sidekick/agents/verifier.py, `EXCEPTION_MARKER`]. When no smoke episode could have
triggered, keep the WARN and say explicitly that the smoke was uninformative.

A takeover arm that silently runs the advise path produces a full set of plausible numbers measuring
the wrong thing. That is the failure this campaign has already paid for more than once, so it is
worth the extra care here.

### 3. Do not change

The per-job `VLLM_PORT`, the `/v1/models` alias identity check, the `setsid` and EXIT-trap teardown,
the absence of `pkill -f`, the directory form of `#PBS -o`/`-e`, the inverted live-planner guard, the
arm-to-system mapping in `LIVE_ARMS`, and the existing between-arm ceiling. Another unit may have
added a sixth arm and adjusted `MAX_PLANNER_CALLS`; keep whatever you find rather than reverting it.

## Verification

- `bash -n scripts/pbs/hj12_live.pbs` and paste the output.
- Paste the new FATAL and projection message lines verbatim.
- The suite must not fall. Run it through `hpc`:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
  and paste the final line. It was 485 passed, 1 skipped before another unit added tests, so report
  what you actually see rather than matching a number.
- **Do not submit the script.**

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X11.md`, under 450 words: the `SAFETY` value and why, the projection formula
as implemented, the exact key the smoke figure comes from, the tightened zero-takeover condition per
arm type, the `bash -n` output and the pasted suite line. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
