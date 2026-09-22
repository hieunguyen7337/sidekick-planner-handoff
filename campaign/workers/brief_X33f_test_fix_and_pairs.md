# Brief X33f — one broken test assertion, and matched decomposition pairs across receivers

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Make your first file edit within your
first three actions. Two files: `tests/unit/test_j13_mechanism.py` and `scripts/analysis/j13_mechanism.py`.
Your X33e fix worked — M2 now measures real errors on real data. Two small things remain.

## Task 1 — a test indexes into `None`

`test_m2_ignores_successful_observations` ends with:

```python
assert m4["first_error_rel_step_dist"]["min"] is None
```

`quartiles()` returns **`None` for an empty list** [OBSERVED scripts/analysis/j13_mechanism.py:75-78], and
in that test there are no errors, so `first_error_rel_step_dist` **is** `None` and the subscript raises
`TypeError` before the assertion is evaluated. It is the only failure in the suite (1 failed, 552 passed).

Change it to assert the distribution itself is `None`:

```python
assert m4["first_error_rel_step_dist"] is None
```

Then scan the whole test file for any other subscript of `first_error_rel_step_dist` (or of any other
value `quartiles()` may return `None` for) in a no-error scenario and fix it the same way. Do not change
`quartiles()` — returning `None` for an empty population is the correct, non-silent behaviour and is what
the project's "never report a believable zero" rule wants.

## Task 2 — let both receivers be decomposed on the same depth pairs

`measure_m3_prefix_exhausted` currently derives its decomposition pairs from the discovered grid, so the
two receivers are decomposed on **different** pairs and cannot be compared:

- tailored (grid m2…m11) → `m2_to_m10`, `m2_to_m11`
- zero-shot (grid m6, m9, m11) → `m6_to_m9`, `m6_to_m11`

[OBSERVED campaign/results/hj13_mechanism_{tailored,zeroshot}_20260923c.report.json, key
`m3_prefix_exhausted.primary.decompositions`]

This matters for the headline: the tailored `m2_to_m11` decomposition attributes 83.3 % of the rise to the
silenced subset, but only because the silenced population grows from **0** episodes at m=2, whereas
zero-shot `m6_to_m11` attributes 60.5 % to the handoff subset starting from 3 silenced episodes at m=6.
The two numbers are not in conflict; they are answers to different questions, and quoting them side by
side would be misleading.

**Add a CLI option** `--decompose-pairs m6:m9,m6:m11` (comma-separated `base:target`, repeatable values in
one string). When given, the script emits **exactly** those decompositions, named `m<base>_to_m<target>`,
in addition to nothing else. When omitted, behaviour is unchanged.

**Fatal, not silent:** if a requested base or target depth is not among the arms discovered for the chosen
receiver, `raise SystemExit` naming the missing depth, the receiver and the depths that *are* available.
Never fall back to the nearest available depth and never silently drop a pair.

Keep every existing key and the markdown renderer working; the markdown should print whichever pairs were
computed.

## Tests to add, `tests/unit/test_j13_mechanism.py`

1. `test_decompose_pairs_emits_exactly_the_requested_pairs` — parse `"m6:m9,m6:m11"` against a scripted
   arm set containing m6, m9, m11 and assert the decomposition keys are exactly
   `{"m6_to_m9", "m6_to_m11"}`.
2. `test_decompose_pairs_missing_depth_is_fatal` — requesting `m6:m9` against an arm set with only m6 and
   m11 raises `SystemExit` naming `9`.
3. `test_decompose_pairs_default_is_unchanged` — omitting the option reproduces the current key set on a
   scripted grid.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Never background anything.
  Never read or list `test_normal` / `test_challenge`. Do not edit `j8_frontier.py`, `j10_report.py` or
  `src/sidekick/**`. Never write under `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X33f.md`, under 250 words: the before/after of the assertion; any other
`None`-subscript sites you found; the new CLI option's parsing code and its fatal branch; the test names.
`[OBSERVED path:line]` / `[INFERRED]` on every claim. **Do not claim any test passes.**
