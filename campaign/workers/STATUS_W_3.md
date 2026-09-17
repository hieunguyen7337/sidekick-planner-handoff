# STATUS_W_3 — matched dataset pair + trainer mask fix

Session 3 complete. No commits. No training. No YAML/PBS templates.

## Deliverables
- [x] A. Per-episode multi-target masks (`meta.supervised_message_indices`; singular + `supervise_last_assistant_only` when exactly one target). `remask_to_message_index` via `remask_to_message_indices`. Identity-first remask map (`_map_target_index_after_budget_fit`).
- [x] B. `build_sft_b_plus` copies frozen teacher jsonl bytes unchanged; correction half is one sequence per episode. Seeds discovered from the campaign tree (1 and 2 present).
- [x] C. `build_ask_dataset` against synthetic `branches.jsonl` (addendum: `label_status=="complete"`; needed ASK; needless/ambiguous/incomplete → no ASK). Labels file does not exist yet.
- [x] D. Cross-file assertion tests + manifest fields.
- [x] Trainer `tokenize_sft_row` honours either spelling; no-spec rows still call `tokenize_and_mask`.
- [x] PBS pytest 25405209: **286 passed, 1 skipped in 12.69s**
- [x] PBS build 25405225: `data/interim/sft_b_plus.jsonl` — 408 sequences (230 teacher + 178 correction), 495 action targets, 0 ASK, 2 drops (`no_intervention`), p50=18838 p90=29970 max=66700.

## Tests changed (intentional, deliverable A)
- `test_one_intervention_one_post_action_target`: still 1 sequence; also asserts `supervised_message_indices` == `[supervised_message_index]`.
- `test_no_emitted_example_contains_intervention_mark`: 2 interventions → **1 sequence** (not 2) with 2 action targets.
- `test_label_mask_covers_only_target_assistant_turn`: uses the list spelling and `remask_to_message_indices`.

## Objection
Salvage rank-among-equals mapped a dropped first duplicate onto the surviving second. Mapper now pairs leftover selected slots with leftover originals after identity; a dropped original stays unmapped (`sft_data.py` `_map_target_index_after_budget_fit`).
