# Brief X30 — align the training cut with the serving cut in the suffix-handoff dataset

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Code edit plus tests. **Do NOT `qsub`, do NOT submit a training job, do NOT rebuild the dataset.**
I submit every job myself. Two GPU jobs are running; they do not import the file you are editing.

## The defect, measured

`src/sidekick/training/handoff_sft.py` builds the suffix-handoff SFT rows. Its cut is defined two
different ways in the same function, and they disagree on 62 of 629 rows.

- The **drop gate** uses executed actions: `if n_actions <= m` where
  `n_actions = _n_executed_actions(events)` [OBSERVED `src/sidekick/training/handoff_sft.py:87-90`].
  `_n_executed_actions` counts an action only when its kind is `CODE` or `COMPLETE` **and** an
  `observation` event follows it [OBSERVED `src/sidekick/prefix_source.py:40-51`].
- The **cut itself** uses assistant messages: `_suffix_target_indices(messages, m)` walks the rendered
  message list and cuts after the `m`-th `role == "assistant"` message
  [OBSERVED `src/sidekick/training/handoff_sft.py:52-62`].

Those are not the same quantity, because `_history_from_events` flushes an assistant turn for **every**
action event regardless of kind, including an action flushed by a following action rather than by an
observation [OBSERVED `src/sidekick/training/sft_data.py:196-226`].

Measured on the built artifact
`/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_handoff_granite8b_20260923.jsonl`:

- `n_action_targets == n_assistant_messages - cut_m` for **629 / 629** rows — the cut is by assistant
  message, confirmed.
- `n_action_targets == n_source_actions - cut_m` for only **567 / 629** rows. **62 rows across 24
  episodes** disagree.
- Excess (`assistant messages` − `executed actions`) per row: 567 rows at 0, 29 at 1, 3 at 2, and
  **30 rows at 10–31**.
- The severe ones are all limit-terminated episodes with exactly 40 assistant turns: e.g. `302c169_2`
  seed 1 has **40 assistant turns but only 11 executed actions**; `6ea6792_1` seed 3 has 40 and **9**.

Consequence: for those rows a cut at `m = 6` does not correspond to six executed actions — it can
correspond to one or two — so the adapter is trained on a handoff point that serving never produces.

## What serving does — match this

`prefix_handoff` replays **m executed actions**. The training cut must therefore land after the
assistant message produced by the **m-th executed action**, not after the m-th assistant message.
Everything before that point stays in context with label `-100`, exactly as now; only the cut index
moves. Non-executed assistant turns inside the prefix remain masked context — they are part of what a
replayed prefix shows the executor, so do not filter them out.

## Your job

1. Read `src/sidekick/training/handoff_sft.py`, `src/sidekick/prefix_source.py:40-51` and
   `src/sidekick/training/sft_data.py:186-235` before changing anything.
2. Add a helper that walks events with **the same pending/flush rules `_history_from_events` uses** and
   returns the 1-based ordinal, among flushed assistant turns, of the `m`-th executed `CODE`/`COMPLETE`
   action. Reuse the existing predicates; do not write a third definition of "executed".
3. Use that ordinal as the argument to `_suffix_target_indices`. Keep the drop gate on executed
   actions — it is already correct.
4. Record both numbers in each row's `meta` so the disagreement can never again be invisible:
   `n_prefix_assistant_turns` (the ordinal you computed) beside the existing `cut_m` and
   `n_source_actions`. Add `n_prefix_assistant_turns` totals to the manifest summary too.
5. **Verify the property in the manifest**: add to `build_handoff_dataset`'s summary a count
   `n_rows_cut_offset` = rows where the ordinal differs from `cut_m`. It should be non-zero after this
   fix (about 62 rows, 24 episodes) — that is the evidence the fix is live, so do not suppress it.

## Tests

In `tests/unit/test_handoff_sft.py`, add a test built on a scripted event list that contains **a
non-executed action inside the prefix region** — an action event immediately followed by another action
event, so `_history_from_events` flushes an assistant turn for it while `_n_executed_actions` does not
count it. Assert:

- the supervised index list is the one implied by the **executed-action** cut, not the assistant-message
  cut, and that the two differ for this fixture (assert both, so the test would fail if the fix were
  reverted);
- every prefix assistant turn, including the non-executed one, has label `-100`, and every suffix
  assistant turn's labels equal its `input_ids` — assert the **exact position lists**, as the existing
  `test_cut_m2_masks_exact_prefix_token_positions` does;
- an episode whose executed-action count equals `m` is still dropped `too_short`.

Keep the existing tests passing unchanged. Do not weaken an assertion to make one pass; if an existing
test encodes the old (wrong) cut, say so in STATUS and quote it rather than editing it silently.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run the tests through `hpc`, prefixing every job with
  `env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-X30-spool`. BLAS pinned to one thread.
- Run only `tests/unit/test_handoff_sft.py` plus the full suite **with
  `--ignore=tests/unit/test_j8_frontier.py`** — another unit owns that file right now and it is
  expected to fail.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Never write under it. Dev only; never read
  `test_normal` or `test_challenge`.
- Do not edit `configs/`, `scripts/pbs/`, `scripts/analysis/j8_frontier.py`,
  `tests/unit/test_j8_frontier.py`, or any `docs/prereg_*.md`.
- Do not rebuild the JSONL and do not delete the existing one — it is the evidence for the measurement
  above. I rebuild it after reviewing your diff.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X30.md`, under 400 words: the helper you added and where; the diff summary;
the pasted `tests/unit/test_handoff_sft.py` result; the pasted full-suite line; and a one-line statement
of what the new test would report if the fix were reverted.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
