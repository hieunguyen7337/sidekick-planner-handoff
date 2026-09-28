# Cost Axes Analysis Report (Brief X40 Unit A)

- **Prices Card**: `configs/cost/prices_2026-09.yaml`
- **Cluster**: `scenario`
- **Ordering Stable Across Axes**: `NO`
- **Non-Inferiority Unchanged Across Axes**: `NO`

## Arm Cost Summary by Axis

| Arm | Non-cached Tokens | Provider USD ($) | Hosted Calls | Local GPU USD (Assump.) |
| --- | ---: | ---: | ---: | ---: |
| `executor_alone` | 0.0 | $0.0000 | 0.00 | null |
| `executor_alone_bplus` | 0.0 | $0.0000 | 0.00 | null |
| `sft_plan` | 22883.2 | $0.0037 | 1.00 | null |
| `planner_alone_cap81` | 1001288.2 | $0.0457 | 16.20 | null |
| `prefix_m9` | 343438.2 | $0.0222 | 9.77 | null |
| `prefix_m11` | 421881.4 | $0.0258 | 11.09 | null |
| `prefix_zs_m9` | 343438.2 | $0.0222 | 9.77 | null |
| `prefix_zs_m11` | 421881.4 | $0.0258 | 11.09 | null |
| `advise_k1_fullctx` | 1756986.6 | $0.0681 | 19.96 | null |
| `advise_k10_fullctx` | 82644.2 | $0.0085 | 2.89 | null |
| `takeover_k10` | 70154.4 | $0.0076 | 2.66 | null |
| `show_k10` | 76111.7 | $0.0081 | 2.82 | null |
| `advise_k10_neutral` | 69008.1 | $0.0082 | 2.72 | null |

## Ordering by Axis (Lowest Cost First)

- **noncached_tokens_per_episode**: `executor_alone` < `executor_alone_bplus` < `sft_plan` < `advise_k10_neutral` < `takeover_k10` < `show_k10` < `advise_k10_fullctx` < `prefix_m9` < `prefix_zs_m9` < `prefix_m11` < `prefix_zs_m11` < `planner_alone_cap81` < `advise_k1_fullctx`
- **usd_per_episode**: `executor_alone` < `executor_alone_bplus` < `sft_plan` < `takeover_k10` < `show_k10` < `advise_k10_neutral` < `advise_k10_fullctx` < `prefix_m9` < `prefix_zs_m9` < `prefix_m11` < `prefix_zs_m11` < `planner_alone_cap81` < `advise_k1_fullctx`
- **hosted_calls_per_episode**: `executor_alone` < `executor_alone_bplus` < `sft_plan` < `takeover_k10` < `advise_k10_neutral` < `show_k10` < `advise_k10_fullctx` < `prefix_m9` < `prefix_zs_m9` < `prefix_m11` < `prefix_zs_m11` < `planner_alone_cap81` < `advise_k1_fullctx`

## Ordering Flips

- Swap between `noncached_tokens_per_episode` (advise_k10_neutral < takeover_k10) and `usd_per_episode` (takeover_k10 < advise_k10_neutral)
- Swap between `noncached_tokens_per_episode` (advise_k10_neutral < show_k10) and `usd_per_episode` (show_k10 < advise_k10_neutral)
- Swap between `noncached_tokens_per_episode` (advise_k10_neutral < takeover_k10) and `hosted_calls_per_episode` (takeover_k10 < advise_k10_neutral)
- Swap between `usd_per_episode` (show_k10 < advise_k10_neutral) and `hosted_calls_per_episode` (advise_k10_neutral < show_k10)

