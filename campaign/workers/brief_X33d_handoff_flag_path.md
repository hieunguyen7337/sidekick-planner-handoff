# Brief X33d — the mechanism script reads `handoff_occurred` from a place it never is

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Make your first file edit within
your first three actions. Two files only: `scripts/analysis/j13_mechanism.py` and
`tests/unit/test_j13_mechanism.py`. X33c just edited the same script's markdown renderer; build on
the file as it is now.

## The defect (verified against real data)

`scripts/analysis/j13_mechanism.py:392` reads `res.get("handoff_occurred")` from **`result.json`**.
That file has no such key — its top-level keys are `error_type, goal_pass_rate, n_asks,
n_interventions, n_planner_calls, run_id, seed, sgc, steps, success, system, task_id, tgc, totals`
(verified on `hj12_prefix_m9_20260923/prefix_handoff/1/0d8a4ee_1/result.json`). So the flag is never
True, every arm reports `handoff_episodes: 0, silenced_episodes: 114`, M2 is entirely `null`, every M3
controlled curve has `n_keys: 0`, and the decompositions attribute 100% of the rise to "silenced" by
construction. The script's own divergence diagnostic recorded 111 / 83 / 58 disagreements at
m = 6 / 9 / 11 — those are the real handoff counts — and the script wrote a report anyway. Both
19:13 reports are invalid (claims ledger MECH-02).

**Where the flag actually is:** the episode's `report` event in `events.jsonl`, beside `result.json`:

```
{"event_type":"report","actor":"system","payload":{"effective_m":9,"n_source_actions":10,
 "handoff_occurred":true,"hash_ok":true,"replayed_planner_tokens":318026,"source_campaign":"..."}, ...}
```

`scripts/analysis/j8_frontier.py` reads it from there and merges it into each row before
`handoff_flag_keys` (`:456-470`) tests `row.get("handoff_occurred") is want`. Find the exact place in
`j8_frontier.py` (or the `j10_report.py` it imports) where the `report` payload is merged into the
row, cite it, and **reuse that function** if it is importable; otherwise mirror it exactly: locate
`events.jsonl` next to each `result.json`, take the last `report` event of the last attempt, and read
`payload.handoff_occurred`, `payload.effective_m`, `payload.n_source_actions`.

## Edits

1. Replace the `result.json` lookup with the events-based one in **both** places (`:392` in M2 and
   the M3 counterpart near `:495`), through one shared helper `load_handoff_flags(arm_root) ->
   dict[(task_id, seed), {handoff_occurred, effective_m, n_source_actions}]`.
2. **Make an empty population fatal.** After loading each arm: if the arm has zero episodes with
   `handoff_occurred is True` while any episode has `executor n_calls > 0`, or if the divergence count
   between the flag and `n_calls > 0` exceeds 5% of episodes, raise `SystemExit` with a message naming
   the arm and the counts. Do not write a report. A missing `report` event in any episode is also
   fatal (name the episode). The `n_calls == 0` proxy stays as the diagnostic only.
3. Keep everything X33b and X33c added (CLI, discovery, `n/a` rendering).
4. Tests, `tests/unit/test_j13_mechanism.py`:
   - `test_handoff_flag_is_read_from_report_event`: a fixture episode whose `result.json` has **no**
     `handoff_occurred` key and whose `events.jsonl` carries a `report` event with
     `handoff_occurred: true` is counted as a handoff episode.
   - `test_empty_handoff_population_is_fatal`: a fixture arm where every `result.json` lacks the key
     and no `report` event exists → `SystemExit`, no report written.
   - `test_divergence_above_threshold_is_fatal`: flag False everywhere but `n_calls > 0` in 10% →
     `SystemExit`.
   - Update the existing M2/M3 fixture tests so their fixtures carry the `report` event.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Never background
  anything. You may `head -c 2000` ONE real `events.jsonl` under
  `/scratch/n12194778/sidekick/results/hj12_prefix_m9_20260923/prefix_handoff/1/` to see the shape.
  Never read or list `test_normal`/`test_challenge`. Do not edit `j8_frontier.py`, `j10_report.py`,
  or `src/sidekick/**`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X33d.md`, under 300 words: the j8_frontier/j10_report location you reused or
mirrored (path:line); the helper's before/after hunk; the fatal-check hunk; the test names; the two
`hpc` commands to re-run both receivers with new output names
`campaign/results/hj13_mechanism_{tailored,zeroshot}_20260923b.report.json`. `[OBSERVED path:line]` /
`[INFERRED]` on every claim. **Do not claim any test passes.**
