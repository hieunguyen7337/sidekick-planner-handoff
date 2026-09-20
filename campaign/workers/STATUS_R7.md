# STATUS R7 — 2026-09-20 Smoke Findings & Pre-Execution Verification

**Unit:** R7 — Record 2026-09-20 smoke findings in `campaign/RUNS.md`
**State:** done
**Last update:** 2026-09-20

## Verification Summary

All figures and facts in `brief_R7_smoke_record.md` were checked against raw logs and config files before recording:

1. **Parallel Execution & Port Isolation**
   - J8 live smoke (`25558685.aqua`): port `38685`, PID/PGID `1821315`, alias `sft_b_plus` verified in `/v1/models`, all 10 arm gates passed, exit `job_rc=0` [OBSERVED campaign/workers/logs/hj8_frontier_live_20260920livesmoke.25558685.aqua.out:98-102, 150-603, 621].
   - B1 pilot smoke (`25559748.aqua`): port `39748`, PID/PGID `2006139`, alias `sft_b` verified in `/v1/models`, 32 branch runs completed, exit `smoke_rc=0` [OBSERVED campaign/workers/logs/b1_pilot_train_20260920c.25559748.aqua.out:11-16, 1118-1122].

2. **B1 Pilot Smoke & Budget Counter Ratio**
   - Spend log confirmed: `n_rows=32 live_planner_calls_sum=44 branch_planner_calls_tick_sum=165 planner_tokens_sum=1343501 error_type_counts=None=17,limit=15` [OBSERVED campaign/workers/logs/b1_pilot_train_20260920c.25559748.aqua.out:1118].
   - Ratio: 44 live vs 165 ticks (3.75x ratio). Old counter would have capped at ~2,667 live calls against 6,118 budgeted [INFERRED].
   - Errors: 17 clean, 15 limit, 0 infrastructure faults [OBSERVED campaign/workers/logs/b1_pilot_train_20260920c.25559748.aqua.out:1118].

3. **J8 Smoke Escalation Profile**
   - 10-arm smoke escalation table verified line-by-line from log [OBSERVED campaign/workers/logs/hj8_frontier_live_20260920livesmoke.25558685.aqua.out:607-617].
   - `sidekick` arms: 0 live calls across all $\tau$; warning `WARN: every sidekick arm in this smoke pass has identical live_planner_calls=0` observed [OBSERVED campaign/workers/logs/hj8_frontier_live_20260920livesmoke.25558685.aqua.out:618]. Historical ask rate: 0/114 (HJ-1) [OBSERVED campaign/RUNS.md:490], 1/114 (HJ-1R) [OBSERVED campaign/RUNS.md:486].
   - `router_seq`: 33 calls at $\tau=0.3$, 0 calls at $\tau=0.5, 0.7$ [OBSERVED campaign/workers/logs/hj8_frontier_live_20260920livesmoke.25558685.aqua.out:611-613].
   - `oracle_escalation`: 0 calls in smoke [OBSERVED campaign/workers/logs/hj8_frontier_live_20260920livesmoke.25558685.aqua.out:617]. Inlined oracle labels checked in `configs/hj8_oracle_escalation.yaml:37-216`: 106 task/seed pairs present (8 missing), 28 with $\ge 1$ step (26.41%), 43 oracle steps total [OBSERVED configs/hj8_oracle_escalation.yaml:37-216]. $P(\text{0 steps in 3 episodes}) = (1 - 0.2641)^3 = 0.3984 \approx 0.40$ [INFERRED].

4. **Ledger Record & Preregistration**
   - Section added to `campaign/RUNS.md` (§9).
   - Owned files touched: `campaign/RUNS.md`, `campaign/workers/STATUS_R7.md`. No code modified, no jobs submitted, no git commands executed.
