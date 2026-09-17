# STATUS W-6 — align documentation with reordered campaign (DOCS ONLY)

**Unit:** W-6. **Docs only under `docs/`. No code, no configs, no PBS, no git commits.**
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
**Date:** 2026-09-17

## Deliverables & Resume State

- [x] **1. `docs/prereg_v1.md`**: Restructured with status DRAFT.
  - Primary endpoint: H2 conjunctive (3 clauses verbatim from RUNS.md:1420-1424; 504 paired comparisons, one-sided 95% paired bootstrap, 10k resamples) [OBSERVED docs/prereg_v1.md:28-34, campaign/RUNS.md:1418-1428].
  - Why conjunctive explanation included [OBSERVED docs/prereg_v1.md:36-39].
  - Secondary hypotheses: H1 (non-inferiority vs `planner_alone` at ε = 7 pp with $FCD_{\text{tokens}} > 0$), H4 (`sidekick` vs `router_seq`), H3 (dev AUROC/ECE/needless-ask), dev needed-fraction $f$ [OBSERVED docs/prereg_v1.md:41-52].
  - Parameters frozen at J9: $\tau^*$, router $\tau^*$, $k_{\text{matched}}$ rule (*$k \in \{3, 5, 10\}$ nearest dev calls/ep, interpolating to 7 on tie*), ASK template string, oracle label rule, and arm list — each resolved on dev and never revisited [OBSERVED docs/prereg_v1.md:9-20].
  - Falsification criteria verbatim from RUNS.md:1434-1436 [OBSERVED docs/prereg_v1.md:58-60].
  - Threats to validity: added verifier sampling bias on timer-tick states and train-split intervention optimism [OBSERVED docs/prereg_v1.md:237-246].
  - N = 3 seeds, ε = 7 pp with power analysis citations preserved [OBSERVED docs/prereg_v1.md:73-96].

- [x] **2. `docs/HEAVY_JOBS.md` and `docs/PLAN.md` (§5, §7, §8, §9)**:
  - Re-sequenced to: J4b (dev fixed_k, Gate A) → J6 (counterfactual branches, Gate B) → J5a `sft_b_plus` / J5b `sft_c` → J7 (verifier) → J8 (dev frontier sweep) → J9 (prereg freeze) → J10 (test_normal, once) [OBSERVED docs/HEAVY_JOBS.md:27-36, docs/PLAN.md:291-299].
  - Added superseded/changed notes with date 2026-09-17 and rationales [OBSERVED docs/HEAVY_JOBS.md:16-24, 76-80, 118-124, docs/PLAN.md:322-332].
  - HJ-6 (DPO) marked superseded and dropped; operating points swept by serve-time $P(\text{ASK})$ thresholding [OBSERVED docs/HEAVY_JOBS.md:118-124, docs/PLAN.md:317].
  - Resource and planner-call estimates updated with `[INFERRED]` tags [OBSERVED docs/HEAVY_JOBS.md:65-74, 150-165].

- [x] **3. `docs/FOLLOWUPS.md`**:
  - Closed J4 timer follow-up $\rightarrow$ RESOLVED, citing re-sequencing (branches first, J6 labels feed J5b ASK channel, `sft_b_plus` no-ASK control) and RUNS.md [OBSERVED docs/FOLLOWUPS.md:300-307].
  - Prompt-budget follow-up: Checked `scripts/setup/verify_configs.py:50-68` — frozen pilot allowlist is **not** present in tree; entry correctly left **OPEN** [OBSERVED scripts/setup/verify_configs.py:50-68, docs/FOLLOWUPS.md:316-360].
  - `hash_match` follow-up left OPEN and untouched [OBSERVED docs/FOLLOWUPS.md:275-299].
  - Opened new follow-up: Verifier trained on timer-tick states only may exhibit calibration bias across arbitrary steps [OBSERVED docs/FOLLOWUPS.md:308-315].

## Owned Files (this unit)
- `docs/prereg_v1.md`
- `docs/PLAN.md`
- `docs/HEAVY_JOBS.md`
- `docs/FOLLOWUPS.md`
- `campaign/workers/STATUS_W_6.md` (this file)
