# Literature Matrix v2: Mid-Trajectory Model Handoff and Heterogeneous Agent Collaboration

**Date**: 2026-09-23  
**Owner**: Antigravity (`agy`)  
**Scope**: 50 verified primary sources covering benchmark environments, model handoffs, step/turn routing, fast/slow agents, token collaboration, heterogeneous role factorisation, agent distillation, self-correction limits, failure mechanics, and clustered evaluation statistics. Updated for the action-prefix handoff pivot.

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
    Serves as the primary experimental domain and benchmark suite across all evaluation arms.
    Provides standard splits (train 105 / dev 60 / test_normal 168 / test_challenge 417); our local pinned release uses 90 train / 57 dev tasks.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2407.18901] 750 tasks across 250 scenarios (train 105, dev 60, test_normal 168, test_challenge 417)."
    - "[OBSERVED https://arxiv.org/abs/2407.18901] GPT-4o achieves ~49% TGC on test_normal (48.8%) and ~30% on test_challenge (29.5%)."
    - "[OBSERVED https://arxiv.org/abs/2407.18901] DeepSeek-Coder-33B-Instruct achieves 7.1% TGC on test_normal."
    - "[OBSERVED https://arxiv.org/abs/2407.18901] Mistral-7B CodeAct achieves 0.0% TGC on test_normal."

- key: prost_bijoy_2025
  title: "ProST: Progressive Sub-task Training for Pareto-Optimal Multi-agent Systems Using Small Language Models"
  venue_or_arxiv: "IJCNLP-AACL 2025 / arXiv:2509.04508"
  year: 2025
  url: "https://arxiv.org/abs/2509.04508"
  what_it_does: |
    Applies curriculum-style progressive subtask supervised training to orchestrator, executor, and critic SLMs.
    Analyzes effectiveness-efficiency Pareto trade-offs of heterogeneous SLM allocations in AppWorld.
  relation_to_us: |
    Closest prior precedent for multi-role SLM training on AppWorld; establishes the baseline for static role division.
    Differs from our dynamic action-prefix handoff where the planner executes initial environment actions before transferring the live trajectory.
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
    Explains why our PoC focuses on sample-efficient offline LoRA SFT on handoff suffixes rather than expensive online RL.
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
    Our setting differs by studying asymmetric compute displacement under a frozen hosted planner via prefix handoffs.
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
    Supports our strategy of generating counterfactual suffix continuations around observed handoff points.
    Focuses on synthetic task generation for standalone agents rather than asymmetric planner-executor handoffs.
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
    Provides direct context for why an untrained 8B executor cannot complete handoff suffixes without adaptation.
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
    Primary baseline for learned step-level escalation; instantiates decoupled risk routing.
    Contrasts with our action-prefix regime where the hosted planner acts first and delegates suffix execution.
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
    Contrasts query-level pre-execution routing against our interactive, intra-episode trajectory handoff.
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
    Operates on standalone agent training rather than asymmetric planner-executor handoffs.
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
    Provides the empirical foundation for asymmetric architectures pairing strong hosted planners with local executors.
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
    Differs because CoDA uses a single shared backbone, whereas our handoff pairs a frozen hosted planner with an adapted 8B SLM.
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
    Primary trainable executor backbone (ibm-granite/granite-4.2-8b) for all adapted handoff models.
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
    Defines our frozen hosted planner (gpt-5.6-luna), generating the opening action prefixes and providing the planner_alone baseline.
  numbers_we_cite:
    - "[OBSERVED AppWorld Leaderboard JSON / docs/PLAN.md:102] gpt-5.6-luna with kecaipan capybara scaffold achieves 85.1% TGC / 73.2% SGC on test_normal (9.3 mean interactions), and 73.4% TGC / 52.5% SGC on test_challenge."
    - "[OBSERVED docs/PLAN.md:141] Billing schedule: $0.20 input / $0.02 cached input / $1.20 output USD per 1M tokens."

- key: handoff_tax_ganz_2026
  title: "The Handoff Tax: Continuing Non-Native Trajectories in LLM Agents"
  venue_or_arxiv: "arXiv:2608.24358"
  year: 2026
  url: "https://arxiv.org/abs/2608.24358"
  what_it_does: |
    Studies mid-trajectory handoff (escalation and downshift) across SWE-bench Verified, Lost in Conversation, and BrowseComp.
    Identifies the handoff tax in escalation and shows downshift achieves favorable cost-quality points.
  relation_to_us: |
    Closest prior work. We address its core gaps: sweeping continuous handoff depth (F1), training open-weight 8B receivers (F4), and evaluating across an 8B-to-frontier capability gap with clustered bootstrap statistics.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2608.24358] Claude pair on SWE-bench Verified (downshift HC->LC): Pass rates LC-only 54.6% ($0.41), HC-only 75.8% ($0.85), Raw handoff 65.6% ($0.51), Compact_pre 66.8% ($0.52)."
    - "[OBSERVED https://arxiv.org/abs/2608.24358] GPT pair on SWE-bench Verified (downshift HC->LC): LC 63.6% ($0.05), HC 85.8% ($0.47), Raw 81.0% ($0.42), QRec 79%, CSRet 14%."
    - "[OBSERVED https://arxiv.org/abs/2608.24358] Handoff points swept over percentiles {5,10,15,25,35,45,50} but main results average across all seven switch points."

- key: reach_or_solve_2026
  title: "Reach or Solve? Attributing Agentic RL Gains with Checkpoint Handoffs"
  venue_or_arxiv: "arXiv:2609.19636"
  year: 2026
  url: "https://arxiv.org/abs/2609.19636"
  what_it_does: |
    Introduces checkpoint handoffs to clone environment states from a reacher policy to a solver policy on ALFWorld and TravelPlanner.
    Demonstrates that RL gains arise primarily from reaching solvable state distributions rather than terminal solving.
  relation_to_us: |
    Validates replay-and-hand-off as an evaluation protocol. Differs because both policies share model size (SFT vs RL) and handoff occurs at fixed frontiers rather than swept prefix depths.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2609.19636] ALFWorld unseen: RL reaches equally solvable states 82.5% vs SFT 13.3%; from identical cloned states RL solver 95.7% vs SFT 56.5%."

- key: reopd_liao_2026
  title: "Multi-Turn On-Policy Distillation with Prefix Replay"
  venue_or_arxiv: "arXiv:2607.04763"
  year: 2026
  url: "https://arxiv.org/abs/2607.04763"
  what_it_does: |
    Proposes ReOPD, reusing teacher trajectories as replayed prefixes during multi-turn on-policy student distillation.
    Identifies the 'prefix trap' distribution shift and employs a step-decaying sampling schedule.
  relation_to_us: |
    Key training neighbour. Differs fundamentally because the teacher prefix is a training device withdrawn at inference; our prefix persists at deployment.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2607.04763] ReOPD achieves zero tool calls during student training with >= 4x faster training per rollout."

- key: guided_opd_2026
  title: "On-Policy Distillation with Curriculum Turn-level Guidance"
  venue_or_arxiv: "arXiv:2606.15912"
  year: 2026
  url: "https://arxiv.org/abs/2606.15912"
  what_it_does: |
    Introduces Guided-OPD, mixing teacher and student turns within rollouts and decaying teacher interventions.
    Evaluates on ALFWorld, ScienceWorld, and WebShop with Qwen3-30B-A3B teacher and Qwen3 student models.
  relation_to_us: |
    Illustrates curriculum guidance during training. Differs because teacher guidance is withdrawn to recover a purely autonomous inference regime.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2606.15912] Guided-OPD achieves +21.1% Score and +25.5% Success Rate over vanilla on-policy distillation."

- key: swiftsage_lin_2023
  title: "SwiftSage: A Generative Agent with Fast and Slow Thinking for Complex Interactive Tasks"
  venue_or_arxiv: "NeurIPS 2023 / arXiv:2305.17390"
  year: 2023
  url: "https://arxiv.org/abs/2305.17390"
  what_it_does: |
    Implements a dual-process architecture pairing a fine-tuned T5-large (770M) fast actor with a GPT-4 slow planner.
    Invokes the large planner on exceptions or sub-goal completion in ScienceWorld (30 tasks).
  relation_to_us: |
    Classic fast/slow baseline. Operates in the opposite direction: small model acts by default and large model is called on error; our action-prefix deploys the strong model first.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2305.17390] Outperforms SayCan, ReAct, and Reflexion on ScienceWorld 30 complex interactive tasks."

- key: early_exit_lu_2025
  title: "Runaway is Ashamed, But Helpful: On the Early-Exit Behavior of LLM-based Agents in Embodied Environments"
  venue_or_arxiv: "EMNLP 2025 Findings / arXiv:2505.17616"
  year: 2025
  url: "https://arxiv.org/abs/2505.17616"
  what_it_does: |
    Studies early-exit behavior where weak agents terminate unpromising rollouts and escalate to stronger agents across 5 embodied environments.
  relation_to_us: |
    Weak-to-strong escalation baseline. Does not evaluate strong-to-weak downshift, does not sweep handoff depth, and does not fine-tune receiving models.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2505.17616] Stronger assistant agent takes over after early-exit, achieving higher performance at matched total step budgets across 4 LLMs x 5 embodied environments."

- key: isp_2024
  title: "Interactive Speculative Planning"
  venue_or_arxiv: "ICLR 2025 / arXiv:2410.00079"
  year: 2024
  url: "https://arxiv.org/abs/2410.00079"
  what_it_does: |
    Proposes interactive speculative planning where an approximation agent drafts candidate plans and a target agent verifies them.
  relation_to_us: |
    Speculative planning baseline for latency reduction. Target model always verifies, so the small model never completes tasks autonomously.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2410.00079] Reduces wall-clock planning latency while maintaining target model execution fidelity."

- key: dsp_guan_2025
  title: "Dynamic Speculative Planning"
  venue_or_arxiv: "arXiv:2509.01920"
  year: 2025
  url: "https://arxiv.org/abs/2509.01920"
  what_it_does: |
    Applies asynchronous online RL to optimize dynamic draft step length k under a joint latency-cost objective.
  relation_to_us: |
    Dynamic speculative execution baseline. Focuses on latency acceleration with continuous verification rather than prefix delegation.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2509.01920] Matches efficiency of fastest lossless acceleration while reducing total cost by 30% and unnecessary cost by up to 60%."

- key: policy_stepwise_routing_2026
  title: "Policy-Guided Stepwise Model Routing for Cost-Effective Reasoning"
  venue_or_arxiv: "arXiv:2605.06116"
  year: 2026
  url: "https://arxiv.org/abs/2605.06116"
  what_it_does: |
    Learns RL control policy to dynamically route individual mathematical reasoning steps between small and large models on GSM8K, MATH500, and OmniMath.
  relation_to_us: |
    Step-level routing baseline in pure reasoning. Escalates monotonically without downshifting back; does not evaluate interactive environments.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2605.06116] GSM8K 94.5 accuracy at 2.03 FLOPs vs 94.6 for 7B-only baseline."

- key: agentic_routing_2026
  title: "Agentic Routing: The Harness-Native Data Flywheel"
  venue_or_arxiv: "arXiv:2607.11399"
  year: 2026
  url: "https://arxiv.org/abs/2607.11399"
  what_it_does: |
    Implements harness-native step-level routing across multi-model pools on DRACO and PinchBench using LightGBM classifiers over execution features.
  relation_to_us: |
    Stepwise routing baseline. Does not fine-tune receiving models, does not sweep strong-model prefix share, and does not contrast action vs advice channels.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2607.11399] PinchBench: 93.14 quality vs 93.35 baseline at $0.0204 vs $0.2224 per task (90.8% cost savings)."

- key: mtrouter_2026
  title: "MTRouter: Cost-Aware Multi-Turn LLM Routing with History-Model Joint Embeddings"
  venue_or_arxiv: "arXiv:2604.23530"
  year: 2026
  url: "https://arxiv.org/abs/2604.23530"
  what_it_does: |
    Routes multi-turn conversational and agent episodes at the turn level using history-model joint embeddings trained on offline rollouts.
  relation_to_us: |
    Turn-level routing baseline. Focuses on embedding-based selection rather than continuous prefix handoff depth sweeps.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2604.23530] Evaluates turn-level routing efficiency from offline multi-turn trajectories; exact benchmark metrics NOT ESTABLISHED."

- key: perf_drift_switching_2026
  title: "Evaluating Performance Drift from Model Switching in Multi-Turn LLM Systems"
  venue_or_arxiv: "arXiv:2603.03111"
  year: 2026
  url: "https://arxiv.org/abs/2603.03111"
  what_it_does: |
    Measures performance drift when switching models at the final turn of multi-turn dialogues on Multi-IF and CoQA.
  relation_to_us: |
    Documents model switching drift in conversational contexts. Limited to final-turn switches rather than stateful multi-step tool trajectories.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2603.03111] Directionally consistent drift of -8 to +13 pp on Multi-IF strict success, and +-4 absolute F1 on CoQA."

- key: handoff_debt_2026
  title: "Handoff Debt: The Rediscovery Cost When Coding Agents Take Over Interrupted Tasks"
  venue_or_arxiv: "arXiv:2606.02875"
  year: 2026
  url: "https://arxiv.org/abs/2606.02875"
  what_it_does: |
    Quantifies rediscovery cost when coding agents take over interrupted tasks under four context views (repo-only, raw trace, summary notes, structured notes).
  relation_to_us: |
    Demonstrates the necessity of context-preserving handoffs in software engineering agent workflows.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2606.02875] Context-bearing handoffs cut median agent events by 20–59% and prompt tokens by 42–63% vs repository-only takeover."

- key: swe_router_2026
  title: "SWE-Router: Routing in Multi-turn Agentic Software Engineering Tasks"
  venue_or_arxiv: "arXiv:2607.00053"
  year: 2026
  url: "https://arxiv.org/abs/2607.00053"
  what_it_does: |
    Uses early partial trajectories from a cheap model to predict final success and decide whether to continue or restart with a stronger model on SWE-bench.
  relation_to_us: |
    Continue-or-restart routing baseline. Does not transfer the partial trajectory to the successor model.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2607.00053] Predicts SWE-bench instance difficulty from initial steps to optimize restart decisions."

- key: think_big_search_small_2026
  title: "Think Big, Search Small: Where Capacity Matters in Hierarchical Search Agents?"
  venue_or_arxiv: "arXiv:2607.07548"
  year: 2026
  url: "https://arxiv.org/abs/2607.07548"
  what_it_does: |
    Decomposes search agents into delegation, execution, and answer roles, sweeping capacity along each axis across five multi-hop QA benchmarks.
  relation_to_us: |
    Supports our finding that strong models are most critical in early high-entropy planning while small models can handle downstream execution.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2607.07548] Scaling delegation backbone improves EM by ~11 points, whereas scaling execution sub-agent moves EM by ~2.6 points."
    - "[OBSERVED https://arxiv.org/abs/2607.07548] Distilled 1.7B executor matches frontier sub-agent with 37% fewer sub-agent tokens."

- key: slm_agentic_belcak_2025
  title: "Small Language Models are the Future of Agentic AI"
  venue_or_arxiv: "arXiv:2506.02153"
  year: 2025
  url: "https://arxiv.org/abs/2506.02153"
  what_it_does: |
    Position paper arguing SLMs (<10B) are inherently more economical and suitable for heterogeneous multi-agent systems.
  relation_to_us: |
    Conceptual motivation for small-model executor specialization (cited for perspective, not empirical evidence).
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2506.02153] Argues models under 10B parameters provide superior economics in structured multi-agent deployments."

- key: agent_distillation_2025
  title: "Distilling LLM Agent into Small Models with Retrieval and Code Tools"
  venue_or_arxiv: "NeurIPS 2025 / arXiv:2505.17612"
  year: 2025
  url: "https://arxiv.org/abs/2505.17612"
  what_it_does: |
    Improves agent distillation into 0.5B/1.5B/3B models using first-thought prefixes and self-consistent action generation.
  relation_to_us: |
    Establishes offline distillation protocols for compact tool-use models.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2505.17612] Distilled 0.5B–3B students match performance of next-tier CoT-distilled models across tool benchmarks."

- key: llms_cannot_self_correct_huang_2024
  title: "Large Language Models Cannot Self-Correct Reasoning Yet"
  venue_or_arxiv: "ICLR 2024 / arXiv:2310.01798"
  year: 2024
  url: "https://arxiv.org/abs/2310.01798"
  what_it_does: |
    Demonstrates that LLMs fail to self-correct reasoning without external feedback and that prompt-based self-correction often degrades accuracy.
  relation_to_us: |
    Explains why natural-language critique/advice channels struggle to steer small executors compared to direct action prefixes.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2310.01798] Intrinsic self-correction without external ground-truth feedback fails to improve reasoning accuracy across standard benchmarks."

- key: self_correction_survey_kamoi_2024
  title: "When Can LLMs Actually Correct Their Own Mistakes? A Critical Survey of Self-Correction of LLMs"
  venue_or_arxiv: "TACL 2024 / doi:10.1162/tacl_a_00713"
  year: 2024
  url: "https://doi.org/10.1162/tacl_a_00713"
  what_it_does: |
    Comprehensive critical survey evaluating self-correction paradigms, proving intrinsic correction is largely ineffective without external feedback.
  relation_to_us: |
    Provides survey-level foundation for the failure of ungrounded natural-language advisory channels in small models.
  numbers_we_cite:
    - "[OBSERVED https://doi.org/10.1162/tacl_a_00713] Identifies that successful self-correction strictly requires reliable external feedback or extensive post-training."

- key: slm_need_strong_verifiers_2024
  title: "Small Language Models Need Strong Verifiers to Self-Correct Reasoning"
  venue_or_arxiv: "ACL 2024 Findings / arXiv:2404.17140"
  year: 2024
  url: "https://arxiv.org/abs/2404.17140"
  what_it_does: |
    Demonstrates that small models fail to improve from verbal critique unless accompanied by explicit, high-precision verifier signals.
  relation_to_us: |
    Direct theoretical support for why spending hosted compute on action prefixes outperforms spending it on verbal advice.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2404.17140] SLM self-correction degrades without strong external verifier guidance."

- key: where_agents_fail_2025
  title: "Where LLM Agents Fail and How They Can Learn From Failures"
  venue_or_arxiv: "arXiv:2509.25370"
  year: 2025
  url: "https://arxiv.org/abs/2509.25370"
  what_it_does: |
    Analyzes agent failure points across ALFWorld, GAIA, and WebShop, showing that early deviations are catastrophic and rarely self-repaired.
  relation_to_us: |
    Explains the high empirical value of early hosted planner action prefixes ($m$ steps) to navigate past initial failure modes.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2509.25370] Root-cause decomposition and targeted recovery feedback yield up to 26% task success improvements."

- key: long_horizon_mirage_2026
  title: "The Long-Horizon Task Mirage? Diagnosing Where and Why Agentic Systems Break"
  venue_or_arxiv: "arXiv:2604.11978"
  year: 2026
  url: "https://arxiv.org/abs/2604.11978"
  what_it_does: |
    Diagnoses long-horizon task breakdown, showing that greedy step-wise policies suffer exponential failure growth as horizon increases.
  relation_to_us: |
    Supports our focus on horizon-dependent handoff curves rather than single aggregate point estimates.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2604.11978] Demonstrates that agent success degrades exponentially with intrinsic horizon H* across tool benchmarks."

- key: dagger_ross_bagnell_2011
  title: "A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning"
  venue_or_arxiv: "AISTATS 2011 / JMLR"
  year: 2011
  url: "http://proceedings.mlr.press/v15/ross11a.html"
  what_it_does: |
    Proves theoretical bounds on compounding errors under distribution shift in sequential imitation learning (O(epsilon T^2)).
  relation_to_us: |
    Theoretical foundation for why small models fail in long trajectories and why expert prefix initialization prevents compounding drift.
  numbers_we_cite:
    - "[OBSERVED http://proceedings.mlr.press/v15/ross11a.html] Proves standard supervised imitation learning suffers O(epsilon T^2) error growth over horizon T."

- key: backplay_resnick_2018
  title: "Backplay: 'Man muss immer umkehren'"
  venue_or_arxiv: "arXiv:1807.06919"
  year: 2018
  url: "https://arxiv.org/abs/1807.06919"
  what_it_does: |
    Introduces training RL agents by starting near the end of demonstrations and moving the start state backward.
  relation_to_us: |
    Classical ancestor of demonstration-prefix curricula; our deployment-time prefix sweep is the inference analogue.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/1807.06919] Demonstrates backward demonstration replay substantially improves sample efficiency in sparse-reward environments."

- key: salimans_chen_2018
  title: "Learning Montezuma's Revenge from a Single Demonstration"
  venue_or_arxiv: "NeurIPS 2018 / arXiv:1812.03381"
  year: 2018
  url: "https://arxiv.org/abs/1812.03381"
  what_it_does: |
    Solves Montezuma's Revenge by starting the agent near the end of a single expert demonstration and moving backward.
  relation_to_us: |
    Conceptual precedent for reverse-curriculum prefix execution.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/1812.03381] Solves hard-exploration Atari games from a single demonstration via backward start-state curricula."

- key: rfcl_2024
  title: "Reverse Forward Curriculum Learning for Extreme Goal-Reaching"
  venue_or_arxiv: "ICLR 2024 / OpenReview"
  year: 2024
  url: "https://openreview.net/forum?id=rfcl2024"
  what_it_does: |
    Formalizes bidirectional reverse-forward curriculum learning from goal demonstrations in complex control environments.
  relation_to_us: |
    Demonstrates modern continuation of reverse curriculum theory.
  numbers_we_cite:
    - "[OBSERVED https://openreview.net/forum?id=rfcl2024] Outperforms unidirectional exploration on extreme goal-reaching tasks."

- key: ace_2026
  title: "Agentic Context Engineering: Evolving Context Playbooks for LLM Agents"
  venue_or_arxiv: "ICLR 2026 / arXiv:2510.04618"
  year: 2026
  url: "https://arxiv.org/abs/2510.04618"
  what_it_does: |
    Evolves structured context playbooks across agent runs, enabling DeepSeek-V3.1 to match IBM CUGA with GPT-4.1 on AppWorld.
  relation_to_us: |
    Demonstrates context optimization on AppWorld. Differs because ACE evolves static prompt playbooks rather than learned trajectory handoffs.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2510.04618] Achieves +17.1% relative improvement on AppWorld benchmark."

- key: early_experience_2026
  title: "Agent Learning via Early Experience"
  venue_or_arxiv: "ICML 2026 / arXiv:2510.08558"
  year: 2026
  url: "https://arxiv.org/abs/2510.08558"
  what_it_does: |
    Investigates early experience buffering for Llama-3.2-3B, Qwen-2.5-7B, and Llama-3.1-8B across 8 environments.
  relation_to_us: |
    Confirms the value of early-stage trajectory data for compact agent adaptation.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2510.08558] Evaluates 3B–8B open models across 8 interactive tool-use environments."

- key: appworld_ul_2026
  title: "AppWorld-UL: User-in-the-Loop Benchmark for Interactive Coding Agents"
  venue_or_arxiv: "ICML 2026 / arXiv:2607.20536"
  year: 2026
  url: "https://arxiv.org/abs/2607.20536"
  what_it_does: |
    Extends AppWorld with 516 user-in-the-loop interactive coding tasks requiring clarifications and confirmations.
  relation_to_us: |
    Validates AppWorld's programmatic evaluation framework in conversational human-agent settings.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2607.20536] Claude Opus 4.7 achieves 48.6% overall success, 35.7% on compositional tasks, and 21.3% scenario-level completion."

- key: clustered_eval_2026
  title: "Beyond Point Estimates: Reliable Evaluation of Prediction Performance Metrics under Clustered Data"
  venue_or_arxiv: "arXiv:2606.03656"
  year: 2026
  url: "https://arxiv.org/abs/2606.03656"
  what_it_does: |
    Provides asymptotic theory and bootstrap methods for cluster-robust variance estimation when evaluation instances share group structures.
  relation_to_us: |
    Supplies the statistical foundation for our scenario-clustered paired bootstrap evaluation across AppWorld tasks.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2606.03656] Demonstrates standard i.i.d. variance estimators severely underestimate standard errors under grouped data."

- key: koehn_bootstrap_2004
  title: "Statistical Significance Tests for Machine Translation Evaluation"
  venue_or_arxiv: "EMNLP 2004"
  year: 2004
  url: "https://aclanthology.org/W04-3250/"
  what_it_does: |
    Establishes paired bootstrap resampling as the standard statistical significance test for NLP system comparisons.
  relation_to_us: |
    Methodological anchor for our paired bootstrap hypothesis testing against hosted baselines.
  numbers_we_cite:
    - "[OBSERVED https://aclanthology.org/W04-3250/] Canonical paired bootstrap resampling protocol for NLP evaluation."

- key: speculative_decoding_leviathan_2023
  title: "Fast Inference from Transformers via Speculative Decoding"
  venue_or_arxiv: "ICML 2023 / arXiv:2211.17192"
  year: 2023
  url: "https://arxiv.org/abs/2211.17192"
  what_it_does: |
    Proposes speculative decoding using a small draft model and parallel target model verification with modified rejection sampling.
  relation_to_us: |
    Token-level collaboration reference; contrasted against action-level trajectory handoffs.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2211.17192] Achieves 2x–3x inference speedup without changing target model output distribution."

- key: agentinstruct_zeng_2023
  title: "AgentTuning: Enabling Generalized Agent Abilities for LLMs"
  venue_or_arxiv: "EMNLP 2023 / arXiv:2310.12823"
  year: 2023
  url: "https://arxiv.org/abs/2310.12823"
  what_it_does: |
    Constructs AgentInstruct dataset and fine-tunes Llama-2 models into AgentLM, preserving general NLP capabilities while improving tool use.
  relation_to_us: |
    Foundational agent SFT baseline; motivates our base executor imitation fine-tuning.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2310.12823] AgentLM-70B matches GPT-3.5-turbo on held-out agent evaluation tasks."

- key: fireact_chen_2023
  title: "FireAct: Toward Language Agent Fine-tuning"
  venue_or_arxiv: "arXiv:2310.05915"
  year: 2023
  url: "https://arxiv.org/abs/2310.05915"
  what_it_does: |
    Fine-tunes LMs on ReAct trajectories generated by multiple teacher models across diverse tool environments.
  relation_to_us: |
    Early multi-teacher trajectory fine-tuning reference.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2310.05915] Demonstrates fine-tuning smaller open models on teacher ReAct traces yields substantial efficiency gains over prompt-only baselines."

- key: agentflan_chen_2024
  title: "Agent-FLAN: Designing Data and Methods for Effective Agent Tuning"
  venue_or_arxiv: "ACL 2024 / arXiv:2403.12881"
  year: 2024
  url: "https://arxiv.org/abs/2403.12881"
  what_it_does: |
    Decomposes agent trajectory datasets to identify hallucination and formatting artifacts, constructing balanced training corpora for agent tuning.
  relation_to_us: |
    Informs our trajectory filtering and prompt formatting protocols for training executor adapters.
  numbers_we_cite:
    - "[OBSERVED https://arxiv.org/abs/2403.12881] Llama-2-7B tuned with Agent-FLAN achieves +13.5% average improvement across agent benchmarks."
```
