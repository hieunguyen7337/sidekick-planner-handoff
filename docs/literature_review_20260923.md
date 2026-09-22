# Systematic Literature Review: Mid-Trajectory Model Handoff and Heterogeneous Agent Collaboration

**Date**: 2026-09-23  
**Scope**: Comprehensive review across nine themes covering intra-episode model handoff, routing, speculative planning, agent distillation, self-correction limits, long-horizon failure mechanics, AppWorld benchmark state of the art, and clustered evaluation statistics.  
**Grounding Convention**: Every factual claim is tagged `[OBSERVED <url-or-path>]` or `[INFERRED]`.

---

## 1. Query-Level Cascades and Routers

Early literature on cost-efficient foundation model deployment focused predominantly on query-level routing, where incoming natural language prompts are classified prior to execution and dispatched in their entirety to an appropriate model tier `[OBSERVED https://arxiv.org/abs/2305.05176]`.

FrugalGPT (Chen et al., 2023) formalized this paradigm through prompt adaptation, task-specific model approximation, and learned cascade policies that query progressively larger models only when cheaper predictors report low confidence `[OBSERVED https://arxiv.org/abs/2305.05176]`. On static question answering and text generation workloads, FrugalGPT demonstrated that query cascades could match GPT-4 performance with up to 98% cost reduction or improve accuracy by 4% at matched cost `[OBSERVED https://arxiv.org/abs/2305.05176]`. Building on this, RouteLLM (Ong et al., 2024) developed preference-based routing frameworks trained on human comparison data, achieving over 50% inference cost reduction while preserving response quality across diverse benchmark suites `[OBSERVED https://arxiv.org/abs/2406.18665]`. Subsequent extensions, including Hybrid LLM (Ding et al., 2024) and dynamic multi-model aggregators (Valkanas et al., 2025; Kotte et al., 2026), refined router feature representations and threshold calibration for heterogeneous commercial endpoints `[OBSERVED https://arxiv.org/abs/2404.14618]`.

However, the fundamental assumption underpinning query-level routing—that task difficulty and resource requirements can be accurately predicted from the initial user prompt alone—breaks down in stateful, multi-turn interactive agent environments `[INFERRED]`. In digital tool-use domains, unforeseen environment responses, database state mutations, API errors, and compounding logical drifts emerge dynamically midway through trajectory execution `[OBSERVED https://arxiv.org/abs/2604.11978]`. Consequently, static episode-level dispatch is incapable of adapting computational spend to emergent runtime uncertainty `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 2. Step- and Turn-Level Routing, and Mid-Trajectory Model Switching (The Handoff Tax Ring)

To overcome the rigidity of query-level cascades, recent research has advanced into intra-episode switching, where the active model changes during trajectory execution `[OBSERVED https://arxiv.org/abs/2608.24358]`.

The closest prior work to our investigation is "The Handoff Tax: Continuing Non-Native Trajectories in LLM Agents" (Ganz et al., 2026-08-25, arXiv:2608.24358) `[OBSERVED https://arxiv.org/abs/2608.24358]`. Ganz et al. investigate the cost-quality dynamics of switching models mid-trajectory across SWE-bench Verified (500 instances), Lost in Conversation (535 tasks), and BrowseComp (200 questions) using pairs of low-cost (LC) and high-cost (HC) models (Claude Haiku 4.5 / Claude Opus 4.7, and GPT-5.6 Luna / GPT-5.6 Sol) `[OBSERVED https://arxiv.org/abs/2608.24358]`. They identify an asymmetric penalty termed the "handoff tax": full-trajectory escalation (LC $\rightarrow$ HC) recovers less than half of the LC-to-HC quality gap while incurring a substantial cost premium `[OBSERVED https://arxiv.org/abs/2608.24358]`. Conversely, downshift (HC $\rightarrow$ LC) yields an advantageous cost-quality trade-off: on SWE-bench Verified with the Claude pair, downshifting achieves 65.6% pass rate under raw trajectory transfer (cost $0.51) compared to 54.6% for LC-only ($0.41) and 75.8% for HC-only ($0.85), retaining 80% of cost savings while recovering 50% of the quality gap `[OBSERVED https://arxiv.org/abs/2608.24358]`. Ganz et al. also demonstrate that interface preferences reverse with handoff direction: reducing LC trajectory information improves escalation quality, whereas preserving the HC trajectory is critical for downshift success `[OBSERVED https://arxiv.org/abs/2608.24358]`.

Crucially, several structural characteristics define the Ganz et al. study:
1. **Averaged Switch Points**: Results are averaged over seven fixed termination percentiles ($p \in \{5, 10, 15, 25, 35, 45, 50\}$); the paper explicitly notes that *"The main results average over all seven switch points"* and does not plot an explicit continuous quality-versus-handoff-depth curve `[OBSERVED https://arxiv.org/abs/2608.24358]`.
2. **Zero-Shot Receivers**: All receiving models operate strictly zero-shot without fine-tuning, adapter specialization, or post-training adaptation `[OBSERVED https://arxiv.org/abs/2608.24358]`.
3. **Frontier-Tier Model Pairs**: The LC models evaluated (e.g., Claude Haiku 4.5, GPT-5.6 Luna) are themselves multi-billion parameter commercial frontier-tier endpoints, rather than an open-weight $\le 8\text{B}$ local model facing a massive capability gap `[OBSERVED https://arxiv.org/abs/2608.24358]`.
4. **Single-Rollout Evaluation**: The study evaluates a single episode per task configuration without repeated rollout seeds or confidence intervals, stating: *"We run a single episode for each of the 500 tasks under every configuration and therefore do not estimate variability across repeated runs."* `[OBSERVED https://arxiv.org/abs/2608.24358]`.

Adjacent studies examine complementary facets of trajectory handoffs:
- **Reach or Solve?** (Liu & Qian, 2026, arXiv:2609.19636) introduces "checkpoint handoff" as an evaluation protocol that *"clones a state one released checkpoint reached and hands it to another, with no retraining"* to separate state-space exploration (reacher) from terminal resolution (solver) on ALFWorld and TravelPlanner `[OBSERVED https://arxiv.html/2609.19636]`. However, Liu & Qian evaluate matched-capacity checkpoints (SFT vs. RL policies on Qwen 1.5B/3B/7B) at fixed terminal frontiers rather than sweeping handoff depth across asymmetric model tiers `[OBSERVED https://arxiv.org/html/2609.19636]`.
- **Policy-Guided Stepwise Routing** (Si et al., 2026, arXiv:2605.06116) trains an RL policy to route individual reasoning steps in mathematical derivation benchmarks (GSM8K, MATH500), but once escalated, the trajectory remains on the large model without allowing downshift resumption `[OBSERVED https://arxiv.org/abs/2605.06116]`.
- **Agentic Routing** (TokenRhythm, 2026, arXiv:2607.11399) implements harness-native step-level routing across multi-model pools on PinchBench (achieving 93.14 quality at 90.8% cost savings via LightGBM over hand features), but leaves receiver fine-tuning to future work and does not evaluate systematic action-prefix sharing `[OBSERVED https://arxiv.org/abs/2607.11399]`.
- **Handoff Debt** (KC & Budathoki, 2026, arXiv:2606.02875) measures the rediscovery overhead when successor coding agents take over interrupted tasks, observing that structured context-bearing handoffs reduce median agent events by 20–59% compared to repository-only handovers `[OBSERVED https://arxiv.org/abs/2606.02875]`.
- **SWE-Router** (Son et al., 2026, arXiv:2607.00053) learns early continue-or-restart decisions from partial trajectories on SWE-bench but does not transfer active trajectories across heterogeneous models `[OBSERVED https://arxiv.org/abs/2607.00053]`.
- **Performance Drift** (Khraishi et al., 2026, arXiv:2603.03111) shows that multi-turn model switching at the final dialogue turn causes $-8$ to $+13$ pp drift on Multi-IF `[OBSERVED https://arxiv.org/abs/2603.03111]`.
- **MTRouter** (2026, arXiv:2604.23530) explores joint history-model embeddings for turn-level routing `[OBSERVED https://arxiv.org/abs/2604.23530]`.

### What we add

TODO(claude): novelty verdict

---

## 3. Fast/Slow Agents and Speculative Planning

A distinct lineage of multi-model execution draws inspiration from dual-process cognitive theories, structuring execution into fast intuitive generation (System 1) and deliberative analytic planning (System 2) `[OBSERVED https://arxiv.org/abs/2305.17390]`.

SwiftSage (Lin et al., NeurIPS 2023) exemplifies this paradigm on ScienceWorld by pairing a fine-tuned T5-large (770M) "Swift" actor with a GPT-4 "Sage" planner `[OBSERVED https://arxiv.org/abs/2305.17390]`. In SwiftSage, the small model executes actions by default, invoking the large model strictly on exceptions or planning deadlocks `[OBSERVED https://arxiv.org/abs/2305.17390]`. This represents the exact inverted operational direction of our action-prefix regime: SwiftSage uses weak-by-default execution with reactive escalation, whereas prefix-handoff deploys strong-first execution to traverse high-entropy initial setup before delegating terminal completion to the small model `[INFERRED]`.

Similarly, Lu et al. (EMNLP 2025 Findings, arXiv:2505.17616) evaluate early-exit mechanisms in embodied agents, showing that allowing a weak agent to forfeit early and escalate to a stronger agent improves multi-step success `[OBSERVED https://arxiv.org/abs/2505.17616]`. In speculative execution frameworks, Interactive Speculative Planning (ISP, ICLR 2025, arXiv:2410.00079) and Dynamic Speculative Planning (DSP, Guan et al., 2025, arXiv:2509.01920) utilize lightweight drafting agents to propose action sequences that are concurrently verified by a target model `[OBSERVED https://arxiv.org/abs/2410.00079]`. These systems focus primarily on wall-clock latency reduction rather than asymmetric compute displacement, and because the target model must verify every step, the small model is never granted autonomous terminal execution authority `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 4. Token-Level Collaboration (Analogy Only)

At the token generation level, speculative decoding (Leviathan et al., ICML 2023; Chen et al., 2023) and collaborative decoding (Kim et al., NeurIPS 2024) use small draft models to generate candidate token sequences that a large target model verifies in parallel via modified rejection sampling `[OBSERVED https://arxiv.org/abs/2211.17192]`.

While conceptually analogous in dividing labor between small and large models, token-level speculative execution does not map to our interactive agent setting for three fundamental reasons:
1. **Remote Hosted Latency & Cost**: Speculative decoding requires synchronous, co-located tensor operations in shared GPU memory at microsecond token intervals `[OBSERVED https://arxiv.org/abs/2211.17192]`. In our setting, the planner is a black-box, remote token-billed hosted API (`gpt-5.6-luna`), where network round-trip latencies and per-call token billing render synchronous token-level verification impossible `[OBSERVED docs/PLAN.md:21-48]`.
2. **Irreversible Environment Side Effects**: In interactive environments like AppWorld, agent actions trigger external side effects—such as database writes, API mutations, and code executions—that cannot be rolled back via autoregressive token rejection sampling `[OBSERVED https://arxiv.org/abs/2407.18901]`.
3. **Macro-Action Granularity**: Mid-trajectory handoff operates across contiguous multi-step action trajectories (spanning API discoveries, parameter formatting, and test executions) rather than next-token probability distributions `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 5. Role-Factorised Heterogeneous Agent Teams

A prominent architectural pattern in multi-agent systems is role factorisation, where complex tasks are decomposed across functional roles such as orchestrator/planner, code executor, and verifier/critic `[OBSERVED https://arxiv.org/abs/2607.07548]`.

Cai et al. (2026, arXiv:2607.07548, "Think Big, Search Small") explore where model capacity matters in hierarchical search agents across five multi-hop QA benchmarks `[OBSERVED https://arxiv.org/abs/2607.07548]`. They discover a marked capacity asymmetry: scaling the high-level delegation backbone improves Exact Match by $\approx 11$ points, whereas scaling the execution sub-agent moves Exact Match by only $\approx 2.6$ points `[OBSERVED https://arxiv.org/abs/2607.07548]`. Furthermore, training a 1.7B executor via quality-filtered trajectory distillation matches a frontier sub-agent while consuming 37% fewer sub-agent tokens `[OBSERVED https://arxiv.org/abs/2607.07548]`.

In the AppWorld environment, ProST (Bijoy et al., IJCNLP-AACL 2025, arXiv:2509.04508) applies progressive subtask supervised training to orchestrator, executor, and critic SLMs, demonstrating that fine-tuning $\approx 8\text{B}$ open models achieves 26.0–33.0% Task Goal Completion (compared to 1.0–17.0% for frozen baselines) `[OBSERVED https://arxiv.org/abs/2509.04508]`. AgentCARD (Jiang et al., 2026, arXiv:2606.20629) formalizes heterogeneous deployment mixtures (API, self-hosted, hybrid) and applies Shapley value analysis to diagnose capability bottlenecks, showing that heterogeneous teams improve accuracy by up to 44% over cost-equivalent homogeneous teams or match frontier performance at up to $12\times$ lower cost `[OBSERVED https://arxiv.org/abs/2606.20629]`. Complementarily, Three Roles One Model (2026, arXiv:2604.11465) shows that scaffolding a single frozen Qwen3-8B into three prompt roles achieves 8.9% TGC on AppWorld `[OBSERVED https://arxiv.org/abs/2604.11465]`, while CoDA (Liu et al., 2025, arXiv:2512.12716) decouples planner and executor contexts under a shared model backbone using trajectory RL `[OBSERVED https://arxiv.org/abs/2512.12716]`.

While these studies validate the Pareto efficiency of heterogeneous role separation, they operate on static role assignments throughout the entire episode. They do not evaluate dynamic handoffs along the temporal execution horizon where the planner actively drives the initial trajectory before relinquishing execution `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 6. Distilling Agents into Small Models, and the Demonstration-Prefix / Reverse-Curriculum Lineage

Training compact open models on trajectory data generated by frontier teacher models is the foundation of agent distillation `[OBSERVED https://arxiv.org/abs/2310.12823]`. Early frameworks—such as AgentTuning / AgentInstruct (Zeng et al., EMNLP 2023), FireAct (Chen et al., 2023), and Agent-FLAN (Chen et al., ACL 2024)—established supervised fine-tuning protocols on filtered teacher rollouts `[OBSERVED https://arxiv.org/abs/2310.12823]`. Recent work by NeurIPS 2025 contributors (arXiv:2505.17612) incorporates "first-thought prefixes" to enhance small model tool use `[OBSERVED https://arxiv.org/abs/2505.17612]`.

In multi-turn interactive settings, on-policy trajectory distillation faces severe distribution shift. ReOPD (Liao et al., Microsoft, 2026-07, arXiv:2607.04763) addresses this by reusing pre-collected teacher trajectories as replayed prefixes during training, identifying the "prefix trap": forcing histories to be purely student-on-policy improves relevance but queries the teacher in states where teacher supervision is unreliable `[OBSERVED https://arxiv.org/abs/2607.04763]`. ReOPD adopts a step-decaying prefix sampling schedule to stabilize multi-turn policy optimization `[OBSERVED https://arxiv.org/abs/2607.04763]`. Similarly, Guided-OPD (Li et al., 2026-06, arXiv:2606.15912) introduces curriculum turn-level guidance, mixing teacher and student turns during training rollouts and decaying teacher interventions to achieve $+21.1\%$ score on interactive benchmarks `[OBSERVED https://arxiv.org/abs/2606.15912]`.

However, in both ReOPD and Guided-OPD, the teacher prefix is exclusively a *training device*; at inference time, the teacher is completely withdrawn, and the student must execute the full trajectory alone `[OBSERVED https://arxiv.org/abs/2607.04763]`.

This prefix continuation structure shares deep conceptual roots with the reinforcement learning demonstration-prefix and reverse-curriculum literature:
- **Backplay** (Resnick et al., 2018, arXiv:1807.06919) initializes the agent near the end of an expert demonstration and moves the starting state progressively backward toward the initial state as training progresses `[OBSERVED https://arxiv.org/abs/1807.06919]`.
- **Salimans & Chen** (NeurIPS 2018, arXiv:1812.03381) solved Montezuma's Revenge from a single demonstration using a reverse curriculum that steps the agent's start point backward from the goal `[OBSERVED https://arxiv.org/abs/1812.03381]`.
- **Reverse Forward Curriculum Learning** (RFCL, ICLR 2024) formalizes bidirectional state expansion from goal-adjacent demonstrations `[OBSERVED https://openreview.net/forum?id=rfcl2024]`.

Our prefix parameter sweep represents the deployment-time, compute-allocation analogue of this classical reverse-curriculum concept: rather than moving the start state backward during training to bootstrap exploration, we sweep the deployment handoff depth $m$ to identify the minimal frontier compute prefix required for downstream completion `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 7. Advice, Critique, and the Limits of Self-Correction in Small Models

An intuitive alternative for heterogeneous collaboration is an advisory channel, where an expensive hosted model inspects the small model's trajectory and provides natural-language critique or guidance without executing environment actions directly `[INFERRED]`.

However, a rigorous body of literature demonstrates that small language models suffer severe structural limitations in processing verbal self-correction and critique `[OBSERVED https://arxiv.org/abs/2310.01798]`:
- Huang et al. (ICLR 2024, "Large Language Models Cannot Self-Correct Reasoning Yet") show that without external ground-truth verifiers, prompting models to critique their own reasoning frequently degrades performance `[OBSERVED https://arxiv.org/abs/2310.01798]`.
- Kamoi et al. (TACL 2024, doi:10.1162/tacl_a_00713) present a critical survey across self-correction literature, establishing that intrinsic verbal self-correction rarely succeeds unless backed by reliable external execution feedback or explicit large-scale fine-tuning `[OBSERVED https://doi.org/10.1162/tacl_a_00713]`.
- "Small Language Models Need Strong Verifiers to Self-Correct Reasoning" (ACL Findings 2024, arXiv:2404.17140) demonstrates that SLMs lack the internal representational capacity to translate natural-language critique into corrected symbolic reasoning steps without external verification signals `[OBSERVED https://arxiv.org/abs/2404.17140]`.

While frameworks like Reflexion (Shinn et al., NeurIPS 2023) and CRITIC (Gou et al., ICLR 2024) demonstrate the utility of verbal reinforcement in frontier models, attempting to steer small open-weight executors via high-cost natural language advice yields unfavorable economics: the prompt ingestion overhead of the planner is incurred without providing deterministic state transitions `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 8. Long-Horizon Failure Mechanics and Learning-to-Defer

The dynamics of multi-turn failure propagation explain why early trajectory intervention is uniquely valuable in interactive agents `[OBSERVED https://arxiv.org/abs/2509.25370]`.

"Where LLM Agents Fail and How They Can Learn From Failures" (arXiv:2509.25370) analyzes multi-step rollouts and shows that failure is strongly governed by the *position of the first error*: once an agent deviates from the valid execution path in early exploration, single-step reactive policies almost never recover autonomously `[OBSERVED https://arxiv.org/abs/2509.25370]`. Similarly, "The Long-Horizon Task Mirage? Diagnosing Where and Why Agentic Systems Break" (arXiv:2604.11978) demonstrates that step-wise greedy reasoning policies suffer exponential degradation as task horizon increases due to unforced early planning errors `[OBSERVED https://arxiv.org/abs/2604.11978]`.

This phenomenon connects directly to classical imitation learning theory: Ross & Bagnell (AISTATS 2011, DAgger) proved that sequential prediction under standard supervised learning suffers quadratic compounding error $\mathcal{O}(\epsilon T^2)$ over horizon $T$ due to covariate shift when the agent encounters non-expert states `[OBSERVED http://proceedings.mlr.press/v15/ross11a.html]`.

In the context of multi-stage delegation, sequential learning-to-defer frameworks (Mozannar & Sontag, ICML 2020; Charusaie et al., NeurIPS 2024) establish optimal mathematical criteria for deferring decisions to an expert under non-uniform stage costs `[OBSERVED https://arxiv.org/abs/2405.19201]`. In our setting, deploying the strong model on the opening stretch ($m$ steps) acts as an error-prevention shield, bypassing the high-entropy initial setup phase where small models are most susceptible to fatal covariate drift `[INFERRED]`.

### What we add

TODO(claude): novelty verdict

---

## 9. AppWorld, Its State of the Art, and Evaluation Statistics

### 9.1 Benchmark Setting and State of the Art
AppWorld (Trivedi et al., ACL 2024 Best Resource Paper, arXiv:2407.18901) is an interactive environment comprising 9 day-to-day applications, 457 APIs, $\approx 100$ simulated users, and 750 multi-step coding tasks across 250 scenarios `[OBSERVED https://arxiv.org/abs/2407.18901]`. Tasks require generating arbitrary Python code to orchestrate multi-app workflows, evaluated via rigorous state-based unit tests and collateral damage checks `[OBSERVED https://arxiv.org/abs/2407.18901]`.

The primary metrics are Task Goal Completion (TGC, the percentage of tasks passing all test requirements) and Scenario Goal Completion (SGC, the percentage of scenarios where all constituent tasks succeed) `[OBSERVED https://arxiv.org/abs/2407.18901]`. The canonical benchmark splits comprise train (105), dev (60), test_normal (168), and test_challenge (417) `[OBSERVED https://arxiv.org/abs/2407.18901]`. (Note: the pinned data release utilized in our local repository contains 90 train tasks and 57 dev tasks across 19 scenarios $\times$ 3 difficulty variants `[OBSERVED docs/feasibility/g2_appworld.md:30-37]`).

Standard baselines from Trivedi et al. (2024) establish that standalone open models collapse on AppWorld without extensive adaptation `[OBSERVED https://arxiv.org/abs/2407.18901]`:
- GPT-4o (ReAct): 48.8% TGC / 32.1% SGC (Test-Normal); 30.2% TGC / 13.0% SGC (Test-Challenge) `[OBSERVED https://arxiv.org/abs/2407.18901]`.
- GPT-4-Turbo (ReAct): 26.8% TGC / 12.5% SGC (Test-Normal); 17.5% TGC / 5.8% SGC (Test-Challenge) `[OBSERVED https://arxiv.org/abs/2407.18901]`.
- LLaMA-3-70B (FullCodeRefl): 24.4% TGC / 17.9% SGC (Test-Normal); 7.0% TGC / 4.3% SGC (Test-Challenge) `[OBSERVED https://arxiv.org/abs/2407.18901]`.
- DeepSeek-Coder-33B-Instruct: 7.1% TGC / 1.8% SGC (Test-Normal); 2.9% TGC / 0.7% SGC (Test-Challenge) `[OBSERVED https://arxiv.org/abs/2407.18901]`.
- Mistral-7B (CodeAct): 0.0% TGC / 0.0% SGC `[OBSERVED https://arxiv.org/abs/2407.18901]`.

Recent high-compute training paradigms have advanced the state of the art on AppWorld:
- **LOOP** (2025, arXiv:2502.01600): Value-network-free PPO on a 32B model outperforms OpenAI o1 by 9 percentage points ($\approx 71\%$ TGC) `[OBSERVED https://arxiv.org/abs/2502.01600]`.
- **CANOPY** (2026-09-01, arXiv:2609.01245): Coverage-Anchored On-Policy RL achieves 86.9% Test-Normal TGC and 67.6% Test-Challenge TGC with Qwen3-14B, establishing the top public leaderboard score in Feb 2026 `[OBSERVED https://arxiv.org/abs/2609.01245]`.
- **ACE** (Agentic Context Engineering, ICLR 2026, arXiv:2510.04618): Evolving context playbooks achieve $+17.1\%$ improvement on AppWorld `[OBSERVED https://arxiv.org/abs/2510.04618]`.
- **AppWorld-UL** (ICML 2026, arXiv:2607.20536): Evaluates user-in-the-loop interaction across 516 tasks, where Claude Opus 4.7 achieves 48.6% success `[OBSERVED https://arxiv.org/abs/2607.20536]`.

**Planner Leaderboard Anchor**: On the official AppWorld leaderboard, our frozen hosted planner (`gpt-5.6-luna`) with the "kecaipan capybara" scaffold scores 85.1% TGC / 73.2% SGC on test_normal (9.3 mean interactions) and 73.4% TGC / 52.5% SGC on test_challenge `[OBSERVED docs/PLAN.md:102-103]`. In our minimal harness on the 57-task dev split under a 25-call cap, `planner_alone` achieves 68.4% TGC at 14.4 mean calls `[OBSERVED campaign/workers/lit/extracts_20260922.md:290-292]`.

### 9.2 Evaluation Statistics and Non-Inferiority Testing
Evaluating agent trajectories on structured suites with scenario-level clustering requires robust statistical inference `[OBSERVED https://arxiv.org/abs/2606.03656]`.

Reporting simple point estimates without uncertainty quantification is unreliable under grouped or clustered experimental conditions `[OBSERVED https://arxiv.org/abs/2606.03656]`. Hong et al. (2026, arXiv:2606.03656, "Beyond Point Estimates: Reliable Evaluation of Prediction Performance Metrics under Clustered Data") provide theoretical foundations for cluster-robust sandwich variance estimation and block bootstrapping under correlated observation structures `[OBSERVED https://arxiv.org/abs/2606.03656]`. In NLP evaluation, paired bootstrap resampling (Koehn, EMNLP 2004) serves as the canonical standard for paired system contrasts `[OBSERVED https://aclanthology.org/W04-3250/]`.

In our experimental methodology, claims of non-inferiority against hosted planner baselines are evaluated using Two One-Sided Tests (TOST) with a task- and scenario-clustered paired percentile bootstrap (10,000 resamples) at a pre-registered non-inferiority margin $\epsilon \in [5, 7]\text{ pp}$ across repeated random seeds `[OBSERVED docs/PLAN.md:74]`.

### What we add

TODO(claude): novelty verdict
