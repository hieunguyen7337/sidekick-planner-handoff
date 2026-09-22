# External Comparison: Published AppWorld Benchmark Results vs. Our Internal Dev Arms

**Date**: 2026-09-23  
**Status**: Landscape reference table for context only.  
**Grounding Convention**: Every factual claim is tagged `[OBSERVED <path-or-url>]` or `[INFERRED]`. Published values trace exclusively to `campaign/workers/lit/extracts_20260922.md` §J.

---

## 1. External Comparison Table

| Model / System | Scaffold / Framework | Split | TGC (%) | SGC (%) | Notes / Setting |
|---|---|---|---|---|---|
| **Published Baselines (Trivedi et al., 2024)** | | | | | |
| GPT-4o | ReAct (max 100 calls) | test_normal | 48.8 | 32.1 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:271-272`] |
| GPT-4o | ReAct (max 100 calls) | test_challenge | 30.2 | 13.0 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:271-272`] |
| GPT-4-Turbo | ReAct (max 100 calls) | test_normal | 26.8 | 12.5 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:272-273`] |
| GPT-4-Turbo | ReAct (max 100 calls) | test_challenge | 17.5 | 5.8 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:272-273`] |
| LLaMA-3 (70B) | FullCodeRefl (5 retrials) | test_normal | 24.4 | 17.9 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:273-274`] |
| LLaMA-3 (70B) | FullCodeRefl (5 retrials) | test_challenge | 7.0 | 4.3 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:273-274`] |
| DeepSeek-Coder-33B-Instruct | ReAct (max 100 calls) | test_normal | 7.1 | 1.8 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:274`] |
| DeepSeek-Coder-33B-Instruct | ReAct (max 100 calls) | test_challenge | 2.9 | 0.7 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:274`] |
| Mistral-7B | CodeAct (10 turns) | test_normal | 0.0 | 0.0 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:274`] |
| Mistral-7B | CodeAct (10 turns) | test_challenge | 0.0 | 0.0 | Trivedi et al. (2024) [OBSERVED `campaign/workers/lit/extracts_20260922.md:274`] |
| **Published SOTA / Recent Work** | | | | | |
| LOOP (32B) | Value-network-free PPO | NOT ESTABLISHED | ~71 | NOT ESTABLISHED | Outperforms OpenAI o1 by 9 pp [OBSERVED `campaign/workers/lit/extracts_20260922.md:278-280`] |
| CANOPY (Qwen3-14B) | Coverage-Anchored On-Policy RL | test_normal | 86.9 | NOT ESTABLISHED | Topped public leaderboard Feb 2026 [OBSERVED `campaign/workers/lit/extracts_20260922.md:280-282`] |
| CANOPY (Qwen3-14B) | Coverage-Anchored On-Policy RL | test_challenge | 67.6 | NOT ESTABLISHED | [OBSERVED `campaign/workers/lit/extracts_20260922.md:280-282`] |
| ACE | Evolving Context Playbooks | NOT ESTABLISHED | NOT ESTABLISHED | NOT ESTABLISHED | +17.1% on AppWorld; DeepSeek-V3.1 matches IBM CUGA with GPT-4.1 [OBSERVED `campaign/workers/lit/extracts_20260922.md:282-284`] |
| **Published Leaderboard Anchor** | | | | | |
| `gpt-5.6-luna` | kecaipan capybara scaffold | test_normal | 85.1 | 73.2 | 9.3 mean interactions [OBSERVED `campaign/workers/lit/extracts_20260922.md:288-290`] |
| `gpt-5.6-luna` | kecaipan capybara scaffold | test_challenge | 73.4 | 52.5 | Official leaderboard anchor [OBSERVED `campaign/workers/lit/extracts_20260922.md:288-290`] |
| **Our Measured Internal Arms** | | | | | |
| `planner_alone` (`gpt-5.6-luna`) | Minimal loop harness (25-call cap) | dev (57 tasks × 2 seeds) | 68.4 | NOT ESTABLISHED | 14.4 mean calls; cap ended 11 of 12 limit episodes [OBSERVED `campaign/workers/lit/extracts_20260922.md:290-292`] |
| `sft_plan` | Minimal loop harness | dev (57 tasks × 2 seeds) | NOT ESTABLISHED | NOT ESTABLISHED | Plan-conditioned adapter baseline |
| `executor_alone` | Minimal loop harness | dev (57 tasks × 2 seeds) | NOT ESTABLISHED | NOT ESTABLISHED | Standalone executor baseline |
| Best prefix arm | Minimal loop harness | dev (57 tasks × 2 seeds) | NOT ESTABLISHED | NOT ESTABLISHED | Action-prefix handoff sweep |

---

## 2. Harness and Benchmark Caveat Block

> [!IMPORTANT]
> The figures above are presented strictly for landscape context and are **not directly comparable**. A reader who takes one number away from this file should take away that our figures are internal and paired.

1. **Split & Seed Differences**: Our numbers are measured on **dev** (57 tasks × 2 seeds); published benchmark numbers are evaluated on **test_normal** or **test_challenge**. They are not comparable and we make no leaderboard claim.
2. **Scaffold Divergence**: Our harness is a minimal loop; the published leaderboard entry for the same planner model (`gpt-5.6-luna`) uses a different scaffold ("kecaipan capybara") at 9.3 mean interactions against our 14.4 mean interactions.
3. **Execution Cap Constraint**: Our `planner_alone` ran under a 25-call cap, which ended 11 of its 12 `limit` episodes `[OBSERVED configs/pilot_planner_alone.yaml:25, configs/hj8_fixed_k_3.yaml:39-41]`. An uncapped re-run is in flight; until it lands, the gap between our 68.4 TGC and the published 85.1 is partly a cap artefact and partly scaffold difference, and we do not yet know the split between them.
4. **Data Release Discrepancy**: The pinned AppWorld data release we use ships **90 train / 57 dev**, not the paper's canonical 105 train / 60 dev `[OBSERVED docs/feasibility/g2_appworld.md:30-37]`.
5. **Distinct Problem Formulation**: Methods trained with heavy on-policy RL (such as LOOP and CANOPY) are solving a different problem — maximising a standalone agent's score — and are included solely for landscape comparison. Our work measures a collaboration frontier under a frozen hosted planner with lightweight offline adaptation.
