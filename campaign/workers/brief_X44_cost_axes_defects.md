# Brief X44 — the USD cost axis is wrong, and the arms block lost its labels

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**FILE EDITS ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Make your first file edit within your
first three actions. Two files: `scripts/analysis/j12_cost_axes.py` and `tests/unit/test_j12_cost_axes.py`
(both yours from X40; the five tests there pass, so the bugs below are **not covered** by them).

I ran your script on the eleven real frontier arms. It completed and wrote
`campaign/results/hj13_cost_axes_20260923.report.json`. Three things in that report are wrong.

## Defect 1 (fatal) — an arm that makes **zero hosted calls** is priced at $0.0799/episode

The `executor_alone` arm has `hosted_calls_per_episode: 0.0` and `noncached_tokens_per_episode: null`,
yet `usd_per_episode: 0.079943` — the **highest** dollar figure of any arm. An arm that never calls the
hosted planner must cost **exactly $0.00** on the provider axis.

## Defect 2 (fatal) — the dollar ordering runs **inverse** to the token ordering

Observed values, in the order they appear in the report's `arms` block:

| index | tokens/episode | usd/episode | calls/episode |
|---|---:|---:|---:|
| 0 | null | 0.079943 | 0.0 |
| 1 | 23,906 | 0.072651 | 1.0 |
| 7 | 357,448 | 0.052185 | 9.77 |
| 8 | 443,361 | 0.049698 | 11.25 |
| 9 | 684,453 | 0.035479 | 14.43 |
| 10 | 1,160,215 | 0.048208 | 17.35 |

More tokens costs **less**. With the price card (`gpt-5.6-luna`: input $0.20, cached_input $0.02,
output $1.20 per 1M tokens), 684,453 non-cached tokens priced entirely as input is **$0.137** — nearly
four times what the report says, and output tokens only push it up. So the dollar figure is not a sum of
priced tokens at all. Likely causes to check, in order: a division by episode count applied twice; a
per-1M scaling applied as per-1k or vice versa; the cached and fresh splits swapped so that big runs are
billed almost entirely at the $0.02 cached rate; or the value being an average of per-token prices rather
than a total. **Find the actual cause, state it in STATUS with `path:line`, and fix it** — do not paper
over it with a rescale that happens to make the numbers look plausible.

Every one of the 33 reported `ordering_flips` is between `usd_per_episode` and
`hosted_calls_per_episode`, i.e. they are all artefacts of this defect. Once it is fixed the flip list
must be recomputed; if the ordering then turns out to be genuinely stable, `ordering_flips` should be
empty and `ordering_is_stable_across_axes` true.

## Defect 3 — the `arms` block is keyed by **integer index**, not by arm label

`jq '.arms | to_entries[]'` yields keys `"0"`, `"1"`, … `"10"`, so no reader can tell which row is which
arm. `ordering_by_axis` does carry the labels, so the labels exist and are simply being dropped when the
`arms` map is built. Key `arms` by the arm label, as `scripts/analysis/j8_frontier.py` does in its own
report (find that construction and cite `path:line`).

## Also fix

`noncached_tokens_per_episode` is `null` for `executor_alone`. A zero-hosted-call arm has **zero**
non-cached tokens, which is a measured fact, not a missing value. Emit `0.0`. Reserve `null` for "not
measurable" and say in STATUS which cases remain `null`.

## Tests to add (the existing five pass and did not catch any of this)

1. `test_zero_hosted_call_arm_costs_zero_usd` — a scripted arm with no planner usage records yields
   `usd_per_episode == 0.0` and `noncached_tokens_per_episode == 0.0`, not `null`.
2. `test_usd_is_monotone_in_tokens_at_a_fixed_mix` — two scripted arms with identical cached/fresh/output
   *proportions* but one with 10× the tokens: the second must cost ~10× the first.
3. `test_usd_matches_a_hand_computed_total` — one scripted episode with a known split (say 100,000 fresh
   input, 50,000 cached input, 10,000 output) priced against `configs/cost/prices_2026-09.yaml` equals
   the hand-computed dollar total; put the arithmetic in the test as a comment.
4. `test_arms_block_is_keyed_by_arm_label` — the report's `arms` keys equal the labels passed on the CLI.
5. `test_ordering_flips_are_empty_when_axes_agree` — three scripted arms whose three axes give the same
   ordering produce `ordering_flips == []` and `ordering_is_stable_across_axes is True`.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`. Never background
  anything. You may read `campaign/results/hj13_cost_axes_20260923.report.json` with `jq` to see the
  shape. Never read or list `test_normal` / `test_challenge`. Do not edit `j8_frontier.py`,
  `j8_noncached_cost.py`, `j13_mechanism.py` or `src/sidekick/**`. Never write under
  `/scratch/.../results/`. **Do not commit.**

## Return contract

`campaign/workers/STATUS_X44.md`, under 350 words: the **actual root cause** of the dollar defect with
`path:line` and the before/after hunk; the `j8_frontier.py` construction you mirrored for the label
keying; what remains `null` and why; the test names. `[OBSERVED path:line]` / `[INFERRED]` on every
claim. **Do not claim any test passes.**
