# J9 — write the pre-J10 freeze

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own **one new file**: `docs/prereg_j9_freeze_20260920.md`. Create nothing else and modify
nothing else. **Do not commit, do not run git, do not `qsub`, do not run python, do not run any
analysis.** A live GPU job (`25560367`) is running; leave it alone. `aquarius01` is a login node —
steering only.

**Do not edit `docs/prereg_v1.md` or `docs/prereg_b1_pilot.md`. Both are FROZEN: read only.**

## What this document is

A freeze written on **dev evidence only, before any test split is read**. It records what J10 will
measure and how, so that the test read is a confirmation rather than a search. It must be honest
that several of its choices are changes from `prereg_v1`, must say why each change was made, and
must say what evidence would have to appear for the change to be wrong.

Every decision below is mine; your job is to write it up precisely and to flag anything that does
not follow. If a decision looks unsupported by the evidence quoted, say so in STATUS rather than
writing around it.

## Source of every number

`campaign/RUNS.md` §10 (the J8 dev frontier, twelve arms, n=114) and
`campaign/results/hj8_frontier_dev_20260920.report.json`. **Read §10 and cite it**; do not restate
numbers from memory and do not cite this brief.

## Decision 1 — the primary claim changes from H2b to F1

`prereg_v1` H2b asks whether the gated policy beats `fixed_k(k_matched)` and `router_seq(τ*)` at
matched planner calls. On dev, no gate discriminates: on real decision points every gate's AUROC is
at or below chance, and all three `sidekick` arms and `router_seq_tau07` escalate zero times, making
them behaviourally identical to `sft_plan`. A superiority test between a policy and itself is not a
test.

**Freeze: the primary claim is F1 — displacement at non-inferior quality.** The policy is
non-inferior to `fixed_k(k_matched)` within a pre-set margin and makes strictly fewer planner calls
than `fixed_k(5)`, both on test.

**H2b is retained as a pre-registered negative result**, reported with its dev evidence and its test
numbers. It is not dropped and not quietly demoted: the document must state that it was the original
primary and that it failed on dev for a stated reason.

## Decision 2 — the primary metric changes from TGC to goal-pass rate

This is a change and must be labelled as one, with its justification and its risk.

Justification, from §10's replicate-noise measurement: the three `sidekick` configs differ only in
`verifier.threshold`, all escalated zero times, so the threshold had no causal effect and the arms
are three stochastic replicates of one policy. Across them, TGC spans 3.5 pp and goal-pass spans
0.9 pp. A 7 pp non-inferiority margin is about twice TGC's own replicate noise, which makes a TGC
non-inferiority test close to uninformative; goal-pass is roughly four times steadier.

**Freeze: `goal_pass_rate` is the primary metric for F1. TGC is reported alongside, always, as a
secondary.** Both are reported for every arm and every contrast whatever the outcome.

The risk must be stated plainly in the document: **choosing the primary metric after seeing dev
results is a researcher degree of freedom.** The mitigations, which must all be named: the choice is
made on dev only, it is recorded before any test read, the justification is a variance property
rather than an effect size, both metrics are reported unconditionally, and the dev values that
motivated the choice are quoted so a reader can check that the decision was not made on the basis of
which metric looked more favourable. State explicitly whether TGC or goal-pass gave the more
flattering dev picture — from §10, say which, and do not omit it if it is the one now chosen.

## Decision 3 — the non-inferiority margin stays at 7 pp, and "matched calls" is declared ill-posed

The 7 pp margin is inherited and is **not** changed; changing both the metric and the margin after
seeing dev would leave nothing pre-registered. Record that on dev the paired CI half-widths were
roughly 9–11 pp at n=114, that test has 504 pairs, and that the expected narrowing of about 2.1×
brings half-widths to roughly 4–5 pp, making a 7 pp margin resolvable on test where it was not on
dev.

Separately, record a limitation the F1 machinery currently hides: `k_matched` is chosen as the
`fixed_k` arm nearest in calls, and for a policy that makes 1.00 calls per episode the nearest
available arm is `fixed_k_10` at 2.75. **That is not a matched-cost comparison, it is the nearest
one that exists**, and the document must say so. The honest presentation of F1 is a point on a
cost–quality frontier, not a matched-cost superiority test.

## Decision 4 — the J10 arm list

Freeze this list, with the stated reason for each:

| arm | seeds | why |
|---|---|---|
| `executor_alone` | 3 | the one large unambiguous dev effect (TGC 0.1316 vs 0.4035 for `sft_plan`); anchors the bottom of the frontier |
| `sft_plan` | 3 | the reference policy; F1's quality side |
| `fixed_k_10` | 3 | `k_matched` for the 1.00-call policies |
| `fixed_k_5` | 3 | F1's cost comparator, fixed by the F1 rule |
| one gated arm, `sidekick_tau05` | 3 | a pre-registered check that the gate remains degenerate on test; it costs 1.00 calls per episode, so it is nearly free |

Dropped, with reasons to record:

- `planner_alone` — approximately 500 episodes × ~20 calls ≈ 10k of an ~11.5k budget, serving only
  secondary H1. Dropped on cost. Record that H1 therefore rests on dev and on the earlier HJ-1
  evidence, and that this is a deliberate weakening.
- `sidekick_tau03`, `sidekick_tau07`, `router_seq_tau07` — behaviourally identical to `sidekick_tau05`
  on dev (zero escalations, 1.00 calls). Running them on test measures the same policy repeatedly.
- `router_seq_tau03` — 15.39 calls per episode and 203.5M planner tokens for the worst quality of any
  dev arm. Its test cost would dominate the budget to confirm a result dev already establishes.
- `oracle_escalation` — **cannot be run on test at all**: its labels come from the J6 dev branch
  sweep and no test-split oracle labels exist. Record this as a hard limitation, not a choice. F2's
  headroom result is therefore a **dev-only** result and must be presented as such.

## Decision 5 — what the paper claims

Record the claim set that the dev evidence actually supports, in this order:

1. A small executor specialised to a frozen planner follows plans well: `sft_plan` TGC 0.4035
   against `executor_alone` 0.1316 — the largest effect measured.
2. Fixed review schedules waste most of what they spend: the J6 measurement (232/734 ticks fire on
   already-succeeding episodes, 11.3 % `needed`), now corroborated live by `router_seq_tau03`
   spending 203.5M tokens to finish last.
3. Adaptive allocation is worth something: on dev, `oracle_escalation` matches `fixed_k_10` quality
   (−0.88 pp, CI [−10.53, +9.65]) at 47 % of the calls and 14 % of the tokens. **Equal quality at
   lower cost — not dominance.**
4. **Learned gating does not yet work.** Both gate families are at or below chance on real decision
   points; the self-gate's `p_ask` never exceeds 0.0347 against thresholds of 0.3/0.5/0.7. This is
   reported as a result, with the negative framing intact.

State that the thesis sentence — displacement of hosted planner compute at non-inferior quality —
is currently carried by the plan-following policy rather than by a working gate, and that this is a
weaker result than `prereg_v1` anticipated.

## Decision 6 — B1 and H4 are out of scope for this freeze

The B1 counterfactual pilot (`25560367`) is running and its analysis is governed by
`docs/prereg_b1_pilot.md` §9, which is frozen. H4 and `sft_c` depend on it. Record that J9 does not
freeze anything about H4, that B1's result may change what can be claimed about gating, and that
`sft_c` was never trained (paused; ASK labels noisy at p=0.7124). Do not pre-judge B1's outcome.

## Decision 7 — sign-off gate

End the document with an explicit statement that **J10 has not been submitted**, that the test split
remains unread, and that submission requires the user's go-ahead because it spends roughly a
thousand planner calls and consumes the one-shot test read. List, as open questions for that
sign-off, the four items currently outstanding: whether to add a random-escalation-at-matched-cost
arm, whether the degenerate threshold arms are worth any test budget at all, that latency is not
accumulated in the ledger and so cannot be reported, and B1's timing relative to the rest.

## Constraints

- Every number must come from `campaign/RUNS.md` §10 or the report JSON, cited
  `[OBSERVED <path>:<line>]` or `[OBSERVED <path>: key "<k>"]`. Judgements are `[INFERRED]`.
- Do not cite this brief as evidence for anything.
- Do not use "dominates", "proves", "state-of-the-art", or "significant" where you mean "large".
- Do not touch the frozen preregs.

## Return contract

Write `campaign/workers/STATUS_J9.md`. Final report, eight lines or fewer: the file you created and
its length, the seven decisions as one line each confirming what you recorded, and anything you
judged unsupported by the cited evidence.
