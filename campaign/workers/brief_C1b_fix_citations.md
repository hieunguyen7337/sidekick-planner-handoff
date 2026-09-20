# C1b — §10 of RUNS.md cites a brief as evidence; repoint it at the artifacts

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own **`campaign/RUNS.md` section 10 only** (currently around lines 2229–2313). Touch no other
file and no other section. **Do not commit, do not run git, do not `qsub`, do not run python, do not
run the analysis.** A live GPU job (`25560367`) is running; leave it alone. `aquarius01` is a login
node — steering only, `timeout` on anything you do run.

## The defect

Every `[OBSERVED ...]` tag in §10 cites `campaign/workers/brief_C1_dev_frontier_record.md`. That
brief is *my own prose*, not an artifact. Citing it proves only that the brief was written, not that
the data says what the section claims. A ledger of record cannot carry circular provenance — this
exact defect already occurred once in this project (R4's post-mortem cited briefs as evidence) and
must not stand a second time.

## The fix

Replace every citation in §10 that points at `brief_C1_dev_frontier_record.md` with one that points
at a real artifact, using the mapping below. Change **only the bracketed tags** — do not alter a
single number, sentence or table cell in the section.

The durable report now exists at:

    campaign/results/hj8_frontier_dev_20260920.report.json

It is the verbatim output of `scripts/analysis/j8_frontier.py` for this run. Its top-level keys are
`headline`, `headline_refused`, `refusals`, `oracle_semantics`, `oracle_semantics_citation`,
`min_rows`, `seeds`, `resample_unit`, `planner_calls_definition`, `arms`, `contrasts`, `frontier`,
`oracle_headroom`, `f1`, `h3`, `headline_population`, `population_preamble`, `population_notes`,
`population_disagreements`, `population_disagreements_text`, `contrast_accounting`,
`quality_populations`.

Mapping from claim to citation:

| claim in §10 | cite instead |
|---|---|
| the arm table, per-episode call rates, crash counts and per-call crash rates | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "frontier"]` |
| per-arm token spend and USD | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "arms"]` |
| the F1 table and its rule | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "f1"]` |
| oracle headroom quality and calls | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "oracle_headroom"]` |
| the H3 AUROC/ECE table | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "h3"]` |
| AUROC is computed on scores / population and pairing semantics | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: keys "quality_populations", "planner_calls_definition"]` |
| oracle semantics "runs free" | `[OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json: key "oracle_semantics_citation"]` |
| the three sidekick configs differ only in `verifier.threshold` | `[OBSERVED configs/hj8_sidekick_tau03.yaml:37]` and `[OBSERVED configs/hj8_sidekick_tau07.yaml:37]` |
| decoding is `temperature: 0.7` | `[OBSERVED configs/hj8_sidekick_tau03.yaml:25]` |
| the report script itself | `[OBSERVED scripts/analysis/j8_frontier.py]` |

Anything that is a judgement rather than a reading — "decided by bootstrap interval width",
"calibration failure, not a discrimination failure", "not resolvable on dev", "three stochastic
replicates of one policy", "F2 is not established" — keeps its `[INFERRED]` tag. Do not convert an
`[INFERRED]` into an `[OBSERVED]`.

Two further edits to the Provenance block:

1. It currently says the JSON is "session scratch, not durable — the numbers below are the record".
   That is now false. Replace with a pointer to
   `campaign/results/hj8_frontier_dev_20260920.report.json`.
2. The A7 comparison numbers (value-function router AUROC 0.6212, feature-blind floor 0.6245) did
   **not** come from this report — they are from the earlier A7 work. Do not cite the JSON for them.
   Tag them `[OBSERVED campaign/RUNS.md]` only if you can find them in an earlier section of
   `RUNS.md` and give that section's line number; if you cannot find them, tag them
   `[INFERRED — carried from the A7 unit, source not located in RUNS.md]` and say so in STATUS.
   Do not delete the comparison.

## Constraints

- Numbers, tables and sentences are frozen. You are editing citation tags and two provenance
  sentences, nothing else.
- Do not renumber, reword or delete any other section.
- If a mapping above does not fit a claim you find, leave that tag alone and list it in STATUS
  rather than guessing.

## Return contract

Write `campaign/workers/STATUS_C1b.md`. Final report, five lines or fewer: how many tags you
repointed, how many you left alone and why, what you did about the A7 numbers, and confirmation that
no number or sentence in the tables changed. Tag claims `[OBSERVED <path>:<line>]` / `[INFERRED]`.
