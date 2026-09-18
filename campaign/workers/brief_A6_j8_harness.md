# A6 (U-V3) — the J8 frontier PBS harness

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your file is the new `scripts/pbs/hj8_frontier.pbs`. Another unit owns
`configs/`, another owns `src/sidekick/runner.py` — **do not touch either**. Do not modify
`scripts/pbs/hj3_eval.pbs`; copy from it.

## Why

J8 measures 12 dev arms and produces the campaign's headline figure: quality against planner cost.
There is no PBS script for it. `scripts/pbs/hj3_eval.pbs` is the closest thing and already
anticipates this — it registers a `sft_b_plus` alias [OBSERVED scripts/pbs/hj3_eval.pbs:56-63],
hard-fails on a bad adapter path [:94-113], serves with
`--enable-lora --max-loras 4 --max-lora-rank 64` [:267,270], and has a commented block for extra
arms that names three configs which do not exist [:302-318].

Read `hj3_eval.pbs` in full before writing anything. Match its structure, its `run_arm` shape
(smoke 3 tasks/seed 1/workers 3 then full 57 tasks/seeds 1,2/workers 6 [:201-224]), its logging and
its error handling.

## Requirements

**1 · Two arm sets, selectable.** The script must run either set independently, via an environment
variable (e.g. `ARMSET=free|live|all`, default `free`):

- **`free`** — arms that make **zero hosted planner calls**: `executor_alone(sft_b_plus)` and
  `sft_plan(sft_b_plus)` with cached packets. These run **before** the quota reset.
- **`live`** — `fixed_k` k ∈ {3,5,10}, `router_seq` τ ∈ {0.3,0.5,0.7}, `sidekick` τ ∈ {0.3,0.5,0.7},
  `oracle_escalation`. These wait for the reset.

🔺 The `free` set must be incapable of spending quota. The configs carry
`planner.on_missing: fail`, but **add a second, independent guard in the script**: before running
the `free` set, assert that no config it is about to use names a live planner without a
`packet_source`. Belt and braces — the last cost overrun in this campaign was 37,368 unbudgeted
calls.

**2 · The τ sweep.** `router_seq` and `sidekick` each run at three thresholds. Each (arm, τ) pair
is a separate campaign and needs its **own campaign id** — otherwise the runs overwrite each other.
Derive the id from the arm and τ, e.g. `hj8_router_seq_tau03_<DATE>`.

**3 · Resumability.** A 12-arm sweep will not finish in one walltime. Completed arms must be
skipped on resume. Use whatever "is this campaign already complete" check the existing scripts use;
if none exists, a marker file per completed arm is acceptable — say which you chose.

**4 · Adapter registration.** `--max-loras 4` is the current ceiling [:267]. This job needs only
`sft_b_plus`, so the ceiling is not binding — but assert the count rather than assuming it, and
fail loudly if a future arm list exceeds it.

**5 · Log paths must carry the campaign id.** This exact defect was just fixed in
`scripts/pbs/hj6_branches.pbs` (commit `2216a0b`) — **read that file's header comment and its
`exec` block and follow the same pattern**: `#PBS -o` names the log *directory* so PBS writes a
unique `<job ID>.OU`, and the script `exec`s a `${CID}.${PBS_JOBID}.out` copy once the id is known.
Do not reintroduce a shared filename.

**6 · Config gate.** Run `scripts/setup/verify_configs.py` at the top of the job and abort on a
non-zero exit. ⚠ It currently exits non-zero on this repo; another unit is fixing that. Wire the
gate in anyway — that is the point — but make the failure message name the script so a reader knows
why the job stopped.

**7 · Queue sizing — measured tonight, use it.** A non-interactive `qsub -q gpu_inter` is routed by
the site to `gpu_batch_exec` regardless of the `-q` directive, and `gpu_batch_exec` is congested.
Size the request to what the job actually needs rather than copying `ncpus=16:mem=128gb`
unexamined, and state your reasoning in a header comment.

## Do not

- **Do not submit this job.** You are writing it, not running it. Claude submits.
- Do not run any GPU job at all — a training job is already queued.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. Any check you need runs in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread.
- 🔺 **Zero planner calls. Do not invoke `codex`.** Quota exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite stays at **349 passed, 1 skipped** if you touch anything importable.
- Write `campaign/workers/STATUS_A_6.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.
- `shellcheck` the script if available, and say whether you did.

## Return contract

- The new script, and a dry syntax check (`bash -n`).
- The arm → config → campaign-id table the script implements.
- Which resume mechanism you chose and why.
- What you sized the job at, and your reasoning.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
