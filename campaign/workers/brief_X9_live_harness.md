# Brief X9 — the harness for the live channel arms, and two recorded hazards

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Two GPU jobs are queued or running and another worker is editing `configs/hj12_*exception*.yaml`.**
Do not `qsub` anything, do not touch a GPU, do not edit any file under `configs/`.

## Part 1 — `scripts/pbs/hj12_live.pbs` (the main deliverable)

Phase P2 runs five arms that each spend real hosted calls:

| config | calls/ep (est.) | episodes | est. calls |
|---|---:|---:|---:|
| `hj12_takeover_fixed_k_10` | 2.4 | 114 | ~280 |
| `hj12_takeover_fixed_k_3` | 6.8 | 114 | ~780 |
| `hj12_takeover_exception` | ~1.5 | 114 | ~170 |
| `hj12_advise_exception` | ~1.5 | 114 | ~170 |
| `hj12_planner_handoff` | ~5–8 | 114 | ~600–900 |

Clone `scripts/pbs/hj12_prefix.pbs` and keep everything that made it safe: the per-job
`VLLM_PORT=$(( 20000 + jobnum % 20000 ))`, the fatal-unless-the-alias-appears-in-`/v1/records` check,
the `setsid` + EXIT trap teardown, no `pkill -f`, the directory form of `#PBS -o`/`-e`, the `ARMS`
and `SMOKE_ONLY` overrides, `--workers 6`.

Four things must change:

1. **Invert the planner guard.** `hj12_prefix.pbs` fatals when a config names a live planner,
   because those arms are meant to be free. This script is the opposite: fatal **before any
   episode runs** if an arm's config does not resolve to a live `type: codex` planner with
   `model: gpt-5.6-luna`. An arm that silently falls back to a mock or a cached packet would
   produce a full set of plausible numbers measuring nothing — that exact failure has already cost
   this campaign a frontier.
2. **A spend ceiling that aborts, not just warns.** Take a `MAX_PLANNER_CALLS` variable (default
   sized from the table above with generous headroom — pick it and say what you picked and why).
   After each arm finishes, read the arm's realised live planner call count from its summary and
   accumulate it. If the running total exceeds the ceiling, **stop before launching the next arm**
   and exit non-zero with a message naming the total and the ceiling. Use the **ledger** count, not
   the replay-inclusive one: `ledger_totals.planner_calls_total`, not `planner_calls_total`. Those
   two differ, and reading the wrong one has already produced a false gate failure here
   [OBSERVED scripts/setup/campaign_summarize.py, the free-arm gate, fixed in commit 7564cc8].
3. **Print a per-arm escalation table** after each arm: episodes, live planner calls, calls per
   episode, and for takeover arms the count of planner-authored `action` events. A takeover arm
   showing zero planner-authored actions ran the advise path and the result is void.
4. **`SMOKE_ONLY=1` must be genuinely cheap**: 3 tasks, and it must print the escalation table so
   an operator can see the channel is live before committing the full spend.

Also emit, per arm, the distribution of `handoff_step` from the `run_end` events when present
(min / median / max / how many episodes never handed off). For `planner_handoff` that distribution
is the result, so it must not require a separate analysis pass to see.

`bash -n` the finished script and paste the output. **Do not submit it.**

## Part 2 — two hazards found reviewing the takeover commit

### 2a. A silent fallback in `CachedPacketPlanner.act`

```
try:
    return self.inner.act(task_id, text, timeout_s=timeout_s, allow_handoff=allow_handoff)
except TypeError:
    return self.inner.act(task_id, text, timeout_s=timeout_s)
```
[OBSERVED src/sidekick/agents/planner.py, in `CachedPacketPlanner.act`]

Every planner in the tree now accepts `allow_handoff`, so the fallback is unreachable in
production — but a `TypeError` raised *inside* `inner.act` for an unrelated reason would be
swallowed and retried with handoff silently disabled. The episode would then run to completion
looking normal while the capability under test was off. Remove the `try`/`except` and call
`inner.act` directly. If some caller genuinely needs the old signature, say so in STATUS instead of
keeping the swallow.

### 2b. `docs/FOLLOWUPS.md` — record two behaviours, do not change them

- **The action-review gate will almost always replace.** `run_action_review` now calls `planner.act`
  with `PROPOSED_ACTION: <text>` appended to the transcript, but the `act` prompt never explains what
  that line means [OBSERVED src/sidekick/agents/planner.py, `CodexExecPlanner.act`]. The planner will
  mostly emit its own next action, which differs from the proposal, so the `approve` verdict is close
  to dead and the gate behaves as takeover-at-trigger rather than as a discriminating review. No
  planned HJ-12 arm uses this path. Anyone who revives `action_review` as a *review* must write a
  review-specific prompt first.
- **`HANDOFF` is matched as a whole line anywhere in the planner's output**
  [OBSERVED src/sidekick/systems/loop.py, in `action_from_planner`], and it is checked *before*
  `resp.code`. A planner that writes a fenced action and also puts the bare word on its own line
  loses the action. The match is deliberately strict and the prompt documents the contract, so this
  is a known edge, not a defect — but if `planner_handoff` shows an implausibly high handoff rate at
  step 1, this is the first thing to check.

Write both as ordinary FOLLOWUPS entries in the file's existing style. Do not restructure the file.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Run the
  suite through `hpc`:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
- Suite is at **483 passed, 1 skipped** and must not fall. Add a test for the removal in 2a only if
  one is natural; do not contrive one.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Frozen, read only: `docs/prereg_*.md`, every `hj8_*` and `hj11_*` config.
- Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X9.md`, under 500 words: the `MAX_PLANNER_CALLS` value and your reasoning,
the exact summary key the spend ceiling reads, the `bash -n` output, what you did with 2a, the two
FOLLOWUPS entry titles, and the pasted suite line. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
