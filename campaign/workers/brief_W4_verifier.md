# W-4 — FeatureVerifier: a cheap, interpretable escalation scorer

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Goal

A logistic regression over features of the loop's `trajectory_state` that scores "is an
expert review needed at this state". It is the router for the `router_seq` arm and it
produces H3's calibration numbers. **Write the code and its tests now**; the fit runs
later, when J6's labels land.

Build three things:

1. `FeatureVerifier` in `src/sidekick/agents/verifier.py`, satisfying the existing
   `Verifier` protocol.
2. A feature extractor with a **frozen, ordered, named** feature spec.
3. A fit/calibrate script, `scripts/setup/fit_feature_verifier.py`, CPU-only.

## What exists — build on it, do not restructure it

- `src/sidekick/agents/verifier.py` holds `Verifier` (a Protocol with
  `score(self, trajectory_state: Any) -> float`), `ConstantVerifier`, `ScriptedVerifier`
  and `ThresholdRouter` (escalates on strict `score > threshold`). Add to this file.
- `trajectory_state` is built at `src/sidekick/systems/loop.py:492-500` and returns
  **exactly** these keys:

  ```python
  {"step": step,
   "transcript": "\n".join(transcript),
   "last_action": None if last_action is None else last_action.model_dump(),
   "last_observation": None if last_obs is None else last_obs.model_dump(),
   "n_asks": n_asks,
   "n_interventions": n_interventions}
  ```

  🔺 Your extractor may use **only** these keys. Anything else has to be derived from the
  transcript string, which is the concatenation of `INSTRUCTION:`, `PLAN:`, `OBS:`,
  `INTERVENTION:`, `ANSWER:` and `ASK_IGNORED` lines (`loop.py:519-524`). Do not add
  fields to `trajectory_state`; W-5 is editing that function concurrently and a second
  editor there will collide.

## The features (this list is the spec; freeze it)

`step`, `n_interventions`, `n_asks`, last observation is an error or traceback,
consecutive-error run length, last action repeats an action seen earlier in the episode,
count of distinct APIs called so far, an access token has appeared in the transcript,
transcript length in characters, and the kind of the last action.

Write the spec to JSON alongside the weights: ordered feature names, the transform for
each, and the version. A model whose feature order is implied by code rather than
recorded is a model that silently mis-scores when someone reorders the extractor.

## The fit script

`scripts/setup/fit_feature_verifier.py`, CPU-only, run in a PBS job, not on the login node.

- Input: J6's `branches.jsonl` (one row per intervention point). The label column is
  `needed`. **Rows whose `label_status` is `incomplete` must be dropped, never imputed.**
  Rows labelled `ambiguous` are excluded from fitting and reported separately — they are
  about 69% of points, so a script that quietly treats them as negatives will look like it
  has a large, well-balanced dataset and will be fitting mostly noise.
- Fit on the **train** split, temperature-scale on **dev**. Never fit on dev.
- Output: weights + feature spec as JSON under `artifacts/verifiers/feature_lr_<date>/`,
  and a metrics JSON with dev **AUROC, Brier and ECE**, plus the positive rate and n at
  each stage.
- Runner wiring so a config can say `verifier: {kind: feature_lr, path: <abs>, threshold: <τ>}`
  for the `sidekick` and `router_seq` systems, in whatever style the runner already
  resolves systems and their kwargs.

## Two things to write down rather than discover later

- **The labels exist only at timer-tick states** — steps 5, 10, 15, … — because that is
  where the J4 reviewer fired. The router and the sidekick's gate will score **every**
  step. That is a train/serve distribution shift; put it in the metrics JSON as a recorded
  threat to validity, and report dev AUROC restricted to tick states separately from
  AUROC over all scored states if you can compute both.
- **The labels are noisy.** Measured 2026-09-17 on partial J6 data: split-half reliability
  of the underlying effect is 0.17–0.20 per replicate, so the two-replicate mean the
  labels are cut from has reliability ≈ 0.29. An AUROC near 0.5 is therefore a plausible
  and reportable outcome, not necessarily a bug in your code. Do not tune against it.

## Constraints — read these, you are not covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Compute goes in a PBS job via `hpc`, `hpc-py` or `qsub`, with `timeout`
  on everything and BLAS pinned to one thread.
- **Do not submit any GPU job and do not run the fit against live J6 output.** Three J6
  jobs are running or queued and `branches.jsonl` is written only at the end of each; it
  is empty or stale until then. Test against synthetic label rows you construct yourself.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- Do not edit `src/sidekick/systems/loop.py`. W-5 owns that file this cycle.
- Run the suite as `pytest tests -q --import-mode=importlib` — plain `pytest` dies on a
  duplicate test basename. Baseline: **286 passed, 1 skipped, 0 failures.**
- Write `campaign/workers/STATUS_W_4.md` and keep it current with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Tests (CPU-only, synthetic)

- each feature fires on a hand-built `trajectory_state` and is zero when it should be;
- a state missing `last_action` or `last_observation` extracts without raising;
- feature order in the JSON spec matches the vector the extractor emits, asserted
  explicitly rather than by construction;
- `incomplete` rows are dropped and `ambiguous` rows are excluded from the fit, with the
  counts reported;
- a fit on separable synthetic data recovers AUROC 1.0, and on pure-noise labels lands
  near 0.5 — this is the test that proves the metric is being computed, not asserted;
- `ThresholdRouter` over a `FeatureVerifier` escalates on strict greater-than.

## Return contract

- The diff, and the test output as emitted.
- The feature spec JSON, inline, since it is the frozen contract.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
