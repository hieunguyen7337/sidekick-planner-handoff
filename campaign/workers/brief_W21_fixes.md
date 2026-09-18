# W-21 — two review fixes: planner-token accounting, and the log-path collision

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Two small, independent fixes found in review. **Do not commit.** Other workers own
`scripts/setup/fit_feature_verifier.py`, `src/sidekick/training/matched_sft.py` and
`src/sidekick/agents/planner.py` — **do not touch them.**

## Fix 1 — the events fallback undercounts planner tokens

`scripts/setup/branch_counterfactual.py` now records per-branch planner cost from two sources.
The primary source is the episode result. The fallback reads the branch's own `events.jsonl`:

```
tokens += int(ev.usage.input_tokens or 0) + int(ev.usage.output_tokens or 0)
```

[OBSERVED scripts/setup/branch_counterfactual.py:841]

That does **not** match the authority it is standing in for. `CostLedger._tokens` sums four
fields:

```
input_tokens + cached_input_tokens + output_tokens + reasoning_output_tokens
```

[OBSERVED src/sidekick/cost/ledger.py:47-53], and `totals()` uses it for
`planner_tokens_total` [OBSERVED src/sidekick/cost/ledger.py:40].

The planner is a **reasoning model with prompt caching**, so `cached_input_tokens` and
`reasoning_output_tokens` are a large share of real usage — J6 spent ~478.6M planner tokens in
total. As written, the two sources disagree substantially, and which one a given branch uses
depends on whether its result dump survived. A planner **budget** computed from a mix of both
would be wrong by an unpredictable amount, which defeats the purpose of having it.

**Requirement:** the fallback must sum exactly the same four fields as `CostLedger._tokens`.
Do not duplicate the arithmetic if you can import or otherwise reuse the ledger's helper;
if you must duplicate it, put a comment naming `ledger.py:47-53` as the authority so the two
cannot silently drift.

### Fix 1b — do not coerce a genuine zero

Same function:

```
calls += max(1, int(ev.usage.n_calls or 1))
```

`Usage.n_calls` is `Field(1, ge=0)` [OBSERVED src/sidekick/protocols/schemas.py:34] — **zero is
a legal value**. `or 1` plus `max(1, …)` turns a real 0 into 1. This codebase has an explicit
convention against exactly this: `Usage` carries the comment *"None means 'not measured' … 0.0
means 'measured, mass was zero'. Never coerce None to 0.0"*
[OBSERVED src/sidekick/protocols/schemas.py:35-36].

Distinguish the two cases: a missing/None `n_calls` may default to 1, but a recorded `0` must
stay `0`. Add a test pinning that.

## Fix 2 — the J6 log paths carry no campaign id

`scripts/pbs/hj6_branches.pbs` writes its vLLM log to `VLOG="${LOGDIR}/hj6_branches_vllm.log"`
and its PBS stdout to `campaign/workers/logs/hj6_branches.out`. Neither carries the campaign id
(`${CID}`), so **the train and dev runs of J6 overwrite each other's logs**, and a resume
overwrites the original run's. This has already cost two misdiagnoses during the J6 crash
investigation.

**Requirement:** both paths carry the campaign id, so concurrent and successive runs cannot
collide.

🔺 **Constraint worth thinking about before you edit:** `Output_Path` comes from a `#PBS -o`
directive, which is evaluated at **submit** time and cannot interpolate a variable computed
inside the script. Solve it deliberately — e.g. pass `-o` at `qsub` time from the submitting
command, or have the script rename/copy its own output at exit. Say in your report which
approach you chose and why, and make sure a job that dies early still leaves a findable log.
Do not silently leave `Output_Path` unfixed while claiming the fix is done.

## Tests

- The four-field token sum, against a synthetic `events.jsonl` whose usage has all four fields
  non-zero: assert the total equals the ledger's own computation for the same usage.
- A recorded `n_calls == 0` stays 0; a missing `n_calls` defaults to 1.
- Keep existing tests green.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any job to a GPU queue** — in
  particular **do not submit `hj6_branches.pbs`**; you are editing it, not running it. The
  Codex quota is exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.**
- Suite: `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`. Current state is
  **347 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_W_21.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff and the test output as emitted.
- `path:line` for the corrected token sum and for the `n_calls` handling.
- Which approach you took for `Output_Path`, and why.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
