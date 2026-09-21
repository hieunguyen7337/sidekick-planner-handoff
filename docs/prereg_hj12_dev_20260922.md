# Preregistration: HJ-12 Dev Protocol — Channel, Allocation, and Tailoring (2026-09-22)

**Status**: **FROZEN** — Written on dev evidence only, strictly before submitting the first HJ-12 job.  
**Date**: 2026-09-22  
**Study**: Sidekick Proof-of-Concept (IAES) — Milestone HJ-12 Dev Protocol  
**Repository**: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`  
**Prior Frozen Documents**: `docs/prereg_v1.md` (2026-09-16, frozen), `docs/prereg_b1_pilot.md` (2026-09-19, frozen), `docs/prereg_j9_freeze_20260920.md` (2026-09-20, frozen)  

---

## 1. What This Document Is and Scope

This document specifies the dev preregistration protocol for the HJ-12 campaign. It establishes the three core hypotheses (Claims C1, C2, and C3), the arm list, the prefix grid $m$, the primary and secondary metrics, the advance predictions, the validity threats, and the exact decision gates G1 and G2.

### 1.1 Timing and Falsification Discipline
A prediction written after empirical numbers arrive is worth nothing [INFERRED]. This document is committed strictly **before the first HJ-12 batch or interactive job is submitted to PBS** [INFERRED].

### 1.2 Scope and Boundaries
- **Scope**: Dev split only (57 tasks $\times$ 2 seeds = 114 paired episodes per arm) [OBSERVED docs/prereg_j9_freeze_20260920.md:15].
- **Non-amendment**: This document does not amend `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`, or the J9 pre-test freeze (`docs/prereg_j9_freeze_20260920.md`) [INFERRED].
- **Split isolation**: This document does not authorise reading, loading, analyzing, or peeking at any `test_normal` or `test_challenge` data [OBSERVED AGENTS.md: rules §5, §7].
- **No pre-judgement**: This document does not pre-judge any empirical outcome [INFERRED].

---

## 2. The Three Core Claims

Following the finding that the advice channel produces no measurable benefit across both counterfactual and live evaluation once format mismatches are resolved (`campaign/RUNS.md` §11, §12; `docs/FOLLOWUPS.md`), the HJ-12 milestone pivots the communication protocol from natural-language advice to direct action and early episode handoff [INFERRED].

### Claim C1 — Channel (Action vs Advice)
At a matched trigger and call count, a planner that *acts* beats a planner that *advises* [INFERRED].
- **Primary contrast**:
  $$\text{takeover\_fixed\_k\_10} - \text{fixed\_k\_10\_iaware}$$
  evaluated on dev ($n=114$ pairs, task-clustered bootstrap), spending approximately $2.4$ calls per episode [INFERRED].
- **Secondary contrasts**:
  - At $k=3$: $\text{takeover\_fixed\_k\_3} - \text{fixed\_k\_3\_iaware}$ (~$6.8$ calls/ep) [INFERRED].
  - At exception trigger: $\text{takeover\_exception} - \text{advice\_exception}$ [INFERRED].

### Claim C2 — Allocation (Prefix Handoff Frontier)
Quality against hosted-token fraction for the planner-prefix / executor-suffix split bows strictly above the straight line joining `sft_plan` (0% suffix hosted tokens) and `planner_alone` (100% hosted tokens) [INFERRED].
- **Non-inferiority target**: There exists an $m \in \{2, 4, 6, 9\}$ at which the hybrid policy `prefix_handoff(m)` is non-inferior to `planner_alone` within a 7 percentage point margin ($\epsilon = 7\text{ pp}$) while consuming no more than approximately half of `planner_alone`'s non-cached hosted tokens [INFERRED].

### Claim C3 — Tailoring (Suffix-Specialised SFT)
An adapter trained specifically on delegated suffixes (trajectories starting from step $m > 0$ after teacher prefix execution) beats the un-delegated baseline adapter (`sft_b_plus_iaware`) when evaluated across the same split prefix arms [INFERRED]:
$$\text{prefix\_handoff}(m, \text{adapter}=\text{sft\_suffix}) - \text{prefix\_handoff}(m, \text{adapter}=\text{sft\_b\_plus\_iaware}) > 0$$

---

## 3. Metrics and Statistical Protocol

The statistical protocol carries forward the J9 dev freeze decisions without alteration [OBSERVED docs/prereg_j9_freeze_20260920.md:70-132].

### 3.1 Primary and Secondary Metrics
- **Primary Quality Metric**: **`goal_pass_rate`** ($\text{GPR} \in [0.0, 1.0]$, mean fraction of programmatic task requirements satisfied) [OBSERVED docs/prereg_j9_freeze_20260920.md:73-75].
- **Secondary Quality Metric**: **Task Goal Completion (TGC)** ($\text{TGC} \in \{0.0, 1.0\}$) [OBSERVED docs/prereg_j9_freeze_20260920.md:75].
- **Reporting commitment**: **Both `goal_pass_rate` and TGC are reported for every arm, contrast, and population without exception** [OBSERVED docs/prereg_j9_freeze_20260920.md:75, 92].

### 3.2 Non-Inferiority Margin
The non-inferiority margin is frozen at:
$$\epsilon = 7.00\text{ percentage points}$$
[OBSERVED docs/prereg_v1.md:37, docs/prereg_j9_freeze_20260920.md:109-112]. A policy is non-inferior to a comparator if the lower bound of the 95% bootstrap confidence interval of the paired difference satisfies $\text{ci95\_pp}[0] \ge -7.00\text{ pp}$.

### 3.3 Bootstrap Specification
- **Procedure**: Task-clustered paired percentile bootstrap matching the reference implementation in `scripts/setup/hj1_gate.py` (`paired_diff(resample="task")`) [OBSERVED scripts/setup/hj1_gate.py:91-100, 150-242].
- **Resample Unit**: **Task** (clusters of seed pairs resampled together; 57 clusters on dev) [OBSERVED scripts/setup/hj1_gate.py:91-100, 209-212].
- **Resamples**: 10,000 bootstrap iterations [OBSERVED scripts/setup/hj1_gate.py:28].
- **Random Seed**: Fixed at `SEED = 20260915` [OBSERVED scripts/setup/hj1_gate.py:29].

### 3.4 Evaluated Populations
1. **All-Episodes (Headline)**: All initialized episodes ($n=114$). Any run ending in `crash`, `timeout`, `limit`, `parse_error`, or `api_error` scores $0.0$ on both `goal_pass_rate` and TGC [OBSERVED docs/prereg_j9_freeze_20260920.md:231-232].
2. **Survivors**: Contrast computed over pairs where neither run encountered an unrecoverable system crash [OBSERVED campaign/RUNS.md:2238].

---

## 4. Evaluated Arms and the $m$ Grid

### 4.1 The Prefix Grid $m$
The prefix grid evaluates $m \in \{2, 4, 6, 9\}$ replayed planner steps before executor handoff.

**Empirical Justification**:
The grid is derived directly from the step distribution of the frozen planner (`gpt-5.6-luna`) on dev ($n=114$ episodes) [OBSERVED campaign/RUNS.md:75, 400]:
- **Minimum steps**: 5
- **Median steps**: 12
- **Maximum steps**: 25 (under max planner calls bound)

Selecting $m \in \{2, 4, 6, 9\}$ spans the initial setup phase ($m=2$), early interaction ($m=4$), half-way to the median ($m=6$), and the late execution phase ($m=9$), ensuring that the handoff occurs before the vast majority of episodes terminate naturally [INFERRED].

### 4.2 System Arms Summary

| Arm Label | System / Mechanism | Adapter | $m$ / Trigger | Role |
|---|---|---|:---:|---|
| `planner_alone` | Planner acts every step | None (luna) | — | Quality ceiling comparator [OBSERVED campaign/RUNS.md:69] |
| `sft_plan_iaware` | Replayed plan, executor acts | `sft_b_plus_iaware` | $m=0$ | Zero-suffix-token anchor [OBSERVED campaign/RUNS.md:2245] |
| `prefix_m2` | Replay 2 planner steps $\to$ handoff | `sft_b_plus_iaware` | $m=2$ | Allocation curve point |
| `prefix_m4` | Replay 4 planner steps $\to$ handoff | `sft_b_plus_iaware` | $m=4$ | Allocation curve point |
| `prefix_m6` | Replay 6 planner steps $\to$ handoff | `sft_b_plus_iaware` | $m=6$ | Allocation curve point (Gate G1 key) |
| `prefix_m9` | Replay 9 planner steps $\to$ handoff | `sft_b_plus_iaware` | $m=9$ | Allocation curve point |
| `takeover_fixed_k_10` | Periodic review with direct action takeover | `sft_b_plus_iaware` | $k=10$ | Primary C1 channel test arm |
| `fixed_k_10_iaware` | Periodic review with advice | `sft_b_plus_iaware` | $k=10$ | Primary C1 advice comparator |
| `takeover_fixed_k_3` | High-frequency review with action takeover | `sft_b_plus_iaware` | $k=3$ | Secondary C1 channel test arm |
| `fixed_k_3_iaware` | High-frequency review with advice | `sft_b_plus_iaware` | $k=3$ | Secondary C1 advice comparator |
| `prefix_m*_suffix` | Replay $m$ planner steps $\to$ handoff | `sft_suffix` | $m \in \{2,4,6,9\}$ | C3 tailoring evaluation |

---

## 5. Pre-Registered Decision Gates (Verbatim)

### Gate G1 (Verbatim)
> Proceed to the live phase in full if either some $m \le 6$ reaches non-inferiority to `planner_alone`, or the curve is monotone with $\text{prefix\_m6} - \text{sft\_plan} \ge +5\text{ pp}$ `goal_pass`. Otherwise the live phase shrinks to the channel arms only.

### Gate G2 (Verbatim)
> C1 is established if $\text{takeover\_fixed\_k\_10} - \text{fixed\_k\_10\_iaware}$ excludes zero on `goal_pass`. C2 holds in deployable form if `planner_handoff` is non-inferior to `planner_alone` at no more than about half its tokens.

---

## 6. Advance Quantitative Predictions (Falsification Anchor)

To prevent post-hoc rationalisation, the prior subjective probabilities for the key empirical outcomes are registered before submission [INFERRED]:
1. **The prefix allocation curve rises meaningfully** ($\text{prefix\_m6} - \text{sft\_plan} \ge +5\text{ pp}$): **~65% probability** [INFERRED].
2. **Claim C1 excludes zero on `goal_pass` at $k=10$** ($\Delta > 0$, 95% CI lower bound $> 0.00\text{ pp}$): **~40% probability** [INFERRED].
3. **Claim C2 holds in deployable form** (non-inferior within 7 pp of `planner_alone` at $\le 50\%$ non-cached tokens): **~40% probability** [INFERRED].

These probabilities serve as the explicit anchor against which the realised results will be judged [INFERRED].

---

## 7. Threats to Validity and Mitigations

### 7.1 Replay Determinism and State Hash Limitations
- **Threat**: The replay verification mechanism compares `snapshot_hash`, which is computed as the SHA-256 digest of the observation history (`environment_io`), rather than a full underlying environment database snapshot (`src/sidekick/replay.py:15-20`) [OBSERVED src/sidekick/replay.py:15-20]. Hidden internal state divergence that produces identical visible observation strings cannot be detected [OBSERVED src/sidekick/replay.py:18-20].
- **Mitigation**: The exact visible state divergence rate (`n_mismatches / n_compared`) must be measured and reported for all replayed prefix trajectories [INFERRED].

### 7.2 Short Trajectory Censoring
- **Threat**: For tasks that the planner solved in fewer than $m$ steps (where the planner issued `COMPLETE` at step $t \le m$), replaying $m$ steps replays the entire solved trajectory. The executor never receives a handoff and the episode automatically records the planner's outcome [INFERRED].
- **Mitigation**: Alongside the all-episodes headline population, the study will explicitly compute and report metrics for the **`handoff_occurred` population** (restricting to episodes where actual executor execution occurred post-step $m$) [INFERRED].

### 7.3 Rationale for Comparator Shift (Claim C2 vs Claim F1)
- **Threat**: In Claim F1 (J9 freeze), the registered comparator was `fixed_k(k_matched)` [OBSERVED docs/prereg_j9_freeze_20260920.md:46-58]. In Claim C2, the primary comparator is changed to `planner_alone` [INFERRED].
- **Rationale**: The scientific question investigated has fundamentally changed:
  - Claim F1 asked whether an executor could match periodic expert advice while using fewer calls [OBSERVED docs/prereg_j9_freeze_20260920.md:49-50].
  - Claim C2 asks whether early planner execution followed by executor handoff can match the full standalone capability of the hosted planner itself at a fraction of the cost [INFERRED].
- **Commitment**: Claim F1 continues to be tracked and reported exactly as registered under the J9 freeze, ensuring no historical comparisons are obscured [INFERRED].

---

## 8. Research Hygiene Commitments

1. **Immutable Logs**: Raw execution event logs under `data/raw/` and `/scratch/` are append-only and will never be deleted, truncated, or modified [OBSERVED AGENTS.md: rules §7].
2. **Deterministic Token Accounting**: Token usage for replayed prefixes is logged under `replayed_planner_tokens` and excludes `cached_input_tokens` [OBSERVED campaign/briefs/SEAM_CONTRACT.md:135-139].
3. **Zero Peeking on Test**: All milestone HJ-12 explorations, adapter evaluations, and threshold choices are confined strictly to dev. No test split (`test_normal`, `test_challenge`) will be evaluated during this milestone [OBSERVED AGENTS.md: rules §5, §7].
