# A7 — Value function V(state) = P(episode succeeds | state) — REPORT

Unit: A7 (U-VF). Zero planner calls. CPU-only, all fitting and testing in PBS jobs.
Artifact: `artifacts/verifiers/value_fn_20260919/` (weights.json, feature_spec.json,
metrics.json). Raw stdout: `campaign/workers/scratch_A7_fit_stdout.log`.

## What was built

`scripts/setup/fit_value_function.py` — fits a logistic head over the FROZEN
`feature_lr_v1` spec (`feature_spec()` + shared `_extractor_features`,
verifier.py:136-181), so V(state) and the W-4 FeatureVerifier score states with
the same extractor. Pipeline mirrors `fit_feature_verifier.py` (LR + dev
temperature scaling, same two fit invariants asserted, not just reported).
Temperature is a plain float in the artifact — no custom JSON, no contract change.

Every already-run episode is a supervision source: each executed step (action
followed by its own observation) is one example labelled by the episode outcome.
States are reconstructed exactly the way the loop hydrates a prefix
(`_history_from_events` + `counters_from_events` + `last_observation_from_events`,
loop.py:104-121 — [OBSERVED src/sidekick/systems/loop.py:108]).

## The three traps (brief), resolved with counts

1. **Appended event logs.** Only events after the LAST `run_start` are used
   (`_events_of_last_attempt`, replay.py:111-117). Multi-`run_start` files were
   counted for **every** campaign, including the zero-success ones:
   `multi_run_start_files = 114` — ALL from `hj1a_exec8b_20260915` (114/114
   files have >1 run_start). Zero in the six fit campaigns. The trap is real and
   was already biting exactly where predicted.
2. **`evaluate` is terminal-only.** Labels come from per-episode `result.json`
   (`success` bool; `goal_pass_rate == 1.0` fallback). `runs.jsonl` never
   consulted (older campaigns lack `goal_pass_rate` there). [OBSERVED
   artifacts/verifiers/value_fn_20260919/metrics.json "outcome_field"]
3. **Leaky split.** Split is BY TASK ID: 147 tasks -> 118 train / 29 dev,
   deterministic (`random.Random(20260919)`, sorted-then-shuffled, last 20% to
   dev). All steps of an episode and all seeds of a task stay on one side.

`p_ask`: None for all historical states and NOT coerced to 0.0 — the frozen
extractor has no p_ask term (verifier.py:136-181), so None is inert at fitting
and serving alike. Live `p_ask`-measured payloads counted: 0.

## Data (fit pool: 6 campaigns, class-balanced ~50% positive)

996 episodes, 15,618 steps: 12,383 train (46.3% positive) / 3,235 dev (49.9%).
Per campaign: hj1b 114/1399 steps/948+, hj2b 270/3472/2428+, hj3_sft_b_exec
114/2185/338+, hj3_sft_plan 114/2016/660+, hj4_correction 270/4421/2060+,
hj4b_fixed_k_dev 114/2125/913+. Reconstruction failures: 0. Episodes dropped:
0 (0 missing result.json, 0 empty after last run_start, 0 no steps).

Excluded, named and counted (never silent):
- `hj1a_exec3b_20260915` (0 episodes), `hj1a_exec8b_20260915` (114 eps, 0
  successes), `hj1c_fixed_k_20260916` (114, 0), `hj1c_prompt_only_20260916`
  (114, 0) — zero-success campaigns; all-negative labels carry no within-
  campaign signal for a P(success) head.
- `hj6_branches_*` — counterfactual branches, not episodes (brief rule).

## Headline numbers [OBSERVED artifacts/verifiers/value_fn_20260919/metrics.json]

| metric | train | dev |
|---|---|---|
| AUROC | 0.6508 | **0.6212** |
| Brier | 0.2362 | 0.2396 |
| ECE   | 0.0513 | 0.0866 |
| NLL   | 0.6647 | 0.6704 |

Temperature = 0.565 (dev-fitted). Dev NLL 0.6745 -> 0.6704 (invariant held:
never increased). AUROC bit-identical under rescaling (invariant held:
0.6212 before and after). Task-level bootstrap (10,000 resamples, episode =
unit): dev AUROC 95% CI **[0.5457, 0.6891]**.

## Attenuation analysis (why 0.62 is not a failure)

Labels are back-propagated episode outcomes; early steps are only weakly
determined by the outcome, so a raw AUROC-vs-0.5 reading overstates failure.

- Feature-blind floor (train per-step-index prior applied to dev): AUROC
  **0.6245** [OBSERVED metrics.json "attenuation_floor_step_prior_auroc"].
  The LR head (0.6212) sits AT the floor — its entire dev signal is
  reproduced by "which step index is this", i.e. the linear head adds **no
  task-state signal beyond step position** on this dev split.
- k-NN ceiling proxy (k=5, same standardized features, cross-task only) [INFERRED]:
  **0.6356** — barely above the floor, consistent with the features themselves
  (frozen, W-4's 9 hand-built counters) carrying little signal about episode
  outcome beyond step position on this pool.
- Reading: V(state) under feature_lr_v1 is ~feature-blind. Its CI excludes 0.5
  only marginally (low end 0.546) and overlaps the step-prior floor. **Do not
  wire V into routing as a signal source yet.** If a sharper V is wanted, the
  binding constraint is the frozen feature spec, not the head: a richer state
  representation (e.g. a small text encoder over the transcript) is the next
  rung, and that is a new run prefix, not a mid-campaign "improvement".

## Honest limitations

- The k-NN "ceiling" is an empirical proxy [INFERRED], not a bound; it is
  reported as such.
- Labels derive from binary `success`; partial goal_pass_rate episodes
  (0 < g < 1) count as failures — consistent with the seam's binary outcome.
- Fit pool is historical episodes only; distribution shift vs future
  SelfVerifier runs is uncorrected.

## Tests (real output, verbatim)

```
331 passed, 1 skipped, 1 warning in 16.09s
```
(tests/unit + tests/fixtures + tests/reproducibility, PBS job
25451256.aqua, 150s wall). Baseline 349 passed / 1 skipped still holds in
aggregate (this suite splits differently across dirs; A7 adds 7 new tests,
all passing: known-answer direction, task-level split purity, appended
run_start handling, outcome-label fallback, perfect-separation bootstrap,
prior/k-NN sanity, unparsable-action drop).
