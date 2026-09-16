# Unit U-A2 — the SFT(b) dataset, the LoRA trainer, and the two PBS jobs

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Context

A campaign is collecting the teacher data right now: `planner_alone` (hosted gpt-5.6-luna) over the
AppWorld **train** split, 90 tasks × 2 seeds, campaign id `hj2b_planner_train_20260916`, results under
`/scratch/n12194778/sidekick/results/hj2b_planner_train_20260916/planner_alone/<seed>/<task_id>/`.
Expect roughly 125 solved trajectories and ~1,550 steps. This unit turns those into an SFT dataset and
trains a LoRA adapter on granite-4.2-8b.

`src/sidekick/training/` currently contains only `assert_no_leakage`. Everything here is new.

## Files in scope

- `src/sidekick/training/sft_data.py` — new.
- `scripts/train/sft_lora.py` — new (create the `scripts/train/` directory).
- `scripts/pbs/train_sft.pbs` — new.
- `scripts/pbs/hj3_eval.pbs` — new.
- `tests/unit/test_sft_data.py` — new.

🔺 **Out of scope:** `src/sidekick/systems/loop.py`, `runner.py`, `agents/`, `replay.py`,
`configs/`, and `src/sidekick/protocols/prompts.py` — you **import** the renderer, you never edit it.

## The renderer you build against (another unit owns it; treat as fixed)

`src/sidekick/protocols/prompts.py`:

```python
EXECUTOR_SYSTEM_PROMPT: str
def render_executor_messages(*, instruction, api_docs="", packet=None, history) -> list[dict]
# history: [{"role": "assistant"|"user", "content": str}, ...]
# returns [{"role":"system",...},{"role":"user",...}] + history
```

🔺 **Training data and inference must come from the same renderer.** If they diverge, the adapter is
trained on a prompt distribution it will never see, and the resulting number is meaningless in a way
no test catches. If the file is not present yet, write against this signature and say so in your
report; do not invent a second renderer.

## Part 1 — `sft_data.py`

```python
def build_sft_dataset(campaign_root, split_ids, out_jsonl, *, system="planner_alone",
                      solved_only=True) -> dict
```

For each run directory under `campaign_root/<system>/<seed>/<task_id>/`:

- Read `result.json`; skip unless `success` is true when `solved_only`.
- Read `events.jsonl` and use **only events after the LAST `run_start`** — a retried run appends to
  the dead attempt's log, so a file can hold two attempts concatenated with nothing marking the
  boundary (`docs/FOLLOWUPS.md`). Order by **file order**, never by `ts`: `ts` is frozen by freezegun
  and identical across events.
- Build `history` the same way the loop does: each executed action an `assistant` turn in canonical
  form (```python fence / `ASK_PLANNER:` / `REPORT:` / `COMPLETE`), each observation a `user` turn
  `OBS: {text}`. Recover the instruction, the api digest and the plan packet from the run's own events.
- Emit **one JSONL line per trajectory**: `{"messages": [...], "meta": {...}}` where `messages` is
  exactly what `render_executor_messages` returns and `meta` carries `task_id`, `seed`, `run_id`,
  `n_turns`, `source_campaign`, and the run's `SIDEKICK_START_COMMIT` if recorded.

Then:

- **Leakage check**: call `assert_no_leakage` (already in `src/sidekick/training/`) with the training
  task ids against the dev and test id sets. Read its real signature first. It must run
  unconditionally, not behind a flag — a silent dev/test leak would invalidate every downstream number.
- Write `<out_jsonl>.manifest.json`: task ids, run ids, counts, the source campaign root, the source
  commit, the sha256 of the jsonl, token-length percentiles (p50/p90/max) over the rendered
  conversations, and the count of trajectories dropped with the reason.
- Return a summary dict and print it.

CLI: `--campaign-root`, `--out`, `--split` (which ids count as train), `--system`, `--no-solved-only`.

## Part 2 — `scripts/train/sft_lora.py`

TRL `SFTTrainer` + PEFT LoRA. Installed versions: vllm 0.29.0, trl 1.13.0, peft 0.20.0,
transformers 5.17.0, torch 2.13.0 — **check the real signatures in the installed packages rather than
recalling an older API**; TRL's config arguments have moved repeatedly.

- Base model `ibm-granite/granite-4.2-8b` (cached under `/scratch/n12194778/hf/hub`, so `HF_HOME=/scratch/n12194778/hf`).
- LoRA r=64, alpha=128, dropout 0.05, targets `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`.
- lr 1e-4, cosine schedule, warmup ratio 0.03, 2 epochs, bf16, gradient checkpointing,
  per-device batch 1 with gradient accumulation to an effective batch of 8, `max_length` 32768.
- 🔺 **Manual assistant-token masking.** Tokenise turn by turn and set labels to -100 everywhere except
  the assistant turns' own tokens. Do **not** rely on a chat template's `{% generation %}` markers —
  whether Granite's template emits them is not something to assume, and a silently unmasked run trains
  the model to predict observations, which looks like successful training and produces a useless
  adapter. Include a test that on a 3-turn example the unmasked label positions are **exactly** the
  assistant token spans.
- Save the adapter, a `manifest.json` (base model, data sha256, all hyperparameters, seed, commit,
  package versions) and `train_log.jsonl` (per-step loss).
- `--dry-run`: 20 optimiser steps on 20 sequences, must finish in under 10 minutes.
- Flags: `--data`, `--out`, `--base-model`, `--epochs`, `--lr`, `--rank`, `--dry-run`, `--seed`.

## Part 3 — `scripts/pbs/train_sft.pbs`

`#PBS -q gpu_inter`, `-l select=1:ncpus=16:ngpus=1:mem=128gb`, `-l walltime=06:00:00`, `-j oe`,
output under `campaign/workers/logs/`. Copy the environment block verbatim from
`scripts/pbs/hj1c_fixed_k.pbs:19-40` — the BLAS pins, `HF_HOME`, `SIDEKICK_VENV`, `PATH`, `PYTHONPATH`,
the `CU13` CUDA block, `VLLM_USE_FLASHINFER_SAMPLER=0`, `ulimit -n`, the inductor/triton cache dirs —
those were all found the hard way on a cold node. `timeout` on every long command. Run the `--dry-run`
first and abort the job if it fails, then the real training. Echo the adapter path at the end.

## Part 4 — `scripts/pbs/hj3_eval.pbs`

Serves the trained adapter under vLLM and runs the dev evaluation. Model the vLLM launch, readiness
polling and teardown on `scripts/pbs/hj1c_fixed_k.pbs` (read it fully — it has a working
`kill_vllm` trap and a health-check loop).

🔺 **LoRA must be registered at launch, statically:**
`--enable-lora --max-loras 4 --max-lora-rank 64 --lora-modules <alias>=<abs path> [...]`.
Dynamic adapter loading was tried in G3 and failed; only the static form works. **The alias must equal
the config's `executor.lora_name`** or requests silently hit the base model and the whole evaluation
measures nothing. Accept the adapter aliases/paths as job variables at the top of the file so the same
script serves `sft_b`, `sft_c`, `sft_b_plus` and `sidekick` later. Do **not** copy the reasoning-parser
flags from G3.

Keep the codex preflight from `hj1c_fixed_k.pbs` (auth.json present, never printed): the `sft_plan`
arm allows executor ASKs, so a planner call is possible even though HJ-1 measured zero of them.

The campaign invocations themselves will be added by Claude once the eval configs exist — leave a
clearly marked, commented block where they go, with the smoke-then-full, separate-`_smoke`-campaign-id,
purge, gate and manifest structure already written out.

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pytest`, `pip`, `tar`, `rsync`, `qsub`, or any
  multi-minute command, and do not start vLLM or any training.** Claude submits the jobs.
- Do not modify anything under `campaign/results/` or `/scratch`.
- Ignore `.claude/worktrees/` and `.git/`.
- Write `campaign/workers/STATUS_UA2.md` as you go (done / next / how to resume).

## Return contract (under 35 lines)

- `build_sft_dataset`'s signature and the exact JSONL line schema.
- The masking implementation in ~10 lines, quoted, plus how the test pins it.
- The TRL/PEFT API you actually found installed, with the version you checked against
  `[OBSERVED <path>:<line>]` — name anything that differs from this brief.
- The `--lora-modules` line as written, and where the alias comes from.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
