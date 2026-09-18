# A13 (U-V4) — two small guards on the J8 harness, before it is ever submitted

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your only file is `scripts/pbs/hj8_frontier.pbs` (plus a test only if the tree
has a natural place for one — check, do not invent a framework for a shell script).
**Do not touch** `configs/`, `src/`, `scripts/setup/`, `scripts/analysis/` — other units own those.
This is a small, surgical unit. Do not refactor the script.

🔺 **Do not submit this job or any GPU job.** A training job is running right now and the GPU
queue is congested. You are editing a script, not running it.

## Defect 1 — the adapter guard accepts a half-trained adapter

`register_lora` accepts any path that is a **directory**
[OBSERVED scripts/pbs/hj8_frontier.pbs:262-265].

That is not sufficient, and it is live right now. The training job writing
`/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b` **creates the directory at
the start of the run**. As of 02:03 today that directory contains only `trainer_state/` and
`train_log.jsonl` — **no `adapter_config.json` and no `adapter_model.safetensors`** [OBSERVED
`ls -la` of that path]. A completed adapter looks like
`/scratch/n12194778/sidekick/artifacts/adapters/sft_b_s123_granite8b`, which has
`adapter_config.json`, `adapter_model.safetensors`, `manifest.json`, the tokenizer files and
`README.md` [OBSERVED `ls` of that path].

So if this job were submitted before training finished, the guard would pass, vLLM would be handed
a LoRA directory with **no weights**, and every arm would quietly serve the base model. The result
would be a complete, plausible, entirely meaningless set of numbers — the exact failure class
catalogued in `campaign/RUNS.md` and in `docs/FOLLOWUPS.md`.

**Fix:** require the files that actually make an adapter loadable — at minimum
`adapter_config.json` and the weights file — and FATAL naming the missing file if absent. Check
what vLLM genuinely requires rather than copying my list; if the weights can legitimately have
another filename (e.g. a `.bin` variant), accept either and say so in a comment. **Do not** merely
count files.

## Defect 2 — there is no way to validate the harness without also running a full campaign

`run_arm` runs a 3-task smoke, gates it, then falls straight through to the full 57-task × 2-seed
campaign [OBSERVED scripts/pbs/hj8_frontier.pbs:330-360]. There is no way to stop after the smoke.

That blocks a validation I want to run **now**, while the real adapter is still training: point
the harness at the already-complete `sft_b_s123_granite8b` adapter, prove the 12 configs load, the
gate passes and an episode completes end to end — without spending hours of GPU on a campaign
whose adapter is deliberately the wrong one.

**Fix:** add a `SMOKE_ONLY` job variable (default off, so nothing changes for a normal run). When
set, each arm runs its smoke and gate and then **stops before the full campaign**, and the job
exits non-zero if any arm's smoke fails. Document it in the header comment beside the existing
`ARMSET`/`DATE`/`ADAPTER_SFT_B_PLUS` list [OBSERVED :43-44].

Keep the existing resume behaviour intact: an arm that already has results skips its smoke
[OBSERVED :351-353]. Think about how `SMOKE_ONLY` interacts with that and say what you decided —
a smoke-only run must not leave state that makes a later real run skip its own smoke, and it must
not delete a real campaign's results. The smoke campaign id is already separate (`scid`) and is
removed after the gate [OBSERVED :331, :350]; confirm that is still true under your change.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. Any check runs in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread.
  Run jobs **synchronously**; never background one and exit.
- 🔺 **Zero planner calls. Do not invoke `codex`** — quota is exhausted until ~21:13 today.
- 🔺 **Do not submit any GPU job. Do not submit this script.**
- 🔺 **Do not modify anything under `/scratch/.../results/` or `/scratch/.../adapters/`.** In
  particular the adapter directory named above is being written by a live training job — read it,
  never touch it.
- **Do not commit.** Suite baseline **402 passed, 1 skipped**; a shell-only change should leave it
  untouched.
- `bash -n` the script, and `shellcheck` it if available; say whether you did.
- Write `campaign/workers/STATUS_A_13.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the `bash -n` output.
- What you decided vLLM actually requires for a loadable LoRA, and how you checked.
- How `SMOKE_ONLY` interacts with resume, and your confirmation that a smoke-only run cannot
  delete or shadow a real campaign's results.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
