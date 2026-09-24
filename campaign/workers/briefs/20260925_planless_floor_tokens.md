# Brief: a planless arm-3 key must not zero the floor's tokens (PLANLESSFLOOR, 2026-09-25)

Worktree (absolute, the only cwd): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
IGNORE `.claude/worktrees/` (other worktrees) and `.git/`.

## Defect (verified by Claude)

`scripts/analysis/j8_noncached_cost.py:76-147`, `attach_sft_plan_source_plan_tokens`, maps every sft_plan (J10
arm 2, "floor") row onto its source's plan event to add the replayed plan's non-cached tokens. If ANY key has
no plan-event usage at its source (:117-120), the function takes the `understatement` route (:128-142) and adds
NOTHING to ANY row. Arm 2's own non-cached tokens are almost entirely that replayed plan (~23.9k/episode on
dev), so the floor's token cost collapses to about zero.

J10 A1 §4.2 (`docs/prereg_j10_amendment_20260924.md:214-240`) registers exactly this case on test_normal: a
**planless key** — an arm-3 source episode scored without a crash that wrote no plan — for which arm 2 calls
`gpt-5.6-luna` live for its first plan (`on_missing: call_if_planless`). That live plan is already in the arm-2
episode's OWN usage. The single definition is `planless_source_keys` / `_last_attempt_plan_event` /
`_scored_without_crash` in `src/sidekick/agents/planner.py:736-804`. One planless key on test would therefore
silently wreck the floor used by the B3 chord's f (`j10_report.py` chord code; `j8_frontier.py:928` calls the
attach function) and by `j12_cost_axes.py` (:45 re-exports it).

## The fix (decided; implement exactly this)

In `attach_sft_plan_source_plan_tokens` only:
- A key whose source episode is **planless by the planner.py definition** (result.json scored without a crash
  AND `_last_attempt_plan_event(events)[0] is None`) is NOT a mapping failure. Map it with **0.0** extra tokens
  (its live first plan is already counted in the row's own live usage), and count it in a new
  `info["n_planless_live"]`, with the keys listed in `info["planless_keys"]` (`"<seed>/<task_id>"`, as planner.py).
- Guard: if such a row's own live non-cached planner tokens (whatever field the cleaned row holds for its live
  planner usage — find it, cite it) are 0 or absent, the key IS a mapping failure (append to `missing` with a
  reason saying "planless source but no live plan in the episode").
- Every other miss (no packet_source, missing file, a non-planless source whose plan event has no usage) keeps
  today's conservative all-or-nothing `understatement` route, unchanged.
- Import the planner.py helpers (reuse; do not reimplement). If importing `sidekick.agents.planner` at module top
  is heavy, import lazily inside the function, as `j12_cost_axes.replayed_plan_usage` does (:755).
- Do not move line 16 of `j8_noncached_cost.py` (cited elsewhere). Keep the change inside the function plus, if
  needed, a small helper placed directly below it.

## Tests (new, in `tests/unit/test_j8_noncached_cost.py`; create it if absent, else append)

Build fixtures under `tmp_path` in the same shapes the existing `tests/unit/test_j12_cost_axes.py:~460-500`
fixture uses for `attach_sft_plan_source_plan_tokens` (read it; reuse its helpers if importable):
1. All keys planned → unchanged behaviour: `route == "source_plan_event"`, tokens attached, `n_planless_live == 0`.
2. One planless source key whose arm-2 row has live planner tokens > 0 → still `source_plan_event`, the other
   keys get their tokens, the planless key gets 0.0 extra, `n_planless_live == 1`, `planless_keys` lists it.
3. One planless source key whose arm-2 row has NO live planner tokens → `understatement` route (as today).
4. One genuinely missing source file → `understatement` route (as today).
Hand-compute every expected number in the test.

## Verify (all python/pytest through the queue — never on the login node)

`timeout 1800 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && export PYTHONPATH=$PWD/src:$PWD OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 && /scratch/n12194778/sidekick/env/bin/python -m pytest -q tests/unit/test_j8_noncached_cost.py tests/unit/test_j12_cost_axes.py tests/unit/test_j10_report.py tests/unit/test_j8_frontier.py'`
(drop a test file from the list if it does not exist; say so). Then prove dev outputs are unchanged: on dev
there are 0 planless keys, so re-running `scripts/analysis/j12_cost_axes.py` with the exact arguments that
produced `campaign/results/hj13_cost_axes_fixed_20260923.report.json` (find them in that file's header keys or in
`/home/n12194778/.claude/jobs/91578989/tmp/attrib/regen_job.sh`) into `/home/n12194778/.claude/jobs/91578989/tmp/planless/`
must give a byte-identical or value-identical JSON (compare with `jq -S`/`cmp`; report which).

## Rules

- HPC: no python/pytest/pip on the login node; `timeout` on every command; BLAS pinned to 1 thread.
- Do not read any `j10_*`, `j11_*`, `j12_*`, `bfcl_*` results or any test_normal/test_challenge data.
- Edit ONLY `scripts/analysis/j8_noncached_cost.py` and the one test file. Other uncommitted work sits in this
  worktree (`j10_report.py`, `j12_cost_axes.py`, cost reports, staging files): do not touch them. Another agent
  is writing `scripts/analysis/replay_divergence_diagnose.py`: do not touch it. Do not commit.

## Return contract (≤ 30 lines)

Tag claims `[OBSERVED path:line]` or `[INFERRED]`. The diff summary (function, lines), the live-token field you
used for the guard and where it comes from, the pytest summary line(s) with PBS job ids, and the dev-identity
result.
