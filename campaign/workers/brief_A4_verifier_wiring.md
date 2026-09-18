# A4 (U-V1) — fix the `feature_lr` verifier wiring. BLOCKING.

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Other units own `configs/`, `scripts/pbs/`, `scripts/setup/branch_counterfactual.py`
and the training code — **do not touch them**. Your files are `src/sidekick/runner.py` and
`tests/unit/`.

## The defect

`make_verifier` returns a `ThresholdRouter` when `verifier.kind == "feature_lr"`:

```python
verifier = FeatureVerifier.load(path)
threshold = vcfg.get("threshold", cfg.get("verifier_threshold", 0.5))
return ThresholdRouter(verifier, threshold=float(threshold))
```
[OBSERVED src/sidekick/runner.py:187-194]

But `ThresholdRouter` exposes only `should_escalate` — it has **no `score` method**
[OBSERVED src/sidekick/agents/verifier.py:43-51]. Both consumers call `.score()`:

- the `sidekick` ASK gate: `v.score(trajectory_state(step)) > policy.verifier_threshold`
  [OBSERVED src/sidekick/systems/loop.py:786]
- the `router_seq` path wraps the returned object in a **second** `ThresholdRouter`, whose
  `should_escalate` then calls `self.verifier.score(...)`
  [OBSERVED src/sidekick/systems/loop.py:248-249] [OBSERVED src/sidekick/agents/verifier.py:51]

So `verifier: {kind: feature_lr, ...}` raises `AttributeError` on **both** arms. That is 6 of the
12 planned J8 arms. It has never been caught because no test constructs through `make_verifier`
with `feature_lr` — `tests/unit/test_feature_verifier.py:270` builds the router directly and
bypasses the seam.

## The fix

`make_verifier` must return an object satisfying the `Verifier` protocol — i.e. something with
`.score(trajectory_state) -> float`. Return the **bare `FeatureVerifier`** and let the loop do its
own wrapping. The threshold already reaches the policy independently, via
`system_kwargs["verifier_threshold"]`, which is read from `cfg["verifier"]["threshold"]`
[OBSERVED src/sidekick/runner.py:217-222] — so dropping the router here loses nothing.

Check the other branches of `make_verifier` for the same class of problem before you finish:
`ScriptedVerifier`, `SelfVerifier` and `ConstantVerifier` all need `.score`. Confirm each does and
say so in your report.

🔺 **Do not "fix" this by adding a `score` method to `ThresholdRouter`.** `ThresholdRouter` is a
*decision* object, not a scorer; giving it a `score` would let a router be nested in a router
silently, which is the very confusion that produced this defect. If you believe otherwise, say so
in the report and do it the way specified anyway.

## Tests — this is the important half of the unit

The defect survived because every existing test bypassed `make_verifier`. Add tests that go
**through `make_verifier`**:

1. For each kind — `feature_lr`, `self_p_ask`, `scores`, and the default — the returned object has
   a callable `.score` and returns a float on a realistic `trajectory_state` dict.
   A realistic state has exactly these 7 keys: `step`, `transcript`, `last_action`,
   `last_observation`, `n_asks`, `n_interventions`, `p_ask`
   [OBSERVED src/sidekick/systems/loop.py:515-524].
2. An end-to-end test of the **`router_seq`** path: build a verifier via `make_verifier` with
   `kind: feature_lr`, wrap it the way the loop does, and assert `should_escalate` returns a bool
   without raising.
3. An end-to-end test of the **`sidekick`** ASK-gate path: same construction, assert the
   comparison at `loop.py:786` executes and returns a bool.
4. Assert the threshold from `verifier.threshold` still reaches `system_kwargs["verifier_threshold"]`
   unchanged after your edit.

For `feature_lr` you need a verifier artifact. A real one exists at
`artifacts/verifiers/feature_lr_20260918/` (`weights.json`, `feature_spec.json`, `metrics.json`).
Prefer writing a tiny synthetic one into `tmp_path` via `FeatureVerifier.save`
[OBSERVED src/sidekick/agents/verifier.py:237-253] so the test does not depend on a campaign
artifact.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`.** The hosted quota is exhausted until
  2026-09-19 ~21:13. **Do not submit any GPU job** — a training job is already running.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.**
- Suite: `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`. Baseline is
  **349 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_4.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff and the test output as emitted.
- `path:line` of the corrected return, and of each new test.
- Confirmation that every branch of `make_verifier` returns something with `.score`.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
