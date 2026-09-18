# W-4b — the verifier fit reads a row shape that does not exist

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## What happened

`scripts/setup/fit_feature_verifier.py` was written and tested against synthetic rows the
author constructed. J6 has now produced real `branches.jsonl` files, and the real row shape
is different. The script would have run to completion and produced plausible-looking numbers
that were wrong in three independent ways. Nothing would have raised.

This is the failure mode this project keeps hitting, so read all three before changing
anything.

Here are the **actual** keys of a real row, read off
`/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branches.jsonl`:

```
actual_gpr, actual_solved, ambiguous, branch_seeds, campaign, correction, delta,
delta_band_delta, delta_crn, delta_local, delta_mean, harmful, i, label_status,
n_later_reviews, needed, needed_strict, needless, seed, step, task_id,
treated_gpr, treated_gpr_local, untreated_gpr, untreated_gpr_local
```

### Defect 1 — there is no `split` key, so the dev set is silently empty

`run_fit` partitions with `str(r.get("split") or "train") == "train"`. No real row has
`split`, so **every** row becomes train and `dev_rows == []`. Temperature scaling and every
dev metric — AUROC, Brier, ECE — would then be computed on an empty set.

**Fix:** take the two splits as **separate explicit inputs**. Replace `--branches` with
`--train-branches` and `--dev-branches`, both required. Never infer the split from a field
that does not exist. If you keep a `split` key anywhere, it must be one *you* attach from
which file the row came from.

### Defect 2 — the ambiguous guard tests the wrong field and never fires

`prepare_dataset` does `status = row.get("label_status")` then `if status == "ambiguous"`.
But `label_status` only ever holds `complete` or `incomplete` — `ambiguous` is a **separate
boolean column**, which you can see in the key list above.

So the guard never fires, and every ambiguous point — about **70 %** of all points — is kept
and fitted as a negative, because its `needed` is `False`. The report would print
`ambiguous_excluded: 0`, which reads as "there were none" rather than "the check is broken".

**Fix:** exclude on the boolean `ambiguous` column. Keep reporting the count. Add an
assertion that `label_status` only ever takes the values you expect, and fail loudly on an
unexpected one rather than falling through.

### Defect 3 — the feature columns are not in the row

`build_xy` calls `_extractor_features(row)` on a `branches.jsonl` row. That row has **no**
`transcript`, `last_action`, `last_observation`, `n_asks` or `n_interventions`. Only `step`
exists. Every other feature would come out at its default, and the fit would be on
near-constant columns — while still reporting an AUROC.

**Fix:** the features must be reconstructed from the **campaign events**, joined to the label
rows. A label row identifies its point by `campaign`, `seed`, `task_id`, `i` and `step`. The
matching episode's `events.jsonl` lives under the campaign root:

- dev labels  → `/scratch/n12194778/sidekick/results/hj4b_fixed_k_dev_20260917`
- train labels → `/scratch/n12194778/sidekick/results/hj4_correction_train_20260917`

`scripts/setup/branch_counterfactual.py` **already reconstructs episode state at an
intervention point** in order to build branch prefixes — `_history_from_events` and the
surrounding enumeration code. Reuse it rather than writing a second reconstruction that can
drift from it. Read it before you design anything.

The feature vector must be the `trajectory_state` as the loop would have built it at that
point: `step`, `transcript`, `last_action`, `last_observation`, `n_asks`, `n_interventions`
(`src/sidekick/systems/loop.py:492-500`). The frozen 13-column spec `feature_lr_v1` in
`src/sidekick/agents/verifier.py` stays exactly as it is — you are fixing how the extractor
is **fed**, not what it computes.

Add `--train-campaign` and `--dev-campaign` arguments for the two roots. If a label row
cannot be joined to an episode, **drop it and count the drops in the report**. Never
substitute a default feature vector for a failed join; a row you could not build features for
is not a row with zero features.

## The test that would have caught all three

Add a fixture built from the **real artifact**, not invented:

- copy a handful of genuine rows out of the dev `branches.jsonl` above into
  `tests/fixtures/` (redact nothing; they are numbers and ids);
- assert the fit path rejects or correctly handles that exact shape;
- assert explicitly that `dev_rows` is **non-empty** after partitioning — the bug was that it
  silently was not;
- assert the ambiguous count reported is **> 0** on a fixture that contains ambiguous rows,
  so a guard that never fires fails the test rather than reporting zero;
- assert that a row whose episode cannot be joined is counted as a drop, not fitted.

Keep W-4's existing synthetic tests — the separable-data AUROC 1.0 and pure-noise AUROC ≈ 0.5
tests are good and must stay green. They prove the metric computes; they just never proved
the data path.

## Do not run the real fit yet

Train's `branches.jsonl` is not final — the ×4 replicate job is still running and the file in
the live tree is currently empty by design. Build and test the code now; the fit runs when
that job lands. **Do not** read or write anything under
`/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/` except to read
`branch_runs.jsonl`.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Everything that computes goes in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- **Do not submit any GPU job.** Two J6 jobs are live.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- Run the suite as
  `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`.
  Current state to match or beat: **329 passed, 1 skipped, 0 failures.**
- Do not edit `src/sidekick/systems/loop.py` or `src/sidekick/agents/executor.py`.
- Update `campaign/workers/STATUS_W_4.md` with a W-4b section and resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- One line each with `path:line`: where the split now comes from, where ambiguous is
  excluded, and where features are joined to episodes.
- The count of label rows that failed to join, for both splits.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
