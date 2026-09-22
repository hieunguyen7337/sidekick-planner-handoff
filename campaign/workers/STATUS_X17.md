# STATUS X17 — common handoff keys

Flag: `--handoff-keys-from ARM` [OBSERVED scripts/analysis/j8_frontier.py:205-214]. Omit = per-arm keys, unchanged. Unknown name is fatal and lists valid arms [OBSERVED scripts/analysis/j8_frontier.py:464-480].

JSON when the flag is set: top-level and NI/chord blocks get `handoff_keys_from` and `handoff_keys_n` (True-flag count on the pinned arm) [OBSERVED scripts/analysis/j8_frontier.py:506-511, :2505]. Each restricted row names the pin in `handoff_keys_from` / `defining_arm`; size is `n_pairs`. Default JSON has neither top-level pin field [OBSERVED hpc 25639125.aqua `DEFAULT_HAS_PIN_KEYS False False`].

## Pinned run (`--handoff-keys-from prefix_m9`, `handoff_keys_n=82`)

`goal_pass_rate` handoff-only vs `planner_alone` [OBSERVED hpc 25639125.aqua `/tmp/x17_pinned.json`]:

| arm | arm_score | reference_score | deficit pp | ci95_pp | n_pairs |
|---|---:|---:|---:|---|---:|
| prefix_m2 | 0.725341 | 0.801976 | −7.66 | [−17.3, 2.41] | 82 |
| prefix_m4 | 0.719256 | 0.801976 | −8.27 | [−18.73, 2.47] | 82 |
| prefix_m6 | 0.686159 | 0.801976 | −11.58 | [−21.54, −1.04] | 82 |
| prefix_m9 | 0.781183 | 0.801976 | −2.08 | [−11.25, 7.51] | 82 |

## prefix_m9 unpinned vs pinned

`noninferiority.arms.prefix_m9.goal_pass_handoff_only` (and `tgc_handoff_only`) equal True [OBSERVED hpc 25639125.aqua]. Both n_pairs=82, `handoff_keys_from=prefix_m9`.

## The number that matters

On the nine-step arm’s 82 keys, prefix_m6 deficit is **−11.58 pp** [−21.54, −1.04]. That is close to its own-111-key −11.70, not to prefix_m9’s −2.08 [OBSERVED hpc 25638908.aqua table; hpc 25638910.aqua unpinned m6 n=111, −11.70, arm 0.7068, ref 0.8238].

## Tests [OBSERVED tests/unit/test_j8_frontier.py]

- `test_handoff_keys_from_second_arm_uses_pinned_set` :1075
- `test_handoff_keys_from_pinned_arm_rows_unchanged` :1113
- `test_omitting_handoff_keys_from_matches_unpinned` :1153
- `test_unknown_handoff_keys_from_raises_with_valid_names` :1177
- `test_n_pairs_equals_pinned_key_set_size_on_restricted_rows` :1199

## Suite [OBSERVED hpc 25638903.aqua]

```
506 passed, 1 skipped, 1 warning in 35.49s
```

Five new tests on a 501+1 baseline; did not fall. JSONs written to `/tmp` inside the PBS jobs, not `campaign/results/`. No commit, no qsub, no GPU.
