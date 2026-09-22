# STATUS_X25 — Novelty Verdict Splice and External Comparison Table

**Date**: 2026-09-23  
**Unit**: Brief X25  

## 1. Novelty Verdict Splicing
- **Zero `TODO(claude)` markers**: Confirmed 0 occurrences remain in `docs/literature_review_20260923.md` [OBSERVED `docs/literature_review_20260923.md:1-256`].
- **Verbatim copy verification**: All nine verdicts from `docs/novelty_boundary_v2.md` §2 (`### Theme 1` through `### Theme 9`) were spliced verbatim with blockquote `> ` prefixes stripped into `docs/literature_review_20260923.md` [OBSERVED `docs/novelty_boundary_v2.md:53-163`, `docs/literature_review_20260923.md:17-256`]. Method: text was extracted character-by-character from source line ranges and verified against target sections.
- **Theme title correspondence**: All nine theme titles correspond exactly with review sections (Themes 1 to 9). No mismatched theme titles were found [OBSERVED `docs/novelty_boundary_v2.md:53-155`, `docs/literature_review_20260923.md:9-209`].

## 2. External Comparison Table
- **Table path**: `docs/external_comparison.md` [OBSERVED `docs/external_comparison.md:1-42`].
- **Row count**: 20 data rows (16 published rows across test_normal/test_challenge splits + 4 internal dev rows) plus 4 category subheader rows [OBSERVED `docs/external_comparison.md:12-34`].
- **Caveat block**: Directly follows the table with all 5 mandatory points [OBSERVED `docs/external_comparison.md:36-47`].

## 3. Facts Marked `NOT ESTABLISHED`
The following fields were not present in the two permitted source files (`campaign/workers/lit/extracts_20260922.md` and `docs/novelty_boundary_v2.md`) and were explicitly marked `NOT ESTABLISHED` [OBSERVED `docs/external_comparison.md:24-34`]:
1. **LOOP**: Split and SGC (`~71% TGC` reported without split or SGC) [OBSERVED `campaign/workers/lit/extracts_20260922.md:278-280`].
2. **CANOPY**: Test-Normal SGC and Test-Challenge SGC (only TGC 86.9 and 67.6 reported) [OBSERVED `campaign/workers/lit/extracts_20260922.md:280-282`].
3. **ACE**: Split, TGC, and SGC (only `+17.1%` relative improvement reported) [OBSERVED `campaign/workers/lit/extracts_20260922.md:282-284`].
4. **`planner_alone`**: SGC on dev (only dev TGC 68.4 reported) [OBSERVED `campaign/workers/lit/extracts_20260922.md:290-292`].
5. **`sft_plan`**: TGC and SGC on dev (no numeric dev results in source files) [INFERRED].
6. **`executor_alone`**: TGC and SGC on dev (no numeric dev results in source files) [INFERRED].
7. **Best prefix arm**: TGC and SGC on dev (no numeric dev results in source files) [INFERRED].

## 4. Compliance Statement
I introduced no citation, number or URL that was not already in one of the two permitted source files (`campaign/workers/lit/extracts_20260922.md` and `docs/novelty_boundary_v2.md`).
