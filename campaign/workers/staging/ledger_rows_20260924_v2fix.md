# Draft ledger rows: unit V2FIX, acting on the regression review of Paper A v2 (2026-09-24)

These rows use `docs/claims_ledger.md`'s column format (claim_id | claim | artifact path | JSON key or line |
status | figure). Two correction notes follow them. Everything here is dev data only. The paper
(`paper/preprint_dev_v2_20260924.md`) cites each new row with a `[[NEEDS LEDGER: <id>]]` marker. Where a count
is still missing, the marker stands in its place. Once the row is appended, replace the marker with the id,
and with the count where it stood for one:
- FDR-03's counts: 17 on the bootstrap p and 7 on the sign-flip p;
- HSTAR-18 and MECH-12: the marker is only the citation.

**Code.** `scripts/analysis/j17_v2_fill.py` has a new block, `by_main_text_hstar`, built by `hstar_by` and
`add_hstar_block`. There are two new options:
- `--update REPORT` keeps every key of REPORT and recomputes only the new block;
- `--paper-file` pins the paper bytes that decide main-text membership.

Tests: `tests/unit/test_j17_v2_fill.py` has 3 new tests, and the file passes 25 of 25 in PBS job 25845181.
`campaign/results/j17_v2_fill_20260924.report.json` was rewritten with `--update`. A raw `diff` against the
pre-update copy changes one line (`generated_at`) and adds one contiguous hunk (the new block). With those
two removed, the two files are identical under `jq` normalisation.

A full rebuild (PBS job 25845189, 33 s) was run against the paper snapshot that FDR-02 records: commit
6320cce, sha256 `6089ca93…`. It reproduces every top-level key, including `by_main_text` and
`by_main_text_hstar`, except `contrast_census`. The census differs only by the two report files added
since 720ab68: `j17_hstar_20260924.report.json` is now counted, and `j12_power_dev_hstar_20260924.report.json`
is excluded by name. So CENSUS-02 stays tied to the committed report, not to a fresh rebuild.

| claim_id | claim | artifact | key | status | figure |
|---|---|---|---|---|---|
| FDR-03 | **Read by h\*, FDR-02's main-text Benjamini–Yekutieli set keeps 17 of 60 on the scenario-bootstrap p (13 under the flag) and 7 on the exact sign-flip p (4 under the flag). On the bootstrap p, 6 of the 16 handoff members survive: the four silenced m6 → m11 spans, and the handoff-only `goal_pass` NI tests at tailored m11 and untailored m9. The tailored `goal_pass` handoff-only span survived under the flag and no longer does, and no other handoff-only member survives. On the sign-flip p no handoff-only member survives; the tailored silenced spans on both metrics do.** **Set.** The set is `by_main_text`'s 60 members, with membership as recorded (paper snapshot sha256 `6089ca93c467…`, commit 6320cce). The 16 handoff-split members are swapped for the same contrast split by h*, taking its value and both p from `campaign/results/j17_hstar_20260924.report.json` (HSTAR-05..08, HSTAR-11..13). They are Table 5's handoff-only and silenced m6 → m11 cells (8, flag values from HO-04..07) and Table 6's handoff-only NI cells (8, from HO-NI-01..03). The other 44 members keep their `by_main_text` p. **Why the p can be swapped.** Every swapped member's all-episode sibling has the same point, bootstrap p and sign-flip p in both reports (16 checks, `p_commensurable.all_equal` = true). BY is `cluster_inference.by_fdr`, m = 60, α 0.05 [OBSERVED key `by_main_text_hstar.{m,n_swapped,p_commensurable}`]. **Bootstrap survivors, 17, with BY p.** H2 advise_k1 − prefix_m11 0.012034. Tailored m6 → 11: `goal_pass` all 0.00432, silenced 0.0; TGC all 0.0, silenced 0.0. Untailored m6 → 11: `goal_pass` all 0.0, silenced 0.0; TGC all 0.0, silenced 0.00432. Chord c81 tailored m11 0.018719. NI `goal_pass`, all episodes: tailored m9 0.021059, tailored m11 0.0, untailored m9 0.0, untailored m11 0.0. NI `goal_pass`, handoff-only: tailored m11 0.042945 (raw 0.0026), untailored m9 0.00432 (raw 0.0002). Narrated − executed, untailored m11: 0.0 [OBSERVED key `by_main_text_hstar.bootstrap.rows`]. **Handoff members that fail on the bootstrap p (BY p).** Handoff-only m6 → 11 spans: tailored `goal_pass` 0.213402 (raw 0.0228; under the flag, FDR-02 kept it at 0.023399), tailored TGC 0.53846, untailored `goal_pass` 0.278981, untailored TGC 0.456287. Handoff-only NI `goal_pass`: tailored m9 0.11487, untailored m11 0.144716. Handoff-only NI TGC: 1.0 for all four [OBSERVED key `by_main_text_hstar.handoff_members`]. **Changes against FDR-02, bootstrap.** Gained: the tailored and untailored `goal_pass` silenced spans, the untailored TGC silenced span, and handoff-only NI `goal_pass` at tailored m11 and untailored m9. Lost: the tailored `goal_pass` handoff-only span [OBSERVED key `changes_vs_by_main_text`]. **Sign-flip survivors, 7.** The tailored silenced spans on `goal_pass` and TGC, BY 0.044084 each. The untailored all-episode TGC span, 0.044084. It is not a handoff member: it crosses 0.05 only because the swapped p change the ranks (FDR-02: 0.061698). NI `goal_pass`, all episodes, at tailored m11, untailored m9 and untailored m11, 0.034257 each. Narrated − executed, untailored m11, 0.034257. **Other counts.** With `goal_pass` only (m = 33), 14 survive on the bootstrap p and 9 on the sign-flip p. D0, C1 at 114, CEIL-07, the D0 limit-as-0 contrast and the m11 DiD still fail. **Reproduction.** A full rebuild against the 6320cce snapshot reproduces `by_main_text` and `by_main_text_hstar` exactly (see the header). | `campaign/results/j17_v2_fill_20260924.report.json` | `by_main_text_hstar.{definition,swapped,p_commensurable,bootstrap,signflip,goal_pass_only,handoff_members,changes_vs_by_main_text}` | exploratory (multiplicity audit) | — |
| HSTAR-18 | **At m = 11, the h\* handoff-only NI contrast is exactly the flag-true episodes plus the 17 rescues, weighted by count. The `goal_pass` NI reading holds because the executor rescues the source planner's step-limit stalls. It fails over the 71 episodes in which the planner was still acting after the prefix.** **Populations.** h* handoff (n = 88) is the union of flag-true (n = 71; HO-NI-01, HO-NI-02) and live-but-unflagged (n = 17; HSTAR-02, HSTAR-14). Both contrasts are arm − `planner_alone_cap81` on the same (task_id, seed) [OBSERVED key `rescued_m11.bplus.comparison`]. **Tailored `goal_pass`.** (71 × −0.940845 + 17 × +48.294118) / 88 = +8.570455, which equals HSTAR-11's +8.570455 to 6 dp. The flag-true part is −0.94 [−9.53, +7.45] and fails; the rescued part is +48.29 [+34.15, +66.41]. **Untailored `goal_pass`.** (71 × −4.359155 + 17 × +37.735294) / 88 = +3.772727, which equals HSTAR-12. **TGC, the same identity.** Tailored: (71 × −8.450704 + 17 × +41.176471) / 88 = +1.136364. Untailored: (71 × −15.492958 + 17 × +35.294118) / 88 = −5.681818. Both equal HSTAR-13 [INFERRED: arithmetic on OBSERVED keys: `ni.{bplus,zs}.m11.{goal_pass,tgc}.handoff_only` in j17_depth_fixes (flag) and j17_hstar (h*); `rescued_m11.{bplus,zs}.summary.{goal_pass,tgc}.diff_pp`]. Descriptive only: the 17 are selected on the source planner failing (HSTAR-14). | `campaign/results/j17_hstar_20260924.report.json`; `campaign/results/j17_depth_fixes_20260924.report.json` | `ni.{bplus,zs}.m11.{goal_pass,tgc}.handoff_only`; `rescued_m11.{bplus,zs}.summary` | exploratory | — |
| MECH-12 | **MECH-05's m = 11 error rates are taken over the flag-defined handoff population. The tailored 42.59 % is 23 of 54 handoff episodes, and the untailored 61.11 % is 33 of 54. Under h\*, the m = 11 handoff population on this cap-25 source is 58 of 114 on both receivers. The rates were not recomputed over it.** **Counts.** Tailored: n_episodes 114, handoff_episodes 54, silenced_episodes 60, error_episodes 23, error_rate_on_handoff 0.4259 [OBSERVED `campaign/results/hj13_mechanism_tailored_20260923c.report.json` key `m2_compounding_error.primary.m11`]. Untailored: handoff 54, error_episodes 33, rate 0.6111 [OBSERVED `campaign/results/hj13_mechanism_zeroshot_20260923c.report.json`, same key]. **The four the report counts as silenced.** The tailored key's `divergence_keys` (= `post_complete_keys`) are 37a8675_1 seed 2, and 383cbac_2, 530b157_2 and 68ee2c9_1 at seed 1 [OBSERVED]. These are HSTAR-17's four live-but-unflagged keys, which the mechanism report counts as silenced. **h\* handoff.** 114 − 56 terminal = 58, that is 54 flag-true + 4 live-but-unflagged, on both receivers (HSTAR-17, `cap25_counts.arms.{tailored,untailored}_m11`). The rate over 58 was not computed [INFERRED: it needs the four episodes' error status]. | `campaign/results/hj13_mechanism_tailored_20260923c.report.json`; `campaign/results/j17_hstar_20260924.report.json` | `m2_compounding_error.primary.m11.{handoff_episodes,error_episodes,divergence_keys}`; `cap25_counts.arms.{tailored,untailored}_m11` | exploratory | mechanism |

## Correction note for QWEN-05 (append to its claim cell)

**A12 (2026-09-24) →** The review lists QWEN-05 as a ledger error in which the paper is right
(`docs/review_paperA_adversarial_20260923.md:148`), without naming the value. Re-checked against the report
key, the one wrong value in this cell is the one A9 already corrects:
- The m9 → m11 `goal_pass` brackets, scenario [−7.03, +1.61] and task [−8.13, +2.80], are the stored
  `m9_minus_m11` interval copied un-negated.
- The paper prints the negation: scenario [−1.61, +7.03], task [−2.80, +8.13].
- Every other interval in the cell is the correct negation of its stored key: m6 → m11 on `goal_pass` and
  TGC, and m9 → m11 on TGC [OBSERVED `campaign/results/hj15_qwen_curve_20260923.report.json` keys
  `contrasts.{goal_pass_all,tgc_all}_qwen_prefix_m{6,9}_minus_qwen_prefix_m11.{diff_pp,ci95_pp_scenario,ci95_pp_task}`].

Cite the A9 values. No other value changes.

## Correction note for NARR-04 (append to its claim cell)

**A12 (2026-09-24) →** The review lists NARR-04 as a ledger error in which the paper is right
(`docs/review_paperA_adversarial_20260923.md:148`). The error is in the untailored narrated m9 → m11 step
that this cell quotes, "+0.10 pp, scen [−5.14, +4.75]". It pairs the negated point with the un-negated
interval:
- The stored key `goal_pass_all_narrated_m9_minus_narrated_m11` is −0.10, scenario [−5.14, +4.75], task
  [−5.24, +5.01] [OBSERVED `campaign/results/hj16_narrated_curve_zs_20260923.report.json`].
- So m9 → m11 is +0.10 pp, scenario [−4.75, +5.14], as NARR-03 and the paper print, and task [−5.01, +5.24]
  (NARR-06).

The rest of the cell was re-checked against `campaign/results/hj16_narrated_curve_bplus_20260923.report.json`
and the zs report:
- the tailored same-depth gaps on both metrics;
- the tailored m6 → m9, m9 → m11 and m6 → m11 rises;
- narrated m11 − executed m6;
- the untailored NI lower bounds.

Each matches its key in the printed orientation. Separately, the cell's reading that tailored narration
matches execution "at ALL THREE depths" is narrowed by NARR-06: tailored NI at m = 9 and the tailored
m9 → m11 rise do not survive task clustering.
