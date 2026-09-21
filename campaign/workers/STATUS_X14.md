# STATUS_X14 — handoff-only population

State: **done**. No commit, no `qsub`, no GPU, no `src/`/`configs/`/`scripts/pbs/` edits. JSON at `/tmp/x14.json` on the compute node (job 25614365.aqua). Six-step arm `25596786` stayed Running; not added.

## Population

Name: **`handoff-only`**. Definition: shared `(task_id, seed)` keys where the **comparison arm** `report` payload has `handoff_occurred is True`. Scoring is all-episodes (crash = 0). Missing (`None`) is neither this nor the complement. Complement name: **`no-handoff`** (`handoff_occurred is False`). [OBSERVED scripts/analysis/j8_frontier.py:106-107, :416, :432, :954]

Reference and floor are **not** subset on their own flags. `restrict_to_defining_handoff` takes keys from the comparison arm, then keeps only those keys in every arm in the contrast [OBSERVED :432]. `n_pairs` is on every NI and chord row.

Existing `all-episodes` / `survivors` keys unchanged; this is an addition on NI and chord only [OBSERVED :1796, :2006].

## prefix_m9 `goal_pass_rate` vs `planner_alone` [OBSERVED hpc 25614365]

```
pop            n_pairs  arm     ref     diff_pp  ci95_pp           holds
all-episodes      114  0.8134  (pool)   -1.50   [-8.1, 5.62]      False
survivors         114  0.8134  (pool)   -1.50   [-8.1, 5.62]      False
handoff-only       82  0.7812  0.8020   -2.08   [-11.25, 7.51]    False
no-handoff         32  0.8961  0.8961    0.00   [0.0, 0.0]        True
```

Arm means: `goal_pass_all=0.813439`, `goal_pass_handoff_only=0.781183`, `goal_pass_no_handoff=0.896094`; `hand_all=0.7193` (82/114). Complement TGC also identical to the planner (0.7500 vs 0.7500).

**Yes: the reference scores far higher on the complement** than on handoff-only (0.8961 vs 0.8020, gap 9.41 pp ≥ 5 pp reporting threshold). JSON note says the pooled hybrid mixes planner-like scores on easy no-handoff tasks with hybrid scores on the rest. [INFERRED threshold `REFERENCE_FAR_HIGHER_PP=5.0` at :113]

Self-check: `prefix_m2` / `prefix_m4` handoff rate 1.0; `goal_pass_handoff_only` equals `goal_pass_all`; NI `handoff-only` `n_pairs=114` matches all-episodes.

## Tests [OBSERVED tests/unit/test_j8_frontier.py:877, :894, :936]

`test_handoff_only_uses_defining_arm_keys_and_restricts_reference`, `test_full_handoff_population_matches_all_episodes`, `test_no_handoff_complement_carries_reference_score`.

## Suite [OBSERVED hpc 25614364.aqua]

```
501 passed, 1 skipped, 1 warning in 35.42s
```
