# A5 served-model probe — can a run observe which model served a hosted planner call?

2026-09-23 08:26 AEST. One hosted call, `codex-cli 0.153.4`, argv shaped exactly as
`CodexExecPlanner` builds it (`src/sidekick/agents/planner.py:212-231`: `exec --json
--skip-git-repo-check -s read-only --disable shell_tool -m gpt-5.6-luna -c
model_reasoning_effort=low -C <scratch>`, prompt on stdin). rc 0.

## Answer: no — only the request is observable

**The `--json` event stream** (what the planner parses) has 4 events — `thread.started`,
`turn.started`, `item.completed`, `turn.completed` — and 10 scalar key paths in total:
`thread_id`, `type`, `item.{id,text,type}`, `usage.{input_tokens, cached_input_tokens,
cache_write_input_tokens, output_tokens, reasoning_output_tokens}`. **None names a model.**

**The session transcript** (`~/.codex/sessions/2026/09/23/rollout-…-<thread_id>.jsonl`, 13
records) does contain `"model": "gpt-5.6-luna"`, but only in client-side records —
`turn_context.payload.model`, `world_state.payload.state.model`,
`session_meta.payload.base_instructions.provenance.model` — i.e. the CLI's own record of the
`-m` it was given. No record carries a model identifier returned by the server.

## Consequences

1. `planner_model_requested` (X16 provenance, commit b290781) is the strongest statement a run
   can make, and it is named as a request for that reason. Stamping the `turn_context` model per
   call would add nothing: it echoes the same `-m`.
2. Amendment A1's no-substitution rule (plan §2, R5) can be enforced only on the request side:
   configs pin `gpt-5.6-luna`, the J10 wrapper refuses any other model and any CLI version other
   than the registered one. A substitution made server-side under the same model id would be
   undetectable from the run's own artifacts. This belongs in Paper B's limitations, beside the
   single-planner caveat.
3. Luna 6 changes nothing observable here: all 86 codex configs and the code fallback pin
   `gpt-5.6-luna` (plan §2), and the CLI version is now stamped into every episode manifest.
