# Brief E1 — make the intervention-retaining dataset path work end to end

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
Branch: `worktree-plan-2026-09-15`. Work only in this worktree.

## Why this unit exists

The runtime appends `INTERVENTION: {correction}` as a user turn at every planner intervention
[`src/sidekick/systems/loop.py:748`, `:775`]. The SFT builder removes that turn at three layers, so
the trained adapter has never seen one. We want to train a variant adapter that DOES see them, as a
one-variable ablation against `sft_b_plus`.

The CLI flag for this already exists — `--no-strip-interventions`
[`src/sidekick/training/matched_sft.py:802`, wired to `strip` at `:806`] — **but it cannot currently
produce a dataset.** It suppresses the per-episode drop at `:445-446`, and then
`_combine_teacher_and_correction` raises **unconditionally**:

```
if _sft._contains_intervention_mark(row.get("messages") or []):
    raise RuntimeError(
        "combined dataset contains an INTERVENTION: turn; refusing to write"
    )
```

(at approximately `src/sidekick/training/matched_sft.py:597-600` — verify the exact lines yourself).

Note the ASK guard immediately below it IS conditional, via `allow_ask_targets = extra_summary is not
None`. The intervention guard is the odd one out.

## Goal

`--no-strip-interventions` writes a valid dataset whose correction episodes retain their
`INTERVENTION:` user turns. The default (stripping) path stays **behaviourally identical**.

## Scope

In scope:
- `src/sidekick/training/matched_sft.py`
- the matching unit test file (find it; likely `tests/unit/test_matched_sft.py`)

Out of scope — do not touch:
- `src/sidekick/training/sft_data.py` semantics
- `src/sidekick/systems/loop.py`
- anything under `configs/`
- `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md` (FROZEN — read only, never edit)
- anything under `/scratch/n12194778/sidekick/results/`

## Design (follow this; do not invent an alternative)

1. Add a keyword-only parameter `allow_interventions: bool = False` to
   `_combine_teacher_and_correction`.
2. Make the `INTERVENTION:` raise conditional on `not allow_interventions`. Leave the ASK guard
   exactly as it is.
3. Thread it through from every caller that already has `strip_interventions` in hand, passing
   `allow_interventions=not strip_interventions`. That includes the `build_sft_b_plus` path and the
   `build_ask_dataset` (sft_c) path.
4. Do **not** rename or remove `--no-strip-interventions`. Do not add new CLI flags.
5. When interventions are retained, record it in the emitted summary/manifest dict under a new key
   `intervention_mode` with value `"retain"` or `"strip"`, so the dataset is self-describing. If the
   builder writes a summary JSON, put it there too.

## Tests (required)

Write these as unit tests using small **synthetic** record lists passed directly to
`_combine_teacher_and_correction`. Do NOT read the real campaign tree, do NOT build a real dataset,
do NOT need GPU or network.

1. `strip` default unchanged: a record containing an `INTERVENTION:` turn still raises
   `RuntimeError` when `allow_interventions` is not passed.
2. `retain`: the same record does NOT raise when `allow_interventions=True`, and the written rows
   still contain the `INTERVENTION:` text.
3. The ASK guard is unaffected by `allow_interventions`: an ASK_PLANNER correction target still
   raises when `extra_summary is None`, both with and without `allow_interventions=True`.
4. The heldout-task leakage assertion (`assert_no_leakage`) still runs in retain mode.
5. `intervention_mode` is reported correctly in both modes.

## Constraints

- **Do not run training, evaluation, or any GPU job. Do not `qsub`. Do not run any command expected
  to take more than ~2 minutes.**
- `aquarius01` is a LOGIN NODE: no `python`/`pip`/`tar`/`rsync`/`ffmpeg` directly on it. Run the test
  suite through PBS: `hpc bash -c '<cmd>'`. Pin BLAS to 1 thread. Put `timeout` on everything.
- The full suite must end at **>= 442 passed, 1 skipped, 0 failed**. It needs
  `--import-mode=importlib`.
- **Do not commit.** Leave the working tree dirty; Claude reviews the diff and commits.
- Do not touch `.git/` or `.claude/worktrees/`.

## Return contract

Write `campaign/workers/STATUS_E1.md` containing:
- what changed, file by file, with line numbers
- the exact test command you ran and its final summary line, pasted verbatim
- every factual claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`
- anything you could not do, stated plainly rather than worked around

Keep the STATUS file under 400 words.
