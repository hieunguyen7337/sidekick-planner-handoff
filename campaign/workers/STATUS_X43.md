# Status X43 — External Comparison Table & Limitations Note

**Date**: 2026-09-23  
**Unit**: X43 (External Comparison & Limitations)  
**Status**: Complete  

## 1. Files Written
- `docs/external_comparison_20260923.md` [OBSERVED docs/external_comparison_20260923.md:1-85]
- `docs/limitations_external_20260923.md` [OBSERVED docs/limitations_external_20260923.md:1-24]

## 2. External Verification Census
- **Total External Rows**: 38 rows.
- **Verified Rows (`[OBSERVED <url>]`)**: 37 rows [OBSERVED docs/external_comparison_20260923.md:13-58].
- **Unverified Rows (`[UNVERIFIED]`)**: 1 row (Early Experience paper's specific AppWorld breakdown cell left blank) [OBSERVED docs/external_comparison_20260923.md:46].

### URLs Fetched & Read
- `https://arxiv.org/abs/2407.18901` and `https://arxiv.org/html/2407.18901v1` (AppWorld) [OBSERVED]
- `https://arxiv.org/abs/2502.01600` (LOOP) [OBSERVED]
- `https://arxiv.org/abs/2609.01245` (CANOPY) [OBSERVED]
- `https://arxiv.org/abs/2510.04618` (ACE) [OBSERVED]
- `https://arxiv.org/abs/2510.08558` (Early Experience) [OBSERVED]
- `https://arxiv.org/abs/2607.20536` (AppWorld-UL) [OBSERVED]
- `https://arxiv.org/abs/2509.04508` (ProST) [OBSERVED]
- `https://arxiv.org/abs/2604.11465` (Three Roles, One Model) [OBSERVED]
- `https://appworld.dev/` (Leaderboard anchor for `gpt-5.6-luna`) [OBSERVED docs/PLAN.md:102-103]

## 3. Internal Dev Numbers & Ledger Claim IDs
All internal figures are evaluated on the 57-task dev split (114 paired episodes, 2 seeds) under our minimal interaction loop:

| Arm | `goal_pass_rate` | Ledger Claim ID | Context |
|---|---|---|---|
| Executor alone (granite 8B + adapter) | 0.5289 | `ADV-FC-02`, `TAILOR-06` [OBSERVED docs/claims_ledger.md:60,83] | Cross-build capability floor |
| One plan (`sft_plan`, `iaware` build) | 0.7181 | `ADV-FC-01`, `ADV-FC-02`, `UF-01` [OBSERVED docs/claims_ledger.md:10,82,83] | Initial plan, zero escalation |
| Advice k=10, full context | 0.7339 | `ADV-FC-01` [OBSERVED docs/claims_ledger.md:82] | Periodic review, full transcript |
| Takeover k=10 (action channel) | 0.8007 | `CHAN-C1-01` [OBSERVED docs/claims_ledger.md:89] | Matched-trigger takeover; point estimate only |
| Action prefix m=9 / m=11 | 0.7852 / 0.8098 | `SHAPE-01`, `SHAPE-06`, `TAILOR-07` [OBSERVED docs/claims_ledger.md:36,47,66] | Tailored receiver post-guard |
| Ceiling, cap-25 | 0.8284 | `CEIL-07`, `CEIL-08` [OBSERVED docs/claims_ledger.md:69,70] | Replayed trajectory source |
| Ceiling, cap-81 | 0.7637 | `CEIL-07`, `CEIL-08`, `CEIL-09` [OBSERVED docs/claims_ledger.md:69,70,72] | Independent planner sample |

## 4. Methodological Alignment
The 4 causes of discrepancy against published leaderboard scores (scaffold, split, task count, reasoning effort) and the paired within-task experimental rationale are documented without hedging [OBSERVED docs/limitations_external_20260923.md:1-24].
