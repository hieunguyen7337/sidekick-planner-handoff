# Brief X28 — delete the fabricated citations, correct the rest

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation only. **Do NOT `qsub`, do not touch a GPU, do not run any evaluation or training. Do
not edit `src/`, `configs/`, `scripts/` or anything under `campaign/results/`.**

## Source of truth

`docs/lit/bibliography_audit.csv` — every entry in `paper/bibliography.bib` audited against the live
record. Columns include `bibkey`, `claimed_title`, `identifier`, `verdict`, `real_title`,
`real_first_authors`, `real_year`.

**Use the audit's `real_title` / `real_first_authors` / `real_year` as authoritative.** Do not fetch
anything new, do not consult your own memory of these papers, and do not invent a replacement for a
deleted entry. If the audit does not answer a question, leave the entry alone and report it.

## Task 1 — delete four fabricated citations

These four bibkeys claim a paper that does not exist; the identifier attached to each resolves to an
unrelated work:

| bibkey | claimed title | what the identifier really is |
|---|---|---|
| `cascade_cost_valkanas_2025` | Cost-Effective LLM Cascades for Natural Language Understanding | Dynamic Pricing in High-Speed Railways Using Multi-Agent Reinforcement Learning |
| `cascading_aggregating_kotte_2026` | Dynamic Cascading and Aggregation for Heterogeneous LLMs | Lifted Relational Probabilistic Inference via Implicit Learning |
| `sequential_deferral_charusaie_2024` | Sequential Learning to Defer in Multi-Stage Systems | Going beyond Compositions, DDPMs Can Produce Zero-Shot Interpolations |
| `cld_kim_2024` | Collaborative Decoding: Small and Large Models Generate in Concert | Large Language Models: A Survey |

For each:

1. Delete the entry from `paper/bibliography.bib`.
2. Remove every in-text mention from `docs/literature_review_20260923.md`,
   `docs/literature_matrix_v2.md` and `docs/concurrent_work.md`. **Repair the surrounding sentence so
   it still reads correctly** — do not leave a dangling "and (…)" or an orphaned comma. Where the
   sentence listed several works and only one was fabricated, drop that one and keep the rest.
3. Mark the corresponding row `include=no` in `docs/lit/screening_log.csv` with
   `reason=fabricated_citation_removed_X28`.

**Do not invent replacements.** A theme with one fewer citation is correct; a theme with a
substituted guess is not.

## Task 2 — one substitution I am supplying

Theme 4 of the review discusses token-level collaboration and cites the fabricated `cld_kim_2024` for
"Big Little Decoder". The real paper is:

```
Speculative Decoding with Big Little Decoder
Sehoon Kim et al., NeurIPS 2023
arXiv:2302.07863
```

That identifier is **already correct in the audit** if an entry for it exists — check first. Add or
correct a single entry with bibkey `bild_kim_2023` using exactly the details above, and point
Theme 4's Big Little Decoder mention at it. This is the only new entry you may create, and you may
not embellish it beyond those four fields.

## Task 3 — correct the title strings on the ~20 entries that name the right paper

The remaining `MISMATCH` rows point at the **correct** paper but record a differently-worded or
truncated title. For each, replace the `title` field in `paper/bibliography.bib` with the audit's
`real_title`, and correct `author` to the audit's `real_first_authors` where the audit supplies it.

Where the review's prose names a paper by a wrong title, correct the prose too.

## Task 4 — fix the year fields

The audit records seven entries whose claimed year differs from the record: `isp_2024` (→2024),
`llms_cannot_self_correct_huang_2024` (→2023), `ace_2026` (→2025), `early_experience_2026` (→2025),
`routellm_ong_2024` (→2024), `speculative_decoding_leviathan_2023` (→2022), `critic_gou_2023`
(→2023). Set `year` to the record year in each case.

⚠ **Do not rename the bibkeys.** They are referenced from other documents; a bibkey whose trailing
year no longer matches its `year` field is acceptable and preferable to a broken cross-reference.

## Task 5 — fix the reverse-curriculum citation

`docs/literature_review_20260923.md:106` cites RFCL as `https://openreview.net/forum?id=rfcl2024`,
which is a placeholder, not a real OpenReview id. The audit establishes the real record as
**arXiv:2405.03379**, "Reverse Forward Curriculum Learning for Extreme Sample and Demonstration
Efficiency in Reinforcement Learning". Correct the bib entry and the prose, and drop the OpenReview
URL entirely rather than guessing a venue id.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. You need no compute and **no network** — everything is in the audit CSV.
- Dev only; never read `test_normal` or `test_challenge`.
- Frozen, read only: every `docs/prereg_*.md`, `docs/novelty_boundary.md`,
  `docs/novelty_boundary_v2.md`, `docs/literature_matrix.md`, `campaign/workers/lit/extracts_20260922.md`.
- **Do not edit `docs/lit/bibliography_audit.csv`** — it is the evidence.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X28.md`, under 500 words: the four deleted bibkeys and every file/line where
a mention was removed, with the repaired sentence quoted; the `bild_kim_2023` entry as written; the
count of titles and years corrected; the RFCL fix; and the new total entry count in
`paper/bibliography.bib`.

Then state the two numbers I will check: **how many entries remain**, and **how many of those have a
verdict of `OK` or a corrected title traceable to the audit**. Every remaining entry must fall into
one of those two categories — if any does not, name it.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
