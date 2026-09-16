# Unit U-B0 — the J2 (HJ-2B) teacher-demo config and PBS job

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Goal

Create exactly two new files so that the HJ-2B teacher-demo campaign can be submitted tonight:

1. `configs/train_planner_alone.yaml`
2. `scripts/pbs/hj2b_planner_train.pbs`

HJ-2B collects the SFT teacher data: `planner_alone` (gpt-5.6-luna drives every step, no executor,
no GPU) over the AppWorld **train** split, 90 tasks x seeds 1,2 = 180 episodes, running to the full
40 steps. Its solved trajectories become the SFT(b) dataset.

**Do not run the campaign. Do not call `qsub`. Do not run `python`, `pytest`, `pip`, `tar` or
`rsync`.** Claude submits the job and runs the checks. You write the two files and report.

## Hard constraints

- **Do not modify any existing file.** In particular `configs/pilot_*.yaml` and
  `scripts/pbs/hj1*.pbs` are FROZEN — they are the record of how HJ-1 ran and their hashes appear in
  archived manifests. Copy from them; never edit them.
- `aquarius01` is a login node. You must not execute any compute. File writes only.
- Ignore `.claude/worktrees/` and `.git/`.

## File 1 — `configs/train_planner_alone.yaml`

Base it on `configs/pilot_planner_alone.yaml` (read it first). Same `planner:` block (type codex,
binary codex, model `gpt-5.6-luna`, reasoning_effort `medium`, timeout_s 300, scratch_parent
`/scratch/n12194778/sidekick/codex_scratch`), same `executor: {type: mock}`, same
`prices: configs/cost/prices_2026-09.yaml`, `env: appworld`.

Differences, all deliberate:

- `campaign_id: hj2b_planner_train_20260916`
- `limits.max_steps: 40` (unchanged)
- `limits.max_planner_calls: 81` — **this is the point of the new config.** In HJ-1 the cap was 25
  and it, not `max_steps`, ended 11 of 12 truncated episodes (`docs/FOLLOWUPS.md`, section "Found by
  running the HJ-1 pilot"): in a planner-driven arm the planner takes every step, so calls and steps
  are the same quantity and the smaller cap wins. 81 = 2 * max_steps + 1, which leaves room for the
  step-0 plan call and for a timeout retry on every step, so that **`max_steps` is the binding cap**.
- `limits.max_tokens_per_episode: 20000000` — non-binding on purpose. `token_count` in
  `src/sidekick/systems/loop.py` counts **cached** input, and a `codex exec` call resends the whole
  transcript on ~15.4k of scaffolding, so a 40-step episode counts 3-7M tokens even though the
  uncached spend is a fraction of that. At 2,000,000 one HJ-1 episode was killed at 24 calls. The
  budget accounting is being corrected in a separate unit; this config must not depend on it.
- `limits.per_step_timeout_s: 120` (unchanged)

Every one of those four numbers gets a short comment saying **why**, in the voice of the existing
config (which explains its own values). State that the split is `train` and that this arm is the
teacher-demo collection for SFT(b), not an HJ-1 arm.

## File 2 — `scripts/pbs/hj2b_planner_train.pbs`

Start from `scripts/pbs/hj1b_planner_alone.pbs` — read it in full; it is the working CPU planner job
and its preflight, env block and resume behaviour are all wanted verbatim. Keep: `set -uo pipefail`,
the BLAS 1-thread exports, `HF_HOME`, `APPWORLD_ROOT`, `SIDEKICK_VENV`, `PATH`, `PYTHONPATH`, the
comment about `CODEX_HOME` deliberately not being set, `SIDEKICK_START_COMMIT`, the codex / auth.json
/ APPWORLD_ROOT preflight (which must never print the contents of auth.json), `--purge-broken` before
running, and the `timeout` wrapper on every long command.

Changes:

- `#PBS -N hj2b-train`, `#PBS -q cpu_inter`, `#PBS -l select=1:ncpus=8:mem=32gb`,
  `#PBS -l walltime=05:00:00`, `-j oe`,
  `-o /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/hj2b_planner_train.out`
- `CID=hj2b_planner_train_20260916`, `CFG="${REPO}/configs/train_planner_alone.yaml"`.
- 🔺 **The smoke slice runs under its own campaign id `SMOKE_CID="${CID}_smoke"`, and is purged when
  it passes.** `hj1b` deliberately shared one id between smoke and full run; that is the pattern that
  later caused stale smoke results to be re-graded as part of the campaign. Take the separated form
  from `scripts/pbs/hj1c_fixed_k.pbs` (read how it does it) — smoke runs into `${SMOKE_CID}`, gates on
  `${SMOKE_CID}`, and on success the smoke campaign directory is removed with `rm -rf` before the full
  run starts. The full campaign directory must never contain a smoke run.
- Smoke: `--system planner_alone --split train --tasks 3 --seeds 1 --env appworld --workers 3`,
  `timeout 1800`. Gate it with
  `campaign_summarize.py --out "${OUT}" --campaign-id "${SMOKE_CID}" --gate --expect-planner --expect-model gpt-5.6-luna --repo "${REPO}"`
  and abort (exit 3) if the gate fails. The smoke slice is also the first evidence that the AppWorld
  **train** split loads at all from `${APPWORLD_ROOT}` — say so in a comment, because if the train
  data is not present this is where the job dies and the message needs to make that obvious.
- Full run: `--system planner_alone --split train --tasks 90 --seeds 1,2 --env appworld --workers 6`,
  `timeout 16200` (4.5 h, inside the 5 h walltime). Expected ~1.7-2 h.
- Summary + manifest exactly as `hj1b` does it, into `"${OUT}/results/${CID}/manifest.json"`, plus a
  **final gate** on the full campaign:
  `--gate --expect-planner --expect-model gpt-5.6-luna`. Record its exit code in the final echo line;
  a failed final gate exits non-zero.
- 🔺 **Archive the event logs.** These trajectories ARE the training data and `/scratch` is not a
  durable store. After the manifest step, copy the campaign's results tree to
  `${HOME}/sidekick_data/${CID}/` with `cp -a` (a plain recursive copy — **do not** use `tar` or
  `rsync`), creating the directory first, and echo the resulting `du -sh`. Guard it so a failure here
  does not mask the campaign's own exit code.
- Every `echo` prefix becomes `[hj2b]`.

## Return contract (short — under 25 lines)

- The two paths you created.
- The exact `limits:` block you wrote, quoted.
- Confirmation, as `[OBSERVED <path>:<line>]`, that (a) you copied the separated-smoke pattern from
  `hj1c_fixed_k.pbs` and (b) you modified no existing file — `git status --short` output pasted.
- Anything in `hj1b_planner_alone.pbs` you chose NOT to carry over, and why.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
