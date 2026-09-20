# STATUS C2 — H3 filler ticks

**Unit:** C2 — `scripts/analysis/j8_frontier.py`, `tests/unit/test_j8_frontier.py`
**State:** done
**Last update:** 2026-09-20

## Owned files

- `scripts/analysis/j8_frontier.py`
- `tests/unit/test_j8_frontier.py`
- this STATUS
- `campaign/results/hj8_frontier_dev_20260920.report.json`

No `.pbs`, no `qsub`, no git, no writes under `/scratch/.../results/`.

## Cause [OBSERVED hpc 25567759.aqua]

Oracle labels: 106 keys; 8 ticks × 106 = 848. On every labelled episode of all six gated arms, `max(gate_scores_from_events)` equals `result.json` `steps`. Missing grid slot agrees with `tick > steps` at rate **1.0** (448/448, 452/452, 455/455, 579/579, 463/463, 443/443). Within-lifetime missing slots: 0. Slots after `steps`: 0. The filler-tick fix is complete. [OBSERVED hpc 25567759 stdout]

## What changed [OBSERVED scripts/analysis/j8_frontier.py]

H3 reports `scored` (primary: `tick <= steps`) and `grid` (published 5..40 filler=0.0). Top-level `auroc`/`ece`/`n`/`n_positive` are scored. `n_escalations`/`degenerate` unchanged in meaning. AUROC-vs-0.5 disagreement prints `CONTRAST DISAGREEMENT`. Real `p_ask` quantiles in `h3_score_quantiles`. JSON labels: `h3_headline_population`, `h3_populations`.

## Final report (≤10 lines)

1. Agreement rate missing-slot ≡ `tick > steps` is 1.0 on all six gates; 0 within-lifetime misses. [OBSERVED hpc 25567759]
2. H3 scored/grid AUROC (n, n_pos, excl): router_seq_tau03 0.5082/0.6294 (269/848, 24/43, 579); tau05 0.4971/0.4988 (385/848, 36/43, 463); tau07 0.5000/0.5000 (405/848, 33/43, 443); sidekick_tau03 0.4332/0.5983 (400/848, 30/43, 448) FLAG; tau05 0.3867/0.6311 (396/848, 34/43, 452) FLAG; tau07 0.4407/0.6759 (393/848, 36/43, 455) FLAG. esc 1533/12/0/0/0/0. [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json key "h3"]
3. p_ask quantiles: router all n=0; sidekick_tau03 n=400 mean=0.004066 min=0 med=0.000924 p90=0.012681 p95=0.016744 p99=0.027147 max=0.034705; tau05 n=396 mean=0.004105 min=0 med=0.001315 p90=0.013045 p95=0.016407 p99=0.019418 max=0.023414; tau07 n=393 mean=0.004160 min=0 med=0.001262 p90=0.012861 p95=0.018485 p99=0.023507 max=0.024001. [OBSERVED same file key "h3_score_quantiles"]
4. Quality numbers unchanged: quality snapshot sha256 `1372fcad0fbf2df142c17769547fab2bef44c044d82d939f78539594543e2876` identical before vs after (arms tgc/gp/calls, contrasts diffs/CIs, f1, frontier, oracle_headroom); §10 table matches (e.g. sidekick_tau07 tgc_all 0.3947). Only `h3` plus new `h3_*` keys differ. [OBSERVED campaign/RUNS.md:2255] [OBSERVED campaign/results/hj8_frontier_dev_20260920.report.json]
5. Tests [OBSERVED tests/unit/test_j8_frontier.py]: (1) early end scored n=2 grid n=8 excl=6 :426; (2) grid AUROC>0.5 scored=0 flagged CONTRAST DISAGREEMENT :456; (3) steps=40 populations coincide, no disagreement :486; (4) no p_ask ask-tick stays in scored AUROC=1.0 :507; (5) known [0.1,0.2,0.3,0.4] p90=0.37 in table :531.
6. Suite [OBSERVED hpc 25567991.aqua]: `442 passed, 1 skipped, 1 warning in 38.55s` (437+5). J8-only: 20 passed [OBSERVED hpc 25567955]. Report rewrite [OBSERVED hpc 25568045].
