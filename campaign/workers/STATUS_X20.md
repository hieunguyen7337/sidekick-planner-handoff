# Worker Status X20: Systematic Literature Review for Pivoted Thesis

**Date**: 2026-09-23  
**Status**: Completed  
**Owner**: Antigravity (`agy`)

---

## 1. Generated Output Paths

All five requested artifacts were generated and verified:
1. `docs/lit/screening_log.csv` `[OBSERVED docs/lit/screening_log.csv]`
2. `docs/literature_review_20260923.md` `[OBSERVED docs/literature_review_20260923.md]`
3. `docs/literature_matrix_v2.md` `[OBSERVED docs/literature_matrix_v2.md]`
4. `docs/concurrent_work.md` `[OBSERVED docs/concurrent_work.md]`
5. `paper/bibliography.bib` `[OBSERVED paper/bibliography.bib]`

Companion protocol: `docs/lit/PROTOCOL.md` `[OBSERVED docs/lit/PROTOCOL.md]`.

---

## 2. Screening Statistics

- **Total Papers Screened**: 73 `[OBSERVED docs/lit/screening_log.csv]`
- **Papers Included**: 58 (target $\ge 35$ met) `[OBSERVED docs/lit/screening_log.csv]`
- **Papers Excluded**: 15 (all with explicit reasons recorded) `[OBSERVED docs/lit/screening_log.csv]`

---

## 3. Search Queries and Exact Hit Counts

Executed on 2026-09-22 across Web/arXiv/Scholar `[OBSERVED docs/lit/PROTOCOL.md:42-59]`:
1. `"model handoff" agent trajectory`: 42 hits `[OBSERVED docs/lit/PROTOCOL.md:43]`
2. `"downshift" "cheaper model" agent trajectory`: 28 hits `[OBSERVED docs/lit/PROTOCOL.md:44]`
3. `"planner executor" "small model" "large model"`: 114 hits `[OBSERVED docs/lit/PROTOCOL.md:45]`
4. `"step-level routing" agent`: 67 hits `[OBSERVED docs/lit/PROTOCOL.md:46]`
5. `"turn-level routing"`: 89 hits `[OBSERVED docs/lit/PROTOCOL.md:47]`
6. `"fast slow agent" small large`: 31 hits `[OBSERVED docs/lit/PROTOCOL.md:48]`
7. `"speculative planning" agent`: 53 hits `[OBSERVED docs/lit/PROTOCOL.md:49]`
8. `"agent distillation" "small model" trajectories`: 76 hits `[OBSERVED docs/lit/PROTOCOL.md:50]`
9. `"on-policy distillation" "multi-turn" agent`: 38 hits `[OBSERVED docs/lit/PROTOCOL.md:51]`
10. `"teacher prefix replay"`: 19 hits `[OBSERVED docs/lit/PROTOCOL.md:52]`
11. `"advice" "critique" "small model" self-correct`: 64 hits `[OBSERVED docs/lit/PROTOCOL.md:53]`
12. `"compounding errors" LLM agents long-horizon`: 82 hits `[OBSERVED docs/lit/PROTOCOL.md:54]`
13. `"learning to defer" sequential`: 95 hits `[OBSERVED docs/lit/PROTOCOL.md:55]`
14. `"AppWorld" benchmark`: 140 hits `[OBSERVED docs/lit/PROTOCOL.md:56]`
15. `"non-inferiority" bootstrap NLP`: 23 hits `[OBSERVED docs/lit/PROTOCOL.md:57]`
16. `"checkpoint handoff" "evaluation protocol"`: 12 hits `[OBSERVED docs/lit/PROTOCOL.md:58]`

---

## 4. Five Closest Papers to Our Setting

1. **`handoff_tax_ganz_2026`** (arXiv:2608.24358): Investigates continuing non-native trajectories during model downshifts and escalations across SWE-bench, establishing the foundational cost-quality dynamics of mid-trajectory handoffs `[OBSERVED docs/literature_matrix_v2.md:144]`.
2. **`reach_or_solve_2026`** (arXiv:2609.19636): Establishes checkpoint handoff as an empirical evaluation protocol to isolate exploration state-reachability from terminal solving `[OBSERVED docs/literature_matrix_v2.md:155]`.
3. **`reopd_liao_2026`** (arXiv:2607.04763): Formalizes prefix replay and analyzes the prefix-trap distribution shift in multi-turn student policy training `[OBSERVED docs/literature_matrix_v2.md:166]`.
4. **`think_big_search_small_2026`** (arXiv:2607.07548): Proves capacity asymmetry where scaling high-level delegation provides massive gains (+11 EM) while execution sub-agents can be distilled to 1.7B with 37% token savings `[OBSERVED docs/literature_matrix_v2.md:270]`.
5. **`prost_bijoy_2025`** (arXiv:2509.04508): Establishes progressive multi-role SLM supervised training and Pareto efficiency evaluation directly on the AppWorld benchmark `[OBSERVED docs/literature_matrix_v2.md:26]`.

---

## 5. Fields Marked NOT ESTABLISHED

- **`mtrouter_2026`**: Exact quantitative benchmark metrics and dataset splits `[OBSERVED docs/literature_matrix_v2.md:239]`.
- **`dsp_guan_2025`**: Specific benchmark names evaluated in the paper abstract `[OBSERVED campaign/workers/lit/extracts_20260922.md:159]`.
