# R7 — record the 2026-09-20 smoke findings in RUNS.md, before the full-scale data exists

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation unit. Change no code, run no jobs, submit nothing, do not run git.

**Timing matters.** The ten-arm dev frontier run and the B1 pilot were submitted minutes ago
(jobs `25560358`, `25560363`, `25560367`). This entry must state what was known **before** any of
their results exist, so that a reader can see the degeneracy was predicted and recorded in
advance rather than discovered afterwards and rationalised.

## Files you own

- `campaign/RUNS.md` — append one new section
- `campaign/workers/STATUS_R7.md` — what you verified

Touch nothing else. `docs/prereg_b1_pilot.md` is frozen.

## The facts to record (verify each against the logs before writing it)

Source logs:
- `campaign/workers/logs/hj8_frontier_live_20260920livesmoke.25558685.aqua.out`
- `campaign/workers/logs/b1_pilot_train_20260920c.25559748.aqua.out`

### 1. Both smokes passed, in parallel, on separate ports

The two jobs ran simultaneously on GPU nodes and chose ports 38685 and 39748 independently. Each
verified that its own expected LoRA alias was present in its server's model list and that its own
process group held its port. This is the repair for the 2026-09-19 collision, tested under exactly
the condition that caused it. J8 exited `job_rc=0` with all ten arms passing their gates; B1
exited `smoke_rc=0`.

### 2. The B1 smoke, and what it says about the budget counter

```
n_rows=32 live_planner_calls_sum=44 branch_planner_calls_tick_sum=165
planner_tokens_sum=1343501 error_type_counts=None=17,limit=15
```

Record the ratio explicitly: **44 live calls against 165 replayed ticks, a factor of 3.7**. The
pre-registration budgets 6,118 live calls against a 10,000 cap. Under the old replay-inclusive
counter that cap would have fired at roughly 2,700 live calls, less than half the expected spend.
The earlier estimate in the post-mortem was "around 6,000"; this measurement says the problem was
worse than estimated. Say so.

Also record that 15 of 32 branches ended at the step limit and 17 ended cleanly, with zero
infrastructure faults, which is why a gate that failed on any non-null error type could never
have passed.

### 3. The smoke escalation table — the finding that matters

Reproduce this table from the J8 log, and label it as three episodes per arm:

```
arm                    | live_planner_calls | n_interventions | steps_mean
hj8_fixed_k_3          | 14 | 14 | 14.33
hj8_fixed_k_5          | 16 | 16 | 28
hj8_fixed_k_10         |  5 |  5 | 21.67
hj8_router_seq_tau03   | 33 | 33 | 11
hj8_router_seq_tau05   |  0 |  0 | 16.33
hj8_router_seq_tau07   |  0 |  0 | 11
hj8_sidekick_tau03     |  0 |  0 | 12.67
hj8_sidekick_tau05     |  0 |  0 | 20
hj8_sidekick_tau07     |  0 |  0 | 33
hj8_oracle_escalation  |  0 |  0 | 30
```

Three conclusions to state plainly:

**(a) All three `sidekick` arms escalate zero times, and this was predicted from the training
data, not discovered here.** The `sft_b_plus` adapter contains no ASK targets by construction, and
the self-gate can only veto an ASK the executor already emitted, never create one, so lowering the
threshold cannot raise the ask rate. The historical base rate of the untrained ask channel is 0
asks in 114 episodes and 1 ask in 114 episodes in two earlier campaigns. The job's own
`WARN: every sidekick arm in this smoke pass has identical live_planner_calls=0` fired
automatically.

**(b) `router_seq` is close to all-or-nothing.** At τ=0.3 it fires 33 times over three episodes,
more per episode than any fixed schedule; at τ=0.5 and τ=0.7 it never fires. Every router score
therefore lies in [0.3, 0.5), so two of the three pre-specified thresholds cannot produce a
frontier point. Note as a follow-up that intermediate thresholds between 0.3 and 0.5 would be
needed to trace the router's curve, and that this is an **addition** to the grid, not a
substitution for it.

**(c) The oracle arm's zero is consistent with label sparsity, not a defect.** The inlined oracle
labels cover 106 task/seed pairs, of which **28 have at least one oracle step (26.4%)**, for 43
oracle steps in total. Three episodes drawing none has probability near 0.40 under that rate.
State that this was checked rather than assumed. Also note that 8 of the expected 114 pairs have
no key at all, which is not the same as an empty list.

### 4. The decision taken, and why

All ten arms were submitted unchanged. Record the reasoning: the plan's contingency for a
degenerate gate says to record the finding and run; the zero-escalation arms consume no planner
quota, so their only cost is GPU time; a 114-episode zero is stronger evidence for the negative
result than a three-episode zero; and revising a pre-specified threshold grid after seeing smoke
data is the kind of post-hoc change this campaign has otherwise avoided.

Record the consequence honestly: **with this adapter, the executor-internal ask hypothesis is not
being tested by these arms.** They measure a veto on a channel that never opens. Testing it
requires the ASK-trained adapter, which is not trained, and which is gated on the B1 pilot.

## Constraints

- `aquarius01` is a login node — steering only. You need nothing heavier than `grep`, `sed -n`,
  `ls`; `timeout` on each. No python, pip, tar, rsync.
- Do not commit, do not run git. Read result trees read-only; never write under
  `/scratch/.../results/`. Do not read `test_normal` or `test_challenge` data.

## Return contract

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. If any figure above does not hold up
in the logs, **say so rather than writing it**. Final report, eight lines or fewer: the section
added, and any number that failed verification.
