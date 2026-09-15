# U7 — HJ-1 Class A: `executor_alone` pilot campaign (GPU only, ZERO money)

**Create the config files within your first three actions, then iterate with the PBS script.**

You are running one arm of the Sidekick HJ-1 pilot. This arm runs entirely on a local GPU and makes
**zero hosted-planner calls**, so it costs no money. Your job is to keep it that way.

## Absolute constraints (violating any of these fails the unit)

- **Never run `python`, `pip`, `tar`, `rsync` or `ffmpeg` on `aquarius01`.** All compute goes in a
  PBS job via `qsub`. You may run `ls`, `git`, `grep`, `qstat`, `qsub`, `qdel`, `cat`, `sed`.
- **Put `timeout` on every command you run.**
- **Maintenance shutdown is ~08:00 on 2026-09-16.** Submit with `walltime=05:00:00`, before 23:30.
- BLAS pinned to one thread: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1`.
- **Never print the value of any API key or secret.** Names only.
- Work only inside the worktree below. Do not touch `.git/` or `.claude/worktrees/`.
- **Do not `git push`. Do not merge. Do not switch branches.** Commit on the current branch only.
- **This arm must make zero planner calls.** If the results show any planner call, that is a defect
  you must report, not paper over.

## Repo and paths

- Repo (your `-c` workspace): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
- Python: `/scratch/n12194778/sidekick/env/bin/python` (never `python` on the login node)
- AppWorld data root: `/scratch/n12194778/sidekick/appworld`
- HF cache: `/scratch/n12194778/hf`
- Durable output root: `/scratch/n12194778/sidekick/results`

## Goal

Run the `executor_alone` arm of HJ-1 on the AppWorld **dev** split for **two executor models**,
57 tasks × 2 seeds each = 228 runs total. This measures the un-helped small-model floor — the other
half of HJ-1's go/no-go gate (`planner_alone − executor_alone ≥ 20 pp` task goal completion).

`executor_alone` sets `plan_first=False` and `planner_drives=False`, so no planner is ever
constructed. Set `planner.type: mock` in both configs to guarantee it.

## Files you own (nobody else is editing these)

- `configs/pilot_exec_8b.yaml` — create
- `configs/pilot_exec_3b.yaml` — create
- `scripts/pbs/hj1a_executor_alone.pbs` — create
- `campaign/workers/STATUS_U7.md` — create and keep updated

**Do not edit anything under `src/sidekick/`.** The harness is frozen and its 127 tests are green.
Another worker (U6) is running a different arm right now and owns
`configs/pilot_planner_alone.yaml` and `scripts/pbs/hj1b_planner_alone.pbs` — do not touch those.

## Step 1 — the two configs

`configs/pilot_exec_8b.yaml`:

```yaml
env: appworld
campaign_id: hj1a_exec8b_20260915
planner:
  type: mock          # never called by executor_alone; must not be codex
executor:
  type: vllm
  model: ibm-granite/granite-4.2-8b
  base_url: http://127.0.0.1:8000
  temperature: 0.7
  max_tokens: 1024
  timeout_s: 120
appworld:
  root: /scratch/n12194778/sidekick/appworld
limits:
  max_steps: 40
  max_tokens_per_episode: 32000
  per_step_timeout_s: 120
  max_planner_calls: 25
prices: configs/cost/prices_2026-09.yaml
```

`configs/pilot_exec_3b.yaml` is identical except
`campaign_id: hj1a_exec3b_20260915` and `model: ibm-granite/granite-4.2-3b`.

**`temperature: 0.7` is deliberate and must not be changed to 0.** HJ-1 exists partly to estimate
the paired variance that sets the non-inferiority margin. At temperature 0 the two seeds would be
byte-identical and the second seed would measure nothing.

## Step 2 — PBS script

Create `scripts/pbs/hj1a_executor_alone.pbs`. Reuse the proven environment block from
`scripts/pbs/g3_granite.pbs`, which already works on this cluster — in particular the CUDA-13
toolkit block, which FlashInfer's JIT needs during vLLM warmup:

```bash
#!/bin/bash
#PBS -N hj1a-exec
#PBS -q gpu_inter
#PBS -l select=1:ncpus=12:ngpus=1:mem=64gb
#PBS -l walltime=05:00:00
#PBS -j oe
#PBS -o /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/U7_hj1a.out

set -uo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export HF_HOME=/scratch/n12194778/hf
export APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld
export SIDEKICK_VENV=/scratch/n12194778/sidekick/env
export PATH="${SIDEKICK_VENV}/bin:${HOME}/.local/bin:${PATH}"
CU13="${SIDEKICK_VENV}/lib/python3.12/site-packages/nvidia/cu13"
if [[ -x "${CU13}/bin/nvcc" ]]; then
  export CUDA_HOME="${CU13}"; export CUDA_PATH="${CU13}"
  export PATH="${CU13}/bin:${PATH}"
  export LD_LIBRARY_PATH="${CU13}/lib:${CU13}/lib64:${LD_LIBRARY_PATH:-}"
fi
REPO=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
OUT=/scratch/n12194778/sidekick/results
cd "${REPO}"
```

The job runs the two models **sequentially on the one GPU**:

1. start vLLM serving `ibm-granite/granite-4.2-8b` on port 8000, background, log to
   `/scratch/n12194778/sidekick/logs/hj1a_vllm_8b.log`;
2. poll `http://127.0.0.1:8000/v1/models` until healthy, **timeout 300 s** — measured startup is
   about 76 s once the torch.compile cache is warm, longer on a cold cache. If it never becomes
   healthy, abort with a clear message rather than running the campaign against a dead server;
3. run the 8B smoke gate, then the 8B campaign (step 3);
4. shut the server down cleanly and confirm the GPU is free;
5. repeat 1–4 for `ibm-granite/granite-4.2-3b`;
6. exit non-zero if either campaign failed.

## Step 3 — smoke gate, then campaign, for each model

Smoke gate first (**do not skip**):

```
"${SIDEKICK_VENV}/bin/python" -m sidekick.runner \
  --system executor_alone --split dev --tasks 3 --seeds 1 \
  --env appworld --workers 3 \
  --config configs/pilot_exec_8b.yaml --out "${OUT}"
```

Abort that model's campaign if all 3 runs crashed or timed out, or if the executor produced zero
parseable actions across all 3 (that means the prompt or parser is broken and the full run would
waste the GPU). A low success rate is **not** a failure — an un-helped 8B model scoring near zero on
AppWorld is an expected and scientifically meaningful result. Only crashes and unparseable output
are gate failures.

Then the full campaign:

```
"${SIDEKICK_VENV}/bin/python" -m sidekick.runner \
  --system executor_alone --split dev --tasks 57 --seeds 1,2 \
  --env appworld --workers 10 \
  --config configs/pilot_exec_8b.yaml --out "${OUT}"
```

`--workers 10` fits within 12 CPUs. AppWorld mocks time process-wide with freezegun, so the runner
uses a `multiprocessing` pool — one world per process. Never change it to threads.

Repeat both commands with `configs/pilot_exec_3b.yaml`.

## Step 4 — manifest and verification

For each campaign write
`/scratch/n12194778/sidekick/results/results/<campaign_id>/manifest.json` with: the worktree git
commit, vLLM version, the model's resolved HF revision, the AppWorld commit from
`/scratch/n12194778/sidekick/appworld.commit`, the config sha256, split and task count actually
used, hostname, PBS job id, start/end timestamps, and total executor tokens and GPU seconds.

Verify and record in STATUS:

- `result.json` count per model (expect 114 each, plus 3 smoke);
- task goal completion rate per model per seed;
- **total planner calls, which must be exactly 0** — report it explicitly;
- mean steps per episode and mean executor tokens per episode;
- that seed 1 and seed 2 actually differ (proving temperature took effect).

## Step 5 — commit

Commit the two configs, the PBS script and your STATUS file on the current branch. Nothing under
`/scratch`. End the commit message with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WAcXxoXWcJdXBPnbnHPek8
```

## STATUS file contract

Keep `campaign/workers/STATUS_U7.md` current at every milestone (configs written, PBS written,
submitted + job id, 8B smoke, 8B campaign, 3B smoke, 3B campaign, verified), each with a timestamp
and enough detail to resume from that point. `hpc-guard` kills anything at 12 h wall.

## Return contract

Report, in under 30 lines: the PBS job id, both smoke gate outcomes, runs completed per model, task
goal completion per model, the total planner call count (must be 0), and whether the two seeds
differ. Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. Do not report success for
anything you did not observe in an artifact on disk. Reporting that a campaign ran without checking
the result files is the one unforgivable error here.
