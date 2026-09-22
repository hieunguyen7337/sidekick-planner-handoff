# Concurrent Work: Setup Contrasts and Distinctions

**Date**: 2026-09-23  
**Scope**: Factual documentation of papers published within approximately eight weeks of 2026-09-22 addressing mid-trajectory model handoffs, replay protocols, multi-turn routing, and interactive agent training.  
**Constraint**: Factual setup differences only; no evaluative novelty claims. All factual claims are tagged `[OBSERVED <url>]` or `[INFERRED]`.

---

## 1. The Handoff Tax: Continuing Non-Native Trajectories in LLM Agents

- **Date**: 2026-08-25 `[OBSERVED https://arxiv.org/abs/2608.24358]`
- **Authors**: Roy Ganz, Mor Shpigel Nacson, Adi Kalyanpur, Ron Litman `[OBSERVED https://arxiv.org/abs/2608.24358]`
- **Identifier**: arXiv:2608.24358 `[OBSERVED https://arxiv.org/abs/2608.24358]`

### Summary
Ganz et al. evaluate mid-trajectory model handoffs (both escalation and downshift) across SWE-bench Verified (500 instances), Lost in Conversation (535 tasks), and BrowseComp (200 questions) using pairs of low-cost (LC) and high-cost (HC) models from the Claude family (Claude Haiku 4.5 / Claude Opus 4.7) and GPT family (GPT-5.6 Luna / GPT-5.6 Sol) `[OBSERVED https://arxiv.org/abs/2608.24358]`. They compare four trajectory interface representations: `Raw` (full verbatim trace), `Compact_pre` (prefix model summary), `Compact_suf` (suffix model summary), and `Traj-drop` (working tree preserved, trajectory dropped) `[OBSERVED https://arxiv.org/abs/2608.24358]`. They find that full-trajectory escalation recovers less than half of the LC-to-HC quality gap with a substantial cost premium (the "handoff tax"), whereas downshifting (HC $\rightarrow$ LC) achieves favorable cost-quality points (e.g., recovering 50% of the quality gap while retaining 80% of cost savings under raw downshift on SWE-bench Verified) `[OBSERVED https://arxiv.org/abs/2608.24358]`.

### Setup Differences from Ours
1. **Switch Point Disaggregation**: Ganz et al. sweep switch points across step-count percentiles $p \in \{5, 10, 15, 25, 35, 45, 50\}$, but report results averaged over all seven switch points; our study systematically records and plots the continuous quality-versus-handoff-depth curve across individual prefix steps $m$ `[OBSERVED https://arxiv.org/abs/2608.24358]`.
2. **Receiver Model Adaptation**: In Ganz et al., all receiving models are frozen zero-shot off-the-shelf endpoints with no task-specific fine-tuning or adapter training; our study trains specialized LoRA adapters on the open-weight executor for handoff suffix execution and includes zero-shot receiver control arms `[OBSERVED https://arxiv.org/abs/2608.24358]`.
3. **Model Tier Gap**: The LC models in Ganz et al. are large commercial frontier endpoints (Claude Haiku 4.5, GPT-5.6 Luna); our study evaluates an asymmetric gap between a hosted frontier planner (`gpt-5.6-luna`) and a local open-weight 8B executor (`ibm-granite/granite-4.2-8b`) `[OBSERVED https://arxiv.org/abs/2608.24358]`, `[OBSERVED docs/PLAN.md:21-22]`.
4. **Channel Contrast**: Ganz et al. evaluate the strong model exclusively as an active trajectory generator; our study includes a budget-matched channel contrast where identical hosted spend is provided as natural language advice versus action execution `[OBSERVED https://arxiv.org/abs/2608.24358]`.
5. **Statistical Replicates**: Ganz et al. evaluate a single episode per task configuration without repeated rollout seeds or confidence intervals (`"We run a single episode for each of the 500 tasks under every configuration and therefore do not estimate variability across repeated runs."`); our study executes paired multi-seed rollouts evaluated with scenario-clustered percentile bootstrap confidence intervals `[OBSERVED https://arxiv.org/abs/2608.24358]`, `[OBSERVED docs/PLAN.md:74]`.

---

## 2. Reach or Solve? Attributing Agentic RL Gains with Checkpoint Handoffs

- **Date**: 2026-09-17 `[OBSERVED https://arxiv.org/html/2609.19636]`
- **Authors**: Xuan Liu, Jingbin Qian `[OBSERVED https://arxiv.org/html/2609.19636]`
- **Identifier**: arXiv:2609.19636 `[OBSERVED https://arxiv.org/html/2609.19636]`

### Summary
Liu & Qian propose "checkpoint handoff" as an evaluation protocol that clones intermediate environment states reached by one policy (the reacher) and transfers them to another policy (the solver) without retraining, isolating exploration capability from terminal problem-solving `[OBSERVED https://arxiv.org/html/2609.19636]`. Evaluating on ALFWorld (with SkillRL) and TravelPlanner (with Agent-STAR) across Qwen 1.5B, 3B, and 7B backbones, they show that RL gains stem predominantly from reaching solvable state distributions (e.g., reaching solvable states 82.5% vs 13.3% on ALFWorld unseen), whereas solver success from identical cloned states exhibits smaller relative differences (95.7% vs 56.5%) `[OBSERVED https://arxiv.org/html/2609.19636]`.

### Setup Differences from Ours
1. **Model Pairing**: Liu & Qian pair checkpoints of identical parameter scale (SFT vs. RL checkpoints within the same model family, e.g., Qwen-7B to Qwen-7B); our study pairs an asymmetric hosted frontier planner with an open 8B local executor `[OBSERVED https://arxiv.org/html/2609.19636]`.
2. **Handoff Locus**: Liu & Qian evaluate handoffs at fixed task frontiers (e.g., immediately prior to the final model call on TravelPlanner, or $D=2$ steps from success on ALFWorld); our study sweeps handoff step $m$ from 0 to full trajectory `[OBSERVED https://arxiv.org/html/2609.19636]`.
3. **Cost Accounting**: Liu & Qian report state-reachability and task success percentages without measuring token consumption, API dollar costs, or compute displacement trade-offs `[OBSERVED https://arxiv.org/html/2609.19636]`.
4. **Environment Domain**: Liu & Qian evaluate text-game (ALFWorld) and synthetic plan generation (TravelPlanner); our study evaluates multi-application Python API coding on AppWorld `[OBSERVED https://arxiv.org/abs/2407.18901]`.

---

## 3. Multi-Turn On-Policy Distillation with Prefix Replay (ReOPD)

- **Date**: 2026-07 `[OBSERVED https://arxiv.org/abs/2607.04763]`
- **Authors**: Baohao Liao et al. (Microsoft) `[OBSERVED https://arxiv.org/abs/2607.04763]`
- **Identifier**: arXiv:2607.04763 `[OBSERVED https://arxiv.org/abs/2607.04763]`

### Summary
Liao et al. introduce ReOPD to address multi-turn on-policy distillation efficiency in mathematical reasoning and search environments `[OBSERVED https://arxiv.org/abs/2607.04763]`. ReOPD reuses pre-collected teacher trajectories as replayed prefixes during training: the student model acts at selected downstream steps while receiving per-step teacher supervision without generating new online teacher rollouts `[OBSERVED https://arxiv.org/abs/2607.04763]`. They identify the "prefix trap"—a distribution shift between student state occupancy and teacher supervisor reliability—and mitigate it using a step-decaying sampling schedule that emphasizes early prefixes `[OBSERVED https://arxiv.org/abs/2607.04763]`.

### Setup Differences from Ours
1. **Deployment Prefix Persistence**: In ReOPD, the teacher prefix is exclusively an offline training mechanism; at inference/deployment time, the student model executes the entire trajectory alone without a teacher prefix `[OBSERVED https://arxiv.org/abs/2607.04763]`. In our deployment architecture, the hosted planner executes the live opening prefix $m$, which persists in the runtime context inherited by the executor `[INFERRED]`.
2. **Supervision Mode**: ReOPD trains via per-step token-level cross-entropy distillation from online teacher logits; our study trains executor adapters via sequence-level SFT on handoff suffixes paired with counterfactual execution branches `[OBSERVED https://arxiv.org/abs/2607.04763]`.
3. **Environment and Actions**: ReOPD evaluates math-with-Python and text search; our study evaluates complex multi-app programmatic state manipulation on AppWorld `[OBSERVED https://arxiv.org/abs/2407.18901]`.

---

## 4. On-Policy Distillation with Curriculum Turn-level Guidance (Guided-OPD)

- **Date**: 2026-06-14 `[OBSERVED https://arxiv.org/abs/2606.15912]`
- **Authors**: Gengsheng Li et al. `[OBSERVED https://arxiv.org/abs/2606.15912]`
- **Identifier**: arXiv:2606.15912 `[OBSERVED https://arxiv.org/abs/2606.15912]`

### Summary
Li et al. develop Guided-OPD, an on-policy distillation framework for multi-turn agents on ALFWorld, ScienceWorld, and WebShop pairing a Qwen3-30B-A3B teacher with Qwen3 student models `[OBSERVED https://arxiv.org/abs/2606.15912]`. Guided-OPD mixes teacher-generated and student-generated turns during training rollouts, scheduling the teacher intervention probability along a decaying curriculum that drops to zero to recover fully autonomous student execution at test time, yielding $+21.1\%$ Score and $+25.5\%$ Success Rate over standard OPD `[OBSERVED https://arxiv.org/abs/2606.15912]`.

### Setup Differences from Ours
1. **Inference Autonomy**: In Guided-OPD, teacher interventions are annealed to zero during training to enforce standalone student inference; our system explicitly retains the hosted planner for the opening $m$ steps at test time `[OBSERVED https://arxiv.org/abs/2606.15912]`.
2. **Intervention Scheduling**: Guided-OPD samples stochastic teacher interventions throughout the trajectory according to an annealing probability schedule; our handoff regime partitions the episode deterministically into a contiguous opening prefix ($1 \dots m$) and a downstream suffix ($m+1 \dots T$) `[OBSERVED https://arxiv.org/abs/2606.15912]`.
3. **Target Benchmark**: Guided-OPD is evaluated on ALFWorld, ScienceWorld, and WebShop; our study evaluates AppWorld `[OBSERVED https://arxiv.org/abs/2606.15912]`, `[OBSERVED https://arxiv.org/abs/2407.18901]`.

---

## 5. Agentic Routing: The Harness-Native Data Flywheel

- **Date**: 2026-07-13 `[OBSERVED https://arxiv.org/abs/2607.11399]`
- **Authors**: Xinchen Liu et al. (TokenRhythm Technologies) `[OBSERVED https://arxiv.org/abs/2607.11399]`
- **Identifier**: arXiv:2607.11399 `[OBSERVED https://arxiv.org/abs/2607.11399]`

### Summary
TokenRhythm proposes harness-native step-level routing for LLM agent execution on DRACO and PinchBench, selecting models per step conditioned on execution harness state features (tool history, intermediate returns, recovery flags) from a pool including Opus 4.8, GLM 5.2, DeepSeek V4, and Gemini 3 Flash `[OBSERVED https://arxiv.org/abs/2607.11399]`. Using LightGBM classifiers, they report 93.14 quality on PinchBench (vs. 93.35 baseline) at $0.0204 vs $0.2224 cost (90.8% savings) `[OBSERVED https://arxiv.org/abs/2607.11399]`.

### Setup Differences from Ours
1. **Model Fine-Tuning**: TokenRhythm uses frozen off-the-shelf API models and trains only a tabular LightGBM router over hand-engineered features; our study trains parameter-efficient LoRA adapters on the open-weight executor `[OBSERVED https://arxiv.org/abs/2607.11399]`.
2. **Prefix Depth Sweep**: TokenRhythm routes dynamically at every step based on feature heuristics; our study systematically measures performance along a parameterized strong-model prefix depth axis ($m$) `[OBSERVED https://arxiv.org/abs/2607.11399]`.
3. **Channel Mechanism Contrast**: TokenRhythm does not evaluate or contrast natural language advice vs. action prefix execution `[OBSERVED https://arxiv.org/abs/2607.11399]`.

---

## 6. MTRouter: Cost-Aware Multi-Turn LLM Routing with History–Model Joint Embeddings

- **Date**: 2026-04 `[OBSERVED https://arxiv.org/abs/2604.23530]`
- **Authors**: Yiqun Zhang et al. `[OBSERVED https://arxiv.org/abs/2604.23530]`
- **Identifier**: arXiv:2604.23530 `[OBSERVED https://arxiv.org/abs/2604.23530]`

### Summary
MTRouter formulates turn-level routing in multi-turn conversational and agent tasks by learning joint embedding representations of dialogue history and candidate model capabilities from offline rollout corpora `[OBSERVED https://arxiv.org/abs/2604.23530]`.

### Setup Differences from Ours
1. **Routing Mechanism**: MTRouter performs embedding-based classification at discrete dialogue turns; our study evaluates structured action-prefix handoffs with contiguous suffix completion by an adapted open executor `[OBSERVED https://arxiv.org/abs/2604.23530]`.
2. **Receiver Adaptation**: MTRouter evaluates frozen candidate endpoints; our study investigates the interaction between prefix depth and receiver LoRA specialization `[OBSERVED https://arxiv.org/abs/2604.23530]`.

---

## 7. Explore More, Drift Less: Outcome-Only Reinforcement Learning Can Suffice for Long-Horizon Interactive Agents (CANOPY)

- **Date**: 2026-09-01 `[OBSERVED https://arxiv.org/abs/2609.01245]`
- **Authors**: Liming Pu et al. `[OBSERVED https://arxiv.org/abs/2609.01245]`
- **Identifier**: arXiv:2609.01245 `[OBSERVED https://arxiv.org/abs/2609.01245]`

### Summary
CANOPY proposes Coverage-Anchored On-Policy RL for training autonomous interactive agents with outcome-only rewards `[OBSERVED https://arxiv.org/abs/2609.01245]`. By combining same-task exploration scaling with action-token KL anchoring, a standalone Qwen3-14B agent achieved 86.9% Test-Normal TGC and 67.6% Test-Challenge TGC on AppWorld (topping the public leaderboard in Feb 2026) and lifted Qwen3.5-9B on SWE-bench Verified by 16.6 points `[OBSERVED https://arxiv.org/abs/2609.01245]`.

### Setup Differences from Ours
1. **System Paradigm**: CANOPY trains a single, standalone autonomous agent via 400+ GPU-hours of online on-policy RL; our study evaluates collaborative compute displacement pairing a frozen hosted planner (`gpt-5.6-luna`) with a lightweight offline-adapted 8B executor (`ibm-granite/granite-4.2-8b`) `[OBSERVED https://arxiv.org/abs/2609.01245]`, `[OBSERVED docs/PLAN.md:21-72]`.
2. **Training Regimes**: CANOPY relies on intensive online environment exploration; our study uses sample-efficient offline SFT on prefix-conditioned handoff trajectories `[OBSERVED https://arxiv.org/abs/2609.01245]`.
