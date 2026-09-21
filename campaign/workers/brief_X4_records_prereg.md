# Brief X4 — ledger entries, seam contract, and the HJ-12 dev preregistration

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

This is a writing unit. You produce documents; you change no code.

## Scope — you own these files, and only these

Modify:
- `campaign/RUNS.md` (append a new section only)
- `docs/FOLLOWUPS.md` (append entries only)
- `campaign/briefs/SEAM_CONTRACT.md`

Create:
- `docs/prereg_hj12_dev_20260922.md`

**Do not touch anything under `src/`, `scripts/`, `configs/`, or any other file in `campaign/`** —
three other units are editing this tree in parallel. Never edit an existing RUNS.md section; append.

## FROZEN — read, never edit

`docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`, `docs/prereg_j9_freeze_20260920.md`, and every
`hj8_*` / `hj11_*` config. If you believe one of them is wrong, say so in your STATUS file. A frozen
preregistration that turns out to be inconvenient is evidence, not a document to fix.

## Task 1 — `campaign/RUNS.md`, new section "## 12. The E-series: intervention-aware retrain"

The facts, all verified against `campaign/results/hj8_frontier_iaware_20260921.report.json`. Every
number below is dev, n=114 per arm, paired and task-clustered, 10,000 bootstrap resamples.

The defect: the executor was trained with planner interventions stripped from its context at three
enforcement layers, while the runtime injects exactly those `INTERVENTION:` turns at evaluation
time. Every escalation result the project had produced was measuring an untrained model's reaction
to an off-distribution token. `campaign/RUNS.md` §11 records the finding; this section records the
experiment that followed.

Two adapters, identical but for the training data: 497 rows and 479 sequences both, hyperparameters
byte-identical, 267 `INTERVENTION:` turns retained versus 0.

Survivor goal_pass against planner calls per episode:

| adapter | 1.0 calls | ~2.4 calls | ~6.8 calls |
|---|---:|---:|---:|
| stripped (`sft_b_plus`) | 0.700 | 0.662 | 0.605 |
| retained (`sft_b_plus_iaware`) | 0.718 | 0.696 | 0.701 |

Same arm, new adapter minus old, survivors:

| arm | metric | Δ (pp) | 95% CI | n |
|---|---|---:|---|---:|
| `fixed_k_3` | goal_pass | +10.18 | [+2.67, +17.43] | 97 |
| `fixed_k_3` | TGC | +12.37 | [+1.05, +23.60] | 97 |
| `fixed_k_10` | goal_pass | +3.83 | [−3.77, +11.38] | 111 |
| `sft_plan` | goal_pass | +1.81 | [−3.28, +7.00] | 114 |

Crashes fell from 17/114 to 0 at k=3 and 3/114 to 0 at k=10. Plan-following did not regress, so the
failure mode stripping was guarding against did not appear.

What was **not** established: within the new adapter, plan-only remains nominally ahead of
escalation on goal_pass (`sft_plan − fixed_k_3` = +1.70 [−4.36, +7.62]) and the oracle does not beat
plan-only either (−0.86 [−6.61, +4.93]). On TGC the sign flips (`fixed_k_3` ahead by 6.14
[−15.79, +2.63]) but the interval still contains zero.

⚠ **Record this explicitly, in its own paragraph**: the J9 freeze made `goal_pass` the primary
metric, and goal_pass shows no benefit from escalation. TGC hints at one. Reaching for TGC now is
exactly the researcher degree of freedom that freeze was written to prevent. It is written down here
so that nobody later discovers it and assumes it went unnoticed. 114 pairs cannot resolve a 7 pp
effect; the TGC interval is 18 points wide.

Commits: `0b47eca` (the dataset-writer flag that refused to emit the dataset), `b6da3a6` (the
action-review build), `6b04ba9` (the retrained adapter), `6556de6` (this analysis).

## Task 2 — `docs/FOLLOWUPS.md`, two appended entries

1. **The action-review gate is inert against the real planner.**
   `src/sidekick/systems/action_review_gate.py:53-61` decides approve-versus-replace by reading
   `resp.code`, but `CodexExecPlanner.correct` (`src/sidekick/agents/planner.py:316-335`) returns
   prose and never sets `code` — its prompt says "Reply with concise correction text only". Against
   the hosted planner every review would return the verdict `approve` while still spending a call.
   The unit test passed because its stub sets `code` (`tests/unit/test_action_review.py:168`).
   Record that the repair is assigned, and that `planner.act` (`planner.py:337-352`) is the method
   that does return a parsed action.
2. **The pivot.** State plainly: the advice channel has now been priced twice and is worth nothing
   measurable. Use **only** these figures, read directly from
   `/scratch/n12194778/sidekick/results/b1_pilot_train_20260920/manifest.json` — they are the
   pilot's own point-level classification over 1,600 branches at 200 points, 195 complete:

   | field | value |
   |---|---|
   | `n_needed` | 11 |
   | `n_needed_strict` | 2 |
   | `n_needless` | 9 |
   | `n_harmful` | 9 |
   | `n_ambiguous` | 175 |
   | `needed_fraction` | 0.0564, task-clustered CI [0.0270, 0.0874] |
   | `mean_delta_crn` | +0.004586, task-clustered CI [−0.01082, +0.02048] |

   The mean-effect interval **includes zero**. Say so. Do not quote any branch-level "helping versus
   harming" tally: it is a recount at a different unit of analysis and is not what this pilot
   reports. After the retrain removed the format mismatch, advice became neutral rather than useful.

3. **Deviation: the B1 pilot ran at δ = 0.2, not the frozen 0.166.**
   `docs/prereg_b1_pilot.md` §2 freezes δ = 0.166 as the primary label band, citing the J6 train
   manifest. The pilot's own manifest records `delta_band_delta: 0.19999999999999998` with
   `delta_band_rule: "75th percentile of |treated_gpr[101]-treated_gpr[102]| over train-split points
   with both treated replicates"` and `delta_band_frozen_on: "train"`. So the *rule* was re-applied
   to this pilot's data and produced 0.2, whereas the preregistration froze the *number* 0.166.
   Record this as a deviation from a frozen document, state which quantities it affects (the
   `needed`/`needless`/`ambiguous` label counts, which are band-dependent) and which it does not
   (`mean_delta_crn`, which is band-free), and **do not resolve it** — flag it for the user. A frozen
   preregistration that turns out to have been departed from is evidence, not a document to fix.
   Also record `factual_vs_treated.fraction_factual_outside_treated_range` = 0.1269 over 197 points
   as the manifest's own manipulation check. The campaign therefore changes the *protocol* (planner acts, or
   starts the episode and hands off) rather than the idea (a small executor specialised to one
   frozen planner).

## Task 3 — `campaign/briefs/SEAM_CONTRACT.md`

It currently names eight systems. Add the ninth and tenth: `action_review` (built, E4, repair
pending) and `prefix_handoff` (being built now — the planner's first `m` recorded steps are replayed
onto a fresh environment and the executor finishes the episode live). Record the new policy flags
`review_proposed_action`, `takeover`, `handoff_allowed`; the `handoff:` config block
(`source_campaign`, `source_system`, `m`); and the cost key `replayed_planner_tokens`, which sums a
replayed prefix's planner usage **excluding `cached_input_tokens`** because cached tokens are
re-sent context rather than new work. Keep the file's existing format.

## Task 4 — `docs/prereg_hj12_dev_20260922.md`, the dev preregistration

This must be committed **before the first HJ-12 job is submitted**. A prediction written after the
numbers arrive is worth nothing. Follow the structure and register-then-run discipline of
`docs/prereg_j9_freeze_20260920.md` (read it as the model; do not edit it).

Contents:
- **Three claims.**
  - **C1 Channel**: at a matched trigger and call count, a planner that *acts* beats a planner that
    *advises*. Primary contrast `takeover_fixed_k_10 − fixed_k_10_iaware`, paired, 2.4 calls/ep.
    Secondary at k=3 and at the exception trigger.
  - **C2 Allocation**: quality against hosted-token fraction for the planner-prefix/executor-suffix
    split bows above the straight line joining `sft_plan` and `planner_alone`; there exists an m at
    which the hybrid is non-inferior to `planner_alone` within 7 pp at no more than about half its
    non-cached tokens.
  - **C3 Tailoring**: an adapter trained on delegated suffixes beats `sft_b_plus_iaware` on the same
    split arms.
- **Metrics**: `goal_pass` primary, TGC secondary, **both reported for every arm and contrast**,
  carrying the J9 decision forward unchanged. Non-inferiority margin 7 pp, unchanged. Task-clustered
  paired percentile bootstrap, 10,000 resamples, the `paired_diff(resample="task")` implementation
  in `scripts/setup/hj1_gate.py`. Both populations: all-episodes (crash scored 0) and survivors.
- **Arms and the m grid**: m ∈ {2, 4, 6, 9}, justified by the planner's dev step distribution
  (min 5, median 12, max 25).
- **Gate G1** (verbatim): proceed to the live phase in full if either some m ≤ 6 reaches
  non-inferiority to `planner_alone`, or the curve is monotone with `prefix_m6 − sft_plan` ≥ +5 pp
  goal_pass. Otherwise the live phase shrinks to the channel arms only.
- **Gate G2** (verbatim): C1 is established if `takeover_fixed_k_10 − fixed_k_10_iaware` excludes
  zero on goal_pass. C2 holds in deployable form if `planner_handoff` is non-inferior to
  `planner_alone` at no more than about half its tokens.
- **Advance predictions**, written now: the prefix curve rises meaningfully at about 65%; C1
  excludes zero at k=10 at about 40%; C2 at about 40%. Record these as the falsification anchor.
- **Threats to validity.** Include at minimum: (a) replay determinism — the hash check compares
  `snapshot_hash`, a sha256 of the observation history and **not** a database dump
  (`src/sidekick/replay.py:15-20`), so it detects visible divergence only, and the divergence rate
  must be reported; (b) episodes shorter than m contribute the planner's own outcome, so the
  `handoff_occurred` population is reported alongside the full one; (c) C2's comparator is
  `planner_alone`, not the `fixed_k(k_matched)` that Claim F1 uses — say why the comparator changed
  (the question moved from "beat periodic review" to "match the planner at a fraction of its cost")
  and confirm F1 is still reported exactly as registered.
- **Scope**: dev only. This document does not amend `docs/prereg_v1.md` or the J9 freeze, does not
  authorise any test read, and does not pre-judge any outcome.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync` or `ffmpeg` there.
- Put a `timeout` on every command.
- **Read-only** on `/scratch/n12194778/sidekick/results/`.
- **Do not read, analyse or report any `test_normal` or `test_challenge` data.**
- **Do not commit.** I review and commit.
- Do not invent a number. Every figure in this brief is verified; if you need one that is not here,
  mark it `[NEEDED]` and leave it blank rather than filling it in.

## Return contract

`campaign/workers/STATUS_X4.md`, under 500 words: the files written, a one-line summary of each,
anything you marked `[NEEDED]`, and any place where this brief contradicts what you found in the
repo. Tag claims `[OBSERVED <path>:<line>]` or `[INFERRED]`.
