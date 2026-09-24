# Brief: diagnose the deterministic replay_divergence (DIVDIAG, 2026-09-25)

Worktree (absolute, the only cwd): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
IGNORE `.claude/worktrees/` (other worktrees) and `.git/`.

## Goal

Establish, **by observation**, why two dev prefix-replay keys fail the replay hash check deterministically,
and estimate how exposed luna-sourced and Qwen3.8-27B-sourced replays are. The answer feeds a pre-data
amendment. You write one script, one unit test, one result file. You do not edit anything else.

## What is already established (by Claude; re-verify, do not trust)

- `src/sidekick/prefix_source.py:157-175`: after `replay_prefix` (`src/sidekick/replay.py:63-108`) replays the
  first m executed actions of a source episode, `broken_reason = "replay_divergence"` when the last replayed
  observation's recorded `env_state_hash` differs from `world.snapshot_hash()`.
- `src/sidekick/environments/appworld_env.py:147-158`: `snapshot_hash` = sha256 of JSON of
  `{environment_io, num_interactions, task_completed}` — i.e. of the cumulative execute INPUT/OUTPUT TEXT,
  not of the database. So any printed text that varies between Python processes breaks the hash even when
  the world state is identical.
- No file under `scripts/pbs/` or `src/` sets `PYTHONHASHSEED` (grep count 0).
- Failing keys: source `/scratch/n12194778/sidekick/results/lp2_planner_alone_cap81_qwen38_27b_20260923`,
  system `planner_alone`, seed `1`, tasks `68ee2c9_2` and `df61dc5_2`, m = 11 (both receivers; the receiver
  is irrelevant because the check runs before the executor acts).
- Claude's hypothesis (UNVERIFIED): step-11 output of `68ee2c9_2` prints `inspect.signature(...)` containing
  `<... LogInOutManager object at 0x14804efed640>` (a memory address); step-11 output of `df61dc5_2` prints a
  Python `set` of e-mail strings, whose order depends on per-process string-hash randomisation. Either
  varies per process, so the replay's `environment_io` differs from the recorded one.

## Deliverables

1. `scripts/analysis/replay_divergence_diagnose.py` (new). Two subcommands:
   - `replay --source <campaign dir> --system <sys> --seed <n> --task <id> --m <int>`: reset an
     `AppWorldEnv` exactly as `replay_prefix` does (reuse `sidekick.replay._events_of_last_attempt` and
     `_action_from_payload`; mirror the loop at replay.py:97-106), but after EACH executed action compare
     (a) the live observation text against the recorded observation event's `payload.text`, and
     (b) the live `env_state_hash` against the recorded observation's `env_state_hash`.
     Emit JSON: per step `{step, text_equal, hash_equal}`, the first step where text differs, and for that
     step the differing region (both sides, ≤ 300 chars each, around the first differing character),
     plus `classify_difference(recorded, live)` (below). Close the world at the end.
   - `scan --source <campaign dir> --system <sys> --max-step <int>`: NO replay, pure text. For every
     seed/task in the source, over observation events with `step <= max-step` of the LAST attempt, count
     episodes whose output text matches `object at 0x[0-9a-fA-F]+` (address) and, separately, episodes
     whose output contains a printed set literal of ≥ 2 quoted strings (a regex such as
     `\{'[^'{}]*'(, '[^'{}]*')+\}` — note dicts contain `': '` and must not match; document the regex's
     known misses). Emit counts per source and the key lists.
   - A pure function `classify_difference(recorded: str, live: str) -> str` returning one of
     `"address"` (the two strings are equal after replacing every `0x[0-9a-fA-F]+` by `0xADDR`),
     `"reordering"` (not address; equal as multisets of whitespace/comma-split tokens), or `"other"`.
   - **Held-out guard**: refuse (exit 2, message) any `--source` whose path contains `/j10_`, `/j11_`,
     `/j12_`, `test_normal` or `test_challenge`. Only dev sources are allowed.
2. `tests/unit/test_replay_divergence_diagnose.py`: `classify_difference` on hand-built strings (address,
   reordered set, genuinely different text, identical text) and the held-out guard (a `/j11_` path exits 2).
   No AppWorld needed in the test.
3. `campaign/results/replay_divergence_diagnosis_dev_20260925.json`: the combined output of
   - `replay` for the two failing keys at m = 11, **each run twice in two separate Python processes**
     (so you can say whether live output differs between two fresh processes, not only vs the source);
   - `replay` for two CONTROL keys of the same source and seed that did NOT diverge at m = 11 (pick keys with
     ≥ 11 executed actions whose `lp2_prefix_zs_m11_v2_20260923/prefix_handoff/1/<key>/result.json` has no
     crash);
   - `scan --max-step 11` over these dev sources, `--system` as on disk:
     `lp2_planner_alone_cap81_qwen38_27b_20260923` (planner_alone),
     `hj13_planner_alone_cap81_20260923`, `hj13_planner_alone_cap81_seed3_20260924`,
     `hj1b_planner_20260915` (list its top-level dir to find the system name), all under
     `/scratch/n12194778/sidekick/results/`.

## How to run (HPC rules — mandatory)

- The login node `aquarius01` is for steering. **Never run python or pytest there.** Every python /
  pytest invocation goes through the queue:
  `timeout 1800 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && export PYTHONPATH=$PWD/src:$PWD APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 && /scratch/n12194778/sidekick/env/bin/python scripts/analysis/replay_divergence_diagnose.py ...'`
  (~2 min queue wait each; batch several runs into one `hpc bash -c` where you can).
  Tests: same wrapper with `/scratch/n12194778/sidekick/env/bin/python -m pytest -q tests/unit/test_replay_divergence_diagnose.py`.
- `timeout` on every shell command. No pip, tar, rsync, recursive find over `/scratch`.
- Read big files narrowly (`jq`, `grep -n`, `sed -n`), never whole events.jsonl files into context.
- Do NOT read, list or open anything under a `j10_*`, `j11_*`, `j12_*` or `bfcl_*` results directory, nor any
  test_normal / test_challenge data. Do not modify anything under `/scratch/.../results/`.
- Do not edit any existing file. Other work is in flight in this worktree (`j10_report.py`,
  `j12_cost_axes.py`, cost reports): do not touch them. Do not commit; do not run git commands that write.

## Return contract (≤ 40 lines)

Tag every claim `[OBSERVED path:line]` (or `[OBSERVED <result json key>]`) or `[INFERRED]`.
1. First differing step and `classify_difference` for each failing key, for both processes; whether the two
   fresh processes differ from EACH OTHER.
2. Controls: did they replay hash-equal at every step ≤ 11?
3. Scan counts per source (address episodes, set-print episodes, episodes scanned) and the regex misses.
4. Test result line (N passed) and the PBS job ids you used.
5. Anything surprising, especially anything that contradicts the hypothesis above.
