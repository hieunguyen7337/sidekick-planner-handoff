# S5 addendum: fold the planning literature into Paper A v2

Same rules as `campaign/workers/briefs/20260924_s5_paper_v2.md` (numbers only from ledger rows; audit exit 0 except
`[[NEEDS LEDGER]]` markers; no exploratory result called registered; edit only
`paper/preprint_dev_v2_20260924.md` and `paper/bibliography.bib`; do not commit). v2 is committed as 88186f7, so
your edits will be reviewed as a diff against it.

## 1. New related work: verified to exist by Claude's checker; read each yourself before citing
Open each with WebFetch and cite only what you read. Describe each in one or two sentences, in §7 unless noted.
- **Fan et al., arXiv 2609.20804**, "An Empirical Study of Harness Design for Coding Agents" (first author Run-Ze
  Fan, 17 Sep 2026). 176 matched settings; planning raises the weakest model's (Nemotron-3 30B) success by 11.6 pp
  on SWE-Bench and 4.5 on Terminal-Bench, while for the two strongest models it cuts SWE-Bench cost by about 30 %
  and 32 % at a 2.0 / 0.4 pp success loss; without planning 68.6 % of the 30B's runs end without an edit (27.8 %
  with). Use it in §1 to place our 8B executor in the regime where outside help changes success, not cost.
- **Liu et al., arXiv 2604.12147**, "From Plan to Action: How Well Do Agents Follow the Plan?" (Shuyang Liu; the
  title is this one, not "Evaluating Plan Compliance…"). A standard plan improves resolution; periodic plan
  reminders reduce violations; a subpar plan hurts more than none; they call for fine-tuning models to follow plans.
  Our tailored receiver is such a fine-tune; and on our executor periodic prose advice adds little over the first
  plan (ADV-FC-01, QUAL-04), a contrast worth one sentence.
- **Si et al., arXiv 2510.05608** (EAGLET, ACL 2026), "A Goal Without a Plan Is Just a Wish…": trains a global
  planner with an executor-capability-gain reward; the gain is larger for Llama-3.1-8B than for GPT-5. They train the
  planner; we hold it frozen and vary the channel and the receiver.
- **Agrawal, arXiv 2609.05232**, "Substrate-Aware AI Agents: Execution Context as a First-Class Input": giving
  frontier models information absent from their default planning state (resource contracts) changes outcomes.
  One sentence, as support for reading our channel result as *information* delivery.
- **Vasileva, arXiv 2608.12426**, "Large Language Models Can Follow Instructions, But Not Many at Once…": planning
  leaves per-constraint reliability unchanged. One sentence beside MECH-05 (a deeper prefix lowers the executor's
  error incidence by taking steps away from it, not by planning).
- **Sun et al., arXiv 2606.04874**, "Agent Planning Benchmark…": step-wise, feedback-conditioned planning is more
  robust than holistic plans. Optional; cite only if it fits the trigger-frequency discussion.
- **Feng et al., arXiv 2608.20274**, "Break It Down, Pass It On: Cross-Task Skill Transfer in LLM Agents": AppWorld,
  planner/executor/summarizer, Qwen3-8B among the models, reports text skills transferring better than code
  skills. **Read it first**: it is about cross-task skill transfer, not in-episode advice; say precisely how its
  "text vs code" differs from our code-bearing advice (DEC-06) before juxtaposing them.

## 2. A taxonomy table (in §2.3 or §7, your choice; <= 8 rows)
Map our arms onto the literature's slots, values from the ledger only: nothing (no-op, NOOP-01); executor alone
(base / tailored); one external plan (base `prompt_only` / tailored `sft_plan`: CHAN-ZS-01, ADV-FC-01, UF-01);
external plan + periodic feedback (advice k = 10 / every step); the planner's actions executed (takeover, prefix);
the same actions as text (narrated, NARR-02); the planner alone. Two slots are empty and are now being run as
exploratory dev controls: the executor's **own** plan (self-plan) and a **wrong-task** plan of matched length. Add
one placeholder subsection for each, as for R2.4/D2/D3: heading + one sentence (exploratory on dev; what it will show).

## 3. Reframes
- **Scope** (§1 and §8): our executor is in the weak regime; the paper says nothing about planning for frontier
  executors.
- **Information, not structure** (§3 discussion): the evidence that the planner's value is instance-specific
  content is NARR-02/NARR-05 (actions carry it, observations add nothing), DEC-06 (code), MECH-08 (API discovery is
  front-loaded). The D2 structured-advice placeholder is the direct test of structure without that content; say so
  in its one sentence.
- **Placeholders for rows being computed now** (write the marker exactly, Claude fills them):
  `[[NEEDS LEDGER: PLANTAX tailoring x plan DiD]]` (does a plan help the tailored executor more than the base one,
  and does that gap vanish in the action channel), `[[NEEDS LEDGER: TERM termination census]]` (Fan-comparable: how
  our executors fail: stopping before acting vs running to the limit), `[[NEEDS LEDGER: CEILHI high-effort planner
  alone]]`.
- **§2.2 correction.** The D3 arm (luna alone at `high` effort, cap 81) has finished; its paired rows are being
  computed. Replace "The reference is therefore harness-limited" with wording that the reference is limited by the
  harness **and by reasoning effort**, pointing at the D3 subsection with the CEILHI marker. Write no number.

## 4. Length
Main text back to <= 7,300 words after these additions (move detail to appendices).

## Report (<= 300 words)
Word counts; audit final output; each new citation with the sentence you read that supports it; markers added.
