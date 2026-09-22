# Brief X37 — a zero-shot second executor family, to test whether the threshold is general

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`, or anything that waits on the PBS
queue — I submit and run everything myself.** Read files, write files, stop. One pass.

## Why this unit exists, and why it is now urgent

An hour ago the campaign measured a zero-shot receiver — base granite, no adapter — against the
tailored one at matched prefix depth:

| receiver | m=6 | m=9 | rise |
|---|---|---|---|
| zero-shot base granite | 0.6825 | 0.7845 | **+10.20 pp** |
| tailored (`sft_b_plus`) | 0.7237 | 0.7852 | +6.15 pp |

The threshold rise is **not** produced by tailoring: an untrained model shows it, and shows it more
strongly. At m=9 the two receivers are indistinguishable (−0.06 pp).

That makes the remaining question *generality across model families*. `docs/prereg_hj13_shape_20260923.md`
§5 kill-condition 4 is a conjunction: the finding dies if "the second family shows no threshold **and**
the zero-shot receiver shows the same rise as the tailored one". The second half is now true. The
first half has never been tested — there are no `hj14_*` results on disk and no `*qwen*` adapter.

Crucially, because the rise does not need tailoring, **the second family does not need training
either**. A zero-shot Qwen3-8B receiver answers the question with one GPU job, no SFT run, and zero
hosted calls. That is what you are wiring.

## Task A — two configs

Create `configs/hj15_prefix_zsq_m6.yaml` and `configs/hj15_prefix_zsq_m9.yaml`.

Each is a **copy of `configs/hj14_prefix_m{6,9}.yaml`** changing only:

- the header comment (say: zero-shot Qwen3-8B receiver, no LoRA, second-family control for the
  threshold; copied from the `hj14_prefix_m{K}` config);
- `campaign_id` → `hj15_prefix_zsq_m{6,9}_20260923`;
- `executor.lora_name` → `null`.

`executor.model` stays `Qwen/Qwen3-8B`. Prefix depth, source campaign, seeds, `max_steps`,
`max_prompt_tokens`, `max_planner_calls`, temperature, stop strings and every other field must match
the `hj14_prefix_m{K}` file exactly — otherwise the cross-family comparison is confounded and the
unit is worthless.

Follow the `lora_name: null` comment style already used at `configs/hj13_prefix_zs_m6.yaml:29`, which
records the real hazard: a dummy alias that is *not* in `--lora-modules` still silently hits the base
model while `usage.model` names the alias.

Write a test asserting each `hj15_prefix_zsq_m{K}.yaml` parses equal to `hj14_prefix_m{K}.yaml`
except for `campaign_id` and `executor.lora_name`, in the style of
`tests/unit/test_hj13_prefix_hf.py`.

## Task B — the harness must not demand an adapter that no arm uses

This is the load-bearing part, and there is a precedent to copy exactly.

`scripts/pbs/hj12_prefix.pbs:409-411` resolves the Qwen group's `EXPECT_ALIAS` /
`ADAPTER_PATH` to `sft_b_plus_qwen8b` / `.../adapters/sft_b_plus_iaware_qwen8b`
**unconditionally**, and `register_lora` (`:346-355`) **exits 2 when the path is not a directory**.
That adapter does not exist and is not going to for this unit. So as the script stands, a Qwen group
containing only zero-shot arms dies on an adapter it never needed.

Fix it the way X35 already fixed the identical defect for granite's handoff adapter at `:914-946`:
compute, while walking `PENDING_ARMS`, whether **any** arm in the group actually names an adapter
alias, and register only what is needed. If every arm in the group has `lora_name: null`, start vLLM
with **no** `--lora-modules` at all and register nothing.

Two things that must NOT change:

- A **mismatch** between a config's `executor.lora_name` and a served alias must stay **FATAL**. Do
  not make the harness tolerant. The whole point is that a mis-aliased run looks normal while
  measuring the wrong model.
- A group that *does* contain a tailored arm must still fail loudly if that adapter is missing.

Only the "nobody asked for an adapter" case becomes non-fatal. Add the two `FREE_ARMS` entries for
the new arms, following the existing pattern at `:149-173`.

Write a test in the style of `tests/unit/test_hj13_prefix_hf.py` asserting (a) a Qwen group of
zero-shot-only arms does not require the Qwen adapter, and (b) a Qwen group containing
`hj14_prefix_m6` still does.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `tar`, `rsync`, `ffmpeg`, **no `pytest`, no
  `hpc`, no `qsub`** in this unit.
- Frozen, read-only: every `docs/prereg_*.md`, every `hj8_*` and `hj11_*` config, and
  `configs/hj12_prefix_*.yaml` / `configs/hj14_*.yaml` — **copy from them, never edit them**.
- Do not edit `scripts/analysis/hj12_shape.py` (another unit just changed it),
  `scripts/analysis/j8_frontier.py`, or anything under `src/sidekick/training/`.
- Read-only on `/scratch/n12194778/sidekick/results/`. Never read or list `test_normal` /
  `test_challenge`.
- `scripts/setup/verify_configs.py` must still pass with your files present — the harness verifies
  **every** config before starting any arm, so one malformed file kills every arm in the run. This
  has already cost this campaign two GPU jobs. You are not running it; just do not break it.
- **Do not commit.** I review and commit.
- **Make your first file edit within your first three actions. Never background a command.**

## Return contract

`campaign/workers/STATUS_X37.md`, under 400 words: the two config paths and their exact diff against
the `hj14_prefix` counterparts; the harness hunk you changed, quoted before and after, with the line
numbers; the `FREE_ARMS` entries; the test names. Then state, unrun, the one command I should use to
evaluate both arms.

Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. **Do not claim any test passes —
you are not running them.** If you do not finish, say so in plain words at the top of STATUS.
