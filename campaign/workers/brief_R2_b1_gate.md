# R2 — B1: outcome-based smoke gate, error detail on rows, live-call budget cap, port contract

Repo (absolute, a git worktree — work here, do not cd elsewhere):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why this unit exists (observed, 2026-09-19)

The B1 pilot smoke job `25519712` exited **0** and reported
`[b1] smoke spend: n_rows=20 branch_planner_calls_sum=88 unknown_call_rows=0`.
Every one of those 20 rows had `branch_error_type: "crash"` and `branch_planner_tokens: 0`.
The run produced no live planner call at all. The "88 calls" were replayed cached review ticks
counted off the replayed prefix. The gate counted rows and summed a field; it never looked at
whether anything succeeded, so it certified a total failure as a pass.

Root cause of the crashes was a vLLM port collision with a second job (handled by a different
worker, in `hj8_frontier.pbs`), but the gate is a separate defect and is this unit's subject:
**a smoke that cannot fail is not a smoke.**

A third defect was found from the same rows. The `--max-planner-calls-total` cap sums
`branch_planner_calls` [`scripts/setup/branch_counterfactual.py:1291`, `:1297-1318`], which is
`RunResult.n_planner_calls` [`:883-905`], which `counters_from_events`
[`src/sidekick/systems/loop.py:119-133`] derives from the prefix **including replayed
interventions** (`:128` charges `max(1, ev.usage.n_calls or 1)` for every intervention event in
the replayed prefix, live or not). The pre-registration's budget is **live hosted-planner
spend**: expected 6,118 against a cap of 10,000 [`docs/prereg_b1_pilot.md:158-199`]. At roughly
2–3 replayed ticks per branch across 1,600 branches, the cap would fire at around 6,000 *live*
calls — at or below the expected spend — stopping the pilot before its sample completes, for a
budget it had not actually spent.

## Scope — files you own in this unit

- `scripts/pbs/b1_pilot.pbs`
- `scripts/setup/branch_counterfactual.py`
- `tests/unit/test_branch_counterfactual.py` and other tests you need
- `campaign/workers/scratch_A20/test_b1_pilot_guards.py` and `run_validation.sh` (you own these)

**Out of scope, owned by another worker running in parallel right now — do not touch:**
`scripts/pbs/hj8_frontier.pbs`, `src/sidekick/runner.py`, `scripts/analysis/*`, `docs/*`,
`campaign/RUNS.md`, `README.md`, any other `.pbs`. **`docs/prereg_b1_pilot.md` is FROZEN — it
must not be edited under any circumstance.** The amendment note recording this change is being
written by a different worker; you do not write it.

## SHARED CONTRACT C1 — vLLM port and lifecycle

The identical contract is being applied to `hj8_frontier.pbs` by another worker. Implement it
exactly as written so the two scripts stay comparable.

1. **Port.** Immediately before the `vllm serve` block (`:466`):
   - derive `JOBNUM` from `${PBS_JOBID%%.*}` with non-digits stripped; fall back to `$$` if empty
   - `VLLM_PORT=$(( 20000 + JOBNUM % 20000 ))`
   - probe with `ss -ltn` and increment (wrapping at 40000 back to 20000, max 50 tries) while the
     port is already LISTENing
   - `export VLLM_PORT` and `export SIDEKICK_VLLM_BASE_URL="http://127.0.0.1:${VLLM_PORT}"`
   - echo the chosen port and base_url on one `[b1]` line
2. **Serve flag** becomes `--host 127.0.0.1 --port "${VLLM_PORT}"`. No literal `8000` may remain
   anywhere in the file.
3. **Every probe** (the `curl .../v1/models` health check at `:475-486`, any other) uses
   `${VLLM_PORT}`.
4. **Launch under `setsid`** so the server leads its own process group:
   `setsid "${SIDEKICK_VENV}/bin/vllm" serve ... & VLLM_PID=$!`
5. **`kill_vllm` (`:392-404`)**: signal the process **group** — `kill -TERM -- -"${VLLM_PID}"`,
   wait up to 60 s, then `kill -KILL -- -"${VLLM_PID}"`. **Delete both `pkill -f "vllm serve"`
   (`:399`) and `pkill -f "EngineCore"` (`:400`).** They are node-wide; on 2026-09-19 this exact
   line killed a different job's vLLM server mid-run. Keep the `nvidia-smi` report.
6. **`trap kill_vllm EXIT`** immediately after the function is defined. The script has no trap
   today, so a mid-script `exit 1` leaves a server holding the GPU.
7. **Health check must verify identity, not liveness.** After the port answers:
   a. `body=$(curl -sf "http://127.0.0.1:${VLLM_PORT}/v1/models")`. Parse the `id` values.
      **FATAL unless every alias the script registers via `--lora-modules` appears as an id**
      (for B1 that is `sft_b`, aliased from `sft_b_s123_granite8b`). This check alone would have
      caught the collision: B1 asked for `sft_b` and the server it reached served only
      `sft_b_plus`.
   b. If `ss` is available: FATAL unless the pid LISTENing on `${VLLM_PORT}` has process-group id
      `${VLLM_PID}`. If `ss` is unavailable, WARN and continue.
   c. FATAL if the vLLM log matches `port .* is used by process` — B1's own log contained exactly
      that line and the job ignored it.
   Every FATAL prints the last 60 lines of the vLLM log, calls `kill_vllm`, exits 1.

## R2-specific work

### A. Row schema — surface the error, and separate live calls from replayed ticks

In `scripts/setup/branch_counterfactual.py`:

- `planner_cost_from_result` (`:883-905`) currently returns the replay-inclusive
  `n_planner_calls` and `planner_tokens_total`. Also extract **`totals.planner_calls_total`**,
  the ledger's live-only count.
- The branch row written at `:952-953` gains two fields:
  - `branch_live_planner_calls` — that ledger live count (`None` if unavailable)
  - `branch_error_detail` — for a failed branch, the first 200 characters of the `error` event's
    `payload.detail` together with its `exc_type`. The 2026-09-19 failure wrote
    `branch_error_type: "crash"` and nothing else; the actual message
    (`Client error '404 Not Found' ... HTTPStatusError`) existed only inside each branch's
    `events.jsonl` and had to be dug out by hand.
- **Keep `branch_planner_calls` exactly as it is** (replay-inclusive). Existing artifacts and
  analyses read it; this is an addition, not a redefinition.

### B. Budget cap counts live calls

`_spent_from_rows` (`:1297-1318`, used by the checks at `:1327` and `:1340`) must sum
`branch_live_planner_calls`. A row missing the field or holding `None` is charged the existing
unknown-call constant (**81**, as `docs/prereg_b1_pilot.md:194` specifies) — reuse the constant
already in the file rather than writing a new literal.

Tests in `tests/unit/test_branch_counterfactual.py`:
- a row whose calls were entirely replayed contributes **0** to `spent`
- a row with live calls contributes exactly its live count
- a row missing the field is charged 81
- `branch_planner_calls` still reports the replay-inclusive count (no regression)

### C. The smoke gate reads outcomes

`print_smoke_spend` (`:415-443`) and the `SMOKE_ONLY` wait loop (`:539-564`). The gate must
**FATAL** (exit non-zero) on any of:

1. **any** row with a non-null `branch_error_type` — print the count and the
   `branch_error_detail` of the first three rows
2. no row with `branch_steps > replay_k + 1` — the executor never took a live step past the
   replayed prefix
3. `sum(branch_planner_tokens) == 0` across the smoke — no live planner call is proven

and it must print **live** calls and tokens, clearly labelled, alongside the tick sum — never the
tick sum alone as "spend".

Raise the smoke sample from its current size to **4 branch points** so at least one later review
is likely to fall inside a branch, and set `SMOKE_TARGET_ROWS` (`:539-564`, currently 16) to
whatever 4 points implies. State in your report what the sample was before and after, and how
points map to rows.

The `OPERATOR_CONFIRM` line and the three existing guards (frozen 1600-point sample identity,
out-root not inside `hj6_branches_train_20260917`, `--untreated-mode suppress_next` present)
must keep working unchanged, including on resume. Their harness is
`campaign/workers/scratch_A20/test_b1_pilot_guards.py` (18 cases) — extend it with the new
gate cases and keep all 18 passing.

## Constraints (these are not optional)

- `aquarius01` is a **login node — steering only**. Never run python, pip, tar, rsync or any
  multi-minute command there. Compute goes in a PBS job: `hpc <cmd>` or `hpc bash -c '...'`.
  `bash -n` and `grep` on the login node are fine.
- Put `timeout` on every command you run. Pin BLAS to 1 thread in anything numeric.
- Do **not** commit and do **not** run git. The orchestrator reads the diff and commits.
- Do not submit any PBS job that holds a GPU. Do not `qsub` this `.pbs` file.
- Do not read or write anything under `/scratch/.../results/`. Never write under
  `hj6_branches_train_20260917`. Do not touch `test_normal` or `test_challenge` data.
- `docs/prereg_b1_pilot.md` is frozen: read it, never edit it.
- The full suite must still pass: baseline **413 passed, 1 skipped**. Run it inside a job
  (`hpc bash -c '... -m pytest tests -q --import-mode=importlib'`; the import mode flag is
  required or collection fails). Report the exact final line.
- `bash -n scripts/pbs/b1_pilot.pbs` must be clean.

## Return contract

Write `campaign/workers/STATUS_R2.md` as you go, not only at the end — if you are killed at the
12 h wall it is the only record. Per milestone: what changed, the test line, how to resume.
Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. Reproduce any log string you
quote with a literal `grep -c` in the same run.

Final report, ten lines or fewer: files changed, each new gate condition and the evidence it was
seen to fire on a crafted bad input, the smoke sample size before/after, the suite's final line,
and anything you could not do.
