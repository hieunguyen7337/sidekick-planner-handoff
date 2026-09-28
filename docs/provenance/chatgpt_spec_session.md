# ChatGPT share: LLM Planner Executor Research

- Source URL: https://chatgpt.com/share/6aba3904-82ac-83ec-98dd-e3daa88a8f81
- Title: "LLM Planner Executor Research"
- Retrieval: exported from the public share link on 2026-09-28. In this public copy, share-level fields not needed for provenance and the citation markers were removed; removed lines are left empty so that line numbers match citations elsewhere in this repository.
- Retrieval time (`date -Is` immediately before the fetch): 2026-09-28T20:06:06+10:00 (saved HTML mtime 2026-09-28T20:06:14+10:00)
- Branch followed: `current_node` walked back through `parent` links; identical to `linear_conversation` (185 nodes, no forks).

## Share-level metadata

- `title`: `"LLM Planner Executor Research"`
- `create_time`: 2026-09-28T09:53:08+00:00 (1790589188.544318)
- `update_time`: 2026-09-28T09:53:10+00:00 (1790589190.390619)

- `conversation_id`: `"6aba3904-82ac-83ec-98dd-e3daa88a8f81"`

- `default_model_slug`: `"gpt-5.6-sol-wm"`












- `is_public`: `true`













## Notes on what the share payload contains

- Skipped (hidden or system), 23 in total: 1 root node with no message; 17 system message (hidden); 2 model_editable_context, empty, not flagged hidden (never rendered by the ChatGPT UI); 3 hidden assistant/model_editable_context
- 42 tool messages carry only the text `The output of this plugin was redacted.` in the public share payload; that is what is reproduced below.
- 39 assistant tool-call messages (recipient not `all`) have an empty text part in the payload.
- 3 `container.exec` calls consist only of `bash -lc apply_patch`; the patch bodies are not in the payload.
- Files the assistant produced appear only as file references (listed under the message that references them); their contents are not in the payload.
- Citation markers in assistant text (private-use Unicode characters) were removed from this public copy; their targets are not reproduced.
- Timestamps below are message `create_time` in UTC.

---

## 1. user — 2026-09-15T08:35:31+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`
- `message_source`: `null`
- `system_hints`: `[]`

Has there been paper on training or rl an llm to assist another better sota llm, even fable or astra tier, the purpose is for efficiency, we want to keep all the capabilty, but lower the price by training the smaller model to do the majority of the work so the smaller is trained on how to execute only while the larger model is training on planning only or are kept frozen

## 2. assistant — 2026-09-15T08:35:31+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

Yes—the idea has several close research lineages, but your exact formulation is unusually specific: **freeze the frontier model as a sparse planner/escalation oracle, then train a much smaller model specifically to execute its plans and invoke the frontier model only when necessary**. I’m checking the recent literature for systems that actually train the small model for that division of labor, rather than ordinary distillation or routing.

## 3. assistant — 2026-09-15T08:35:31+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 4. tool — 2026-09-15T08:35:43+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 5. tool — 2026-09-15T08:35:43+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 6. assistant — 2026-09-15T08:35:44+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 7. tool — 2026-09-15T08:35:49+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 8. assistant — 2026-09-15T08:35:54+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 11 websites

```

## 9. assistant — 2026-09-15T08:35:50+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

A few papers are already very close. The strongest match so far is not ordinary distillation: recent work explicitly **decouples planning from execution and trains the roles for collaboration**, while separate work trains **small/large cascades with RL-calibrated escalation**. The missing piece seems to be combining those two ideas into one asymmetric system where the frontier model is the planner and the small model is the learned executor.

## 10. assistant — 2026-09-15T08:35:50+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 11. tool — 2026-09-15T08:35:57+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 12. tool — 2026-09-15T08:35:57+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 13. assistant — 2026-09-15T08:35:58+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 14. tool — 2026-09-15T08:36:04+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 15. assistant — 2026-09-15T08:36:04+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 16. tool — 2026-09-15T08:36:07+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 17. assistant — 2026-09-15T08:36:14+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning summary — content_type `thoughts`, 3 item(s)]**

```text
[1] Formulating the distinction
I’m separating exact capability preservation from approximate cost reduction. Smaller models can handle routine work, while larger models remain necessary for verification or difficult cases; otherwise, quality losses can occur.

[2] Designing a training approach
I’m shaping a planner–executor system: a frozen stronger model produces structured plans, while a smaller model learns execution through supervised traces, reinforcement learning, cost penalties, checkpoints, and selective replanning. The main risks are incomplete plans, grounding failures, and recovery errors.

[3] Formulated distinctions and designed a training approach

```

## 18. assistant — 2026-09-15T08:36:08+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 19. tool — 2026-09-15T08:36:20+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 20. assistant — 2026-09-15T08:36:28+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 11 websites

```

## 21. assistant — 2026-09-15T08:36:28+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning recap]** Worked for 56s

## 22. assistant — 2026-09-15T08:36:20+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

Yes. There is now a fairly substantial research thread around this idea, but I **did not find one established method that exactly combines all the pieces you described**:

> **Frozen frontier model = planner/reasoner → specially trained small model = executor → small model handles most tokens/tool calls → it learns when execution exceeds its competence and asks the large model again.**

Several 2025–2026 papers separately cover almost every component. That makes your formulation especially interesting.

### The closest work

| Work | What it does | Relation to your idea |
|---|---|---|
| **COREA, EACL 2026** | RL-trains a small model both to reason and to know when to defer to a large model | **Very close on cost-aware collaboration** |
| **CoDA, 2025** | RL co-optimizes explicit Planner and Executor roles | **Very close architecturally**, but uses one shared model |
| **Sub-goal Distillation, 2025** | Large LLM generates subgoals; lightweight hierarchical agent learns planning + execution | Close, but removes large model entirely at inference |
| **Draft-OPD, 2026** | Trains a small draft model against feedback from a frozen target LLM | **Extremely close training philosophy**, but token-level rather than agent-level |
| **Speculative Decoding** | Small model generates; large model verifies, preserving the large model's exact distribution | Gives the strongest version of your “keep all capability” requirement |
| **RouteLLM / Learning-to-Defer** | Learns which queries need the strong model | Useful for your escalation mechanism |
| **HuggingGPT** | Large LLM plans/selects expert models, experts execute | Same planner→executor structure, but executors aren't jointly trained for it |

COREA is particularly relevant. It trains the SLM with RL, including a **confidence-calibration reward**, so the SLM attempts a problem and sends difficult cases to the LLM. It reports 16.8–21.5% lower cost than always using the LLM with less than a 2-point absolute pass@1 loss on their out-of-domain tests.

CoDA is probably the closest to your intended *division of cognition*. It explicitly separates a high-level **Planner** from a low-level **Executor** and introduces Planner-Executor Co-Optimization (PECO), using trajectory-level RL reward so the two roles become good at cooperating. Its important difference is that both roles currently come from the **same shared LLM backbone**.

Sub-goal Distillation goes even further toward hierarchical execution: an LLM labels trajectories with subgoals, after which a much smaller 770M agent learns a planning module and an execution module. The authors specifically motivate it by the cost of repeated LLM calls. In their final system, however, the original LLM is gone during inference rather than retained as the high-level brain.

### There is an even closer analogy at the token level

Speculative decoding is basically your hypothesis applied to **tokens rather than tasks**.

A cheap model says:

\[
t_1,t_2,t_3,t_4,\ldots
\]

and the huge model verifies several of them simultaneously. If they're correct, you avoid doing expensive autoregressive generation for each one.

Crucially, speculative decoding can be **lossless**: the resulting distribution remains the same as running the large model normally. Leviathan et al. demonstrated 2–3× acceleration while preserving the target model's output distribution.

And a 2026 paper, **Draft-OPD**, is even more analogous to your proposed training scheme. Instead of merely distilling static outputs from the big model, the small draft model generates its own attempts and gets feedback specifically at the places where the target rejects it. They call this **on-policy distillation**. Their reported result is over **5× lossless acceleration for thinking models** in their experiments.

That is essentially:

\[
\text{Frozen strong model}
\rightarrow
\text{feedback}
\rightarrow
\text{train assistant to become better at assisting that exact model}.
\]

What you're proposing is the **agent-level generalization** of Draft-OPD.

---

## Your version would look different from normal distillation

I think the most interesting formulation is **not**:

\[
\text{Frontier LLM}\rightarrow\text{distill everything}\rightarrow\text{small LLM}.
\]

That inevitably tries to squeeze a much more capable model into an insufficiently large model.

Instead:

\[
\boxed{
\text{Large model = intelligence}
\qquad
\text{Small model = labor}
}
\]

Suppose the request is:

> Research five papers, reproduce one experiment, inspect the code, compare results, and prepare a report.

A frontier model might produce:

```text
Goal:
Determine whether method X improves Y.

Plan:
1. Find papers satisfying A/B/C.
2. Extract methodology and reported numbers.
3. Clone implementation.
4. Run benchmark Z with configuration Q.
5. Compare results against Table 3.
6. If discrepancy >5%, investigate.
7. Return structured evidence.
```

The frontier model doesn't need to spend another 30,000 reasoning/output tokens reading files, searching repositories, calling Python, parsing tables, retrying commands, etc.

The small executor could perform:

\[
E(s_t,\text{plan})\rightarrow
\{\text{tool action},\text{result},\text{continue},\text{ask planner}\}.
\]

You would specifically RL-train it on **following plans produced by that strong model**.

This is subtly different from training a generic small agent.

---

## The RL objective is quite natural

Let

- \(P\) = frozen frontier planner
- \(E_\theta\) = trainable small executor
- \(D_\theta\) = executor's defer/replan decision
- \(C_P\) = cost of a frontier-model call
- \(C_E\) = cost of small-model computation
- \(S\) = task success/quality.

Then train:

\[
\max_\theta
\mathbb E[
S
-\lambda_P C_P
-\lambda_E C_E
].
\]

But I would add an important constraint:

\[
\text{Quality}(P+E_\theta)
\ge
\text{Quality}(P_{\text{alone}})-\epsilon.
\]

So this isn't merely RL for task success.

The problem becomes:

> **Minimize expensive-model compute subject to retaining frontier-model capability.**

And the executor's action space contains a particularly important action:

\[
\boxed{\texttt{ASK\_PLANNER}}
\]

So during training the small model learns:

> “I should execute this.”

versus

> “This step requires reasoning that I am not reliable enough to perform.”

This combines **CoDA-style planner/executor training** with **COREA/learning-to-defer-style escalation**. RouteLLM provides another related formulation for cost-sensitive strong/weak model selection; it learned routers that substantially cut expensive-model usage while attempting to retain strong-model quality.

---

## I would actually train three abilities, not one

The small executor doesn't need to become a miniature Astra/Fable-level reasoner. That would defeat the point.

It needs unusually strong capabilities in:

**Plan grounding.** Convert a high-level instruction into deterministic actions, tool calls and intermediate outputs.

**Error detection.** Recognize when an observation deviates from the planner's assumptions.

**Deferral.** Recognize situations where additional high-level intelligence has higher expected value than continuing locally.

That last capability is particularly important.

The small model might be only a 3B–14B model but become extremely good at:

```text
execute()
observe()
validate()
execute()
observe()
validate()
...
DEFER(reason, state_summary)
```

rather than being optimized for independently solving Olympiad mathematics, philosophical questions, research synthesis, etc.

So its capacity is being spent on **execution intelligence rather than general reasoning intelligence**.

---

# The important problem with “keep all capabilities”

There are two different meanings here.

With speculative decoding, you can genuinely preserve the output distribution of the large model:

\[
P_{\text{system}}(y|x)=P_{\text{large}}(y|x).
\]

That's possible because the large model verifies the generated tokens.

At the agent level, however, if the large model says:

> “Go investigate X.”

and the small model performs 50 actions without the large model seeing them, you no longer have that mathematical guarantee.

The executor could overlook something that the frontier model would have noticed.

So a practical system needs something like:

\[
P
\rightarrow E
\rightarrow E
\rightarrow E
\rightarrow
\begin{cases}
E & \text{high confidence}\\
P & \text{uncertain/novel}\\
P & \text{plan violated}
\end{cases}
\rightarrow E...
\]

rather than simply

\[
P\rightarrow E\rightarrow\text{answer}.
\]

That turns the frontier model into an **interrupt-driven cognitive supervisor**.

And that could be dramatically cheaper.

---

## Why this might matter much more for agentic models than ordinary chat

Imagine a powerful model spends:

- 2,000 tokens understanding/planning,
- 40,000 tokens navigating/searching/coding,
- 8,000 tokens correcting execution errors,
- 3,000 tokens synthesizing.

You're paying frontier-model rates for **53,000 tokens**.

But perhaps only:

\[
2,000 + 2,000 + 3,000
\]

really require frontier-level intelligence.

The other ~46k tokens could potentially be generated by an executor costing 10–50× less.

Therefore your architecture could transform the economic equation from roughly

\[
C\approx N_{\text{total}}C_\text{frontier}
\]

into

\[
C\approx
N_{\text{reasoning}}C_\text{frontier}
+
N_{\text{execution}}C_\text{small}.
\]

If the frontier model is 30× more expensive and only 10% of the trajectory actually needs it, the theoretical cost ratio becomes roughly

\[
0.1+\frac{0.9}{30}\approx0.13.
\]

About **87% cheaper**, before accounting for extra communication/verification.

That is potentially much larger than ordinary routing savings.

---

# And there is a real research gap here

After looking through the recent literature, I would distinguish the existing areas like this:

```text
Speculative decoding
    small generates → big verifies
    ✓ trained assistant
    ✓ frozen target
    ✓ exact capability preservation
    ✗ only token-level

COREA / learning-to-defer
    small attempts → escalate to big
    ✓ train small
    ✓ cost-aware RL
    ✓ heterogeneous models
    ✗ no explicit big-planner → small-executor relationship

CoDA
    planner → executor
    ✓ explicit cognitive decomposition
    ✓ joint RL
    ✗ same model/backbone
    ✗ not focused on asymmetric inference cost

Sub-goal Distillation
    big teacher → hierarchical small agent
    ✓ plan/execution decomposition
    ✓ efficiency motivation
    ✗ big model disappears at inference

HuggingGPT
    big planner → cheap/specialized workers
    ✓ correct hierarchy
    ✗ essentially no collaboration training

YOUR PROPOSAL
    frozen frontier planner
           ↓
    RL-trained cheap executor
           ↓
    learned defer/replan
           ↖──── frontier
           
    ✓ explicit heterogeneous cognition
    ✓ train assistant specifically for target planner
    ✓ cost-aware RL
    ✓ retain frontier model for hard reasoning
    ✓ optimize percentage of frontier compute eliminated
```

HuggingGPT is an early demonstration of the basic controller/executor concept: ChatGPT decomposes the request, selects expert models and lets them perform subtasks. But it doesn't solve the training problem you're describing.

There's also newer work on training models specifically to acquire **delegation intelligence**, such as SearchSwarm, which synthesizes delegation trajectories and fine-tunes a model on when/how to delegate long-horizon research work.

So the field is moving conspicuously toward your direction.

---

## I think the strongest research version is even more specific

I wouldn't frame the paper as:

> “Can small LLMs help large LLMs?”

That's already well explored.

I'd frame it as:

> **Can inference-time cognition be factorized into scarce reasoning and abundant execution, such that a frozen frontier model supplies only the scarce reasoning while a learned small executor performs the majority of a long-horizon trajectory?**

And train the executor **against one particular frozen planner**, somewhat analogous to Draft-OPD:

\[
E_0
\rightarrow
\text{rollout with }P
\rightarrow
\text{identify executor failures}
\rightarrow
\text{train}
\rightarrow
E_1
\rightarrow \cdots
\]

Instead of asking:

> “Can this 7B model become as smart as the frontier model?”

the optimization target becomes:

> **“Given instructions produced by this particular frontier model, how much of its workload can this 7B model safely remove?”**

That's a significantly easier learning problem—and potentially a very valuable one.

My read of the literature through **September 2026** is that the individual ingredients now clearly exist, including RL deferral, planner–executor RL, hierarchical distillation and on-policy training of assistants against frozen target models, but **a general-purpose heterogeneous `frozen frontier planner + RL-specialized small executor + learned replanning/escalation` system is still not a solved or standardized architecture**. It looks like a legitimate research direction rather than something already exhausted.

If you're thinking of this as a potential research project, the particularly novel part is probably **not planner/executor separation itself; it's training the smaller model to maximize _frontier-compute displacement_ under a capability-preservation constraint**. That gives you a very clean objective and a direct economic metric alongside task performance.

## 23. user — 2026-09-15T08:46:49+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`
- `message_source`: `null`
- `system_hints`: `[]`

There are actually product like the devin new swe2 model which can accomplish near astra or fable quality but with two thirds of the cost, is it trained for orchestration or is it just train on normal coding capability? Are there any publish paper on the devin model? Are there any similar paper? I know that cursor has eval have one model planning and one model execute? And sakana AI has build a basically model router and combiner in their ultra fugu? That is not our concept right? We still have a research gap?

## 24. assistant — 2026-09-15T08:46:49+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

I’ll separate the question into three parts: what is actually known about Devin’s newer SWE model training, what Cursor and Sakana are doing architecturally, and whether those systems collapse the research gap we identified. The key distinction is **generic coding competence vs. a model explicitly trained to execute another stronger model’s plans**.

## 25. assistant — 2026-09-15T08:46:49+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 26. tool — 2026-09-15T08:46:56+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 27. tool — 2026-09-15T08:46:56+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 28. assistant — 2026-09-15T08:46:57+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 29. tool — 2026-09-15T08:47:00+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 30. assistant — 2026-09-15T08:47:01+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 31. tool — 2026-09-15T08:47:05+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 32. assistant — 2026-09-15T08:47:05+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 33. tool — 2026-09-15T08:47:08+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 34. assistant — 2026-09-15T08:47:13+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 12 websites

```

## 35. assistant — 2026-09-15T08:47:08+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

The Cursor result is more important than I first thought: in August 2026 they explicitly tested **a frontier model as planner plus a cheaper/faster model as worker**, and report similar quality across model mixes with very different costs. That is almost the *inference architecture* you proposed—but it appears to be harness/orchestration engineering, not training the cheap worker specifically to execute the frontier planner. 

## 36. assistant — 2026-09-15T08:47:08+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 37. tool — 2026-09-15T08:47:16+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 38. tool — 2026-09-15T08:47:16+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 39. assistant — 2026-09-15T08:47:17+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 40. tool — 2026-09-15T08:47:20+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 41. assistant — 2026-09-15T08:47:21+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 42. tool — 2026-09-15T08:47:23+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 43. assistant — 2026-09-15T08:47:24+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 44. tool — 2026-09-15T08:47:26+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 45. assistant — 2026-09-15T08:47:27+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 46. tool — 2026-09-15T08:47:31+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 47. assistant — 2026-09-15T08:47:32+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 48. tool — 2026-09-15T08:47:38+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 49. assistant — 2026-09-15T08:47:38+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 50. tool — 2026-09-15T08:47:42+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 51. assistant — 2026-09-15T08:47:42+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 52. tool — 2026-09-15T08:47:45+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 53. assistant — 2026-09-15T08:47:46+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 54. tool — 2026-09-15T08:47:52+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 55. assistant — 2026-09-15T08:47:53+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 56. tool — 2026-09-15T08:47:55+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 57. assistant — 2026-09-15T08:47:56+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`web.run`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

_(empty text part in the share payload)_

## 58. tool — 2026-09-15T08:47:59+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`web.run`

The output of this plugin was redacted.

## 59. assistant — 2026-09-15T08:48:05+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Assessing research novelty
I’m finding that the proposal remains potentially novel, but its strongest claim should shift from inventing an agent swarm to systematically evaluating coordination, specialization, tool use, and economics against simpler baselines, using reproducible empirical methods.
```

## 60. assistant — 2026-09-15T08:48:09+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 11 websites

```

## 61. assistant — 2026-09-15T08:48:09+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

**[Reasoning recap]** Worked for 1m 19s

## 62. assistant — 2026-09-15T08:48:00+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"extended"`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `resolved_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`

Yes. After looking at the newer 2026 material, I’d revise the conclusion from my previous answer:

**the research gap still exists, but it is considerably narrower than it first appears.** In particular, **Devin Fusion and Cursor’s swarm experiments have already validated the inference-time architecture you are proposing.** What still looks underexplored is **training the cheap executor specifically for this asymmetrical relationship with a frozen frontier planner**.

### 1. SWE-2 itself is not, as far as Cognition has disclosed, an orchestration-trained executor

Cognition’s SWE-2 is much more interesting than just a normal code-finetuned model, but its public training description is still basically **single-agent agentic RL**.

SWE-2 starts from Kimi K3, a 2.8T-parameter model that had already undergone extensive RL for agentic coding. Cognition then performs additional RL in software-engineering environments. The reward explicitly incorporates both task success and inference cost:

\[
R = S-\lambda_e C
\]

where \(S\) is task success and \(C\) includes inference cost and rollout time. They also train different reasoning-effort levels together and expanded the RL environments/verifiers.

That training produces behaviors such as:

- less unnecessary repo exploration,
- earlier implementation,
- planning/todo usage,
- editing,
- testing,
- verification,
- fewer overall turns.

For example, SWE-2 medium averages 53 steps versus 127 for SWE-1.7 on FrontierCode, while scoring better.

So I would characterize SWE-2 as:

\[
\boxed{\text{cost-aware RL-trained autonomous software engineer}}
\]

rather than

\[
\boxed{\text{executor trained to follow another model's plans}}.
\]

I found **no public indication in the SWE-2 training write-up that its RL environments specifically contain Fable/Astra → SWE-2 delegation**, or that its reward measures fidelity to another model's plan. Searching the technical post for sidekick/delegation/collaboration also turns up nothing; the disclosed training is framed around SWE-2 completing the task itself.

And I did **not find a peer-reviewed/arXiv SWE-2 paper** from Cognition. Their September 10 post is unusually technical—it includes the RL objective, derivations, ablations and appendices—but at present it appears to be a technical research blog rather than a formal conference/arXiv paper.

---

# 2. But Devin **Fusion** is astonishingly close to your architecture

This is the part that changes the picture.

On September 11, Cognition explicitly described Fusion as:

> choose a frontier model for planning/review as the **lead**, and a cheaper model for execution as the **sidekick**.

Their recommended pairing is currently **Fable 5.1 + SWE-2**.

The architecture is essentially:

\[
\text{User}
\rightarrow
\boxed{\text{Fable/Astra lead}}
\rightarrow
\boxed{\text{SWE-2 sidekick}}
\]

with the responsibilities divided as:

\[
\begin{aligned}
\text{Frontier lead}:&
\quad \text{planning}\\
&\quad \text{ambiguity resolution}\\
&\quad \text{important decisions}\\
&\quad \text{review}\\[4pt]
\text{SWE-2 sidekick}:&
\quad \text{repo exploration}\\
&\quad \text{implementation}\\
&\quad \text{tests}\\
&\quad \text{mechanical execution}
\end{aligned}
\]

That is almost exactly the architecture you described. Cognition says the lead sends the sidekick a brief containing constraints and success criteria; the sidekick performs implementation/testing and reports back. The lead reviews it and can take control again.

And the numbers are quite striking:

| Configuration | Benchmark score | Cost |
|---|---:|---:|
| Fable 5.1 | 63.6 FrontierCode | $2.68 |
| **Fable 5.1 + SWE-2** | **63.5** | **$1.67** |
| Astra | 63.1 | $2.62 |
| **Astra + SWE-2** | **63.4** | **$2.34** |

On DeepSWE:

- Fable: 64.3 at $14.63
- Fusion: 63.1 at $7.88 — **46% cheaper**
- Astra: 67.6 at $7.88
- Fusion: 67.3 at $4.69 — **40% cheaper**.

So Cognition has already demonstrated something remarkably close to:

\[
\boxed{
\text{frontier intelligence}
+
\text{cheap executor}
\approx
\text{frontier quality}
}
\]

at substantially lower cost.

This is therefore **not an untouched systems idea anymore**.

But notice the important difference:

> **Fusion trains/tunes the harness around the models. It does not publicly say that SWE-2 itself was trained specifically to be Fable/Astra's executor.**

Cognition explicitly says they tune instructions and delegation boundaries differently depending on the lead/sidekick pair.

That's prompt/harness optimization.

Your proposed research asks:

> What happens if we optimize the **weights of the executor itself** for this collaboration?

That is still different.

---

# 3. And Cursor independently found almost exactly the same architecture

You remembered correctly.

Cursor's long-running agent research initially experimented with:

\[
Planner \rightarrow Executor \rightarrow Workers \rightarrow Judge
\]

and then changed architectures several times. Their eventual system uses recursive planners and workers.

More importantly, their August 2026 write-up explicitly says they tested different model allocations:

> in some runs one model did everything; in others **a frontier model planned while a fast inexpensive model carried out the work**.

And:

> **every mix produced similar quality, but costs varied enormously.**

Their role split is explicitly:

- **Planner agents:** smartest models
- **Worker agents:** generally faster and cheaper models.

So we now have at least two major production coding labs independently converging on:

\[
\boxed{
\text{expensive intelligence at tree nodes}
+
\text{cheap execution at leaves}
}
\]

That is strong empirical evidence for the underlying hypothesis.

Cursor also built a separate learned Router. That's different: Cursor Router predicts task complexity and chooses which model should handle each turn. It currently reports above-Fable-level user satisfaction at substantially lower cost by routing easier turns away from expensive models.

So Cursor actually has **both concepts**:

\[
\text{routing}
\]

and

\[
\text{planner→cheap-worker decomposition}.
\]

---

# 4. Sakana Fugu is related, but the asymmetry is basically reversed

This distinction is important.

Fugu/Conductor isn't principally:

\[
\text{smart planner}\rightarrow\text{trained cheap executor}.
\]

It's closer to:

\[
\boxed{\text{trained cheap coordinator}}
\rightarrow
\boxed{\text{collection of powerful workers}}.
\]

Their ICLR 2026 **Conductor** work trains a 7B model with RL to decide:

1. which LLM to call,
2. what instruction to give it,
3. what previous messages it should receive.

For difficult tasks it can spontaneously create planner/coder/verifier pipelines.

So:

\[
\text{Conductor}_{7B}
\rightarrow
\{\text{GPT},\text{Claude},\text{Gemini},...\}.
\]

TRINITY is even smaller: approximately a 0.6B coordinator plus a tiny routing head chooses an LLM and gives it a Thinker, Worker or Verifier role.

Fugu proper has evolved further. The latency-oriented Fugu uses an extremely cheap routing decision: a lightweight head on the orchestrator's hidden state selects a worker model without even generating an autoregressive textual decision. Fugu-Ultra instead uses RL-trained Conductor-style workflows over multiple frontier agents.

So Sakana's central question is:

\[
\boxed{\text{"How do I train a manager to exploit a pool of experts?"}}
\]

Your question is:

\[
\boxed{\text{"How do I train a worker to maximally exploit instructions from one superior manager?"}}
\]

Those are almost mirror images.

That's an important distinction.

---

# 5. There are academic papers even closer than Fugu

This is where I would narrow your novelty claim considerably.

An EMNLP 2025 paper, **An Empirical Study on Strong-Weak Model Collaboration for Repo-level Code Generation**, explicitly tests having the strong model provide planning/context and having the weaker model generate the implementation. Their best collaboration matches strong-model performance at roughly **60% of the strong-model cost**.

The paper explicitly includes a strategy:

\[
\text{Strong LM planning}
\rightarrow
\text{Weak LM generation}.
\]

However, these models are **not specially trained for the relationship**. They're prompting/inference schemes.

Another very relevant 2026 preprint is **AgentCARD: Specialize Roles, Mix Deployments**. It systematically evaluates heterogeneous Planner/Executor/Verifier assignments. They find heterogeneous teams consistently occupy the cost–accuracy Pareto frontier and can match the strongest homogeneous configuration at up to **12× lower per-task cost** in some deployment configurations. Crucially, they also find which role deserves the strong model is domain-dependent: some tasks are planner-bottlenecked, others executor-bottlenecked.

That last result matters enormously for your hypothesis.

It means we **shouldn't assume the expensive model should always be the planner**.

For some tasks:

\[
P_{\text{strong}}+E_{\text{weak}}
\]

may dominate.

For others:

\[
P_{\text{weak}}+E_{\text{strong}}
\]

may dominate.

So a good research project should learn this allocation rather than hard-code it.

---

# 6. There is one paper that gets almost uncomfortably close to the conceptual core

ICLR 2026's **Latent-Guided Reasoning: Empowering Small LLMs with Large-Model Thinking** explicitly argues that ordinary LLM inference unnecessarily couples:

- high-level cognitive planning, and
- low-level linguistic realization.

Their architecture is literally:

\[
\boxed{\text{Large model = Implicit Thinker}}
\rightarrow
\boxed{\text{Small model = Explicit Executor}}.
\]

The large model produces compact latent vectors representing the cognitive plan. The small model is specifically trained to take that plan and realize it into the reasoning chain and answer.

And the authors state explicitly:

> the goal is **not** for the small model to learn to reason from scratch, but to learn the linguistic realization of a pre-computed cognitive plan.



That's extremely close philosophically to your proposal.

But there are still large differences:

\[
\text{Their work:}
\quad
L_{\text{trained planner}}
\xrightarrow{\text{latent vector}}
S_{\text{trained executor}}
\rightarrow
\text{answer}.
\]

Your envisioned agentic system:

\[
\text{Frontier frozen planner}
\xrightarrow{\text{natural-language task/spec}}
S_{\theta}
\xrightarrow{\text{tools/environment}}
\text{execution}
\xrightarrow{\text{feedback}}
\text{planner}
\]

They actually **train the large model too** to produce the latent guidance.

And their executor performs linguistic reasoning, not hours-long tool execution over repositories/computers.

So it occupies the same conceptual territory but not the same agentic problem.

---

# 7. That lets us define the remaining gap much more precisely

The original idea:

> “strong model plans, weak model executes”

is **not novel anymore**.

There is quite a lot of evidence for that.

Neither is:

> “use multiple models to reduce cost.”

Also well explored.

Neither is:

> “train an orchestrator.”

Fugu does that very directly.

Neither even is:

> “train a small model to execute a large model's cognitive plan.”

Latent-Guided Reasoning now gets very close.

The gap I think is still defensible is much narrower:

> **Train an agentic executor specifically to maximize the amount of work it can safely absorb from a fixed, substantially more capable frontier planner.**

More formally:

\[
P_F=\text{frozen frontier planner}
\]

\[
E_\theta=\text{trainable economical executor}.
\]

Instead of optimizing:

\[
\max_\theta P(\text{task solved}\mid E_\theta)
\]

as SWE-2 approximately does, optimize:

\[
\boxed{
\max_\theta
\left[
Q(P_F,E_\theta)
-\lambda C(P_F,E_\theta)
\right]
}
\]

subject to

\[
Q(P_F,E_\theta)
\geq Q(P_F)-\epsilon.
\]

That means the executor is rewarded for four things simultaneously:

\[
\begin{aligned}
&\text{correct execution}\\
+&\text{faithful adherence to planner intent}\\
+&\text{minimal need for frontier intervention}\\
+&\text{correctly escalating when necessary}.
\end{aligned}
\]

That's different from SWE-2.

SWE-2 optimizes:

\[
\text{“How cheaply can \textbf{I} solve this?”}
\]

Your executor optimizes:

\[
\boxed{
\text{“How much expensive cognition can I remove from \textbf{this specific stronger model}?”}
}
\]

I think that is the important novelty.

---

# 8. Devin Fusion actually gives you an unusually good baseline

Imagine taking Fusion as the baseline:

### Baseline

\[
\text{Fable 5.1}
\rightarrow
\text{SWE-2}
\]

using Cognition's hand-tuned sidekick protocol.

### Proposed

Start from SWE-2 or another competent open model:

\[
E_0
\]

collect trajectories:

\[
P_F\rightarrow E_0\rightarrow P_F\rightarrow E_0...
\]

and RL-train:

\[
E_0 \rightarrow E_1
\]

specifically based on whether its actions caused:

- planner corrections,
- rework,
- extra review,
- missed constraints,
- unnecessary planner calls,
- task failures.

For example:

\[
R=
R_{\text{task}}
-\alpha C_{\text{planner}}
-\beta C_{\text{executor}}
-\gamma N_{\text{correction}}
-\delta N_{\text{unnecessary escalation}}.
\]

Now you've turned Cognition's **hand-tuned relationship** into a **learned relationship**.

That is a clean research question.

---

## So I would draw the landscape like this

```text
                     TRAINED COMPONENT

                    manager            worker
                      │                  │
                      │                  │
Fugu / Conductor      █                  ·
TRINITY                █                  ·
Cursor Router          █                  ·/none
                      │
                      │
Devin Fusion           ·                  ·
Cursor Swarm           ·                  ·
AgentCARD              ·                  ·
Strong/Weak EMNLP      ·                  ·
                      │
Latent Guidance        █                  █
                      │                  │
                      │                  │
YOUR DIRECTION         frozen          █████
                      frontier        explicitly
                      planner         trained
```

The **empty cell** is still basically:

\[
\boxed{
\text{frozen frontier planner}
+
\text{executor RL-trained specifically for that planner}
+
\text{agentic tools}
+
\text{learned escalation}
+
\text{cost/capability preservation objective}
}
\]

I would no longer claim **“nobody has investigated strong planner + cheap executor.”** Cursor and Cognition would immediately falsify that claim.

I would instead make the paper's thesis:

> **Current heterogeneous agent systems obtain large cost savings mainly through routing, hand-designed delegation, or learned orchestration. We investigate the complementary problem of learned execution: can a smaller model be post-trained specifically as a subordinate to a frozen frontier planner, increasing delegation depth while preserving frontier-level task quality?**

That, based on the literature I can find through **September 2026**, still looks like a credible gap.

And there's a particularly compelling empirical hook now: **Cognition already gives you evidence that Fable/Astra + SWE-2 works without executor-specific collaboration training.** If executor-specific RL could move Fusion's ~40–46% savings toward, say, **60–80% while preserving quality**, that would be a genuinely meaningful result rather than just an architectural demonstration.

## 63. user — 2026-09-15T08:54:52+00:00 — model: gpt-5-6-thinking

- Message fields: content_type=`text`; recipient=`all`
- `default_model_slug`: `"gpt-5-6-thinking"`
- `model_slug`: `"gpt-5-6-thinking"`
- `message_source`: `null`
- `system_hints`: `[]`

Perform a full comprehensive literature review and refine and ensure we have a research gap to exploit enough to form an academic paper

## 64. assistant — 2026-09-15T08:55:26+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 0 item(s)]**

## 65. assistant — 2026-09-15T08:55:32+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

I’ll treat this as a paper-scoping review, not merely a source list. I’ll verify the cited 2025–2026 work, search adjacent fields that could invalidate novelty, then formulate the narrowest defensible gap, research questions, baselines, evaluation design, and claims you can safely make.

## 66. assistant — 2026-09-15T08:55:36+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

I’m using the document and Library workflows because this is substantial enough to preserve as a structured academic review. The review will clearly separate peer-reviewed evidence, preprints, and product claims so the proposed novelty does not rest on marketing material.

## 67. assistant — 2026-09-15T08:55:56+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "site:aclanthology.org strong weak model collaboration planner executor code generation 2025"}, {"type": "search", "q": "site:arxiv.org frozen large language model planner small executor training agent escalation cost"}, {"type": "search", "q": "site:openreview.net planner executor heterogeneous LLM collaboration reinforcement learning"}, {"type": "search", "q": "site:proceedings.mlr.press learning to defer large language model cascade reinforcement learning"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["site:aclanthology.org strong weak model collaboration planner executor code generation 2025", "site:arxiv.org frozen large language model planner small executor training agent escalation cost", "site:openreview.net planner executor heterogeneous LLM collaboration reinforcement learning", "site:proceedings.mlr.press learning to defer large language model cascade reinforcement learning"]}`

_(empty text part in the share payload)_

## 68. assistant — 2026-09-15T08:56:02+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": []}`

_(empty text part in the share payload)_

## 69. assistant — 2026-09-15T08:56:09+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "'7B'"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["'7B'"]}`

_(empty text part in the share payload)_

## 70. assistant — 2026-09-15T08:56:21+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "site:arxiv.org OR site:aclanthology.org small language model executor trained strong planner agent 2024 2025 2026"}, {"type": "search", "q": "site:arxiv.org heterogeneous planner executor LLM agent cost training executor"}, {"type": "search", "q": "site:aclanthology.org model collaboration large small language models planning execution delegation"}, {"type": "search", "q": "site:openreview.net specialized executor agent language model trained plan tool use"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["site:arxiv.org OR site:aclanthology.org small language model executor trained strong planner agent 2024 2025 2026", "site:arxiv.org heterogeneous planner executor LLM agent cost training executor", "site:aclanthology.org model collaboration large small language models planning execution delegation", "site:openreview.net specialized executor agent language model trained plan tool use"]}`

_(empty text part in the share payload)_

## 71. assistant — 2026-09-15T08:56:30+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "site:cognition.ai SWE-2 Fusion lead sidekick planning execution September 2026"}, {"type": "search", "q": "site:cursor.com blog frontier model planned fast inexpensive model carried out work 2026"}, {"type": "search", "q": "site:sakana.ai Fugu Ultra Conductor routing orchestration 2026"}, {"type": "search", "q": "\"Latent-Guided Reasoning\" large model small executor ICLR 2026"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["site:cognition.ai SWE-2 Fusion lead sidekick planning execution September 2026", "site:cursor.com blog frontier model planned fast inexpensive model carried out work 2026", "site:sakana.ai Fugu Ultra Conductor routing orchestration 2026", "\"Latent-Guided Reasoning\" large model small executor ICLR 2026"]}`

_(empty text part in the share payload)_

## 72. assistant — 2026-09-15T08:56:36+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 21 websites

```

## 73. assistant — 2026-09-15T08:56:36+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

A critical finding has already changed the novelty assessment: ProST (IJCNLP 2025) explicitly trains a small executor on plans produced by an orchestrator, and R2V-Agent (May 2026 preprint) distils an interactive small policy and learns step-level escalation to a stronger teacher. Therefore, “train a small executor plus learned escalation” is no longer a safe novelty claim by itself. The defensible gap must be defined by what these systems still do not jointly optimize or evaluate.

## 74. assistant — 2026-09-15T08:56:46+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "FrugalGPT paper arxiv 2023 LLM cascade cost"}, {"type": "search", "q": "RouteLLM learning router preference data ICLR 2025 official"}, {"type": "search", "q": "HuggingGPT paper Microsoft Research 2023 planner tools"}, {"type": "search", "q": "sub-goal distillation lightweight hierarchical agent 770M PMLR 2025"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["FrugalGPT paper arxiv 2023 LLM cascade cost", "RouteLLM learning router preference data ICLR 2025 official", "HuggingGPT paper Microsoft Research 2023 planner tools", "sub-goal distillation lightweight hierarchical agent 770M PMLR 2025"]}`

_(empty text part in the share payload)_

## 75. assistant — 2026-09-15T08:56:54+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "AgentCARD Specialize Roles Mix Deployments arxiv 2606.20629"}, {"type": "search", "q": "CoDA Planner Executor Co-Optimization 2512.12716"}, {"type": "search", "q": "An Empirical Study Strong-Weak Model Collaboration Repo-level Code Generation 2505.20182"}, {"type": "search", "q": "EAGLET executor capability gain reward planner ACL 2026"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["AgentCARD Specialize Roles Mix Deployments arxiv 2606.20629", "CoDA Planner Executor Co-Optimization 2512.12716", "An Empirical Study Strong-Weak Model Collaboration Repo-level Code Generation 2505.20182", "EAGLET executor capability gain reward planner ACL 2026"]}`

_(empty text part in the share payload)_

## 76. assistant — 2026-09-15T08:57:14+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 38 websites

```

## 77. assistant — 2026-09-15T08:57:14+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

The gap is now refined to a stronger, narrower contribution: **planner-conditioned executor specialization under a fixed frontier-model budget, with intervention-aware training and counterfactual evaluation against the same frozen planner**. Existing papers cover executor role tuning, strong/weak collaboration, and step-level escalation separately; the review will test whether any paper combines all three and, if not, define experiments that distinguish the contribution from ProST and R2V rather than merely recombining them.

## 78. assistant — 2026-09-15T08:57:20+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc 'find /root/.codex -path "*/builtins/documents/container_tools/mark_artifact_operation_started.mjs" -o -path "*/builtins/documents/render_docx.py" | head -20'
```

## 79. tool — 2026-09-15T08:57:20+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 80. assistant — 2026-09-15T08:57:24+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc '"$CODEX_PRIMARY_RUNTIME_NODE" /root/.codex/skills/builtins/documents/container_tools/mark_artifact_operation_started.mjs --operation-kind create --expected-output-count 1 --output-format docx'
```

## 81. tool — 2026-09-15T08:57:24+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 82. assistant — 2026-09-15T09:01:11+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc apply_patch
```

## 83. tool — 2026-09-15T09:01:12+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 84. assistant — 2026-09-15T09:01:16+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc '"$CODEX_PRIMARY_RUNTIME_PYTHON" build_review.py'
```

## 85. tool — 2026-09-15T09:01:16+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 86. assistant — 2026-09-15T09:01:27+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc '"$CODEX_PRIMARY_RUNTIME_PYTHON" /root/.codex/skills/builtins/documents/render_docx.py /workspace/scratch/d9e6da15b832/frontier_planner_small_executor_literature_review.docx --output_dir /workspace/scratch/d9e6da15b832/rendered_review_v1 --emit_pdf'
```

## 87. tool — 2026-09-15T09:01:31+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 88. assistant — 2026-09-15T09:01:37+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc 'find /workspace/scratch/d9e6da15b832/rendered_review_v1 -maxdepth 1 -name "page-*.png" -printf "%f
" | sort'
```

## 89. tool — 2026-09-15T09:01:38+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 90. assistant — 2026-09-15T09:01:47+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc 'command -v montage || command -v magick'
```

## 91. tool — 2026-09-15T09:01:47+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 92. assistant — 2026-09-15T09:01:51+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc 'montage /workspace/scratch/d9e6da15b832/rendered_review_v1/page-*.png -thumbnail 420x544 -tile 3x4 -geometry +8+8 /workspace/scratch/d9e6da15b832/rendered_review_v1/contact.png'
```

## 93. tool — 2026-09-15T09:01:54+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 94. assistant — 2026-09-15T09:02:20+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 2 item(s)]**

```text
[1] Adjusting table font and margins for pagination
**Adjusting table font and margins for pagination**

[2] Adjusted table font and margins for pagination

```

## 95. assistant — 2026-09-15T09:02:25+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc apply_patch
```

## 96. tool — 2026-09-15T09:02:26+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 97. assistant — 2026-09-15T09:02:31+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc '"$CODEX_PRIMARY_RUNTIME_PYTHON" build_review.py && "$CODEX_PRIMARY_RUNTIME_PYTHON" /root/.codex/skills/builtins/documents/render_docx.py /workspace/scratch/d9e6da15b832/frontier_planner_small_executor_literature_review.docx --output_dir /workspace/scratch/d9e6da15b832/rendered_review_v2 --emit_pdf'
```

## 98. tool — 2026-09-15T09:02:36+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 99. assistant — 2026-09-15T09:02:43+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc 'montage /workspace/scratch/d9e6da15b832/rendered_review_v2/page-*.png -thumbnail 420x544 -tile 3x4 -geometry +8+8 /workspace/scratch/d9e6da15b832/rendered_review_v2/contact.png && find /workspace/scratch/d9e6da15b832/rendered_review_v2 -maxdepth 1 -name "page-*.png" | wc -l'
```

## 100. tool — 2026-09-15T09:02:46+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 101. assistant — 2026-09-15T09:02:54+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Created, rendered, and reviewed literature review document artifacts

```

## 102. assistant — 2026-09-15T09:02:54+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

The review is complete and the gap survives, but as a conjunctive method-and-evaluation gap rather than a broad architectural one. I have also built the study around direct “novelty killers”: ProST-style executor training, R2V-style step routing, prompt-only strong-to-weak collaboration, role swapping, and the frontier planner acting alone.

## 103. assistant — 2026-09-15T09:03:01+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

Saving the completed review now.

## 104. assistant — 2026-09-15T09:03:04+00:00 — model: none

- Message fields: content_type=`text`; recipient=`api_tool.call_tool`

The output of this plugin was redacted.

## 105. tool — 2026-09-15T09:03:08+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`; author name=`api_tool.call_tool`

The output of this plugin was redacted.

## 106. assistant — 2026-09-15T09:03:14+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Created Frontier Planner literature review document

```

## 107. assistant — 2026-09-15T09:03:14+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc "python3 /root/.codex/plugins/cache/openai-curated-remote/openai-library/0.1.55/skills/library/scripts/library_file_transfer.py apply-xattrs /workspace/scratch/d9e6da15b832/frontier_planner_small_executor_literature_review.docx libfile_cee64ae164308191838b95353b7ac290 <<'JSON'
[{\"name\":\"user.library-file-version\",\"value\":\"0\"}]
JSON"
```

## 108. tool — 2026-09-15T09:03:14+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 109. assistant — 2026-09-15T09:03:19+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Applied library file metadata

```

## 110. assistant — 2026-09-15T09:03:19+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning recap]** Worked for 7m 53s

## 111. assistant — 2026-09-15T09:03:19+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`
- Referenced file: `frontier_planner_small_executor_literature_review.docx`

The literature review confirms a viable paper, but the research gap is narrower than originally proposed.

The broad claim—“a strong model plans while a smaller model executes”—is already covered. More importantly:

- **ProST** already trains an interactive executor using an orchestrator’s plans. [IJCNLP 2025](https://aclanthology.org/2025.ijcnlp-long.179/)
- **R2V-Agent** distils a small interactive policy and learns step-level escalation to a stronger teacher. [R2V-Agent](https://arxiv.org/abs/2605.16604)
- Strong–weak collaboration already matches strong-model coding performance with about 40% reported cost reduction. [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1043/)
- **AgentCARD** shows that heterogeneous teams can dominate cost–accuracy frontiers, but also warns that some domains are executor-bottlenecked rather than planner-bottlenecked. [AgentCARD](https://arxiv.org/abs/2606.20629)

The defensible research gap is:

> **Planner-conditioned, intervention-aware executor specialization:** train a small executor specifically for one frozen frontier planner, jointly learning execution and escalation to minimize planner corrections, takeovers, replanning, verification, and frontier tokens, subject to a measured non-inferiority constraint against that same planner operating alone.

The paper’s scientific novelty must come from:

1. A new correction-sensitive or counterfactual intervention training signal.
2. Joint executor-and-escalation optimization, rather than ProST-style supervised tuning or R2V’s sequential policy-then-router training.
3. Directly measuring **frontier-compute displacement at matched quality**.
4. Paired evaluation against the identical frozen planner.
5. Cross-planner transfer, role-swap, perturbation, calibration, and safety tests.

The complete 11-page review includes the literature taxonomy, comparison matrix, precise gap, research questions, hypotheses, reward formulation, training stages, baselines, ablations, metrics, statistical design, threats to validity, minimum publishable study, stronger study, paper structure, and linked references:

[frontier_planner_small_executor_literature_review.docx](sandbox:/workspace/scratch/d9e6da15b832/frontier_planner_small_executor_literature_review.docx)

## 112. user — 2026-09-15T09:11:06+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`
- `default_model_slug`: `"gpt-5.6-sol-wm"`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `message_source`: `null`
- `system_hints`: `[]`

Give the full idea with all the literature info, expected goal, ... everything into an md file to be given to claude code to initialize the research project

## 113. assistant — 2026-09-15T09:11:08+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 0 item(s)]**

## 114. assistant — 2026-09-15T09:11:17+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

I’ll convert the review into an implementation-ready research specification for Claude Code: literature map, exact novelty boundary, hypotheses, system interfaces, training objective, data collection, baselines, experiments, repository structure, milestones, acceptance criteria, and explicit safeguards against overstating novelty. I’m using the Library workflow so the Markdown brief remains available as the project’s canonical initialization document.

## 115. assistant — 2026-09-15T09:16:25+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc apply_patch
```

## 116. tool — 2026-09-15T09:16:26+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 117. assistant — 2026-09-15T09:16:32+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc "wc -l -w RESEARCH_PROJECT_SPEC.md && rg -n '"'^## |''^### '"' RESEARCH_PROJECT_SPEC.md | tail -20 && rg -n 'TODO|PLACEHOLDER|turn[0-9]|utm_source' RESEARCH_PROJECT_SPEC.md || true"
```

## 118. tool — 2026-09-15T09:16:32+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 119. assistant — 2026-09-15T09:16:37+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Applied a code patch and audited the research project specification

```

## 120. assistant — 2026-09-15T09:16:37+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`

The Markdown specification is ready. It is deliberately written as an initialization contract rather than a narrative proposal, including falsification criteria and “unsafe novelty claims” so Claude Code does not accidentally build the project around a claim that ProST or R2V already invalidates.

## 121. assistant — 2026-09-15T09:16:37+00:00 — model: none

- Message fields: content_type=`text`; recipient=`api_tool.call_tool`

The output of this plugin was redacted.

## 122. tool — 2026-09-15T09:16:45+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`; author name=`api_tool.call_tool`

The output of this plugin was redacted.

## 123. assistant — 2026-09-15T09:16:52+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Created research project specification

```

## 124. assistant — 2026-09-15T09:16:56+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`code`; recipient=`container.exec`
- `model_slug`: `"gpt-5.6-sol-wm"`

```
bash -lc /bin/bash -lc "python3 /root/.codex/plugins/cache/openai-curated-remote/openai-library/0.1.55/skills/library/scripts/library_file_transfer.py apply-xattrs /workspace/scratch/d9e6da15b832/RESEARCH_PROJECT_SPEC.md libfile_7607b3bc4aec8191962f5e31765dbd96 <<'JSON'
[{\"name\":\"user.library-file-version\",\"value\":\"0\"}]
JSON"
```

## 125. tool — 2026-09-15T09:16:56+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`; author name=`container.exec`

The output of this plugin was redacted.

## 126. assistant — 2026-09-15T09:16:56+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Used container tool

```

## 127. assistant — 2026-09-15T09:16:56+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning recap]** Worked for 5m 46s

## 128. assistant — 2026-09-15T09:16:57+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"min"`
- `model_slug`: `"gpt-5.6-sol-wm"`
- Referenced file: `RESEARCH_PROJECT_SPEC.md`

Created the complete Claude Code research initialization specification:

[RESEARCH_PROJECT_SPEC.md](sandbox:/workspace/scratch/d9e6da15b832/RESEARCH_PROJECT_SPEC.md)

It contains:

- The complete research idea and expected contribution
- Precise, defensible research gap
- Detailed literature review and source links
- Safe and unsafe novelty claims
- Research questions and hypotheses
- Formal constrained optimization objective
- Planner–executor communication protocol
- Intervention and trajectory schemas
- Training stages from SFT through constrained RL
- Full baseline and ablation suite
- Dataset and model-selection guidance
- Evaluation and statistical methodology
- Cost, calibration, safety, and robustness metrics
- Falsification criteria
- Minimum publishable and stronger study designs
- Repository architecture and engineering requirements
- Eight implementation milestones
- Explicit initial instructions and completion criteria for Claude Code

The file is approximately 7,400 words and is ready to place at the root of the new research repository.

## 129. user — 2026-09-17T00:29:20+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`
- `message_source`: `null`

# The thesis, the method, and the jobs

## 1. The claim

A large hosted model (`gpt-5.6-luna`) is good at AppWorld: 0.684 task goal completion. A small local model (`granite-4.2-8b`) is not: 0.0175 zero-shot. The obvious fix — let the big model plan and the small one execute — recovers little on its own (`prompt_only`, 0.0439). That gap, **64.0 pp, CI [54.4, 72.8]**, is the headroom the project exists to attack.

The interesting question isn't "can a small model be trained to do better" — it can, and that's already measured (SFT takes it to 0.430 with a plan). The question is about **cost**. Every call to the hosted planner costs money and latency. A system that calls it constantly gets good results expensively; a system that never calls it gets poor results cheaply. The thesis is that a policy can be trained to know *when* it needs help, and that this beats both extremes:

- **H1** — `sidekick` is non-inferior to `planner_alone` at ε = 7 pp while displacing planner tokens. *Expected to fail.* An 8B won't reach 0.68. `PLAN.md` says so in advance, which is why the fallback is pre-planned rather than improvised.
- **H2 — the core claim.** `sidekick` beats `sft_plan` at matched planner cost. `sft_plan` is the same model, same data, trained *without* the escalation channel. This isolates the one thing under test.
- **H3** — escalation is calibrated: better than a fixed schedule (`fixed_k`), approaching the oracle, with a low needless-ask rate.
- **H4** — training the decision *into* the policy beats bolting a router onto a frozen executor (`router_seq`).

If H1 fails the deliverable becomes the **quality-versus-displacement frontier**: at what fraction of displaced planner cost does quality hold, and does `sidekick` dominate `sft_plan`, `router_seq` and `fixed_k` on that curve. That's a real result, not a consolation prize — it's the shape practitioners actually need.

## 2. What ASK is

`ASK_PLANNER:` is a line the executor can emit instead of an action. The executor's output is parsed (`protocols/schemas.py:337-368`) for one of a few canonical forms — a ```python fence, `REPORT:`, `COMPLETE`, or `ASK_PLANNER:`. When the last one fires:

1. The loop checks whether asking is allowed — the system's `allow_executor_ask`, and if `gate_ask_with_verifier` is on, a verifier score must clear a threshold.
2. If allowed: the last 8 transcript lines plus `ASK: <reason>` go to the planner as a `correct()` call. The planner's reply comes back and is appended to the executor's conversation as a user turn, `ANSWER: <text>`.
3. The step is *not* consumed as an environment action — the executor then acts with the answer in context.
4. If refused, the executor gets `ASK_IGNORED` instead.

So ASK is the executor raising its hand. It is the **one channel** through which a trained policy can spend hosted budget on its own initiative, and its cost is exactly one planner call. In 114 HJ-1R episodes it fired **once**, unprompted, and solved a task that scored 0.0 without it (n=1 — suggestive, not evidence).

The contrast that defines the experiment: `fixed_k` spends planner calls on a **timer** — every 5 steps, whether or not anything is wrong. `sidekick` spends them **on demand**. Same currency, different allocation policy.

## 3. The problem J4 exposed

J4 ran `fixed_k` on the trained executor across 180 episodes and produced 495 interventions. The plan was to turn those into ASK training targets: wherever the reviewer intervened, teach the model to ask.

That turned out to be unusable, for a reason worth stating precisely. Inspection of the event logs showed the reviewer fires on a **deterministic 5-step timer** (event positions 12, 23, 34, 45 — exactly 11 apart), speaks **before** the executor acts, never sees a proposed action, and **cannot reject one**. All 495 carry `forced: true`; zero are `ask` events.

So the data records 495 corrections and **nothing about whether any of them mattered**. Training ASK targets on them would teach the model to ask every 5 steps — a metronome. H2 would then be measuring "does asking on a schedule help", which is `fixed_k`, not the hypothesis.

That single finding is what reordered the campaign: the label has to be manufactured before the policy can be trained.

## 4. How the label gets made — counterfactual branching

For each intervention point, replay the episode to the state just before the reviewer spoke, then continue **without** the correction, using the same adapter, reviews off, two samples at temperature 0.7. Grade each continuation.

- `needed` := mean(branch score) < actual score — removing the correction made things worse, so it mattered.
- `needless` := mean ≥ actual — the episode would have gone the same or better unaided.
- Also tracked: `harmful` (branch beat the actual) and `needed_strict` (both samples worse).

This does offline credit assignment explicitly and cheaply. It yields three things at once: the ASK targets for training, the labels to fit the router, and — before any sidekick exists — the headline measurement *"X % of a fixed schedule's calls actually changed the outcome"*. That number is a paper figure on its own.

## 5. The jobs

**J4b — does the timer help on held-out tasks?** ~1.2 GPU-h. `fixed_k` on the trained executor, dev split, 114 pairs, plus a third training seed. This has only ever been run on *train* (0.577 — the policy's own training tasks, inflated and uncomparable).

*Gate A*, written before submission: paired against `sft_plan` at 0.430 on the identical pairs. ≥ +7 pp with CI excluding zero → interventions buy real quality, proceed. **CI includes zero → stop.** There's nothing for a learned policy to capture, H2 is unsupported at this data scale, and the remaining ~29 GPU-h shouldn't be spent. That gate is the reason this job runs first.

**J6 — the branches.** ~5.3 GPU-h, ~2,100 rollouts across train and dev. Produces `branches.jsonl` and `oracle_labels.json`. *Gate B* reports the needed-fraction by split and depth. Too few positives → collect another seed before training. Nearly all needed → the timer is almost always right and the achievable saving is bounded; record it and proceed.

**J5a / J5b — the matched adapter pair.** ~8 GPU-h. Identical data except at `needed` points: `sft_b_plus` gets the corrected action, `sft_c` gets ASK → `ANSWER:` → the corrected action. Tests assert the two files are byte-identical everywhere else. That difference *is* the manipulation.

**J7 — the verifier.** Minutes, CPU. Logistic regression on trajectory features (error streaks, repeated actions, step count) fit on the J6 labels. Serves `router_seq` and supplies H3's calibration numbers. Only escalates to a neural verifier if dev AUROC < 0.65.

**J8 — the dev frontier.** ~6.5 GPU-h, 12 arms × 114. Sweeps `fixed_k` over k, `router_seq` over its threshold, and `sidekick` over **τ**, a threshold on the policy's own P(ASK) from first-token logprobs. That last knob is why DPO was dropped: one adapter, no extra training, any number of operating points, and the AUROC of P(ASK) against the J6 labels *is* the H3 calibration measurement. Picks τ*, k_matched, and the first FCD numbers.

**J9 — freeze.** The prereg locks with H2 conjunctive as primary: `sidekick` ≥ `fixed_k(k_matched)` − 7 pp **and** > `sft_plan` **and** fewer planner calls than `fixed_k(5)`. The conjunction has teeth — a policy that never asks satisfies the first clause trivially only if the timer is worthless, which then fails the second.

**J10 — the final run, once.** ~9 GPU-h. test_normal, 168 tasks × 3 seeds × 7 arms, one window, no re-runs. Power analysis already fixed N=3 and ε=7 pp, and established that extra *seeds* are wasted quota because the binding constraint is the number of tasks.

## 6. Why this design, briefly

Two things keep recurring in this project's history and shape every choice above. First, **harness defects that return believable numbers** — nineteen so far, several of which produced plausible results rather than errors, including a probe that measured a configuration no arm ran in. Hence: gates written before jobs, labels defined before data exists, assertions between the two training files, and every load-bearing number re-derived from raw artifacts rather than summaries.

Second, **the data ceiling**. AppWorld train is 90 tasks. That's why the escalation decision is converted into a supervised problem via branching rather than learned by RL, and why the frontier comes from sweeping a threshold on one adapter instead of training several.

This is now the current state of the research project, give prompt to ask for more detail if needed but as of now, is this research direction new knowledge, that this is a research gap that we can write about?

## 130. assistant — 2026-09-17T00:29:21+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 0 item(s)]**

## 131. assistant — 2026-09-17T00:29:31+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

I’m going to reassess novelty against the project’s now-specific contribution—not the earlier broad idea. The decisive question is whether counterfactual branching to label the value of planner intervention, followed by matched ASK/no-ASK executor training and a cost-matched frontier, is already established in agent-routing or learning-to-defer literature. I’ll verify the closest 2025–2026 work before judging the claim.

## 132. assistant — 2026-09-17T00:29:39+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "site:arxiv.org LLM agent counterfactual branching intervention labels escalation planner executor ask for help"}, {"type": "search", "q": "site:aclanthology.org agent ask for help counterfactual trajectories planner intervention executor"}, {"type": "search", "q": "site:openreview.net LLM agent learned escalation counterfactual rollout router executor"}, {"type": "search", "q": "site:arxiv.org fixed schedule planner review learned ask planner agent cost frontier"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["site:arxiv.org LLM agent counterfactual branching intervention labels escalation planner executor ask for help", "site:aclanthology.org agent ask for help counterfactual trajectories planner intervention executor", "site:openreview.net LLM agent learned escalation counterfactual rollout router executor", "site:arxiv.org fixed schedule planner review learned ask planner agent cost frontier"]}`

_(empty text part in the share payload)_

## 133. assistant — 2026-09-17T00:29:48+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "\"counterfactual\" \"ask for help\" LLM agent escalation"}, {"type": "search", "q": "\"counterfactual rollouts\" LLM agent routing"}, {"type": "search", "q": "\"intervention\" \"counterfactual\" LLM agents planner executor"}, {"type": "search", "q": "\"oracle escalation\" LLM agent"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["\"counterfactual\" \"ask for help\" LLM agent escalation", "\"counterfactual rollouts\" LLM agent routing", "\"intervention\" \"counterfactual\" LLM agents planner executor", "\"oracle escalation\" LLM agent"]}`

_(empty text part in the share payload)_

## 134. assistant — 2026-09-17T00:29:56+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "site:arxiv.org 2026 \"ask\" \"planner\" executor escalation LLM agent"}, {"type": "search", "q": "site:arxiv.org 2026 \"planner intervention\" LLM agent"}, {"type": "search", "q": "site:aclanthology.org 2026 executor asks planner help agent"}, {"type": "search", "q": "site:openreview.net 2026 executor planner ask for help model"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["site:arxiv.org 2026 \"ask\" \"planner\" executor escalation LLM agent", "site:arxiv.org 2026 \"planner intervention\" LLM agent", "site:aclanthology.org 2026 executor asks planner help agent", "site:openreview.net 2026 executor planner ask for help model"]}`

_(empty text part in the share payload)_

## 135. assistant — 2026-09-17T00:30:09+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 3 item(s)]**

```text
[1] Analyzing R2V preprint novelty
**Analyzing R2V preprint novelty**

[2] Clarifying counterfactual labeling challenges
**Clarifying counterfactual labeling challenges**

[3] Analyzed R2V preprint novelty and counterfactual labeling challenges

```

## 136. assistant — 2026-09-17T00:30:15+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 3 item(s)]**

```text
[1] Analyzing R2V preprint novelty
**Analyzing R2V preprint novelty**

[2] Clarifying counterfactual labeling challenges
**Clarifying counterfactual labeling challenges**

[3] Analyzed R2V preprint novelty and counterfactual labeling challenges

```

## 137. assistant — 2026-09-17T00:30:18+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": []}`

_(empty text part in the share payload)_

## 138. assistant — 2026-09-17T00:30:26+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "'counterfactual'"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["'counterfactual'"]}`

_(empty text part in the share payload)_

## 139. assistant — 2026-09-17T00:30:38+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 3 item(s)]**

```text
[1] Evaluating research novelty and gaps
**Evaluating research novelty and gaps**

[2] Identifying flaws in causal intervention claims
**Identifying flaws in causal intervention claims**

[3] Evaluated research novelty and identified flaws in causal claims

```

## 140. assistant — 2026-09-17T00:30:55+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 3 item(s)]**

```text
[1] Evaluating research novelty and gaps
**Evaluating research novelty and gaps**

[2] Identifying flaws in causal intervention claims
**Identifying flaws in causal intervention claims**

[3] Evaluated research novelty and identified flaws in causal claims

```

## 141. assistant — 2026-09-17T00:30:55+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 44 websites

```

## 142. assistant — 2026-09-17T00:30:55+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning recap]** Worked for 1m 34s

## 143. assistant — 2026-09-17T00:30:55+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

Yes—this can produce new knowledge and a defensible paper. But the novelty is narrower than “training a small executor to ask a large planner for help.”

The strongest defensible contribution is:

> **Using counterfactual intervention ablations to train an executor-internal help-seeking policy, then measuring whether it allocates a frozen planner’s calls more efficiently than periodic review and a post-hoc router in a long-horizon interactive environment.**

That precise combination still appears underexplored. However, several individual components now have close precedents, so the paper must position itself carefully and fix two important causal-design issues before J6.

## Novelty verdict

| Possible claim | Verdict |
|---|---|
| Large planner plus small executor | Already established |
| Train executor on planner-generated plans | Already covered by ProST |
| Small model asks a stronger model for help | Already covered by R2V-Agent and Bayesian self-escalation |
| Sweep escalation thresholds to obtain a cost-quality frontier | Already covered conceptually |
| Use counterfactual agent rollouts for training labels | Overlaps CausalFlow |
| Determine whether individual scheduled planner interventions actually improve outcomes | Likely new in this setting |
| Use intervention ablation to create ASK supervision | Defensible novelty |
| Compare an executor-internal ASK policy with fixed review and a post-hoc router under matched planner cost | Strongest experimental contribution |
| Measure planner-compute displacement on AppWorld | New empirical knowledge if rigorously established |
| Matched SFT adapters differing only at causally validated ASK points | Strong controlled contribution |

So this is not an untouched research area. It is a credible gap at the intersection of causal credit assignment, help-seeking policy learning, and cost allocation in planner–executor agents.

## Why the project still differs from the closest papers

### R2V-Agent

R2V-Agent already asks the broad question:

> Can a cheap interactive policy act locally and invoke a stronger teacher only when the current state is risky?

It trains a small policy first and then trains a calibrated router on that frozen policy’s residual failures. Its labels say whether a trajectory containing a visited context eventually failed. They do **not** estimate whether invoking the teacher at that particular state would have changed the outcome. [R2V-Agent](https://arxiv.org/abs/2605.16604)

Your project instead asks:

\[
\text{What is the causal value of planner intervention at state }s_t?
\]

Conceptually:

\[
\Delta_t
=
\mathbb{E}[Q\mid \text{intervene at }t]
-
\mathbb{E}[Q\mid \text{do not intervene at }t].
\]

That is a better target for allocating expensive planner calls than R2V’s approximate target:

\[
P(\text{episode eventually fails}\mid s_t).
\]

A state can have high failure risk even when planner intervention would not help. Conversely, a state can look ordinary while a short planner clarification has high value. Your label estimates the value of intervention, not merely the risk of failure.

That distinction should be central to the paper.

### Bayesian Self-Escalation

A very recent preprint, *Knowing When to Ask for Help*, formulates mid-generation escalation as Bayesian optimal stopping over a learned competence posterior. It reports that self-escalation can beat post-hoc routing at equal cost in a Qwen code cascade. Therefore, you cannot claim that executor-initiated escalation, threshold sweeping, calibration, or equal-cost comparison is new. [Bayesian Self-Escalation](https://arxiv.org/abs/2608.24087)

Your differences are still material:

- AppWorld is a long-horizon tool environment rather than answer generation.
- ASK obtains planner guidance and resumes execution; the paper’s escalation is effectively a terminal handoff.
- Your executor is directly trained to emit ASK.
- Your labels estimate intervention utility through environment replay.
- You compare against periodic planner review.
- Your primary outcome is planner-compute displacement across an interactive trajectory.

This paper should be added to the related-work section and probably included as a conceptual baseline. Your logistic verifier can be described as estimating intervention value or competence, while the executor’s ASK probability is the embedded alternative.

### CausalFlow

CausalFlow uses step-level counterfactual interventions to identify failure-causing actions and converts the resulting repairs into training supervision. This means you should not claim to introduce counterfactual branching over agent trajectories. [CausalFlow](https://arxiv.org/abs/2605.25338)

The distinction is the intervention being evaluated:

- CausalFlow: “Did this agent step cause failure, and what minimal repair reverses it?”
- Your project: “Did an expensive planner correction improve the outcome enough to justify its cost?”

You are estimating the causal value of external assistance, not merely the causal responsibility of an erroneous action.

### ProST

ProST already trains AppWorld executors on orchestrator plans, environmental feedback, correct actions, and self-corrected actions. It also evaluates heterogeneous planner/executor allocations. [ProST](https://aclanthology.org/2025.ijcnlp-long.179/)

Your matched `sft_b_plus` versus `sft_c` design is important because it isolates what ProST does not:

\[
\text{corrected action}
\quad\text{versus}\quad
\text{ASK}\rightarrow\text{answer}\rightarrow\text{corrected action}.
\]

If the datasets are genuinely byte-identical everywhere else, the comparison provides unusually clean evidence about embedding the allocation decision into the executor.

## The paper’s actual new knowledge

If successful, the paper could establish four findings.

### 1. The causal efficiency of periodic supervision

J6 can estimate:

> What proportion of fixed-schedule planner calls materially improve AppWorld task outcomes?

That is independently useful. A fixed reviewer may issue hundreds of plausible corrections while only a minority change the final environment state.

Report at least:

\[
\text{Needed Rate}
=
\frac{N_{\text{beneficial interventions}}}
     {N_{\text{all interventions}}},
\]

along with:

- needless rate;
- harmful rate;
- effect-size distribution;
- intervention utility by episode depth;
- utility by task family;
- utility following errors or repeated actions;
- utility conditional on the executor’s uncertainty;
- planner tokens per unit of TGC gained.

This is stronger than simply reporting that `fixed_k` improves average performance.

### 2. Whether intervention utility is learnable

J7 and the ASK-probability analysis determine whether the causal labels have predictable structure:

\[
P(\Delta_t>0\mid s_t).
\]

If neither trajectory features nor the executor’s ASK probability distinguish useful interventions, then adaptive allocation may not be learnable at this data scale.

A positive result establishes that planner value is predictable from executor-visible state.

### 3. Whether help seeking should be inside the executor

The comparison between `sidekick` and `router_seq` tests an architectural question:

> Should the acting model learn help seeking as an action, or should a separate router monitor a fixed policy?

R2V deliberately separates the policy and router to isolate allocation. Your experiment tests the complementary claim that entangling execution and escalation improves the frontier.

That is a legitimate scientific disagreement, not merely an implementation choice.

### 4. The attainable quality-displacement frontier

Even if H1 fails, the resulting frontier answers:

\[
Q(b)=
\max_{\pi:\ C_P(\pi)\le b} Q(\pi),
\]

where \(b\) is the permitted planner budget.

This tells practitioners whether, for example:

- 20% planner cost retains 45% TGC;
- 40% planner cost retains 55% TGC;
- 70% planner cost retains near-planner quality.

The location and shape of this frontier are new empirical knowledge even if the 8B executor never reaches planner-alone performance.

## Two important problems to fix before J6

### 1. The current branch may not isolate the focal intervention

You wrote:

> replay to immediately before the correction, remove the correction, turn reviews off, and continue.

If all subsequent reviews are disabled, the branch does not estimate the effect of the focal correction alone. It estimates the effect of:

\[
\text{current correction}
+
\text{every subsequent scheduled correction}.
\]

Suppose the intervention at step 5 is useless, but the intervention at step 10 is essential. Turning both off makes the step-5 intervention appear needed.

The correct estimand requires two worlds that differ only at the focal intervention:

\[
\Delta_i
=
Q(\text{review policy with intervention }i)
-
Q(\text{same policy with intervention }i\text{ omitted}).
\]

Possible implementations:

- Omit only the focal correction and keep later scheduled reviews.
- Evaluate a local horizon that ends before the next scheduled review.
- Branch four ways to separate current and future review effects.
- Use a sequential marginal-contribution or Shapley-style approximation if later reviews cannot be held constant.

The first is preferable if technically possible.

If later scheduled reviews become semantically impossible after trajectory divergence, preserve the policy rather than the exact messages: at the same later review schedule, call the reviewer on the branch’s actual state.

### 2. Two untreated branches against one factual trajectory are noisy labels

Your current definition compares the mean of two stochastic no-correction branches with one observed corrected result. That mixes intervention effect with sampling variance:

\[
\hat{\Delta}_i
=
Q_{\text{actual},1}
-
\frac{Q_{\text{branch},1}+Q_{\text{branch},2}}{2}.
\]

A label can flip simply because the factual trajectory was lucky or one branch was unlucky.

A better design would collect replicated treated and untreated continuations:

\[
\hat{\Delta}_i
=
\frac{1}{m}\sum_{j=1}^{m}Q^{(1)}_{ij}
-
\frac{1}{n}\sum_{j=1}^{n}Q^{(0)}_{ij}.
\]

Given the budget, at least consider:

- two corrected and two uncorrected continuations;
- common random seeds or common random numbers where supported;
- a continuous effect label rather than immediately binarizing;
- confidence-weighted training;
- using `needed_strict` for ASK targets and ambiguous cases only for verifier calibration;
- an indifference band, such as labeling `needed` only when the difference exceeds a meaningful TGC threshold.

For example:

\[
y_i=
\begin{cases}
1 & \hat{\Delta}_i>\delta\\
0 & \hat{\Delta}_i<-\delta\\
\text{ambiguous} & |\hat{\Delta}_i|\le\delta.
\end{cases}
\]

This will reduce the number of labels but improve their causal meaning.

## H2 needs a wording correction

The current statement says:

> `sidekick` beats `sft_plan` at matched planner cost.

But `sft_plan` makes no planner calls. Its planner cost is zero, whereas any sidekick operating point that asks for help has positive planner cost. They cannot be matched on planner cost except at the sidekick threshold that never asks.

Split H2 into two comparisons:

### H2a: value of adaptive assistance

\[
Q(\text{sidekick}_\tau)>Q(\text{sft-plan})
\]

while reporting the additional planner cost required to obtain that gain.

This tests whether the ASK channel adds useful capability.

### H2b: allocation efficiency

At matched planner calls or planner tokens:

\[
Q(\text{sidekick}_\tau)
>
Q(\text{fixed-k}_{\text{matched}})
\]

and

\[
Q(\text{sidekick}_\tau)
>
Q(\text{router-seq}_{\text{matched}}).
\]

This tests whether the embedded policy spends the same hosted budget better.

A clean primary hypothesis would be:

> At a planner-token budget selected on development data, sidekick achieves higher test TGC than both fixed-schedule review and sequential routing, while also improving over the no-escalation SFT executor.

Alternatively, make Pareto dominance primary:

\[
\exists \tau:
Q_{\text{sidekick}}(\tau)\ge Q_b
\quad\land\quad
C_{\text{sidekick}}(\tau)<C_b,
\]

or the corresponding strict-quality/equal-cost condition, for baseline \(b\).

## Be careful with P ASK

A first-token probability is only a valid ASK score if ASK is represented unambiguously at that decoding position.

Check:

- whether leading whitespace changes tokenization;
- whether `ASK_PLANNER:` is one token or several;
- whether other output forms share the same first token;
- whether code fences and textual actions receive comparable probability mass;
- whether chat-template artifacts occur before the canonical output;
- whether the logprob API returns all necessary alternatives.

If ASK is multi-token, “first-token P(ASK)” is not literally the probability of the ASK sequence.

Safer choices include:

- reserve a single control token for each action class;
- constrain the first generated token to `ACT`, `ASK`, `REPORT`, or `COMPLETE`;
- calculate the conditional sequence probability of the complete ASK prefix;
- train a small classification head over the final prompt state.

A single canonical control token would make the threshold sweep and calibration claim much cleaner.

## Other methodological recommendations

### Cluster by task

Your 114 pairs and three seeds are not 342 fully independent task observations. Bootstrap and confidence intervals should resample at the task level, retaining all seeds and paired arms within each sampled task.

### Account for multiple intervention points per episode

The 495 J4 intervention records are nested inside episodes and tasks. Do not treat them as independent rows in verifier evaluation. Split by task and use task-grouped cross-validation or cluster-robust uncertainty.

### Address policy-induced distribution shift

J6 labels states visited by `fixed_k`. The trained sidekick will create a different state distribution because its ASK choices change future observations.

This is an offline-policy problem. At minimum:

- measure how often sidekick test states are outside the J6 feature distribution;
- compare intervention depth and error-state distributions;
- consider one post-training data-aggregation round on train only;
- do not use test trajectories to repair this shift.

### Distinguish risk from intervention value

Train and report both if possible:

\[
P(\text{failure}\mid s_t)
\]

and

\[
P(\text{planner intervention improves outcome}\mid s_t).
\]

This would make the contrast with R2V especially strong. A high-risk state does not necessarily imply that this planner can help cost-effectively.

### Treat Gate A as a resource rule

Gate A is sensible as a preregistered compute-spending rule, but it is not a proof that adaptive intervention cannot work. A periodic reviewer could have a small average effect because most calls are useless while a few are highly valuable—the exact condition where adaptive allocation could help.

Therefore phrase the stopping conclusion as:

> At this sample size and resource budget, fixed review did not establish sufficient aggregate benefit to justify training an adaptive allocator.

Avoid:

> There is nothing for a learned policy to capture.

The latter is stronger than Gate A demonstrates.

## Recommended thesis statement

I would now state the thesis this way:

> Periodic planner review wastes hosted-model computation because the causal value of an intervention varies across executor states. We estimate that value by replaying planner–executor trajectories with individual interventions ablated, use the resulting labels to train an executor-internal ASK action, and compare its quality–cost frontier with no review, fixed-schedule review, and a separately trained router on AppWorld.

The central claimed contribution can be:

> We introduce a controlled framework for learning help seeking from counterfactually validated planner interventions. Unlike failure-risk routing, the supervision estimates whether planner assistance changes the task outcome. A matched-adapter experiment isolates the effect of embedding this decision in the executor policy, and a preregistered cost-matched evaluation measures whether it allocates planner calls more efficiently than fixed and external routing policies.

That is a credible research contribution.

## Bottom line

The answer is **yes, conditionally**:

- The broad research direction is not new.
- ASK-based self-escalation is not new.
- Counterfactual agent rollouts are not new.
- Training executors on plans and corrections is not new.
- Cost-quality frontiers are not new.

But this specific scientific question remains defensible:

> **Can the causal value of individual planner interventions be learned from counterfactual environment branches and distilled into the executor itself, producing a better planner-cost frontier than scheduled intervention and a post-hoc risk router?**

That can generate new knowledge even if H1 fails.

Before spending the remaining compute, I would make three changes:

1. Redesign J6 so the branch ablates only the focal intervention, not all future reviews.
2. Rewrite H2 into the no-help quality comparison and the cost-matched allocation comparison.
3. Validate that the ASK score is a genuine, well-defined probability rather than an ambiguous first-token proxy.

With those changes, the project has a clear gap, strong internal controls, meaningful negative-result paths, and a paper-worthy empirical question.

## 144. user — 2026-09-20T03:19:17+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`
- `message_source`: `null`

this is now the thesis:
Thesis [docs/prereg_v1.md:29]: a small local executor specialised to a frozen hosted planner                            achieves superior task performance through intervention-aware training while selectively                           requesting planner assistance to displace hosted planner compute.
can we apply a more general thesis of 
a smalller executor can be trained to adapt to a frozen bigger higher capability planner model to achieve close to the bigger model result when it act as the full planner and executor while keeping the implementation cost much lower
we simple focus on the aspect of executor-planner which should differentiate us from past work?

## 145. assistant — 2026-09-20T03:19:21+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 0 item(s)]**

## 146. assistant — 2026-09-20T03:19:42+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 3 item(s)]**

```text
[1] Clarifying thesis scope and cost distinctions
**Clarifying thesis scope and cost distinctions**

[2] Refining thesis to emphasize executor specialization
**Refining thesis to emphasize executor specialization**

[3] Refined thesis scope and emphasized executor specialization

```

## 147. assistant — 2026-09-20T03:19:44+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning recap]** Worked for 23s

## 148. assistant — 2026-09-20T03:19:44+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

You can use the broader idea as the project’s motivation, but **planner–executor specialization alone does not differentiate the work sufficiently**. ProST already trains executors from orchestrator plans, CoDA trains planner–executor collaboration, and several strong–weak systems evaluate large-planner/small-worker configurations.

Your defensible distinction is:

> A small executor is specialized to a particular frozen, higher-capability planner and learns when planner intervention is worth its cost.

Also, use **inference or deployment cost**, not “implementation cost.” Training, data collection, and engineering may be expensive even if hosted-model usage falls.

## Recommended general thesis

> **A smaller local executor can be specialized to collaborate with a frozen, higher-capability planner, improving the task-performance versus hosted-compute frontier by executing routine steps locally and selectively requesting planner intervention.**

This is general, testable, and remains valid if H1 fails.

A slightly stronger version is:

> **For long-horizon tool-use tasks, specializing a smaller local executor to a frozen, higher-capability planner—including learning when to request assistance—recovers more of the planner-alone performance at lower hosted-model cost than unspecialized execution, fixed-schedule intervention, or separately routed assistance.**

That is probably the best thesis for the paper.

## Why not claim “close to the bigger model” yet?

Your proposed version says:

> “…achieve close to the bigger model result…”

But H1 is explicitly expected to fail. If the final sidekick reaches, for example, 0.55 while `planner_alone` reaches 0.684, calling that “close” becomes debatable. It also makes the entire thesis depend on an arbitrary closeness threshold.

The Pareto-frontier formulation is stronger scientifically:

\[
Q_{\text{sidekick}}(C)
>
Q_{\text{baseline}}(C)
\]

for a meaningful range of planner budgets \(C\).

This lets the thesis succeed if the sidekick provides:

- higher quality at equal planner cost;
- lower planner cost at equal quality; or
- both.

It does not require the 8B model to reach 0.684.

## Use three levels of framing

### Broad research vision

> Expensive frontier agents should perform scarce high-level reasoning, while specialized local models perform most routine execution.

This explains why the topic matters, but it is not the novelty claim.

### Scientific thesis

> Specializing a small executor to a frozen planner and embedding selective help seeking into the executor improves the quality–hosted-compute frontier over unspecialized and externally controlled collaboration.

This is the testable central claim.

### Specific methodological contribution

> Counterfactual replay identifies which planner interventions change task outcomes; those intervention-value labels are used to train an executor-internal `ASK_PLANNER` action.

This is what most clearly distinguishes your method.

## Recommended replacement for the current preregistration thesis

I would replace the current sentence with:

> **Thesis:** A small local executor specialized to a frozen hosted planner can improve the task-performance versus hosted-compute frontier by performing routine execution locally and selectively requesting planner assistance. We test whether intervention-aware training allocates planner calls more effectively than no escalation, fixed-schedule intervention, and a separately trained router.

If you want the planner-alone comparison explicitly included:

> **Thesis:** A small local executor can be specialized to a frozen, higher-capability planner to recover a greater proportion of planner-alone task performance per unit of hosted-model compute. Intervention-aware training teaches the executor when assistance is valuable, producing a better quality–cost frontier than plan-conditioned SFT, fixed-schedule review, and post-hoc routing.

## What actually differentiates you from past work

| Element | Already established? | Your difference |
|---|---:|---|
| Planner–executor separation | Yes | Not the novelty |
| Strong planner, small executor | Yes | Not sufficient |
| Plan-conditioned executor SFT | Yes, especially ProST | Your matched baseline |
| Mid-trajectory escalation | Yes, R2V and self-escalation | ASK is trained inside the executor |
| Counterfactual agent replay | Yes, CausalFlow | You estimate planner-intervention value |
| Cost-quality frontier | Yes | Applied to causal intervention allocation |
| Frozen planner-specific executor | Partially explored | Combined with intervention-value supervision |
| Matched ASK/no-ASK adapters | Much less explored | Cleanly isolates embedded help seeking |
| Fixed schedule versus endogenous ASK | Strong differentiator | Same expensive-call currency, different allocation |
| Intervention necessity labels | Strong differentiator | Labels whether assistance changes outcome |

Therefore, do not write:

> “We differ from previous work because we focus on planner–executor collaboration.”

Write:

> “Previous work studies planner–executor specialization and sequential escalation. We study whether the causal value of planner intervention can be distilled into the executor itself, allowing a model specialized to one frozen planner to allocate hosted-model calls more efficiently than fixed or external allocation policies.”

## Best final formulation

> **A small local executor can be specialized to a frozen, higher-capability planner to improve the quality–hosted-compute frontier. By learning an internal help-seeking policy from counterfactually validated planner interventions, the executor retains more of the planner-alone task performance than comparable systems using no intervention, periodic review, or a separately trained router.**

This preserves your broader vision while putting the actual research gap—**planner-specific, intervention-aware executor training**—at the center.

## 149. user — 2026-09-20T03:23:34+00:00 — model: none

- Message fields: content_type=`text`; recipient=`all`
- `message_source`: `null`

wasn't there already a paper about a small executor train and test on the ability to escalate to a bigger model? can we build on top of it to create new knowledge and have it publishable by focus on multi turn, multi step reasoning task? as compare to the past paper just being a one turn task?

## 150. assistant — 2026-09-20T03:23:38+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 0 item(s)]**

## 151. assistant — 2026-09-20T03:24:21+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`commentary`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

Yes—there are papers close enough that the novelty must be stated as an extension, not as “first learned escalation.” I’m going to verify the closest paper’s exact training setup and whether its evaluation is truly one-turn versus stepwise/agentic, then map your AppWorld design onto a defensible contribution.

## 152. assistant — 2026-09-20T03:24:29+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "site:arxiv.org small model trained escalate bigger model step-level routing residual failures R2V-Agent"}, {"type": "search", "q": "site:arxiv.org Bayesian Self-Escalation small large language model mid-generation delegation"}, {"type": "search", "q": "site:aclanthology.org trained small executor orchestrator plan AppWorld ProST"}, {"type": "search", "q": "site:arxiv.org LLM learned escalation larger model multi-turn agent tool use"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["site:arxiv.org small model trained escalate bigger model step-level routing residual failures R2V-Agent", "site:arxiv.org Bayesian Self-Escalation small large language model mid-generation delegation", "site:aclanthology.org trained small executor orchestrator plan AppWorld ProST", "site:arxiv.org LLM learned escalation larger model multi-turn agent tool use"]}`

_(empty text part in the share payload)_

## 153. assistant — 2026-09-20T03:24:35+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "https://arxiv.org/abs/2605.16604"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["https://arxiv.org/abs/2605.16604"]}`

_(empty text part in the share payload)_

## 154. assistant — 2026-09-20T03:24:40+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": []}`

_(empty text part in the share payload)_

## 155. assistant — 2026-09-20T03:24:48+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "'teacher action'"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["'teacher action'"]}`

_(empty text part in the share payload)_

## 156. assistant — 2026-09-20T03:24:58+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_queries` (metadata): `[{"type": "search", "q": "COREA collaborative reasoning small language model know when defer large model RL confidence calibration 2026"}, {"type": "search", "q": "site:aclanthology.org/2026.eacl-long.208 COREA"}, {"type": "search", "q": "\"Teaching SLMs When to Ask for Help\" executor policy ASK token"}]`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": ["COREA collaborative reasoning small language model know when defer large model RL confidence calibration 2026", "site:aclanthology.org/2026.eacl-long.208 COREA", "\"Teaching SLMs When to Ask for Help\" executor policy ASK token"]}`

_(empty text part in the share payload)_

## 157. assistant — 2026-09-20T03:25:05+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 2 item(s)]**

```text
[1] Comparing COREA and R2V multi-turn approaches
**Comparing COREA and R2V multi-turn approaches**

[2] Compared COREA and R2V multi-turn approaches

```

## 158. assistant — 2026-09-20T03:25:07+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`web.run`
- `model_slug`: `"gpt-5.6-sol-wm"`
- `search_model_queries` (metadata): `{"type": "search_model_queries", "queries": []}`

_(empty text part in the share payload)_

## 159. assistant — 2026-09-20T03:25:20+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 2 item(s)]**

```text
[1] Clarifying novelty and mechanistic distinctions
**Clarifying novelty and mechanistic distinctions**

[2] Clarified novelty and mechanistic distinctions

```

## 160. assistant — 2026-09-20T03:25:20+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`thoughts`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning summary — content_type `thoughts`, 1 item(s)]**

```text
[1] Searched 27 websites

```

## 161. assistant — 2026-09-20T03:25:20+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`reasoning_recap`; recipient=`all`
- `model_slug`: `"gpt-5.6-sol-wm"`

**[Reasoning recap]** Worked for 1m 42s

## 162. assistant — 2026-09-20T03:25:20+00:00 — model: gpt-5.6-sol-wm

- Message fields: content_type=`text`; recipient=`all`; channel=`final`
- `thinking_effort`: `"standard"`
- `model_slug`: `"gpt-5.6-sol-wm"`

Yes—the paper you remember is likely one of these two:

- **COREA** trains a small model to produce an answer plus calibrated confidence and defers the entire query to a larger model when confidence is low. Its evaluation is essentially single-query reasoning. ([EACL 2026](https://aclanthology.org/2026.eacl-long.208/))
- **R2V-Agent** is even closer to your project: it distills a small agent, trains a separate router to predict when it will fail, and substitutes a larger model’s action at risky steps. Importantly, R2V is **already multi-step and interactive**, evaluated on HumanEval+, TextWorld, and TerminalBench. Therefore, “we extend learned escalation from one-turn to multi-turn tasks” would not be a defensible novelty claim. ([R2V-Agent](https://arxiv.org/abs/2605.16604))

Your project can still produce new and publishable knowledge, but the contribution must be more precise than “multi-step escalation.”

## The critical distinction

| Dimension | COREA | R2V-Agent | Your proposed system |
|---|---|---|---|
| Environment | Single-query reasoning | Sequential interactive tasks | Long-horizon AppWorld tool use |
| Escalation decision | SLM confidence | Separate learned router | Executor’s own `ASK_PLANNER` action |
| What the large model does | Answers whole query | Directly supplies current action | Gives guidance/correction; executor retains control |
| Escalation label | Answer correctness/confidence | Every state on a failed episode is labeled risky | Counterfactual value of the specific intervention |
| Executor trained to ask | Confidence is trained | No—the executor is frozen before router training | Yes, ASK is embedded in executor policy |
| Planner relationship | Fallback answerer | Action-replacement teacher | Frozen planner supervising a subordinate executor |
| Primary metric | Accuracy versus cost | Success versus escalated steps | Task quality versus hosted planner tokens displaced |

R2V’s router label is particularly important. Every state on a failed small-model trajectory receives the failure label. The paper explicitly says that the label does **not** test whether the teacher’s intervention at that step would have prevented failure. At inference, the router either executes the SLM’s candidate or replaces it with a teacher-generated action. ([R2V method and labels](https://arxiv.org/html/2605.16604v1))

Your counterfactual branching asks a different causal question:

\[
\Delta_t =
R(\text{trajectory with planner intervention at }t)
-
R(\text{trajectory without that intervention})
\]

That estimates the **value of asking at a particular state**, not merely the probability that the current trajectory will eventually fail.

This gives you a strong conceptual distinction:

\[
\Pr(\text{executor eventually fails}\mid s_t)
\neq
\mathbb{E}[\text{benefit from planner assistance}\mid s_t].
\]

A state can have high failure risk even when the planner cannot help, or low failure risk while a cheap intervention would substantially improve the outcome. Existing risk routing does not cleanly learn that difference.

## The publishable thesis

I recommend:

> In long-horizon interactive tool-use tasks, a small executor can be specialized to a frozen, higher-capability planner by learning an internal help-seeking action from counterfactually validated interventions. This intervention-aware executor improves the task-quality–hosted-compute frontier relative to executor-only training, periodic planner intervention, and post-hoc routing.

A slightly broader paper-level version:

> We investigate whether planner–executor collaboration should be learned inside the executor rather than imposed by an external router. Given a frozen high-capability planner, we train a smaller executor both to follow its plans and to request additional guidance only when counterfactual evidence indicates that intervention has positive downstream value.

That is safer than claiming that the executor reaches “close to the bigger model,” because your preregistration already expects planner-aloneness non-inferiority to fail.

## What the paper would add beyond R2V

The paper’s contribution should be presented as four linked advances.

### 1. Intervention-value supervision

Instead of labeling every state on a failed trajectory as an escalation state, estimate whether removing the focal planner intervention changes downstream reward.

Your target is:

\[
y_t^{\text{ask}}
=
\mathbf{1}
\left[
\mathbb{E}(R\mid do(I_t=1))
-
\mathbb{E}(R\mid do(I_t=0))
>
\delta
\right].
\]

This directly targets assistance utility.

### 2. Policy-internal help seeking

The executor learns `ASK_PLANNER` as part of its action distribution:

\[
\pi_\theta(a_t\mid h_t),
\qquad
a_t\in
\mathcal A_{\mathrm{environment}}
\cup
\{\texttt{ASK\_PLANNER}\}.
\]

That lets the same model jointly represent:

- what it intends to do;
- whether it understands the plan;
- whether observations violate planner assumptions;
- whether external reasoning is worth its cost.

R2V deliberately freezes its SLM before training an external router. Your `router_seq` baseline therefore directly tests whether this factorization is inferior to embedding the decision inside the executor.

### 3. Advisory intervention rather than action replacement

R2V escalates by letting the teacher select the environment action. Your planner returns information:

\[
\texttt{ASK(reason,state)}
\rightarrow
\texttt{ANSWER(guidance)}
\rightarrow
E_\theta\text{ chooses the action}.
\]

This preserves the planner–executor division of labor: the expensive model provides scarce reasoning, while the economical executor remains responsible for grounding, tool use and implementation.

That difference should be explicit in the paper. It is stronger than simply describing both systems as escalation.

### 4. Long-horizon intervention allocation

AppWorld introduces features not captured by query-level deferral:

- delayed task reward;
- accumulating state changes;
- irreversible or difficult-to-repair actions;
- multiple potential intervention points;
- error propagation;
- partial observability;
- planner advice whose value depends on later executor behavior.

ProST already studies specialized smaller models and multi-agent training on AppWorld, so AppWorld itself is not novel. But ProST’s contribution is progressive subtask training, not counterfactually supervised self-escalation to a frozen planner. ([ProST](https://aclanthology.org/2025.ijcnlp-long.179/))

## The central comparison

The strongest experiment is not simply:

\[
\text{sidekick} > \text{sft\_plan}.
\]

It is:

\[
Q_{\text{sidekick}}(b)
>
\max
\left\{
Q_{\text{fixed-k}}(b),
Q_{\text{router}}(b)
\right\}
\]

at the same planner-token budget \(b\), while also reporting improvement over the zero-intervention SFT executor.

This creates three questions:

1. Does selective planner assistance improve over no assistance?
2. Does learned allocation improve over scheduled assistance?
3. Does executor-internal asking improve over an external router?

The third question is your clearest contrast with R2V.

## One necessary correction to the branching design

To claim causal intervention value, the counterfactual must remove only the **focal intervention**.

If the untreated branch disables all subsequent reviews, then the measured difference is:

\[
\text{current intervention}
+
\text{all future interventions},
\]

not the effect of the intervention at time \(t\).

Use one of these designs:

- Remove the focal correction but preserve the subsequent review policy.
- Evaluate a local horizon ending immediately before the next scheduled intervention.
- Replay both treated and untreated branches with the same downstream intervention policy.
- Replicate both sides across seeds and use a continuous estimated treatment effect instead of a single binary comparison.

With only two untreated samples and one observed treated trajectory, labels will otherwise be noisy. Use an indifference band:

\[
\begin{cases}
\text{needed}, & \widehat{\Delta}_t > \delta\\
\text{needless}, & \widehat{\Delta}_t < -\delta\\
\text{uncertain}, & |\widehat{\Delta}_t|\leq\delta
\end{cases}
\]

and either discard or downweight uncertain examples.

## Required baselines

For a strong submission, include:

- Planner alone.
- Executor zero-shot.
- Prompt-only planner–executor.
- `sft_plan`: trained executor, no help channel.
- `fixed_k`: periodic assistance.
- `router_seq`: separate router over the frozen executor.
- `sidekick`: policy-internal ASK.
- Random escalation at matched cost.
- Oracle escalation from counterfactual labels.
- Ideally an R2V-style residual-failure router, not only your lightweight logistic router.

Report:

- task goal completion;
- planner calls;
- planner input and output tokens;
- dollar-normalized cost;
- latency;
- needless-ask and missed-ask rates;
- ASK AUROC/AUPRC against intervention-value labels;
- quality–cost Pareto curves;
- performance by trajectory depth;
- recovery after errors;
- number and timing of interventions.

Planner calls alone are inadequate because one correction might consume radically more tokens than another.

## What you should and should not claim

Do not claim:

> We are the first to train a small model to escalate to a large model.

COREA prevents that.

Do not claim:

> Previous escalation systems only handle one-turn tasks.

R2V prevents that.

Do not claim:

> We are the first small/large system for multi-step agents.

R2V and other heterogeneous agent systems prevent that.

You can plausibly claim:

> We study executor-internal, intervention-aware help seeking for long-horizon planner–executor systems.

And, if the literature continues to support it:

> Unlike prior failure-risk routers, we derive escalation supervision from the estimated counterfactual utility of individual planner interventions and train the help-seeking decision directly into the executor policy.

## Is it publishable?

Yes—conditionally. The publishable unit is not merely “multi-turn escalation.” It is the combination of:

\[
\boxed{
\text{frozen planner}
+
\text{specialized executor}
+
\text{policy-internal ASK}
+
\text{counterfactual intervention-value labels}
+
\text{long-horizon tool use}
+
\text{matched-budget evaluation}
}
\]

A convincing positive result would show that `sidekick` dominates both `fixed_k` and an R2V-style external router on the quality–planner-token frontier. A convincing negative result could also be publishable if it establishes that policy-internal asking does **not** outperform external routing, or that intervention-value labels fail to transfer because they were collected under a different behavior policy.

Your strongest framing is therefore:

> **Beyond risk-based routing: learning the causal value of planner assistance inside a long-horizon executor.**

That builds directly on COREA and R2V while asking a genuinely unanswered question.
