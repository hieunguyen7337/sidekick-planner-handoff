# D3 — record the train/serve intervention mismatch, and what it invalidates

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own **`docs/FOLLOWUPS.md`** (append a new entry) and **`campaign/RUNS.md`** (append a new
section 11). Touch nothing else. **Do not commit, do not run git, do not `qsub`, do not run python,
do not modify any code.** `aquarius01` is a login node — steering only.

**Do not edit `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md` or
`docs/prereg_j9_freeze_20260920.md`.** The first two are FROZEN; the third is today's freeze and is
settled.

## The finding (all citations below were verified directly against the code — reuse them verbatim)

The executor adapter is evaluated on an input class it was never trained on.

**Training strips planner interventions from the context, at three enforcement layers:**

- `src/sidekick/training/matched_sft.py:255` and `:316` — `strip_interventions: bool = True`, the
  default.
- `src/sidekick/training/matched_sft.py:262` —
  `working = [m for m in working if not _sft._is_intervention_turn(m)]`
- `src/sidekick/training/matched_sft.py:445-446` — an example whose rendered context still contains
  the mark is discarded: `drop(task_id, seed, DROP_INTERVENTION_LEAK)`.
- `src/sidekick/training/matched_sft.py:597-600` — the writer refuses to emit such a dataset at all:
  `raise RuntimeError("combined dataset contains an INTERVENTION: turn; refusing to write")`
- The mark is `INTERVENTION:` [`src/sidekick/training/sft_data.py:48`]; the drop reason is named
  `intervention_in_context` [`src/sidekick/training/sft_data.py:46`].

**The runtime injects exactly that turn at evaluation time:**

- `src/sidekick/systems/loop.py:748` and `:775` —
  `exec_turns.append({"role": "user", "content": f"INTERVENTION: {correction}"})`
- The same applies to the reply to an executor ASK, `ANSWER: {answer}`
  [`src/sidekick/systems/loop.py:856`], and to `ASK_IGNORED` [`src/sidekick/systems/loop.py:881`,
  `:898`].

**Consequence:** `sft_b_plus_granite8b` has seen essentially zero `INTERVENTION:` turns in context
during training (a read of the built dataset found 1 preserved such context in 497 rows, and that
one was an `ANSWER:` context, not an `INTERVENTION:`), while every J8 escalation and every B1
treated branch places one in its context.

**This is a specification conflict, not a coding bug.** The naming (`DROP_INTERVENTION_LEAK`,
`intervention_in_context`) shows the exclusion is deliberate: corrections are distilled into the
base policy so the executor acts correctly *unprompted*. That is coherent, and it is the likely
reason `sft_plan` performs as well as it does. It is also incompatible with the mechanism H2b
requires — a policy that benefits from live assistance. The training objective and the evaluation
protocol optimise different things.

## What it invalidates (write this plainly)

Every escalation-related measurement in this project was taken through this mismatch and measures an
untrained model's reaction to an off-distribution token, not the value of planner assistance:

- The J8 dev frontier's gated arms and the finding that no arm beats `sft_plan`
  (`campaign/RUNS.md` §10).
- B1's counterfactual Δ: mean +0.0048, 95% CI [−0.0125, +0.0223]; 17/200 points help, 19/200 harm;
  perfect-oracle ceiling +0.0335 GPR per episode, CI [+0.0153, +0.0530]. **The ceiling is
  conditional on an executor that cannot exploit interventions and is therefore a lower bound on the
  mechanism, not a ceiling on it.**
- The H3 gate AUROCs, already corrected once today for a separate defect.
- The D2 error-trigger test (`campaign/results/b1_error_trigger_20260920.json`): HELP precision
  0.174 against a 0.085 base rate at the one-step window, lift 2.05×, recall 0.471, bootstrap CI
  [0.068, 0.292] which includes the base rate; mean-Δ difference +0.0109, CI [−0.0383, +0.0603].
  Record this as **underpowered at 17 positives — compatible with chance, not shown to be chance.**

Do **not** write that these results are wrong. They are correct measurements of the system as built.
What changes is what they are evidence *about*.

## The remedy, recorded but not performed

`src/sidekick/training/matched_sft.py:806` already exposes the switch:
`strip = not args.no_strip_interventions`. Rebuilding the correction dataset with interventions
retained and training a variant adapter is the decisive experiment. Record two conditions on it:

1. It must also measure unprompted plan-following, because stripping plausibly guarded against a
   real failure — a model trained with interventions in context may learn to wait for them, which is
   what "leak" implies the authors feared.
2. The intervention-conditioned signal is thin: 267 correction episodes, 775 action targets, from 90
   train tasks × 3 seeds.

State that this has **not** been run and requires the user's approval because it is a training run.

## Where to put it

- `docs/FOLLOWUPS.md`: a new entry in the established style of that file, dated 2026-09-20, carrying
  the citations above and the remedy.
- `campaign/RUNS.md`: a new `## 11.` section recording the finding, what it invalidates, the B1
  numbers above, and the D2 result. Do not alter §10 or any earlier section.

## Return contract

Write `campaign/workers/STATUS_D3.md`. Final report, six lines or fewer: the two locations you wrote
and their line ranges, confirmation that no code and no frozen document was touched, and confirmation
that you did not describe the existing results as wrong. Cite `[OBSERVED <path>:<line>]`; every code
citation must be one of the ones given above, unchanged.
