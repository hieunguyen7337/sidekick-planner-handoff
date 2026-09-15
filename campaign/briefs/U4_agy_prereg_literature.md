# U4 — preregistration, literature matrix and novelty boundary (owner: Antigravity / agy)

## Goal

Three documents that fix what this study claims **before** any result exists, and place it honestly
among the work that already exists. These are judgement documents, not code. Write them so a sceptical
reviewer can check every claim.

Read first, in this order:
- `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/docs/PLAN.md` (the actual study)
- `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/RESEARCH_PROJECT_SPEC.md` (the
  full spec this is a reduced proof of concept of)

## Deliverable 1 — `docs/prereg_v1.md`

A preregistration draft. Sections, in this order:

1. **Question and hypotheses.** H1 non-inferiority of the collaboration against the planner alone with
   displacement; H2 intervention-aware training beats intervention-agnostic training at matched planner
   cost; H3 escalation is calibrated; H4 training escalation into the policy beats a bolted-on router.
   State each as a directional, falsifiable prediction.
2. **Design.** Eight systems, paired by task and seed on AppWorld; train 105 / dev 60 / test_normal 168;
   3 seeds on the final run; what is frozen and when.
3. **Primary and secondary outcomes.** Primary: task goal completion, and frontier-compute displacement
   on planner tokens. Secondary: scenario goal completion, planner calls, dollars, intervention burden,
   escalation precision and recall against oracle labels, needless-ask rate, unsafe-action rate.
4. **Analysis plan.** Paired bootstrap, 10,000 resamples; one-sided 95% CI for non-inferiority at
   **ε = 5 percentage points**; how ties, crashes, timeouts and limit-hits are handled (they stay in the
   denominator with an `error_type`); the multiple-comparison policy across the λ sweep.
5. **Stopping and decision rules.** What result would make us abandon the method; what counts as a
   successful replication of H2; the rule that the final test run happens **once**.
6. **What is explicitly not claimed.** No leaderboard position, no frontier-model claim (the planner is
   the cheapest GPT-5.6 tier), no online-RL claim.
7. **Deviations register.** A table with columns: spec requirement, what this study does, why, date.
   Seed it from §2 of `docs/PLAN.md`.

The most important paragraph in the document: the plan predicts, **in advance**, that a post-trained 8B
executor is unlikely to reach non-inferiority at a high displacement rate, because published numbers put
a frozen ~8B model at 1–17 task goal completion and supervised fine-tuning at roughly 26–33, against 85
for the planner. Write the rule that follows from that: the deliverable is the quality-versus-
displacement frontier, H2 and H3 are the claims that survive a weak executor, and a weak H1 must not be
retold afterwards as though H1 was never the headline.

## Deliverable 2 — `docs/literature_matrix.md`

Roughly 12 papers, each with a machine-readable YAML block: `key`, `title`, `venue_or_arxiv`, `year`,
`url`, `what_it_does` (2 lines), `relation_to_us` (2 lines), `numbers_we_cite`.

Start from these, **verify each one by fetching it** (do not trust this list blindly — one of the
identifiers below may be wrong, and finding that is part of the job):

| area | starting points |
|---|---|
| the benchmark | AppWorld (arXiv 2407.18901) |
| training small models on AppWorld | ProST (arXiv 2509.04508); LOOP (arXiv 2502.01600); CANOPY (arXiv 2609.01245); CoEvolve (arXiv 2604.15840); Three Roles One Model (arXiv 2604.11465) |
| routing and escalation | R2V-Agent (arXiv 2605.16604), a Brier-calibrated CVaR-constrained router over a frozen policy's residual failures; FrugalGPT; RouteLLM |
| synthetic agent environments | EnvScaler (arXiv 2601.05808) |
| the models | Granite 4.2 (ibm-granite on Hugging Face); gpt-oss (openai.com) |

For each, `numbers_we_cite` must record the exact figure and where it came from, because these numbers
appear in our related-work table and in the calibration argument.

## Deliverable 3 — `docs/novelty_boundary.md`

One page. For each neighbouring work, a row: **what they did / what we do differently / what would make
our contribution collapse into theirs**. Be adversarial about the last column — that is the point of the
document. Cover at minimum:

- ProST and other plan-conditioned SFT: they condition on plans; we train the executor to judge when its
  own action is insufficient. If plan-conditioned SFT alone reproduced our gains, our contribution is
  gone — which is exactly why `sft_plan` is a system in the comparison.
- R2V-style routers: they bolt a calibrated router onto a frozen policy; we train the escalation
  decision into the policy. `router_seq` is the control that tests this.
- Cascades and query routers (FrugalGPT, RouteLLM): they route whole queries by difficulty; we route
  *within* an episode, at the step level, with an executor that has been specialised to one planner.
- RL work on AppWorld (LOOP, CANOPY): they reach far higher absolute scores with on-policy RL. State
  plainly that we do offline post-training, that their numbers are not comparable to ours, and what our
  result would and would not imply about theirs.

## Constraints

- Shared HPC login node: **no Python, no package installs, nothing heavy.** Put `timeout <seconds>` in
  front of every command. **Do not run any `git` command.**
- You own only `docs/prereg_v1.md`, `docs/literature_matrix.md`, `docs/novelty_boundary.md` and
  `campaign/workers/logs/U4_STATUS.md`. Other agents are editing `src/`, `scripts/`, `docs/PLAN.md` and
  `docs/HEAVY_JOBS.md` right now — do not touch those.
- Every citation must be **fetched and verified**. Tag claims `[OBSERVED <url>]` or `[INFERRED]`. If an
  identifier in the table above does not resolve, say so explicitly rather than inventing a plausible
  reference. A fabricated citation is worse than a missing one.

## Return contract

At most 20 lines: the three files written, how many papers were verified and how many identifiers failed
to resolve, the single strongest threat to novelty you found, and anything in `docs/PLAN.md` that struck
you as scientifically weak.
