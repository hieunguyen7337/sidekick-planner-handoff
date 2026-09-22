# STATUS_X47

- **Regenerated figures**: F1 (`f1_depth_curve`), F2 (`f2_channel_matched_budget`), F3 (`f3_tailoring_gap`), F4 (`f4_mechanism`), F5 (`f5_second_family`), and F6 (`f6_narrated_vs_executed`) as PDF and PNG [OBSERVED `paper/figures/figures_manifest.json:1-239`].
- **New tests**:
  - `test_f5_no_floor_series_drawn` [OBSERVED `tests/unit/test_figures.py:302`]
  - `test_f5_mandatory_annotation_present` [OBSERVED `tests/unit/test_figures.py:335`]
  - `test_f1_confidence_bands_drawn_when_present` [OBSERVED `tests/unit/test_figures.py:348`]
  - `test_f6_narrated_vs_executed_generation_and_manifest` [OBSERVED `tests/unit/test_figures.py:375`]
- **Pass count**: 10 passed of 10 tests [OBSERVED `pytest tests/unit/test_figures.py` run].
- **F5 annotation string**: `"Floor not shown: both Qwen floor arms score identically and complete no tasks, so no floor-relative lift is measurable (QWEN-03)."` [OBSERVED `scripts/analysis/figures.py:35-38`].
- **Skipped series/figures**: None skipped; all 6 figures generated with `skipped_reason: null` [OBSERVED `paper/figures/figures_manifest.json:51,98,119,168,192,237`]. Per-arm confidence bands in F1/F5 note absence of interval keys in source reports [OBSERVED `paper/figures/figures_manifest.json:25,37,188`].
