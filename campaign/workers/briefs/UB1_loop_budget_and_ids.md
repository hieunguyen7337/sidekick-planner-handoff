# Unit U-B1 — episode budget, failed-call model id, and plan thread id

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Goal

Three surgical corrections in `src/sidekick/systems/loop.py`, plus a new unit-test file.
All three are harness-accounting defects found by running the HJ-1 pilot; none changes control flow.

## Files in scope — nothing else

- `src/sidekick/systems/loop.py` — **only** the three sites named below.
- `tests/unit/test_limits_and_policy.py` — new file.

🔺 **Explicitly out of scope, because another worker is editing them concurrently:**
`_executor_messages` (~lines 729-781), the `transcript` list and every `transcript.append(...)` call,
`src/sidekick/runner.py`, `src/sidekick/agents/planner.py`, `src/sidekick/protocols/schemas.py`, and
everything under `configs/`. Do not touch them even if they look wrong. Do not reformat the file, do
not reorder imports, do not "tidy" anything you were not asked to change.

## Change 1 — the episode token budget must not count cached input

`token_count` at `src/sidekick/systems/loop.py:64` is:

```python
def token_count(usage: Usage) -> int:
    return int(usage.input_tokens + usage.output_tokens + usage.reasoning_output_tokens)
```

`usage.input_tokens` **includes** `usage.cached_input_tokens`. A `codex exec` call resends the whole
transcript on top of ~15.4k of Codex scaffolding, and HJ-1 measured 86.6% of a planner episode's
input tokens as cached. The consequence, from `docs/FOLLOWUPS.md` section 6: at
`max_tokens_per_episode: 32000` the planner arm died at step 2 while the executor arm reached step 20
— **two arms of one comparison given wildly different step budgets under one nominal cap**. One
HJ-1 episode (`37a8675_1`, seed 2) was still killed at 24 planner calls by the 2,000,000 cap.

Make it count uncached input plus output plus reasoning, clamped at zero so a provider that reports
`cached_input_tokens > input_tokens` cannot produce a negative budget. Keep it a single function with
one caller (`loop.py:185`, `episode_tokens += token_count(usage)`); do not add a config flag or a
second code path. Write a docstring that says what it counts and why cached input is excluded —
match the explanatory voice of `_planner_model_id` further down the same file.

## Change 2 — a failed executor call is labelled with the class name

`src/sidekick/systems/loop.py:327` stamps the bookkeeping `Usage` of a **failed** executor call with
`model=getattr(executor, "name", "executor")`. `VLLMExecutor.name` is the string `"vllm-executor"`
(`src/sidekick/agents/executor.py:30`) — a class name, not a model id. This is exactly the defect
that made the HJ-1 `fixed_k` gate report `planner ran as ['codex-exec']` for an arm where all 931
real calls went to gpt-5.6-luna; the planner half was fixed in commit `71ca6e3` and left this half
open (`docs/FOLLOWUPS.md` section 5).

`_planner_model_id` at `src/sidekick/systems/loop.py:717` already solves this shape for the planner.
Generalise it into one helper both sites use — e.g. `_client_model_id(client, fallback)` — that
prefers, in order, `client.config.model`, then `client.model`, then `client.name`, then the fallback.
`CodexExecPlanner` carries `self.config.model` (`planner.py:288`); `VLLMExecutor` carries
`self.model` (`executor.py:46`); `MockExecutor` has neither, so the fallback must still work. Keep
the existing docstring's explanation of *why* a class name here is dangerous — it is the record of a
real incident — and update both planner call sites (`loop.py:228`, `loop.py:248`) to the new helper.

## Change 3 — the plan event should record the codex thread id

The `plan` event emitted at `src/sidekick/systems/loop.py:~455-467` has a payload of
`{"packet", "parse_path", "model", "model_reasoning_effort"}`. Add `"thread_id": resp.thread_id`
(`PlannerResponse.thread_id` exists — `src/sidekick/protocols/schemas.py:85`, "codex session id, for
resume"; it may be `None`).

Why: a later unit replays archived plans instead of re-calling the planner, and the thread id is the
only link from a stored packet back to the hosted session that produced it. Without it, a cached plan
is unattributable.

## Change 4 — tests (`tests/unit/test_limits_and_policy.py`)

Offline, fast, no network, no GPU, no AppWorld. Cover:

1. `token_count` excludes cached input: `input=100000, cached=90000, output=500, reasoning=0` → 10500.
2. `token_count` clamps at zero when `cached > input`, and still adds output/reasoning.
3. `token_count` is unchanged when `cached_input_tokens == 0` (the executor's usual shape).
4. `_client_model_id` (or whatever you name it) returns the configured model for a
   `CodexExecPlanner`-shaped object, `self.model` for a `VLLMExecutor`-shaped object, and the
   fallback for an object with neither. Use tiny local stand-in classes; do not import vLLM.
5. The `limit` error event names which cap ended the episode. **Read the three emit sites first**
   (`loop.py:198`, `:477`/`:490`/`:529`, `:659`) — the payload key `"limit"` already carries
   `max_planner_calls` / `max_tokens_per_episode` / `max_steps`, so this needs **no production
   change**; write a test that pins it. Drive a short episode with `MockEnv` + `MockPlanner` /
   `MockExecutor` and `RunLimits(max_steps=2, ...)` and assert the emitted event's
   `payload["limit"] == "max_steps"`. If the mock objects cannot be driven that cheaply, say so in
   your report and pin the behaviour some other way rather than inventing a new production code path.

Each test gets a one-line comment naming the defect it guards, in the style of
`tests/unit/test_campaign_gate.py` (read it first — it is the house style for regression tests).

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pytest`, `pip`, `tar`, `rsync` or `qsub`.**
  Claude runs the suite in a PBS job. Write the code and report.
- Do not change behaviour beyond the three sites. In particular `max_tokens_per_episode` values in
  existing configs stay as they are — they are handled elsewhere.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract (under 30 lines)

- The final text of `token_count` and of the model-id helper, quoted.
- The exact lines you changed, as `[OBSERVED src/sidekick/systems/loop.py:<line>]`.
- Whether test 5 was written as an end-to-end mock episode or some other way, and why.
- Anything you found that contradicts this brief — say so rather than silently adapting.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
