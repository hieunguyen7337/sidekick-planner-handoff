# W-10 independent recount

The raw snapshot contained 1,527 dev lines and 1,399 train lines; all lines parsed as JSON
objects. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:3-6]

The 21 keys found in both files were `actual_gpr`, `actual_solved`, `branch_error_type`,
`branch_gpr`, `branch_gpr_local`, `branch_seed`, `branch_solved`, `branch_steps`, `campaign`,
`condition`, `correction`, `i`, `key`, `n_later_reviews`, `replay_k`, `review_every_k`,
`run_id`, `sampling_seed`, `seed`, `step`, and `task_id`. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:7-8]
The same run used literal `grep -c` checks for every listed key: each key occurred 1,527 times
in dev and 1,399 times in train. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:38-81]

I used `branch_gpr` as the treated/untreated goal-pass value and `actual_gpr` as the numeric
factual outcome. [INFERRED]

Dev had 382 intervention points. No rows were ignored for an out-of-scope branch seed or
condition. There were 374 complete points and 8 dropped points: 1 for a missing expected cell
and 7 for null `branch_gpr`; there were no duplicate expected cells. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:9-19]

The train band used 347 points with both non-null treated samples and the 75th percentile with
linear interpolation: `band = 0.166000`. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:12-15]

Using the strict inequalities in the brief (`delta > band`, `delta < -band`, otherwise
ambiguous), the complete dev points were: [INFERRED] [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:20-23]

| label | count | fraction | mean delta |
|---|---:|---:|---:|
| needed | 59 | 0.157754 | 0.342686 |
| needless | 53 | 0.141711 | -0.356472 |
| ambiguous | 262 | 0.700535 | 0.004672 |

All table entries are observed in the recount output. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:20-23]

The overall mean delta was `0.006817`. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:20-23]

The factual outcome was missing for 0 complete points; 81 of 374 lay outside the treated
interval `[min(treated), max(treated)]`, a fraction of `0.216578`. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:24-27]

For split-half agreement over the 374 complete points, Pearson `r = 0.163962` and Spearman
`rho = 0.222022`. Among the 84 points where both deltas were nonzero, 59 had the same sign,
fraction `0.702381`. [OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:28-33]

There were 124 points with `|d101| > band`, 108 with `|d102| > band`, and 56 with both. Under
independence using the observed marginal rates, the expected both count was `35.807487`.
[OBSERVED /tmp/hpc-w10-spool/20260917-224425-10.out:34-37]
