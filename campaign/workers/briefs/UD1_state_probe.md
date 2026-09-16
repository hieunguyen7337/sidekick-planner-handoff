# Unit U-D1 — the state probe: can this executor act correctly given a correct history?

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why

HJ-1's executor arms scored 0.000, but under a prompt that hid the executor's own actions from it
(harness defect #16, fixed in unit U-A1). So we do not yet know whether granite-4.2-8b is untrained
or unusable — and that distinction decides whether the next 20 GPU-hours are spent training it or
replacing it.

The probe answers it cheaply and **without the planner**: take a trajectory the planner solved,
replay the first k steps into a fresh AppWorld so the world is in the exact state the teacher was in,
show the executor the gold history, and ask for step k+1. If it can act correctly from a correct
history, it is trainable. If it cannot, no amount of SFT on that history will help.

## Files in scope

- `src/sidekick/replay.py` — add one function. Do not change `replay()`.
- `scripts/setup/state_probe.py` — new.
- `tests/unit/test_replay_prefix.py` — new.

🔺 **Out of scope:** `src/sidekick/systems/loop.py`, `runner.py`, `agents/`, `configs/`,
`scripts/pbs/`, `src/sidekick/protocols/prompts.py` (you *import* the renderer, you do not edit it).

## Part 1 — `replay_prefix`

`replay()` (`src/sidekick/replay.py:~80-125`) walks the events, steps every recorded `CODE`/`COMPLETE`
action into a fresh world, compares `env_state_hash`, and then **calls `world.close()` and returns a
report** — so it cannot hand back a live world positioned mid-trajectory. Add:

```python
def replay_prefix(events_path, k: int, env=None) -> tuple[BaseEnv, list[Event]]:
```

which replays the first `k` executed (`CODE`/`COMPLETE`) actions and returns the **still-open** world
plus the remaining gold events, so the caller can ask the model for step k+1 and then close it.
Reuse `replay()`'s event-walking logic rather than duplicating it — factor the shared part out if
that is cleaner, but do not change `replay()`'s behaviour or signature.

🔺 **Only events after the LAST `run_start` count.** A retried run appends to the dead attempt's log,
so a file can hold two attempts concatenated with nothing marking the boundary (`docs/FOLLOWUPS.md`,
"A retried run appended its events to the dead attempt's log"). Order by **file order**, never by the
`ts` field — `ts` is frozen by freezegun and is identical across events. Check whether `replay()`
already handles this; if it does not, that is a real bug — report it, and make `replay_prefix`
correct regardless.

The caller owns closing the world. Say so in the docstring.

## Part 2 — `scripts/setup/state_probe.py`

For each solved teacher trajectory in a campaign (default
`/scratch/n12194778/sidekick/results/hj1b_planner_20260915`, system `planner_alone`), for each step
k in that trajectory:

1. `replay_prefix(events, k)` → a world in the teacher's state at step k.
2. Render the gold history with `render_executor_messages` from
   `src/sidekick/protocols/prompts.py` — **the same renderer inference uses**, so the probe measures
   the deployed prompt and not a lookalike. Build `history` from the gold events: each executed action
   becomes an `assistant` turn in canonical form, each observation a `user` turn `OBS: {text}`.
3. Ask the executor (`VLLMExecutor`, an OpenAI-compatible server at `--base-url`) for one action at
   **temperature 0** — this is a capability measurement, not a sample.
4. Parse it with `parse_executor_action` and execute it in the replayed world.

Score three metrics per step, and report each overall and bucketed by depth (k in 1-5, 6-10, 11+):

- **primary — `agreement`**: the action executed without an error **and** the set of
  `apis.<app>.<api>` identifiers it called equals the gold action's set. Extract identifiers with a
  regex over the code; a single `[OBSERVED]`-able regex constant, not scattered string matching.
- **`state_equivalent`**: take the **gold** next action, execute it in the probe's world, and check
  it returns the gold next observation. This asks "did the model leave the world in a state where the
  teacher's plan still works" — a weaker and more meaningful test than byte equality.
- **strict — `hash_match`**: `env_state_hash` equality. 🔺 Note in a comment that this is expected to
  be near-zero and is not a failure signal: `snapshot_hash` hashes `environment_io`, which **includes
  the input code** (`src/sidekick/environments/appworld_env.py:134-146`), so it can only match when
  the model emits byte-identical code to the teacher. Report it, do not gate on it.

Also report a `value_forwarding` subset: steps whose gold action references a value that first
appeared in an earlier observation (e.g. a token, id or username). That is precisely the
carry-state-across-steps ability in question, so break the three metrics out for it too.

CLI: `--campaign-root`, `--system` (default `planner_alone`), `--model`, `--base-url`,
`--lora-name` (optional, for probing an adapter later), `--max-steps-per-run`, `--max-runs`,
`--out` (JSON). Print a compact table and write JSON with per-bucket counts and rates, the model and
lora name probed, the campaign root, and the number of trajectories and steps used. `timeout` every
model call. BLAS stays at 1 thread.

Every probe call must be recorded, including failures — a step that errored is a data point, not a
step to skip. A probe that silently drops failures reports the model as better than it is; that class
of defect has already cost this project 15 times.

## Part 3 — tests (`tests/unit/test_replay_prefix.py`)

Offline, `MockEnv` only, **no AppWorld, no vLLM, no network**. Cover: `replay_prefix(k)` steps exactly
k executed actions and leaves the world open; it ignores non-executing action kinds when counting;
a file with two `run_start` events replays only the second attempt; `k` larger than the trajectory
raises or clamps (pick one, document it); `replay()`'s own behaviour is unchanged.
For `state_probe.py`, test the api-identifier extraction and the metric arithmetic against small
fixtures with a stubbed executor — do not test against a live server.

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pytest`, `pip`, `tar`, `rsync`, `qsub`, or any
  multi-minute command, and do not start a vLLM server.** Claude runs everything in PBS jobs.
- Do not modify anything under `campaign/results/` or `/scratch`.
- Ignore `.claude/worktrees/` and `.git/`.
- Write `campaign/workers/STATUS_UD1.md` as you go (done / next / how to resume).

## Return contract (under 30 lines)

- `replay_prefix`'s signature and what it does about the two-`run_start` case — and whether `replay()`
  already handled it `[OBSERVED src/sidekick/replay.py:<line>]`.
- The api-identifier regex, quoted.
- The exact JSON keys `state_probe.py` writes.
- How you determined the `value_forwarding` subset, in two sentences.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
