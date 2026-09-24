# Unit ANA: dev analyses prompted by the planning literature, plus the high-effort ceiling (D3)

Read `campaign/workers/briefs/20260924_common_rules.md` first. It binds this unit, with **one change**: you write
directly into the plan worktree `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15` (WT).
**Do not commit, `git add`, stash, or qsub anything except `hpc` jobs.** Other units are editing `src/`,
`scripts/pbs/`, `configs/`, `paper/` and `scripts/analysis/j12_*`; you create only the files named below.
**Dev data only.** Never read `test_normal`/`test_challenge`, never any `j10_*`/`j11_*`/`j12_*` campaign.

## Deliverables
- `scripts/analysis/j17_planning_lit.py`: pure functions + CLI, dev-only guard like
  `scripts/analysis/j17_review_fixes.py` (copy its held-out refusal). Reuse `cluster_inference.py`
  (paired cluster bootstrap, scenario primary, task secondary, 10,000 draws, seed 20260924) and the result/event
  readers other j17/j16 scripts already use. Crash = `error_type == "crash"` only, dropped; `limit` is scored.
- `tests/unit/test_j17_planning_lit.py`: synthetic fixtures with hand-computed answers for every function.
- `campaign/results/j17_planning_lit_20260924.report.json`, produced by running the CLI through `hpc`.
- `campaign/workers/staging/ledger_rows_20260924_planning.md`: draft ledger rows in the exact column format of
  `docs/claims_ledger.md` (id | claim | file | key | status | family), status `exploratory`, every number at full
  precision **and** its printed form, as rows COST-04 and NOOP-01 do. Ids must not collide with existing ones
  (`grep -o '^| [A-Z0-9-]*' docs/claims_ledger.md`). Do not edit the ledger itself.

## A. Tailoring x plan (id family PLANTAX-*)
Question: does an external plan help a plan-trained executor more than an untrained one, and does that tailoring
advantage vanish when the planner's help arrives as executed actions instead of a plan?
Arms (verify each campaign's arm dir, seeds and adapter from `run_start`; report [OBSERVED]):
- tailored executor alone `hj8_executor_alone_bplus_20260919`; tailored + one luna plan
  `hj8_sft_plan_bplus_20260921iaware`;
- base executor alone `hj1r_exec8b_20260916/executor_alone`; base + one plan `hj1r_prompt_only_20260916/prompt_only`;
- action channel at m = 6 / 9 / 11: tailored `hj12_prefix_m{6,9,11}_20260923`, untailored
  `hj13_prefix_zs_m{6,9,11}_20260923` (confirm these are the campaigns behind ledger TAILOR-01/04/07).
Contrasts, paired on the intersection of (task_id, seed) keys non-crashed in every arm used, goal_pass and TGC:
1. plan gain tailored = sft_plan_bplus - exec_alone_bplus; plan gain base = prompt_only - exec_alone_base;
   **DiD1** = tailored gain - base gain.
2. tailoring gap given a plan G_plan = sft_plan_bplus - prompt_only_base; given m actions G_act(m) =
   prefix_m(tailored) - prefix_zs_m; **DiD2(m)** = G_plan - G_act(m) for m = 6, 9, 11.
3. If the zero-shot Qwen3-8B floor pair behind ledger QWEN-03 exists, its plan gain as a third point
   (no DiD needed).
**Provenance caveat (must travel with every row):** for each campaign record the git sha / date from its run
manifest or `run_start`, and whether its plan was replayed from `hj1b_planner_20260915` packets or produced live.
If the base and tailored plan arms did not receive the same plans, say so in the row.

## B. Termination census, Fan-comparable (id family TERM-*)
Fan et al. (arXiv 2609.20804) report a weak executor without a plan stopping before acting. Classify every
non-crashed episode of each arm below from `events.jsonl` + `result.json`:
`no_handoff` (prefix arms only: `handoff_occurred` false), `stopped_before_acting` (episode ended with zero
executor actions executed; for prefix arms count only actions after the handoff), `limit` (`error_type ==
"limit"`), `completed_after_acting`, `other` (parse_error etc.). Define "executor action" from the event schema
and cite the loop code that writes it [OBSERVED src/sidekick/systems/loop.py:line]. Per arm: counts, shares with
scenario and task intervals, median steps, median executor actions.
Arms: `dev_noop_complete_20260924`; base and tailored executor alone; base prompt_only; tailored sft_plan (iaware);
`hj12_advise_fixed_k_10_fullctx_20260923`; `hj12_takeover_fixed_k_10_20260923`; the B2 neutral-advice and show
arms (find their campaigns via ledger DEC-01..06); the cap-81 pooled prefix family
`hj17_prefix_c81_{bplus,zs}_m{6,9,11}_20260923` + `hj18_prefix_c81s3_{bplus,zs}_m{6,9,11}_20260924`; the Qwen
floor arms behind QWEN-03; planner alone cap 81 (medium, the campaign behind ledger CEIL-07 / HO-NI rows) and
`dev_planner_alone_cap81_high_20260924`.

## C. The high-effort ceiling, D3 (id family CEILHI-*)
`dev_planner_alone_cap81_high_20260924`: luna planner alone, cap 81, `reasoning_effort: high`, dev seeds 1, 2,
114 episodes, 0 crashed, 4 limit (Claude's count). Against the medium-effort cap-81 planner-alone campaign on the
same (task, seed) keys:
1. paired high - medium, goal_pass and TGC, both clusterings; limit rates of each;
2. per-episode mean hosted calls, input / cached / output tokens and USD (prices from `configs/cost/prices_2026-09.yaml`
   via the repo's existing cost code), with intervals for the high/medium ratio;
3. **exploratory re-reading of non-inferiority**: `high_ceiling - arm` for the cap-81 prefix m = 11 arms (both
   receivers, seeds 1-2 only, since D3 has no seed 3), goal_pass and TGC, scenario and task, against the registered
   7.00 pp margin (NI holds when the upper bound < +7.00). Do not re-label anything registered; these rows are
   exploratory and say that the prefixes replay the *medium*-effort planner.

## Report (<= 450 words)
The headline numbers of A, B, C with intervals; the provenance caveats found; test count and PBS job ids; the list
of drafted row ids. Tag every claim [OBSERVED path:line or key] / [INFERRED].
