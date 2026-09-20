# STATUS_D2 — error-trigger heuristic (done)

Read-only. Outputs: this file and `campaign/results/b1_error_trigger_20260920.json`.
Scratch scripts only under `/scratch/n12194778/sidekick/tmp_d2/` (not in the repo).

## How an environment error is represented

Inspected all 270 `events.jsonl` files under
`/scratch/n12194778/sidekick/results/hj4_correction_train_20260917/fixed_k/`
(10989 events, 4691 observations). [OBSERVED inspect job 25571656 / 25571710]

- Observation payload keys are `text`, `done`, `kind` only. No `error_type` field.
- `Event.error_type` is `None` except 36 `limit` events (system `max_steps`, `event_type=error` or `run_end`), not env failures.
- Literal `"Traceback (most recent call last)"` never appears.
- Env failures are observation `payload.text` starting with **`Execution failed. Traceback:`** (1032/4691 obs, all `kind=CODE`).
  Citation: `/scratch/n12194778/sidekick/results/hj4_correction_train_20260917/fixed_k/2/2a163ab_3/events.jsonl:5`
  quote: `Execution failed. Traceback:\n  File "<python-input>", line 2, in <module>\n    print(apis.api_docs.show_api_doc(...))\nException: Response status code is 422:`
- Of those 1032: 785 contain `Exception:`, 231 contain `Error:` (e.g. `TypeError:` / `KeyError:`), 16 are SyntaxError/StopIteration with neither. 0 hits of `Exception:`/`Error:` outside the envelope.

Windows: observation events with `step in {I-1}` and `{I-1,I-2,I-3}` where `I` is the intervention `step`. The observation *at* `I` is the post-intervention env result (intervention event precedes action/observation at the same step) and is not counted.

## Δ

200 points from 1600 `branch_runs.jsonl` rows; 0 excluded (every `(seed, task_id)` has `fixed_k/{seed}/{task_id}/events.jsonl`; every point has treated and untreated `branch_gpr`).
Δ = mean(treated) − mean(untreated). HELP 17, HARM 19, neutral 164, mean Δ = 0.004818. [OBSERVED campaign/results/b1_error_trigger_20260920.json:2-19]

## Primary marker `Execution failed. Traceback:`

Window 1 (46 flagged):
```
                      HELP            otherwise
recent error          8               38
no recent error       9               145
```
HELP P=0.174 R=0.471 lift=2.05; Wilson P 95% CI [0.091, 0.307]; bootstrap P [0.068, 0.292] (includes base 0.085).
HARM 5/41 vs 14/140; P=0.109 R=0.263 lift=1.14; Wilson [0.047, 0.230] (includes base 0.095).
meanΔ flagged−unflagged = +0.0109, bootstrap 95% CI [−0.0383, +0.0603] seed 0, 2000 resamples.

Window 3 (87 flagged):
```
                      HELP            otherwise
recent error          10              77
no recent error       7               106
```
HELP P=0.115 R=0.588 lift=1.35; Wilson [0.064, 0.199] includes 0.085.
HARM 8/79 vs 11/102; P=0.092 R=0.421 lift=0.97.
meanΔ diff = +0.0031, CI [−0.0327, +0.0382].

## Other definitions (all reported)

- `Exception:` w1: 7/27 vs 10/156; HELP P=0.206 Wilson [0.103, 0.368] (bootstrap P [0.077, 0.351] includes 0.085); meanΔ diff +0.0223 CI [−0.038, +0.085].
- `Error:` w1: 0/10 HELP, 2/8 HARM; HELP P=0; meanΔ diff −0.0509 CI [−0.104, −0.0076] (excludes 0) but n_flagged=10 and HARM P Wilson [0.057, 0.510] includes base 0.095 — not a usable harm detector.
- `Event.error_type is not None` in the window: 0 flagged. Not an env-error signal at decision points.

## Verdict

An error-triggered gate is **not worth building**. Apparent HELP lift (~2× at w1) does not survive uncertainty (bootstrap precision CI includes the 0.085 base rate; mean-Δ CIs include 0). Compatible with chance on n=200 / 17 positives.

No tests added (analysis-only unit; no package code changed).
