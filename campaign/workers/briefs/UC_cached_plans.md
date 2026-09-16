# Unit U-C — replay archived planner packets instead of re-calling the planner

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

🔺 **Create the files within your first three actions, then iterate.** Do not spend the session
planning. Write `campaign/workers/STATUS_UC.md` after each milestone below (what is done, what is
next, how to resume) — if this session dies, that file is the only handover.

## Why this exists

HJ-1 spent 936 hosted `gpt-5.6-luna` calls to produce 114 plans. Every later experiment that needs
"the same plan for this task" — the `prompt_only` re-run, `sft_plan`, the SFT(c) correction pass —
should **replay those archived packets** instead of buying them again. Replay also removes
plan-sampling noise from every comparison: each arm then sees a byte-identical plan per (task, seed).

## Files in scope — nothing else

- `src/sidekick/agents/planner.py` — add one class at the end. Do not modify `CodexExecPlanner`,
  `MockPlanner`, or any parsing helper.
- `src/sidekick/protocols/schemas.py` — one literal widened (below).
- `src/sidekick/runner.py` — `make_planner` wiring, and the `make_env` fix (below).
- `tests/unit/test_cached_planner.py` — new.

🔺 **Out of scope, being edited concurrently by other workers:**
`src/sidekick/systems/loop.py` (all of it), `configs/`, `scripts/`, `src/sidekick/protocols/prompts.py`,
`src/sidekick/training/`. Do not touch them.

## Milestone 1 — `Provider` accepts cached plans

`src/sidekick/protocols/schemas.py:14` is `Provider = Literal["codex","vllm","mock"]`. Add `"cache"`.
A replayed plan is not a mock: `"mock"` is what the campaign gate uses to detect a mistyped
`planner.type` silently falling back to `MockPlanner`, and a replayed real packet must not look like
that failure. Add a short comment saying so.

## Milestone 2 — `CachedPacketPlanner`

In `src/sidekick/agents/planner.py`:

```python
class CachedPacketPlanner:
    name = "cached-packet"
    def __init__(self, inner, packet_source, system="planner_alone", on_missing="fail"): ...
```

The planner protocol is `plan` / `correct` / `act` / `close` (`planner.py:71-77`).

- **`plan(task_id, goal, context, timeout_s=None) -> PlannerResponse`** does no I/O to any model. It
  reads `<packet_source>/<system>/<seed>/<task_id>/events.jsonl`, finds the `plan` event, and rebuilds
  the packet with `DelegationPacket.model_validate(payload["packet"])`.
  - The seed is not passed to `plan()`, so take it in the constructor (`seed=`) and have
    `make_planner` supply it, **or** glob the seed directories and fail loudly if a task appears
    under more than one; pick one and say which in your report. Constructor argument is preferred.
  - 🔺 **Read the events file forwards and use only events after the LAST `run_start`.** A retried run
    appends to the dead attempt's log, so a file can hold two attempts concatenated with nothing
    marking the boundary (`docs/FOLLOWUPS.md` — "A retried run appended its events to the dead
    attempt's log"). Ordering must come from **file order**, never from the `ts` field: `ts` is frozen
    by freezegun and is identical across events.
  - The returned `PlannerResponse` has `kind="PLAN"`, the packet, and a `Usage` with **all token
    counts zero**, `provider="cache"`, `model` = the model id recorded on the cached event
    (`payload["model"]`, falling back to the event's `usage.model`), `n_calls=0`, and
    `raw={"cached_from": "<the events.jsonl path>", "cached_thread_id": <payload thread_id if present>}`.
    Zero tokens and `n_calls=0` because nothing was bought.
    ⚠ `campaign_summarize._planner_models` must still attribute this to the original model, so the
    provenance gate reports `gpt-5.6-luna` for a replayed arm. Read
    `scripts/setup/campaign_summarize.py` and confirm it does; report what you find. Do not edit it.
  - `on_missing="fail"` raises `FileNotFoundError` with the path it looked for. `on_missing="call"`
    falls through to `inner.plan(...)`. Default `fail` — a silently-live plan call would quietly spend
    quota and break the "every arm sees the same plan" property.

- **`correct(...)` and `act(...)` delegate to `inner`.** 🔺 But a replayed plan creates **no codex
  thread**, so the inner planner's first live call starts from nothing, whereas in HJ-1 it resumed a
  session that already held the task context. Therefore: on the **first** live call only, prepend the
  api-docs digest and the packet to the prompt content so the reviewer has what the thread would have
  carried. Implement this by passing the digest through — store the `context` argument that
  `plan()` was called with (the api digest) and prepend it to the `transcript_delta` handed to
  `inner.correct(...)` / the `transcript` handed to `inner.act(...)`, once, then set a flag. Mark the
  prepended block clearly, e.g. `=== api digest (plan was replayed; no prior session) ===`.
  Note `CodexExecPlanner.correct` already embeds the full packet in its prompt (`planner.py:317-324`),
  so the packet does not need repeating — only the digest. Confirm that when you read it.
- **`close()`** delegates to `inner.close()`.

## Milestone 3 — wiring in `src/sidekick/runner.py`

- `make_planner(cfg)` (`runner.py:87-100`): when `cfg["planner"]["packet_source"]` is set, build the
  inner planner exactly as now and wrap it in `CachedPacketPlanner`. Keep `packet_source` optional so
  every existing config behaves identically. The seed and system name must reach the planner — read
  how `make_planner` is called and thread them through the least invasive way; if that needs a
  signature change, make it and say so in your report.
- **`make_env` fix** (`runner.py:128-132`): it forwards the whole `appworld:` config block into
  `AppWorld(...)` as `extra_kwargs`, but `root` is an `AppWorldEnv` parameter, not an AppWorld one, so
  `appworld: {root: ...}` crashes **every episode** with
  `AppWorld.__init__() got an unexpected keyword argument 'root'` (`docs/FOLLOWUPS.md` section 6).
  Pop `root` out of the block and pass it as `AppWorldEnv(root=...)`. Read `AppWorldEnv.__init__`
  first and match its real signature.

## Milestone 4 — tests (`tests/unit/test_cached_planner.py`)

Offline, fast, no network, no GPU, no AppWorld import. Build tiny `events.jsonl` fixtures in
`tmp_path`. Cover: a cache hit returns the archived packet with zero-token `provider="cache"` usage
carrying the original model id; a miss under `on_missing="fail"` raises and names the path; a file
holding **two** `run_start` events yields the packet from the second (later) attempt; the first live
`correct()` receives the digest and the second does not; `make_planner` without `packet_source`
returns an unwrapped planner. Use a stub `inner` that records the prompts it was given.

## Constraints

- `aquarius01` is a login node. **Do not run `python`, `pytest`, `pip`, `tar`, `rsync` or `qsub`.**
  Claude runs the suite in a PBS job. Write the code and report.
- Do not modify any archived artifact under `campaign/results/` or anything in `/scratch`.
- Ignore `.claude/worktrees/` and `.git/`.
- Match the existing house style: explanatory docstrings that say *why*, not *what*.

## Return contract (under 30 lines)

- The `CachedPacketPlanner` constructor signature and the `Usage` it returns, quoted.
- How the seed reaches the planner, and any signature you changed.
- What `campaign_summarize._planner_models` does with a `provider="cache"` record — quote the lines.
- The `make_env` fix as a before/after pair.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
