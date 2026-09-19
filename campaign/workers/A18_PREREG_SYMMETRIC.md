# A18 (U-B1PRE2) — Symmetric `suppress_next` B1 Prereg Correction Report

- **Worker:** A18 / U-B1PRE2
- **Date:** 2026-09-19
- **Owned files:** `docs/prereg_b1_pilot.md`, `campaign/workers/A18_PREREG_SYMMETRIC.md`, `campaign/workers/STATUS_A_18.md`
- **Untouched files:** `src/`, `configs/`, `scripts/`, `campaign/RUNS.md`, all other `docs/` files. Zero git operations, zero rollout/GPU jobs, zero planner calls.

---

## 1. Summary of Edits Applied to `docs/prereg_b1_pilot.md`

All edits were surgical updates addressing the symmetric `suppress_next` correction implemented in A17 [OBSERVED campaign/workers/STATUS_A_17.md:12-32]:

1. **Status Line (`docs/prereg_b1_pilot.md:3`)**: Updated the status line to note that the document was corrected on 2026-09-19 for the symmetric `suppress_next` fix prior to any data generation.
2. **§1 Mechanism & Estimand (`docs/prereg_b1_pilot.md:22-31`)**:
   - Updated description of `--untreated-mode suppress_next` to state symmetric suppression across **both** arms: focal tick at `s` and the next scheduled tick `t` are skipped in both arms (`skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT`) [OBSERVED scripts/setup/branch_counterfactual.py:82-92, 1022].
   - Replaced single specification clash with two specification clashes in order: (a) residual later reviews (`n_later = 0` not guaranteed by construction; handled via manipulation check), and (b) arm-asymmetry defect (A8 untreated-only suppression confounded intervention with review advantage; fixed in code by A17) [OBSERVED campaign/workers/STATUS_A_17.md:17-32].
   - Updated the estimand quote verbatim to match `_ESTIMAND_SUPPRESS_NEXT` [OBSERVED scripts/setup/branch_counterfactual.py:88-91].
3. **§7 Item 4 Manipulation Check (`docs/prereg_b1_pilot.md:144-151`)**:
   - Expanded manipulation check to evaluate **both** arms separately to verify that the treated arm also skipped tick `t` and that later-review counts are equal in distribution between arms.
   - Added the residual `n_later` measurement benchmark from A17 on the frozen 200 points (median 0.0, mean 0.235 point-level; median 0.0, mean 0.47125 replicate-level; median 5 remaining ticks if run to max_steps=40) [OBSERVED campaign/workers/STATUS_A_17.md:130-156].
   - Explicitly noted the length-held-fixed proxy caveat [INFERRED].
4. **§8 Cost Projection (`docs/prereg_b1_pilot.md:187`)**: Adjusted the sentence explaining that `suppress_next` can only reduce live reviews relative to J6 in **both** arms (since `t` is suppressed in both), making 6,118 an even more conservative expectation [INFERRED]. All numerical figures (6,118 expected calls and 10,000 hard cap) remain strictly unchanged.
5. **§12 Item 1 Threats (`docs/prereg_b1_pilot.md:243`)**: Updated note to reflect that `suppress_next` suppresses one future scheduled tick (`t`) in both arms, retaining the point that `n_later = 0` is not guaranteed by construction [OBSERVED scripts/setup/branch_counterfactual.py:82-92, 1022].

---

## 2. Quoted Corrections

### §1 Paragraph & Specification Clashes (Quoted)

```markdown
`--untreated-mode suppress_next` (A8, corrected to symmetric suppression by A17) suppresses, in **both** arms, the scheduled tick at `s` **and the next scheduled tick the schedule would actually have fired after `s`** (`skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT`) [OBSERVED scripts/setup/branch_counterfactual.py:82-92, 1022] [OBSERVED campaign/workers/STATUS_A_17.md:24-29]. The treated arm injects the correction at `s` and skips the next scheduled tick; the untreated arm omits the review at `s` and skips the next scheduled tick. Later ticks after that stay live in both arms.

⚠ **Specification clashes, recorded rather than silently fixed.**
1. **Residual later reviews:** The original unit brief states that `suppress_next` makes `n_later = 0` **by construction**. The frozen estimand string and code do not do that: one future tick is suppressed, but later reviews after that suppressed tick remain live [OBSERVED scripts/setup/branch_counterfactual.py:82-92]. This pilot runs the mode as implemented. `n_later` on both arms is a **manipulation check**, reported as secondary, not a gate. A result in which the first substitute is gone but later ticks still fire is still the experiment that was built.
2. **Arm-asymmetry defect (fixed in code):** The initial A8 implementation suppressed the next review in the untreated arm only, leaving the treated arm with an extra review. Because reviews were measured at +27.19 pp TGC in J8a (CI [16.67, 37.72]) [OBSERVED campaign/workers/A15_J8A.md], an asymmetric design confounded the intervention with an extra review. A17 fixed this specification defect in code by making suppression symmetric across both arms [OBSERVED scripts/setup/branch_counterfactual.py:1022] [OBSERVED campaign/workers/STATUS_A_17.md:17-32].

The estimand this job actually runs, copied from the frozen strings:

> `Q(policy with intervention i present) - Q(policy with intervention i omitted); the next scheduled review after s is suppressed in both arms; later reviews after that stay live`
> [OBSERVED scripts/setup/branch_counterfactual.py:88-91]
```

### §7 Item 4 Manipulation Check (Quoted)

```markdown
4. **Manipulation check, `n_later` (both arms).** For each complete point and condition (treated and untreated), `n_later` is the count of `event_type == "intervention"` events with `source == "live_policy"` and `step > s` on each replicate, then the median across the four replicates for that arm, following W-25 [OBSERVED campaign/workers/W25_SUBSTITUTION.md:21] [OBSERVED scripts/setup/branch_counterfactual.py:520-524]. Under symmetric suppression, the manipulation check must also verify that the **treated** arm lost its tick at `t` (guarding against a regression of the arm-asymmetry bug). Report later-review counts and histograms for treated and untreated arms **separately**; they should be equal in distribution. Report the fraction with median 0 and the fraction with *all four* replicates at 0 for each arm. The brief’s “zero by construction” claim is tested here; it is not assumed. If median `n_later` is not materially lower than the paired J6 `schedule_live` value on the overlapping complete points, or if the two arms diverge in later review counts, the instrument did not behave as intended and the primary tests are still reported but are not a clean test of substitution.

   **Residual `n_later` benchmark (frozen 200-point list):**
   From the frozen 200-point list and J6 untreated replicates [OBSERVED campaign/workers/STATUS_A_17.md:130-156]:
   - Point-level median of `max(0, n_later − 1)` on the frozen 200: **median 0.0**, mean 0.235, min 0, max 4; 161/200 points at 0.
   - Replicate level (800 untreated rows): **median 0.0**, mean 0.47125; 607/800 at 0.
   - **If** a branch ran to `max_steps = 40`, the live schedule after `t` still has median **5** remaining ticks (mean 4.51, 174/200 points at 3+) — that is the policy remainder, not what J6 lived long enough to receive.
   - ⚠ **Length-held-fixed proxy caveat:** This quantity is computed from J6 `schedule_live` replicates [INFERRED]. If skipping `t` changes when an episode ends, the residual changes with it. No `suppress_next` data exists yet.
```

---

## 3. Invariance Confirmation

The following elements were strictly **unmodified** and remain byte-for-byte identical to their prior specification:
- **Primary hypotheses (B1a and B1b)**: Unchanged (§5) [OBSERVED docs/prereg_b1_pilot.md:95-121].
- **Decision rule**: Unchanged (§6), including the 3 branches (both hold, neither holds, exactly one holds -> inconclusive) [OBSERVED docs/prereg_b1_pilot.md:123-134].
- **δ**: Unchanged at **0.166** (§2, §5, §12) [OBSERVED docs/prereg_b1_pilot.md:43, 103].
- **Permutations**: Unchanged at **10,000** paired sign-flips with RNG seed `20260918` (§2, §5) [OBSERVED docs/prereg_b1_pilot.md:46-47, 117-119].
- **Hard planner call cap**: Unchanged at **10,000** total calls (§8, §13) [OBSERVED docs/prereg_b1_pilot.md:189-195, 285].
- **Expected spend estimate**: Unchanged at **6,118** calls (§8) [OBSERVED docs/prereg_b1_pilot.md:187].
- **Primary population definition**: Unchanged (`complete` and `mean(untreated) < 1.000`) (§4) [OBSERVED docs/prereg_b1_pilot.md:81-93].
- **Frozen 200-point list & Appendix**: Unchanged (SHA-256 `4ec6fa2733a141da4335240c215b605ff466e2d85a0a0f7ce55179a6ef5b1017`) (§3, Appendix) [OBSERVED docs/prereg_b1_pilot.md:73, 292-498].
- **Falsifier & Licensing**: Unchanged (§10, §11) [OBSERVED docs/prereg_b1_pilot.md:208-238].

---

## 4. Assessment of Remaining Issues

No structural defects or inconsistencies remain in `docs/prereg_b1_pilot.md`.
The document accurately reflects:
1. The codebase's symmetric suppression semantics (`skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT`) [OBSERVED scripts/setup/branch_counterfactual.py:1022].
2. The exact estimand string in the codebase [OBSERVED scripts/setup/branch_counterfactual.py:88-91].
3. The empirical baseline residual later reviews on the frozen 200 points [OBSERVED campaign/workers/STATUS_A_17.md:130-156].
4. The prospective, falsifiable criteria for evaluating the substitution mechanism in B1.
