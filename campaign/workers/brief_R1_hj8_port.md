# R1 — per-job vLLM port, scoped shutdown, identity-verified health check, ARMS override

Repo (absolute, a git worktree — work here, do not cd elsewhere):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why this unit exists (observed, 2026-09-19)

Two GPU jobs (`25519712` B1 pilot, `25519749` J8 live smoke) landed on the same node
`gpu0n007` at the same second. Every GPU PBS script pins vLLM to `--host 127.0.0.1 --port 8000`
and the health check only probes the port. vLLM 0.29 does **not** hard-fail the bind loser:
both printed `Application startup complete`; one owned the socket and the other served nothing.
The loser's requests went to the winner's server, which had a different LoRA alias registered,
producing 20 × `404 The model 'sft_b' does not exist`. Then the loser's cleanup ran
`pkill -f "vllm serve"` — node-wide — and killed the winner's server mid-run. Both jobs were
destroyed. Nothing in either script could have detected any of this.

## Scope — files you own in this unit

- `scripts/pbs/hj8_frontier.pbs`
- `src/sidekick/runner.py` (one line, `:162`, plus the manifest record)
- tests under `tests/`
- `campaign/workers/scratch_A20/` — add cases in NEW files only (`cases_r1_*`); do not edit
  `test_b1_pilot_guards.py`

**Out of scope, owned by another worker running in parallel right now — do not touch:**
`scripts/pbs/b1_pilot.pbs`, `scripts/setup/branch_counterfactual.py`,
`tests/unit/test_branch_counterfactual.py`, `scripts/analysis/*`, `docs/*`, `campaign/RUNS.md`,
`README.md`. Legacy scripts (`hj6_branches.pbs`, `hj3_eval.pbs`, `hj4*.pbs`, `hj1*.pbs`,
`hj15_state_probe.pbs`) keep the hazard deliberately — they are not being resubmitted and are
being recorded in FOLLOWUPS by a different worker. Do not edit them.

## SHARED CONTRACT C1 — vLLM port and lifecycle

The same contract is being applied to `b1_pilot.pbs` by another worker. Implement it exactly as
written so the two scripts stay comparable.

1. **Port.** Immediately before the `vllm serve` block:
   - derive `JOBNUM` from `${PBS_JOBID%%.*}` with non-digits stripped; fall back to `$$` if empty
   - `VLLM_PORT=$(( 20000 + JOBNUM % 20000 ))`
   - probe with `ss -ltn` and increment (wrapping at 40000 back to 20000, max 50 tries) while the
     port is already LISTENing
   - `export VLLM_PORT` and `export SIDEKICK_VLLM_BASE_URL="http://127.0.0.1:${VLLM_PORT}"`
   - echo the chosen port and base_url on one `[hj8]` line
2. **Serve flag** becomes `--host 127.0.0.1 --port "${VLLM_PORT}"`. There must be no literal
   `8000` left anywhere in the file.
3. **Every probe** (`curl .../v1/models`, any other) uses `${VLLM_PORT}`.
4. **Launch under `setsid`** so the server leads its own process group:
   `setsid "${SIDEKICK_VENV}/bin/vllm" serve ... & VLLM_PID=$!`
5. **`kill_vllm` (`:290-302`)**: signal the process **group** — `kill -TERM -- -"${VLLM_PID}"`,
   wait up to 60 s, then `kill -KILL -- -"${VLLM_PID}"`. **Delete both `pkill -f "vllm serve"`
   and `pkill -f "EngineCore"` lines.** They are node-wide and caused the incident above. Keep
   the `nvidia-smi` report.
6. **`trap kill_vllm EXIT`** immediately after the function is defined. The script has no trap
   today, so a mid-script `exit 1` leaves a server holding the GPU.
7. **Health check must verify identity, not liveness** (`:481-492`). After the port answers:
   a. `body=$(curl -sf "http://127.0.0.1:${VLLM_PORT}/v1/models")`. Parse the `id` values.
      **FATAL unless every alias the script passes in `--lora-modules` appears as an id.**
      (The alias half is the text before `=` in each `LORA_MODULES` entry.) This alone would
      have caught the 2026-09-19 collision in under a second.
   b. If `ss` is available: find the pid LISTENing on `${VLLM_PORT}` via `ss -ltnp`. FATAL
      unless its process-group id equals `${VLLM_PID}` (setsid makes VLLM_PID the pgid leader,
      so children pass). If `ss` is unavailable, print a WARN and continue — check (a) is the
      decisive one.
   c. FATAL if the vLLM log matches `port .* is used by process`.
   Every FATAL prints the last 60 lines of `${VLOG}`, calls `kill_vllm`, exits 1.

## R1-specific work

8. **`ARMS` override.** `hj8_frontier.pbs` today accepts only `ARMSET=free|live|all`
   (`:128-145`). Add: when `ARMS` is set and non-empty, it is a space-separated list of campaign
   id **stems** (the third `|`-field of a `FREE_ARMS`/`LIVE_ARMS` entry, e.g.
   `hj8_fixed_k_3 hj8_sidekick_tau05`).
   - each stem must match exactly one entry across `FREE_ARMS`+`LIVE_ARMS`; on an unknown stem,
     FATAL printing the offending stem **and** the full list of valid stems
   - `SELECTED_ARMS` is built in the order the stems were given, and `ARMSET` no longer selects
   - echo `[hj8] ARMS override: N arms: <stems>`
   This exists so the 10 live arms can be split across two GPU jobs (`max_run=2`).
9. **Walltime** `#PBS -l walltime=` from `08:00:00` to `10:00:00` (`:5`). Five live arms at
   ~114 episodes are estimated at 5–6 h and 8 h has no margin.
10. **Smoke escalation table.** At the very end of a `SMOKE_ONLY=1` pass, print one table over
    the smoke trees this pass produced, one row per arm:
    `arm | n_episodes | live_planner_calls | n_interventions | n_success | steps_mean`
    Source it from the per-arm summary the script already writes if one exists; otherwise count
    from each run's `events.jsonl`. Then:
    - WARN if every `router_seq` arm in the pass has an identical `live_planner_calls`
    - WARN, separately, if every `sidekick` arm does
    That is the signature of a gate that never fires, which must be seen before ~3,200 live
    planner calls are spent. WARN, not FATAL — the operator judges it.

## `runner.py` — env override for the executor base URL

`src/sidekick/runner.py:162` currently reads
`base_url=str(exec_cfg.get("base_url", "http://127.0.0.1:8000")),`.
22 YAML configs hardcode `base_url: http://127.0.0.1:8000`; several are frozen experiment
inputs and **must not be edited**. The server URL is a deployment fact, not an experiment
parameter, so add an environment override with precedence **env > yaml > default**:
read `SIDEKICK_VLLM_BASE_URL`; if set and non-empty it wins. Record the effective base_url in
each run's `manifest.json` (find how the manifest is assembled nearby and add the field there).

Tests (new, in the existing unit test layout): env set → the executor client is constructed
with the env URL even when the yaml says `:8000`; env unset → yaml wins; neither → the default.

## Guard harness cases

Add to `campaign/workers/scratch_A20/` as new files (`cases_r1_hj8.txt` + a small runner, or
extend the existing `run_validation.sh` pattern without editing `test_b1_pilot_guards.py`):
- `/v1/models` returns a body missing an expected alias → the health check FATALs
- a foreign pid holds the port → FATAL (may be simulated by stubbing the `ss` output)
- `SIDEKICK_VLLM_BASE_URL` set → honoured by the client
- an unknown stem in `ARMS` → FATAL naming it
Each guard must be *seen to fire*. A guard that has never fired is not a guard — an earlier unit
here waved one through on that reasoning and accepted a weightless LoRA adapter.

## Constraints (these are not optional)

- `aquarius01` is a **login node — steering only**. Never run python, pip, tar, rsync or any
  multi-minute command there. Compute goes in a PBS job: `hpc <cmd>` or `hpc bash -c '...'`.
  `bash -n` and `grep` on the login node are fine.
- Put `timeout` on every command you run. Pin BLAS to 1 thread in anything numeric.
- Do **not** commit and do **not** run git. The orchestrator reads the diff and commits.
- Do not submit any PBS job that holds a GPU. Do not run `qsub` on any of these `.pbs` files.
- Do not read or write anything under `/scratch/.../results/`. Never write under
  `hj6_branches_train_20260917`. Do not touch `test_normal` or `test_challenge` data.
- The full test suite must still pass: baseline is **413 passed, 1 skipped**. Run it inside a
  job (`hpc bash -c '... -m pytest tests -q --import-mode=importlib'`; `--import-mode=importlib`
  is required or collection fails). Report the exact final line.
- `bash -n scripts/pbs/hj8_frontier.pbs` must be clean.

## Return contract

Write `campaign/workers/STATUS_R1.md` as you go (not only at the end — if you are killed at the
12 h wall it is the only record). It must contain, per milestone: what changed, the test line,
and a resume instruction. Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
Reproduce any log string you quote with a literal `grep -c` in the same run.

Final report, ten lines or fewer: files changed, the guard cases and the evidence each was seen
to fire, the suite's final line, and anything you could not do.
