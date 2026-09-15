# Run ledger

One row per submitted campaign job, written when the job is submitted and closed out when
it ends. This exists because a campaign's own `manifest.json` records the commit at the
moment it is *written*, which is when the campaign finishes — and on 2026-09-15 six commits
landed while an arm was running. `SIDEKICK_START_COMMIT` (added in `419c0f6`) fixes that for
future jobs, but PBS snapshots a job script at submission, so any job submitted before that
commit cannot report its own provenance. The rows below are the record for those.

⚠ A manifest whose `git_commit_source` reads `manifest time (MAY NOT be the code that ran)`
must be reconciled against this file before its numbers are quoted anywhere.

| job | arm | campaign_id | submitted | code actually run | status |
|---|---|---|---|---|---|
| 25386878 | `planner_alone` (gpt-5.6-luna) | `hj1b_planner_20260915` | 2026-09-15 23:09 | **`6435bc0`** | see below |
| 25386895 | `executor_alone` (granite-4.2-8b, -3b) | `hj1a_exec8b/3b_20260915` | 2026-09-15 23:15 | `6435bc0` | exited 1 at 23:20 — smoke gate failed, `parse_error` 3/3 on both models. Results purged. |
| 25387603 | `executor_alone` (granite-4.2-8b, -3b) | `hj1a_exec8b/3b_20260915` | 2026-09-15 23:25 | **`419c0f6`** | see below |

## Why 25386895 does not count as a result

Both models scored 0.0 on every episode, and neither number was about the model. Granite
emits its native `<tool_call><py>…</py>` rather than a markdown fence, so correct code was
rejected unparsed; and with no stop sequence the 8b invented the environment's reply and
reasoned over the invention. Fixed in `5aa209c`. The 3b additionally never emitted code at
all, which `419c0f6` addresses in the prompt. The gate refused the arm rather than letting
it run five hours, which is the behaviour that was wanted.

## Provenance of the planner arm, and whether it may be compared across a code change

25386878 ran under `6435bc0`, which carries every harness fix that affects it: the real
`api_docs_prompt` (not the sha256 digest), `COMPLETE: <answer>` reaching
`apis.supervisor.complete_task(answer=…)`, and `plan_first=True`.

The two arms therefore ran under **different commits**, which is only acceptable if the
commits in between cannot move either arm's score. Checked rather than assumed, because the
first version of this note asserted `planner_alone` never touches the executor parser and
that was simply wrong:

- `planner_alone` sets `planner_drives=True`, so the planner's reply becomes the action via
  `loop.action_from_planner` (`src/sidekick/systems/loop.py:272`). That function **does**
  call `parse_executor_action`, so the parser is shared between the arms.
- But it only reaches the parser when `resp.code` is empty. Code is extracted first by the
  planner client's own `_maybe_python_fence` (`src/sidekick/agents/planner.py:471`), using
  `_PYTHON_FENCE_RE` — which is **already non-greedy** and was not touched tonight.
- So for the planner arm `parse_executor_action` only ever sees fence-less replies, i.e.
  `ASK_PLANNER:` / `REPORT:` / `COMPLETE` lines. That branch is byte-identical between
  `6435bc0` and `419c0f6`: every change tonight was to the code-block branch above it.

Conclusion: the arms are comparable. The remaining commits (`3ac04c3`, `791c160`, `2eb8eff`)
are docs and tests. Any future change to the `ASK_PLANNER`/`REPORT`/`COMPLETE` line scanning,
to `_maybe_python_fence`, to the planner client, or to `AppWorldEnv` invalidates this and the
arm must be re-run.

⚠ One known loss the planner arm keeps. Run `383cbac_3` seed 2 scored 0.0 because the model
closed its code fence with two backticks instead of three, so
`print(apis.supervisor.complete_task(answer=42, status="success"))` — a correct answer —
was discarded as unparseable. The parser learned to salvage that afterwards, verified against
the recorded bytes, but the fix landed while the arm was running and cannot apply to it. One
episode in 86, and it biases **against** `planner_alone`, so it makes the ≥20 pp gate harder
to pass rather than easier. Left as-is rather than re-running the arm for 1.2%.

⚠ Uncovered by the above: there are **two independent implementations of fenced-code
extraction** — `_PYTHON_FENCE_RE` in the planner client and `_FENCE_LAZY_RE`/`_PY_TAG_RE` in
`schemas.py` — and tonight they diverged. The schemas one now tolerates a `<py>` tag and a
fence truncated by a token limit; the planner one does not, so a planner reply cut off
mid-block silently yields `code=None` and falls through to a parse error. Logged in
`docs/FOLLOWUPS.md`; it has not bitten because luna's replies are short and well-formed.
