# STATUS X23 — bibliography citation-integrity audit

Audit complete for all 59 bibliography entries and all 58 screening-log rows marked `include=yes`; the included screening keys are a subset of the bibliography keys. [OBSERVED docs/lit/bibliography_audit.csv:1-60] [OBSERVED docs/lit/screening_log.csv:1-74]

## Verdict counts

- `OK`: 14. Each is pre-verified against the trusted fetched extracts, with matching title and first-author surname. [OBSERVED docs/lit/bibliography_audit.csv:2-60]
- `MISMATCH`: 1. [OBSERVED docs/lit/bibliography_audit.csv:2-60]
- `UNRESOLVED`: 0. [OBSERVED docs/lit/bibliography_audit.csv:2-60]
- `UNVERIFIABLE`: 44. Direct canonical-source fetches failed at DNS resolution; no verdict was guessed from bibliography metadata. [OBSERVED https://arxiv.org/abs/2602.14890]

## Complete action list

- `MISMATCH` — `cascading_aggregating_kotte_2026`: real title **“Lifted Relational Probabilistic Inference via Implicit Learning”**, by Ge, Juba, Nilsson, and Shao; the claimed LLM-cascading paper is fabricated. [OBSERVED campaign/workers/brief_X23_bibliography_audit.md:19-20]
- `UNRESOLVED` — none. [OBSERVED docs/lit/bibliography_audit.csv:2-60]

## Risk and year checks

The bibliography contains 20 entries using the `and others` author form. [OBSERVED paper/bibliography.bib:1-588]

Four claimed years differ from the submission year encoded in their pre-verified arXiv identifiers: `isp_2024` claims 2025 vs 2024; `llms_cannot_self_correct_huang_2024` claims 2024 vs 2023; `ace_2026` claims 2026 vs 2025; `early_experience_2026` claims 2026 vs 2025. [INFERRED] In each case, the claimed year is the venue year. [OBSERVED campaign/workers/lit/extracts_20260922.md:153-155] [OBSERVED campaign/workers/lit/extracts_20260922.md:222-223] [OBSERVED campaign/workers/lit/extracts_20260922.md:282-285]

Audit table: `docs/lit/bibliography_audit.csv`. [OBSERVED docs/lit/bibliography_audit.csv:1-60]

## Validation output

```text
CSV data rows: 59
Verdicts: OK=14 MISMATCH=1 UNRESOLVED=0 UNVERIFIABLE=44
CSV keys missing from bibliography: 
Bibliography keys missing from CSV: 
Included screening keys missing from CSV: 
Duplicate CSV keys: 
and others entries: 20
```

[OBSERVED docs/lit/bibliography_audit.csv:1-60]
