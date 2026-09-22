# Brief X46 — draft the dev-only preprint from the claims ledger

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You are drafting a workshop-length preprint. **Every number in it must be copied from
`docs/claims_ledger.md`.** Do not compute, estimate, round differently, or infer any number. If a number
you want is not in the ledger, write `[TODO: not yet in ledger]` and move on. Inventing a plausible
number is the single worst thing you can do in this unit.

**Do NOT run `python`, `pip`, `pytest`, `hpc`, `qsub`, `tar`, `rsync`, or `ffmpeg`.** `aquarius01` is a
login node. This unit is reading and writing Markdown only. Do not commit. Do not touch anything under
`/scratch/`. IGNORE `.claude/worktrees/` and `.git/`.

## Output

**One file: `paper/preprint_dev_20260923.md`.** Target 3,500–5,000 words. Markdown, with a YAML-ish
title block at the top. Create the `paper/` directory entry only if missing; `paper/figures/` already
exists and holds the figures.

## Sources, in priority order

1. `docs/claims_ledger.md` — **94 rows, the sole source of every number.** Each row carries the claim,
   the report JSON path, the key, its registration status and its cluster. Cite rows by their ID.
2. `docs/plan_publishable_then_top_venue_20260922.md` §7 and §8 — the narrative outcome record; useful
   for framing and for which findings are headline.
3. `docs/external_comparison_20260923.md` — the related-work table, 38 external rows.
4. `docs/limitations_external_20260923.md` — limitations already written; fold in, do not contradict.
5. `paper/figures/figures_manifest.json` — which figures exist and what each series is sourced from.
   Reference figures as F1–F4. **F5 does not exist and must not be referenced.**

## Structure

1. **Title + abstract** (200 words). The abstract states the channel result and the depth result, both
   with their intervals, and names the dev-only scope in its last sentence.
2. **Introduction** — the problem: a small local executor paired with a strong hosted planner, and how
   the hosted budget should be spent. Contributions as a bulleted list, each one traceable to a ledger row.
3. **Setup** — AppWorld; the planner (`gpt-5.6-luna`) and executor (`ibm-granite/granite-4.2-8b`);
   the advice vs action channels; the replayed-prefix design; metrics `goal_pass` and TGC; the paired
   task- and scenario-clustered percentile bootstrap (10,000 draws) and the 7.00 pp non-inferiority
   margin; n = 114 pairs from 57 tasks × 2 seeds, 19 scenario clusters.
4. **The action channel beats the advice channel at matched trigger** — CHAN-C1-02 as the headline,
   CHAN-C1-03 for the live-vs-oracle equivalence, ADV-FC-01/ADV-FC-02 for the full-context control.
   State CHAN-C1-03 as "cannot distinguish at n = 114", never as "equal".
5. **It is also cheaper** — COST-01 (dominance on all three axes), COST-02 (the one flip, off the
   critical path), COST-03 (NI verdict is currency-invariant). Note that COST-03 is an NI result on
   **TGC**, not `goal_pass`, and that m=9 fails on interval width rather than on its point estimate.
6. **Prefix depth** — the curve, and then the honest negative: MULT-01 shows no single adjacent-depth
   step is significant before or after Holm correction, so the effect is a rise **across a span** and
   never a jump at a named depth. Say so plainly; it is a strength of the paper, not a weakness to bury.
   No figure may show a breakpoint marker.
7. **What the prefix actually conveys** — the narrated-prefix control (the NARR rows, if present; if the
   ledger has no NARR row yet, write the section heading and `[TODO: narrated contrast not yet in
   ledger]` and nothing else).
8. **Receivers and tailoring** — TAILOR-07, HF-02 (registered C3, answered *no*), MECH-07. The reading
   is that depth, tailoring and suffix training are partially substitutable and do not stack.
9. **Mechanism** — the MECH rows: discovery is front-loaded, and the rise at m6→m9 is earned on handoff
   episodes rather than arriving by construction.
10. **A second executor family** — QWEN-04 for the curve, QWEN-03 for why no floor-relative lift may be
    claimed. This section must be scrupulous: the floor is invariant to the plan and is not a
    competence baseline.
11. **Related work** — from `docs/external_comparison_20260923.md`. Do not add citations of your own;
    use only rows in that file, and keep each row's attribution exactly as written there.
12. **Limitations** — dev split only, no test-split read, n = 114, single planner, the Qwen floor defect,
    the cap-81 ceiling scoring below cap-25, and the analysis defects found and fixed. Be direct.

## Constraints

- **No number that is not in the ledger.** Where the ledger gives both scenario- and task-clustered
  intervals, report both. Where it flags a ⚠, carry that caution into the prose rather than dropping it.
- Do not describe any result as significant unless its ledger row says its interval excludes zero.
- Do not write a "future work" section promising runs. Do not claim a test-split result exists.
- Frozen documents are read-only: `docs/prereg_*.md` must not be modified.
- Prose, not bullet soup: sections 4–10 should read as paragraphs with numbers inline.

## Return contract

`campaign/workers/STATUS_X46.md`, under 200 words: the word count of the draft, the list of ledger row
IDs you cited, and every place you wrote `[TODO:`. Tag each claim `[OBSERVED path:line]` or `[INFERRED]`.
State plainly if you were unable to source something.
