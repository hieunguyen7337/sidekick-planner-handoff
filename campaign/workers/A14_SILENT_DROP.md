# A14 — trainer silent drop made visible

**Unit:** A14 (U-TRAIN). Instrumentation only. Did not retrain. Did not submit a GPU job.
Did not write under `/scratch/.../results/` or `/scratch/.../adapters/`. Did not commit.

## Retrospective (the number that matters)

**18 of 497 rows in `sft_b_plus_20260918.jsonl` are dropped by the current rule. That equals the 18 implied by `497 - 479`.**

| quantity | value | source |
|---|---|---|
| JSONL lines / rows loaded | 497 | [OBSERVED campaign/workers/a14_retrospective.json `n_lines_wc` / `n_rows_loaded`] |
| Adapter `n_sequences` | 479 | [OBSERVED /scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b/manifest.json:43] |
| Dropped, no supervised tokens | **18** | [OBSERVED campaign/workers/a14_retrospective.json `n_dropped_no_supervised_tokens`] |
| of which truncated past labels | **18** | [OBSERVED same file `n_dropped_truncated_past_labels`] |
| of which fully masked before truncation | **0** | [OBSERVED same file `n_dropped_fully_masked_before_truncation`] |
| Truncated but kept | **17** | [OBSERVED same file `n_truncated_kept`] |
| `n_sequences` under the current rule | **479** | [OBSERVED same file `n_sequences`; 497 − 18] |
| Matches implied 18? | **yes** | [OBSERVED same file `matches_implied_18`: true] |

Tokenizer only: `ibm-granite/granite-4.2-8b`, `MAX_LENGTH=32768`, same `collect_tokenized_sft_rows` path the trainer now uses. No model load. PBS job `25456324.aqua` on `cpu1n040`, wall 01:17:50, tokenize 4655.3 s, mem 600608 kb, exit 0 [OBSERVED /home/n12194778/.hpc-spool/20260919-031446-4002914.out].

A first attempt at the brief's 30-minute slot (`25454825.aqua`) was killed at walltime after loading 497 rows and the tokenizer; no counts. The 2-hour rerun finished.

All 18 dropped `run_id`s are correction (`hj4_correction_train_20260917/fixed_k/...`) episodes [OBSERVED campaign/workers/a14_retrospective.json `dropped_run_ids`]. The 17 truncated-but-kept ids are mostly teacher `planner_alone` rows plus three correction rows [OBSERVED same file `truncated_kept_run_ids`].

This is a caveat on the J8 control adapter, not a reason to redo the two GPU-hours.

## What changed (count and record; training set unchanged)

`scripts/train/sft_lora.py` still skips a row when every label is `-100`. That `continue` is now `collect_tokenized_sft_rows`, which:

1. Counts drops and records `meta.run_id` when present (it is: JSONL rows are `{messages, meta}` with `meta.run_id` [OBSERVED first line of the 20260918 jsonl; also tests/unit/test_sft_data.py:272-276]).
2. Splits drop **reasons** (see below).
3. Counts rows that were **truncated but kept**.
4. Prints a stderr `WARNING:` whenever anything is dropped (and a separate warning if only truncated-kept).
5. Leaves `n_sequences = len(tokenized)` = rows actually trained on [OBSERVED scripts/train/sft_lora.py:378]. New fields are **added**, not reused.

New manifest keys (merged via `**drop_stats`):

- `n_rows_in`
- `n_dropped_no_supervised_tokens`
- `n_dropped_truncated_past_labels`
- `n_dropped_fully_masked_before_truncation`
- `n_dropped_missing_run_id`
- `n_truncated_kept`
- `dropped_run_ids`
- `dropped_truncated_past_labels_run_ids`
- `dropped_fully_masked_before_truncation_run_ids`
- `truncated_kept_run_ids`

## Drop reasons: what could be separated, and what could not

**Separated** (not guessed), using `tokenize_sft_row`'s `truncated` flag plus a second tokenisation **only on the drop path** with `max_length=None` [OBSERVED scripts/train/sft_lora.py:82-98]:

| reason key | meaning |
|---|---|
| `truncated_past_labels` | truncated example has no supervised tokens, but the untruncated row does |
| `fully_masked_before_truncation` | even without the 32768 cap, every label is `-100` |

On the 497-row file, the split is 18 / 0 [OBSERVED a14_retrospective.json].

**Not separated** (would be guessing):

- Message-drop truncation vs remask-unrepresentable (budget fit drops the supervised turn and zeros labels). Both look like `truncated=True` with labels present in the untruncated row, so both are filed as `truncated_past_labels`.
- Character-elision (`n_chars_elided`) vs whole-message drop. Both set `truncated=True`.
- Data-build truncation (`correction.n_truncated = 21` [OBSERVED data/interim/sft_b_plus.jsonl.manifest.json]) is a **different layer** from trainer-time `MAX_LENGTH=32768` fitting. This unit does not claim those 21 are the same 18.

## Tests

`tests/unit/test_sft_lora_drop.py`:

- Fully-masked row (no assistant turn) is counted as dropped, not kept; stderr contains `WARNING: dropped`.
- Truncated row that still has supervised tokens is kept **and** counted as `n_truncated_kept`.
- Manifest-shaped dict contains the new counts; `n_sequences` equals the number trained on.
- Known-answer: N=7 in, k=3 droppable, `dropped == 3`, `n_sequences == 4`.

## Suite (verbatim)

Job `25459839.aqua` after the final trainer patch:

```
406 passed, 1 skipped, 1 warning in 52.38s
```

[OBSERVED that pytest stanza on stdout of the hpc job; spool /home/n12194778/.hpc-spool/20260919-044940-1191268.out]. Baseline was 402 passed, 1 skipped; +4 new tests, never fewer, zero failures.

Earlier suite run on the first instrumentation patch: `406 passed, 1 skipped, 1 warning in 26.34s` [OBSERVED job 25454826.aqua].

## Diff (owned files only; git not run)

`scripts/train/sft_lora.py`:

- `collect_tokenized_sft_rows` + helpers `_row_run_id`, `_has_supervised_labels`, `_drop_reason`, `_emit_drop_warning`.
- `train()` calls the collector instead of the silent loop; writes `**drop_stats` into `manifest.json`; stdout JSON also reports `n_rows_in`, `n_dropped_no_supervised_tokens`, `n_truncated_kept`.
- Optional `retain_examples=False` / `progress_every` for tokenizer-only audits (defaults preserve training).

`tests/unit/test_sft_lora_drop.py`: new.

## Files written

- `scripts/train/sft_lora.py`
- `tests/unit/test_sft_lora_drop.py`
- `campaign/workers/STATUS_A_14.md`
- `campaign/workers/A14_SILENT_DROP.md`
- `campaign/workers/a14_retrospective.json` (raw counts from job 25456324)
