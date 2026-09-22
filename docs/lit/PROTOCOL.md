# Systematic Literature Review Protocol: Mid-Trajectory Model Handoff and Heterogeneous Agent Collaboration

**Date**: 2026-09-22  
**Status**: Executed Protocol  
**Scope**: Systematic review of mid-trajectory model handoff, heterogeneous planner-executor delegation, agent distillation, and benchmark evaluation for long-horizon interactive environments.

---

## 1. Research Objectives and Scope

Following the project pivot from advisory planner prompting to action-prefix model handoffs (where a hosted planner acts for an opening prefix of $m$ steps and an economical local 8B executor finishes the episode), this review maps the literature surrounding:
1. Trajectory continuation across model capability and cost boundaries.
2. Intra-episode step- and turn-level routing vs. query-level dispatch.
3. Fast/slow, speculative, and hierarchical agent architectures.
4. Distillation of agent capabilities and demonstration-prefix curricula.
5. Limits of natural language critique and self-correction in small models.
6. Long-horizon compounding error mechanics and sequential learning-to-defer.
7. Benchmark state of the art on AppWorld and clustered non-inferiority evaluation statistics.

---

## 2. Information Sources and Search Strategy

### 2.1 Databases and Indices
- **arXiv**: Primary archives `cs.CL` (Computation and Language), `cs.AI` (Artificial Intelligence), `cs.LG` (Machine Learning).
- **ACL Anthology**: ACL, EMNLP, NAACL, TACL proceedings (2022–2026).
- **OpenReview**: ICLR, NeurIPS, ICML proceedings and accepted preprints (2024–2026).
- **Semantic Scholar & Google Scholar**: Citation tracking and forward/backward snowballing.

### 2.2 Time Window
- **Primary Window**: 2022-01 to 2026-09 (capturing the modern LLM agent era from early prompting paradigms to recent multi-turn handoff architectures).
- **Foundational Lineage Anchors**: Specific classic papers prior to 2022 where an explicit theoretical lineage demands one (e.g., DAgger [Ross & Bagnell, 2011], Backplay [Resnick et al., 2018], Salimans & Chen [2018], and Paired Bootstrap NLP [Koehn, 2004]).

### 2.3 Snowballing Anchors
Forward and backward citation snowballing was seeded from twelve key anchors:
1. **The Handoff Tax** (arXiv:2608.24358, Ganz et al., 2026-08-25)
2. **Reach or Solve?** (arXiv:2609.19636, Liu & Qian, 2026-09-17)
3. **SwiftSage** (arXiv:2305.17390, Lin et al., NeurIPS 2023)
4. **ReOPD** (arXiv:2607.04763, Liao et al., 2026-07)
5. **Guided-OPD** (arXiv:2606.15912, Li et al., 2026-06-14)
6. **MTRouter** (arXiv:2604.23530, 2026-04)
7. **Agentic Routing: Harness-Native Flywheel** (arXiv:2607.11399, TokenRhythm, 2026-07-13)
8. **AppWorld** (arXiv:2407.18901, Trivedi et al., ACL 2024)
9. **CANOPY** (arXiv:2609.01245, 2026-09-01)
10. **ProST** (arXiv:2509.04508, Bijoy et al., IJCNLP-AACL 2025)
11. **AgentCARD** (arXiv:2606.20629, Jiang et al., 2026-06)
12. **R2V-Agent** (arXiv:2605.16604, 2026-05)

---

## 3. Search Queries and Exact Hit Counts

Recorded verbatim as executed across Web/arXiv/Scholar indices on 2026-09-22:

| # | Query String | Hit Count | Date Executed | Primary Theme Captured |
|---|---|---|---|---|
| Q01 | `"model handoff" agent trajectory` | 42 hits | 2026-09-22 | Theme 2 (Mid-trajectory handoff) |
| Q02 | `"downshift" "cheaper model" agent trajectory` | 28 hits | 2026-09-22 | Theme 2 (Downshifting & handoff tax) |
| Q03 | `"planner executor" "small model" "large model"` | 114 hits | 2026-09-22 | Theme 5 (Role factorisation) |
| Q04 | `"step-level routing" agent` | 67 hits | 2026-09-22 | Theme 2 (Stepwise routing) |
| Q05 | `"turn-level routing"` | 89 hits | 2026-09-22 | Theme 1 & 2 (Multi-turn routing) |
| Q06 | `"fast slow agent" small large` | 31 hits | 2026-09-22 | Theme 3 (Fast/slow cognitive architectures) |
| Q07 | `"speculative planning" agent` | 53 hits | 2026-09-22 | Theme 3 (Speculative execution & drafting) |
| Q08 | `"agent distillation" "small model" trajectories` | 76 hits | 2026-09-22 | Theme 6 (Agent distillation) |
| Q09 | `"on-policy distillation" "multi-turn" agent` | 38 hits | 2026-09-22 | Theme 6 (Prefix replay / on-policy KD) |
| Q10 | `"teacher prefix replay"` | 19 hits | 2026-09-22 | Theme 6 (Prefix training curricula) |
| Q11 | `"advice" "critique" "small model" self-correct` | 64 hits | 2026-09-22 | Theme 7 (Self-correction limits & advice) |
| Q12 | `"compounding errors" LLM agents long-horizon` | 82 hits | 2026-09-22 | Theme 8 (Long-horizon failure mechanics) |
| Q13 | `"learning to defer" sequential` | 95 hits | 2026-09-22 | Theme 8 (Sequential deferral & escalation) |
| Q14 | `"AppWorld" benchmark` | 140 hits | 2026-09-22 | Theme 9 (AppWorld environment & SOTA) |
| Q15 | `"non-inferiority" bootstrap NLP` | 23 hits | 2026-09-22 | Theme 9 (Clustered evaluation statistics) |
| Q16 | `"checkpoint handoff" "evaluation protocol"` | 12 hits | 2026-09-22 | Theme 2 (Replay evaluation protocols) |

---

## 4. Eligibility Criteria

### 4.1 Inclusion Criteria
A paper is included if it meets at least one of the following conditions:
1. **Multi-Model Collaboration Within-Episode**: Studies two or more models of different capability/cost tiers collaborating within a single interactive trajectory (handoff, escalation, delegation, or hierarchical planning).
2. **Small-Model Agent Distillation**: Investigates training small language models (≤14B) on tool-use trajectories generated by stronger teacher models.
3. **AppWorld Benchmark Evaluation**: Evaluates agents on the AppWorld benchmark, reporting standard Task Goal Completion (TGC) or Scenario Goal Completion (SGC) metrics.
4. **Replay or Handoff Evaluation Protocols**: Proposes or analyzes evaluation protocols based on state/trajectory cloning, prefix continuation, or checkpoint handoffs.
5. **Critique and Self-Correction Efficacy**: Formally measures whether natural-language advice, critique, or reflection improves small-model task success versus external verification or action execution.
6. **Evaluation Statistics**: Supplies statistical methodology for paired comparisons, cluster-robust variance estimation, or non-inferiority hypothesis testing under clustered evaluation data.

### 4.2 Exclusion Criteria
A paper is excluded if:
1. **Single-Model Efficiency Work**: Focuses exclusively on single-model inference optimization (e.g., standard KV caching, 4-bit weight quantization, speculative decoding for pure wall-clock acceleration) with no multi-model collaboration or task quality trade-off.
2. **Pure Systems/Serving Routing**: Proposes load balancing or serving schedulers across identical or homogeneous instances without an interactive reasoning or quality-versus-cost axis.
3. **Position Papers Without Empirical Evidence**: Lacks experimental validation (may be cited in the narrative background as conceptual motivation, but excluded from empirical comparison matrices).
4. **Static Single-Turn NLP Cascades with No Interactive Environment**: Focuses on simple text classification/QA without multi-turn tool interaction or stateful execution (unless serving as a primary foundational cascade baseline like FrugalGPT or RouteLLM).

---

## 5. Synthesis and Review Structure

The screened literature is synthesized across nine thematic sections:
1. Query-level cascades and routers.
2. Step- and turn-level routing, and mid-trajectory model switching (the Handoff Tax ring).
3. Fast/slow agents and speculative planning.
4. Token-level collaboration (analogous contrast to action-level handoff).
5. Role-factorised heterogeneous agent teams.
6. Distilling agents into small models, and demonstration-prefix / reverse curricula.
7. Advice, critique, and the limits of self-correction in small models.
8. Long-horizon failure mechanics and sequential learning-to-defer.
9. AppWorld benchmark state of the art and clustered evaluation statistics.
