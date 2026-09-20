# Amendment to Pre-Registration: B1 Clean Counterfactual Pilot (2026-09-20)

**Date**: 2026-09-20  
**Target Document**: `docs/prereg_b1_pilot.md` (committed 2026-09-19, frozen, unedited) [OBSERVED docs/prereg_b1_pilot.md:1]

This document records a technical correction to the budget tracking implementation for the B1 clean counterfactual pilot. The target pre-registration document `docs/prereg_b1_pilot.md` remains frozen and is not edited.

## 1. Defect Identified in Implementation

Section 8 of `docs/prereg_b1_pilot.md` defines the experiment's budget as live hosted-planner spend: an expected spend of 6,118 live calls against a hard cap of `--max-planner-calls-total 10000` [OBSERVED docs/prereg_b1_pilot.md:187-195].

During smoke testing, auditing the dispatch counter revealed that `--max-planner-calls-total` summed `branch_planner_calls` [OBSERVED scripts/setup/branch_counterfactual.py:1291, 1297-1318]. In the runtime loop, `branch_planner_calls` is populated from `RunResult.n_planner_calls` [OBSERVED scripts/setup/branch_counterfactual.py:883-905], which `counters_from_events` [OBSERVED src/sidekick/systems/loop.py:119-133] accumulates over all prefix events, including cached, replayed planner interventions.

With approximately 2–3 replayed review ticks per branch over the 1,600 planned branches, the running total would have accumulated 4,000–4,800 replayed ticks alongside live calls. Consequently, the 10,000 cap would have triggered after only ~5,500–6,000 live calls—at or below the expected 6,118 live spend—halting the pilot prematurely on an unearned budget exhaustion.

## 2. Technical Correction

The dispatch accounting in `scripts/setup/branch_counterfactual.py` is corrected to match §8:
- `spent` now sums `branch_live_planner_calls`, extracted from the ledger's live-only call count (`totals.planner_calls_total`).
- A branch row missing live call metadata or holding `None` continues to be charged the pre-registered unknown-call penalty of **81** [OBSERVED docs/prereg_b1_pilot.md:194], preventing silent undercounting.
- The replay-inclusive `branch_planner_calls` field is retained unchanged on result rows for backward compatibility with downstream tools.

## 3. Methodological Status: Correction vs. Renegotiation

This modification is a strict correction to align execution with the pre-registered specification, not a post-hoc renegotiation of experimental terms:

1. **Alignment with Pre-Registered Definition**: §8 explicitly specifies the 10,000 cap and 6,118 expectation in terms of live hosted-planner calls against quota. The implementation was measuring a different quantity (prefix replay ticks + branch live calls). The cap of 10,000 and expected spend of 6,118 remain unchanged and are not being loosened after seeing data.
2. **Absence of Outcome Contamination**: **No valid B1 data existed when this amendment was written.** The sole preceding execution (`25519712.aqua`) suffered a port collision and node-wide kill, yielding 20 crashed rows (HTTP 404 from missing adapter alias), zero completed branches, and zero live planner calls [OBSERVED /scratch/n12194778/sidekick/results/b1_pilot_train_20260919_smoke/branch_runs.jsonl:1-20]. No outcome, partial estimate, or effect size was observed or could have informed this correction.
3. **Invariance of Experimental Rules**: All stopping, resumption, and truncation protocols in §9—including the 5% quota-stall threshold [OBSERVED docs/prereg_b1_pilot.md:213] and the prohibition against analyzing truncated partial prefixes—remain in full effect without modification.
