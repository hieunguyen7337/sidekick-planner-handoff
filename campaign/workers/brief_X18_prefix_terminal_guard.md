# Brief X18 — the executor keeps acting after the replayed prefix already finished

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Code + tests only. **Do not `qsub`, do not run any evaluation, do not touch a GPU.** I submit the
re-runs myself after reviewing your diff.

## The defect

`run_episode` rebuilds the last observation from the replayed prefix:

```
loop.py:582   last_obs = last_observation_from_events(list(prefix.events))
```

and `last_observation_from_events` carries `done` through from the recorded payload
[OBSERVED `src/sidekick/systems/loop.py:144-157`, `done=bool(payload.get("done", False))`].

The live loop then starts **unconditionally**:

```
loop.py:690   for step in range(start_step, limits.max_steps + 1):
```

There is no check of `last_obs.done` between `:582` and `:690`. The only termination check is
**after** an action has already been taken:

```
loop.py:1053  if action.kind == "COMPLETE" or last_obs.done:
                  break
```

So when the source episode ended within the prefix — the planner emitted `COMPLETE` and the
environment returned `done=True` — the executor is still asked for an action and still executes it
against an already-finished episode. Measured consequence: in `hj12_prefix_m11_20260922`, 60 of 114
episodes replay the whole source episode, and the executor took **113 actions** across them; at m9,
**38 actions** across 32 such episodes.

This makes those arms a *second attempt with extra budget*, not a replay, and it is the single
largest threat to the campaign's headline number.

## What to build

1. **A terminal guard.** If the replayed prefix's last observation has `done` set (or the last
   recorded action event in the prefix is a `COMPLETE`), the live loop must not run. The episode ends
   immediately with the replayed outcome.
2. **Make the behaviour explicit and recorded, not implicit.** Add a policy field
   `post_prefix_terminal: Literal["stop", "continue"] = "stop"`. `"stop"` is the new default and is
   the corrected science; `"continue"` reproduces today's behaviour so the old runs remain
   explicable. Whichever is in force must be written into the `run_start` payload alongside the
   existing `prefix` block [OBSERVED `loop.py:621-626`], and the count of post-terminal executor
   actions must appear in `run_end` as `n_post_terminal_actions` (0 under `"stop"`).
3. **Do not change non-prefix behaviour at all.** When `prefix is None`, `last_obs` comes from
   `env.reset` and the guard must be a no-op. A fresh episode whose reset somehow reported `done`
   is not a case you should invent handling for — assert the existing path is untouched.

## Constraints

- Touch `src/sidekick/systems/loop.py` and, if the policy field needs declaring, the policy
  dataclass it lives beside. **Do not** edit `src/sidekick/replay.py`, any config, anything under
  `scripts/pbs/`, or any file under `campaign/results/`.
- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Run the
  test suite through `hpc`. `timeout` on every command.
- Read-only on `/scratch/n12194778/sidekick/results/`. Dev only; never read `test_normal` or
  `test_challenge`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- The suite is at **506 passed, 1 skipped** and must not fall.
- **Do not commit.** I review and commit.

## Tests (add to `tests/unit/`)

Use a scripted environment, as the existing prefix tests do.

1. A prefix whose final observation has `done=True`: under the default the executor is asked for
   **zero** actions, the episode's outcome equals the replayed outcome, and
   `n_post_terminal_actions == 0`.
2. The same prefix under `post_prefix_terminal="continue"`: behaviour is byte-identical to today's,
   and `n_post_terminal_actions` is the number of extra actions taken.
3. A prefix that ends mid-episode (`done=False`): the executor runs normally and nothing about the
   existing path changes.
4. `prefix is None`: unchanged; the guard never fires.
5. `run_start` records which policy was in force.

## Return contract

`campaign/workers/STATUS_X18.md`, under 500 words: the exact lines you changed, the policy field's
name and default, how `run_start`/`run_end` record it, the five test names, and the pasted suite
line. Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.

State plainly in STATUS whether the guard changes any code path when `prefix is None`.
