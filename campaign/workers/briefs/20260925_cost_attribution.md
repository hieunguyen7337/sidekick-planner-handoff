# Unit ATTRIB: charge channel arms for their replayed plan (tokens and dollars), and add J10's calls companion

WT = /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 (HEAD 4111c9f). Written by Claude, 2026-09-25.
Common rules: `campaign/workers/briefs/20260924_common_rules.md`.

Read first:
- the CACHECALLS audit: `campaign/results/cache_calls_audit_20260925.report.json` (use `jq` by key) and
  `campaign/workers/staging/ledger_rows_20260925_cachecalls.md`.

## Claude's decision: the convention is attribution
An episode is charged for all the planner output it consumes, bought live or replayed. The prefix arms and the
one-plan floor are already charged this way on all three axes: calls, tokens and dollars
(`j12_cost_axes.py:361-376`, `loop.py:151,647`). The depth cost analysis (GANZ-03, ROB-19's prefix figures) needs
it.

On this convention the published **calls** figures are correct: a replayed plan is one call. The gap is that the
**channel arms** (fixed_k takeover, advise, show and neutral, and any other arm whose step-0 plan comes from
`packet_source` with `provider == "cache"`) are charged the replayed plan's call but **not its tokens or dollars**.
So the published tokens and USD figures for channel arms are under-attributed.

## A. Full-attribution pricing (analysis only; existing outputs unchanged)
Add an opt-in path to `scripts/analysis/j12_cost_axes.py`: a flag or function argument, off by default. With it, each
channel-arm episode's cached plan event is priced from the **source** plan event it replays. Look that event up the
way the `sft_plan` branch at :361-367 does: `usage.raw.cached_from` names the source events file, and the
`packet_source` config names the campaign. The default outputs must stay byte-identical: prove it by diffing a
default run against the committed reports, excluding `generated_at`.

Then write `campaign/results/cost_attribution_20260925.report.json`. For every published tokens or USD figure that
involves a channel arm, give the published value and the fully-attributed value, with intervals where the figure has
them, and state whether any verdict, direction or ordering changes. Find the figures by grepping `docs/claims_ledger.md`
for `USD`, `\$` and `tokens`. At least:
- COST-01..04, including COST-02's frontier ordering and COST-03's NI cost axes;
- ROB-18 and ROB-19;
- CHAN-PRICE-01 and CHAN-PRICE-02 (the 3.19× non-cached tokens and the H2 P4 predicate);
- DEC-05;
- any figure in `paper/preprint_dev_v2_20260924.md` stating channel-arm tokens or dollars.

Reproduce each figure through its own script's function, as the audit did. Run everything in PBS.

## B. J10 report companion (Amendment 4; pre-data)
In `scripts/analysis/j10_report.py`, append new functions only, at the end of the file, like
`a1_hstar_companions`. No existing line may move, and no existing key may change: A1 and its amendments cite line
numbers.

Top-level key `a1_am4_calls`, called from `build_report_a1`'s return in the same way `a1_hstar_companions` is:
```
a1_am4_calls = {
  "per_arm": { "<arm>": {"n_episodes", "calls_attributed_mean", "calls_live_mean", "n_cached_plan_events",
                         "usd_attributed_mean", "usd_as_published_mean"} },   # arms 2, 3, 4-7, 8-12 where present
  "p2_calls_clause": {
     "attributed": {"advise_k1": x, "prefix_m11": y, "holds": x > y},
     "live":       {"advise_k1": x_live, "prefix_m11": y, "holds": x_live > y},
     "holds_both": bool,
     "note": "Amendment 4: P2's calls clause is supported only if it holds under both conventions"
  }
}
```

Definitions:
- `calls_live` = the episode's planner calls minus the calls of its `provider == "cache"` events.
- `calls_attributed` = the count as published.
- The prefix arm is always charged its replayed prefix, as registered at `A1:347-349`.

Tests go in `tests/unit/test_j10_report.py` or a new test file, using the synthetic A1 fixtures, with hand-computed
answers. They must include one cached-plan episode and one prefix episode. Run the whole j10_report test file (its
line-citation tests) and `tests/unit/test_j10_arm_pbs.py` in PBS.

## C. Staging rows
Rewrite `campaign/workers/staging/ledger_rows_20260925_cachecalls.md` under the attribution convention:
- **CALLS-01:** the mechanism.
- **CALLS-02:** the live-only sensitivity for calls. Every cached arm is −1.00 per episode.
- **CALLS-03:** ROB-27's live-only verdict change is a convention artefact; on attribution the published value stands.
- **CALLS-04:** the registered text vs the code, resolved by Amendment 4.
- **CALLS-05:** channel-arm tokens and USD are under-attributed.
- **New ATTRIB-01..n rows:** the fully-attributed values from A, and any verdict change.
- **A13 notes:** only for rows whose printed tokens or USD value is misleading as stated. Keep the style of the
  existing A9/A12 notes (`grep -n 'A12 (' docs/claims_ledger.md`).

## Constraints
- **Data.** Dev campaigns only. Never open `j10_*`, `j11_*`, `j12_*` or `bfcl_*` campaigns, or `test_normal` or
  `test_challenge` data.
- **Workers and runs.** No hosted calls, no codex or luna workers.
- **Login node.** aquarius01 is a login node: python, pytest and bulk jq only in `hpc bash -c '...'`, with timeout,
  `OMP_NUM_THREADS=1` and `PYTHONPATH=src:.`.
- **Shell.** Put scripts in `/home/n12194778/.claude/jobs/91578989/tmp/attrib/` and run them with `bash`.
- **Files you may not touch.** `src/`, configs, preregs, the ledger, the paper, and the pinned checkouts. Claude
  writes Amendment 4 and edits the ledger and the paper.
- **Git.** Do not commit.
- **Reading.** Read narrowly.

## Report (≤ 400 words; [OBSERVED path:line] / [INFERRED] tags)
- A: a table of old vs fully-attributed tokens and USD per figure, with any verdict change, and the byte-identity
  proof;
- B: the new functions with their `path:line` and the test counts with their PBS job ids;
- C: the rows drafted;
- the files changed.
