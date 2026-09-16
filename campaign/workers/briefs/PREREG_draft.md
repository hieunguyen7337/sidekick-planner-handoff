# Unit PREREG — draft `docs/prereg_v1.md`

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Goal

Write **one new file**, `docs/prereg_v1.md`: the preregistration for HJ-7, the single run that
produces this project's headline numbers. It is a **DRAFT** — it freezes only after the DPO
milestone (HJ-6) reports. Mark it clearly as a draft at the top, with a "frozen on: ____" line left
blank and a short list of exactly which fields are still open.

The purpose of a prereg is that the analysis is chosen before the data exists. So write the analysis
plan as if the results were already in and you could not see them.

## Files in scope

- `docs/prereg_v1.md` — new, the only file you create or modify.

Read for source material, modify nothing: `docs/PLAN.md`, `docs/HEAVY_JOBS.md` (especially the HJ-7
section), `campaign/RUNS.md` (the HJ-1 gate verdict, the correction note about the executor prompt,
and the "HJ-1R + HJ-1.5 decision rules" section at the end), `campaign/results/hj7_power.json` and
`campaign/results/hj7_power_mixture.json`, `scripts/setup/hj1_gate.py`, `scripts/setup/hj7_power.py`.

## What the document must contain

1. **The claim being tested**, stated so it could fail. The project's thesis: a small executor
   specialised to a frozen hosted planner (`sidekick`) matches the planner-driven baseline's task
   quality at materially lower planner cost. Write the primary hypothesis as a **non-inferiority**
   claim on task goal completion (TGC) plus a **superiority** claim on frontier cost/quality, and say
   which is primary.
2. **The design, with the numbers already decided** (do not re-derive them, cite them):
   - split `test_normal`, **168 tasks**, six systems: `planner_alone`, `executor_alone`,
     `prompt_only`, `fixed_k`, `sft_plan`, `sidekick`.
   - **N = 3 seeds**, **ε = 7 pp**, one-sided 95% paired non-inferiority.
   - Justify both from `hj7_power.json`: measured seed discordance **28.07%**; smallest margin
     resolvable at ≥80% power is **7 pp at N=3**, unchanged at N=4 and N=5; ε=5 pp reaches only
     0.591 power at N=3 and 0.809 at N=5. State plainly that **more seeds would not help** because
     the binding constraint is the number of tasks, and report the pessimistic
     (`--correlation-model mixture`) result as a sensitivity: it resolves only 10 pp even at N=5.
3. **The primary metric and the exact test.** TGC per (task, seed), aggregated per task over seeds,
   paired by `task_id` across systems, 10,000-resample paired bootstrap — the procedure already in
   `scripts/setup/hj1_gate.py`. Name the file and function, so the analysis is a rerun of existing
   code and not a fresh choice.
4. **Secondary metrics**, each with its direction stated in advance: SGC, planner calls per episode,
   planner tokens, frontier cost per solved task, ASK rate, and the fraction of ASKs the verifier
   gated.
5. **The controls, and what each one rules out.** In particular `sft_b_plus`: trained on identical
   data to `sidekick` with every ASK target replaced by the post-correction action, so `sidekick`
   vs `sft_plan(sft_b_plus)` differs **only in the ASK channel and not in data volume**. Without it,
   any gain could be more training data rather than learned escalation. State that explicitly.
6. **Stopping and exclusion rules, written before the run**: what counts as a broken run, when a run
   is retried rather than dropped, the `api_error + timeout ≤ 5%` quota-stall rule, and the
   commitment that no arm is re-run after its numbers are seen.
7. **What has already been decided by earlier gates, and what remains open.** Open items to list:
   the DPO λ (chosen on the dev frontier at HJ-6), the verifier threshold (calibrated on dev), and
   whether the executor is granite-4.2-8b or Qwen3-8B (decided by the HJ-1.5 probe).
8. 🔺 **A short, honest "threats to validity" section.** It must include: HJ-1's executor baselines
   were measured under a prompt that hid the executor's own actions and are being re-measured
   (HJ-1R); `planner_alone` was truncated by a 25-call cap on 10.5% of HJ-1 episodes, so 0.684 is a
   floor; and dev is the split every prompt and threshold was tuned on. Do not soften these.

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pip`, `qsub`, or any multi-minute command.**
  Write the document only.
- Every number you state must come from a file in this repo — cite it as `path:line` or by the JSON
  key you read. **Do not invent a figure to make a sentence work**; if something is not yet
  measured, write `TBD (from <which job>)`.
- Prose in the style of the existing docs: direct, explanatory, saying *why* a choice was made.
  No bullet-point-only sections, no filler, no restating the brief.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract (under 20 lines)

- The path written and its section headings.
- Every number you cited, with its source file and key.
- The list of fields you left TBD and which job resolves each.
- Anything in the source documents that contradicted something else — say so rather than picking one.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
