# Brief X5 — PBS harness, hj12 configs, and the frontier analysis extension

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You are building the harness that will run the campaign's next experiment and the analysis that
reads it. A parallel unit is building the runtime it drives; you never touch `src/`.

## Why

The hosted planner solves AppWorld dev at goal_pass 0.83 over ~14 steps. The local executor with a
cached plan reaches 0.70 in one call. We are measuring what happens when the planner's first `m`
steps are replayed from recordings already on disk and the executor finishes the episode. The
experiment costs zero hosted calls, so the harness only has to serve the local model.

## Scope — you own these files, and only these

Create:
- `scripts/pbs/hj12_prefix.pbs`
- `configs/hj12_prefix_m2.yaml`, `hj12_prefix_m4.yaml`, `hj12_prefix_m6.yaml`, `hj12_prefix_m9.yaml`

Modify:
- `scripts/analysis/j8_frontier.py`

**Do not touch anything under `src/`**, any other `scripts/analysis/*.py`, any `hj8_*`/`hj11_*`
config, or `campaign/RUNS.md`. Three other units are working in this tree in parallel.

## Part 1 — `scripts/pbs/hj12_prefix.pbs`

Clone `scripts/pbs/hj8_frontier.pbs` and keep every hardening it already has. Read it first; the
details below are the ones that have burned this campaign before.

- **Per-job vLLM port.** `hj8_frontier.pbs` derives the port from the job id and verifies it is free
  before serving. Two jobs once pinned port 8000 simultaneously, the bind loser served zero requests
  while still logging `Application startup complete`, and a whole campaign of results was silently
  measuring nothing. Keep that logic verbatim.
- **Alias-verified health check.** The script parses `GET /v1/models` and **fails fatally unless the
  expected LoRA alias appears in `data[].id`**. Keep it. A mismatch means requests silently hit the
  base model and the evaluation measures nothing while still producing plausible numbers.
- **Scoped kill.** vLLM is launched under `setsid` and only its process group is killed. There must
  be **no `pkill -f "vllm serve"`** anywhere — that pattern once killed a *different* job's server
  mid-run. Keep the `trap` on EXIT.
- **`#PBS -o` is a fixed path** in these scripts and overwrites the previous job's log. Point this
  script's `-o`/`-e` at `hj12_prefix.out`/`.err`, not at any existing name.
- `ARMS="<stem> <stem>"` override, space-separated, validated against the arm table; `SMOKE_ONLY=1`
  restricted to 3 tasks; `DATE=` for the campaign suffix. Walltime `04:00:00`.
- **The adapter served is the intervention-aware one**:
  `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b`, registered under the
  alias `sft_b_plus` (the configs name that alias). This is the adapter from the most recent
  training run, not the older `sft_b_plus_granite8b`. Getting this wrong invalidates the experiment,
  so log the resolved adapter path and assert the directory contains `adapter_config.json` plus a
  weights file before serving.
- At the end of a `SMOKE_ONLY` pass, print a table: arm → episodes, `effective_m`,
  `handoff_occurred` count, `hash_ok` count, replayed planner tokens, live planner calls. **WARN
  loudly if live planner calls is anything other than 0** — this arm must spend nothing hosted.
- The runner is invoked with `--system prefix_handoff`. That system is being created right now by
  another unit; if it does not exist when you test, say so in STATUS and verify the script with
  `bash -n` plus a `--system sft_plan` dry run instead. **Do not create it yourself.**

## Part 2 — the four configs

Base them on `configs/hj8_sft_plan_bplus.yaml` (frozen — copy, never edit). Each differs only in `m`
and `campaign_id`:

```yaml
campaign_id: hj12_prefix_m<K>_20260922
handoff:
  source_campaign: /scratch/n12194778/sidekick/results/hj1b_planner_20260915
  source_system: planner_alone
  m: <K>
```
K ∈ {2, 4, 6, 9}. Source episodes run min 5 / median 12 / max 25 steps, so m=2 and m=4 hand off on
every episode, m=6 on nearly all, m=9 on roughly three quarters. Keep `executor.lora_name:
sft_b_plus`, the `limits` block, `prices`, and the executor decoding settings identical to
`hj8_sft_plan_bplus.yaml` so the only difference from the 1-call arm is the prefix. There is **no
`planner` block spend**: the plan is replayed, so keep the `packet_source`/`on_missing: fail`
pattern the frozen config uses.

## Part 3 — `scripts/analysis/j8_frontier.py`

Read the file first. It already implements per-arm metrics, task-clustered paired bootstrap
contrasts, the frontier table, and refuses to emit a headline when an arm has fewer than 114 rows.
**Reuse its bootstrap and pairing code; do not write a second one.** Add:

1. **`--cost-key <name>`** so the cost axis can be replayed planner tokens rather than live calls.
   Default unchanged. Arms with zero live calls must not be dropped or divided by zero.
2. **`--reference-arm <label>`** and a **non-inferiority test**: for each arm, the paired
   task-clustered difference against the reference, reporting whether the 95% CI upper bound is
   below the 7 pp margin. Primary metric `goal_pass`, secondary `TGC`, **both always reported** —
   this campaign froze `goal_pass` as primary and reaching for whichever metric looks better is
   exactly the degree of freedom the freeze exists to prevent.
3. **The chord test**: given the reference arm (`planner_alone`) and a floor arm (`sft_plan`), for
   each prefix arm compute the straight-line interpolation between floor and reference at that arm's
   cost fraction, and report the arm's quality minus that interpolation with a CI. Positive means the
   quality/cost curve bows above the chord, which is the claim.
4. Report per arm: `handoff_occurred` rate, `hash_ok` rate, `effective_m` mean, and **both
   populations** (all-episodes with crashes scored 0, and survivors), as the existing report does.

**Dry-run it** on trees that already exist, in a PBS job, and paste the output in STATUS:
`/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware`,
`/scratch/n12194778/sidekick/results/hj1b_planner_20260915`. It must run clean and must still refuse
a headline on incomplete arms. Do not write a report JSON into `campaign/results/` for this dry run;
print to stdout or write under `/tmp`.

## Constraints

- `aquarius01` is a **login node**. Never run the interpreter, `pip`, `tar`, `rsync` or `ffmpeg`
  there. Everything computational goes through
  `timeout 1800 hpc bash -c '... OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 ...'`.
- **Do not `qsub` anything.** I submit the jobs. `bash -n` is how you check the PBS script.
- Put a `timeout` on every command.
- **Read-only** with respect to `/scratch/n12194778/sidekick/results/`. Never write under
  `hj6_branches_train_20260917`.
- Do not read, analyse or report any `test_normal` or `test_challenge` data. Dev only.
- **Do not commit.** I review the diff and commit.
- pytest needs `--import-mode=importlib`; if you touch anything with tests, the suite stays at
  **≥ 456 passed, 0 failed**.
- Frozen, read but never edit: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.

## Return contract

`campaign/workers/STATUS_X5.md`, under 800 words, updated at each milestone so the unit is
resumable:
- Every file created/modified; the exact new CLI flags with their defaults.
- The `bash -n` result for the PBS script and the resolved adapter path it would serve.
- The dry-run command and its pasted output.
- Each claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`.
- Anything in this brief that is wrong about the code — say so rather than working around it.
