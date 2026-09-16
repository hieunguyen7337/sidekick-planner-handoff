# Unit U-D2 — the HJ-1R configs and the one GPU job that runs J1

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Context

HJ-1's two untrained-executor arms (`executor_alone`, `prompt_only`) both scored 0.000 — but under a
prompt that never showed the executor its own past actions (harness defect #16, now fixed: the
executor prompt is rendered multi-turn by
`src/sidekick/protocols/prompts.py:render_executor_messages`). Those zeros are therefore not a clean
baseline, and no SFT result may be compared against them.

**HJ-1R re-measures both arms on dev under the fixed prompt.** In the same job, a state probe asks
whether granite-4.2-8b can act correctly when it *is* given a correct history — the measurement that
decides whether the next 20 GPU-hours train this model or replace it.

`prompt_only` needs a plan per task. It must **replay HJ-1's archived packets** rather than buying new
ones: `planner.packet_source` (built in unit U-C) makes `plan()` read the packet from an archived
campaign, spending zero hosted calls and giving every arm a byte-identical plan per task.

## Files in scope

- `configs/hj1r_exec8b.yaml` — new.
- `configs/hj1r_prompt_only.yaml` — new.
- `scripts/pbs/hj15_state_probe.pbs` — new.

🔺 **Out of scope:** everything under `src/`, `tests/`, and every existing config or PBS script. The
`configs/pilot_*.yaml` and `scripts/pbs/hj1*.pbs` files are **frozen** — their hashes appear in
archived manifests. Copy from them; never edit them.

## The two configs

`configs/hj1r_exec8b.yaml`: copy `configs/pilot_exec_8b.yaml`, changing only
`campaign_id: hj1r_exec8b_20260916` and `limits.max_planner_calls: 81` (harmless here — this arm makes
no planner calls — but keeps every new config on one cap convention). Everything about the executor,
including `stop` and `chat_template_kwargs.enable_thinking: false`, stays byte-identical to the
frozen pilot: the point of a re-run is that **only the prompt changed**.

`configs/hj1r_prompt_only.yaml`: copy `configs/pilot_prompt_only.yaml`, changing
`campaign_id: hj1r_prompt_only_20260916`, `limits.max_planner_calls: 81`, and adding to the `planner:`
block:

```yaml
  packet_source: /scratch/n12194778/sidekick/results/hj1b_planner_20260915
```

🔺 Read `src/sidekick/agents/planner.py` and `src/sidekick/runner.py` (unit U-C landed there) and use
the **actual** key name and value form that `make_planner` reads — if it differs from the above, follow
the code and say so in your report. Comment the line to say the arm spends **zero** hosted planner
calls and that every arm consequently sees the identical plan per task, which removes plan-sampling
noise from the comparison.

Both configs get a header comment saying they are the HJ-1R re-run under the fixed multi-turn executor
prompt, that they are paired against the HJ-1 originals, and that only the prompt differs.

## The job — `scripts/pbs/hj15_state_probe.pbs`

`#PBS -q gpu_inter`, `-l select=1:ncpus=12:ngpus=1:mem=64gb`, `-l walltime=04:00:00`, `-j oe`,
output to `campaign/workers/logs/hj15_state_probe.out`.

Take the environment block, the vLLM launch, the readiness poll, the `kill_vllm` trap and the codex
preflight **verbatim** from `scripts/pbs/hj1c_fixed_k.pbs` — read it in full first. Those settings
(the `CU13` CUDA block, `VLLM_USE_FLASHINFER_SAMPLER=0`, `ulimit -n`, the inductor/triton cache dirs)
were all found the hard way on a cold node.

Phases, in order, each `timeout`-wrapped and each echoing its exit code:

1. **Serve granite-4.2-8b** (`ibm-granite/granite-4.2-8b`, `HF_HOME=/scratch/n12194778/hf`). Wait for
   health, fail loudly if it never comes up.
2. **Smoke**: 3 dev tasks, seed 1, `executor_alone`, into campaign id `hj1r_exec8b_20260916_smoke`;
   gate it with `campaign_summarize.py --gate` (no `--expect-planner` — this arm has no planner);
   abort the job if the gate fails; `rm -rf` the smoke campaign on success. 🔺 The smoke campaign id
   must be **separate** from the full one: sharing an id is how stale smoke results were once
   re-graded into HJ-1.
3. **HJ-1R arm A**: `executor_alone`, dev, 57 tasks × seeds 1,2, 10 workers,
   `--config configs/hj1r_exec8b.yaml`, campaign `hj1r_exec8b_20260916`. ~30 min.
4. **HJ-1R arm B**: `prompt_only`, dev, 57 × seeds 1,2, 10 workers,
   `--config configs/hj1r_prompt_only.yaml`, campaign `hj1r_prompt_only_20260916`. ~50 min.
   Gate this one with `--expect-planner --expect-model gpt-5.6-luna`: replayed packets carry the
   original model id, so provenance must still read as luna. If the gate rejects a cached record,
   **stop and report** rather than loosening the gate.
5. **Probe on granite**: `scripts/setup/state_probe.py` against
   `/scratch/n12194778/sidekick/results/hj1b_planner_20260915`, writing
   `/scratch/n12194778/sidekick/results/probe_granite8b.json`. ~15 min.
6. **Swap models**: kill vLLM, wait for the port to free, relaunch on `Qwen/Qwen3-8B` with
   `HF_HOME=${HOME}/.cache/huggingface` — 🔺 Qwen3-8B is cached **there**, not under
   `/scratch/n12194778/hf/hub`, which holds granite-4.2-3b, granite-4.2-8b and Qwen3-1.7B. Getting
   this wrong makes the job silently try to download 16 GB from a compute node.
7. **Probe on Qwen3-8B** → `probe_qwen3_8b.json`. ~15 min.
8. **Summary + manifests** for both HJ-1R campaigns, then archive both campaign trees and both
   probe JSONs to `${HOME}/sidekick_data/` with `cp -a` (**not** `tar`, **not** `rsync`), guarded so
   an archive failure cannot mask the campaigns' own exit codes.

Each phase must be independently resumable: the runner skips runs whose `result.json` exists, and
`campaign_summarize --purge-broken` runs before each campaign so crashed runs retry. Structure the
script so that re-submitting it after a walltime kill continues rather than restarting. Record every
phase's exit code in one final `echo` line, and exit non-zero if any campaign or probe failed.

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pytest`, `pip`, `tar`, `rsync`, `qsub`, or any
  multi-minute command, and do not start vLLM.** Claude submits the job.
- Do not modify anything under `campaign/results/` or `/scratch`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract (under 25 lines)

- The two config paths and their diffs against the frozen pilots (just the changed lines).
- The `packet_source` key exactly as `make_planner` reads it `[OBSERVED <path>:<line>]`.
- The vLLM launch lines for both models, quoted, including each one's `HF_HOME`.
- How re-submission resumes rather than restarts, in two sentences.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
