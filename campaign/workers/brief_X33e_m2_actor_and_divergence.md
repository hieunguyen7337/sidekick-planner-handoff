# Brief X33e — M2 scans the wrong actor, and the divergence guard fires on a documented behaviour

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Make your first file edit within your
first three actions. Two files only: `scripts/analysis/j13_mechanism.py` and
`tests/unit/test_j13_mechanism.py`. X33d just edited both; build on the files as they are now.

Your X33d fix **worked** — the zero-shot run now reports real handoff populations (111 / 82 / 54 at
m6 / m9 / m11) and the M3 decomposition is valid. Two defects remain, both found by running it.

---

## Defect 1 — M2 finds zero errors because it filters observations by the wrong actor

`measure_m2_compounding_error` scans for the executor's first error with
`elif e.event_type == "observation" and e.actor == "executor":` [OBSERVED scripts/analysis/j13_mechanism.py:619].

**Observations are never emitted by the executor.** Verified across every episode of
`hj13_prefix_zs_m9_20260923/prefix_handoff/1`: the only pairs present are `action|executor` and
`observation|environment` (plus `run_start|system`, `run_end|system`, `report|system`,
`evaluate|environment`). So the branch never runs, `first_err_rel` stays `-1` for every episode, and the
report prints `error_rate_on_handoff = 0.00%` with `n/a` for both first-error shares — across all three
arms, while 17–32 % of those episodes actually fail. Another believable zero.

**The real error signal, verified on the same arm:** 167 observations whose `payload.text` starts with
`Execution failed. Traceback:` and whose `error_type` is `null`; 52 start with `Execution successful.`.
So the text prefix is load-bearing and `error_type` alone is not sufficient — keep both tests, change only
the actor.

**Edit:** match observations with `e.actor == "environment"`. Do not match on actor `executor`. Keep the
existing `exec_action_count` logic (it correctly counts `action|executor`) so `first_error_rel_step`
remains 1-based relative to the executor's first step.

⚠ Be careful about ordering: the counter must be incremented on the action **before** the observation that
answers it is inspected, so an error in the reply to the executor's first action yields
`first_error_rel_step == 1`. Confirm the current loop already does this and say so in STATUS.

---

## Defect 2 — the divergence guard is fatal on a behaviour we documented on purpose

Your guard aborted the tailored receiver with:

```
Fatal: arm 'm7' divergence count 8/114 (7.02%) exceeds 5% threshold
```

That arm is the **comparison** arm `hj12_prefix_m7_20260922` — a run from *before* the F0(a) loop repair.
In those runs, when a replayed prefix ended in the planner's `COMPLETE`, the live loop still let the
executor act. So `handoff_occurred == False` (the prefix consumed the episode) while executor
`n_calls > 0` (it acted anyway). That divergence is the **documented pre-repair behaviour**, recorded in
`docs/claims_ledger.md` and `campaign/RUNS.md` §14 — not a data defect. A blanket 5 % threshold therefore
blocks a valid analysis.

**Replace the blanket threshold with a directional check, which is both stricter and correct:**

- **Fatal in either arm class:** any episode with `handoff_occurred is True` but executor `n_calls == 0`.
  That direction cannot be explained by the post-`COMPLETE` behaviour and means the flag or the loading is
  wrong. Name the arm, the episode and the count.
- **Fatal, unchanged:** an episode missing a `report` event; and zero `handoff_occurred is True` episodes
  in an arm while any episode has executor `n_calls > 0` (the MECH-09 signature).
- **Not fatal, but recorded:** episodes with `handoff_occurred is False` and `n_calls > 0`. Count them per
  arm into a new report field `post_complete_executor_actions` beside the existing `divergence_count`, and
  add one line to the markdown naming it as the pre-F0 behaviour. Keep `divergence_count` as it is so the
  existing tests and reports still read.

Keep the 5 % threshold **only** for the fatal direction (handoff True with zero calls), where even one
episode is suspicious — so in practice make that direction fatal at any count above zero.

---

## Tests, `tests/unit/test_j13_mechanism.py`

Update the existing fixtures so observations carry `actor="environment"` (they currently cannot exercise
the real path), then add:

1. `test_m2_counts_errors_from_environment_observations` — a scripted handoff episode with an executor
   action followed by an `observation|environment` whose text starts `Execution failed. Traceback:` yields
   `error_rate_on_handoff == 1.0` and `first_error_rel_step == 1`.
2. `test_m2_ignores_successful_observations` — text `Execution successful.` yields no error.
3. `test_m2_first_error_step_is_one_based_on_executor_actions` — error in the reply to the third executor
   action yields `first_error_rel_step == 3`.
4. `test_handoff_true_with_zero_executor_calls_is_fatal` — `SystemExit`, no report written.
5. `test_post_complete_actions_are_recorded_not_fatal` — an arm where 10 % of episodes have
   `handoff_occurred False` and `n_calls > 0` completes and reports
   `post_complete_executor_actions == <count>`.
6. Keep `test_empty_handoff_population_is_fatal` and `test_handoff_flag_is_read_from_report_event` passing.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Never background anything.
  You may `head -c 2000` ONE real `events.jsonl` under
  `/scratch/n12194778/sidekick/results/hj13_prefix_zs_m9_20260923/prefix_handoff/1/` to confirm the shapes
  above. Never read or list `test_normal` / `test_challenge`. Do not edit `j8_frontier.py`,
  `j10_report.py` or `src/sidekick/**`. Never write under `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X33e.md`, under 350 words: the before/after hunk for the actor filter; your
confirmation (quoting the loop) that the action counter increments before the observation is inspected;
the before/after hunk for the directional guard; the new report field name and where it is written; the
test names. `[OBSERVED path:line]` / `[INFERRED]` on every claim. **Do not claim any test passes.**
