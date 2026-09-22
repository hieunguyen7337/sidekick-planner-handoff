# Status X30: Align Training Cut with Serving Cut in Suffix-Handoff Dataset

## Helper Added and Location
Added `_prefix_assistant_turns_for_executed_cut(events: list[Any], m: int) -> int | None` to [src/sidekick/training/handoff_sft.py:44-118](file:///mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/src/sidekick/training/handoff_sft.py#L44-L118).
It walks events matching `_history_from_events` pending/flush semantics [OBSERVED src/sidekick/training/sft_data.py:196-258], counting flushed assistant turns and returning the 1-based ordinal of the assistant turn when the `m`-th executed `CODE`/`COMPLETE` action is flushed by an observation [OBSERVED src/sidekick/training/handoff_sft.py:44-118].

## Diff Summary
- `src/sidekick/training/handoff_sft.py`:
  - Imported `_action_from_payload` from `sidekick.training.sft_data` [OBSERVED src/sidekick/training/handoff_sft.py:24].
  - Implemented `_prefix_assistant_turns_for_executed_cut` [OBSERVED src/sidekick/training/handoff_sft.py:44-118].
  - Updated `row_from_events` to compute `n_prefix_assistant_turns` via the helper and pass it to `_suffix_target_indices(messages, n_prefix_asst)` [OBSERVED src/sidekick/training/handoff_sft.py:166-178].
  - Populated `n_prefix_assistant_turns` into `extras` and `row["meta"]` [OBSERVED src/sidekick/training/handoff_sft.py:170,185].
  - In `build_handoff_dataset`, added `n_prefix_assistant_turns` and `n_rows_cut_offset` to manifest summary [OBSERVED src/sidekick/training/handoff_sft.py:298-323].
- `tests/unit/test_handoff_sft.py`: Adding test for non-executed action in prefix region and verifying position masking and too_short drops.

## Test Results
Running tests via HPC.
