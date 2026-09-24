# Unit CACHECALLS: are replayed (cached) planner events counted as hosted calls, and which published numbers move?

WT = /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 (HEAD 4111c9f). Written by Claude, 2026-09-25.
Common rules: `campaign/workers/briefs/20260924_common_rules.md`. **Read-only on code and results.** Write only the
report and staging files named below.

## What Claude has verified
- **The mechanism.**
  - `CachedPacketPlanner` returns the replayed plan with `Usage(provider="cache", n_calls=0, tokens 0)`
    (`src/sidekick/agents/planner.py:930-939`).
  - The loop then overwrites it: `usage = resp.usage.model_copy(update={"n_calls": attempts})`
    (`src/sidekick/systems/loop.py:465`, plan HEAD; the pinned checkouts have the same line earlier).
  - So the charged `n_calls` is 1.
- **One real dev episode.** `/scratch/n12194778/sidekick/results/hj12_takeover_fixed_k_10_20260923/fixed_k/1/0d8a4ee_1`.
  - Its step-0 `plan` event has `usage.provider = cache`, `n_calls = 1` and `input_tokens = 0`. The one live codex
    call is at step 10.
  - `result.json` has `n_planner_calls = 2`, and `totals.per_actor.planner.n_calls = 2`.
  - The dollar figure comes from tokens, so the cached plan costs $0.
- **Consequence.** Calls and dollars disagree about the replayed plan: calls charge it, dollars do not.

## Questions (answer each with evidence)
1. **Which figures.** Which ledger rows and paper figures state hosted planner **calls**?
   - Grep `docs/claims_ledger.md` and `paper/preprint_dev_v2_20260924.md` for `calls`. Include at least COST-*,
     ROB-18, ROB-19, ROB-27, GANZ-03, CEILHI-02, CHAN-PRICE-*, and any H2 or J9 prediction judged on calls.
   - For each, name the script and function that computed it.
2. **How each script counts.** For each script, does it count from `n_planner_calls`,
   `totals.per_actor.planner.n_calls`, or events? Does it include or exclude `provider == "cache"` events? Cite
   `path:line`.
3. **Prefix arms.** How are hosted calls attributed to a prefix-replay arm?
   - Does the arm's own `result.json` count the replayed prefix actions as calls? Look at one dev prefix episode's
     events and result.
   - Or does a report attribute the source's first m calls? Cite the code.
4. **Every arm type.** Which arm types carry a cached plan event: channel arms (takeover, advise, show),
   `sft_plan` / plan, and any other that uses `packet_source`?
   - Count the affected episodes per published dev campaign with jq over `events.jsonl`.
   - Use only dev campaigns. Never open `j10_*`, `j11_*` or `j12_*` campaigns, or anything on `test_normal` or
     `test_challenge`.
5. **Recomputed values.** For every affected figure, recompute it counting only live calls (provider ≠ "cache").
   - Do it in a PBS job via `hpc`, reusing the original function if it can be pointed at a live-only count.
     Otherwise make a minimal local re-implementation, checked to reproduce the published value first.
   - Give the old value, the new value and whether any verdict or direction changes. Include every interval, and
     every NI or "fails" statement that is judged on calls.
6. **Registered definitions.**
   - What do A1 (`docs/prereg_j10_amendment_20260924.md`), the H2 prereg and the J11/J12 preregs say "hosted calls"
     means? Quote the line.
   - Does `scripts/analysis/j10_report.py` (and `j11_report.py`) count cached events? Cite `path:line`.
   - Is the registered definition the one the code implements?
7. **Dollars.** Confirm that the USD figures exclude the cached plan, i.e. the original purchase is not attributed.
   State whether any USD figure the paper prints is therefore inconsistent with its calls figure.

## Constraints
- **Login node.** aquarius01 is a login node: python only in `hpc bash -c '...'` with timeout,
  `OMP_NUM_THREADS=1`, `PYTHONPATH=src:.` and `/scratch/n12194778/sidekick/env/bin/python`.
- **jq.** jq over many `events.jsonl` files goes in a PBS job too, unless a single file is being read.
- **Shell.** Put scripts in `/home/n12194778/.claude/jobs/91578989/tmp/cachecalls/` and run them with `bash`.
- **Workers and runs.** No codex or luna workers. No hosted calls. No qsub of arms.
- **Files you may not change.**
  - Code, configs, the ledger, the paper and the preregs.
  - Anything under `/scratch/.../results/`. Write your outputs under `campaign/results/` only: the new file named
    below.

## Outputs
- `campaign/results/cache_calls_audit_20260925.report.json`: per figure, the id, script, old value, live-only
  value and verdict change, plus per-campaign counts of cached plan events.
- `campaign/workers/staging/ledger_rows_20260925_cachecalls.md`: draft ledger rows (id prefix `CALLS-`) and
  correction notes (`A13 (2026-09-25) →`, in the A9/A12 style) for every row whose calls figure changes.
- A proposal only, with no edit: the smallest change that fixes future counting, whether in `loop.py` or in the
  analysis. Say which already-frozen reports (J10/J11/J12) it would touch, and whether that needs a pre-data
  amendment. No `j10_*` test data exists yet except arm 3, which you must not open.

## Report (≤ 400 words; [OBSERVED path:line] / [INFERRED] tags; quote strings only with a `grep -c` in the same run)
A table of affected figures (old, new, verdict change), the registered definition, the dollar consistency finding,
the fix proposal, and the files written.
