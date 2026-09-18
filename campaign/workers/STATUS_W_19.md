# STATUS_W_19

**Task:** brief_W19_delta — is the frozen δ = 0.166 too conservative for a four-replicate Δ?
**Status:** DONE (2026-09-18)
**Ownership:** only `campaign/workers/scratch_W19/`, `campaign/workers/W19_DELTA.md`, this file.

## What was done

- Script `campaign/workers/scratch_W19/analyze_delta.py` (+ `check_frozen.py` anchor check).
- Run in PBS jobs **25422390.aqua** (NameError — `report` def lost in an edit; fixed),
  **25422402.aqua** (full run, verbatim output in `scratch_W19/w19_out.txt`),
  **25422408.aqua** (frozen-δ reproduction: n=741, p75=0.166 ✓).
- Report: `campaign/workers/W19_DELTA.md`.

## Headline findings

- Frozen δ reproduced exactly from the 2-replicate single-draw rule → it was calibrated to a
  statistic √2× noisier than the 4-rep Δ being thresholded; CRN r ≈ 0.59–0.68 adds more slack.
- Derived floor (same rule on the 4-rep-scale null): **δ = 0.100 (train)**, 0.200 (dev).
- Train labels at δ = 0.100: needed 54 / needless 67 / ambiguous 276, **f = 0.169**.
- Half-agreement at 0.100 = 0.6851 vs 0.7229 at 0.166. **Reference 0.8388 did NOT reproduce**
  — flag for whoever owns that number.

## Resume state

Nothing pending. No production code touched, nothing committed, no `/scratch` writes,
zero planner calls, no GPU. If resumed: everything needed is in the three scratch files.

## Objections / notes

- Train (0.100) vs dev (0.200) derived floors differ by 2×; any δ amendment decision must
  pick which split defines the rule. Stated in report §7.5.
- Script printed the TRAIN block twice (identical output; cosmetic bug in driver, noted in
  report caveats).
