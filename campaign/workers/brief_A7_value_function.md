# A7 (U-VF) — a value-function escalator built from episodes we already have

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files are **new**: `scripts/setup/fit_value_function.py`, its tests under
`tests/unit/`, and a report. 🔺 **Do not touch `src/sidekick/runner.py`, `src/sidekick/agents/verifier.py`,
`configs/` or `scripts/pbs/`** — other units own those this cycle. Wiring this into the runner is a
LATER unit; your job ends at a fitted artifact plus an honest evaluation of it.

**Create the files within your first three actions, then iterate with tests.**

## Why this exists

The campaign's escalation signal has so far been estimated by counterfactual branch rollouts, at
roughly four hosted planner calls per branch — the most expensive estimator available, and the one
that exhausted the quota. A value function needs **no counterfactual and no planner calls at all**:
every step of every episode already run is a labelled example, because the episode's outcome is
known.

Target: **`V(state) = P(the episode ends successfully | state)`**. An escalation policy then calls
the expert when `V` is low. Sweeping that threshold gives a frontier, exactly as the verifier
threshold does.

## Data

Root: `/scratch/n12194778/sidekick/results/` — **read-only, write nothing there.**

Episodes nest `<campaign>/<system>/<seed>/<task_id>/` with `events.jsonl`, `manifest.json`,
`result.json`.

**Fit on this pool** (class-balanced, ≈1,110 episodes / ≈19,900 action steps, ≈50 % positive):
`hj1b_planner_20260915`, `hj2b_planner_train_20260916`, `hj3_sft_b_exec_20260917`,
`hj3_sft_plan_20260917`, `hj4_correction_train_20260917`, `hj4b_fixed_k_dev_20260917`.

**Exclude from fitting but report separately**: `hj1a_exec3b_*`, `hj1a_exec8b_*`,
`hj1c_fixed_k_*`, `hj1c_prompt_only_*` — these four have **0 successes across 345 episodes**
(~13,300 all-negative steps) and carry no within-campaign signal. Report their count and say
plainly that they were excluded and why. **Do not drop them silently.**

Exclude `hj6_branches_*` entirely — those are counterfactual branches, not episodes.

## Three traps, all measured. Handle each explicitly.

1. 🔺 **`hj1a_exec8b_20260915` has appended event logs** — 111 of its 114 `events.jsonl` contain
   **two** `run_start` events and 3 contain three; an aborted attempt is concatenated ahead of the
   real run, and `result.json` reflects only the last. Your loader must **split on `run_start` and
   keep the final segment**. This exact pattern is already solved in
   `CachedPacketPlanner._load_plan_event`, which reads forwards and uses only events after the LAST
   `run_start` [OBSERVED src/sidekick/agents/planner.py:686-700] — follow it. Apply the rule to
   **every** campaign, not just that one, and report how many files had more than one `run_start`.

2. 🔺 **`evaluate` is terminal-only.** There is no per-step score: 270 `evaluate` events for 270
   episodes. Every mid-episode state is labelled by back-propagating the episode outcome. Use
   `result.json`, not the campaign `runs.jsonl` — `goal_pass_rate` is **absent** from the older
   campaigns' `runs.jsonl` but present per-episode. Report which outcome field you used
   (`success` boolean and/or `goal_pass_rate`) and why.

3. **Train/dev separation must be by task, not by step.** All steps of one episode share a label,
   and tasks recur across seeds. **Split by `task_id`** so no task appears in both train and dev;
   a step-level split would leak and inflate AUROC. State the split rule and the resulting counts.

## Features

Reuse `_extractor_features` [OBSERVED src/sidekick/agents/verifier.py:137-181] so that fitting and
serving share one extractor — the same discipline `scripts/setup/fit_feature_verifier.py:33-38`
already follows. Import it; do not reimplement it.

To call it you must reconstruct a `trajectory_state` dict at each step, with exactly the 7 keys the
loop produces: `step`, `transcript`, `last_action`, `last_observation`, `n_asks`,
`n_interventions`, `p_ask` [OBSERVED src/sidekick/systems/loop.py:515-524]. Rebuild these by
replaying `events.jsonl` forward. `p_ask` will be `None` for historical episodes — that is correct
and must not be coerced to 0.0.

If you find the extractor needs a field the event log cannot reconstruct, **report it rather than
approximating silently.**

## Fitting and evaluation

Logistic regression, same shape as `scripts/setup/fit_feature_verifier.py`. Read that script first
and follow its conventions.

🔺 **It contains a hard-won lesson you must not undo.** Its `fit_temperature` was rewritten
(commit `957ec7a`) after the original silently *de*calibrated: it now uses golden-section search
over log T and returns 1.0 whenever the optimum fails to strictly beat T = 1.0, and it writes
`dev_nll_before` / `dev_nll_after` into the artifact. **Reuse that function. Apply the same
invariants to your fit:**

- **improvement**: calibration must never increase dev NLL; assert it.
- **invariance**: temperature scaling is monotone, so AUROC must be **bit-identical** before and
  after; assert it.
- **before/after in the artifact**: write both NLLs.
- **a known-answer test**: at least one case where the right answer is known by construction.

Report: dev AUROC with a **bootstrap CI** (10,000 resamples), Brier, ECE, the positive rate, and
the counts at every filtering stage (read → kept → dropped, with reasons).

🔺 **Report AUROC against the attenuation ceiling, not against 0.50 alone.** These labels are
episode outcomes back-propagated to steps, so an early step is only weakly determined by the
outcome; the achievable AUROC is bounded well below 1. State the bound you assume and how you got
it. An AUROC of 0.70 may be near-ceiling or near-chance and the number alone does not say which.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- Reading ~1,100 event logs is the heavy part: read once, cache in memory.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job** — this is CPU work and
  a training job is already queued.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **349 passed, 1 skipped** — never fewer.
- Artifact → `artifacts/verifiers/value_fn_20260919/`; report →
  `campaign/workers/A7_VALUE_FUNCTION.md`; raw output → `campaign/workers/scratch_A7/`.
- Write `campaign/workers/STATUS_A_7.md` with resume state per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- Counts at every stage: episodes read, multi-`run_start` files found, steps kept, dropped + why.
- The task-level split rule and its counts.
- Dev AUROC + bootstrap CI, Brier, ECE, positive rate, and the assumed attenuation ceiling.
- Confirmation of the four fit invariants above.
- The excluded zero-success campaigns, counted and named.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
