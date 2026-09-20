# STATUS C1 — record the J8 dev frontier in campaign/RUNS.md

Unit: C1
Started: 2026-09-20
State: DONE — section 10 appended to `campaign/RUNS.md`; no other files modified.

## Resume state
- Section 10 appended to `campaign/RUNS.md` [OBSERVED campaign/RUNS.md:2229-2310].
- Did not submit any jobs, run python, or execute git commands.

## Files owned
- `campaign/RUNS.md`
- `campaign/workers/STATUS_C1.md` (this)

## Summary of changes
- Appended `## 10. J8 dev frontier — 2026-09-20 (twelve arms, n=114 each)` at `campaign/RUNS.md:2229-2310`.
- Recorded twelve-arm dev frontier table and cost metrics (`calls`, token spend, crash rates).
- Evaluated F1 non-inferiority: only `router_seq_tau05` clears margin (by 0.86 pp CI lower bound).
- Evaluated F2 oracle headroom: matches `fixed_k_10` quality at 47% calls and 14% tokens; no strict multi-axis dominance established.
- Evaluated H3 gate calibration (sidekick AUROC 0.6759, highest yet, zero escalations) and replicate-noise measurement (TGC spread 3.5 pp, goal_pass spread 0.9 pp across identical τ=0.3/0.5/0.7 policies).
- Nothing in the brief was declined.
