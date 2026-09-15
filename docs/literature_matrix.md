# Literature Matrix: Intervention-Aware Executor Specialization (Sidekick)

**Date**: 2026-09-15  
**Owner**: Antigravity (`agy`)  
**Scope**: 15 verified primary sources covering the benchmark, executor training on AppWorld, routing & escalation, multi-agent collaboration, and core foundation models.

---

```yaml
- key: appworld_trivedi_2024
  title: "AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents"
  venue_or_arxiv: "ACL 2024 / arXiv:2407.18901"
  year: 2024
  url: "https://arxiv.org/abs/2407.18901"
  what_it_does: |
    Introduces an interactive environment of 9 day-to-day apps (457 APIs, ~100 users) and 750 multi-step coding tasks.
    Evaluates agents with programmatic state-based unit tests and collateral damage checks.
  relation_to_us: |
    Serves as the primary experimental domain and benchmark suite across all 8 systems in this study.
    Provides standard splits (train 105 / dev 60 / test_normal 168 / test_challenge 417).
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2407.18901] 750 tasks across 250 scenarios (train 105, dev 60, test_normal 168, test_challenge 417)."
    - "[OBSERVED https://arxiv.org/abs/2407.18901] GPT-4o achieves ~49% TGC on test_normal (48.8%) and ~30% on test_challenge (29.5%)."
    - "[OBSERVED https://arxiv.org/abs/2407.18901] DeepSeek-Coder-33B-Instruct achieves 7.1% TGC on test_normal."

- key: prost_bijoy_2025
  title: "ProST: Progressive Sub-task Training for Pareto-Optimal Multi-agent Systems Using Small Language Models"
  venue_or_arxiv: "IJCNLP-AACL 2025 / arXiv:2509.04508"
  year: 2025
  url: "https://arxiv.org/abs/2509.04508"
  what_it_does: |
    Applies curriculum-style progressive subtask supervised training to orchestrator, executor, and critic SLMs.
    Analyzes effectiveness-efficiency Pareto trade-offs of heterogeneous SLM allocations in AppWorld.
  relation_to_us: |
    Closest prior precedent for plan-conditioned executor training on AppWorld; motivates our sft_plan control arm.
    Does not learn dynamic escalation to a frozen hosted planner or optimize downstream intervention burden.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2509.04508] Supervised fine-tuning of ~8B models on AppWorld reaches roughly 26.0–33.0% TGC (vs. 1.0–17.0% frozen baseline)."

- key: loop_2025
  title: "Reinforcement Learning for Long-Horizon Interactive LLM Agents"
  venue_or_arxiv: "arXiv:2502.01600"
  year: 2025
  url: "https://arxiv.org/abs/2502.01600"
  what_it_does: |
    Formalizes interactive digital agents as a POMDP and trains them with LOOP, a value-network-free PPO variant.
    Maintains a single LLM copy in memory to enable memory-efficient on-policy RL in AppWorld.
  relation_to_us: |
    Demonstrates upper bound of standalone on-policy RL on AppWorld; we contrast offline collaborative specialization.
    Explains why our PoC focuses on sample-efficient offline LoRA SFT+DPO rather than high-compute online RL.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2502.01600] 32B parameter agent trained with LOOP on AppWorld outperforms OpenAI o1 by 9 percentage points (15% relative improvement)."

- key: canopy_2026
  title: "Explore More, Drift Less: Outcome-Only Reinforcement Learning Can Suffice for Long-Horizon Interactive Agents"
  venue_or_arxiv: "arXiv:2609.01245"
  year: 2026
  url: "https://arxiv.org/abs/2609.01245"
  what_it_does: |
    Introduces Coverage-Anchored On-Policy RL (CANOPY) scaling same-task exploration with action-token KL anchoring.
    Demonstrates that outcome-only RL on small open models can achieve top benchmark scores without auxiliary rewards.
  relation_to_us: |
    Current autonomous open-model state-of-the-art anchor on AppWorld; establishes the ceiling for pure-RL agents.
    Our setting differs by studying asymmetric compute displacement under a frozen hosted planner with offline training.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2609.01245] Qwen3-14B trained with CANOPY achieved 86.9% Test-Normal TGC and 67.6% Test-Challenge TGC on AppWorld (Feb 2026)."
    - "[OBSERVED https://arxiv.org/abs/2609.01245] Lifts Qwen3.5-9B on SWE-bench Verified by 16.6 points."

- key: coevolve_2026
  title: "CoEvolve: Training LLM Agents via Agent-Data Mutual Evolution"
  venue_or_arxiv: "arXiv:2604.15840"
  year: 2026
  url: "https://arxiv.org/abs/2604.15840"
  what_it_does: |
    Extracts forgetting and uncertainty feedback from rollouts to synthesize targeted interactive training tasks.
    Updates the task data distribution in a closed loop to prevent coverage failure in complex environments.
  relation_to_us: |
    Supports our strategy of generating counterfactual continue-branches around observed intervention points.
    Focuses on synthetic task generation for standalone agents rather than planner-subordinate collaboration.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2604.15840] Yields absolute gains of +19.43% (Qwen2.5-7B), +15.58% (Qwen3-4B), and +18.14% (Qwen3-30B-A3B) on AppWorld and BFCL."

- key: three_roles_2026
  title: "Three Roles, One Model: Role Orchestration at Inference Time to Close the Performance Gap Between Small and Large Agents"
  venue_or_arxiv: "arXiv:2604.11465"
  year: 2026
  url: "https://arxiv.org/abs/2604.11465"
  what_it_does: |
    Deploys a frozen Qwen3-8B in three inference roles (summarizer, main agent, isolated code corrector) on 1x 24GB GPU.
    Demonstrates inference-time scaffolding gains on AppWorld without modifying model weights.
  relation_to_us: |
    Empirically pins the frozen capability floor and scaffolding headroom for ~8B models in AppWorld.
    Provides direct context for why an untrained 8B executor cannot reach high TGC alone.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2604.11465] Raw frozen Qwen3-8B achieves 5.4% (FP16) and 3.0% (AWQ) TGC on AppWorld."
    - "[OBSERVED https://arxiv.org/abs/2604.11465] Three-role scaffolding lifts Qwen3-8B to 8.9% (FP16) and 5.9% (AWQ) TGC (difficulty-1 tasks: 15.8% -> 26.3% FP16)."
    - "[OBSERVED https://arxiv.org/abs/2604.11465] Surpasses DeepSeek-Coder 33B Instruct (7.1% TGC) from the original AppWorld benchmark."

- key: r2v_agent_2026
  title: "R2V Agent: Teaching SLMs When to Ask for Help"
  venue_or_arxiv: "arXiv:2605.16604"
  year: 2026
  url: "https://arxiv.org/abs/2605.16604"
  what_it_does: |
    Trains a stable SLM policy (BC + DPO), freezes it, and trains a Brier-calibrated CVaR-constrained step router.
    Escalates to a teacher model when residual failure risk exceeds a threshold on HumanEval+, TextWorld, TerminalBench.
  relation_to_us: |
    Primary baseline for learned step-level escalation; directly instantiates our router_seq control arm.
    We test whether training escalation directly into the executor policy (sidekick) beats this two-stage decoupled pipeline (H4).
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2605.16604] HumanEval+: 94.3% success with 0.60% LLM escalation."
    - "[OBSERVED https://arxiv.org/abs/2605.16604] TextWorld: 98.2% success (from 64.6% SLM-only) at 41.7% escalation."
    - "[OBSERVED https://arxiv.org/abs/2605.16604] TerminalBench: 93.3% success at 33.9% LLM calls (~half heuristic router cost)."

- key: frugalgpt_chen_2023
  title: "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance"
  venue_or_arxiv: "NeurIPS 2023 / arXiv:2305.05176"
  year: 2023
  url: "https://arxiv.org/abs/2305.05176"
  what_it_does: |
    Formulates prompt adaptation, model approximation, and learned LLM cascades to route queries across commercial LLMs.
    Demonstrates large cost reductions on query-level question answering and text generation workloads.
  relation_to_us: |
    Foundational conceptual predecessor for multi-LLM cost optimization.
    Contrasts query-level pre-execution routing against our interactive, intra-episode step-level escalation.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2305.05176] Matches GPT-4 performance with up to 98% cost reduction or improves accuracy by 4% at matched cost."

- key: routellm_ong_2024
  title: "RouteLLM: Learning to Route LLMs with Preference Data"
  venue_or_arxiv: "ICLR 2025 / arXiv:2406.18665"
  year: 2024
  url: "https://arxiv.org/abs/2406.18665"
  what_it_does: |
    Trains preference-based routing models to direct queries between strong and weak LLMs.
    Shows router transferability across different model pairs at test time.
  relation_to_us: |
    Standard baseline for query-level routing based on preference learning.
    Highlights the limitation of query routing in interactive agent tasks where difficulty emerges during execution.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2406.18665] Reduces inference costs by over 2x (50%+ savings) without compromising response quality."

- key: envscaler_2026
  title: "EnvScaler: Scaling Tool-Interactive Environments for LLM Agent via Programmatic Synthesis"
  venue_or_arxiv: "arXiv:2601.05808"
  year: 2026
  url: "https://arxiv.org/abs/2601.05808"
  what_it_does: |
    Programmatically synthesizes tool-interactive environment skeletons (SkelBuilder) and validated scenarios (ScenGenerator).
    Demonstrates SFT and RL sample-efficiency gains on Qwen3 models across multi-turn tool benchmarks.
  relation_to_us: |
    Validates synthetic interactive data generation for agent post-training; supports our counterfactual branch curation.
    Operates on standalone agent training rather than asymmetric planner-executor delegation.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2601.05808] Programmatically synthesizes 191 environments and ~7,000 scenarios for tool-agent SFT and RL."

- key: agentcard_jiang_2026
  title: "Specialize Roles, Mix Deployments: Pushing the Cost-Accuracy Frontier of LLM Agent Teams"
  venue_or_arxiv: "arXiv:2606.20629"
  year: 2026
  url: "https://arxiv.org/abs/2606.20629"
  what_it_does: |
    Evaluates multi-role agent teams (planner, executor, verifier) across API, self-hosted, and hybrid deployments.
    Uses Shapley value analysis to diagnose whether a domain is planner-bottlenecked or executor-bottlenecked.
  relation_to_us: |
    Establishes that heterogeneous agent teams dominate the cost-accuracy Pareto frontier across domains.
    Provides the empirical foundation for our asymmetric architecture where a strong planner directs a cheap executor.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2606.20629] Heterogeneous teams improve accuracy by up to 44% over cost-equivalent homogeneous teams, or match strongest homogeneous teams at up to 12x lower per-task cost."

- key: coda_liu_2025
  title: "CoDA: A Context-Decoupled Hierarchical Agent with Reinforcement Learning"
  venue_or_arxiv: "arXiv:2512.12716"
  year: 2025
  url: "https://arxiv.org/abs/2512.12716"
  what_it_does: |
    Decouples strategic planner context from ephemeral executor tool-workspace using a single shared LLM backbone.
    Trains planner and executor roles jointly with Planner-Executor Co-Optimization (PECO) trajectory RL.
  relation_to_us: |
    Demonstrates that context decoupling prevents context explosion in long-horizon interactive tasks.
    Differs because CoDA uses a single shared backbone, whereas Sidekick pairs a frozen hosted planner with an adapted SLM.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2512.12716] Demonstrates robust multi-hop reasoning in long-horizon settings where unified single-context agents degrade severely."

- key: granite_4_2_ibm_2026
  title: "Granite 4.2 Language Models: Dense Text-Only Foundation Models for Enterprise Agentic Workflows"
  venue_or_arxiv: "Hugging Face / IBM Technical Report"
  year: 2026
  url: "https://huggingface.co/ibm-granite/granite-4.2-8b"
  what_it_does: |
    Releases dense text-only causal models (8B: 40 layers, hidden 4096, GQA 32/8, 128k context, Apache-2.0).
    Pre-trained and instruction-tuned specifically for coding, tool use, and structured function calling.
  relation_to_us: |
    Primary trainable executor backbone (ibm-granite/granite-4.2-8b) for all Sidekick adapters.
    Selected for its clean dense transformer architecture (standard LoRA in PEFT/vLLM) and cross-family independence.
  numbers_we_cite:
    - "[OBSERVED https://huggingface.co/ibm-granite/granite-4.2-8b] Benchmarks: BFCL v4 52.39, tau3-bench 58.06, SWE-bench Verified 47.67, Terminal-Bench 2.1 20.56, LiveCodeBench v6 73.24, IFBench 79.33, MMLU-Pro 74.04."

- key: gpt_oss_openai_2025
  title: "GPT-OSS: Open-Weight Models for Advanced Reasoning and Agentic Workflows"
  venue_or_arxiv: "OpenAI Technical Announcement"
  year: 2025
  url: "https://openai.com"
  what_it_does: |
    Releases open-weight MoE reasoning models (gpt-oss-20b, gpt-oss-120b) under Apache 2.0 with MXFP4 experts.
    Optimized for multi-step reasoning and function calling.
  relation_to_us: |
    Examined during model selection; serves as open-weight reference point with published AppWorld scores.
    Rejected as primary executor due to MXFP4 serving complexity and shared model family with the planner.
  numbers_we_cite:
    - "[OBSERVED OpenAI / AppWorld Leaderboard JSON] gpt-oss-20b achieves 76.2% TGC on AppWorld test_normal."

- key: gpt_5_6_luna_2026
  title: "GPT-5.6 Luna Benchmark Anchor on AppWorld"
  venue_or_arxiv: "AppWorld Official Leaderboard / OpenAI API"
  year: 2026
  url: "https://appworld.dev/"
  what_it_does: |
    Evaluates GPT-5.6 Luna with standard interactive scaffolding on the AppWorld benchmark suite.
  relation_to_us: |
    Defines our frozen hosted planner (gpt-5.6-luna), providing the planner_alone baseline and the FCD reference.
  numbers_we_cite:
    - "[OBSERVED AppWorld Leaderboard JSON / docs/PLAN.md:102] gpt-5.6-luna with kecaipan capybara scaffold achieves 85.1% TGC / 73.2% SGC on test_normal (9.3 mean interactions), and 73.4% TGC / 52.5% SGC on test_challenge."
    - "[OBSERVED docs/PLAN.md:141] Billing schedule: $0.20 input / $0.02 cached input / $1.20 output USD per 1M tokens."
```
