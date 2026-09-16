# Unit U-A1 — the executor must see its own actions (harness defect #16)

**Repo (a git worktree — work here, do not cd elsewhere):**
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## The defect

The executor is prompted with a system message plus **one** user message holding a rendered
transcript (`src/sidekick/systems/loop.py:739-799`, `_executor_messages`). That transcript is built
by `transcript.append(f"OBS: {last_obs.text}")` at `loop.py:657` for every action that executes; the
`ACTION: {action.kind}` line at `loop.py:661` is reached **only** in the `else` branch, i.e. only for
action kinds that do *not* execute.

**So the executor never sees the code it wrote.** It receives a stream of observations with no record
of what produced them. The planner does not have this problem — it sees its whole history through its
codex thread.

This is very likely the cause of HJ-1's signature executor failure: granite-4.2-8b logged in
successfully, received a real `access_token`, and then called `login` again, repeatedly
(`campaign/RUNS.md`, and the correction note now inserted above "Three consequences"). That is what
any agent does when its own last action is absent from its context. HJ-1's executor arms scored 0.000
under this prompt, so those zeros are not a clean measurement of the model.

## Goal

Render the executor prompt as a **multi-turn conversation** — its own actions as `assistant` turns,
observations as `user` turns — behind a reusable function that the SFT data builder will also use, so
training data and inference share one renderer by construction.

## Files in scope

- `src/sidekick/protocols/prompts.py` — **new file**.
- `src/sidekick/systems/loop.py` — the executor prompt path only.
- `tests/unit/test_executor_prompt.py` — new.

🔺 **Out of scope, being edited concurrently by other workers:** `src/sidekick/runner.py`,
`src/sidekick/agents/planner.py`, `src/sidekick/protocols/schemas.py`,
`src/sidekick/training/`, `scripts/`, `configs/`. Do not touch them.

## 🔺 The hard constraint: the planner's prompt must not change by one byte

The `transcript: list[str]` at `loop.py:156` feeds **both** sides. The planner consumes it at
`loop.py:545` (`"\n".join(transcript)` → `planner.act`), `loop.py:515` and `loop.py:592`
(`transcript[-8:]` → `planner.correct`), and `loop.py:404` (the `trajectory_state` payload).

A campaign collecting teacher data with the *current* planner prompt is **running right now**, and
HJ-1's planner baseline was measured with it. Changing it would invalidate both.

**Therefore: leave `transcript` and every `transcript.append(...)` call exactly as they are.** Add a
*second, parallel* list used only for the executor prompt. The redundancy is deliberate and should be
stated in a comment: one list is a frozen wire format for the planner, the other is the executor's
conversation.

## The seam contract (Claude owns this; another unit builds against it — do not change it)

In `src/sidekick/protocols/prompts.py`:

```python
EXECUTOR_SYSTEM_PROMPT: str   # the system text, moved verbatim from _executor_messages

def render_executor_messages(
    *,
    instruction: str,
    api_docs: str = "",
    packet: DelegationPacket | None = None,
    history: list[dict],       # [{"role": "assistant"|"user", "content": str}, ...]
) -> list[dict]: ...
```

Returns `[{"role": "system", ...}, {"role": "user", ...}] + history`, where the single user message
is the task framing: `Task: {instruction}`, then `api_docs` if non-empty, then
`Plan: {packet.model_dump_json()}` if a packet is given — **exactly the text `_executor_messages`
builds today, minus the `Transcript:\n{transcript}\n` tail**, which the history replaces. Keep the
existing docstring about `api_docs` not being optional in practice, and keep the system prompt text
character-for-character: it encodes two measured failure modes and is not yours to improve.

`history` entries are already role-tagged, so the renderer only concatenates. Validate roles and
raise on anything else.

## Wiring in `loop.py`

Alongside `transcript`, maintain `exec_turns: list[dict]`, appending at the same places:

| existing `transcript.append` | `exec_turns` entry |
|---|---|
| `OBS: {last_obs.text}` (`:657`) | `{"role": "user", "content": f"OBS: {last_obs.text}"}` |
| `ACTION: {action.kind}` (`:661`) | nothing extra — see below |
| `INTERVENTION: {correction}` (`:532`) | `{"role": "user", "content": f"INTERVENTION: {correction}"}` |
| `ASK: {reason}` (`:608`) | `{"role": "assistant", "content": f"ASK_PLANNER: {reason}"}` |
| `ANSWER: {answer}` (`:609`) | `{"role": "user", "content": f"ANSWER: {answer}"}` |
| `ASK_IGNORED: {reason}` (`:618`) | `{"role": "assistant", "content": f"ASK_PLANNER: {reason}"}` then `{"role": "user", "content": "ASK_IGNORED"}` |
| `REPORT: {message}` (`:629`) | `{"role": "assistant", "content": f"REPORT: {message}"}` |
| `INSTRUCTION:` (`:413`), `PLAN:` (`:479`) | nothing — already in the framing user message |

🔺 **And the entry the current code never makes:** immediately before each observation is appended,
append the executor's own action as an `assistant` turn, in the **canonical form the parser accepts**
— a ` ```python ` fenced block for code, `ASK_PLANNER: …`, `REPORT: …`, `COMPLETE` / `COMPLETE: …`.
Read `parse_executor_action` in `src/sidekick/protocols/schemas.py:333` and the `_fenced_block` /
`_tagged_block` helpers so the rendered form is one the parser would round-trip. Prefer reconstructing
from the parsed `ExecutorAction` (so the history is canonical) rather than replaying the model's raw
output; if the `ExecutorAction` does not retain enough to reconstruct the action faithfully, say so in
your report rather than inventing a field.

Replace the `_executor_messages(...)` call site with `render_executor_messages(...)` passing
`exec_turns`, and delete `_executor_messages`. The planner call sites keep using `transcript`.

## Tests (`tests/unit/test_executor_prompt.py`)

Offline, fast, no network, no GPU. Cover:

1. **The regression itself**: a history of two code actions and two observations produces a message
   list in which the first action's code appears **before** the first observation, and both actions
   are present. A test that would have failed against the old single-message renderer.
2. Roles alternate as expected and the system message is first.
3. `api_docs` empty vs present; `packet` None vs present.
4. A round-trip: every `assistant` turn the renderer emits is parseable by `parse_executor_action`.
5. A `loop.py`-level test with `MockEnv` + `MockExecutor` over ≥ 2 steps asserting the messages the
   executor was handed contain its own first action. `MockExecutor` records what it was called with —
   read `src/sidekick/agents/executor.py:150-180` first.
6. 🔺 **A guard that the planner prompt did not change**: drive a short `planner_alone`-shaped mock
   episode and assert the string handed to `planner.act` still has the old `INSTRUCTION:` / `OBS:`
   shape. This is the test that protects the running campaign's comparability.

## Constraints

- `aquarius01` is a login node: **do not run `python`, `pytest`, `pip`, `tar`, `rsync`, `qsub`, or
  any multi-minute command.** Claude runs the suite in a PBS job. Write the code and report.
- Do not reformat files, reorder imports, or change anything outside the executor prompt path.
- The 104 existing tests must still pass; if a change requires touching an existing test, say which
  and why in your report rather than quietly rewriting it.
- Ignore `.claude/worktrees/` and `.git/`.
- Write `campaign/workers/STATUS_UA1.md` as you go (done / next / how to resume).

## Return contract (under 30 lines)

- The final signature of `render_executor_messages` and the `EXECUTOR_SYSTEM_PROMPT` provenance
  (confirm it is verbatim).
- How you reconstruct an action's canonical text, with the `ExecutorAction` fields you used
  `[OBSERVED src/sidekick/protocols/schemas.py:<line>]`.
- Confirmation that `transcript` and every planner call site are untouched, quoting the lines.
- Any existing test you had to change.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
