# Status X28 — Bibliography Repair

## 1. Deleted Fabricated Citations and In-Text Repairs

Four fabricated bibkeys were deleted from `paper/bibliography.bib` `[OBSERVED paper/bibliography.bib:1-560]` and marked `include=no` with `reason=fabricated_citation_removed_X28` in `docs/lit/screening_log.csv:5,6,26,57` `[OBSERVED docs/lit/screening_log.csv:5,6,26,57]`:
- `cascade_cost_valkanas_2025`
- `cascading_aggregating_kotte_2026`
- `cld_kim_2024`
- `sequential_deferral_charusaie_2024`

In-text mentions removed and sentences repaired:
- `docs/literature_review_20260923.md:13` (dropped Valkanas et al., 2025 and Kotte et al., 2026) `[OBSERVED docs/literature_review_20260923.md:13]`:
  > "Subsequent extensions, including Hybrid LLM (Ding et al., 2024), refined router feature representations and threshold calibration for heterogeneous commercial endpoints `[OBSERVED https://arxiv.org/abs/2404.14618]`."
- `docs/literature_review_20260923.md:94` (replaced collaborative decoding / Kim 2024 with Big Little Decoder / Kim 2023; updated Leviathan year to 2022) `[OBSERVED docs/literature_review_20260923.md:94]`:
  > "At the token generation level, speculative decoding (Leviathan et al., 2022; Chen et al., 2023) and Big Little Decoder (Kim et al., NeurIPS 2023) use small draft models to generate candidate token sequences that a large target model verifies in parallel via modified rejection sampling `[OBSERVED https://arxiv.org/abs/2211.17192]`."
- `docs/literature_review_20260923.md:201` (dropped Charusaie et al., 2024 and pointed URL tag to Mozannar 2006.01862) `[OBSERVED docs/literature_review_20260923.md:201]`:
  > "In the context of multi-stage delegation, learning-to-defer frameworks (Mozannar & Sontag, ICML 2020) establish optimal mathematical criteria for deferring decisions to an expert under non-uniform stage costs `[OBSERVED https://arxiv.org/abs/2006.01862]`."
- `docs/literature_matrix_v2.md` and `docs/concurrent_work.md`: verified clean of the four deleted keys `[OBSERVED docs/literature_matrix_v2.md:1-655]`, `[OBSERVED docs/concurrent_work.md:1-119]`.

## 2. Substitution: `bild_kim_2023`

Written as `[OBSERVED paper/bibliography.bib:521-529]`:
```bibtex
@inproceedings{bild_kim_2023,
  author    = {Sehoon Kim and others},
  title     = {Speculative Decoding with Big Little Decoder},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year      = {2023},
  eprint    = {2302.07863},
  archivePrefix = {arXiv},
  url       = {https://arxiv.org/abs/2302.07863}
}
```

## 3. Corrections Count

- **Titles corrected (14)**: `guided_opd_2026`, `early_exit_lu_2025`, `isp_2024`, `dsp_guan_2025`, `mtrouter_2026`, `where_agents_fail_2025`, `rfcl_2024`, `ace_2026`, `appworld_ul_2026`, `granite_4_2_ibm_2026`, `gpt_oss_openai_2025`, `gpt_5_6_luna_2026`, `agentflan_chen_2024`, `critic_gou_2023` `[OBSERVED paper/bibliography.bib:1-560]`.
- **Years corrected (7)**: `isp_2024` (→2024), `llms_cannot_self_correct_huang_2024` (→2023), `ace_2026` (→2025), `early_experience_2026` (→2025), `routellm_ong_2024` (→2024), `speculative_decoding_leviathan_2023` (→2022), `critic_gou_2023` (→2023) `[OBSERVED paper/bibliography.bib:1-560]`.

## 4. RFCL Fix

- `paper/bibliography.bib:258-266`: set author to `Stone Tao and Arth Shukla and Tse-kai Chan and Hao Su`, title to `Reverse Forward Curriculum Learning for Extreme Sample and Demonstration Efficiency in Reinforcement Learning`, eprint/url to `arXiv:2405.03379` `[OBSERVED paper/bibliography.bib:258-266]`.
- `docs/literature_review_20260923.md:148`: updated prose citation to `Tao et al., 2024, arXiv:2405.03379` and dropped OpenReview URL `[OBSERVED docs/literature_review_20260923.md:148]`.
- `docs/literature_matrix_v2.md:535-546`: aligned title and URL with arXiv record `[OBSERVED docs/literature_matrix_v2.md:535-546]`.

## 5. Verification Numbers

- **Remaining entries in `paper/bibliography.bib`**: **56** `[OBSERVED paper/bibliography.bib:1-560]`.
- **Entries with verdict `OK` or corrected title traceable to audit/brief**: **56** (30 `OK` + 25 corrected `MISMATCH` + 1 supplied `bild_kim_2023`) `[OBSERVED paper/bibliography.bib:1-560]`, `[OBSERVED docs/lit/bibliography_audit.csv:2-60]`. None outside these categories.
