# STATUS W-12 — Gate B (train), fired harmful flag, and ×4 reliability result

**Unit:** W-12. **Docs only under `campaign/RUNS.md`, `docs/FOLLOWUPS.md`, and this status file. No code, no configs, no PBS, no git commits.** [OBSERVED campaign/workers/brief_W12_gateb_train.md:111-116]
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15` [OBSERVED campaign/workers/brief_W12_gateb_train.md:3]
**Date:** 2026-09-18

## Deliverables & Resume State

- [x] **1. `campaign/RUNS.md`: Gate B (train) block (Task 1)** [OBSERVED campaign/workers/brief_W12_gateb_train.md:10-42, campaign/RUNS.md:1767-1794]
  - **Source**: `branch_runs.jsonl` of `hj6_branches_train_20260917`, 4,188 rows at aggregation, re-aggregated on CPU with branch seeds 101/102 [OBSERVED campaign/workers/brief_W12_gateb_train.md:12-13].
  - **Coverage**: 777 intervention points seen; **734 complete** on seeds 101/102; 43 incomplete (261 points complete on all 4 seeds at aggregation; ×4 job running) [OBSERVED campaign/workers/brief_W12_gateb_train.md:14-16].
  - **δ is now FROZEN on train**: `delta_band_delta = 0.166` (pre-registered rule: 75th percentile of |treated[101] − treated[102]| over 734 complete points). Confirmed identical to provisional dev value; dev provisional warning updated [OBSERVED campaign/workers/brief_W12_gateb_train.md:17-20, campaign/RUNS.md:1720].
  - **Labels over 734 complete points**: needed = 83 (0.1131), needless (= harmful) = 120 (0.1635), ambiguous = 531 (0.7234) [OBSERVED campaign/workers/brief_W12_gateb_train.md:22-26].
  - **Mean Δ per point** = **−0.0206**; on train, fixed review schedule average effect is negative [OBSERVED campaign/workers/brief_W12_gateb_train.md:28-29].
  - **Validation**: factual outside `[min(treated), max(treated)]` for 0.16869 of 741 compared; mean signed difference +0.03529 [OBSERVED campaign/workers/brief_W12_gateb_train.md:30-31].
  - **Verdict against pre-registered Gate B thresholds**:
    - `f_train < 0.10` → does not fire (0.1131). 83 needed points clears "< 75 positives" concern, so no 4th teacher/correction seed required before J5b [OBSERVED campaign/workers/brief_W12_gateb_train.md:35-36].
    - `f_dev > 0.85` → does not fire (0.158 at two replicates, 0.130 at four) [OBSERVED campaign/workers/brief_W12_gateb_train.md:37].
    - `harmful > 0.15` → **🔺 FIRES** at **0.1635** (120 of 734). Pre-registered consequence flags review format in `docs/FOLLOWUPS.md`; changes H3 reading [OBSERVED campaign/workers/brief_W12_gateb_train.md:38-41].

- [x] **2. `campaign/RUNS.md`: Dev ×4 replicate reliability and label movement (Task 2)** [OBSERVED campaign/workers/brief_W12_gateb_train.md:43-73, campaign/RUNS.md:1796-1830]
  - **Replicate run**: 3,056 branch runs, 332 points complete on all 4 seeds × both conditions [OBSERVED campaign/workers/brief_W12_gateb_train.md:45-46].
  - **Reliability scaling (measured vs predicted)**:
    - Mean single-replicate Pearson r: predicted 0.164 → **measured 0.1697** [OBSERVED campaign/workers/brief_W12_gateb_train.md:51].
    - Reliability of 2-replicate mean: predicted 0.282 → **measured 0.2902** [OBSERVED campaign/workers/brief_W12_gateb_train.md:52].
    - Reliability of 4-replicate mean: predicted 0.440 → **measured 0.4504** (direct 2-vs-2 splits: 0.5026, 0.3074, 0.5412; spread reflects estimation noise in r at n = 332) [OBSERVED campaign/workers/brief_W12_gateb_train.md:53, 55-58].
    - Mean single-replicate Spearman ρ = **0.1951** [OBSERVED campaign/workers/brief_W12_gateb_train.md:60].
  - **Label movement (332 points, band 0.166)**:
    - 2-seed mean: needed 50, needless 48, ambiguous 234 [OBSERVED campaign/workers/brief_W12_gateb_train.md:64].
    - 4-seed mean: needed 43, needless 43, ambiguous 246 [OBSERVED campaign/workers/brief_W12_gateb_train.md:65].
    - Agreement: 276/332 = **0.8313**; outright needed ↔ needless flips = **0** [OBSERVED campaign/workers/brief_W12_gateb_train.md:66].
  - **Substantive reading**: every disagreement is borderline crossing the band, never a sign reversal (noise reduction, not label breakdown) [OBSERVED campaign/workers/brief_W12_gateb_train.md:68-69].
  - **Headline consequence**: 2-replicate f was noise-inflated; at 4 replicates, f_dev falls to **0.130** and **1 − f rises from 0.843 to 0.870** (fixed schedule is *more* wasteful) [OBSERVED campaign/workers/brief_W12_gateb_train.md:70-73].

- [x] **3. `docs/FOLLOWUPS.md`: OPEN entry for fired harmful flag (Task 3)** [OBSERVED campaign/workers/brief_W12_gateb_train.md:74-91, docs/FOLLOWUPS.md:478-490]
  - Documented train harmful = 0.1635 (> 0.15 threshold) and mean Δ = −0.0206 vs dev (0.1417 and +0.0068) [OBSERVED campaign/workers/brief_W12_gateb_train.md:78-79].
  - Recorded consequences: changes H3 reading (active damage), raises review format vs timing question, provides direct evidence for Gate A fallback branch (richer review format). No fix proposed [OBSERVED campaign/workers/brief_W12_gateb_train.md:83-91].

- [x] **4. `docs/FOLLOWUPS.md`: Extend wedged-branch entry with startup rebuild finding (Task 4)** [OBSERVED campaign/workers/brief_W12_gateb_train.md:93-107, docs/FOLLOWUPS.md:469-476]
  - Documented startup rebuild on `--resume` (`branch_counterfactual.py:1099-1100`) [OBSERVED scripts/setup/branch_counterfactual.py:1099-1100].
  - Recorded 2026-09-18 observation where train ×4 startup rebuild wrote empty derived files over 2-seed aggregation, noting that derived files are not safe across differing `--branch-seeds` and empty derived files beside healthy `branch_runs.jsonl` is expected mid-campaign [OBSERVED campaign/workers/brief_W12_gateb_train.md:97-107].

## Owned Files (this unit)

- `campaign/RUNS.md`
- `docs/FOLLOWUPS.md`
- `campaign/workers/STATUS_W_12.md` (this file)
