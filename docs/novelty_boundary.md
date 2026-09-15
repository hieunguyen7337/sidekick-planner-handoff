# Novelty Boundary: Intervention-Aware Executor Specialization (Sidekick)

**Date**: 2026-09-15  
**Owner**: Antigravity (`agy`)  
**Scope**: Explicit novelty perimeter, contrast against neighbouring paradigms, and adversarial collapse criteria.

---

## 1. The Core Scientific Claim

The proposed method (**Sidekick / IAES**) targets a specific conjunctive setting:
> **An asymmetric, one-sided post-training regime where an economical open executor is specialized to a frozen, hosted frontier planner to maximize frontier-compute displacement at matched task quality, by optimizing execution fidelity and learned sequential escalation against downstream planner intervention costs.**

To establish genuine scientific novelty, the table below defines our exact boundary against adjacent literature, what we do differently, and the specific empirical results that would cause our contribution to collapse into prior work.

---

## 2. Adversarial Novelty Boundary Matrix

| Neighbouring Work & Paradigm | What They Did | What We Do Differently | Adversarial Collapse Condition (What Makes Our Contribution Collapse Into Theirs) | Control Arm Testing This |
|---|---|---|---|---|
| **Plan-Conditioned Supervised Fine-Tuning**<br>*(ProST, PLAN-TUNING)* | Supervised fine-tuning of open models conditioned on high-level plans or subtasks across peer models via imitation learning on successful traces. | Specialize an executor specifically to a **frozen hosted planner** (`gpt-5.6-luna`), train the executor to judge its own sufficiency (`ASK_PLANNER`), and optimize against planner intervention burden (corrections, takeovers, rework) using counterfactual DPO. | If standard plan-conditioned imitation (`sft_plan`) achieves an equivalent cost-quality Pareto frontier to `sidekick`—meaning intervention-aware credit and learned escalation add no significant gain over basic plan imitation—our contribution collapses into a simple application of ProST. | `sft_plan` (Control for H2) |
| **Residual Risk & Post-Hoc Routers**<br>*(R2V-Agent, CURA)* | Train a stable small policy first, freeze its weights, and subsequently train a separate calibrated router on the frozen policy's residual failure states to trigger teacher escalation. | Train the escalation decision **directly into the executor policy** alongside action execution and recovery under the planner's structured packet, optimizing joint planner-executor coordination rather than decoupling acting from routing. | If a two-stage sequential baseline (`router_seq`) with a frozen executor and an external risk router matches or dominates `sidekick` across the quality-versus-displacement frontier, joint policy specialization is superfluous, and our contribution reduces to a benchmark instance of R2V-Agent. | `router_seq` (Control for H4) |
| **Query-Level Cascades & Routers**<br>*(FrugalGPT, RouteLLM, Mix-of-Thought)* | Classify incoming user requests by difficulty prior to execution and dispatch the entire query to either a cheap or expensive model. | **Intra-episode step-level escalation**. The executor interacts with environment APIs, manages state transitions, and escalates dynamically midway through execution when encountering runtime uncertainty or tool errors. | If task difficulty in interactive environments is predominantly static and predictable upfront—such that a task-level classifier routing whole episodes yields equivalent cost-quality trade-offs to dynamic step-level escalation—the intra-episode delegation machinery collapses into query routing. | `planner_alone` vs. `executor_alone` baseline gap |
| **On-Policy RL on Interactive Environments**<br>*(LOOP, CANOPY, CoEvolve)* | Train open models (14B–32B) via intensive on-policy RL (PPO, Coverage-Anchored RL) directly in the environment for 400+ GPU-hours with outcome-only rewards, achieving high standalone benchmark scores (e.g., CANOPY 14B at 86.9% TGC). | Focus on **asymmetric collaborative compute displacement** using lightweight offline post-training (LoRA SFT + DPO on 105 tasks, ~120 GPU-hours total) under a frozen hosted planner. We do not attempt to build a standalone self-sufficient agent. | If an offline-trained 8B executor cannot absorb enough routine steps to displace planner compute without catastrophic quality loss, offline collaborative specialization is an unviable dead end compared to direct on-policy RL.<br>*(Note: Our numbers are not directly comparable to CANOPY/LOOP; our result establishes what offline collaboration can achieve without online RL).* | `sidekick` vs. `planner_alone` frontier curve |
| **Inference-Time Scaffolding & Multi-Role Prompting**<br>*(Three Roles One Model, AgentCARD, Tandem)* | Use prompting, multi-role decomposition (summarizer, actor, corrector), or static role allocation across frozen off-the-shelf models without updating model weights. | Train planner-specific adapter weights optimized against the specific planner's delegation style, context digest, and error-recovery patterns. | If prompt-only collaboration (`prompt_only`) or fixed periodic review (`fixed_k`) achieves the same Pareto efficiency as trained executor adapters, weight specialization is unnecessary and the problem reduces to prompt scaffolding. | `prompt_only`, `fixed_k` (Controls for H1 & H3) |
| **Hierarchical Co-Optimization with Shared Backbones**<br>*(CoDA)* | Decouple planning and execution contexts using a single, shared open-weight model serving both roles, trained end-to-end via trajectory RL (PECO). | Target the asymmetric enterprise setting where the planner is a black-box, hosted model that cannot be modified, requiring one-sided adaptation of an open subordinate executor. | If effective hierarchical delegation strictly requires joint co-adaptation of both planner and executor representations, adapting the executor alone against a frozen planner will fail to establish stable coordination. | `sidekick` vs. `planner_alone` paired contrast |

---

## 3. Summary of Falsification Matrix

Our claims stand or fall on four empirical contrasts:

1. **Against Plan-Conditioned SFT**: `sidekick` must strictly dominate `sft_plan` on the cost-quality Pareto curve (validating **H2**).
2. **Against Post-Hoc Routing**: `sidekick` must strictly dominate `router_seq` (validating **H4**).
3. **Against Fixed Review Heuristics**: Verifier escalation in `sidekick` must achieve superior calibration and lower needless asks than `fixed_k` (validating **H3**).
4. **Against Prompt Scaffolding**: `sidekick` must significantly outperform `prompt_only` at matched planner spend (validating the necessity of executor training).
