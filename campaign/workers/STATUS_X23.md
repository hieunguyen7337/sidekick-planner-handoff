# STATUS X23 — bibliography citation-integrity audit

The network gate passed: arXiv 2608.24358 returned **“The Handoff Tax: Continuing Non-Native Trajectories in LLM Agents.”** [OBSERVED https://arxiv.org/abs/2608.24358]

All 59 bibliography entries were audited from live records; all 58 `include=yes` screening keys are represented. [OBSERVED docs/lit/bibliography_audit.csv:1-60] [OBSERVED docs/lit/screening_log.csv:1-74]

## Verdicts

`OK=30`, `MISMATCH=29`, `UNRESOLVED=0`, `UNVERIFIABLE=0`. [OBSERVED docs/lit/bibliography_audit.csv:2-60]

## Complete MISMATCH list — real titles

- `guided_opd_2026` — “On-Policy Distillation with Curriculum Turn-level Guidance for Multi-turn Agents.” [OBSERVED docs/lit/bibliography_audit.csv:5]
- `early_exit_lu_2025` — “Runaway is Ashamed, But Helpful: On the Early-Exit Behavior of Large Language Model-based Agents in Embodied Environments.” [OBSERVED docs/lit/bibliography_audit.csv:7]
- `isp_2024` — “Interactive Speculative Planning: Enhance Agent Efficiency through Co-design of System and User Interface.” [OBSERVED docs/lit/bibliography_audit.csv:8]
- `dsp_guan_2025` — “Dynamic Speculative Agent Planning.” [OBSERVED docs/lit/bibliography_audit.csv:9]
- `agentic_routing_2026` — “Agentic Routing: The Harness-Native Data Flywheel.” [OBSERVED docs/lit/bibliography_audit.csv:11]
- `mtrouter_2026` — “MTRouter: Cost-Aware Multi-Turn LLM Routing with History-Model Joint Embeddings.” [OBSERVED docs/lit/bibliography_audit.csv:12]
- `agent_distillation_2025` — “Distilling LLM Agent into Small Models with Retrieval and Code Tools.” [OBSERVED docs/lit/bibliography_audit.csv:18]
- `slm_need_strong_verifiers_2024` — “Small Language Models Need Strong Verifiers to Self-Correct Reasoning.” [OBSERVED docs/lit/bibliography_audit.csv:21]
- `where_agents_fail_2025` — “Where LLM Agents Fail and How They can Learn From Failures.” [OBSERVED docs/lit/bibliography_audit.csv:22]
- `long_horizon_mirage_2026` — “The Long-Horizon Task Mirage? Diagnosing Where and Why Agentic Systems Break.” [OBSERVED docs/lit/bibliography_audit.csv:23]
- `rfcl_2024` — “Reverse Forward Curriculum Learning for Extreme Sample and Demonstration Efficiency in Reinforcement Learning” (arXiv:2405.03379; no OpenReview venue record established). [OBSERVED https://arxiv.org/abs/2405.03379]
- `loop_2025` — “Reinforcement Learning for Long-Horizon Interactive LLM Agents.” [OBSERVED docs/lit/bibliography_audit.csv:29]
- `canopy_2026` — “Explore More, Drift Less: Outcome-Only Reinforcement Learning Can Suffice for Long-Horizon Interactive Agents.” [OBSERVED docs/lit/bibliography_audit.csv:30]
- `ace_2026` — “Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models.” [OBSERVED docs/lit/bibliography_audit.csv:31]
- `early_experience_2026` — “Agent Learning via Early Experience.” [OBSERVED docs/lit/bibliography_audit.csv:32]
- `appworld_ul_2026` — “AppWorld-UL: Benchmarking Diverse Agent-User Interactions for Tool-Use.” [OBSERVED docs/lit/bibliography_audit.csv:33]
- `coevolve_2026` — “CoEvolve: Training LLM Agents via Agent-Data Mutual Evolution.” [OBSERVED docs/lit/bibliography_audit.csv:37]
- `three_roles_2026` — “Three Roles, One Model: Role Orchestration at Inference Time to Close the Performance Gap Between Small and Large Agents.” [OBSERVED docs/lit/bibliography_audit.csv:38]
- `r2v_agent_2026` — “R2V Agent: Teaching SLMs When to Ask for Help.” [OBSERVED docs/lit/bibliography_audit.csv:39]
- `envscaler_2026` — “EnvScaler: Scaling Tool-Interactive Environments for LLM Agent via Programmatic Synthesis.” [OBSERVED docs/lit/bibliography_audit.csv:42]
- `granite_4_2_ibm_2026` — “Granite-4.2-8B.” [OBSERVED docs/lit/bibliography_audit.csv:45]
- `gpt_oss_openai_2025` — “gpt-oss-120b & gpt-oss-20b Model Card.” [OBSERVED docs/lit/bibliography_audit.csv:46]
- `gpt_5_6_luna_2026` — “kecaipan capybara” (leaderboard submission). [OBSERVED docs/lit/bibliography_audit.csv:47]
- `agentflan_chen_2024` — “Agent-FLAN: Designing Data and Methods of Effective Agent Tuning for Large Language Models.” [OBSERVED docs/lit/bibliography_audit.csv:51]
- `cascade_cost_valkanas_2025` — “Dynamic Pricing in High-Speed Railways Using Multi-Agent Reinforcement Learning.” [OBSERVED docs/lit/bibliography_audit.csv:53]
- `cascading_aggregating_kotte_2026` — “Lifted Relational Probabilistic Inference via Implicit Learning.” [OBSERVED docs/lit/bibliography_audit.csv:54]
- `cld_kim_2024` — “Large Language Models: A Survey.” [OBSERVED docs/lit/bibliography_audit.csv:56]
- `critic_gou_2023` — “CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing.” [OBSERVED docs/lit/bibliography_audit.csv:58]
- `sequential_deferral_charusaie_2024` — “Going beyond Compositions, DDPMs Can Produce Zero-Shot Interpolations.” [OBSERVED docs/lit/bibliography_audit.csv:60]

`UNRESOLVED`: none. [OBSERVED docs/lit/bibliography_audit.csv:2-60]

## Risk and year checks

The bibliography contains 20 `and others` entries. [OBSERVED paper/bibliography.bib:1]

Claimed year differs from record year for: `isp_2024` 2025→2024; `llms_cannot_self_correct_huang_2024` 2024→2023; `ace_2026` 2026→2025; `early_experience_2026` 2026→2025; `routellm_ong_2024` 2025→2024; `speculative_decoding_leviathan_2023` 2023→2022; `critic_gou_2023` 2024→2023. [OBSERVED docs/lit/bibliography_audit.csv:8] [OBSERVED docs/lit/bibliography_audit.csv:19] [OBSERVED docs/lit/bibliography_audit.csv:31-32] [OBSERVED docs/lit/bibliography_audit.csv:41] [OBSERVED docs/lit/bibliography_audit.csv:48] [OBSERVED docs/lit/bibliography_audit.csv:58]

Audit table: `docs/lit/bibliography_audit.csv`. [OBSERVED docs/lit/bibliography_audit.csv:1-60]

## Validation output

```text
60 docs/lit/bibliography_audit.csv
30
29
0
0
20
```

[OBSERVED docs/lit/bibliography_audit.csv:1-60] [OBSERVED paper/bibliography.bib:1]
