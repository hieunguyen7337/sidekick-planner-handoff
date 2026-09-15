# U3 — Sidekick harness: planner client, environments, systems, runner (owner: Cursor #2)

## Goal (what "done" means)

The experiment harness runs end to end **offline**: a mock planner plus a mock environment drive all
eight system variants to completion, writing a valid event log and cost totals, with a replay check that
re-derives the same environment state hashes. The real planner client (`codex exec`) and the real
environment (`AppWorldEnv`) are implemented and unit-tested against fixtures, but **you do not need
AppWorld installed** — another worker is installing it in parallel.

## Files you own — do not create or edit anything else

| path | content |
|---|---|
| `src/sidekick/agents/__init__.py`, `planner.py`, `executor.py`, `verifier.py` | `PlannerClient` protocol, `CodexExecPlanner`, `MockPlanner`, `VLLMExecutor`, `MockExecutor`, `Verifier` stub |
| `src/sidekick/environments/__init__.py`, `base.py`, `mock_env.py`, `appworld_env.py` | `BaseEnv`, `MockEnv`, `AppWorldEnv` |
| `src/sidekick/systems/__init__.py` + one module per system | the eight systems |
| `src/sidekick/runner.py` | the run loop, limits, CLI entry point |
| `src/sidekick/replay.py` | replay checker |
| `tests/integration/` | end-to-end tests on mocks |
| `campaign/workers/logs/U3_STATUS.md` | STATUS file |

**Do NOT create or edit** `pyproject.toml`, `src/sidekick/__init__.py`,
`src/sidekick/protocols/`, `src/sidekick/trajectories/`, `src/sidekick/cost/`, `configs/cost/`,
`tests/unit/`, `scripts/`, `docs/`, or `campaign/briefs/`. Two other workers own those and are editing
them right now. If a module you need does not exist yet, **write your code against the seam contract
anyway** and stub the import behind a `try/except ImportError` in your tests only.

## The seam contract is non-negotiable

Read `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/briefs/SEAM_CONTRACT.md`
and use exactly those type names, field names and method signatures. Another worker is implementing
those types right now; a rename breaks the build.

## 1. `CodexExecPlanner` — the frozen planner

The planner is the hosted model `gpt-5.6-luna`, driven through the **Codex CLI** as a subprocess. This
has been verified working from a compute node tonight (job 25382616): exit 0, usage fields present, no
sandbox created.

Build the command exactly like this, and make every element configurable:

```
codex exec --json --skip-git-repo-check -s read-only --disable shell_tool
           -m gpt-5.6-luna -c model_reasoning_effort=medium
           -C <an empty scratch dir unique to this call>
           [--output-schema <json schema file>]
           <prompt on argv or stdin>
```

Critical details, all verified:

- **`--disable shell_tool` is mandatory.** It stops Codex from running commands, which means no bwrap
  sandbox is created. The login-node sandbox is currently broken, so a planner that tries to use tools
  would fail.
- The user's `~/.codex/config.toml` defaults to a **different model (`gpt-5.6-sol`) at `xhigh` effort**.
  Therefore **always pass `-m` and `-c model_reasoning_effort=` explicitly** on every call. Never rely
  on the default. Log the resolved values into the event payload.
- Read stdout as **JSONL**. The events you need:
  - `{"type":"thread.started","thread_id":"..."}` → keep for resume;
  - `{"type":"turn.completed","usage":{"input_tokens":N,"cached_input_tokens":N,
    "cache_write_input_tokens":N,"output_tokens":N,"reasoning_output_tokens":N}}` → map straight into
    `Usage` (provider `"codex"`, model the id you passed). Missing keys default to 0.
  - the assistant text arrives as an `agent_message` / `item.completed` item — take the last one.
- Multi-turn: `codex exec resume <thread_id> [prompt]` continues a thread and hits the prompt cache.
  **Never pass `--ephemeral`** — it silently prevents resume.
- Always `< /dev/null` on stdin when the prompt is on argv, and wrap every subprocess in a timeout
  (default 300 s, configurable). A timeout is a logged event with `error_type="timeout"`, and the
  policy is: retry once, then fail the run.
- Baseline overhead measured tonight: a trivial prompt still consumed **15,378 input tokens** of Codex
  scaffolding. Do not be surprised by it; do log it.

Three methods, per the contract: `plan()` (task → `DelegationPacket`), `correct()` (packet + transcript
delta → correction text), `act()` (planner-alone: transcript → next code action). For `plan()` use
`--output-schema` with a JSON Schema for `DelegationPacket` (strict mode requires
`additionalProperties: false` and every property listed in `required`); fall back to fenced-JSON parsing
if the schema call errors, and log which path was taken.

`MockPlanner` returns canned, deterministic responses keyed by (task_id, call index), with realistic
`Usage` numbers, and **must never touch the network**. Every test uses it.

## 2. Executor client

`VLLMExecutor` talks to a vLLM OpenAI-compatible server over HTTP (`httpx`), with `model`, `base_url`,
optional `lora_name`, temperature, max tokens. Map the response `usage` into `Usage`
(provider `"vllm"`). Estimate `gpu_seconds` as wall time of the request times the fraction of the
server this run owns — make it an explicit, documented field, default `latency_s` (one request at a
time). `MockExecutor` emits scripted actions for tests.

`Verifier` is a stub in this unit: an interface `score(trajectory_state) -> float` plus a
`ThresholdRouter` that escalates when the score exceeds a threshold. A constant-0.5 implementation is
fine; the trained one comes later.

## 3. Environments

`MockEnv`: a deterministic toy world of a few files with a `delete_all()` irreversible action and a
2-step goal, no dependencies. `snapshot_hash()` = sha256 of the sorted state dict. It must support
being wrong in interesting ways so the systems have something to recover from.

`AppWorldEnv`: wraps AppWorld. Import it **lazily inside `reset()`** so the module imports fine on a
machine without AppWorld. Key facts (verified from the upstream repo):
- `from appworld import AppWorld, load_task_ids`; `load_task_ids(split)` with splits
  `train|dev|test_normal|test_challenge`;
- `AppWorld(task_id=..., experiment_name=...)`, then `world.task.instruction`, `world.task.api_docs`,
  `world.execute(code) -> str`, `world.evaluate(suppress_errors=True)`, `world.task_completed()`,
  `world.close()`;
- **one world per process** — AppWorld mocks time with `freezegun`, which is process-wide. Never create
  two worlds in one process, and never use threads. The runner parallelises with
  `multiprocessing.Pool`, one world per worker process, each with a unique `experiment_name` of the
  form `<run_id>/<system>/<seed>/<task_id>`;
- `snapshot_hash()` = sha256 over a stable serialisation of what the environment exposes about its
  state; if nothing suitable exists, hash the concatenated observation history and **say so in a
  docstring and in STATUS.md** (this weakens replay, so it must be visible).

## 4. The eight systems

All eight share one loop and one cost path. Differences are only in who is called when.

| name | behaviour |
|---|---|
| `planner_alone` | planner drives every step via `act()`; no executor |
| `executor_alone` | executor only, task instruction, no plan, no escalation |
| `prompt_only` | planner produces a plan once; executor executes; executor may emit `ASK_PLANNER`, planner answers via `correct()` |
| `fixed_k` | like `prompt_only` but the planner reviews every k steps regardless (k configurable, default 5) — the cost-matched control |
| `sft_plan` | same protocol as `prompt_only` but the executor uses a trained adapter (adapter name configurable) — the intervention-agnostic control |
| `router_seq` | `sft_plan` executor, frozen; a verifier/router decides when to escalate |
| `sidekick` | the trained executor decides for itself when to emit `ASK_PLANNER`, gated by the verifier |
| `oracle_escalation` | dev-only diagnostic: escalates exactly when a recorded oracle label says to |

Enforce the global limits from the contract: `max_steps=40`, `max_tokens_per_episode=32000`,
`per_step_timeout_s=120`, `max_planner_calls=25`. Exceeding one ends the run with
`error_type="limit"` and `success=False` — **never drop it from the results**.

Every planner call, executor call, action, observation, escalation and evaluation is an `Event`.
Escalations log `n_asks`; planner-initiated corrections log `n_interventions`.

## 5. Runner and replay

`runner.py` exposes a CLI: `python -m sidekick.runner --system <name> --split dev --tasks N
--seeds 1,2 --out <dir> --config <yaml>`, parallelised with `multiprocessing.Pool` (default 8, one
world per process), writing one `EventLog` per run and a `RunResult` per run, plus a combined
`results/<run_id>/runs.jsonl`. It must be resumable: on restart, skip runs whose result already exists.

`replay.py`: read an event log, re-execute the recorded actions against a fresh environment, and assert
the recorded `env_state_hash` sequence matches. Works on `MockEnv` in this unit; report whether it can
work on `AppWorldEnv`.

## Constraints (shared HPC login node)

1. **Never run Python, `pytest`, package installs, `tar` or `rsync` on the login node `aquarius01`.**
   Run them in a PBS job: `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<command>'`.
2. Put `timeout <seconds>` in front of **every** command.
3. **Do not run any `git` command**; do not touch `.git/` or `.claude/worktrees/`.
4. Never print the value of a token, key or credential — names only.
5. Do not call the real planner more than **5 times total** in this unit (it costs money and quota).
   Everything else uses `MockPlanner`.

## Return contract

Update `campaign/workers/logs/U3_STATUS.md` per milestone. Finish with at most 25 lines: files created,
the verbatim final pytest line for `tests/integration`, confirmation that all eight systems complete a
mock run, the replay result, anything stubbed and why, and any point where the seam contract did not fit
reality. Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
