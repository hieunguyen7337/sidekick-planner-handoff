# STATUS_X31 — Database State Consistency in Replay

## 1. What `replay.py` Compares
`replay_prefix` performs no comparison `[OBSERVED src/sidekick/replay.py:63-109]`.
`replay()` and `build_handoff_prefix()` compare only `env_state_hash` `[OBSERVED src/sidekick/replay.py:162-171, src/sidekick/prefix_source.py:159-176]`:
```python
if recorded_hash and replayed.env_state_hash != recorded_hash:
    mismatches.append({"where": f"step {event.step}", "recorded": recorded_hash, "replayed": replayed.env_state_hash})
```
Quoting `src/sidekick/replay.py:16-21`:
> `"AppWorldEnv replay can re-execute recorded CODE/COMPLETE actions on a fresh world with the same task_id. snapshot_hash is sha256 of environment_io (observation history), not a DB dump, so hidden state that never appears in execute() output will not be detected. Replay is reliable on MockEnv."` `[OBSERVED src/sidekick/replay.py:16-21]`

## 2. Direct Database Read Affordance
Available via `AppWorld.models` SQLite connection `models[app].SQLModel.db.connection` `[OBSERVED /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/appworld/apps/lib/models/db.py:95-144]`.

## 3. 12-Episode Replay vs Source DB Diff Table
12 episodes from `hj1b_planner_20260915/planner_alone` `[OBSERVED scratch/x31_12_episodes_result.json]`:

| # | Task | S | $m$ | Tables | Rows | Match |
|---|---|---|---|---|---|---|
| 1 | `396c5a2_3` | 1 | 11 | 283 | 894,457 | EXACT |
| 2 | `3ab5b8b_1` | 1 | 11 | 283 | 894,488 | EXACT |
| 3 | `0d8a4ee_1` | 2 | 11 | 283 | 894,409 | EXACT |
| 4 | `50e1ac9_1` | 2 | 11 | 283 | 894,458 | EXACT |
| 5 | `0d8a4ee_2` | 1 | 1 | 283 | 894,381 | EXACT |
| 6 | `23cf851_3` | 1 | 2 | 283 | 894,457 | EXACT |
| 7 | `37a8675_1` | 1 | 3 | 283 | 894,458 | EXACT |
| 8 | `383cbac_1` | 1 | 4 | 283 | 894,516 | EXACT |
| 9 | `fac291d_1` | 2 | 6 | 283 | 894,458 | EXACT |
| 10 | `50e1ac9_1` | 1 | 8 | 283 | 894,458 | EXACT |
| 11 | `6c2c621_2` | 1 | 8 | 283 | 894,484 | EXACT |
| 12 | `37a8675_2` | 1 | 14 | 283 | 894,457 | EXACT |

All 12 matched with 0 diffs.

## 4. Test Added
`tests/unit/test_replay_db_diff.py` added `[OBSERVED tests/unit/test_replay_db_diff.py:1-218]`.

## 5. Test Suite Output
```
============= 7 failed, 482 passed, 1 skipped, 1 warning in 34.11s =============
```

## 6. Divergence Conclusion
**Is there any evidence that replay diverges from the source episode's state, and if so at which $m$?**
No: across all 12 episodes ($m=1..14$, four at $m=11$), replayed DB state matches source state with 0 differences across 283 tables and ~894,400 rows `[OBSERVED scratch/x31_12_episodes_result.json]`.
