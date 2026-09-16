# Unit U-D1b — the probe's primary metric has a diluted denominator

**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
**Files in scope:** `scripts/setup/state_probe.py`, `tests/unit/test_replay_prefix.py`. Nothing else.

## The defect

`record()` does `bucket["n"] += 1` for **every** probed step, and `finalize()` divides each metric by
that `n`. But `agreement` is only ever computed when **both** the model's action and the gold action
are `CODE`:

```python
if action.kind == "CODE" and gold_action is not None and gold_action.kind == "CODE":
```

So every step whose **gold** action is `COMPLETE`, `REPORT` or `ASK_PLANNER` enters the denominator
while being incapable of ever entering the numerator. Each solved trajectory ends in a `COMPLETE`,
so roughly one step in twelve is structurally unscoreable, and `agreement_rate` is understated by
about 8% of its own value.

This is not cosmetic. The probe's thresholds decide whether the project trains granite-4.2-8b or
replaces it: **≥ 40%** means train it, **< 15%** means switch. A metric diluted by unscoreable steps
reports a model as worse than it is, and the number looks perfectly plausible either way — which is
the exact failure mode this project has now hit sixteen times.

## The fix

Separate "could this step be scored" from "was it scored correctly".

- Add `n_scorable` to each bucket: steps where the **gold** action is `CODE` (the ones on which
  `agreement` is defined). Keep `n` as the count of all probed steps.
- Report `agreement_rate = agreement / n_scorable`, and add `agreement_rate_all_steps` computed over
  `n` so nothing is hidden — both go in the JSON and the printed table.
- Add `n_gold_noncode` and a breakdown of those gold kinds, so a reader can see exactly what was
  excluded and check it is the ~1-in-12 trailing `COMPLETE` and not something larger.
- Decide and document the same question for `state_equivalent` and `hash_match`: `state_equivalent`
  is computed whenever `gold_action` and `gold_obs` exist, so its natural denominator is different
  again. Give each metric a denominator that matches the condition under which it is computed, name
  each one in the JSON, and put a comment above `record()` stating the rule: **a metric is divided by
  the number of steps on which it was defined, never by the number of steps attempted.**
- An `error_type` step (parse error, call error, exec error) must still count as a **failure** on
  every metric whose denominator it belongs to — it is a real inability, not a missing data point.
  Verify the current code does that and say so; do not silently exclude errors.

## Tests

Extend `tests/unit/test_replay_prefix.py`:

- a trajectory ending in a gold `COMPLETE` yields `n_scorable == n - 1`, and an `agreement_rate`
  strictly greater than `agreement_rate_all_steps` when there is at least one agreement;
- a step that errors counts in the denominator and not the numerator;
- `n_gold_noncode` matches the number of non-CODE gold actions in the fixture.

Also fix the stale comment in `campaign/workers/STATUS_UD1.md` that records the campaign layout as
`campaign_root/<system>/<task_id>/<run_id>/`. It is `campaign_root/<system>/<seed>/<task_id>/` —
verified at `/scratch/n12194778/sidekick/results/hj1b_planner_20260915/planner_alone/1/0d8a4ee_1/`.
The glob in `find_solved_runs` happens to be the right depth, so the code works; the note is wrong
and would mislead the next person.

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pytest`, `pip`, `qsub`, or any multi-minute
  command.** Claude runs the suite in a PBS job.
- `tests/unit/test_replay_prefix.py::test_probe_step_agreement_and_state_equivalent` currently FAILS
  (`assert rec["agreement"] is True` got False). Diagnose it as part of this unit and fix whichever
  side is wrong — if the test's expectation is wrong say so explicitly rather than weakening the
  assertion to make it pass.
- Do not change `replay()`'s behaviour or signature.

## Return contract (under 20 lines)

- The final `record()`/`finalize()` denominators, quoted.
- The full set of JSON keys each bucket now carries.
- The cause of the currently-failing test, and which side you changed.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
