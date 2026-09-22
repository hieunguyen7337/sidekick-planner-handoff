# Brief X25 — splice the novelty verdicts, and build the external comparison table

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation only. **Do NOT `qsub`, do not touch a GPU, do not run any evaluation or training. Do
not edit `src/`, `configs/`, `scripts/` or anything under `campaign/results/`.**

## 🔺 The rule that matters most in this unit

**You may not introduce a single new citation, number, paper title, author name or URL.**

Every fact you write must already exist in one of exactly two files:

- `campaign/workers/lit/extracts_20260922.md` — records fetched and verified by Claude
- `docs/novelty_boundary_v2.md` — Claude's own judgements

A previous unit on this project invented a paper — a plausible title, a real author surname taken
from another work's reference list, and an arXiv identifier belonging to an unrelated paper on
probabilistic logic. It survived a casual check because the identifier resolved. If you cannot find a
fact in one of the two files above, **write `NOT ESTABLISHED` and move on.** Do not search, do not
recall, do not reconstruct. This is not a stylistic preference: a fabricated citation in a thesis is
treated as misconduct.

## Task 1 — splice the nine novelty verdicts (verbatim)

`docs/literature_review_20260923.md` has nine sections, each ending:

```
### What we add

TODO(claude): novelty verdict
```

`docs/novelty_boundary_v2.md` §2 contains nine verdicts headed `### Theme 1 — …` through
`### Theme 9 — …`, matching the review's nine themes in order. Each verdict is written as a
blockquote.

Replace each `TODO(claude): novelty verdict` line with the matching verdict's text, **copied
verbatim**, with the blockquote `> ` markers removed so it reads as body prose. Do not paraphrase,
summarise, shorten, "improve", re-order or re-punctuate a single sentence. These are the author's
words and the whole point of the unit is that they arrive unchanged.

Match by theme number and confirm the theme titles correspond. If any theme title does not match,
stop and report it rather than guessing.

Verify afterwards that zero occurrences of `TODO(claude)` remain, and that each spliced paragraph
appears exactly once.

## Task 2 — the external comparison table

Create `docs/external_comparison.md`: a table placing our measured arms beside published AppWorld
results, so a reader can see the benchmark's landscape without being misled into thinking our numbers
are comparable to it.

**Published rows** — take these *only* from `campaign/workers/lit/extracts_20260922.md` §J. Include
the AppWorld paper's baselines (GPT-4o ReAct, GPT-4-Turbo ReAct, LLaMA-3 FullCodeRefl, DeepSeek,
Mistral-7B CodeAct), LOOP, CANOPY, ACE, and the leaderboard anchor for `gpt-5.6-luna`. Reproduce TGC
and SGC exactly as recorded there, with the split each was measured on.

**Our rows** — `planner_alone`, `sft_plan`, `executor_alone` and the best prefix arm, with TGC, the
split (dev), and the harness caveats.

**The caveat block, which must appear directly beneath the table, not in a footnote.** State plainly:

1. Our numbers are **dev**, 57 tasks × 2 seeds; published numbers are test_normal or test_challenge.
   They are not comparable and we make no leaderboard claim.
2. Our harness is a minimal loop; the leaderboard entry for the same planner model uses a different
   scaffold ("kecaipan capybara") at 9.3 mean interactions against our 14.4.
3. Our `planner_alone` ran under a 25-call cap, which ended 11 of its 12 `limit` episodes
   [OBSERVED `configs/pilot_planner_alone.yaml:25`, `configs/hj8_fixed_k_3.yaml:39-41`]. An uncapped
   re-run is in flight; until it lands, the gap between our 68.4 TGC and the published 85.1 is
   partly a cap artefact and partly scaffold difference, and we do not yet know the split between
   them.
4. The pinned AppWorld data release we use ships **90 train / 57 dev**, not the paper's 105 / 60
   [OBSERVED `docs/feasibility/g2_appworld.md:30-37`].
5. Methods trained with heavy on-policy RL (LOOP, CANOPY) are solving a different problem —
   maximising a standalone agent's score — and are included for landscape only.

The caveat block is the reason the table exists. A reader who takes one number away from this file
should take away that our figures are internal and paired.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. You need no compute.
- Dev only; **never read, list or load `test_normal` or `test_challenge` data.** (Quoting published
  test-split *numbers from the extracts file* is fine — that is literature, not our data.)
- Frozen, read only: every `docs/prereg_*.md`, `docs/literature_matrix.md`,
  `docs/novelty_boundary.md`, `docs/novelty_boundary_v2.md`, every `hj8_*` and `hj11_*` config.
- **Do not edit `paper/bibliography.bib`** — it is under audit in another unit.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X25.md`, under 500 words: confirmation that zero `TODO(claude)` markers
remain; confirmation that each verdict was copied verbatim and the method you used to check that;
any theme whose title did not match; the external table's path and row count; and **an explicit list
of every fact you marked `NOT ESTABLISHED`**. Tag every claim `[OBSERVED <path>:<line>]` or
`[INFERRED]`.

State plainly: **you introduced no citation, number or URL that was not already in one of the two
permitted source files.**
