# R4b — re-cite the post-mortem's "Repairs Landed" section against the real code

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## The problem

You wrote the section **"### Repairs Landed on 2026-09-20 (R1, R2)"** in `docs/FOLLOWUPS.md`.
Every one of its seven items cites a **brief file** — `campaign/workers/brief_R1_hj8_port.md`,
`campaign/workers/brief_R2_b1_gate.md` — as its `[OBSERVED ...]` evidence. Those briefs are
*instructions*, not code. When you wrote the section the repairs had not landed yet, so the
document asserted that a repair exists on the strength of a document asking for it. That is a
citation to intent, and it is exactly the failure this project's `[OBSERVED]` convention exists
to prevent.

The repairs **have now landed**. Your job is to re-cite the section against the code, and to
correct anything that turns out not to match what was actually built.

## Scope — files you own

- `docs/FOLLOWUPS.md` — only the "Repairs Landed on 2026-09-20 (R1, R2)" section
- `README.md` — one sentence, see below
- `campaign/workers/STATUS_R4.md` — append what you did

Touch nothing else. Do not run git, do not commit, do not submit any job.

## What to do

1. For each of the seven repair items, **open the file named and verify the claim**, then replace
   the brief citation with a real `[OBSERVED <path>:<line>]`. Starting points found already:
   - `resolve_executor_base_url` at `src/sidekick/runner.py:153`, used at `:176`, recorded into
     the manifest at `:281`
   - process-group kill at `scripts/pbs/hj8_frontier.pbs:357` and `scripts/pbs/b1_pilot.pbs:552`
   - `trap kill_vllm EXIT` at `scripts/pbs/hj8_frontier.pbs:371` and `scripts/pbs/b1_pilot.pbs:564`
   - the missing-alias FATAL at `scripts/pbs/hj8_frontier.pbs:457`
   - the three smoke-gate FATALs at `scripts/pbs/b1_pilot.pbs:293`, `:299`, `:305`
   - `branch_live_planner_calls` charging at `scripts/setup/branch_counterfactual.py:949-951`,
     written onto the row at `:1029`
   - the per-job port helper in each `.pbs` — find it yourself and cite it
   Verify each line actually says what the claim says. **If an item does not match the code, fix
   the claim to describe what was really built, rather than keeping the tidy version.**
2. Add one short sentence to that section recording the **one behaviour change the repair made
   that goes beyond the stated fix**: the budget cap no longer filters on `is_done_row`, so a
   branch that crashes with no result at all is now charged the unknown-cost factor of 81 rather
   than contributing zero. This is faithful to §8 of the pre-registration, and it makes the cap
   stricter than before; a run with many hard crashes will reach the cap sooner and need the §9
   resume. It belongs in the record.
3. `README.md`: you changed the Status section to say the project "is currently executing the J8
   dev frontier evaluation and the B1 clean counterfactual pilot". Nothing is executing — those
   runs have not been submitted. Correct it to say the harness repairs are complete and those two
   campaigns are the next submissions.

## Constraints

- `aquarius01` is a login node — steering only. You need nothing heavier than `grep`, `sed -n`
  and `ls`; put `timeout` on each. No python, pip, tar, rsync.
- `docs/prereg_b1_pilot.md` is frozen. Do not edit it.
- Do not commit, do not run git, do not touch any result tree.

## Return contract

Report in eight lines or fewer: each of the seven items with the real citation you gave it, and
**explicitly name any claim that did not survive verification** and what you replaced it with.
That is the valuable part of this unit.
