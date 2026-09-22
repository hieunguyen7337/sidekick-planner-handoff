# Brief X34 — eval arms for the handoff-trained adapter, completing a three-way receiver contrast

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Configs, a harness wiring change and tests. **Do NOT `qsub` anything and do not touch a GPU** — I
submit every job myself. Two GPU jobs and a training job are in flight.

## What this completes

The campaign is about to have three receivers that can each be handed the same replayed planner prefix:

| receiver | adapter | what it was trained on | arms |
|---|---|---|---|
| **base** | none (`lora_name: null`) | — | `hj13_prefix_zs_m{6,9,11}` (exist, running) |
| **generally tailored** | `sft_b_plus` (alias of `sft_b_plus_iaware_granite8b`) | correction / intervention data | `hj12_prefix_m{6,9,11}` (exist) |
| **handoff-specialised** | `sft_b_plus_handoff_granite8b` | **suffixes of planner trajectories cut at m ∈ {6,9,11}** | **you build these** |

That three-way contrast is the point. The interesting question is not "does tailoring help" but
**which kind** of tailoring helps a small model finish a stronger model's trajectory. Nobody has run
this at an 8B-local versus hosted-frontier capability gap, and all three arms are free.

## Task A — three configs

Create `configs/hj13_prefix_hf_m6.yaml`, `hj13_prefix_hf_m9.yaml`, `hj13_prefix_hf_m11.yaml`.

Each is a **copy of the corresponding `configs/hj12_prefix_m{6,9,11}.yaml`**, changing only:

- the header comment,
- `campaign_id` → `hj13_prefix_hf_m{6,9,11}_20260923`,
- `executor.lora_name` → `sft_b_plus_handoff`.

Nothing else may differ. The prefix depth, the source campaign, seeds, `max_steps`,
`max_prompt_tokens` and every policy field must match the m-matched `hj12_prefix` config exactly, or
the three-way contrast is confounded. Write a test that asserts this field-by-field: load each
`hj13_prefix_hf_m<K>.yaml` and the matching `hj12_prefix_m<K>.yaml` and assert the parsed dicts are
identical except for `campaign_id` and `executor.lora_name`.

## Task B — serve the adapter under the right alias

`scripts/pbs/hj12_prefix.pbs` launches vLLM with `--lora-modules`. Its own header warns that the alias
launched there **must equal `executor.lora_name` or requests silently hit the base model** — that is
the exact failure this campaign has to avoid, because a mis-aliased run looks completely normal in the
records while measuring the wrong model.

Add the alias `sft_b_plus_handoff` pointing at
`/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_handoff_granite8b`, **alongside** the
existing `sft_b_plus` alias — do not replace it, both must be servable in one job. Add the three arms
to `FREE_ARMS` following the existing pattern.

⚠ The adapter directory **does not exist yet** — training has not run. Your configs and wiring must be
correct in advance; do not create a placeholder directory, and do not make the harness tolerate a
missing adapter. If it is missing at run time the job should fail loudly.

## Task C — the record check that makes the contrast checkable

Write a test in the style of `tests/unit/test_hj13_prefix_zs.py` asserting the three receivers are
distinguishable in the run records: base resolves to `ibm-granite/granite-4.2-8b`, the tailored arm to
`sft_b_plus`, and the handoff arm to `sft_b_plus_handoff`, both in the request model field and in
`run_start.payload.policy.adapter_name`.

This matters because it has already been verified live for two of the three: the zero-shot arm's events
carry `"model":"ibm-granite/granite-4.2-8b"` with `adapter_name: null`, and the tailored arm's carry
`"model":"sft_b_plus"` with `adapter_name: sft_b_plus` [OBSERVED
`/scratch/n12194778/sidekick/results/hj13_prefix_zs_m6_20260923` and `.../hj12_prefix_m6_20260923`
`events.jsonl`]. The third must be equally checkable before it runs.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run tests through `hpc`; BLAS pinned to one thread.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read or list `test_normal`
  or `test_challenge`.
- Frozen, read only: every `docs/prereg_*.md`, every `hj8_*` and `hj11_*` config, and
  `configs/hj12_prefix_*.yaml` (copy from them, never edit them).
- Do not edit `src/sidekick/training/*`, `scripts/analysis/j8_frontier.py`, or
  `src/sidekick/training/matched_sft.py` — other units own these right now.
- `scripts/setup/verify_configs.py` must print "all configs OK" with your new files present. The
  harness verifies **every** config before starting any arm, so one malformed file kills every job in
  the run; this has already cost two GPU jobs in this campaign.
- **Make your first edit within your first three actions. Never background a command and exit.**
- **Write `campaign/workers/STATUS_X34.md` even if you finish only part of this.**
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X34.md`, under 400 words: the three config paths and the exact diff against
their `hj12_prefix` counterparts; the vLLM alias line you added and where; the `FREE_ARMS` entries; the
test names; the pasted `verify_configs.py` line; and the pasted suite line.

Then state the one command I should run to evaluate all three arms once the adapter exists, unrun.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
