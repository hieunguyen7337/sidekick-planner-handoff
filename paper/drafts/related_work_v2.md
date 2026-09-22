<!--
Draft v2 of the Related Work section (2026-09-23). Intended to replace the literature-review part of
§10 in paper/preprint_dev_20260923.md; the external score table and the non-comparability subsection
can stay in §10 or move to an appendix. Citations are pandoc-style keys into paper/bibliography.bib.
Every cited work was checked against its arXiv / proceedings page on 2026-09-23 (see "Sources checked").
-->

## 10. Related Work

**Large–small collaboration and cascades.** Pairing an expensive model with a cheap one is most often
treated as a routing decision made per query. FrugalGPT learns a cascade that queries LLM APIs in
sequence and stops once an answer is judged reliable [@frugalgpt_chen_2023], and Hybrid LLM and
RouteLLM train routers that send each query to a small or a large model [@hybrid_llm_ding_2024;
@routellm_ong_2024]. More recent work moves the decision inside the trajectory, routing per reasoning
step with an RL-trained control policy [@policy_stepwise_routing_2026], per turn from joint embeddings
of history and candidate models [@mtrouter_2026], or letting a cheap model explore for a few turns
before deciding whether to escalate [@swe_router_2026]; R2V escalates from a distilled small model to a
teacher LLM only when a calibrated step-level router predicts failure [@r2v_agent_2026]. SwiftSage is
the closest agent design: a small model fine-tuned on oracle trajectories acts by default, and a GPT-4
module for subgoal planning and grounding is invoked by heuristic rules [@swiftsage_lin_2023]. In LATM a
strong model writes reusable Python tools that a lightweight model applies [@latm_cai_2024]. Speculative decoding has a small model draft tokens
that a large model verifies [@speculative_decoding_leviathan_2023], and speculative agent planning
transfers this to agent steps [@dsp_guan_2025]. These methods decide *which* model acts, or verify every
step; we fix the schedule and vary the *form* in which the strong model's budget reaches the small one.

**Planner–executor and delegation architectures.** ReWOO writes a complete tool-use plan before any
observation and distils the planner from GPT-3.5 into a 7B model [@rewoo_xu_2023]; Plan-and-Act trains
a planner whose structured plans an executor grounds into web actions [@plan_and_act_erdogan_2025]; and
AppWorld's baselines include a plan-and-execute agent [@appworld_trivedi_2024]. Role-factorised systems
give planner, executor or critic roles to models of different sizes for a whole episode
[@coda_liu_2025; @agentcard_jiang_2026; @three_roles_2026]; in hierarchical search agents, scaling the
delegating model moves accuracy far more than scaling the executing sub-agent
[@think_big_search_small_2026]. Switching models even for a single turn shifts multi-turn outcomes
[@perf_drift_switching_2026], and handing over context reduces the rediscovery cost when a coding agent
takes over an interrupted task [@handoff_debt_2026]. Reach-or-Solve clones states one checkpoint reaches
and hands them to another to separate reaching from solving, and warns that restricting analysis to
states both policies reach selects on outcome [@reach_or_solve_2026]; our replayed prefixes use this
state-handoff protocol, with the planner as reacher and the 8B executor as solver. The closest work is
Ganz et al. [-@handoff_tax_ganz_2026], who hand SWE-bench Verified trajectories between Claude and GPT
model pairs in both directions at seven switch points, compare four trajectory-transfer interfaces with
prompted receivers, and find that downshifting a stronger model's trajectory to a cheaper one is a
favourable cost–quality point; we do not claim that result. We differ in who acts and in what is
compared: the same planner either acts or advises at a matched trigger and context, the receiver is a
local 8B model tested with and without LoRA tailoring, and the contrasts are pre-registered. Their
observation that dropping the stronger model's trajectory while keeping its edits lowers quality
complements our narrated control, which keeps the trajectory text and removes its execution.

**Feedback and critique channels.** Our advice arms descend from verbal-feedback methods: Self-Refine
has a model critique and revise its own output [@self_refine_madaan_2023], Reflexion keeps verbal
reflections on task feedback in memory across trials [@reflexion_shinn_2023], and CRITIC grounds
critiques in tool interactions [@critic_gou_2023]. Evidence on when feedback helps is mixed. Without
external feedback, LLMs struggle to self-correct reasoning [@llms_cannot_self_correct_huang_2024]; a
survey finds reliable self-correction mainly with reliable external feedback or large-scale fine-tuning
[@self_correction_survey_kamoi_2024]; and small models self-correct markedly better with a strong
GPT-4-based verifier [@slm_need_strong_verifiers_2024]. In MINT, GPT-4-simulated natural-language
feedback yields absolute gains of 2–17% across 20 tool-using models [@mint_wang_2024]. Our advice is
externally authored by a stronger model that sees the full transcript, the regime this literature
treats as favourable.

**Demonstrations and trajectory prefixes.** The action channel is closer to demonstration than to
feedback. ReAct steers agents with one or two in-context trajectories [@react_yao_2023], and Synapse
prompts with complete abstracted state–action trajectories [@synapse_zheng_2024]; our narrated control
is the task-specific case in which the exemplar is the planner's own opening on the current task.
DAgger queries the expert on states the learner visits [@dagger_ross_bagnell_2011], and
reverse-curriculum methods start episodes from demonstration states [@backplay_resnick_2018;
@salimans_chen_2018]. Agent tuning distils teacher trajectories into smaller models [@fireact_chen_2023;
@agentinstruct_zeng_2023; @agentflan_chen_2024; @agent_distillation_2025]. ReOPD replays pre-collected
teacher trajectories as prefixes during on-policy distillation and names a "prefix trap", where the
teacher's targets become unreliable on student-like histories [@reopd_liao_2026], and Guided-OPD mixes
teacher and student turns under a schedule that decays to zero [@guided_opd_2026]. In both the teacher
prefix is withdrawn before deployment; in ours it is present in every episode, so the tailored receiver
is trained for the condition it is served in.

**Tool-use benchmarks.** AppWorld's 750 tasks require code written against the APIs of nine everyday
apps [@appworld_trivedi_2024]; τ-bench adds a simulated user and domain policies [@tau_bench_yao_2025],
and BFCL scores function calls and extends to stateful multi-step settings [@bfcl_patil_2025]. The
strongest AppWorld results train or adapt a single agent, by RL [@loop_2025; @canopy_2026] or context
optimisation [@ace_2026], and are reported on the test splits. Our scores are on the dev split, in a
minimal harness, with a planner at medium reasoning effort, and are not comparable to those figures.

**Positioning.** To our knowledge, no prior work compares a stronger model's budget spent as executed
actions against the same budget spent as prose advice, at a matched trigger and context, with a small
local executor as the receiver. Prior work establishes that a cheaper model can continue a stronger
model's trajectory [@handoff_tax_ganz_2026] and supplies the state-handoff protocol we use
[@reach_or_solve_2026]; we add the channel comparison, a prefix-depth curve for 8B receivers with and
without tailoring, and a narrated control that separates what a prefix conveys from its execution. These
are paired, pre-registered contrasts on the AppWorld dev split with one planner, not benchmark results.

---

### Sources checked

All fetched 2026-09-23. "Abstract" means the claim in the draft was checked against the abstract text;
"body" means against the paper's HTML full text.

| key | URL | what was verified |
|---|---|---|
| frugalgpt_chen_2023 | https://arxiv.org/abs/2305.05176 | Title/authors; abstract: LLM cascade, matches best LLM with up to 98% cost reduction. |
| hybrid_llm_ding_2024 | https://arxiv.org/abs/2404.14618 | Router assigns queries to small or large model by predicted difficulty; ICLR 2024. |
| routellm_ong_2024 | https://arxiv.org/abs/2406.18665 | Router selects between stronger and weaker LLM, trained with preference data; ICLR 2025 (iclr.cc/virtual/2025/poster/30737). |
| policy_stepwise_routing_2026 | https://arxiv.org/abs/2605.06116 | Stepwise routing for reasoning as constrained decision problem; small control policy trained by RL. |
| mtrouter_2026 | https://arxiv.org/abs/2604.23530 | Multi-turn routing via joint history–model embeddings; ACL 2026 per arXiv comment. |
| swe_router_2026 | https://arxiv.org/abs/2607.00053 | Cheap model runs a few exploratory turns, then value-based decision to continue or escalate. |
| r2v_agent_2026 | https://arxiv.org/abs/2605.16604 | Distilled SLM + teacher LLM; calibrated step-level router escalates when residual failure risk warrants. Abstract does not say what the teacher does on escalation, so the draft does not either. |
| swiftsage_lin_2023 | https://arxiv.org/abs/2305.17390 | Swift = small LM fine-tuned on oracle trajectories; Sage = GPT-4 for subgoal planning and grounding; heuristic integration; ScienceWorld. |
| latm_cai_2024 (new) | https://arxiv.org/abs/2305.17126 | Strong model makes reusable Python tools, lightweight model uses them; ICLR 2024 (iclr.cc/virtual/2024/poster/17729). |
| speculative_decoding_leviathan_2023 | https://arxiv.org/abs/2211.17192 | Draft-then-verify sampling with an approximation model and target model; ICML 2023 oral per arXiv comment. |
| dsp_guan_2025 | https://arxiv.org/html/2509.01920 | Body: approximation agent generates candidate actions, target agent verifies; online RL predicts speculation length. |
| rewoo_xu_2023 (new) | https://arxiv.org/abs/2305.18323 | Reasoning detached from observations; offloads reasoning from 175B GPT-3.5 to 7B LLaMA. |
| plan_and_act_erdogan_2025 (new) | https://arxiv.org/abs/2503.09572 | Planner generates structured plans, Executor translates to environment actions; web navigation; ICML 2025 per arXiv journal_ref. |
| appworld_trivedi_2024 | https://arxiv.org/abs/2407.18901 | Abstract: 9 day-to-day apps, 457 APIs, 750 tasks; body (arxiv.org/html/2407.18901): baselines include Plan & Execute (PlanExec); ACL 2024. |
| coda_liu_2025 | https://arxiv.org/abs/2512.12716 | Decouples high-level planning from low-level execution, trained with RL; WSDM '26. |
| agentcard_jiang_2026 | https://arxiv.org/abs/2606.20629 | Heterogeneous role-specialised teams occupy the cost–accuracy frontier. |
| three_roles_2026 | https://arxiv.org/abs/2604.11465 | Inference-time role orchestration of one small model, no extra training, improves goal completion. |
| think_big_search_small_2026 | https://arxiv.org/abs/2607.07548 | Scaling delegation backbone ~+11 EM vs ~+2.6 for execution sub-agent. |
| perf_drift_switching_2026 | https://arxiv.org/abs/2603.03111 | A single-turn model handoff yields statistically significant directional effects in multi-turn systems. |
| handoff_debt_2026 | https://arxiv.org/abs/2606.02875 | Context-bearing handoffs reduce agent events and prompt tokens vs repository-only takeover. |
| reach_or_solve_2026 | https://arxiv.org/html/2609.19636 | Body: checkpoint handoff clones reached states; SFT vs RL checkpoints; ALFWorld and TravelPlanner; explicit warning that restricting to tasks both policies reach changes the target / induces selection. |
| handoff_tax_ganz_2026 | https://arxiv.org/html/2608.24358 | Body: SWE-bench Verified (plus LiC, BrowseComp extensions); Haiku 4.5/Opus 4.7 and GPT-5.6 Luna/Sol; switch points at 5–50th percentiles (seven), reported per point and averaged; four interfaces (Raw, Compact-pre, Compact-suf, Traj-drop); prompted receivers; downshift favourable; dropping HC trajectory while keeping edits lowers quality; no advisor role found. Note: they DO report bootstrap CIs (appendix), so the draft makes no claim about their statistics. |
| self_refine_madaan_2023 (new) | https://arxiv.org/abs/2303.17651 | Same LLM gives feedback on and refines its own output; NeurIPS 2023 (proceedings.neurips.cc). |
| reflexion_shinn_2023 | https://arxiv.org/abs/2303.11366 | Verbal reinforcement; reflective text in episodic memory across trials. |
| critic_gou_2023 | https://arxiv.org/abs/2305.11738 | Tool-interactive critiquing then revision; ICLR 2024. |
| llms_cannot_self_correct_huang_2024 | https://arxiv.org/abs/2310.01798 | LLMs struggle to self-correct without external feedback, sometimes degrade; ICLR 2024. |
| self_correction_survey_kamoi_2024 | https://api.crossref.org/works/10.1162/tacl_a_00713 | Survey: self-correction works with reliable external feedback, suited tasks, or large-scale fine-tuning; TACL 12, pp. 1417–1440. |
| slm_need_strong_verifiers_2024 | https://arxiv.org/abs/2404.17140 | Small-model self-correction gains notably with a strong GPT-4-based verifier; ACL Findings 2024. |
| mint_wang_2024 (new) | https://arxiv.org/abs/2309.10691 | GPT-4-simulated NL feedback; 20 LLMs; 2–17% absolute gains from NL feedback; ICLR 2024. |
| react_yao_2023 (new) | https://arxiv.org/abs/2210.03629 | Interleaved reasoning/acting, prompted with one or two in-context examples on ALFWorld/WebShop; ICLR 2023. |
| synapse_zheng_2024 (new) | https://arxiv.org/abs/2306.07863 | Trajectory-as-exemplar prompting with complete abstracted state–action trajectories; ICLR 2024. |
| dagger_ross_bagnell_2011 | https://proceedings.mlr.press/v15/ross11a.html | Title, authors, AISTATS 2011, PMLR 15:627–635; abstract: iterative no-regret algorithm; expert queried on states visited by the learner's (mixture) policy, confirmed via secondary descriptions (arXiv 1811.06711 survey; CMU copy ri.cmu.edu/pub_files/2011/4/Ross-AISTATS11-NoRegret.pdf) because the PMLR PDF did not parse. |
| backplay_resnick_2018 | https://arxiv.org/abs/1807.06919 | Curriculum from a single demonstration, starting near the end and moving backward. |
| salimans_chen_2018 | https://arxiv.org/abs/1812.03381 | Resets episodes to demonstration states; NeurIPS 2018 Deep RL Workshop. |
| fireact_chen_2023 | https://arxiv.org/abs/2310.05915 | Fine-tuning Llama2-7B on agent trajectories. |
| agentinstruct_zeng_2023 | https://aclanthology.org/2024.findings-acl.181/ | AgentTuning / AgentInstruct; Findings of ACL 2024. |
| agentflan_chen_2024 | https://aclanthology.org/2024.findings-acl.557/ | Agent-FLAN agent-tuning data design for Llama2-7B; Findings of ACL 2024. |
| agent_distillation_2025 | https://arxiv.org/abs/2505.17612 | Distils full task-solving behaviour of LLM agents into sLMs with retrieval and code tools; NeurIPS 2025. |
| reopd_liao_2026 | https://arxiv.org/abs/2607.04763 | Replays pre-collected teacher trajectories as prefixes during OPD; names the "prefix trap". |
| guided_opd_2026 | https://arxiv.org/abs/2606.15912 | Mixes teacher and student turns within rollouts, teacher probability decays to zero by inference. |
| tau_bench_yao_2025 (new) | https://arxiv.org/abs/2406.12045 | Simulated user + domain APIs and policy documents; ICLR 2025 (proceedings.iclr.cc). |
| bfcl_patil_2025 (new) | https://proceedings.mlr.press/v267/patil25a.html | Function-calling benchmark with AST evaluation, stateful multi-step agentic setting; ICML 2025, PMLR 267:48371–48392. |
| loop_2025 | https://arxiv.org/abs/2502.01600 | RL in target environment; 32B agent beats o1 by 9 pp on AppWorld. |
| canopy_2026 | https://arxiv.org/abs/2609.01245 | Outcome-only RL; Qwen3-14B topped the AppWorld leaderboard. |
| ace_2026 | https://arxiv.org/abs/2510.04618 | Context optimisation offline and online, +10.6% on agents; ICLR 2026 per arXiv comment. |
