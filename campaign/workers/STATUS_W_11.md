# STATUS W-11 — Gate B (dev) results and campaign hazards documentation

**Unit:** W-11. **Docs only under `campaign/RUNS.md`, `docs/FOLLOWUPS.md`, and this status file. No code, no configs, no PBS, no git commits.** [OBSERVED campaign/workers/brief_W11_docs.md:96-105]
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15` [OBSERVED campaign/workers/brief_W11_docs.md:3-4]
**Date:** 2026-09-17

## Deliverables & Resume State

- [x] **1. `campaign/RUNS.md`: Gate B (dev) result block (Task 1)** [OBSERVED campaign/workers/brief_W11_docs.md:11-49, campaign/RUNS.md:1715-1744]
  - Job: `25412541.aqua`, campaign `hj6_branches_dev_20260917`, split dev, adapter `sft_b`, branch seeds 101/102, commit `dc92a25` [OBSERVED campaign/workers/brief_W11_docs.md:18-19, campaign/RUNS.md:1717].
  - Coverage: 1527 of 1528 branches; 382 intervention points, 374 complete, 8 dropped (1 missing all samples, 7 null `branch_gpr`) [OBSERVED campaign/workers/brief_W11_docs.md:20-21, campaign/RUNS.md:1718].
  - Band δ: 0.166 (75th percentile of |treated[101] − treated[102]| over train points as of 22:44), flagged as provisional [OBSERVED campaign/workers/brief_W11_docs.md:22-25, campaign/RUNS.md:1719].
  - Negative control: unfrozen δ yields `label_status: incomplete` for all 381 rows [OBSERVED campaign/workers/brief_W11_docs.md:43-44, campaign/RUNS.md:1720].
  - Labels over 374 complete points: needed = 59 (0.157754, mean Δ +0.342686), needless (= harmful) = 53 (0.141711, mean Δ −0.356472), ambiguous = 262 (0.700535, mean Δ +0.004672) [OBSERVED campaign/workers/brief_W11_docs.md:26-33, campaign/RUNS.md:1722-1729].
  - Mean Δ per point = +0.006817; 1 − f = 0.8422 (paper figure) [OBSERVED campaign/workers/brief_W11_docs.md:34, campaign/RUNS.md:1730-1732].
  - Validation: 81 of 374 factual outcomes outside `[min(treated), max(treated)]` (0.216578) [OBSERVED campaign/workers/brief_W11_docs.md:35-36, campaign/RUNS.md:1733].
  - Oracle allocation: +0.0541/point vs +0.0068 always-on at 84.2 % fewer calls, flagged as inflated by regression to the mean [OBSERVED campaign/workers/brief_W11_docs.md:37-39, campaign/RUNS.md:1734].
  - Cross-check: W-10 independent recount in `campaign/workers/W10_RECOUNT.md` agrees to ≥ 4 decimals on every statistic [OBSERVED campaign/workers/brief_W11_docs.md:40-42, campaign/RUNS.md:1735].
  - Verdict against pre-registered thresholds: f_dev = 0.158 is not > 0.85; harmful = 0.1417 is just under 0.15 flag threshold; f_train is not final and omitted [OBSERVED campaign/workers/brief_W11_docs.md:46-49, campaign/RUNS.md:1737-1743].

- [x] **2. `campaign/RUNS.md`: Label-reliability threat analysis (Task 2)** [OBSERVED campaign/workers/brief_W11_docs.md:50-71, campaign/RUNS.md:1745-1763]
  - Split-half agreement (seeds 101 vs 102 over 374 complete dev points): Pearson r = 0.163962, Spearman ρ = 0.222022, sign agreement 0.7024 (59/84), 56 points above band on both halves vs 35.81 expected (1.56× chance) [OBSERVED campaign/workers/brief_W11_docs.md:55-58, campaign/RUNS.md:1749-1754].
  - Spearman-Brown reliability: 0.282 for 2 replicates, 0.440 for 4 replicates [OBSERVED campaign/workers/brief_W11_docs.md:58-60, campaign/RUNS.md:1755].
  - Substantive reading: heterogeneity is real (70 % sign agreement vs 50 % null) but weak (~72 % variance is sampling error) [OBSERVED campaign/workers/brief_W11_docs.md:62-63, campaign/RUNS.md:1757-1759].
  - Gate B gap: Gate B thresholds concern f only and would not catch low reliability; reliability criterion is proposed, not an adopted gate [OBSERVED campaign/workers/brief_W11_docs.md:64-67, campaign/RUNS.md:1761-1763].

- [x] **3. `docs/FOLLOWUPS.md`: Two OPEN entries (Task 3)** [OBSERVED campaign/workers/brief_W11_docs.md:72-95, docs/FOLLOWUPS.md:415-461]
  - (a) Wedged branch idling J6 job (`fixed_k/2/37a8675_1__b2_untreated_s102` wedged at step 34), consequences for all-or-nothing aggregation and worker invisibility, and suggested fixes (per-branch timeout, incremental aggregation) [OBSERVED campaign/workers/brief_W11_docs.md:76-85, docs/FOLLOWUPS.md:443-461].
  - (b) J6 log paths lacking campaign ID: expanded the existing server log entry to also cover `#PBS -o campaign/workers/logs/hj6_branches.out`, detailing concurrent overwrite at overlapping offsets and unusable diagnostic logs [OBSERVED campaign/workers/brief_W11_docs.md:86-95, docs/FOLLOWUPS.md:415-441].

## 2.3× Figure Confirmation

The superseded 2.3× figure was searched across all files in `campaign/` and `docs/`. It existed only in `campaign/workers/brief_W11_docs.md:68` (the brief itself) and did not appear anywhere else in `campaign/` or `docs/`; the full-dev 1.56× figure has been recorded in `campaign/RUNS.md:1753-1754` with a note that 2.3× from partial data was superseded. [OBSERVED campaign/workers/brief_W11_docs.md:68-70, campaign/RUNS.md:1753-1754]

## Owned Files (this unit)

- `campaign/RUNS.md`
- `docs/FOLLOWUPS.md`
- `campaign/workers/STATUS_W_11.md` (this file)
