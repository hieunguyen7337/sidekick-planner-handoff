# Brief X36 — fix the segmented-fit tie-break so a straight line cannot invent a threshold

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**This unit is FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, or any command that waits on the
PBS queue — I run every test myself and report the result back to you if another pass is needed.**
Editing files and reading files is the whole unit. It should take one pass.

## The defect

`scripts/analysis/hj12_shape.py` implements the registered segmented ("threshold") fit for
`docs/prereg_hj13_shape_20260923.md` §3. It profiles residual sum of squares over breakpoint
candidates and is documented — in its own docstring at `:160` — as *"Ties take the smallest tau."*

It does not. At `:189` it does:

```python
ranked.sort(key=lambda t: (t[0], t[1]))
```

That tie-breaks only on **exact** float equality of RSS. Fed a perfectly straight line, a segmented
model fits exactly at *every* candidate breakpoint, so all RSS values are mathematically identical —
but numerically they land around `1e-33` and differ in the last bits. The sort therefore picks
whichever candidate happened to accumulate the smallest rounding error.

Measured just now [OBSERVED PBS job 25693192, `pytest tests/unit/test_hj12_shape.py`]:

```
test_straight_line_s3_does_not_exclude_m_le_4  assert 8 == 4
test_tie_break_takes_smallest_tau_on_a_line    assert 8 == 4
2 failed, 4 passed in 0.68s
```

**The two failing tests are correct and must not be weakened, relaxed, skipped or deleted.** They
encode the registered rule. The prereg amendment states the purpose in as many words: the tie-break
"is the rule that makes a straight line fail S3 (interval includes 4) rather than invent a
threshold." A fitter that returns τ=8 on a straight line manufactures a threshold from data that has
none — which is exactly the reviewer objection this whole analysis exists to answer. Fix the code.

## The fix

In `fit_segmented` (`scripts/analysis/hj12_shape.py:153-199`), select the minimiser with a
**tolerance scaled to the data**, then take the smallest τ among everything inside that tolerance.

A relative tolerance on RSS alone is useless here, because the tied RSS is ~`1e-33` and a relative
band around it is still ~`1e-33`. Scale the tolerance to the spread of the response instead. Concretely:

- compute the total sum of squares of `qs` about its mean (`tss`);
- set `tol = 1e-12 * max(tss, 1.0)`;
- take `best = min(rss)`, keep every candidate with `rss <= best + tol`, and among those return the
  **smallest τ**.

Keep the existing behaviour in every other respect: same return dict keys, same `None`/`note` paths
for the degenerate cases at `:161-170` and `:179-188`, same `taus` argument and `x_of_m` remapping.
`1e-12` is a deliberate choice — on a genuine threshold the RSS gap between candidates is many orders
of magnitude larger than this, so the tolerance cannot fire spuriously; add a one-line comment saying
so, in the register of the surrounding comments.

Apply the same tolerance rule anywhere else in the file that selects a τ by minimising RSS — check
the bootstrap path (`bootstrap_segmented`) and the percentile-remapped path, since a per-resample
refit that keeps the naive `sort` would reintroduce the same bias inside every bootstrap draw and
silently shift the τ interval. **Search the file for `sort(` and for `min(` over RSS and report every
site you found and what you did about each.** If a shared helper is the clean way to do this, write
one and use it everywhere.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `tar`, `rsync`, `ffmpeg` there, and **no
  `pytest` and no `hpc`/`qsub`** in this unit at all.
- Do not edit the tests. Do not edit `docs/prereg_hj13_shape_20260923.md` — it is registered text.
- Do not touch `scripts/analysis/j8_frontier.py`, anything under `src/sidekick/training/`, or any
  `configs/*.yaml`.
- Read-only on `/scratch/n12194778/sidekick/results/`. Never read or list `test_normal` /
  `test_challenge`.
- **Do not commit.** I review and commit.
- **Make your first file edit within your first three actions. Never background a command.**

## Return contract

Write `campaign/workers/STATUS_X36.md`, under 300 words:

1. The exact before/after of the changed lines in `fit_segmented`, quoted.
2. Every other RSS-minimising site you found, with `[OBSERVED <path>:<line>]`, and what you changed.
3. Whether any behaviour other than tie-breaking changed (it should not).
4. Anything you could not do.

Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. Do not claim the tests pass —
you are not running them. I run them.
