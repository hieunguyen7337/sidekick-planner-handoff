# Status X4 — Ledger Entries, Seam Contract, and HJ-12 Dev Preregistration

**Date**: 2026-09-21  
**Unit**: X4 (Records and Preregistration)  

### Files Written / Modified

1. `campaign/RUNS.md` [OBSERVED campaign/RUNS.md:2376-2426]: Appended Section 12 ("The E-series: intervention-aware retrain") recording paired dev frontier comparisons ($n=114$) between stripped (`sft_b_plus`) and intervention-aware (`sft_b_plus_iaware`) adapters, crash elimination, and explicit freeze discipline regarding `goal_pass` vs TGC.
2. `docs/FOLLOWUPS.md` [OBSERVED docs/FOLLOWUPS.md:947-961]: Appended two entries: (a) action-review gate inertia against the hosted planner (`resp.code` absence in `CodexExecPlanner.correct` vs `planner.act`), and (b) protocol pivot from natural-language advice to planner action / prefix handoff following B1 counterfactual results.
3. `campaign/briefs/SEAM_CONTRACT.md` [OBSERVED campaign/briefs/SEAM_CONTRACT.md:70-73, 138-142, 183-201]: Added systems `action_review` and `prefix_handoff` (10 total); cost key `replayed_planner_tokens` (excluding cached input tokens); policy flags `review_proposed_action`, `takeover`, `handoff_allowed`; and the `handoff:` config block.
4. `docs/prereg_hj12_dev_20260922.md` [OBSERVED docs/prereg_hj12_dev_20260922.md:1-175]: Created the HJ-12 dev preregistration specifying Claims C1 (Channel), C2 (Allocation), and C3 (Tailoring); $m \in \{2, 4, 6, 9\}$ grid; verbatim decision gates G1 and G2; advance predictions; and threats to validity.

### Items Marked `[NEEDED]`
- **None** [INFERRED]. All empirical figures, confidence intervals, sample counts, and code references were verified against `campaign/results/hj8_frontier_iaware_20260921.report.json` [OBSERVED:1-15], `/scratch/n12194778/sidekick/results/b1_pilot_train_20260920/manifest.json` [OBSERVED:37-53], and repo source files.

### Repository Reconciliations / Discrepancies
- In `src/sidekick/protocols/schemas.py:106-109`, `EventType` had already added `"action_review"`, while `SEAM_CONTRACT.md:70-73` listed the legacy 10-element literal. `SEAM_CONTRACT.md` was updated to reflect `"action_review"` alongside the new systems and policy flags [OBSERVED src/sidekick/protocols/schemas.py:106-109, campaign/briefs/SEAM_CONTRACT.md:70-73].
- All modifications were strictly confined to documentation files; no code files were modified [INFERRED].
