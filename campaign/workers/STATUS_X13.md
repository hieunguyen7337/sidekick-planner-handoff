# STATUS — X13: Record Phase P1 Prefix Frontier & Gate G1 Verdict

## Summary of Recorded Artifacts

1. **`campaign/RUNS.md` Heading**: `## 14. Phase P1 prefix curve and Gate G1 verdict — 2026-09-22` [OBSERVED campaign/RUNS.md:2451].
   - Recorded per-arm results table across all 114 dev episodes, noncached token costs, and handoff rates [OBSERVED campaign/RUNS.md:2464-2475].
   - Recorded the three contrast tables (prefix vs `sft_plan` floor, non-inferiority vs `planner_alone`, chord allocation test) [OBSERVED campaign/RUNS.md:2477-2514].
   - Recorded $m=9$ contamination detail (32 no-handoff easy tasks) and honest handoff-only contrast ($-2.08\text{ pp}$ [−11.25, +7.51]) [OBSERVED campaign/RUNS.md:2516-2522].
   - Recorded Gate G1 verdict as **FAILED** on both pre-registered clauses [OBSERVED campaign/RUNS.md:2524-2533].
   - Recorded the substantive mechanism finding: executor failure begins in opening steps, but providing 4–6 planner opening steps does not improve completion [OBSERVED campaign/RUNS.md:2535-2543].
   - Stated zero hosted planner calls spent; jobs `25596786` and `25596787` [OBSERVED campaign/RUNS.md:2457-2460].

2. **`docs/FOLLOWUPS.md` Entry Title**: `## OPEN 2026-09-22 — m=9 prefix arm cannot be reported on all-episodes without handoff-only figure` [OBSERVED docs/FOLLOWUPS.md:1027].
   - Documents that $m=9$ all-episodes figure mixes 32 replayed reference episodes on easier tasks (reference goal-pass 0.8961 vs 0.8020 on handoff tasks) and mandates reporting handoff-only ($-2.08\text{ pp}$) alongside all-episodes ($-1.50\text{ pp}$) [OBSERVED docs/FOLLOWUPS.md:1027-1037].

3. **`docs/prereg_hj12_dev_20260922.md` Amendment Heading**: `## Amendment 2026-09-22 — Phase P1 Prefix Curve Result and Gate G1 Verdict` [OBSERVED docs/prereg_hj12_dev_20260922.md:291].
   - Records empirical gate failure on clause (a) (all lower bounds $\le -17.46\text{ pp}$ vs $-7.00\text{ pp}$ margin) and clause (b) (diff $-0.37\text{ pp}$ vs $+5.00\text{ pp}$, non-monotone) [OBSERVED docs/prereg_hj12_dev_20260922.md:297-310].
   - Confirms flat-curve branch is in force (live phase shrinks to channel arms, tailoring becomes central) without altering registered gate definitions [OBSERVED docs/prereg_hj12_dev_20260922.md:312-315].

## Gap Markers
- `[GAP]`: None. All figures and contrast statistics were resolved directly from `campaign/results/hj12_prefix_frontier_20260922.report.json` and `campaign/results/failure_anatomy_dev_20260921.json`.

## Constraints Honored
- Documentation only: no modifications to `src/`, `scripts/`, or `configs/` [INFERRED].
- No git commands run [INFERRED].
- Zero hosted planner calls spent [OBSERVED campaign/RUNS.md:2459].
