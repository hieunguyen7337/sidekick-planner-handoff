# STATUS A14 — silent trainer drop (instrumentation)

**Unit:** A14 (U-TRAIN)
**State:** done
**Started:** 2026-09-19

## Files owned / written
- `scripts/train/sft_lora.py`
- `tests/unit/test_sft_lora_drop.py`
- `campaign/workers/STATUS_A_14.md`
- `campaign/workers/A14_SILENT_DROP.md`
- `campaign/workers/a14_retrospective.json`

## Milestone
- [x] STATUS written
- [x] Read trainer, tokenize path, existing tests, row identifiers (`meta.run_id`)
- [x] Count/record dropped + truncated-but-kept in manifest; warn on drop
- [x] Unit tests written (`tests/unit/test_sft_lora_drop.py`)
- [x] PBS suite: `406 passed, 1 skipped, 1 warning in 52.38s` (job 25459839.aqua)
- [x] PBS retrospective tokenize of 497-row jsonl (tokenizer only): **18 dropped, matches 479**
- [x] Report `campaign/workers/A14_SILENT_DROP.md`

## Notes
No retrain, no GPU, no planner, no writes under `/scratch/.../results/` or `/scratch/.../adapters/`.
`n_sequences` stays = rows actually trained on.
Drop reasons: 18 truncated_past_labels, 0 fully_masked_before_truncation; 17 truncated-but-kept.
30 min job 25454825.aqua was walltime-killed; 2h job 25456324.aqua finished in 1h18m.
