# Intervention-Aware Executor Specialization for Frozen Frontier Planners

## Instructions for Claude Code

This file is the canonical research-project specification. Read it completely before creating code, downloading datasets, selecting models, or launching experiments.

Initialize a reproducible research repository that tests the proposal below. Do not assume the proposed method works. The project must be able to falsify the central hypothesis, reproduce the strongest adjacent baselines, and preserve raw evidence needed for an academic paper.

Do not present "strong model plans and weak model executes" as novel. That architecture and several of its training components already exist. The potential contribution is the narrower combination of planner-specific executor post-training, intervention-sensitive optimization, learned escalation, and paired quality-constrained evaluation against the same frozen planner.

## Executive Summary

Frontier language-model agents are expensive partly because the same high-capability model performs both scarce high-level reasoning and large volumes of routine work: repository exploration, tool calls, file reading, implementation, testing, retries, and state reporting. Existing commercial and academic systems show that a stronger model can plan while a cheaper model executes. Existing research also separately covers executor specialization, strong/weak collaboration, model routing, step-level escalation, planner-executor reinforcement learning, and large-model guidance of small models.

The unresolved research question is narrower:

> Can a smaller agent be post-trained specifically for one frozen frontier planner so that it safely absorbs more long-horizon execution, causes fewer planner corrections and takeovers, and reduces frontier-model compute while remaining non-inferior to the same planner operating alone?

The proposed method, provisionally called **Intervention-Aware Executor Specialization** or **IAES**, treats the relationship between a fixed planner and a trainable executor as the learning target. The executor learns three coupled abilities:

1. interpret and faithfully ground plans produced by the selected frontier planner;
2. execute plans through tools and recover from environmental errors; and
3. request planner intervention before its uncertainty produces expensive or irreversible failure.

The key outcome is not the small model's independent benchmark score. It is **frontier-compute displacement at matched task quality**.

## Expected Research Goal

Develop and evaluate a heterogeneous agent system with:

- a frozen, substantially stronger planner available throughout inference;
- a trainable, cheaper executor conditioned on the planner's natural-language plan, constraints, success criteria, and subsequent corrections;
- an explicit `ASK_PLANNER` or escalation action;
- training signals based on task success, plan fidelity, planner corrections, planner takeovers, rework, unsafe actions, and model cost;
- a constrained objective that minimizes expensive-model use without allowing silent quality collapse; and
- an evaluation that compares the collaborative system with the identical frontier planner completing the task alone.

The project succeeds scientifically if it produces reliable evidence about whether planner-specific executor training improves the cost-quality frontier beyond strong existing baselines. A negative result is still valuable if the experiment is well controlled and reveals that generic agent tuning or a separate risk router captures most available gains.

## Core Research Gap

### Claims that are already covered

Do not claim novelty for any of the following in isolation:

- a strong model planning for a weak model;
- heterogeneous planner/executor teams;
- using a smaller model to reduce LLM inference cost;
- task-level model routing or cascades;
- training specialized planner, executor, or critic agents;
- training an executor from an orchestrator's plans;
- reinforcement learning for planner-executor collaboration;
- distilling a strong agent into a small interactive policy;
- step-level escalation from a small model to a stronger model;
- large-model insights or latent plans guiding a small model;
- capability-aware planner training; or
- a small learned orchestrator that delegates to stronger models.

### Defensible gap

The reviewed literature did not identify a work that jointly provides all of these elements:

1. **Fixed asymmetry:** a substantially more capable planner remains frozen and available at inference.
2. **Planner-specific subordinate training:** the cheaper executor's weights are adapted to the frozen planner's delegation language, correction patterns, constraints, and success criteria.
3. **Intervention-sensitive credit:** executor actions are evaluated by their downstream marginal burden on the planner, including corrections, replanning, takeovers, repeated verification, and rework.
4. **Learned sequential escalation:** the executor learns when to continue, report, request clarification, or return control during a changing tool trajectory.
5. **Quality-constrained cost optimization:** the target is frontier-compute displacement subject to non-inferiority, rather than unconstrained cost reduction or independent small-model accuracy.
6. **Paired counterfactual evaluation:** the same tasks are run with the same frozen planner alone and with the trained executor, allowing direct comparison of quality and frontier work.
7. **Long-horizon environment interaction:** evaluation includes tool use, environmental feedback, recovery, and persistent task state rather than answer completion alone.

This is a conjunctive gap. Merely combining ProST-style supervised executor tuning with an R2V-style router will probably be judged incremental. The method needs a distinctive intervention-aware learning signal, paired trajectory construction, joint optimization procedure, or theoretically principled constrained objective.

## Research Questions

### Primary question

Can planner-conditioned executor post-training reduce frontier-model computation at a fixed task-success level relative to an unadapted executor, generic agent tuning, plan-conditioned supervised tuning, and a separately trained step-level router?

### Secondary questions

1. Does explicitly penalizing planner corrections, takeovers, verification, and executor rework improve the cost-quality frontier beyond terminal success and token-cost rewards?
2. Does joint executor-and-escalation optimization outperform training a fixed executor first and a router afterward?
3. How planner-specific are the gains? Does an executor trained with planner A retain its advantage with planner B?
4. Does specialization transfer to unseen task families, repositories, tools, and environmental failure modes?
5. Which tasks are planner-bottlenecked and which are executor-bottlenecked?
6. Can the escalation policy detect dangerous states before an irreversible or costly action?
7. How well calibrated is the executor's estimated need for planner intervention?
8. Does reducing planner calls introduce new security or instruction-fidelity failures?
9. Is a single executor trained across several planners more economical than planner-specific adapters?
10. How much performance headroom remains between the learned escalation policy and an oracle escalation policy?

## Hypotheses

- **H1:** Planner-conditioned executor training reduces frontier-model input tokens, output tokens, calls, and dollar cost at matched success compared with prompt-only collaboration.
- **H2:** It outperforms equally sized models tuned as autonomous agents because it spends capacity on interpreting the planner, execution, validation, and deferral rather than duplicating all frontier reasoning abilities.
- **H3:** Correction-sensitive training reduces planner rework more than a reward using only terminal success and inference cost.
- **H4:** Joint executor/escalation optimization dominates a fixed executor followed by a separately trained router on the empirical cost-quality Pareto frontier.
- **H5:** Benefits are larger in planner-bottlenecked domains and smaller where low-level execution itself requires frontier-level capability.
- **H6:** Planner-specific tuning improves in-pair efficiency but creates a measurable specialization-generalization trade-off across planners.
- **H7:** Risk calibration and explicit escalation reduce catastrophic or irreversible errors compared with confidence heuristics and fixed review intervals.

## Formal Problem Definition

Let:

- `P` be a frozen frontier planner;
- `E_theta` be a trainable economical executor;
- `V_phi` be an optional process-risk verifier;
- `s_t` be the full interaction state available to the executor at step `t`;
- `p_t` be the current plan, constraints, success criteria, and planner messages;
- `a_t` be an executor tool action, report, clarification request, or `ASK_PLANNER`;
- `Q` be task quality or success;
- `C_P` be planner cost;
- `C_E` be executor and verifier cost;
- `I` be planner intervention burden; and
- `R` be executor-caused rework or recovery cost.

The constrained deployment objective is:

```text
minimize_theta   E[C_P + lambda_E C_E + lambda_I I + lambda_R R]

subject to       Q(P, E_theta) >= Q(P_alone) - epsilon
                 Safety(P, E_theta) >= required_threshold
```

A practical Lagrangian form is:

```text
J(theta) = E[
    R_task
    + w_fidelity * R_plan_fidelity
    + w_recovery * R_recovery
    - lambda_p * C_planner
    - lambda_e * C_executor
    - lambda_c * N_corrections
    - lambda_t * N_takeovers
    - lambda_r * C_rework
    - lambda_u * N_unsafe_actions
    - lambda_x * N_unnecessary_escalations
]
```

Do not select only one multiplier setting. Sweep relevant multipliers and thresholds to estimate the full cost-quality Pareto frontier.

## Definition of Planner Intervention

Instrument intervention explicitly. At minimum, log:

- initial plan creation;
- requested clarification;
- routine progress review;
- plan revision caused by new external information;
- correction caused by executor misunderstanding;
- correction caused by executor technical error;
- correction caused by planner error or ambiguity;
- takeover because the executor cannot proceed;
- takeover because continuing would be unsafe;
- final verification;
- repeated verification caused by poor executor reporting; and
- planner work needed to undo or repair an executor action.

Separate **necessary interventions** from **avoidable interventions**. Penalizing every planner call is invalid because some calls carry essential high-level reasoning or protect task quality.

## Proposed System Protocol

### Initial planner output

The planner should produce a structured but natural-language delegation packet:

```yaml
goal: string
context: string
constraints:
  - string
success_criteria:
  - string
plan:
  - id: step_id
    objective: string
    allowed_actions: [string]
    evidence_required: [string]
    escalation_conditions: [string]
risk_level: low | medium | high
review_policy:
  required_checkpoints: [string]
  irreversible_actions_require_approval: true
```

The protocol must not over-constrain the planner so strongly that it becomes an artificial planning language. Retain a free-text rationale or notes field. Test both structured and predominantly natural-language variants.

### Executor action schema

```yaml
action_type: TOOL | REPORT | ASK_PLANNER | REQUEST_APPROVAL | COMPLETE
plan_step_id: string
reason: string
tool_name: string | null
tool_arguments: object | null
expected_observation: string | null
risk_estimate: float
plan_violation_risk: float
recoverability: reversible | costly | irreversible
evidence: [string]
```

### Planner response schema

```yaml
response_type: CONTINUE | CORRECT | REPLAN | CLARIFY | TAKE_OVER | VERIFY | COMPLETE
diagnosis: string
updated_constraints: [string]
updated_plan: object | null
executor_error: boolean | unknown
intervention_necessity: necessary | avoidable | ambiguous
```

Keep raw prompts and raw model responses in addition to parsed fields.

## Literature Review

### 1. Routing and cascades

**FrugalGPT** studies prompt adaptation, model approximation, and learned LLM cascades. It establishes that model portfolios can improve the cost-quality trade-off and reports large savings in its evaluated workloads. Its typical allocation unit is a query or completed answer rather than a changing long-horizon agent state.

- Chen, L., Zaharia, M., and Zou, J. (2023). *FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance.* <https://arxiv.org/abs/2305.05176>

**RouteLLM** learns whether to use a strong or weak model from preference data. It supplies an important query-routing baseline and a method for evaluating cost thresholds, but it does not train the weak model to execute the strong model's evolving plan.

- Ong, I., et al. (2025). *RouteLLM: Learning to Route LLMs with Preference Data.* ICLR 2025. <https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html>

**Mixture-of-Thought cascades** use weak-model consistency to decide when a stronger model is needed for reasoning. This reinforces the query-level cascade baseline.

- Yue, M., Zhao, J., Zhang, M., Du, L., and Yao, Z. (2023). *Large Language Model Cascades with Mixture of Thoughts Representations for Cost-Efficient Reasoning.* <https://arxiv.org/abs/2310.03094>

**Learning to defer** provides the statistical foundation for a learner that either predicts or delegates to an expert. This literature motivates calibrated deferral, expert-aware loss functions, and constrained cost optimization.

- Mozannar, H., and Sontag, D. (2020). *Consistent Estimators for Learning to Defer to an Expert.* ICML 2020. <https://proceedings.mlr.press/v119/mozannar20b.html>

**Relation to this project:** routing is necessary but insufficient. The difficulty of an interactive task changes after tool results, partial observations, and earlier errors. The proposed work trains both execution behavior and sequential intervention decisions under a persistent frontier plan.

### 2. Strong-weak model collaboration

**An Empirical Study on Strong-Weak Model Collaboration for Repo-level Code Generation** directly evaluates context-based, pipeline-based, and dynamic collaboration. Its strongest strategy reportedly matches strong-model performance with approximately 40% lower cost. This invalidates novelty claims based only on strong-model planning or context followed by weak-model generation.

- Gandhi, S., Naik, A., Xie, Y., and Rose, C. (2025). *An Empirical Study on Strong-Weak Model Collaboration for Repo-level Code Generation.* EMNLP 2025. <https://aclanthology.org/2025.emnlp-main.1043/>

**AgentCARD** evaluates planner, executor, and verifier role assignments under unified cost models. It finds that heterogeneous teams commonly occupy the cost-accuracy Pareto frontier and that the most capability-sensitive role depends on the domain. Some domains are planner-bottlenecked; others are executor-bottlenecked.

- Jiang, Y., et al. (2026). *Specialize Roles, Mix Deployments: Pushing the Cost-Accuracy Frontier of LLM Agent Teams.* <https://arxiv.org/abs/2606.20629>

**Relation to this project:** both are required inference-time baselines. AgentCARD also requires role swaps or bottleneck diagnostics; the project must not assume a strong planner is always the optimal allocation.

### 3. Role-specialized executor training

**ProST** is the closest precedent for plan-conditioned executor training. It uses orchestrator, executor, and critic roles in AppWorld. The executor receives a subtask and corresponding plan, generates code actions, observes environment feedback, and interacts with the critic. Role-specific small models are trained using progressive subtask training. The work evaluates heterogeneous allocations such as 14B-7B-7B and 7B-14B-14B and plots accuracy against estimated FLOPs.

- Bijoy, B. S., et al. (2025). *ProST: Progressive Sub-task Training for Pareto-Optimal Multi-Agent Systems.* IJCNLP-AACL 2025. <https://aclanthology.org/2025.ijcnlp-long.179/>

Why it does not fully answer this project:

- all roles are trainable small/open models rather than one fixed frontier planner paired with a subordinate;
- the central method is progressive supervised trajectory training;
- it has a critic but no learned frontier escalation action;
- it does not optimize the marginal intervention burden imposed on the same planner; and
- it does not use paired planner-alone versus collaboration runs as the primary quality constraint.

**CoDA** separates planner and executor contexts and jointly optimizes both roles with trajectory-level reinforcement learning. A shared model backbone serves both roles. It provides strong evidence that context separation and joint planner-executor credit assignment matter.

- Liu, X., et al. (2025). *CoDA: A Context-Decoupled Hierarchical Agent with Reinforcement Learning.* <https://arxiv.org/abs/2512.12716>

**Multi-Agent Reinforcement Learning for Collaborative LLMs** and related multi-agent RL work reduce the novelty of generic claims about applying RL to collaboration.

- Zhao, Y., et al. (2026). *Multi-Agent Reinforcement Learning for Collaborative LLMs.* ICLR 2026. <https://openreview.net/forum?id=IdF6JqXWzx>

**Relation to this project:** ProST must be reproduced or approximated as the executor-training baseline. CoDA motivates joint credit assignment but differs because the planner is neither larger nor frozen.

### 4. Interactive small-model escalation

**R2V-Agent** is the closest precedent for learned step-level help seeking. It trains a stable small policy using behavioral cloning on teacher trajectories, verifier-guided DPO, and consistency regularization. After freezing the small policy, it trains a calibrated stateful router on residual failures. It evaluates HumanEval+, TextWorld, and TerminalBench and reports strong reliability-cost trade-offs.

- Hemadri, R. V., et al. (2026). *R2V-Agent: Teaching SLMs When to Ask for Help.* <https://arxiv.org/abs/2605.16604>

Why it does not fully answer this project:

- it centers a small acting policy plus teacher escalation rather than an explicit persistent frontier-generated plan;
- executor learning and router learning are sequential rather than jointly optimized;
- its main novelty is calibrated residual-risk routing; and
- it does not optimize planner corrections, takeover, rework, or planner-specific delegation fidelity.

**CURA** and related runtime-risk systems show that frozen agent pipelines can be monitored for escalation or stopping with statistical false-alarm control. Include this family when designing safety alarms and calibration, even if it remains separate from the executor's learned policy.

- *CURA: Certified Runtime Alarms for Computer-Use Agents.* <https://arxiv.org/abs/2608.27808>

**Relation to this project:** implement an R2V-like sequential pipeline as a primary baseline. Joint optimization must show gains beyond it. Consider a frozen external alarm as an additional safety baseline.

### 5. Guided reasoning and hierarchical distillation

**Tandem** uses a large mentor to generate progressively richer reasoning insights and a small model to complete the solution. A sufficiency classifier determines whether more guidance is required. The paper reports favorable cost-performance results on mathematics and code generation.

- Fu, Z., et al. (2026). *Tandem: Riding Together with Large and Small Language Models.* Findings of ACL 2026. <https://aclanthology.org/2026.findings-acl.2098/>

**Latent-Guided Reasoning** explicitly separates a large implicit thinker and a small explicit executor. The executor learns to realize a large model's latent cognitive guidance. This is philosophically close to the project, but both sides are trained and the executor produces reasoning and answers rather than long-horizon tool trajectories.

- Chen, H., et al. (2026). *Latent-Guided Reasoning: Empowering Small LLMs with Large-Model Thinking.* ICLR 2026. <https://proceedings.iclr.cc/paper_files/paper/2026/hash/6958e9d0f5a76d54ff97da8c45f4d52e-Abstract-Conference.html>

**Sub-goal Distillation** uses large-model subgoals to train a lightweight hierarchical agent, but the teacher is removed during inference.

- Hashemzadeh, M., et al. (2025). *Sub-goal Distillation: A Method to Improve Small Language Agents.* <https://proceedings.mlr.press/v274/hashemzadeh25a.html>

**PLAN-TUNING** distils planning trajectories and uses supervised and reinforcement-learning objectives to improve a smaller independent reasoner.

- Parmar, M., et al. (2025). *PLAN-TUNING: Post-Training Language Models to Learn Step-by-Step Planning for Complex Problem Solving.* EMNLP 2025. <https://aclanthology.org/2025.emnlp-main.1087/>

**EAGLET** trains a plug-and-play global planner with an executor-capability-gain reward. This is the mirror image of the proposal: it adapts the planner to the executor rather than the executor to a fixed planner.

- Si, S., et al. (2026). *A Goal Without a Plan Is Just a Wish: Efficient and Effective Global Planner Training for Long-Horizon Agent Tasks.* ACL 2026. <https://aclanthology.org/2026.acl-long.1116/>

**Relation to this project:** the paper cannot claim that training a small model to consume a large model's plan is wholly new. The distinction is interactive tool execution, the frozen inference-time planner, intervention-aware credit, and quality-constrained compute displacement.

### 6. Learned orchestration

**HuggingGPT** uses a large language model for task planning and model selection, invokes specialist models, and synthesizes their outputs. It established the controller/expert architecture without training a subordinate model for one planner.

- Shen, Y., et al. (2023). *HuggingGPT: Solving AI Tasks with ChatGPT and Its Friends in Hugging Face.* NeurIPS 2023. <https://arxiv.org/abs/2303.17580>

**Conductor** trains a small model with reinforcement learning to select and instruct stronger agents. Its learned component is the manager, not the subordinate executor.

- Nielsen, S., et al. (2026). *Learning to Orchestrate Agents in Natural Language with Reinforcement Learning.* ICLR 2026. <https://openreview.net/forum?id=U23A2BUKYt>

**Relation to this project:** learned orchestration is the reverse direction of adaptation. It is adjacent, not identical. A possible later extension jointly trains a small orchestrator adapter and an executor, but this should not be part of the minimum viable paper.

### 7. Speculative decoding

Speculative decoding uses a smaller draft model to propose tokens and a target model to verify them in parallel. Under the algorithm's conditions, this can preserve the target distribution exactly while accelerating decoding.

- Leviathan, Y., Kalman, M., and Matias, Y. (2023). *Fast Inference from Transformers via Speculative Decoding.* ICML 2023. <https://proceedings.mlr.press/v202/leviathan23a.html>

This is a useful analogy but not an agent-level guarantee. When a planner delegates many actions without observing them, it cannot verify omitted evidence or unnoticed errors. This paper must describe capability preservation as empirical non-inferiority on a defined distribution, never as exact preservation.

### 8. Planner-executor robustness

**PEAR** evaluates utility and adversarial vulnerability in planner-executor systems. It reports that weakening the planner often harms clean performance more than weakening the executor and that planner attacks are particularly consequential.

- Dong, S., et al. (2026). *PEAR: Planner-Executor Agent Robustness Benchmark.* Findings of EACL 2026. <https://aclanthology.org/2026.findings-eacl.237/>

**Actor-observer asymmetry** work examines how agents attribute failure differently when acting versus auditing. Its planner-executor examples highlight ambiguity between high-level directives and low-level implementation.

- Li, B., et al. (2026). *Taming Actor-Observer Asymmetry in Agents via Counterfactual Evaluation.* ACL 2026. <https://aclanthology.org/2026.acl-long.1104/>

**Relation to this project:** distinguish planner-caused, executor-caused, environment-caused, and ambiguous interventions. Include adversarial and ambiguous plans, prompt injection, corrupted observations, and recovery tests.

## Product Evidence and Its Proper Role

Commercial systems reportedly use similar asymmetric execution structures, including frontier leads with cheaper sidekicks and frontier planners with inexpensive workers. These product results motivate economic relevance, but public materials generally do not expose sufficient training data, objectives, model weights, or controlled ablations.

Do not use product claims as proof of the method. Mention them only as evidence that industry has independently identified the cost opportunity. The academic contribution must be supported by reproducible models, public benchmarks, transparent cost accounting, and controlled baselines.

## Baselines

Every serious experiment should include the following where technically feasible.

### Essential references

1. **Frozen planner alone:** the frontier model plans, executes, observes, recovers, and completes every task.
2. **Small executor alone:** the economical model completes the task with no planner.
3. **Prompt-only planner-worker:** the frozen planner delegates to an unadapted small executor using the same protocol as IAES.
4. **Generic autonomous-agent tuning:** the same small backbone is tuned to solve tasks independently.
5. **Plan-conditioned SFT:** the executor is supervised on successful plan/action trajectories without intervention-aware reward.
6. **ProST-style progressive tuning:** progressively expand the trained trajectory/subtask coverage.
7. **R2V-style sequential routing:** train or distil the executor first, freeze it, then train the step-level risk router.
8. **Query-level router:** choose small or frontier model before a task begins.
9. **Fixed review intervals:** planner reviews every `k` executor actions for several values of `k`.
10. **Role swap:** weak planner with strong executor.
11. **Oracle escalation:** escalate at steps known after the fact to cause failure or expensive recovery.
12. **Equal-cost self-consistency:** give the small model additional samples or attempts equal to the collaborative system's cost.

### Ablations

Remove or vary one element at a time:

- planner-specific training data;
- natural-language plan text;
- structured success criteria;
- correction penalty;
- takeover penalty;
- rework penalty;
- unsafe-action penalty;
- explicit escalation action;
- process verifier features;
- joint optimization;
- plan perturbation training;
- correction trajectory training;
- planner identity token or adapter;
- final frontier verification;
- persistent versus ephemeral executor context; and
- planner-specific adapter versus universal executor weights.

## Recommended Environments

### Minimum viable paper

Use two interactive domains:

1. **AppWorld** because ProST uses it and tasks have programmatic state-based evaluation.
2. **TerminalBench** because R2V-Agent uses it and tasks involve long-horizon terminal interaction.

### Stronger paper

Add one repository-level coding benchmark such as an uncontaminated or carefully time-filtered SWE-bench variant. Repository tasks directly test whether expensive planning can be separated from exploration, implementation, and testing.

### Optional domains

- WebArena or BrowserGym for web interaction;
- TextWorld for controlled sequential risk and oracle analysis;
- τ-bench for tool-agent behavior and policy adherence;
- OSWorld for computer use, if infrastructure and safety isolation are adequate.

Do not begin with too many domains. First validate instrumentation and paired cost accounting on a small, deterministic subset.

## Model Selection

Use open or reproducibly callable models wherever possible.

### Planner requirements

- clearly stronger than the executor on the selected task;
- frozen model version and prompt throughout primary experiments;
- accessible token accounting;
- stable API or local checkpoint;
- supports tool planning and structured outputs; and
- terms allow research evaluation and storage of necessary metadata.

### Executor requirements

- approximately 3B to 14B parameters for the first study;
- supports LoRA or QLoRA;
- competent at tool calling and code generation before adaptation;
- permissive enough for releasing adapters and evaluation code;
- fits available training hardware; and
- has a tokenizer and chat template that can encode planner packets reliably.

### Pair selection rule

Before training, run a pilot factorial study:

```text
planner ∈ {strong_A, strong_B}
executor ∈ {small_A, small_B}
allocation ∈ {
    strong-alone,
    small-alone,
    strong-plan/small-execute,
    small-plan/strong-execute
}
```

Choose primary pairs with a meaningful planner-executor capability gap and evidence that the domain is at least partly planner-bottlenecked.

## Data Collection

### Paired trajectory design

For each task and seed, collect:

1. a frontier-planner-alone trajectory;
2. a prompt-only frontier-planner plus base-executor trajectory;
3. optional role-swapped and fixed-review trajectories; and
4. counterfactual branches around intervention points.

The planner-alone run is the quality and cost reference. The collaborative run reveals which frontier work can be displaced. Counterfactual branches estimate whether a planner intervention was necessary and what would have happened had the executor continued.

### Required event log

Use append-only JSONL or Parquet events with stable schemas. Each event should include:

```yaml
run_id: string
task_id: string
seed: integer
timestamp: string
system_variant: string
planner_model: string
executor_model: string
planner_prompt_hash: string
executor_checkpoint: string
event_index: integer
actor: USER | PLANNER | EXECUTOR | VERIFIER | TOOL | EVALUATOR
event_type: string
plan_step_id: string | null
raw_input: string | object
raw_output: string | object
parsed_action: object | null
tool_result: object | null
input_tokens: integer
output_tokens: integer
cached_tokens: integer | null
latency_ms: number
nominal_cost_usd: number
error_type: string | null
intervention_type: string | null
intervention_necessity: string | null
reversible: boolean | null
environment_state_hash: string | null
git_commit: string
config_hash: string
```

Never overwrite raw trajectories. Store derived annotations separately with annotator, version, timestamp, and confidence.

### Training examples

Construct several example types:

- clean delegated segments;
- executor failures followed by planner correction;
- recoverable tool failures;
- necessary escalations;
- unnecessary escalations;
- cases where the planner is wrong or ambiguous;
- irreversible actions requiring approval;
- prompt-injection and untrusted-observation cases; and
- matched positive/negative continuation pairs around the same state.

Avoid training only on successful clean traces. That produces imitation without recovery or calibrated deferral.

## Training Plan

### Stage 0: instrumentation pilot

- implement the full protocol and event schema;
- run 20 to 50 tasks with no training;
- verify deterministic evaluation where possible;
- reconcile token counts with provider billing;
- label a sample of interventions manually; and
- confirm that failures can be attributed with reasonable agreement.

Do not start expensive training until instrumentation passes.

### Stage 1: supervised warm start

Train the executor on planner-conditioned successful actions and reports. Include corrected trajectories where the target is the post-correction action. Consider loss masks so invalid or known-failing actions are not imitated.

Compare:

- generic autonomous-agent SFT;
- plan-conditioned SFT;
- progressive subtask SFT; and
- SFT with correction and recovery examples.

### Stage 2: risk verifier

Train `V_phi(s_t, p_t, a_t)` to estimate:

- probability of eventual task failure if the executor continues;
- probability of plan or constraint violation;
- expected recovery cost;
- probability that planner intervention has positive expected value; and
- probability that an action is irreversible or unsafe.

Use calibrated probabilities. Report Brier score, expected calibration error, reliability diagrams, AUROC, AUPRC, and false-negative rates in high-risk strata.

### Stage 3: intervention-aware preference optimization

Construct chosen/rejected pairs from counterfactual branches and corrections. Examples:

- chosen: safe executor continuation; rejected: unnecessary planner call;
- chosen: planner escalation before an irreversible mistake; rejected: risky continuation;
- chosen: action aligned with the plan; rejected: action later corrected by the planner;
- chosen: concise evidence-rich report; rejected: report that triggers repeated verification.

Start with DPO or another stable offline preference method before online RL.

### Stage 4: constrained online optimization

If resources allow, optimize the executor and escalation action online. Use constrained policy optimization, a primal-dual method, or a Lagrangian sweep. Terminal task reward alone is too sparse; combine it with verified intermediate rewards while guarding against reward hacking.

Keep the planner frozen. If planner prompts change during method development, version them and rerun all primary baselines.

### Stage 5: calibration

Choose escalation thresholds only on validation data. Predeclare the non-inferiority margin and safety thresholds before final test evaluation.

## Evaluation Metrics

### Primary metrics

#### Task quality

- task success rate;
- scenario success rate where applicable;
- accepted patch rate;
- fraction of environment assertions passed;
- constraint adherence; and
- unsafe or irreversible action rate.

#### Frontier-compute displacement

```text
FCD = 1 - C_frontier(collaboration) / C_frontier(frontier_alone)
```

Report separate variants for:

- frontier input tokens;
- frontier output and hidden reasoning tokens when observable;
- frontier calls;
- frontier wall-clock time;
- frontier dollar cost; and
- total system cost including executor, verifier, tools, and retries.

Do not report only nominal API dollars. Prices change and can obscure mechanism.

#### Quality-constrained cost

Estimate the minimum total cost at which the lower confidence bound on collaborative quality satisfies:

```text
Q_collaboration >= Q_frontier_alone - epsilon
```

#### Intervention burden

- corrections per successful task;
- replans per successful task;
- takeovers per successful task;
- planner verification tokens;
- avoidable intervention rate;
- executor-caused rework tokens and actions; and
- time to recovery after first error.

#### Escalation quality

- AUROC and AUPRC;
- Brier score;
- expected calibration error;
- false-negative rate for dangerous states;
- unnecessary escalation rate;
- cost-weighted regret relative to oracle escalation; and
- oracle gap.

### Secondary metrics

- total trajectory length;
- tool-call count;
- invalid action rate;
- repeated-action rate;
- plan-step completion accuracy;
- evidence completeness;
- latency percentiles;
- GPU memory and local serving cost;
- cross-planner transfer loss;
- out-of-domain success;
- robustness under plan paraphrase; and
- robustness under environmental perturbation.

## Statistical Analysis

- Use the task instance as the experimental unit.
- Pair system runs on the same tasks and, where possible, the same stochastic seeds.
- Use paired bootstrap confidence intervals for quality and cost differences.
- For binary success, use paired tests or hierarchical logistic regression with task and seed effects.
- Predeclare a non-inferiority margin `epsilon`; justify it using domain consequences and baseline variance.
- Report confidence intervals for frontier-compute displacement and total cost, not only point estimates.
- Plot complete cost-quality curves and identify Pareto-efficient points.
- Correct for multiple comparisons in secondary ablations or clearly label them exploratory.
- Perform power analysis after the instrumentation pilot using observed paired variance.
- Report failure counts and denominators for every filtered subset.

## Robustness and Safety Evaluation

Test at least:

1. ambiguous planner instructions;
2. conflicting constraints;
3. omitted success criteria;
4. plan paraphrases;
5. corrupted or truncated tool observations;
6. flaky tool calls;
7. unexpected environment-state changes;
8. prompt injection in retrieved or viewed content;
9. an incorrect planner assumption;
10. irreversible actions requiring approval;
11. long-context accumulation; and
12. out-of-distribution task families.

Attribute failures to planner, executor, environment, protocol, verifier, or ambiguous causes. Use blinded human review for a stratified sample. Measure inter-annotator agreement.

## Repository Structure

Initialize approximately this structure, adapting only when the selected framework requires it:

```text
.
├── AGENTS.md
├── README.md
├── RESEARCH_PROJECT_SPEC.md
├── CITATION.cff
├── LICENSE
├── pyproject.toml
├── uv.lock or equivalent lockfile
├── configs/
│   ├── models/
│   ├── environments/
│   ├── systems/
│   ├── training/
│   └── evaluation/
├── docs/
│   ├── literature_matrix.md
│   ├── novelty_boundary.md
│   ├── protocol.md
│   ├── data_governance.md
│   ├── experiment_registry.md
│   └── paper_outline.md
├── src/iaes/
│   ├── agents/
│   │   ├── planner.py
│   │   ├── executor.py
│   │   ├── verifier.py
│   │   └── router.py
│   ├── protocols/
│   │   ├── schemas.py
│   │   └── messages.py
│   ├── environments/
│   ├── trajectories/
│   ├── annotations/
│   ├── rewards/
│   ├── training/
│   ├── evaluation/
│   ├── cost/
│   └── cli/
├── scripts/
│   ├── run_pilot.py
│   ├── collect_trajectories.py
│   ├── build_training_data.py
│   ├── train_executor_sft.py
│   ├── train_verifier.py
│   ├── train_preferences.py
│   ├── train_online.py
│   ├── evaluate.py
│   └── make_paper_tables.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── protocol/
│   ├── cost/
│   └── reproducibility/
├── data/
│   ├── README.md
│   ├── raw/          # ignored; immutable external/raw traces
│   ├── interim/      # ignored
│   ├── processed/    # ignored unless safely releasable
│   └── samples/      # tiny public fixtures only
├── artifacts/        # ignored except manifests and small tables
├── results/
│   ├── manifests/
│   ├── metrics/
│   ├── tables/
│   └── figures/
└── paper/
    ├── manuscript/
    ├── figures/
    ├── tables/
    └── bibliography.bib
```

## Engineering Requirements

### Reproducibility

- Pin dependencies and model revisions.
- Store a config snapshot and hash for every run.
- Record git commit, dirty-worktree state, hardware, driver, CUDA, framework, seed, and environment version.
- Separate raw events from derived metrics.
- Make evaluation idempotent.
- Never depend on notebook state for primary results.
- Generate tables and plots from machine-readable result files.
- Add smoke-test fixtures requiring no paid API calls.
- Mock model providers in unit tests.

### Cost accounting

Create a provider-independent cost interface. Track tokens and latency even when dollar prices are missing. Version price schedules by date. Distinguish:

- planner input;
- planner output;
- cached planner input;
- executor input and output;
- verifier cost;
- embedding or retrieval cost;
- tool cost;
- failed and retried calls; and
- local GPU amortization assumptions.

### Data safety

- Keep credentials outside the repository.
- Redact secrets, personal information, and proprietary source code from traces.
- Treat tool observations as untrusted.
- Run executable actions in isolated environments.
- Require approval gates for irreversible real-world actions.
- Document dataset licenses and provider terms.
- Do not commit raw commercial-model reasoning traces if terms prohibit it.

### Code quality

- Use typed schemas for all protocol events.
- Validate parsed model output and retain raw fallback text.
- Use structured logging.
- Add explicit timeouts, retries, and retry budgets.
- Test cost calculations and event ordering.
- Avoid hiding exceptions that would bias success statistics.
- Treat parser failure as an observable result, not a silently repaired success.

## Initial Implementation Milestones

### Milestone 1: repository and literature foundation

Deliver:

- repository skeleton;
- environment and dependency lock;
- literature matrix and BibTeX entries;
- novelty-boundary document;
- experiment registry template;
- model/provider abstractions; and
- contribution statement that avoids all unsafe novelty claims.

Acceptance criteria:

- tests run in a clean environment;
- citations resolve to primary sources;
- no method claim exceeds the evidence in this specification; and
- every planned experiment maps to a research question.

### Milestone 2: protocol and event instrumentation

Deliver:

- planner, executor, verifier, and tool interfaces;
- validated message schemas;
- append-only event logging;
- cost accounting;
- task-run manifest;
- replay utility; and
- deterministic mock environment.

Acceptance criteria:

- one run can be replayed from logged events;
- token and cost totals reconcile with raw calls;
- every intervention has a typed event; and
- raw outputs survive parsing errors.

### Milestone 3: untrained pilot

Deliver:

- planner-alone, executor-alone, prompt-only collaboration, fixed review, and role-swap systems;
- 20 to 50 paired task runs;
- preliminary cost-quality curves;
- intervention annotation guide; and
- failure taxonomy.

Go/no-go checks:

- the planner materially outperforms the executor;
- prompt-only delegation moves some work to the executor;
- intervention events occur often enough to learn from;
- programmatic task evaluation is reliable; and
- the selected domain is not purely executor-bottlenecked.

If these checks fail, change the task/model pair before training.

### Milestone 4: supervised baselines

Deliver:

- generic autonomous-agent SFT;
- plan-conditioned SFT;
- correction/recovery SFT;
- ProST-style progressive training; and
- controlled evaluation with identical inference protocol.

Acceptance criteria:

- checkpoints are reproducible;
- training examples do not cross evaluation splits;
- gains are reported with paired confidence intervals; and
- executor quality is separated from routing effects.

### Milestone 5: verifier and R2V-style baseline

Deliver:

- process-risk labels;
- calibrated verifier;
- separately trained step router;
- reliability plots;
- oracle router; and
- threshold sweeps.

Acceptance criteria:

- calibration is measured on held-out data;
- dangerous false negatives are separately reported;
- router comparisons use the same frozen executor; and
- the oracle gap is known.

### Milestone 6: IAES method

Deliver:

- intervention-aware preference dataset;
- correction/takeover/rework reward components;
- joint executor and escalation training;
- multiplier and threshold sweeps; and
- full ablations.

Acceptance criteria:

- method beats or meaningfully differs from plan-conditioned SFT and the R2V-style baseline;
- cost reductions do not result from silent quality loss;
- reward hacking checks pass; and
- failed runs remain included in evaluation denominators.

### Milestone 7: generalization and safety

Deliver:

- cross-planner transfer;
- unseen-domain or unseen-task evaluation;
- role swaps;
- perturbation suite;
- security and irreversible-action tests; and
- attribution analysis.

Acceptance criteria:

- primary conclusions survive at least one out-of-distribution setting;
- specialization costs are quantified;
- safety performance is not worse than declared thresholds; and
- claims are narrowed if generalization fails.

### Milestone 8: paper artifacts

Deliver:

- frozen experiment manifests;
- publication tables and figures generated from result files;
- statistical analysis notebook or script;
- manuscript outline and related-work draft;
- limitations and reproducibility statements; and
- release checklist.

## Minimum Publishable Experiment

If resources are limited, implement:

- one frozen strong planner;
- one 7B to 14B trainable executor;
- AppWorld and TerminalBench;
- planner-alone, small-alone, prompt-only, generic SFT, plan-conditioned SFT, ProST-style, R2V-style, fixed-review, and oracle baselines;
- supervised warm start followed by intervention-aware DPO;
- an explicit `ASK_PLANNER` action;
- paired non-inferiority analysis;
- cost-quality Pareto curves;
- correction, takeover, rework, and calibration metrics; and
- one perturbation suite.

This is sufficient only if IAES yields a statistically and economically meaningful gain over both ProST-style executor tuning and R2V-style routing at matched quality.

## Stronger Study

For a stronger conference submission, use:

- two frozen frontier planners;
- two executor sizes;
- at least three domains;
- planner-specific and mixture-trained executors;
- cross-planner transfer;
- role bottleneck analysis;
- online constrained RL after offline training;
- counterfactual intervention branches;
- adversarial and ambiguous-plan evaluation;
- external runtime alarms;
- human failure attribution; and
- public release of non-sensitive collaboration traces and evaluation infrastructure.

## Expected Figures and Tables

Prepare code to generate these automatically:

1. cost versus task-success Pareto frontier;
2. frontier-compute displacement versus non-inferiority margin;
3. planner tokens divided into planning, correction, replanning, takeover, and verification;
4. escalation reliability diagram;
5. learned versus oracle escalation curve;
6. correction and rework breakdown by failure source;
7. cross-planner transfer matrix;
8. role-swap performance by domain;
9. perturbation and safety results;
10. ablation table;
11. full baseline comparison; and
12. example collaboration trajectory showing a successful local continuation and a necessary escalation.

## Threats to Validity

### Moving models and prices

Frontier models, inference implementations, and prices change. Freeze exact model identifiers, prompts, dates, token records, and price schedules. Report mechanism-independent units as well as dollars.

### Contamination

Executors may have seen benchmark tasks or repository solutions. Prefer held-out, time-filtered, generated, or contamination-audited tasks. Report contamination controls.

### Planner leakage and overfitting

The executor may memorize one planner's phrasing. Test paraphrases, unseen plan formats, another planner, and mixture training.

### Evaluator bias

LLM judges may favor the planner's wording. Prefer programmatic environment assertions. Use blinded humans for ambiguous trajectory attribution.

### Silent quality loss

Average success can hide constraint violations, insecure actions, or irreversible mistakes. Measure them directly.

### Cost externalities

Several local models may require substantial GPU memory and serving overhead even if estimated FLOPs are low. Report end-to-end latency, memory, hardware, batching, and amortization assumptions.

### Domain-dependent roles

A strong executor may matter more than a strong planner in some domains. Include role swaps and capability-bottleneck diagnostics.

### Conjunctive novelty

Reviewers may describe IAES as "ProST plus R2V." The project must identify and empirically isolate a new contribution: counterfactual marginal-intervention credit, planner-specific correction learning, joint constrained optimization, or a new paired evaluation methodology.

## Falsification Criteria

The central hypothesis should be rejected or substantially narrowed if:

- prompt-only collaboration achieves the same frontier displacement;
- generic autonomous-agent tuning matches planner-specific tuning;
- plan-conditioned SFT matches intervention-aware training;
- a separately trained R2V-style router matches joint optimization;
- gains disappear under paired confidence intervals;
- apparent savings come from accepting lower success or safety;
- the selected domains are executor-bottlenecked;
- training works only on the same tasks used to collect trajectories;
- planner-specific gains collapse under minor plan paraphrases; or
- total system cost, latency, or hardware overhead exceeds planner-alone execution.

Do not conceal these outcomes. They determine the correct scientific conclusion.

## Paper Positioning

### Recommended working title

**Intervention-Aware Executor Specialization for Frozen Frontier Planners**

Alternative titles:

- **Training Small Executors to Displace Frontier Agent Compute**
- **Planner-Conditioned Post-Training for Cost-Constrained Agent Execution**
- **Learning When to Execute and When to Return Control**

### Safe contribution statement

> We study the complementary problem of learned execution in heterogeneous language-model agents. Given a frozen frontier planner, we post-train a smaller executor on paired collaboration trajectories so that it follows planner intent, performs long-horizon tool actions, and requests intervention when continuing locally has high expected cost or risk. We introduce an intervention-aware objective that accounts for planner corrections, takeovers, verification, and executor rework, and evaluate frontier-compute displacement under a paired non-inferiority constraint.

### Unsafe contribution statements

Do not write:

- "We are the first to separate planning and execution."
- "We are the first to use a strong planner with a weak executor."
- "We are the first to train an executor from plans."
- "We are the first to teach a small model when to call a large model."
- "We preserve all frontier capabilities."
- "Our method is lossless."
- "No prior work trains multi-agent collaboration."

### Intended contribution categories

The final paper should ideally contribute at least two of:

1. a new intervention-aware executor-training objective;
2. a paired counterfactual collaboration dataset;
3. a quality-constrained frontier-displacement evaluation protocol;
4. empirical evidence about planner-specific specialization and transfer; and
5. a reusable benchmark harness for frozen-planner/trainable-executor systems.

## Suggested Paper Structure

1. **Introduction:** economic motivation, existing asymmetric systems, precise missing question, and contributions.
2. **Related Work:** routing and cascades; strong-weak collaboration; role-specialized training; interactive deferral; hierarchical guidance; learned orchestration; agent robustness.
3. **Problem Formulation:** frozen planner, trainable executor, interventions, costs, safety, and non-inferiority.
4. **Method:** protocol, paired trajectories, intervention labels, verifier, executor optimization, and calibration.
5. **Experimental Design:** environments, models, baselines, cost accounting, perturbations, and statistics.
6. **Results:** Pareto frontiers, non-inferiority, intervention burden, calibration, transfer, role bottlenecks, and safety.
7. **Analysis:** why the executor improves, which decisions still require the planner, failure attribution, and oracle gap.
8. **Limitations:** moving models, contamination, evaluator limitations, generalization, hardware cost, and lack of exact capability guarantees.
9. **Conclusion:** evidence-supported answer to the primary research question.

## Immediate Tasks for Claude Code

Perform these tasks in order:

1. Inspect the current repository without deleting or overwriting unrelated work.
2. Check for `AGENTS.md`, existing project conventions, dependency files, and uncommitted changes.
3. Propose the smallest compatible repository initialization plan.
4. Create the research repository skeleton and preserve this file at the repository root.
5. Build a machine-readable literature matrix and `bibliography.bib` from the references above; verify bibliographic metadata against primary sources before finalizing.
6. Define typed protocol and event schemas.
7. Implement provider-agnostic planner, executor, verifier, router, environment, and cost interfaces.
8. Implement deterministic mock components and tests before live model calls.
9. Add append-only trajectory logging and run manifests.
10. Implement planner-alone, executor-alone, prompt-only collaboration, and fixed-review baselines.
11. Add a tiny local smoke-test environment and end-to-end test.
12. Write the pilot experiment configuration but do not launch expensive API or training jobs without explicit authorization.
13. Produce a short initialization report listing created files, tests run, unresolved choices, and the exact next experiment.

## Rules for Autonomous Project Work

- Do not spend money, call paid models at scale, provision cloud resources, or launch long training runs without explicit approval.
- Do not fabricate experimental results, citations, model availability, or costs.
- Verify recent model and benchmark details before coding against them.
- Preserve raw evidence and failed runs.
- Never tune on the final test set.
- Keep primary baselines on the same protocol and cost-accounting implementation.
- Prefer programmatic evaluators over LLM judges.
- Treat security and irreversible actions as first-class evaluation outcomes.
- Document every deviation from this specification.
- When evidence contradicts the proposed gap, update `docs/novelty_boundary.md` and narrow the project before continuing.

## Definition of Project Initialization Complete

Initialization is complete when:

- the repository installs reproducibly;
- all unit and smoke tests pass;
- the literature and novelty boundary are documented;
- model and environment interfaces are provider-independent;
- a complete mock planner-executor trajectory can be run and replayed;
- costs and interventions are recorded in the event log;
- baseline configurations exist;
- no expensive external experiment has been launched without approval; and
- the next step is a clearly specified 20-to-50-task untrained pilot.

## Final Research Decision

The proposed topic remains viable, but the architecture itself is not the contribution. The paper must study the learned subordinate relationship: how a small executor adapts to a fixed superior planner, when it should return control, and how much expensive planner work it removes without causing statistically or operationally meaningful quality loss.

The decisive comparison is:

```text
IAES
versus
prompt-only collaboration
versus
generic agent tuning
versus
ProST-style plan-conditioned executor training
versus
R2V-style separately trained step routing
```

If IAES does not improve that frontier, the correct conclusion is that executor-specific intervention-aware post-training adds little beyond existing methods. If it does improve the frontier and the result survives cross-domain, cross-planner, calibration, and safety tests, the project has a defensible contribution to efficient agentic inference and heterogeneous multi-agent learning.
