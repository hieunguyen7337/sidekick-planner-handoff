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
| 25386878 | `planner_alone` (gpt-5.6-luna) | `hj1b_planner_20260915` | 2026-09-15 23:09 | **`6435bc0`** | **COMPLETE 114/114**, see results below |
| 25386895 | `executor_alone` (granite-4.2-8b, -3b) | `hj1a_exec8b/3b_20260915` | 2026-09-15 23:15 | `6435bc0` | exited 1 at 23:20 — smoke gate failed, `parse_error` 3/3 on both models. Results purged. |
| 25387603 | `executor_alone` (granite-4.2-8b, -3b) | `hj1a_exec8b/3b_20260915` | 2026-09-15 23:25 | **`419c0f6`** | see below |

## `planner_alone` result, 2026-09-15 (114/114, code `6435bc0`)

| | |
|---|---|
| TGC | **0.684** (78 of 114 solved) |
| per seed, same 57 tasks | seed 1 **0.649**, seed 2 **0.719** |
| steps / episode | 13.52 mean |
| planner calls | 1,645 total, 14.4 per episode |
| outcomes | 101 clean, **12 `limit`**, 1 `parse_error` |
| provenance | `manifest.json` self-labels its commit "MAY NOT be the code that ran" — trust this file, not that field |

Two things in this table matter more than the headline.

**The binding cap was `max_planner_calls`, not `max_steps`.** Of the 12 `limit` episodes,
**11 hit `max_planner_calls=25` and none hit `max_steps=40`**. In `planner_alone` the planner
drives every step, so calls and steps are the same quantity, and the smaller cap silently
wins: this arm was effectively limited to 25 steps while `executor_alone` gets 40. It is the
conservative direction for the ≥20 pp gate (it holds the planner down), so it cannot
manufacture a pass — but the caps must be reconciled before any arm-to-arm cost or quality
number is published, and 10.5% of episodes being truncated means 0.684 is a floor on what
this planner does, not its ceiling.

**Seed spread is 7.0 pp on identical task sets.** 0.649 vs 0.719 over the same 57 tasks is a
clean read on the frozen planner's sampling noise, since nothing else differs. `PLAN.md` sets
ε = 5 pp for the later non-inferiority test — smaller than the noise of the baseline it is
measured against. Pairing by task removes task difficulty but not this, so ε = 5 pp with 2
seeds is likely unresolvable. Either widen ε or budget more seeds; decide before M6, not after.

## What `executor_alone` actually fails at (granite-4.2-8b, zero-shot)

Once the harness could read its output, the 8B executor stopped failing on format and
started failing on the task — and it fails the same way almost every time. A representative
episode, 40 actions, **0 parse errors, 12 distinct actions**:

```
print(apis.spotify.show_song_library())
print(apis.spotify.show_account())
print(apis.spotify.login())
print(apis.spotify.login(username="test_user", password="test_password"))   <- then repeats
```

It does not know how to obtain credentials — AppWorld requires looking them up through the
supervisor app — so it **invents** them and loops until the step cap. Every task needs a
login, so one unsolved sub-problem gates everything and the arm lands near TGC 0.

Two things follow, and both belong in how HJ-1 is reported:

- **The comparison is fair.** Both arms receive exactly the same information: the same API
  listing, no worked examples, no demonstrations. `gpt-5.6-luna` works the credential flow
  out for itself (it calls `apis.api_docs.show_api_doc(...)` and the supervisor APIs); the
  8B does not. That difference *is* the capability gap the pilot is meant to find.
- **This is a harsher baseline than the literature's.** Published frozen-8B ReAct numbers on
  AppWorld are ≈ 1–17 TGC, from scaffolds that include few-shot demonstrations of exactly
  this flow. Ours is zero-shot. So the measured gap is partly scaffold, not purely
  capability, and the pilot must say so rather than let a large number stand unqualified.
  It also means the headroom for a trained executor is, if anything, overstated by this
  arm — the right read is "there is plenty of room", not "the gap is 68 points".

The credential lookup is also the first concrete entry for the delegable-step analysis: it
is precisely the kind of step a planner knows and an executor does not.

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
