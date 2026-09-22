# Novelty Boundary v2 — what is ours after the pivot, and what would take it away

**Date**: 2026-09-23
**Author**: Claude (orchestrator). The verdicts below are judgements, not retrieval, and are mine.
**Supersedes**: `docs/novelty_boundary.md` (2026-09-15), which was written for the advice-channel
thesis and is kept unedited as a record of what we believed before the pivot.
**Evidence base**: `campaign/workers/lit/extracts_20260922.md` (verified fetches) and
`docs/literature_review_20260923.md`. Any claim about a paper here must trace to the extracts file,
not to the review's prose, until `docs/lit/bibliography_audit.csv` is clean.

---

## 0. The honest one-paragraph version

**"A cheap model can finish an expensive model's trajectory" is no longer novel.** Ganz et al.
published it on 2026-08-25 for SWE-bench with frontier-tier model pairs, and found the same
qualitative result we did: handing a partially-completed trajectory down to a cheaper model is a
favourable cost-quality point. If our thesis claims that sentence, it is scooped by five weeks.

What is not in that paper, or in any other we found, is **the shape of the trade-off** — how quality
moves as the handoff point sweeps across the episode — **the channel comparison** — the same hosted
budget spent as advice versus as actions — and **a receiver that was trained for the job** rather than
prompted zero-shot. Those three, plus the pre-registered statistics, are the contribution. Everything
below is an attempt to state that precisely enough to be attacked.

---

## 1. The adversarial collapse matrix

Format inherited from `docs/novelty_boundary.md:20-27`. "Collapse condition" is the empirical result
that would make our contribution a special case of theirs.

| Neighbouring work | What they did | What we do differently | Collapse condition | Arm that tests it |
|---|---|---|---|---|
| **The Handoff Tax** (Ganz et al., arXiv 2608.24358, 2026-08-25) — the closest paper | Swept switch points p5–p50 on SWE-bench Verified, Claude and GPT pairs, **averaged results over the seven switch points**, **zero-shot receivers**, one episode per task, no CIs, HC never used as a critic | Sweep prefix depth and **report the curve rather than its average**; a **tailored** open-weight 8B receiver **with a zero-shot control**; the strong model in both an **acting** and an **advising** channel at matched budget; pre-registered non-inferiority with clustered CIs over two seeds | Our zero-shot receiver shows the same rise across $m$ as the tailored one **and** the curve turns out to be smooth rather than threshold-shaped. Then we have reproduced their downshift result on a second benchmark with error bars, which is a replication, not a contribution. | `hj13_prefix_zs_m{6,9,11}` (zero-shot control) vs the tailored arms; the F1 breakpoint test |
| **Reach or Solve?** (arXiv 2609.19636, 2026-09-17) | "Checkpoint handoff": clone a state one policy reached, hand to another, no retraining. **Same-capacity** SFT vs RL checkpoints, **fixed** handoff point, ALFWorld/TravelPlanner, no cost axis | Asymmetric capability and **cost** tiers rather than two checkpoints of one model; handoff depth is the **swept independent variable**; hosted spend is the axis | Nothing they report collapses ours — but we must **cite them for the protocol** rather than present replay-handoff as our invention. Their finding that restricting to states both policies reach *selects on an outcome and can flip the sign* directly threatens our pinned-key-set analysis and must be addressed, not ignored. | our pinned `--handoff-keys-from` analyses |
| **ReOPD** (Microsoft, arXiv 2607.04763) and **Guided-OPD** (arXiv 2606.15912) | Replay teacher prefixes / mix teacher turns **during training**; teacher is withdrawn at inference; ReOPD names the "prefix trap" | Train on teacher-prefix suffixes for a deployment in which **the prefix persists at serving time**. Train and serve are matched rather than mismatched | Our suffix-trained adapter fails to beat the plan-conditioned adapter on the prefix arms. Then C3 is a negative and our tailoring story rests only on the zero-shot contrast. | `sft_b_plus_handoff_granite8b` vs `sft_b_plus_iaware` on `prefix_m{6,9,11}` |
| **SwiftSage** (arXiv 2305.17390) | Small model acts by default, GPT-4 invoked **on exception**; small module fine-tuned on oracle trajectories | The strong model acts **first**, for a contiguous opening stretch, then leaves. Allocation is a **continuous depth**, not an interrupt | Our curve turns out to be flat everywhere and only exception-triggered escalation helps. Then the useful structure is SwiftSage's, not ours. | the prefix curve vs `hj12_takeover_exception` / `advise_exception` |
| **Stepwise / turn-level routing** (2605.06116; 2607.11399 Agentic Routing; 2604.23530 MTRouter; 2607.00053 SWE-Router) | Decide per step or per turn which model acts, usually to minimise cost at fixed quality; routers are learned; receivers are **not** fine-tuned; none reports quality as a function of *how much* of the episode the strong model executed | We fix the allocation **by construction** and measure the whole frontier, so the result is a property of the problem rather than of a particular router. We also train the receiver | A trivial router beats our best fixed-$m$ point at equal cost, making the fixed sweep merely a worse router. (Note this is a *different* claim from ours and we should say so rather than compete.) | `hj12_planner_handoff` (planner picks its own point) against the fixed-$m$ curve |
| **Role-factorised teams** (ProST 2509.04508; AgentCARD 2606.20629; Think-Big-Search-Small 2607.07548; CoDA 2512.12716; Three-Roles-One-Model 2604.11465) | Assign planner/executor/critic roles to models of different sizes for the **whole episode**; sweep *capacity*; some train the small executor | We hold the roles fixed and sweep **when** the handoff happens along the episode's time axis. Our allocation variable is temporal, theirs is architectural | Quality depends only on which role the strong model holds and not on how long it holds it — i.e. our curve is flat. | the prefix curve |
| **Query-level cascades** (FrugalGPT 2305.05176; RouteLLM 2406.18665; Hybrid LLM 2404.14618) | Route a whole query by predicted difficulty before execution | Intra-episode allocation, where difficulty is revealed by tool results after the episode starts | Episode difficulty proves predictable up front, so a task-level router matches the best point on our curve at equal cost | `planner_alone` vs `executor_alone` gap by task, and the failure-anatomy split |
| **Token-level collaboration** (speculative decoding 2211.17192, 2302.01318; Co-LLM; BiLD; CITER) | Draft-and-verify at token granularity, co-located, with exactness guarantees | Macro-actions with irreversible environment side effects, a remote black-box planner, and **no verification of what the small model did**. We must describe preservation as *empirical non-inferiority*, never as a guarantee | Not a collapse risk; an over-claim risk. If we ever write "preserves quality" without "empirically, on this distribution", the analogy becomes a false claim | n/a — wording discipline |
| **Small-model self-correction limits** (2310.01798; TACL 2024; 2404.17140) | Show small models cannot reliably act on natural-language critique **of their own output** without an external verifier | We price an **externally authored** critique from a stronger model, at matched budget against the same model acting | Our full-context advice arm at high budget closes the gap to the action channel. Then the advice channel was starved, not weak, and our channel claim dies | `hj12_advise_fixed_k_10_fullctx`, `hj13_advise_fixed_k_1_fullctx` |
| **AppWorld SOTA** (LOOP 2502.01600; CANOPY 2609.01245 at 86.9 test_normal; ACE 2510.04618) | Maximise benchmark score, mostly via heavy on-policy RL on a standalone agent | We do not compete on score. We measure a collaboration frontier under a frozen hosted planner with lightweight offline adaptation | Not a collapse condition — a **framing** risk. Any sentence implying we approach the leaderboard is false and must not appear | n/a — see the leaderboard caveat in §3 |

---

## 2. The nine per-theme verdicts

These are the `What we add` paragraphs for `docs/literature_review_20260923.md`, one per theme, to be
spliced in verbatim.

### Theme 1 — Query-level cascades and routers

> We keep the cost-quality framing of this literature and move its decision variable inside the
> episode. A cascade asks *which model should answer this query*; we ask *how much of this episode's
> opening should the expensive model execute before the cheap one takes over*. The distinction is
> not merely granularity: a query-level router must predict difficulty from the prompt, whereas our
> allocation is made against difficulty that the environment reveals only after execution begins. We
> inherit their evaluation discipline — cost on an explicit axis, quality reported against it — and
> contribute the observation that on a stateful suite the frontier's *shape* along this new axis is
> not the smooth concave curve cascade work leads one to expect.

### Theme 2 — Step/turn-level routing and mid-trajectory switching

> This is where our contribution must be stated most carefully, because Ganz et al. (2026-08-25)
> reported the qualitative result — a cheaper model can continue a stronger model's trajectory at a
> favourable cost-quality point — five weeks before this work was written, and we do not claim it.
> We add three things their design forecloses. First, they average over seven switch points and so
> report a *point*; we sweep nine depths and report a *curve*, and the curve is not monotone in the
> way an averaged summary implies — it is flat across the first third of a median episode and rises
> only past a threshold. Second, every receiver in that study is prompted zero-shot; ours is
> LoRA-specialised to the specific planner whose trajectory it inherits, and we run the zero-shot
> receiver as an explicit control so that "tailored" is measured rather than asserted. Third, their
> capability gap is between two frontier-tier hosted endpoints, while ours is between a hosted
> frontier planner and an 8B open-weight model running locally at no marginal hosted cost — the
> regime in which the displacement question actually bites. We also supply what a single-rollout
> study cannot: pre-registered non-inferiority testing with paired, task- and scenario-clustered
> bootstrap intervals over repeated seeds. None of this contradicts their findings; it measures the
> object they summarised.

### Theme 3 — Fast/slow agents and speculative planning

> Our allocation runs in the opposite temporal direction to this entire lineage. SwiftSage and the
> early-exit work let the weak model act until something goes wrong and then summon the strong one;
> we spend the strong model first, on the opening stretch, and then leave. That inversion is
> motivated by the failure mechanics in Theme 8 rather than by convenience: if the first error
> dominates the outcome, compute is worth more before the error than after it. Speculative planning
> shares our vocabulary but not our economics — there the target model verifies every step, so the
> small model never holds terminal authority and the saving is latency, not hosted spend. We give
> the small model the rest of the episode outright and measure what that costs in quality.

### Theme 4 — Token-level collaboration

> We take only the intuition from this literature and explicitly disclaim its guarantee. Speculative
> decoding preserves the target model's output distribution exactly, because every draft token is
> verified and rejection sampling is available. No agent-level analogue of that guarantee exists
> here: our planner does not observe, let alone verify, the actions the executor takes after handoff,
> and AppWorld actions write to databases and call APIs, so there is nothing to roll back. Our
> contribution at this boundary is therefore a discipline rather than a method — we state capability
> preservation as empirical non-inferiority on a declared distribution with a pre-registered margin,
> and never as preservation in the speculative-decoding sense.

### Theme 5 — Role-factorised heterogeneous teams

> This literature sweeps *capacity* across roles and holds the assignment fixed for the episode; we
> hold the roles fixed and sweep *time*. Think-Big-Search-Small's finding that delegation is far more
> capacity-sensitive than execution is the closest quantitative neighbour to our own regime result
> that one plan is worth most of the available gain, and we should cite it as convergent evidence
> from a different domain rather than as a competitor. What no role-factorisation study reports is
> that the value of strong-model involvement is *non-linear in its duration*: assigning the strong
> model the planner role for a whole episode and assigning it the first nine actions are different
> allocations at different prices, and only the second is on the frontier we measure.

### Theme 6 — Agent distillation and the reverse-curriculum lineage

> Our training contribution sits in a gap these two literatures leave between them. ReOPD and
> Guided-OPD replay teacher prefixes *during training* precisely so that the student can eventually
> run alone, withdrawing the teacher before deployment; the classical reverse-curriculum work
> (Backplay, Salimans & Chen) moves a demonstration-derived start state backward through training for
> the same reason. In both cases the prefix is scaffolding to be removed. In our deployment the
> prefix is not scaffolding — it is the product, purchased anew on every episode — so the matched
> training objective is the one nobody has needed before: supervise the suffix that follows a teacher
> prefix, for a serving condition in which that prefix is always present. We also import ReOPD's
> warning under a new name: their "prefix trap" is a statement about where teacher supervision is
> reliable, and its deployment-time counterpart is that the executor is only on-distribution for
> prefixes drawn from the planner it was trained against.

### Theme 7 — Advice, critique and self-correction limits

> The established negative results here concern *self*-correction, and are therefore adjacent to our
> finding rather than identical to it: our critique is externally authored by a materially stronger
> model, which is the condition under which that literature expects correction to work. Our
> contribution is to put a price on it and compare it, at matched spend, against the same strong
> model spending the same budget on actions instead of words. That comparison is what the literature
> lacks, and it is also the claim our own evidence does not yet support: at matched budget our two
> channels are currently indistinguishable, and advice has never been priced at the budget where the
> action channel wins. Until the full-context and step-level advice arms run, the honest statement is
> that advice saturates early — cheaply — and that whether it would ever catch up is untested.

### Theme 8 — Long-horizon failure mechanics and learning-to-defer

> This literature supplies the mechanism our curve needs and, read carefully, predicts the wrong
> shape. If early errors are unrecoverable, buying the strong model's first few actions should pay
> immediately, and quality should rise steeply and then saturate. We observe the opposite: nothing is
> bought until roughly the seventh step, after which quality climbs. That mismatch is the most
> interesting thing in our data, and our mechanism chapter takes it as its subject — testing whether
> the threshold coincides with where novel API discovery ends rather than with where errors begin.
> Against learning-to-defer, our allocation is deliberately *not* learned: every gate we measured sat
> at chance, so we fix the allocation by construction and characterise the frontier a learned deferral
> policy would have to beat.

### Theme 9 — AppWorld, its state of the art, and evaluation statistics

> We make no claim on this benchmark's leaderboard and our numbers are not comparable to the entries
> on it: we evaluate on dev, in a minimal harness, with a capped planner, and every claim we make is
> internal and paired. Reporting the external table matters anyway, for one reason — it shows that
> our frozen planner scores well below its own published figure under our scaffold, which bounds how
> far our conclusions travel. Methodologically we contribute what this benchmark's results sections
> generally omit: a pre-registered primary metric and margin, paired contrasts with clustered
> bootstrap intervals, repeated seeds, explicit populations, and a public record of which analyses
> were registered in advance and which were chosen after seeing the data.

---

## 3. Standing wording rules that follow from the above

1. Never write that a cheap model finishing a strong model's trajectory is new. Cite Ganz et al. and
   claim the curve, the channel and the tailoring.
2. Never write "preserves quality". Write "non-inferior within the pre-registered margin on dev,
   under the stated populations".
3. Never write "never reaches the plan-only floor" for the advice arms. They are *indistinguishable*
   from it.
4. Never compare our TGC to a leaderboard entry without the scaffold, split and cap caveat in the
   same sentence.
5. Never describe m7–m11 as anything but exploratory, and never describe the shape test on the
   existing arms as confirmatory.
6. Replay-handoff as an evaluation protocol is cited to Reach-or-Solve, not claimed.

## 4. What would make this thesis not worth publishing

Stated plainly so the decision is not made by accumulation. If **all** of the following hold after the
repairs and the approved hosted wave, the contribution is a replication with error bars and should be
written up as a short empirical note rather than a thesis chapter set:

- the zero-shot receiver rises like the tailored one (tailoring does nothing), **and**
- the suffix adapter does not move the curve (C3 negative), **and**
- full-context advice at high budget matches the action channel (no channel effect), **and**
- the curve has no threshold once the terminal-guard repair lands.

Any one of these failing leaves a real contribution. All four failing leaves Ganz et al.
