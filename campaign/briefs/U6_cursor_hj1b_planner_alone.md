# U6 — HJ-1 Class B: `planner_alone` pilot campaign (CPU only, SPENDS REAL MONEY)

You are running one arm of the Sidekick HJ-1 pilot. This arm calls the hosted `gpt-5.6-luna`
planner and **spends real money**. A hard budget cap and a smoke gate are mandatory, not optional.

## Absolute constraints (violating any of these fails the unit)

- **Never run `python`, `pip`, `tar`, `rsync` or `ffmpeg` on `aquarius01`.** All compute goes in a
  PBS job via `qsub`. You may run `ls`, `git`, `grep`, `qstat`, `qsub`, `qdel`, `cat`, `sed`.
- **Put `timeout` on every command you run.**
- **Maintenance shutdown is ~08:00 on 2026-09-16.** Your job must be submitted with a walltime that
  ends well before then. Use `walltime=05:00:00` and submit before 23:30 tonight.
- BLAS pinned to one thread: export `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.
- **Never print the value of any API key or secret.** Names only.
- Work only inside the worktree below. Do not touch `.git/` or `.claude/worktrees/`.
- **Do not `git push`. Do not merge. Do not switch branches.** Commit on the current branch only.
- This arm must **not** start a vLLM server and must **not** request a GPU.

## Repo and paths

- Repo (your `--workspace`): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
- Python interpreter: `/scratch/n12194778/sidekick/env/bin/python` (never `python` on the login node)
- AppWorld data root: `/scratch/n12194778/sidekick/appworld`
- HF cache: `/scratch/n12194778/hf`
- Durable output root: `/scratch/n12194778/sidekick/results`
- Codex session archive: `/scratch/n12194778/sidekick/codex_home`

## Goal

Run the `planner_alone` arm of the HJ-1 pilot on the AppWorld **dev** split, 57 tasks × 2 seeds =
114 runs, and store every artifact durably. This measures the planner-alone ceiling — one half of
HJ-1's go/no-go gate (`planner_alone − executor_alone ≥ 20 pp` task goal completion).

`planner_alone` sets `planner_drives=True` and `plan_first=False`, so it calls `planner.act()` at
every step and **never loads an executor model**. That is why this arm needs no GPU.

## Files you own (nobody else is editing these)

- `configs/pilot_planner_alone.yaml` — create
- `scripts/pbs/hj1b_planner_alone.pbs` — create
- `campaign/workers/STATUS_U6.md` — create and keep updated

**Do not edit anything under `src/sidekick/`.** The harness is frozen and its 127 tests are green.
If you believe the harness is broken, write that in STATUS and stop; do not fix it.

## Step 1 — config

Create `configs/pilot_planner_alone.yaml`:

```yaml
env: appworld
campaign_id: hj1b_planner_20260915
planner:
  type: codex
  binary: codex
  model: gpt-5.6-luna
  reasoning_effort: medium
  timeout_s: 300
  scratch_parent: /scratch/n12194778/sidekick/codex_scratch
executor:
  type: mock          # planner_alone never calls the executor; this must not be a vllm client
appworld:
  root: /scratch/n12194778/sidekick/appworld
limits:
  max_steps: 40
  max_tokens_per_episode: 32000
  per_step_timeout_s: 120
  max_planner_calls: 25
prices: configs/cost/prices_2026-09.yaml
```

The planner model and effort **must** be stated explicitly as above. The user's `~/.codex/config.toml`
defaults to a different and far more expensive model; relying on the default would silently cost
many times the budget.

## Step 2 — PBS script

Create `scripts/pbs/hj1b_planner_alone.pbs`. Required header and environment:

```bash
#!/bin/bash
#PBS -N hj1b-planner
#PBS -q cpu_inter
#PBS -l select=1:ncpus=8:mem=32gb
#PBS -l walltime=05:00:00
#PBS -j oe
#PBS -o /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/U6_hj1b.out

set -uo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HOME=/scratch/n12194778/hf
export APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld
export SIDEKICK_VENV=/scratch/n12194778/sidekick/env
export PATH="${SIDEKICK_VENV}/bin:${HOME}/.local/bin:${PATH}"
REPO=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
OUT=/scratch/n12194778/sidekick/results
cd "${REPO}"
```

**Do not set `CODEX_HOME`.** Leave it at its default `~/.codex`, which already holds `auth.json` and
where Codex writes a full session transcript per thread. Pointing it at an empty scratch directory
would strand the credentials and fail every planner call. The transcripts are small (order 50 MB for
this campaign) and home is durable, so the default is both safer and sufficient.

"Store everything" is therefore satisfied by three archives, and you must confirm all three exist:

1. our own event logs and `result.json` under `/scratch/n12194778/sidekick/results` (durable);
2. Codex's own per-thread session transcripts under `~/.codex/sessions` — **after the campaign,
   record in STATUS which session files belong to this campaign** (match by modification time
   window and thread id) so they can be found later;
3. the manifest from step 5.

Note that the harness passes `-m gpt-5.6-luna -c model_reasoning_effort=medium` explicitly on every
call, so the expensive defaults in `~/.codex/config.toml` do not apply — but verify this in the
smoke gate rather than assuming it.

## Step 3 — the smoke gate (MANDATORY, do not skip)

Inside the job, **before** the full campaign, run a 3-task slice:

```
"${SIDEKICK_VENV}/bin/python" -m sidekick.runner \
  --system planner_alone --split dev --tasks 3 --seeds 1 \
  --env appworld --workers 3 \
  --config configs/pilot_planner_alone.yaml \
  --out "${OUT}"
```

Then inspect the results and **abort the job** (exit non-zero, do not proceed) if any of:

- all 3 runs failed with `error_type` in `api_error`, `timeout`, or `crash`;
- zero planner calls were recorded (means the planner was never actually invoked);
- the recorded `model` in any usage record is not `gpt-5.6-luna`;
- measured cost for the 3 runs exceeds **US$0.60** (that would extrapolate past budget).

Print the measured cost-per-run and the mean planner calls per episode before continuing. If the
gate passes, proceed to step 4 in the same job.

## Step 4 — full campaign

```
"${SIDEKICK_VENV}/bin/python" -m sidekick.runner \
  --system planner_alone --split dev --tasks 57 --seeds 1,2 \
  --env appworld --workers 6 \
  --config configs/pilot_planner_alone.yaml \
  --out "${OUT}"
```

`--workers 6` runs six concurrent `codex exec` subprocesses, which fits 8 CPUs. The runner is
already resumable: it skips any run whose `result.json` exists, so the 3 smoke runs are not repeated
and a killed job resumes cheaply.

**Hard budget cap: US$10 for this unit.** After the campaign, total the cost ledger. If the run is
on track to exceed US$10, stop it. Record the actual figure in STATUS.

## Step 5 — manifest and verification

Write `/scratch/n12194778/sidekick/results/results/hj1b_planner_20260915/manifest.json` containing:
git commit of the worktree, `codex --version`, the AppWorld commit from
`/scratch/n12194778/sidekick/appworld.commit`, the config file's sha256, the split and task count
actually used, hostname, PBS job id, start and end timestamps, and the total usage and cost.

Then verify and record in STATUS:

- number of `result.json` files written (expect 114 + 3 smoke = 117 at most);
- task goal completion rate across seeds;
- mean planner calls and mean tokens per episode;
- total US$ spent;
- confirmation that `/scratch/n12194778/sidekick/codex_home` contains session transcripts.

## Step 6 — commit

Commit `configs/pilot_planner_alone.yaml`, `scripts/pbs/hj1b_planner_alone.pbs` and your STATUS file
on the current branch. Do not commit anything under `/scratch`. End the commit message with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WAcXxoXWcJdXBPnbnHPek8
```

## STATUS file contract

Keep `campaign/workers/STATUS_U6.md` current at every milestone (config written, PBS written,
submitted + job id, smoke gate result, campaign finished, verified). Each entry gets a timestamp and
enough detail to resume from that point if you are killed. `hpc-guard` kills anything at 12 h wall.

## Return contract

Report, in under 30 lines: the PBS job id, whether the smoke gate passed and its measured
cost-per-run, the number of runs completed, the task goal completion rate, total US$ spent, and any
claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`. Do not report success for anything you did
not actually observe in an artifact on disk. Reporting that a campaign ran without checking the
result files is the one unforgivable error here.
