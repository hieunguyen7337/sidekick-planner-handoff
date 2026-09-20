# Brief E4 — build (do not evaluate) an action-reviewing planner with label-free triggers

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Create the files within your first three actions, then iterate with tests.** Do not spend the turn
planning.

## Why this unit exists

Today the planner intervenes by seeing the trajectory and emitting a correction, which reaches the
executor as `INTERVENTION: {correction}` [`src/sidekick/systems/loop.py:748`, `:775`]. Measured on
dev, this helps at exactly chance and harms above chance. One structural reason: at step *k* the
planner holds no information the executor lacks — same model family, same task, same trajectory.

This unit builds the variant where it DOES: the planner sees the **proposed action before it is
executed** and can veto or replace it. Plus two **label-free** triggers, because the learned gates
are all at or below chance and the label pool is only 25 positives.

**This unit is BUILD AND UNIT TESTS ONLY. No GPU. No planner API calls. No evaluation. No `qsub` of
any eval job.** The decision about whether to evaluate this comes later and is not yours.

## What to build

### 1. A rule-based trigger as a new verifier kind

`make_verifier` in `src/sidekick/runner.py:194-211` dispatches `verifier.kind`. Currently registered:
`self_p_ask`/`self` → `SelfVerifier`, `feature_lr` → `FeatureVerifier.load(path)`, `verifier.scores`
→ `ScriptedVerifier`, anything else → `ConstantVerifier`.

Add kind `rule_trigger`, configured like:

```yaml
verifier:
  kind: rule_trigger
  rules: [on_exception, on_irreversible]
  irreversible_patterns: ["\\.create_", "\\.delete_", "\\.send_", "\\.update_"]
```

Semantics — returns 1.0 when any enabled rule matches, else 0.0:
- `on_exception`: the most recent observation contains the execution-failure marker. Use the marker
  already verified in this project: `Execution failed. Traceback:`. Do **not** use
  `Traceback (most recent call last)` — it occurs zero times in the corpus.
- `on_irreversible`: the **proposed action** matches any `irreversible_patterns` regex.

Rules must be independently toggleable, and the default when `rules` is absent is `[on_exception]`.

### 2. An action-reviewing system

New module under `src/sidekick/systems/`, following the structure of the existing systems there.
Behaviour: at each step the executor proposes an action; if the gate fires, the planner is shown
(task, plan, trajectory-so-far, **proposed action**) and returns either an approval or a replacement.
On approval the proposed action executes unchanged. On replacement the replacement executes.

Study how the existing systems build their planner requests and reuse that seam rather than inventing
a new transport. **Record the planner call in the ledger exactly as existing systems do**, so call
counts stay comparable across arms — a review is a planner call and must be counted as one.

Emit the review verdict into the event stream so a later analysis can separate approvals from
replacements.

### 3. Configs

New prefix `hj11_action_review_*.yaml` — do NOT reuse or edit any `hj8_*` config; those are frozen
inputs to a completed campaign. Mirror `configs/hj8_sft_plan_bplus.yaml` for the executor block
(`executor.lora_name`), and add the verifier block above. Make at least two: one `on_exception` only,
one with both rules.

### 4. Tests

Unit tests with a **mock planner** — no network, no GPU, no adapter. Cover:
- `rule_trigger` fires on the exception marker and not on a clean observation
- `on_irreversible` fires on a matching proposed action and not otherwise
- rules toggle independently; default is `[on_exception]`
- an unknown `verifier.kind` still falls through to `ConstantVerifier` (no regression)
- the system executes the proposal on approval and the replacement on replacement
- a review increments the planner call count by exactly one

## Constraints

- **No GPU, no `qsub` of eval jobs, no planner API calls, no multi-minute commands.**
- `aquarius01` is a LOGIN NODE: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Run the test
  suite via `hpc bash -c '<cmd>'`. `timeout` on everything. BLAS pinned to 1 thread.
- Suite must end at **>= 442 passed, 1 skipped, 0 failed** plus your new tests. Needs
  `--import-mode=importlib`.
- Do not edit `docs/prereg_v1.md` or `docs/prereg_b1_pilot.md` — FROZEN.
- Do not touch anything under `/scratch/n12194778/sidekick/results/`, `.git/`, or
  `.claude/worktrees/`.
- **Do not commit.** Claude reviews the diff and commits.

## Return contract

`campaign/workers/STATUS_E4.md`, under 500 words: files added/changed with line numbers, the exact
test command and its verbatim final summary line, every claim tagged `[OBSERVED <path>:<line>]` or
`[INFERRED]`, and anything you could not do stated plainly.
