# STATUS_U_Z — oversized last observation (defect #19)

Owner: U-Z
Started: 2026-09-17
Finished: 2026-09-17
Do not submit. Do not commit. Do not qsub/qdel. Job 25401962 left alone.

## Checklist

- [x] 1. `src/sidekick/protocols/prompts.py` — middle-elide oversized anchors in `fit_messages_to_budget`; return `BudgetFit(selected, n_messages_dropped, representable, n_chars_elided)`
- [x] 2. `src/sidekick/agents/executor.py` — keep `representable`; record `n_chars_elided` and `representable` in `usage.raw`; 400 backstop unchanged
- [x] 3. `src/sidekick/training/sft_data.py` — unpack new return; tokenize elided selected; surface `n_chars_elided`
- [x] 4. `tests/unit/test_prompt_budget.py` — six new tests + existing unpack updated
- [x] 5. pytest via `hpc` (unit + reproducibility): `202 passed, 1 skipped in 7.99s`
- [x] 6. This STATUS file

## Return shape [OBSERVED src/sidekick/protocols/prompts.py:43-52,143]

```
BudgetFit(selected, n_messages_dropped, representable, n_chars_elided)
```

Call sites: executor.py:91-99; sft_data.py:358-364. `representable` stored at executor.py:98 and usage.raw at executor.py:172.

## Last pytest result [OBSERVED hpc 25401982.aqua]

```
........................................................................ [ 35%]
........................................................................ [ 70%]
..........................................................s              [100%]
202 passed, 1 skipped in 7.99s
```

Baseline was 196 passed, 1 skipped; six new tests. [INFERRED] 196+6=202.
