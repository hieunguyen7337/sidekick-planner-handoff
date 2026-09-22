# Brief X38 — the narrated-prefix arm: the planner's recorded actions as TEXT, fresh environment

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`, or the script you write — I run
everything myself in PBS.** Read files, write files, stop. One pass. Make your first file edit within
your first three actions.

## Why this unit exists

The campaign's largest effect is the *channel* contrast: on the untailored base executor, one prose
plan from the planner buys +9.8 pp over executor-alone, while replaying the planner's first nine
recorded **actions** buys +59.4 pp (`docs/claims_ledger.md` CHAN-ZS-01). A reviewer will say: "of
course — the executed actions *moved the world*; the prose did not. Unfair by construction."

Today we cannot answer that, because the executed-prefix arm differs from the plan-only arm in two
ways at once: (1) the executor **sees** the planner's actions and their observations (they are seeded
into its context as real turns — `src/sidekick/systems/loop.py:584-606`, via `_history_from_events`),
and (2) the environment has **already been advanced** by those actions (`src/sidekick/replay.py:103`,
`world.step`). This unit builds the arm that separates (1) from (2): the executor gets the same
actions (and, in a second variant, the same observations) **as text inside the plan**, and starts from
step 0 in a **fresh** environment. Zero hosted calls — the actions are already recorded.

The result is publishable whichever way it lands, so build it straight, with no thumb on the scale.

## Design (decided — do not redesign)

Reuse the existing `sft_plan` system and `CachedPacketPlanner` unchanged. A packet source is just a
directory of `<packet_source>/<packet_system>/<seed>/<task_id>/events.jsonl` files whose last
`run_start`-delimited slice contains one `event_type == "plan"` event with `payload.packet` (a
`DelegationPacket` dict) and a non-empty `payload.model` (`src/sidekick/agents/planner.py:702-751`).
The executor sees the packet verbatim as `Plan: {packet.model_dump_json()}`
(`src/sidekick/protocols/prompts.py:222-229`). So: **write a synthetic packet directory** whose
packet = the planner's original packet **plus** the first m recorded actions appended as plan steps.
No new system class, no registry change, no change to `prompts.py`.

### Task A — `scripts/analysis/hj16_narrate_prefix.py`

CLI:

```
--source-campaign /scratch/n12194778/sidekick/results/hj1b_planner_20260915
--source-system   planner_alone
--m 9
--seeds 1,2
--with-observations            (flag; off = actions only)
--out /scratch/n12194778/sidekick/artifacts/packets/<name>
```

For every `<source>/<system>/<seed>/<task_id>/` directory (all 57 dev tasks × 2 seeds exist there):

1. **Select the events exactly as the replayed arm does.** Call the same code path `prefix_handoff`
   uses — `build_handoff_prefix` / `EpisodePrefix` in `src/sidekick/prefix_source.py:121-178` — so the
   narrated actions are byte-for-byte the actions the executed-prefix arm replays, with the same
   `effective_m = min(m, n_source_actions)` (`prefix_source.py:139`) and the same rule that only
   `CODE`/`COMPLETE` actions count (`prefix_source.py:40-51`, `replay.py:98-106`). Do **not**
   re-implement the selection.
2. **Take the original packet** from the source episode's own plan event (same loader semantics as
   `_load_plan_event`, `planner.py:718-745`): `goal`, `plan_steps`, every other field, untouched.
3. **Append one plan step per selected action**, after the original steps, continuing `index`:
   - `description`: `"Expert trajectory, step k of M (code the planner actually ran on this task): "`
     followed by the action's `code` verbatim (from the action event payload, `schemas.py:64-67`).
     For a `COMPLETE` action say so in the description instead of code.
   - `expected_outcome`: **empty string** without `--with-observations`; **with** the flag, the
     matching observation event's `payload.text`, truncated with the *same* rule `_history_from_events`
     applies when it seeds the executed-prefix executor's context (find it in `loop.py`; cite the
     line). Parity with what the prefix arm's executor sees is the whole point of the variant.
   - `apps`: empty list (or whatever the schema requires).
   Validate the result against `DelegationPacket` (`planner.py:28-66`) before writing. If the schema
   forbids appended steps for any reason, STOP and say so in STATUS — do not change the schema.
4. Write `<out>/<source-system>/<seed>/<task_id>/events.jsonl` containing exactly two lines: a
   `run_start` event and the `plan` event, `payload.model` = the source plan event's model (provenance)
   and an extra `payload.narrated_from` = the source episode path, `payload.narrated_m` = effective m,
   `payload.with_observations` = bool. Copy `manifest.json` fields the loader might need only if the
   loader reads them (check; cite).
5. Write `<out>/manifest.json`: source campaign, system, m, seeds, with_observations, per-seed counts,
   the count of episodes where effective m < m (prefix shorter than m), the git SHA of HEAD, timestamp.
6. **Refuse** any `--out` under `/scratch/n12194778/sidekick/results/` and any path containing
   `test_normal` or `test_challenge`; refuse to overwrite an existing non-empty `--out` unless
   `--force`. Print a one-line summary per seed and exit 0.

Keep it under ~250 lines, stdlib + the repo's own modules, BLAS irrelevant (no numpy).

### Task B — four configs, `sft_plan` system

Copies of `configs/hj8_sft_plan_bplus.yaml` changing **only** the header comment, `campaign_id`,
`planner.packet_source`, and (for the untailored pair) `executor.lora_name: null` with the hazard
comment style of `configs/hj13_prefix_zs_m6.yaml:29`:

| file | campaign_id | packet_source | lora_name |
|---|---|---|---|
| `configs/hj16_narrated_m9_zs.yaml` | `hj16_narrated_m9_zs_20260923` | `/scratch/n12194778/sidekick/artifacts/packets/hj16_narrated_m9` | `null` |
| `configs/hj16_narrated_obs_m9_zs.yaml` | `hj16_narrated_obs_m9_zs_20260923` | `.../packets/hj16_narrated_obs_m9` | `null` |
| `configs/hj16_narrated_m9_bplus.yaml` | `hj16_narrated_m9_bplus_20260923` | `.../packets/hj16_narrated_m9` | `sft_b_plus` |
| `configs/hj16_narrated_obs_m9_bplus.yaml` | `hj16_narrated_obs_m9_bplus_20260923` | `.../packets/hj16_narrated_obs_m9` | `sft_b_plus` |

`packet_system` stays `planner_alone` (the script writes that subdirectory name). Everything else —
`on_missing: fail`, temperature, `max_tokens`, stop strings, `max_prompt_tokens`, `max_steps`,
`max_planner_calls` — must match the template exactly; the comparison against the plan-only and
executed-prefix arms is confounded otherwise.

Confirm by reading `src/sidekick/systems/sft_plan.py` that `sft_plan` runs with `lora_name: null`
(no adapter assumption in the system itself; the adapter is a serving matter). Cite the line. If it
does not, say so in STATUS and stop; do not patch the system.

**`scripts/setup/verify_configs.py:146-162` asserts that every `packet_source` resolves on disk.**
The packet directories will not exist until I run your script, so verify_configs will fail on your
four configs until then. That is expected. Do not weaken verify_configs. State this in STATUS.

### Task C — harness entries

Add four `FREE_ARMS` lines to `scripts/pbs/hj12_prefix.pbs` after the `hj15_*` lines (`:174-175`),
system `sft_plan`, following the existing `sft_plan` entry format there. `sft_plan` is already in the
free-system case list (`:745-850`); touch nothing else in the harness.

### Task D — tests, `tests/unit/test_hj16_narrated.py`

Style of `tests/unit/test_hj15_prefix_zsq.py`. Build a small scripted source episode in `tmp_path`
(a `run_start`, a plan event with a two-step packet, then N action/observation pairs including at least
one non-counting `ASK_PLANNER` and a final `COMPLETE`) — look for an existing fixture that
`tests/unit/test_prefix_source*.py` or `test_replay*.py` already use and reuse it if there is one.

1. The actions the narrator selects for `m` are identical (order and content) to the actions
   `build_handoff_prefix` returns for the same `m` — including that `ASK_PLANNER` does not count.
2. The written `events.jsonl` loads through `CachedPacketPlanner`'s loader and yields a
   `DelegationPacket` with `len(plan_steps) == original + effective_m`, original steps unchanged.
3. `--with-observations` fills `expected_outcome` with the observation text (truncated per the rule);
   without it every appended `expected_outcome` is empty.
4. `effective_m < m` when the source is shorter, and the manifest counts it.
5. The four configs parse and equal `hj8_sft_plan_bplus.yaml` except the listed keys; the `zs` pair
   resolve to base granite with `lora_name` `None` (reuse the `_served_model` pattern from
   `test_hj15_prefix_zsq.py`).
6. `--out` under `/scratch/n12194778/sidekick/results/` is refused (exit non-zero, nothing written).
7. The four `FREE_ARMS` lines are present in the PBS text.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `tar`, `rsync`, `ffmpeg`, `pytest`, `hpc`,
  `qsub` in this unit. Read and write files only.
- Frozen, read-only: every `docs/prereg_*.md`, every `hj8_*`/`hj11_*`/`hj12_*`/`hj14_*` config — copy,
  never edit. Do not edit `src/sidekick/**` (the whole point is zero runtime change), `scripts/analysis/hj12_shape.py`,
  `scripts/analysis/j8_frontier.py`, `scripts/setup/verify_configs.py`.
- Read-only on `/scratch/n12194778/sidekick/results/`. Never read or list `test_normal`/`test_challenge`.
  You may read ONE source episode directory under `hj1b_planner_20260915/planner_alone/1/` to see the
  real event shapes (head, not the whole file).
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X38.md`, under 450 words: the script path and its CLI; the exact function you
call for event selection and why it guarantees parity (path:line); the truncation rule you mirrored
(path:line); the four config paths and their diff against the template; the `FREE_ARMS` lines; the test
names; the `sft_plan`-without-adapter citation; then, unrun, (a) the two `hpc` commands I should use to
build the two packet directories and (b) the one `qsub` command for the untailored pair.

Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. **Do not claim any test passes —
you are not running them.** If you do not finish, say so in plain words at the top of STATUS.
