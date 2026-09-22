# Brief X22 — two configs and one PBS parameterisation for the approved hosted wave

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Configs and shell only. **Do NOT `qsub`. Do NOT run any evaluation. Do NOT touch a GPU.** These arms
spend real hosted money and I submit them myself after reviewing your diff. A submission from this
unit is the one unrecoverable mistake available to you.

## Context

A hosted wave of roughly 5,000 planner calls has been approved. Five arms run. Three already have
configs and are registered in `scripts/pbs/hj12_live.pbs` `LIVE_ARMS` [OBSERVED
`scripts/pbs/hj12_live.pbs:155-162`]: `hj12_advise_fixed_k_10_fullctx`, `hj12_planner_handoff`,
`hj12_takeover_fixed_k_10`. Two do not exist yet. That is this unit.

## Task 1 — `configs/hj13_planner_alone_cap81.yaml`

The ceiling arm `hj1b_planner_20260915` ran under `max_planner_calls: 25` [OBSERVED
`configs/pilot_planner_alone.yaml:25`], while every arm it is compared against uses 81 [OBSERVED
`configs/hj8_fixed_k_3.yaml:39-41`, whose comment records the 25 cap ended 11 of 12 `limit`
episodes]. Every non-inferiority claim in the campaign is therefore against an understated ceiling.

Copy `configs/pilot_planner_alone.yaml` and change **exactly three things**:

1. the header comment, to say this is the uncapped re-run of the ceiling arm and why;
2. `campaign_id: hj13_planner_alone_cap81_20260923`;
3. `max_planner_calls: 25` → `81`.

Everything else — planner type, model `gpt-5.6-luna`, `reasoning_effort: medium`, timeouts,
`max_steps: 40`, prices — is byte-identical. A diff against the source must show three changed
regions and nothing else. Say so in STATUS and paste the diff.

## Task 2 — `configs/hj13_advise_fixed_k_1_fullctx.yaml`

Purpose: price the **advice** channel at or above the budget where the **action** channel wins. The
campaign's most expensive advice arm costs about 204.5k non-cached planner tokens per episode; the
action arms that win cost 357k and 443k. Advice has never been priced there, so the claim that the
channel rather than the budget determines quality is currently unsupported at matched spend. This arm
fixes that.

Copy `configs/hj12_advise_fixed_k_10_fullctx.yaml` and change **exactly three things**:

1. the header comment, to state the purpose above;
2. `campaign_id: hj13_advise_fixed_k_1_fullctx_20260923`;
3. `fixed_k: 10` → `fixed_k: 1` (review at every step).

Keep `correct_context: full` — starved advice is already a known confound and this arm must not
reintroduce it. Keep the `packet_source` / `packet_system` cached-plan block exactly as it is: the
up-front plan must stay free so the arm's cost is purely the reviews.

**Do not** try to tune `fixed_k` to hit a token target. Reviewing every step is the honest maximum,
and I want the projection from the smoke run, not an estimate.

## Task 3 — register the new advise arm

Add one line to `LIVE_ARMS` in `scripts/pbs/hj12_live.pbs`, in the same format as its neighbours:

```
  "fixed_k|${REPO}/configs/hj13_advise_fixed_k_1_fullctx.yaml|hj13_advise_fixed_k_1_fullctx"
```

Change nothing else in that file. In particular do not alter `MAX_PLANNER_CALLS`, the smoke gate, the
projected-spend check, or the vLLM alias logic.

## Task 4 — let the planner-alone PBS take a config

`scripts/pbs/hj1b_planner_alone.pbs` hard-codes `CID=hj1b_planner_20260915` [OBSERVED
`scripts/pbs/hj1b_planner_alone.pbs:33`] and its config path. Parameterise both **without changing
default behaviour**:

- `CONFIG="${CONFIG:-<the existing hard-coded path>}"`
- `CID="${CID:-hj1b_planner_20260915}"`

A submission that passes neither variable must behave exactly as it does today — same config, same
campaign id, same output path. Document the new submission form in the header comment, matching the
house style of `scripts/pbs/hj12_live.pbs:12-13`, and add the line `# Do NOT submit from a worker.`

If that file already reads `CONFIG`/`CID` from the environment, say so in STATUS and change nothing.

## Verification (no submission)

- `bash -n scripts/pbs/hj1b_planner_alone.pbs` and `bash -n scripts/pbs/hj12_live.pbs` — both clean.
- Both new configs parse as YAML. Read them with `python -c` **inside `hpc`**, never on the login
  node, or use a YAML-aware tool if one is available without an interpreter.
- Confirm both new configs resolve `planner.type: codex` and `planner.model: gpt-5.6-luna`. An arm
  that silently resolves to another model spends money measuring nothing.
- Grep both new configs for `max_planner_calls` and paste the values.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Compute through `hpc`.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read `test_normal` or
  `test_challenge`.
- Frozen, read only — **do not edit**: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, `docs/prereg_hj12_dev_20260922.md`,
  `docs/prereg_hj13_shape_20260923.md`, every `hj8_*` and `hj11_*` config, and
  `configs/pilot_planner_alone.yaml` (copy it, never modify it).
- New arm, new prefix: the new campaign ids must be `hj13_*` and must not collide with any existing
  directory under `/scratch/n12194778/sidekick/results/`. Check and report.
- The suite is at **506 passed, 1 skipped** and must not fall.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X22.md`, under 500 words: the two config paths, the pasted diff of each
against its source, the `LIVE_ARMS` line added, what you changed in the planner-alone PBS and proof
the default path is unchanged, both `bash -n` results, the `max_planner_calls` values, the
planner-model check, and confirmation that no `hj13_*` results directory already exists. Tag every
claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.

State plainly in STATUS: **you did not submit any job.**
