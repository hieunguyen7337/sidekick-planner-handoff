# Staging: paper edits for the cost fixes (2026-09-25), not applied

Target: `paper/preprint_dev_v2_20260924.md` (not edited). Convention throughout: **attribution** — an episode is charged for all the planner output it consumes, bought live or replayed. Channel arms (`advise_*`, `takeover_*`) are charged their replayed plan's source plan event (ATTRIB); the one-plan floor (`plan_only` / `sft_plan`) is priced on the plan event it replays, not on its source's last planner action (COSTFIX). Source for every new value: `campaign/results/cost_attribution_20260925.report.json` (key named per edit). Hosted calls, goal_pass and TGC do not change anywhere.

Format: `line N: old string → new string (ledger id)`. Line numbers are those of the file at HEAD 38f19be; the paper is unchanged since 4111c9f.

## §1 table, §3.5 and Appendix B (advice at every step, CHAN-PRICE-02 / ROB-19)

- line 80: `P4 fails (1,414,410 tokens per episode against 300k–700k)` → `P4 fails (1,438,316 tokens per episode against 300k–700k)` (CHAN-PRICE-02, ATTRIB-04; `figures[CHAN-PRICE-01 …].attributed.advise_k1_fullctx.noncached_tokens_per_episode`)
- line 150: `it spent 1,414,410 and made 19.02 hosted calls per episode` → `it spent 1,438,316 and made 19.02 hosted calls per episode` (CHAN-PRICE-02, ATTRIB-04)
- line 152: `at 3.19× its non-cached tokens ([2.47, 4.06]; ROB-19)` → `at 3.24× its non-cached tokens ([2.52, 4.11]; ROB-19)` (ROB-19, ATTRIB-04; `figures[ROB-19 (+ ROB-27)].axes.noncached_tokens_per_episode.attributed`). Task companion (ROB-27, not printed in the paper): [2.49, 4.01] → [2.54, 4.07].
- line 334: `while this arm spent 1,414,410 tokens, far above the prefix arms` → `while this arm spent 1,438,316 tokens, far above the prefix arms` (CHAN-PRICE-02, ATTRIB-04)
- line 340 (Table B1): `| 49,819 |` → `| 73,725 |` in the `advise_fixed_k_10_fullctx` row (COST-01, ATTRIB-01)
- line 341 (Table B1): `| 1,414,410 |` → `| 1,438,316 |` in the `advise_fixed_k_1_fullctx` row (CHAN-PRICE-02, ATTRIB-04)
- line 336 (Table B1 caption), suggested addition after `(114 pairs; CHAN-PRICE-01, CHAN-PRICE-02, COST-01)`: `; each advice arm's replayed plan is charged its source plan's tokens (ATTRIB-01, ATTRIB-04)`.
- Lines 342–343 (`prefix_m9` 357,448, `prefix_m11` 443,361) and line 345 (1.69× hosted calls [1.51, 1.89]) are unchanged.

## Appendix D.9, Table D7 (COST-01)

- line 539: `23,906   $0.003015` → `23,906   $0.003921` (COST-01, COSTFIX; `figures[COST-01 plan_only USD (COSTFIX)].fixed`; regenerated `campaign/results/hj13_cost_axes_fixed_20260923.report.json` `arms.plan_only.usd_per_episode`)
- line 540: `43,823   $0.004386` → `67,729   $0.008308` (COST-01, ATTRIB-01)
- line 541: `49,819   $0.005494` → `73,725   $0.009416` (COST-01, ATTRIB-01)
- line 542: `41,464   $0.004820` → `65,369   $0.008742` (COST-01, ATTRIB-01)
- line 543: `204,500   $0.012203` → `228,405   $0.016125` (COST-01, ATTRIB-01, ATTRIB-02; now above `prefix_m6`'s 221,043 on tokens, so the token column is no longer monotone down the table)
- line 534 (caption), suggested: `(COST-01; TGC from the same arms)` → `(COST-01; TGC from the same arms; channel arms charged their replayed plan, ATTRIB-01; plan_only priced on the plan it replays, COSTFIX)`. Column widths shift by one character where a value gains a digit.
- Rows 538 and 544–548 (executor_alone, prefix arms, planner alone) are unchanged.

## Appendix D.9, line 552 (ROB-18, DEC-05)

- line 552: the ROB-18 clause (`−8,356 non-cached tokens [−17,744, +617], −$0.000674 [−0.001361, −0.000024] (task [−0.001539, +0.000161]) and −0.149 hosted calls [−0.368, +0.070]`) is **unchanged**: the replayed plan is the same source plan in both arms of every matched pair, so it cancels in the difference (ATTRIB-05).
- line 552: `(41.8k against 53.2k for correction-prompt advice)` → `(65.4k against 76.9k for correction-prompt advice)` (DEC-05, ATTRIB-07)
- line 552: `dollars ($0.00478 against $0.00578)` → `dollars ($0.00880 against $0.00980)` (DEC-05, ATTRIB-07)
- line 552: the cap-25 sentence (0.746× dollars, 0.648× tokens, 0.78× calls; ROB-19) is unchanged: no channel or floor arm.

## GANZ-03 dollars (§4.5 line 199, Appendix D.9 line 554)

The floor (`sft_plan`) now costs $0.003921, not $0.003015. A dearer floor narrows c_ceil − c_floor, so every dollar savings retained rises slightly. It still falls with depth, and every interval still excludes zero on both receivers. The tailored and zero-shot receivers carry identical dollar values, as they did before. Source: regenerated `campaign/results/j17_depth_fixes_20260924.report.json` `ganz.<bplus|zs>.<m>.savings_retained.usd`, and `figures[GANZ-03 (dollars) / COST-04]` in the ATTRIB report.

- line 199: `0.4684 of the dollar saving are retained against the cap-81 planner (GANZ-03;` → `0.4780 of the dollar saving are retained against the cap-81 planner (GANZ-03;` (GANZ-03, COSTFIX)
- line 554: `dollar savings retained 0.7058, 0.5545 and 0.4684 (GANZ-03;` → `dollar savings retained 0.7202, 0.5658 and 0.4780 (GANZ-03;` (GANZ-03, COSTFIX)
- line 554: `and [0.27, 0.62] and [0.34, 0.57] (dollars), scenario then task` → `and [0.28, 0.62] and [0.35, 0.58] (dollars), scenario then task` (GANZ-03, COSTFIX)
- Unchanged on line 554: QRec (GANZ-01/02, goal_pass), hosted-call savings retained 0.6325 / 0.4528 / 0.3605 with [0.23, 0.47] and [0.27, 0.43], and COST-04's 0.6550 [0.56, 0.76] [0.59, 0.73], 0.4292 [0.26, 0.57] [0.32, 0.52], 0.4048 and 0.6508, because COST-04's cost share has no floor (`cost_share_unchanged (COST-04)`: true).
- Other depths, for the ledger, with scenario and task intervals: m = 6 0.7202 [0.607, 0.802] [0.649, 0.775] (was 0.7058 [0.586, 0.794] [0.631, 0.764]); m = 9 0.5658 [0.396, 0.689] [0.459, 0.649] (was 0.5545 [0.382, 0.682] [0.446, 0.639]); m = 11 0.4780 [0.280, 0.623] [0.351, 0.578] (was 0.4684 [0.271, 0.617] [0.341, 0.570]).

## Not printed in the paper (ledger only)

- ROB-19's `2.12×` USD ratio [1.75, 2.57] (task [1.76, 2.54]) does not occur in the paper (`grep -c '2\.12'` = 0); attributed it is 2.27× [1.90, 2.72] (task [1.91, 2.68]) — ledger A13 only.
- `3.19×` occurs once, at line 152 (above); the D appendix does not print it (the one other match, line 446, is an interval bound −3.19).
- CHAN-PRICE-02's `28.4×` advise_fixed_k_10_fullctx and `about 2.0×` the top of P4's range, ROB-20's USD ratio 0.750× and QUAL-03's 204.5k are ledger-only; line 345 prints ROB-20's quality contrast only (−2.25 pp), which does not change.
- Line 195 (chord, UF-07 / CHORD-01) places arms on token shares with the one-plan floor's tokens, which were already charged on the plan event (j8_noncached_cost), and no channel arm: unchanged.
