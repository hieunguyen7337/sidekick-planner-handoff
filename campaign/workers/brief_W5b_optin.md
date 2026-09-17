# W-5b — make the P(ASK) instrumentation strictly opt-in

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why this is urgent

W-5's implementation is correct in substance and its tests pass (325 passed, 1 skipped,
verified independently). But it is **on by default**, and three J6 PBS jobs run straight out
of this worktree — `scripts/pbs/hj6_branches.pbs:30` sets
`PYTHONPATH=<this worktree>/src`. Two of those jobs have not started yet. When they start
they will import whatever is in `src/` at that moment. The earliest release is about 01:35
tonight.

A live campaign's inputs are frozen. Half its branches were produced by the old code path;
the rest must not be produced by a new one. Your job is to make the new behaviour invisible
unless it is explicitly switched on.

## Defect 1 — logprobs are requested on every call

`src/sidekick/agents/executor.py:263`:

```python
if kw.get("logprobs", True):
    payload["logprobs"] = True
    payload["top_logprobs"] = int(kw.get("top_logprobs", DEFAULT_TOP_LOGPROBS))
```

The default is `True`, so every existing caller now sends `logprobs` and `top_logprobs` to
vLLM. The W-5 seam contract required the opposite: *"carry the new number on the `Usage`
object as an optional field defaulting to `None`, so every existing caller is untouched."*

**Fix:** default it to `False`. Only a caller that explicitly passes `logprobs=True` gets the
extra request fields. When logprobs are not requested, `p_ask` is `None` — which the existing
code already treats as "not measured, leave the ask allowed". Do not change that handling.

## Defect 2 — every action event gains two new keys

`src/sidekick/systems/loop.py:488-490`:

```python
payload["p_ask"] = last_p_ask
if last_p_ask is None:
    payload["p_ask_fallback"] = True
```

This is unconditional, so `events.jsonl` action payloads change shape for every run,
including J6 branches that must stay comparable to the ones already on disk. The same
pattern repeats at `loop.py:785-786`, `:821-822` and `:846-847`.

**Fix:** emit `p_ask` (and `p_ask_fallback`) **only when the measurement was actually
requested** — i.e. when the self-gate path is active. When it is off, the action payload must
be byte-identical to what the pre-W-5 code wrote: no `p_ask` key, no `p_ask_fallback` key.

🔺 Keep the `None` vs `0.0` distinction fully intact **when the feature is on**. That was the
whole point of W-5 and it must not regress. Absent-key means "feature off"; `null` means
"feature on but unmeasurable"; `0.0` means "measured, mass was zero". Three states, all
distinguishable from the event log alone.

`trajectory_state` at `loop.py:509` may keep its `p_ask` key unconditionally — it is
in-memory only and never serialised to `events.jsonl`. Verify that claim before relying on
it; if it *is* serialised anywhere, apply the same rule to it.

## Defect 3 — the sidekick path must still work

With the defaults flipped, something has to turn the measurement back on. Wire it where the
verifier is resolved: when the configured verifier is `kind: self_p_ask`, the executor must
request logprobs. `src/sidekick/runner.py` already resolves `verifier.kind`; follow whatever
style it uses. The sidekick and `router_seq` systems are the only ones that need it.

Do not invent a new config key if an existing one will carry it. If you must add one, name it
and say so in your report.

## Tests — add these, keep all existing ones passing

- the default `complete()` request payload contains **no** `logprobs` and **no**
  `top_logprobs` key;
- `complete(..., logprobs=True)` does contain both;
- an episode run with the self-gate **off** produces action events with **no** `p_ask` key
  and no `p_ask_fallback` key — assert on the parsed event dict's keys, not on a substring;
- with the self-gate **on**, `None` and `0.0` remain distinguishable after a round trip
  through the event log (this test already exists — keep it green);
- a config with `verifier: {kind: self_p_ask, threshold: τ}` results in an executor that
  requests logprobs.

## Constraints — read these, you are not covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Anything that computes goes in a PBS job via `hpc`, `hpc-py` or `qsub`,
  with `timeout` on every command and BLAS pinned to one thread.
- **Do not submit any job to a GPU queue.** Three J6 jobs are live against this tree; a stray
  submission corrupts them.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- Run the suite in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
  Current state to match or beat: **325 passed, 1 skipped, 0 failures.**
- Do not revert or re-litigate W-5's design. It is right. Only its defaults are wrong.
- Update `campaign/workers/STATUS_W_5.md` (append a W-5b section) with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- One line each, with `path:line`: where the logprobs default now lives, where the event-key
  suppression is decided, and what turns the measurement on for the sidekick.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
