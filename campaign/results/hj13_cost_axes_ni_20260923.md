# Cost Axes Analysis Report (Brief X40 Unit A)

- **Prices Card**: `configs/cost/prices_2026-09.yaml`
- **Cluster**: `scenario`
- **Ordering Stable Across Axes**: `NO`
- **Non-Inferiority Unchanged Across Axes**: `YES`

## Arm Cost Summary by Axis

| Arm | Non-cached Tokens | Provider USD ($) | Hosted Calls | Local GPU USD (Assump.) |
| --- | ---: | ---: | ---: | ---: |
| `executor_alone` | 0.0 | $0.0000 | 0.00 | null |
| `plan_only` | 23905.6 | $0.0030 | 1.00 | null |
| `advise_k10_starved` | 43823.4 | $0.0044 | 2.42 | null |
| `advise_k3_starved` | 204499.8 | $0.0122 | 6.82 | null |
| `advise_k10_fullctx` | 49819.4 | $0.0055 | 2.46 | null |
| `takeover_k10` | 41463.7 | $0.0048 | 2.32 | null |
| `prefix_m6` | 221043.1 | $0.0163 | 6.98 | null |
| `prefix_m9` | 357448.4 | $0.0227 | 9.77 | null |
| `prefix_m11` | 443361.4 | $0.0265 | 11.25 | null |
| `ceiling_cap25` | 684453.3 | $0.0355 | 14.43 | null |
| `ceiling_cap81` | 1160215.1 | $0.0482 | 17.35 | null |

## Ordering by Axis (Lowest Cost First)

- **noncached_tokens_per_episode**: `executor_alone` < `plan_only` < `takeover_k10` < `advise_k10_starved` < `advise_k10_fullctx` < `advise_k3_starved` < `prefix_m6` < `prefix_m9` < `prefix_m11` < `ceiling_cap25` < `ceiling_cap81`
- **usd_per_episode**: `executor_alone` < `plan_only` < `advise_k10_starved` < `takeover_k10` < `advise_k10_fullctx` < `advise_k3_starved` < `prefix_m6` < `prefix_m9` < `prefix_m11` < `ceiling_cap25` < `ceiling_cap81`
- **hosted_calls_per_episode**: `executor_alone` < `plan_only` < `takeover_k10` < `advise_k10_starved` < `advise_k10_fullctx` < `advise_k3_starved` < `prefix_m6` < `prefix_m9` < `prefix_m11` < `ceiling_cap25` < `ceiling_cap81`

## Ordering Flips

- Swap between `noncached_tokens_per_episode` (takeover_k10 < advise_k10_starved) and `usd_per_episode` (advise_k10_starved < takeover_k10)
- Swap between `usd_per_episode` (advise_k10_starved < takeover_k10) and `hosted_calls_per_episode` (takeover_k10 < advise_k10_starved)

