# Run ledger

## HJ-1 gate verdict, 2026-09-16 — **PASS**

Paired on (task_id, seed), all 114 pairs present on both sides, nothing dropped.

| arm | n | TGC | SGC | solved | steps | planner calls |
|---|---|---|---|---|---|---|
| `planner_alone` (gpt-5.6-luna) | 114 | **0.684** | 0.447 (17/38 scenarios) | 78 | 13.5 | 1,645 |
| `executor_alone` (granite-4.2-8b, zero-shot) | 114 | **0.000** | 0.000 | 0 | 39.9 | 0 |
| `prompt_only` (luna plans once, 8b executes) | 114 | **0.000** | 0.000 | 0 | 39.9 | 114 |
| `fixed_k` (luna reviews every 5 steps) | 114 | **0.000** | 0.000 | 0 | 36.2 | 936 |

All three executor-driven arms sit at exactly 0.000, so each differs from `planner_alone` by the
identical **68.42 pp, 95 % CI [59.65, 76.32]** (10,000 paired bootstrap resamples, 114 pairs, none
dropped). The gate asks for ≥ 20 pp; even the lower bound clears it threefold. Full report:
`campaign/hj1_gate.json`.

🔺 **The headline is no longer the gate — it is that 936 planner calls bought nothing.**
(936 attempted, 931 billed — reconciled in the `fixed_k` section.) One plan:
nothing. Eight expert reviews per episode: nothing. Whatever separates luna from granite-4.2-8b on
AppWorld, it is not information that can be handed over in text.

**What this does and does not license.** It licenses the conclusion the gate exists for:
there is ample room between a frozen hosted planner and an untrained small executor, so a
trained executor has something to close and the later milestones are not measuring noise.
It does **not** license quoting 68.4 pp as the capability gap, for three reasons that all
push the same way:

1. `executor_alone` is **zero-shot**, while the published frozen-8B ReAct numbers on
   AppWorld (≈ 1–17 TGC) come from scaffolds that few-shot the very flow ours never
   discovers. Part of the 68 pp is scaffold, not capability.
2. `planner_alone` was capped at 25 planner calls (see below) and 10.5% of its episodes
   were truncated by it, so 0.684 is a floor.
3. Both are measured on dev, which is the split the prompts were tuned on.

The honest headline is "plenty of headroom, gate passed", and the exact figure is an upper
bound.

**Why there is no 3B row.** The strengthened smoke gate refused the `granite-4.2-3b` arm:
`parseable_actions=6, ended_in_parse_error=2/3`. The 3B still cannot hold the action format
— it narrates its intentions rather than emitting code — and no arm was run. This costs
nothing: the 3B exists in `PLAN.md` as a fallback for the case where the executor is *too
strong* and the gap is too small to study, and the 8B scored 0.000, so that risk did not
materialise. Chasing 3B format compliance would not change the gate.


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
| 25387603 | `executor_alone` (granite-4.2-8b, -3b) | `hj1a_exec8b/3b_20260915` | 2026-09-15 23:25 | `419c0f6` | exited 1 at 23:41 — the smoke gate shared a campaign_id with the main run, so `run_campaign` skipped all 3 tasks (`n_jobs: 0, n_skipped: 3`) and the gate re-graded the *previous* build's results. Ran no episodes. |
| 25388321 | `executor_alone` (granite-4.2-8b) | `hj1a_exec8b_20260915` | 2026-09-15 23:45 | `ec3f29e` | **killed by me** at 23:57. The old gate passed on "any action parsed anywhere" and the arm ran to completion at 108 runs / 108 `parse_error` / 0 solved. Results purged; gate rewritten. |
| 25388996 | `executor_alone` (granite-4.2-8b) | `hj1a_exec8b_20260915` | 2026-09-16 00:01 | `6ba8270` | **killed by me** at 00:07. Parsing worked (episodes reached step 3 instead of 1) but a single unparseable step still ended an episode, so ~⅓ would have died on format. Killed rather than bank a gate that passes *because* the executor looks weak. |
| 25389506 | `executor_alone` (granite-4.2-8b, -3b) | `hj1a_exec8b/3b_20260915` | 2026-09-16 00:13 | **`7829a4c`** | **8B COMPLETE 114/114** (gate: 120 parseable actions, 0 parse errors). 3B arm **refused by the gate** (2/3 episodes ended in parse_error). Job exit 1 is the 3B refusal, not an 8B failure. |
| 25390326 | `prompt_only` (luna + granite-4.2-8b) | `hj1c_prompt_only_20260916` | 2026-09-16 00:49 | **`a733865`** | **COMPLETE 114/114**, exit 0. Gate PASS (120 actions, 3 planner calls, 0 parse errors); final gate PASS with the expected planner and model. |
| 25392080 | `fixed_k` (luna every 5 steps + granite-4.2-8b) | `hj1c_fixed_k_20260916` | 2026-09-16 01:52 | **`b2a1160`** | **COMPLETE 114/114**, exit 0, 52 min wall. The final gate printed FAIL — a **gate defect, not a run defect** (see below). Re-graded **PASS** after the fix, from the same archived results.

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

## `prompt_only`: a one-shot plan from a strong planner does not help a weak executor at all

**Completed 114/114 on 2026-09-16. TGC 0.000, SGC 0.000, 0 solved, 114 planner calls (exactly one
per episode), 113 `limit` + 1 `crash`, 39.87 mean steps.** Identical to `executor_alone`.

⚠ **This corrects a preliminary reading taken from the 3-task smoke.** At n=3, none of the plans
mentioned authentication, and I recorded the hypothesis that the planner omits the operational
prerequisite the executor cannot discover. **At n=114 that is false: 48 of 114 plans (42%) do
mention `login`/`password`/`authenticat`/`access_token`/`supervisor`** — and TGC is 0.000 anyway,
including on those 48. The small sample was unrepresentative, which is exactly why it was marked
preliminary.

The real mechanism is worse for the plan-only approach, and was checked directly. In episode
`23cf851_2`, whose plan names the supervisor app, the executor calls `supervisor` **zero times in
40 actions** and instead loops:

```
print(apis.api_docs.show_api_doc(app_name="venmo", api_name="show_transactions"))
print(apis.phone.get_current_date_and_time())
print(apis.phone.get_current_date_and_time())
print(apis.phone.get_current_date_and_time())   ← and on, to the step cap
```

So granite-4.2-8b does not fail for want of being told. It fails to *follow* a plan it has been
given, and degenerates into repeating one harmless call. The bottleneck is executor agency, not plan
content.

What this licenses, at n=114 and paired:

| arm | TGC | vs planner_alone |
|---|---|---|
| `planner_alone` | 0.684 | — |
| `executor_alone` (8b) | 0.000 | 68.42 pp [59.65, 76.32] |
| `prompt_only` (luna plan + 8b) | 0.000 | 68.42 pp [59.65, 76.32] |

**One frozen plan buys exactly nothing here — 0.000 either way.** That is a real result for the
project's premise rather than a null: it says the gap is not an information gap that a better prompt
closes, so the remaining arms have to earn their improvement through *when and how* the planner
re-enters, not by planning harder up front. It makes `fixed_k` (periodic review) and `sidekick`
(verifier-gated escalation) the load-bearing comparisons, and it predicts `prompt_only ≈
executor_alone ≪ fixed_k ≤ sidekick` — falsifiable by the arms that have not run.

⚠ It also raises a live risk for the project: if the 8B cannot follow a good plan at all, training it
to *ask* may not be enough either, and the 30B or a stronger executor may be needed for the method to
have anything to work with. That is a question for M3, and it should be asked explicitly rather than
discovered at M6.

## `fixed_k`: 936 expert corrections, and the diagnosis they produced

**Completed 114/114. TGC 0.000, 936 planner calls (8.2/episode), 96 `limit`, 12 `parse_error`,
4 `crash`, 2 finished cleanly but wrong, 36.2 mean steps.**

⚠ **This arm's final gate printed `FAIL`, and the gate was wrong.** The reason it gave was
`planner ran as ['codex-exec'], expected only 'gpt-5.6-luna'` — but no call went to any model
called `codex-exec`. `codex-exec` is the *class name* of the planner client, and `loop.py` stamped
it on the zero-token bookkeeping `Usage` it charges when a planner call **fails** (timeout or
`PacketParseError`). Three of the 114 runs hit a packet parse error, so three synthetic records
entered the ledger, and `campaign_summarize._planner_models` read them as model provenance. The
gate's message lists only the *unexpected* models, which is why the real `gpt-5.6-luna` records
did not appear in it and the failure looked total rather than 3-in-114.

Both halves are fixed: `loop.py` now stamps the *configured* model on a failed-call record, and
the summariser ignores a zero-token placeholder that carries an `error_type`. A genuine
`MockPlanner` fallback — the mistyped-`planner.type` case this check exists for — is deliberately
**not** filtered, because its usage carries real token counts (15,378 input); `tests/unit/
test_campaign_gate.py` pins both directions. Re-graded from the same archived results, all three
planner-using arms now gate **PASS**.

**Three different planner-call totals, all correct, none interchangeable:**

| figure | count | what it is |
|---|---|---|
| loop counter (`n_planner_calls`) | **936** | every call the episode loop *attempted* |
| ledger records (`planner_calls_total`) | **934** | every call that recorded a usage row |
| real billed calls | **931** | the above minus the 3 zero-token failure placeholders |

The loop/ledger gap of 2 is entirely in the **2 crashed runs** (`23cf851_1`, `57c3486_2`), where
the episode died before the usage row was written. All 112 healthy runs agree exactly. Quote
**931** for spend and **936** for intervention burden.

`fixed_k` was run precisely because `prompt_only` failed: if one plan does nothing, does periodic
re-entry? It does not. But *how* it fails is the most useful thing HJ-1 produced, because the
planner's reviews are not vague — they are correct, specific, and they name the exact call:

> "Authenticate first: call `apis.supervisor.show_account_passwords()` to obtain the phone account
> credentials, then call `apis.phone.login(username=..., password=...)`; only after a successful
> login, search contacts and send the exact message."

> "Use `apis.supervisor.show_profile()` to obtain the correct phone-account username … Do not use
> `"phone"` as the username or expose credentials."

The second review has even diagnosed the executor's specific error. And in that episode the executor
**complied**: it called `show_account_passwords()`, obtained real credentials, and logged in
successfully — the environment returned a genuine `access_token`. It then called `login` again. And
again. It never passed the token to anything.

So the failure is not ignorance, and it is not disobedience. Across the whole arm, **34 of 114
episodes (30%) did eventually pass an `access_token` to a later call** — and none of them finished
either. Auth is only the first wall; the executor fails at the next composition point too. The
defect is **carrying state across steps**, and it is general rather than a single missing fact.

> 🔺 **Correction, 2026-09-16 — this mechanism is withdrawn pending HJ-1R.** The paragraph above
> reads a prompt-level defect as a model-level one. The executor's prompt is a system message plus a
> single user message holding a rendered transcript (`src/sidekick/systems/loop.py:729-781`), and
> that transcript is built by appending `OBS: <output>` for every executed action
> (`loop.py:647-651`) — the `ACTION:` line is reached **only** for action kinds that do not execute.
> So the executor never saw the code it had just written. It was shown a stream of outputs with no
> record of what produced them. The planner, by contrast, saw its whole history through its codex
> thread.
>
> "Logged in, then called `login` again" is exactly what an agent does when its own previous action
> is not in its context. The observation is real; the inference that granite-4.2-8b **cannot** carry
> state is not supported, because it was never given the state to carry. Measured corroboration:
> executor input grew only 11.5k → 13.2k tokens across 40 steps, and steps 1 and 2 of
> `prompt_only/1/0d8a4ee_1` carry an identical failing observation.
>
> **What still stands:** the HJ-1 gate verdict. `planner_alone` beat all three untrained-executor
> arms by 68.42 pp [59.65, 76.32] against a ≥ 20 pp threshold, and that comparison is unaffected —
> if anything the baselines were handicapped, so the gap is an upper bound on the true one.
> **What does not stand:** any claim about *why* the executor failed, and therefore any SFT result
> compared against these zeros. HJ-1R re-runs `executor_alone` and `prompt_only` on dev under a
> multi-turn prompt that includes the executor's own actions, and those numbers — not these — are
> the baseline for SFT(b). Consequence 1 below is on hold until HJ-1R reports; consequences 2 and 3
> are unaffected.

Three consequences worth carrying into M3/M4:

1. **This is the best possible case for the project's premise and its biggest risk at once.** Text
   cannot transfer what luna has; that is why an executor must be *trained* rather than prompted. But
   if the 8B cannot hold state across five steps even under expert correction, teaching it *when to
   ask* may not be enough — the thing it lacks is not timing.
2. **The SFT target is now concrete.** `planner_alone` produced 78 solved trajectories that do carry
   state correctly. That is exactly the behaviour to distil, and it is already on disk.
3. **Check this before spending M4's 20 GPU-hours.** A cheap M3 probe — does granite-4.2-8b complete
   *any* AppWorld task when handed a correct, fully-specified action sequence? — separates "needs
   training" from "cannot be trained at this scale", and it costs a few GPU-minutes. If the answer is
   no, the executor choice should change before, not after, the training milestone.

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

---

## HJ-1R + HJ-1.5 (job J1) — decision rules, recorded before submission

These are written down **before** the job is submitted, so that the reading of its result is not
chosen after seeing it. Campaigns: `hj1r_exec8b_20260916`, `hj1r_prompt_only_20260916`; probes to
`probe_granite8b.json` and `probe_qwen3_8b.json`.

**What changed since HJ-1, and what deliberately did not.** Only the executor prompt: it is now a
multi-turn conversation including the executor's own actions (commit `b6e31ca`). The configs differ
from the frozen pilots in campaign id, `max_planner_calls`, and `prompt_only`'s `packet_source` —
nothing else. `prompt_only` replays HJ-1's archived packets, so every task gets the identical plan it
got in HJ-1 and the arm spends zero hosted planner calls. Same split, same tasks, same seeds.

### HJ-1R — the honest untrained baseline

| outcome | reading | consequence |
|---|---|---|
| `prompt_only` TGC still 0.000, CI excluding any positive effect | the prompt was not the binding constraint; HJ-1's mechanism claim was wrong but its numbers stand | restore a *narrowed* version of the claim, and proceed to SFT with HJ-1R as the baseline |
| `prompt_only` > 0 with a bootstrap CI excluding 0 | part of HJ-1's 68.42 pp gap was harness, not model | report **both** numbers; the ≥20 pp gate is re-evaluated on HJ-1R, not assumed to carry over |
| `prompt_only` ≥ `planner_alone` − 20 pp | the gate no longer passes on the honest baseline | stop; the project's premise needs restating before any training spend |

The gate verdict is expected to survive — the old baselines were handicapped, so 68.42 pp is an
upper bound — but it is **re-computed**, not inherited. `hj1_gate.py` is re-run pairing
`hj1b_planner_20260915` against the two HJ-1R arms on their shared (task_id, seed) pairs.

⚠ Whatever HJ-1R reports, **it, and not HJ-1's zeros, is the baseline every SFT number is compared
against.** Comparing a trained executor under the fixed prompt to an untrained one under the broken
prompt would credit the prompt fix to training.

### HJ-1.5 — the state probe

Primary metric: given a correct gold history replayed into a fresh world, the model's next action
executes without error and calls the same `apis.<app>.<api>` set as the teacher's. Temperature 0.

| primary agreement | reading | consequence |
|---|---|---|
| ≥ 40% overall, not collapsing with depth | granite-4.2-8b can act from a correct history; it needs training, not replacing | train SFT(b) on Granite as planned |
| < 15% on Granite **and** materially better on Qwen3-8B | the executor choice is wrong, and cheaply fixable | switch the executor before J3, not after |
| between, or degrading sharply with depth | trainable but marginal | proceed on Granite **and** add a third seed to HJ-2B for more teacher data |
| < 15% on **both** Granite and Qwen3-8B | the teacher's action is not predictable from what the executor can see — an unrealizable expert, not a weak model | do **not** swap executors; it cannot help. Enrich the conditioning (carry more of the planner's reasoning into the packet) and re-probe, before any further SFT spend |

🔺 **The fourth row was added 2026-09-16 21:37 AEST, after job 25401397 was submitted but before any
probe output existed** (`probe_granite8b.json` / `probe_qwen3_8b.json` absent at the time of
writing; the job was 3 minutes into an 8-phase run whose probes are phases 5 and 7). It closes a
genuine gap: the original table said what to do when Granite is weak *and Qwen is better*, but not
when **both** are weak, which is the one outcome that would invalidate the executor-swap remedy
rather than trigger it. Pre-registering it now keeps that call out of post-hoc territory.

**Two notes on reading the number, recorded before it exists:**

1. **Agreement is stricter than per-step accuracy.** It scores the same `apis.<app>.<api>` set as
   the teacher — one particular correct action among several that may all be correct. So agreement
   *understates* competence, and the 40 % / 15 % thresholds are conservative. A 0.35 reading does
   not contradict a substantially higher true per-step success rate.
2. **A near-zero end-to-end TGC is not evidence of a weak model.** At the teacher's mean solved
   length of 13.52 steps, a per-step accuracy of 0.704 yields TGC 0.0088 — which is exactly HJ-1R
   arm A's observed 1/114. Compounding, not inability, is sufficient to explain the floor, and the
   leverage runs the other way too: +13.9 pp of per-step accuracy takes TGC to 0.10, +18.3 pp takes
   it to 0.20. (Model: TGC ≈ p^13.52, assuming no recovery from a bad step. AppWorld does permit
   recovery, so true per-step accuracy may sit below 0.704 — treat this as an order-of-magnitude
   reasoning device, not a measurement.)

`hash_match` (byte-identical `env_state_hash`) is reported but **gates nothing**: `snapshot_hash`
hashes `environment_io`, which includes the input code, so it can only match when the model emits
byte-identical code to the teacher. Reading a near-zero there as failure would be a measurement
artefact, not a finding.

These probe numbers are the **pre-SFT baseline** the post-SFT probe in J3 is compared against.

---

## HJ-2B teacher demos on train — job 25397852, COMPLETE 180/180

| | |
|---|---|
| campaign | `hj2b_planner_train_20260916` |
| code | `d873781` (`SIDEKICK_START_COMMIT`, pinned at job start) |
| submitted / ended | 2026-09-16 18:31 / 19:47 AEST |
| wall / cpu | 1:12:53 / 1:50:35, 8 cpus, no GPU |
| runs | **180/180, 0 broken**, exit 0 |
| TGC | **0.744** (seed 1), **0.733** (seed 2) — 90 train tasks |
| steps / episode | 13.52 mean |
| planner calls | **2,613** total, 14.5 per episode, all `gpt-5.6-luna` |
| gate | smoke **PASS**, final **PASS** (`--expect-planner --expect-model gpt-5.6-luna`) |
| archive | `~/sidekick_data/hj2b_planner_train_20260916/`, 180 `events.jsonl`, 12 MB |

This is the SFT(b) teacher set: **133 solved trajectories** of the 180, replacing `PLAN.md`'s
"successful `prompt_only` segments", which do not exist because `prompt_only` solved 0 of 114.

**The cap fix worked.** In HJ-1, `max_planner_calls=25` ended 11 of 12 truncated episodes and none
hit `max_steps`; the arm was silently running at 25 steps while `executor_alone` had 40. With the cap
at 81 (2·max_steps+1), **exactly one episode of 180 hit any limit at all**. Step counts now sit where
the episodes actually end — mostly 11–20, one at 26, one at 40 — rather than at the cap.

⚠ **Train is not harder than dev, and the seed noise there is smaller.** TGC 0.739 on train against
0.684 on dev is the same planner on a comparable distribution, which is what SFT needs. But the
seed-to-seed discordance is **18.89% on train (17 of 90)** versus **28.07% on dev (16 of 57)**, and
the marginal seed gap is **1.11 pp** against dev's 7.02 pp. The two discordance estimates are ≈1.3
combined standard errors apart — compatible, pooling to 22.4% over 147 pairs — so the 7 pp dev seed
gap that prompted the HJ-7 power analysis looks like an unlucky draw on 57 tasks rather than a
property of the planner. **ε = 7 pp stays**, calibrated on the pessimistic dev figure: revising a
margin downward after seeing a friendlier number is the post-hoc selection preregistration exists to
prevent, and if the truth is nearer 19% the realised power simply exceeds the stated 0.860.

---

## HJ-1R — the untrained baselines, re-run under the fixed executor prompt (2026-09-16)

Jobs `25400264` (aborted at phase 4, see below) and `25401397`; commit `1e3dc38`, clean tree;
AppWorld `42b5bcf`; granite-4.2-8b via vLLM, dev 57 × seeds 1,2 = 114 episodes per arm.
Artefacts: `campaign/results/hj1r_{exec8b,prompt_only}_20260916.{runs.jsonl,manifest.json}`,
gate in `campaign/results/hj1r_gate.json`. Both campaign gates **PASS**.

### Why it was re-run

Defect #16: `loop.py` appended `OBS:` for every executed action but reached the `ACTION:` line only
for non-executing kinds, so the executor's prompt held outputs but never the code that produced
them. HJ-1's executor-arm zeros were therefore produced under a prompt that hid the executor's own
actions, and the "cannot carry state" mechanism could not be distinguished from that artefact.

### Results

| arm | prompt | n | TGC | goal-pass | steps | ended normally | hit cap | crash |
|---|---|---|---|---|---|---|---|---|
| `executor_alone` (HJ-1) | old | 114 | 0.000 | 0.213 | 39.89 | 0 | 113 | 0 |
| `prompt_only` (HJ-1) | old | 114 | 0.000 | 0.250 | 39.87 | — | — | — |
| **`executor_alone` (HJ-1R)** | fixed | 114 | **0.0175** | 0.1903 | 30.16 | 77 | 37 | 0 |
| **`prompt_only` (HJ-1R)** | fixed | 114 | **0.0439** | 0.286 ⚠ | 32.00 | 69 | 39 | 6 |
| `planner_alone` (teacher) | — | 114 | 0.684 | 0.828 | 13.52 | — | — | — |

⚠ `prompt_only`'s goal-pass is over n=108: 6 episodes died on vLLM HTTP 400 (context overflow,
FOLLOWUPS §7.4) and carry no rate. The censored episodes are the longest, so 0.286 is biased
slightly **down**.

### Verdict against the rule recorded before submission

The rule required: if `prompt_only` under the fixed prompt is > 0 with CI excluding 0, part of
HJ-1's gap was the harness — report both numbers and keep the 20 pp gate, which holds *a fortiori*
only if the re-run stays ≥ 20 pp below the planner.

`prompt_only` is **0.0439, not 0.000** — five solved tasks where the old prompt solved none. Paired
bootstrap (10,000 resamples, 114 pairs, `hj1r_gate.json`):

| comparison | gap | CI95 | ≥ 20 pp margin |
|---|---|---|---|
| `planner_alone` − `executor_alone_R` | 66.67 pp | [57.89, 75.44] | **yes** |
| `planner_alone` − `prompt_only_R` | 64.04 pp | [54.39, 72.81] | **yes** |

**HJ-1's gate stands** on the honest baseline, with a CI lower bound of 54.4 pp against a 20 pp
margin. The headline number changes from 68.4 pp to 64.0 pp.

**The mechanism claim is narrowed, not restored.** The prompt fix changed the failure mode — cap-
hitting fell from 113/114 to 37/114 and mean steps from 39.9 to 30.2, i.e. the executor now
terminates instead of looping — but it did not make the executor competent. What it did establish,
which HJ-1 could not, is that **the plan transfers measurable value**: `prompt_only` beats
`executor_alone` by +2.6 pp TGC and +9.6 pp goal-pass on identical tasks and seeds. Under the old
prompt both arms were pinned at 0.000 and that effect was unmeasurable. "Cannot carry state" stays
withdrawn.

### Two observations worth recording

**The graded metric is what makes the untrained arms distinguishable at all.** Under TGC the three
HJ-1 baselines were 0.000, 0.000, 0.000. Under goal-pass they are ordered — `executor_alone` 0.213 <
`prompt_only` 0.250 ≈ `fixed_k` 0.252 — and all three ran the same prompt, so that ordering is
attributable to the plan and the corrections respectively. `fixed_k`'s +0.2 pp over `prompt_only`
is the weaker signal: corrections bought almost nothing under a prompt the executor could not use.

**The ASK channel fired once, and it worked.** One episode of 114 escalated (`n_asks: 1`) — one live
`codex` call among 114 cached replays, 34,650 tokens, correctly tagged `provider="codex"` against
114 `provider="cache"`. That episode solved its task with `goal_pass_rate 1.0`. Its counterfactual,
the same task and seed in `executor_alone`, scored **0.0** goal-pass and failed. n=1 proves no
effect size, but HJ-1 recorded zero ASKs in 114 episodes and so demonstrated nothing either way.

### What did NOT run

**The state probe produced no data, in two successive jobs.** `25400264` aborted at phase 4 on the
cached-packet resolution bug (commit `1e3dc38`); `25401397` reached both probe phases and both died
on `timeout 1800` (rc=124). `state_probe.py` buffered every result in memory and wrote once at the
end, so ~60 minutes of probe work was discarded rather than partially recovered. That is a briefing
failure — the unit's brief specified the metrics and denominators in detail and never required the
script to survive being killed — compounded by a 1800 s budget set without measuring the per-point
cost. Fixed under U-G: append-per-point JSONL, exact `(run_id, step)` resume, an in-process
`--time-budget-s` that writes a valid partial report and exits 0, and a depth-stratified
`--max-points 300` sampled from a fixed seed so both models are probed on identical points.

Qwen3-8B itself is not implicated: it served healthy in 121 s under `HF_HOME=~/.cache/huggingface`.
**Granite vs Qwen remains undecided**, and no evidence bearing on it has been collected.

---

## HJ-1.5 attempt 3 — the probe ran to completion, and every point of it is void (2026-09-17)

Job `25401566`, 8 h walltime, cancelled by me at 00:41 elapsed after the Granite probe
finished and before the Qwen phase began. Artifacts preserved at
`~/sidekick_data/probes/probe_granite8b.json` (+ `.partial.jsonl`).

**The resumability work from U-G did its job.** `n_planned 300, n_completed 300,
budget_exhausted false` — the first probe attempt of three to produce a complete report,
within budget, with per-point JSONL flushed throughout. That part is sound and is retained.

**Every one of the 300 points measured the wrong thing.** Reported numbers, all void:

| metric | reported | why it is meaningless |
|---|---|---|
| primary agreement | 0.033 (9/272) | measured against the wrong environment, **and all 9 are vacuous**: verified by `jq`, 9 of 9 had an empty gold API set. Under the corrected metric this run scored **0 of 260** — exactly zero, as a model never shown the API surface should |
| depth 1-5 / 6-10 / 11+ | 0.080 / 0.012 / 0.000 | same |
| `state_equivalent` | 0.000 (0/262) | metric is **sound**; the zero is a true consequence of the defect |
| `hash_match` | 0.000 (0/262) | expected near-zero by construction; uninformative either way |

### Defect 1 — the probe ran in `MockEnv`, not AppWorld

- `src/sidekick/replay.py:88` (pre-fix): `world = env or MockEnv()`.
- `scripts/setup/state_probe.py:509` (pre-fix): `replay_prefix(events_path, k)` — no `env`.
- Therefore every point replayed real AppWorld gold trajectories into the toy
  four-function file world, then rendered the prompt from **that** world's
  `instruction` and `api_docs_prompt` (`state_probe.py:516-517`, the second using
  `getattr(world, "api_docs_prompt", "")`, whose `""` default would have hidden a missing
  attribute as well).
- The model was therefore asked to predict the next AppWorld action while being told its
  task was "Copy the exact contents of inbox.txt into outbox.txt"
  (`src/sidekick/environments/mock_env.py:104`) and that its available API was
  `list_files / read / write / delete_all` (`mock_env.py:17`).

**Evidence, in the artifact.** 51 distinct predicted actions across 300 points, of which
211 are file-listing variants: `print(list_files())` x95, `files = list_files()` x47,
`apis.api_docs.list_files()` x18, and three further spellings x17 each. Across 78
trajectories spanning venmo, supervisor and phone tasks. The model wrote the diagnosis
itself, in `model_raw` of step 0: it states the task is to copy `inbox.txt` to
`outbox.txt`, observes that the replayed history calls `apis.phone...`, and calls that
"unrelated".

**What exposed it was not the headline.** 3.3% was plausible and would have been believed.
The tell was `state_equivalent` returning **exactly** 0 across 262 independent trials — a
metric that never fires once is more often broken than true. Auditing it found it sound,
which relocated the suspicion to the inputs rather than the scorer.

### Defect 2 — the agreement metric counts an empty set as agreement

Independent of defect 1, and it survives the environment fix untouched. `agreement`
compares the set of `apis.<app>.<api>` ids in gold's code against the model's. When gold's
action calls **no** API — pure code printing a value already in scope, e.g.
`print({"credential_count": len(passwords)})` — the sets are both empty and compare equal,
so any model action that also calls no API scores as agreement. 12 of 272 scorable gold
actions call no API, so the metric carries a vacuous-pass floor.

All sampled `agreement == true` records were of exactly this shape: gold formatted a local
variable, the model emitted `print(list_files())`, scored as agreement.

Fixed by excluding gold-no-API points from both numerator and denominator
(`agreement_defined = False`), with `n_gold_no_api` reported per bucket so the shrinking
denominator is visible, and `gold_api_ids` / `pred_api_ids` now stored on every step
record — their absence is what made establishing this take source archaeology rather than
a `jq` query.

### Effect on the pre-registered decision rule

**The four-row rule at RUNS.md:353 was NOT applied and no evidence bearing on Granite vs
Qwen3-8B has been collected.** Three GPU attempts, still undecided. The first two lost the
run; this one lost the *conclusion*, which is the worse failure, and is the only one that
had to be caught by reading rather than by a non-zero exit code.

The thresholds (>= 40%, < 15%) were pre-registered against the metric as it behaved
*before* defect 2 was fixed. The correction is strictly stricter — it removes free passes
and adds none — so a threshold set against the looser metric remains conservative under
the stricter one, and the rule stands unamended. Recording this because a threshold whose
metric changed underneath it is exactly the kind of silent amendment a prereg exists to
prevent.

### What is retained from this attempt

- The resume/budget machinery, validated end to end (300/300, budget not exhausted).
- The depth-stratified 300-point sample at seed 0, so the rerun probes identical points.
- Measured per-point cost, which the earlier `timeout 1800` failures lacked.

### HJ-1.5 attempt 4 — the fixed probe reported the broken probe's numbers (2026-09-17)

Job `25401656`, submitted after both defects above were fixed and committed
(`82442ae`). Cancelled at 00:41 elapsed. **No new data.**

It skipped phase 5 entirely and resumed the previous run's report. `probe_granite8b.json`
was still at the output path from attempt 3, carrying `budget_exhausted: false` and
`n_completed: 300`, so `probe_report_status` classified it `complete` and the probe was
not run. Confirmed by `cmp`: the file was byte-identical to the attempt-3 artefact
preserved at `~/sidekick_data/probes/`, and lacked both fields the fixed code emits
(`n_gold_no_api`, `gold_api_ids`).

**The resume guard was not wrong.** It was hardened earlier the same evening specifically
to distinguish a complete report from a budget-exhausted partial, and it did that
correctly. The artefact was stale, and nothing inside it said so.

⚠ **The near-miss is the finding, not the wasted job.** Only Granite had a stale *full*
report. Qwen had only a stale `.partial.jsonl` (136 KB, from attempt 3's Qwen phase before
it was cancelled), so Qwen would have re-run and partially resumed. The job was therefore
on course to produce a **comparison between a contaminated arm and a mostly-clean one**,
and feed it to the pre-registered rule at RUNS.md:353 — which reads "< 15% on Granite and
materially better on Qwen3-8B" as *switch the executor before J3*. An artefact would have
selected the executor for the rest of the project.

**Asymmetric staleness is more dangerous than total staleness**, because the output still
looks like a comparison. Total staleness reproduces the old numbers exactly and is
therefore noticeable; partial staleness produces a novel, plausible, wrong result.

Fixed in `51ce7be`, not by remembering to delete files. `PROBE_SCHEMA_VERSION = 2` is
stamped into the report and into every `.partial.jsonl` record; resume discards mismatched
or unversioned records with a visible count; the PBS guard reports `stale` and treats it
as a missing report. The version is read by importing `state_probe` rather than
hard-coded twice, because a drifted version check is worse than none — it looks like
protection.

Both attempt-3 artefacts and the attempt-3 Qwen partial are preserved under
`~/sidekick_data/probes/` as the evidence for this entry. The live output path was
emptied before resubmission.

**Granite vs Qwen3-8B: still undecided, now after four attempts.**

### HJ-1.5 attempt 5 — the probe worked, and Granite stays (2026-09-17)

Job `25401677`, commit `176fcb1`. **`probe_granite8b.json`: 300/300 points,
`schema_version: 2`, `budget_exhausted: false`, 78 trajectories, `lora_name: null`
(untrained base — this is the pre-SFT baseline).** Output path verified empty before
submission, so nothing was resumed.

**Primary agreement: 56 / 250 scorable = 0.224.**

| bucket | n | scorable | agreement | rate | parse_error | state-equiv |
|---|---|---|---|---|---|---|
| k 1–5 | 100 | 90 | 19 | 0.211 | 20 | 0.720 |
| k 6–10 | 100 | 80 | 10 | 0.125 | 34 | 0.573 |
| k 11+ | 100 | 80 | 27 | 0.338 | 23 | 0.725 |
| **overall** | **300** | **250** | **56** | **0.224** | **77** | **0.676** |
| value-forwarding subset | 204 | 185 | 41 | 0.222 | 56 | 0.670 |

`n_scorable` excludes 12 gold actions calling no API (the agreement-vacuity fix from
`3a2cf46`) and 28 gold `COMPLETE` actions, which are non-code and therefore unscorable on
an API-set metric.

**Verdict against the pre-registered table at RUNS.md:353 — row 3, "between".**
0.224 is above the 0.15 switch threshold and below the 0.40 clean-pass threshold, and it
does **not** degrade with depth. Consequence, as pre-registered: *proceed on Granite and
add a third seed to HJ-2B*. That seed is already collected (job `25401588`, 2026-09-17),
so the remedy the rule prescribes was already in hand when the rule fired.

🔺 **The switch branch was arithmetically closed before the run finished.** Row 2 requires
< 0.15 on Granite. At 266/300 points there were already 52 agreements against an expected
~250 scorable, so the final rate could not fall below 0.208 even had every remaining point
missed. The Qwen3-8B probe still runs — for the record and for row 4 — but it cannot
change the executor choice.

**Agreement does not collapse with depth; it rises.** That was the stated condition that
would have flipped the recommendation to Qwen, and it did not happen. Removing points
where the model emitted nothing parseable:

| bucket | parsed points | agreement | rate |
|---|---|---|---|
| k 1–5 | 58 | 14 | 0.241 |
| k 6–10 | 53 | 11 | 0.207 |
| k 11+ | 74 | 31 | **0.418** |
| **overall** | **185** | **56** | **0.302** |

The raw dip at k 6–10 is a **format** dip, not a capability dip: that bucket carries 34 of
the 77 parse errors. Corrected for it, agreement rises monotonically with depth — Granite
is most able to predict the teacher exactly where the teacher's remaining moves are most
constrained.

**77 of 300 points (25.7%) produced no parseable action.** All 77 have `model_code: null`.
The raw text shows the shape: the model solves the step and then narrates its own
verification instead of emitting the canonical action — e.g. *"We have a result:
COMPLETE: 79. However, we need to ensure that the year is 'this year'… we should
double-check that the pagination worked correctly"*. This is the failure class SFT on
assistant-masked teacher turns is the direct instrument for, and it is a quarter of the
gap. Note the honest framing: 0.224 is the pre-registered number and a parse failure *is*
a failure to predict the teacher, so 0.224 stays the headline; 0.302 is the decomposition,
not a competing metric.

⚠ **`hash_match` is unusable and no number should be quoted from it.** It is 0 across all
262 defined points and 0.000 in every bucket — including **all 18 points where the model's
emitted code is byte-identical to the gold code**. Identical code executed from an
identical replayed prefix must produce an identical state hash, so the zero is the metric,
not the model. This is the strict secondary from `PLAN.md`; it gates nothing, and the
comparison the J3 gate uses is primary agreement. Filed rather than chased mid-run.

`state_equivalent` — the secondary that does carry weight — is healthy at 0.676: when
Granite picks the wrong API it usually leaves the world in a state from which the
teacher's next action still succeeds. Recoverable errors, not destructive ones, which is
the more forgiving regime for a policy that will be corrected during J4.

**Executor decision: granite-4.2-8b. Settled after five attempts.** Attempts 1–2 were lost
to harness defects, 3 measured a toy environment, 4 reported 3's numbers from a stale
artefact, and 5 is the first that measured what it claimed to.

#### ⚠ Defect #18, found 2026-09-17 while reading the Qwen arm: the probe does not use the serving configuration

`scripts/setup/state_probe.py:668` builds its `VLLMExecutor` with **no
`chat_template_kwargs` and no `stop`**:

```python
executor = VLLMExecutor(
    model=args.model, base_url=args.base_url, lora_name=args.lora_name,
    temperature=0.0, timeout_s=120.0,
)
```

`executor.py:74` stores `chat_template_kwargs or None` and `:101` sends the field only
`if ctk`; `:104` does the same for `stop`. So the probe requests fall through to the
**template defaults** — for Granite 4.2, `enable_thinking: True` — and carry **no stop
sequences**. Every eval config sets both deliberately, and says why in comments that
describe this exact outcome:

- `executor.py:72-73` — "spends the whole budget reasoning without ever emitting an
  action — measured 2026-09-15: 3072 output tokens of deliberation and no fenced block."
- `executor.py:76-80` — "Without them Granite writes an action, then invents the output
  it expects, then reasons over its own invention for the rest of the budget."

The second comment describes, almost verbatim, the raw text cited above as evidence of a
format failure (*"We have a result: COMPLETE: 79. However, we need to ensure…"*). The
77 Granite and ~99 Qwen parse errors are therefore substantially **an artefact of the
probe's own configuration**, not a property of either model at serving time.

**What this does and does not change.**

- ✅ **The executor decision stands, unweakened.** Both models were handicapped
  identically, so the comparison is apples-to-apples, and Granite wins it decisively:
  0.224 against Qwen3-8B's ~0.105 at roughly half the parse-failure rate. Moreover both
  the "≥ 0.40" and the "between" rows of the rule prescribe *train Granite*, so no
  reading of the corrected number could have selected a different action.
- ⚠ **0.224 is a floor, not an estimate.** Granite's agreement under its real serving
  configuration is higher by an unknown margin, plausibly much higher given that a
  quarter of its points failed to parse at all. **Do not quote 0.224 as "Granite's
  agreement" without this caveat**; quote it as agreement measured without the serving
  template or stop sequences.
- 🔺 **It threatens the J3 gate, which is the live problem.** The gate reads "probe
  agreement up vs J1". The post-SFT probe in `hj3_eval.pbs` shares this defect, so the
  paired delta is at least internally consistent — but `sft_b` is trained on
  conversations rendered *without* thinking blocks and is served with
  `enable_thinking: false`, so probing it with thinking **on** measures the adapter off
  its own distribution. A trained adapter could easily look flat or worse for a reason
  that has nothing to do with training.

**Recommended, and flagged rather than done:** make the probe take the same
`chat_template_kwargs` and `stop` the arms use, then re-measure the Granite pre-SFT
baseline before J3's gate is read (~2 h GPU). Fixing the probe *without* re-baselining is
the worse option, because it would leave the post-SFT number incomparable to the J1
number it is supposed to be compared against. Leaving both as they are is defensible but
measures the wrong thing twice.

This is the 18th harness defect on this project and the eighth to return believable
numbers rather than an obvious failure. See [[silent-zeros-in-eval-harnesses]] — point 5
of that memory is literally "a new model family needs its output format checked against
the parser before its arm is trusted", which is what the Qwen arm's 48% parse rate
surfaced here.

#### The Qwen3-8B arm, for the record (job 25401677, same run)

`probe_qwen3_8b.json`: 300/300 points, `schema_version: 2`, `budget_exhausted: false`,
78 trajectories, `lora_name: null`.

| | Granite 4.2-8B | Qwen3-8B |
|---|---|---|
| scorable points | 250 | 250 |
| agreements | 56 | 26 |
| **primary agreement** | **0.224** | **0.104** |
| parse errors (of 300) | 77 | 139 |
| state-equivalence | 0.676 | 0.431 |
| hash match | 0 (metric broken) | 0 (metric broken) |

**The comparison is genuinely paired.** Both arms report the identical point structure —
250 scorable, 12 gold actions calling no API, 28 gold `COMPLETE`, 262 hash-defined — which
is what `--seed 0 --max-points 300` against the same campaign root is supposed to
guarantee, and here demonstrably did. Same points, same replayed prefixes, same metric.

**Granite wins on every axis**: roughly twice the agreement, roughly twice the
state-equivalence, and a little over half the parse failures. There is no reading of this
table on which switching the executor to Qwen3-8B is the better move, which retires the
question rather than merely answering it.

⚠ Both arms carry defect #18 (below/above as filed): neither was sent the serving
chat-template kwargs or stop sequences. That inflates **both** parse-error counts and
depresses **both** agreement rates. It does not bias the comparison — the handicap is
identical and the point sets are the same — but it does mean **neither absolute number is
the model's serving-time agreement**, and Qwen's 0.104 in particular should not be quoted
as "Qwen3-8B cannot do this task". Qwen3-8B has its own thinking mode, so a family whose
template defaults differ from Granite's is exactly where an unconfigured probe is least
trustworthy — `silent-zeros-in-eval-harnesses` point 5, arriving on schedule.

The honest claim is the relative one, and it is the only claim the decision needed:
**under identical conditions, Granite is about twice as good at predicting the teacher's
next action, and Qwen is not a cheap fix for a marginal executor.**

---

## J3 — HJ-3a SFT(b): the adapter (2026-09-17)

### Training — job 25401722, exit 0

`scripts/pbs/train_sft.pbs`, submitted with
`-v DATA_JSONL=…/sft_b_s123_p075.jsonl,ADAPTER_OUT=…/adapters/sft_b_s123_granite8b`
so the frozen 133-trajectory dataset and its adapter are untouched.

| | |
|---|---|
| data | `sft_b_s123_p075.jsonl`, **230 trajectories** (196 solved + 34 partial ≥ 0.75) |
| `data_sha256` | `f56fe6ea21b0…5ef812` |
| base | `ibm-granite/granite-4.2-8b` |
| adapter | `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_s123_granite8b` (791 MB) |
| LoRA | r=64, α=128, dropout 0.05, q/k/v/o/gate/up/down |
| schedule | 2 epochs, lr 1e-4 cosine, effective batch 8 (grad-accum 8), bf16, grad checkpointing |
| masking | `manual_assistant_token_spans` — not `{% generation %}` markers |
| max_length | 32768 |
| **final train loss** | **0.1414** |
| runtime | 2059 s (34 min) on one H100, plus a 103 s dry-run |
| commit | `e4580d8` |

Loss fell 0.566 → 0.073 with token accuracy 0.902 → 0.977 and grad-norm settling
7.0 → 0.45. Nothing diverged; the cosine schedule annealed to ~0 as intended.

🔺 **The dataset identity was verified observationally, not assumed.** PBS `-v` silently
failing to propagate would have trained on the superseded 133-trajectory file and produced
a perfectly plausible adapter measuring the wrong thing — the defect shape that has cost
this project three probe attempts. Three independent confirmations:

1. the dry-run wrote to `…sft_b_s123_granite8b_dryrun` while the old
   `…sft_b_granite8b_dryrun` kept its previous-day mtime;
2. `manifest.json` records `"data": "…/sft_b_s123_p075.jsonl"` with the matching sha256
   and `"n_sequences": 230`;
3. the job log's own `[sft] data=…` line and the PBS epilogue's `Submit_arguments` both
   name the `s123_p075` file.

The 2-epoch run is `dry_run: false`, `epochs: 2.0`, and its `effective_batch: 8` explains
the ~28.75 optimiser steps per epoch (230 / 8).

### Evaluation — job 25401780, submitted 2026-09-17 02:3x, queued

`scripts/pbs/hj3_eval.pbs`, walltime 08:00, four phases on one vLLM server holding
`granite-4.2-8b` with `--lora-modules sft_b=…sft_b_s123_granite8b`:

1. **arm A** `executor_alone` (`lora_name: sft_b`), dev 57 × seeds 1,2 →
   `hj3_sft_b_exec_20260917`. No `--expect-planner`: this arm never calls the planner and
   the flag would fail a healthy arm.
2. **arm B** `sft_plan` with `packet_source: hj1b_planner_20260915`, dev 57 × seeds 1,2 →
   `hj3_sft_plan_20260917`, gated `--expect-planner --expect-model gpt-5.6-luna`.
3. **pre-SFT baseline probe** — same server, **no** `--lora-name` → base model →
   `probe_granite8b_serving.json`.
4. **post-SFT probe** — same server, `--lora-name sft_b` → `probe_sft_b.json`.

Phases 3 and 4 are the J3 gate's "probe agreement up vs J1" criterion, **re-based**. They
do not compare against `probe_granite8b.json`, because that report carries defect #18 (no
serving chat-template kwargs or stop sequences) and `sft_b` is trained on renderings
without thinking blocks. Comparing a thinking-off adapter against a thinking-on baseline
would measure the adapter off its own distribution. Both new probes share
`invoke_state_probe`, so their sampling arguments and template/stop cannot drift; only
`--lora-name` and `--out` differ. They are `PROBE_SCHEMA_VERSION 3`.

**All four output paths were verified absent before submission** —
`probe_granite8b_serving.json`, `probe_sft_b.json`, `hj3_sft_b_exec_20260917`,
`hj3_sft_plan_20260917`. A stale artefact at an output path silently voided job 25401656
earlier the same night; the schema-version guard now catches that class, but checking the
paths costs nothing and catches the rest.

**Gate, restated before the numbers exist:** `sft_plan` TGC > 0 with a bootstrap CI
excluding 0, paired against HJ-1R's `prompt_only` on the same tasks and the same cached
plans; and probe agreement up, phase 4 against phase 3. Below the gate: stop and decide
before further GPU spend.

### J3 arm A — `executor_alone(sft_b)` on dev, complete (2026-09-17)

Campaign `hj3_sft_b_exec_20260917`, job `25401780`, adapter `sft_b_s123_granite8b`
served as LoRA alias `sft_b`. **114/114 episodes, zero crashes.**

Paired against `hj1r_exec8b_20260916` — the same arm, same 57 dev tasks × 2 seeds, same
multi-turn executor prompt, differing **only** in the adapter.

| | untrained | SFT(b) |
|---|---|---|
| solved / 114 | 2 | **24** |
| TGC | 0.0175 | **0.2105** |
| mean goal_pass_rate | 0.190 | **0.614** |
| mean steps | 30.16 | **19.17** |
| `limit` episodes | 37 | 15 |
| planner calls | 0 | 0 |

**Paired bootstrap, `hj1_gate.py`, 10,000 resamples, 114 pairs, 0 dropped:
+19.3 pp TGC, 95% CI [12.28, 27.19].** The interval excludes zero.

**This answers J3's stated question — "is the 8B trainable at this data scale" — yes.**
230 teacher trajectories, drawn from a train split hard-capped at 90 tasks, took a local
8B executor from 2 solved to 24 on held-out dev tasks, with no planner involved at
inference at all (`planner_calls: 0` in both arms).

🔺 **The step count is the more interesting number than the pass rate.** The untrained
executor averaged 30.16 steps against a 40-step ceiling and hit `limit` in 37 of 114
episodes: it was not failing to know what to do so much as failing to stop. SFT halved
`limit` episodes and cut mean steps by a third. Two independent signals of the same
learned behaviour — termination — which is exactly what training on *complete* teacher
trajectories with the terminal `COMPLETE` preserved should produce, and is the direct
payoff of the terminal-action masking done when the partial-credit set was built.

**Read TGC beside goal_pass_rate here, not instead of it.** Mean goal-pass is 0.614 while
TGC is 0.2105, because AppWorld success requires *every* goal-check to pass. Of the 90
unsolved episodes, only 2 scored 0.0; the modal unsolved score is 0.5, with a long tail at
0.667–0.833. The adapter completes most of most tasks and misses one or two checks. Any
write-up that quotes 0.21 alone will substantially understate what was learned — and,
symmetrically, quoting 0.614 as a success rate would overstate it.

⚠ **Not the gate.** The pre-registered J3 gate turns on arm B (`sft_plan`) paired against
HJ-1R's `prompt_only`, plus the probe delta. Arm A is supporting evidence, and it is
reported here because it is complete, not because it decides anything.

**Baselines re-measured this session for the record**, both under the fixed prompt, both
n=114 with all results present:

| HJ-1R arm | solved | TGC | mean gpr | `limit` |
|---|---|---|---|---|
| `executor_alone` | 2 | 0.0175 | 0.190 | 37 |
| `prompt_only` | 6 | 0.0526 | 0.288 | 40 |

✅ **The previously-flagged "HJ-1R `prompt_only` is short 6 crashed episodes" item is
closed as a non-issue.** Verified directly: 114 `events.jsonl`, 114 `result.json`, zero
directories with events but no result, and no `crash` error type in the arm. No re-run is
needed and no ledger number needs revising.

### J3 arm B — `sft_plan(sft_b)` on dev, and the gate (2026-09-17)

Campaign `hj3_sft_plan_20260917`, job `25401780`. **114/114 episodes, zero crashes.**
Plans replayed from `hj1b_planner_20260915` via `CachedPacketPlanner`, so the arm spends
**zero live hosted-planner calls** — `planner_calls_total: 114` is exactly one cached
packet per episode.

Paired against `hj1r_prompt_only_20260916`: same 57 dev tasks × 2 seeds, same cached
plans, same multi-turn executor prompt. **The only difference between the two arms is the
LoRA adapter.**

| | `prompt_only` untrained | `sft_plan` (sft_b) | teacher `planner_alone` |
|---|---|---|---|
| solved / 114 | 6 | **49** | 78 |
| TGC | 0.0526 | **0.4298** | 0.684 |
| SGC | 0.000 (0/38) | **0.2895** (11/38) | 0.447 (17/38) |
| mean goal_pass_rate | 0.288 | **0.713** | — |
| mean steps | 31.79 | **17.68** | — |
| `limit` episodes | 40 | 15 | — |
| live planner calls | 0 | **0** | 936 |

## ✅ GATE — primary criterion PASSED

Pre-registered: *`sft_plan` TGC > 0 with a bootstrap CI excluding 0, paired against
HJ-1R's `prompt_only` on the same tasks and the same cached plans.*

**`hj1_gate.py`, 10,000 bootstrap resamples, 114 pairs, 0 dropped from either arm:
+37.72 pp TGC, 95% CI [28.07, 47.37].** Report at
`/scratch/n12194778/sidekick/results/hj3_gate.json`. The interval clears zero by 28
points; this is not a marginal pass.

**The interpretation that matters.** `prompt_only` and `sft_plan` receive the *identical*
plan for the identical task and seed. HJ-1's central negative finding was that 936 planner
calls bought nothing — one plan changed nothing, eight expert reviews per episode changed
nothing. This arm shows why: **the plans were never the bottleneck, the executor was.**
Hold the plan fixed, train only the executor, and the same plans go from 6 solved to 49.

A LoRA-tuned local 8B replaying cached plans reaches **63% of the hosted frontier
teacher's TGC** and **65% of its SGC**, at zero live planner cost, on held-out dev tasks.
The training set was 230 trajectories drawn from a train split hard-capped at 90 tasks.

⚠ **The gate's second criterion is not yet in.** It also requires probe agreement to rise
post-SFT, measured against the re-based pre-SFT baseline (phases 3 and 4 of this job, both
at `PROBE_SCHEMA_VERSION 3` under the serving configuration). Until those land the gate is
**passed on its primary criterion only**, and J4 stays unsubmitted.

⚠ **Read TGC beside goal_pass_rate, as in arm A.** 0.4298 against a mean goal-pass of
0.713 means most unsolved episodes are near-misses; AppWorld requires *every* goal-check.
Quoting either number alone misrepresents the arm in opposite directions.

⚠ **`steps_mean` 31.79 → 17.68** repeats arm A's finding independently on a second arm:
the untrained executor ran to the ceiling, the trained one terminates. `limit` episodes
fell 40 → 15.

**Comparison hygiene**: both arms are n=114 with every episode present and no dropped
pairs, so the paired statistic uses the full sample. The `prompt_only` arm was verified
complete this session (114 `events.jsonl`, 114 `result.json`, zero mismatches).

### J3 probes — paired pre/post-SFT, and the gate's second criterion (2026-09-17)

Both probes ran in job `25401780` against the one vLLM server holding
`granite-4.2-8b` with `--lora-modules sft_b=…sft_b_s123_granite8b`, through the shared
`invoke_state_probe` helper. **The only differences between the two invocations are
`--lora-name` and `--out`**; sampling arguments, campaign root, chat template kwargs and
stop sequences are byte-identical by construction.

| | pre-SFT base (`probe_granite8b_serving.json`) | post-SFT (`probe_sft_b.json`) |
|---|---|---|
| `lora_name` | `null` | `sft_b` |
| points | 300/300 | 300/300 |
| scorable | 250 | 250 |
| **agreement** | 64 → **0.256** | 123 → **0.492** |
| state-equivalence | 0.866 | **0.920** |
| parse errors | 2 | 2 |
| depth 1–5 | 0.167 | **0.489** |
| depth 6–10 | 0.213 | **0.388** |
| depth 11+ | 0.400 | **0.600** |
| schema | 3 | 3 |

## ✅ GATE — second criterion PASSED. J3 passes in full.

Pre-registered: *probe agreement up vs the pre-SFT baseline.* **0.256 → 0.492, +23.6 pp,
improving at every depth stratum** (+32.2, +17.5, +20.0 pp).

Together with the +37.72 pp TGC result above, **both J3 gate criteria are met** and the
plan's "below the gate: stop and decide" branch is not taken.

**Why the probe result matters more than the TGC result.** Task completion can rise for
many reasons. Agreement measures something narrower and harder to fake: given a *correct*
teacher history replayed into a fresh world, does the executor choose the same API call
the teacher chose? That rose at every depth. The executor did not merely get luckier — it
got better at the thing the sidekick architecture depends on, which is standing in for the
planner on the next action.

**Point-sequence identity was verified, not assumed.** At 86 points into the post-SFT run
the two `.partial.jsonl` files were compared on `run_id|k` and found identical for all 86,
with `n_defined` 71 in both; the like-for-like figure at that prefix was 25/71 vs 44/71.
The final reports agree on `n_scorable` (250), `n_gold_no_api` and `n_gold_noncode`, which
is what `--seed 0 --max-points 300` against one campaign root should guarantee.

### Defect #18 is confirmed by direct measurement

The re-based baseline is the same base model on the same 300 points as
`probe_granite8b.json`, differing only in that the serving chat template and stop
sequences are now sent:

| | defect-#18 run (v2) | re-based (v3) |
|---|---|---|
| parse errors | 77 / 300 (25.7%) | **2 / 300 (0.7%)** |
| agreement | 0.224 | **0.256** |
| state-equivalence | 0.676 | **0.866** |

🔺 **The 25.7% parse-failure rate was entirely the harness.** It was written up earlier
the same night as a Granite format-discipline weakness, quoting the model's own narration
as evidence. The model had been asked to think aloud by a probe that omitted
`enable_thinking: false`. The earlier decomposition survives intact, though: agreement
among *parsed* points in the defective run was 0.302, and once essentially everything
parses the overall figure is 0.256 — the same quantity, now measured directly.

The state-equivalence jump (0.676 → 0.866) is the clearest single symptom: when the model
emits an action instead of narrating, its wrong actions are far more often harmless ones
the teacher's next step can still recover from.

**`probe_granite8b.json` (v2) is superseded.** It must never be compared against a v3
report; `PROBE_SCHEMA_VERSION` enforces that mechanically.

🔺 **Amended 2026-09-17.** This paragraph previously kept the v2 Granite-vs-Qwen comparison
alive on the grounds that "both arms carried the identical handicap". The *configuration*
was identical; the *damage* was not. The missing `enable_thinking: false` cost Qwen
**139/300** points to parse errors against Granite's **77/300** — nearly double. That is
plausibly a property of the misconfiguration meeting a reasoning-first model rather than of
Qwen's ability to act, so the raw 0.224-vs-0.104 gap overstates the real one. Correcting
for it on parsed points only gives Granite ≈0.301 vs Qwen ≈0.194 (proportional allocation
of parse errors across scorable points — an estimate, not a measurement); scaling by the
0.256/0.301 ratio Granite actually exhibited when fixed puts Qwen near **0.165**.

**Do not quote 0.224 vs 0.104 as the reason Granite was chosen.** See the selection
rationale below, which does not depend on Qwen at all.

---

## J4 — HJ-2C correction data on the trained policy (job 25401962, 2026-09-17)

`fixed_k` with k=5, run **on `sft_b`** rather than on the untrained executor. Campaign
`hj4_correction_train_20260917`, config `configs/hj4_correction.yaml`, PBS
`scripts/pbs/hj4_correction.pbs`, walltime used **01:21:15** of 06:00, `Exit_status: 0`,
all phases rc=0, archived to `~/sidekick_data/hj4_correction_train_20260917`.

Split **train**, 90 tasks x seeds 1,2 = 180 episodes, 6 workers. Plans came from J2's
teacher campaign (`packet_source: hj2b_planner_train_20260916`, `packet_system:
planner_alone`), so the same task+seed gets the identical plan the teacher had; only the
**reviews** went live to `gpt-5.6-luna`.

| | value | note |
|---|---|---|
| episodes | 180 / 180 | none skipped, none missing |
| solved | 104 | |
| TGC | **0.577** | 🔺 **train split — not comparable to any dev figure** |
| mean goal-pass-rate | 0.829 | |
| interventions | **488** | 2.71 / episode |
| hosted planner calls | 669 | budget was <= 1,450 |
| mean steps | 15.6 | |
| errors | 12 | `crash` 3, `limit` 9 |

Gate passed with `--gate --expect-planner --expect-model gpt-5.6-luna`.

**Read the 0.577 as a data yield, not a result.** This is the *train* split, which no arm
in this campaign has ever been evaluated on, and the executor is being corrected five
steps in — it is not an eval arm and must never be quoted beside dev's 0.4298.

Two things in the table do carry meaning. **488 interventions across 180 episodes is 2.71
per episode**, against the plan's estimate of about 2 and its ceiling of 8 — so the
correction budget was sized correctly and `sft_b` is finishing short enough episodes that
the reviewer is not being called on every step. And **669 planner calls against a 1,450
budget** means J5's dataset was bought for under half the allowance.

`limit` at 9/180 (5.0%) is consistent with J3's dev `sft_plan` (15/114, 13.2%) once the
easier split is accounted for; it is not a new truncation problem.

### The 3 crashes are defect #19, and they are censoring rather than noise

Three episodes died with a 400 from vLLM: `fixed_k/1/2a163ab_2`, `fixed_k/2/afc0fce_1`
and `fixed_k/2/22cc237_1` (enumerated by `grep -rl '"error_type": *"crash"'` over the
campaign root, 2026-09-17, before the recovery job purged them). Cause, traced and
fixed in commit `03640a0`: a single AppWorld observation of **604,915 characters** — one
message larger than the entire 32,768-token context — reached
`fit_messages_to_budget`, which correctly returned `representable=False`, and
`executor.py:89` destructured that flag into `_` and sent the prompt anyway. The 400
backstop could not save it either, because it deletes from the *middle* while the
oversized message was last.

🔺 **These 3 are not a random 1.7% loss.** A crash triggered by large observations removes
exactly the tasks whose API calls return large result sets, so the surviving 177 are
biased toward tasks with small result sets, in a predictable direction. The affected
episodes record `goal_pass_rate: null` and leave the denominator silently.

The size of the bias is small enough not to threaten any J4 conclusion — 488 interventions
would gain roughly 8 — but the *kind* of data lost is disproportionately valuable to J5:
these are precisely the states where the right correction is "you dumped an unpaginated
result set, paginate instead", which is a behaviour SFT(c) should be learning and which
cannot appear in a dataset that crashes whenever it occurs.

**Recovery: job 25402025**, resubmitting the same PBS script against the same campaign id.
`hj4_correction.pbs:120` runs `campaign_summarize --purge-broken` before the arm, which
drops the 3 broken episode directories, and the runner's resume skips the 177 complete
ones — so only the failures re-run, against the fixed code (the runner imports from
`${REPO}/src` at run time, so the committed fix applies without a rebuild). The dataset
build for J5 must wait for this job, not for 25401962.

### Recovery job 25402025 — complete, and it did NOT validate the fix

`Exit_status: 0`, walltime **00:06:04**, one H100 on `gpu0n007`. `--purge-broken` dropped
the 3 broken directories (verified: results went 180 → 177 with 0 crashed), resume skipped
the 177 survivors, and only the 3 failures re-ran. All three completed with real scores and
`error_type: null`:

| episode | goal-pass-rate | outcome |
|---|---|---|
| `fixed_k/1/2a163ab_2` | 0.667 | not solved |
| `fixed_k/2/afc0fce_1` | 0.444 | not solved |
| `fixed_k/2/22cc237_1` | 0.750 | not solved |

**Campaign totals, before → after recovery:**

| | 25401962 | 25402025 | delta |
|---|---|---|---|
| episodes | 180 (3 void) | **180** | 3 real |
| solved / TGC | 104 / 0.577 | 104 / **0.577** | unchanged |
| mean goal-pass-rate | 0.829 | **0.839** | +0.010 |
| interventions | 488 | **495** | +7 |
| hosted planner calls | 669 | **675** | +6 |
| errors | 12 (3 crash, 9 limit) | **9 (all limit)** | **0 crashes** |

The +0.010 on mean goal-pass-rate is the censoring correction made visible: the crashed
episodes had been entering that mean as `null`, which the tally coerced to 0.

🔺 **Correction to what was written above, before this job ran.** The entry predicted that
recovery would capture "precisely the states where the right correction is *you dumped an
unpaginated result set, paginate instead*". **It did not, and the claim is withdrawn.**

Every step of all three re-runs records `n_chars_elided: 0` and `representable: true`
(16, 25 and 23 steps respectively) — so the new elision path **never fired**. The largest
single event line in the three re-runs is 22,647 characters, against the 604,915-character
observation that caused the original crash. At `temperature: 0.7` the executor simply took
different actions the second time and never issued the call that returned the huge result
set.

Two consequences, and they point in opposite directions:

- **The sample bias is genuinely fixed.** All 180 episodes now carry a real
  `goal_pass_rate`, nothing is silently absent from a denominator, and J5's dataset is
  built from a complete campaign. That was the point of the recovery and it succeeded.
- **This run is not evidence that defect #19 is fixed.** The fix's only validation remains
  the unit tests (6 new, including train/serve elision parity; 202 passed, 1 skipped).
  The instrumentation is confirmed live — `n_chars_elided` and `representable` are being
  written into `usage.raw` on every step — but it has never yet been observed firing on
  real oversized input. The first production exercise of the elision path is still ahead,
  and whoever sees a non-zero `n_chars_elided` should check the rendered prompt by hand.

Do not describe the elision path as "proven in production" on the strength of this job.

### What a J4 intervention actually is — and why it changes J5

Characterised directly from the recovered campaign, then verified independently on three
episodes chosen at random from the largest event logs.

**Structure.** Every episode is `run_start`, initial `observation`, `plan`, then
`action`/`observation` pairs. Interventions land at event positions **12, 23, 34, 45, 56,
67, 78, 89** — exactly **11 apart** (5 actions + 5 observations + 1 intervention). The
same layout appears in `fixed_k/1/229360a_3`, `fixed_k/2/6104387_3` and
`fixed_k/2/b0a8eae_1`.

**The reviewer speaks before the executor acts, and never rejects an action.** The order is
`… action, observation, INTERVENTION, action …`. The correction is injected at the top of
step 5, 10, 15 …; the executor then acts with it in context.

**Campaign-wide, verified by direct count:**

| | value |
|---|---|
| interventions with `forced: true` | **495 / 495 (100%)** |
| interventions with `forced: false` or absent | 0 |
| `ask` events | **0** |
| interventions per episode | min 0, median 2, max 8 (the ceiling); 2 episodes have none |

Intervention payload keys are `correction` (string), `forced` (bool), `n_interventions`
(int). **The executor's own prior action is not in the payload** — it is recoverable only
as the separate `action` event before it.

**The corrections are imperative prose, not executable code.** Verbatim, from three
episodes: *"Log in to Spotify first and pass the returned access token to every
`show_artist_following` and `follow_artist` call; paginate all `search_artists(...)`
results, deduplicate by `artist_id` …"*; *"Paginate all library/liked/downloaded results,
compare IDs, remove only non-qualifying library items …"*; *"Count a coworker as paid only
when Venmo shows a received transaction matching their recorded share …"*. So the training
*target* must be the following `action` event; the correction text belongs in the context
as the `INTERVENTION:` user turn, which `sft_data.py:167` already renders.

#### 🔺 Two parts of the written J5 spec do not survive this

`PLAN.md` specifies SFT(c) as "post-correction actions as targets (**overridden action
masked**) and `ASK_PLANNER` as the target **where the review overrode the executor**".

1. **No action is ever overridden**, so there is nothing to mask on that basis. The
   reviewer speaks before the executor proposes anything. The instruction is a no-op
   against this data.
2. **"Where the review overrode the executor" is not identifiable.** All 495 interventions
   are `forced: true` on a fixed timer; not one was triggered by the executor asking (0
   asks) or by a reviewer judging an action wrong. Selecting ASK targets at intervention
   points would train the model to **ask every 5 steps** — a metronome. That is precisely
   what `fixed_k` already does, and the opposite of the need-based escalation the sidekick
   exists to learn. It would also corrupt H2: the comparison would measure "does asking on
   a timer help", not "does escalation help".

**The signal the plan needs is J6's, not J4's.** J6 branches forward from each intervention
point *without* the planner and labels the intervention needed vs needless. That label is
exactly what distinguishes a real escalation point from step 5.

**Recommended re-ordering, pending a decision:**

- **`sft_b_plus` is buildable today** from J3's teacher conversations plus J4's
  post-intervention actions, with **no ASK targets and no oracle labels required**. It is
  both the H2 control and a useful adapter on its own.
- **`sft_c`'s ASK channel should wait for J6's labels**, so ASK is trained on points where
  proceeding unaided actually failed.

This costs nothing in wall-clock — J6 was already on the critical path — and it stops H2
from being decided by a timer.

---

## Executor selection: the defensible rationale, and why Qwen was not re-probed (2026-09-17)

**This is the statement to use in the prereg and the write-up.** It replaces any framing
built on the v2 Granite-vs-Qwen numbers.

The pre-registered rule, recorded before HJ-1.5 ran:

> agreement ≥ 0.40 overall and not collapsing with depth → train Granite;
> **< 0.15 on Granite *and* materially better on Qwen3-8B → switch executor before J3**;
> between → proceed with Granite and add J2's third seed.

Granite, measured under the **serving configuration** (`probe_granite8b_serving.json`,
`PROBE_SCHEMA_VERSION` 3, `enable_thinking: false`, stop sequences set):

| | value |
|---|---|
| agreement, overall | **0.256** (64 / 250) |
| by depth 1–5 / 6–10 / 11+ | 0.167 / 0.213 / **0.400** — rising, not collapsing |
| parse errors | 2 / 300 |
| state-equivalence | 0.866 |

0.256 lands in the **"between"** band, so the rule says *proceed with Granite and add a
third J2 seed*. That was done, and the third seed was collected.

🔺 **The switch branch is conjunctive and its first clause fails.** It requires Granite
below 0.15. Granite is at 0.256 — 1.7× the threshold — so the branch is closed **whatever
Qwen's true value is**. The decision therefore never depended on the Granite-vs-Qwen
comparison, which is fortunate, because that comparison came from a configuration no arm
runs in.

### Why Qwen was not re-measured at v3 — a deliberate decision, not an oversight

`probe_qwen3_8b.json` is the only report still at schema v2; Granite and `sft_b` were both
re-run at v3. A v3 Qwen run would cost about 20 minutes of GPU and zero hosted calls.
**It was considered and dropped**, on the reasoning that:

- It is **not decision-relevant.** J3 and J4 are complete and the J3 gate passed on both
  criteria (+37.72 pp, CI [28.07, 47.37]). No Qwen result would cause an executor switch
  at this point, so the run could only produce a number nobody would act on.
- The executor choice is a **methods footnote, not a thesis claim.** The hypotheses concern
  planner–executor collaboration and the ASK channel; which 8B model carries the adapter is
  implementation detail, and a Qwen figure would not appear in the findings.

**What must therefore be said, and not said.** The selection is justified by Granite
clearing the pre-registered threshold on a correctly-configured measurement — full stop.
Any claim of the form "Granite outperformed Qwen" is **unsupported** and must not be made:
Qwen's performance under the serving configuration was never measured, and the best
available estimate (~0.165, inferred) carries no measurement behind it.

### Independent corroboration that the choice works

Not part of the selection rule — it postdates it — but it is real evidence the chosen
executor is adequate:

| | untrained Granite | SFT(b) |
|---|---|---|
| probe agreement | 0.256 | **0.492** |
| `sft_plan` TGC (dev) | 0.0526 | **0.4298** |
| state-equivalence | 0.866 | **0.920** |

Granite is trainable at this data scale. That does not establish it was the *best* choice,
and the write-up should not imply it does.

---

## The campaign from here: gates A and B, written before the jobs (2026-09-17)

Granite is settled, SFT(b) works, and the plan transfers. What is **not** measured is the
thing the thesis is about. This section records the reordered campaign and the two decision
rules, *before* the jobs that test them are submitted. Plan of record:
`~/.claude/plans/robust-dancing-sonnet.md`.

### Why the order changed

`docs/PLAN.md` put SFT(c) (ASK targets) before the counterfactual branches. That order cannot
work. J4's 495 interventions are ticks of a 5-step timer — the reviewer speaks before the
executor acts, never sees a proposed action, never overrides one, and 495/495 are
`forced: true` with 0 `ask` events. **Nothing in the J4 data says which interventions
mattered.** The counterfactual branches are the only source of that label, so they move
ahead of SFT(c). New order: **J4b → J6 (branches) → J5a/J5b (the matched adapters) → J7
(verifier) → J8 (dev frontier) → J9 (freeze) → J10 (test)**.

Two further decisions, taken 2026-09-17:

- **DPO (PLAN.md M5 / HJ-6) is dropped.** The sidekick's frontier is swept by thresholding
  the policy's own P(ASK) (the existing `gate_ask_with_verifier` path,
  `src/sidekick/systems/loop.py:816-820`), which needs one adapter instead of three, gives
  arbitrarily many operating points, and *is* the H3 calibration measurement. Recorded as a
  deliberate deviation from the written plan, not an omission.
- **The prereg's primary endpoint changes from H1 to H2** (see J9, below).

### Gate A — does the timer buy anything on held-out tasks? (J4b)

`fixed_k` on the `sft_b` policy has only ever run on **train** (`hj4_correction_train_20260917`,
TGC 0.577), the split that adapter was trained on. That number is inflated and is not
comparable to any dev arm. J4b runs the identical arm on **dev** (57 × seeds 1,2, plans cached
from `hj1b_planner_20260915`) so it is paired, task-for-task and seed-for-seed, against
`hj3_sft_plan_20260917` — same adapter, same cached plans, same prompt, TGC **0.4298**.

Statistic: paired bootstrap (10k resamples, `scripts/setup/hj1_gate.py`) of
`TGC(fixed_k, sft_b, dev) − TGC(sft_plan, sft_b, dev)` over all 114 pairs.

| outcome | reading | action |
|---|---|---|
| **≥ +7 pp, CI excludes 0** | the reviewer adds real quality on held-out tasks | proceed to J6 as planned |
| **CI includes 0** | fixed periodic review did not establish aggregate benefit at this sample size | **J6 still runs** (see the scope note below); **stop before J5a/J5b training.** Record H2 as unsupported at this data scale and decide, with the user, between a richer review format (a reviewer that sees the proposed action) and writing up the SFT + plan-transfer result alone |
| **between** | the effect is real but small | proceed, and pre-register H2 as a **dominance-on-the-frontier** claim only, never superiority |

Also recorded from the same run, because the sidekick has to beat it on cost, not just
quality: reviews per episode, planner calls per episode, planner tokens per episode.

🔺 **Scope — amended 2026-09-17, before the gate fired.** Gate A gates **training** (J5a, J5b
and everything downstream, ≈ 25 GPU-h), **not branching** (J6, ≈ 10.7 GPU-h). The original
rule stopped both, and that was the wrong cut for two reasons.

The first is inferential. Gate A measures the timer's **average** effect; the thesis is about
the **variance** of intervention value. A null Gate A with high dispersion in Δ — most calls
worthless, a few decisive — is not evidence against the thesis, it is the exact condition
adaptive allocation exists to exploit. Stopping there would discard the hypothesis on a
statistic that cannot test it.

The second is that J6 produces the one measurement in this project that does not depend on the
sidekick working: the needed-fraction *f*. "*X % of a fixed schedule's expert calls changed
nothing*" is a fact about periodic supervision in agent pipelines, it is method-independent,
and it survives every downstream outcome including H2 failing outright. It is a paper either
way, and it is the cheaper half of the remaining compute.

So a null Gate A is a decision point, not an automatic stop, and it is a decision taken **after
J6 reports**, when *f* and the shape of the Δ distribution are in hand rather than guessed at.
What Gate A still protects is the expensive, sidekick-specific half: two training runs and the
frontier evaluation that follows them. Better to learn that from a 1.2 GPU-h evaluation than
from the final test run.

⚠ Operational consequence, recorded because it changes the calendar: **J6 no longer waits on
Gate A being computed**, and therefore no longer waits on the task-clustered bootstrap (W-8)
landing. J6 is submittable as soon as J4b's episodes are archived and W-1b's branch code is
reviewed and committed. Gate A is still computed, with the clustered bootstrap, and still
written here — it just gates the next spend rather than this one.

### Gate B — does the frontier exist? (J6)

Every intervention point is branched twice (seeds 101, 102) from the state just before the
reviewer spoke, without the correction, same adapter, temperature 0.7. Label, fixed here and
not tuned later:

- `needed := mean(branch_gpr) < actual_gpr`
- `needless := mean(branch_gpr) >= actual_gpr` (the boundary case is needless)
- `harmful := mean(branch_gpr) > actual_gpr`; `needed_strict :=` both samples below actual
- either sample missing → `incomplete`, no label, never imputed

🔺 **Superseded by the focal + band definition (amendment §1), and one consequence of that
change is a naming trap worth stating before any number is quoted.** Under the band rule as
implemented (`scripts/setup/branch_counterfactual.py:250-259`, committed in `744361f`):

- `needed := Δ > δ` — the correction helped, beyond the noise floor
- `needless := Δ < −δ` — the correction **actively hurt**, beyond the noise floor
- `ambiguous := |Δ| ≤ δ` — the correction changed nothing measurable
- `harmful` is defined **identically to `needless`** and is therefore a redundant column

The trap: under the old zero-threshold rule `needless` meant "did not help", which included
every call that changed nothing. Under the band rule those calls are `ambiguous`, and
`needless` has narrowed to "made it worse". So:

> **The headline "X % of a fixed schedule's expert calls changed nothing" is
> `needless + ambiguous`, i.e. `1 − f` — never the `needless` column alone.**

Likewise Gate B's "`harmful` > 0.15 flags the review format" now reads off a column that is
the same as `needless`, and the plan's needless-ask rate (asks at states labelled `needless`)
now scores asks only at states where asking actively hurt — a much narrower set than was
intended. Both are defensible quantities; they are simply not the quantities the old names
imply, so the report must print `needed` / `needless` / `ambiguous` as three separate counts
and never a two-way split. No code change: Δ is stored per point, so any relabelling is free
and costs no rollouts.

Let *f* = the needed fraction. Report it on **dev** (train is inflated for the same reason as
above), by depth bucket (1–5 / 6–10 / 11+) and by seed.

| outcome | action |
|---|---|
| f_train < 0.10 (< ~75 positives) | too few ASK targets to train on — collect a fourth correction seed before J5b |
| f_dev > 0.85 | the timer is nearly always useful; the sidekick's possible saving is bounded by 1 − f. Record the bound and proceed — choosing *which* ticks still has value |
| harmful > 0.15 | a reviewer that hurts one time in seven changes the H3 reading; open a FOLLOWUP on the review format |

**f_dev is a paper figure whatever follows** — "*X % of a fixed schedule's hosted calls
changed the outcome*" is the quantitative case for need-based escalation, and it is the first
number in this project that measures the premise rather than a system.

### What J9 will freeze, and the endpoint change

The prereg draft (`docs/prereg_v1.md`, N = 3, ε = 7 pp) names **H1** — sidekick non-inferior
to `planner_alone` — as primary. Dev says that will fail: the best executor arm is 0.430
against the planner's 0.684, and `PLAN.md:259-262` already anticipated it, naming the
quality-versus-displacement frontier as the deliverable in that case. Freezing a primary
endpoint we expect to fail would bury the result the work actually supports.

**Primary becomes H2, conjunctive**, on test_normal over 504 paired (task, seed) pairs,
one-sided 95 % bootstrap — all three must hold:

1. `sidekick` ≥ `fixed_k(k_matched)` − 7 pp
2. `sidekick` > `sft_plan(sft_b_plus)`, CI excluding 0
3. `sidekick` planner calls/episode < `fixed_k(k=5)`'s, CI excluding 0

The conjunction has teeth. A policy that never asks passes (1) trivially only when the timer
is worthless, and (3) trivially always — but then fails (2), because it *is* `sft_plan`. A
policy that always asks passes (2) and fails (3). Only a policy that asks selectively passes
all three. H1 becomes secondary and is reported whatever it shows.

`k_matched` is a **rule, frozen now, not a number**: the k ∈ {3, 5, 10} whose dev calls per
episode is nearest the sidekick's, interpolating to k = 7 if k = 5 and k = 10 tie. It is
resolved on dev at J8 and never revisited after J9.

Falsification, stated plainly so it cannot be softened later: if (2) fails, intervention-aware
training did not beat intervention-agnostic training on this data; if (3) fails, it did not
save cost. Either is reported as measured. J10 runs once.

---

## 🔺 Amendment 2026-09-17 (later): three corrections to the design above, before J6 runs

A methodological review of the campaign plan raised three problems and several statistical
ones. J4b (job 25404924) was already queued and is unaffected — it runs the timer arm on dev
and collects a third correction seed, which every version of the design needs. **J6 has not
run.** The corrections below supersede the branch definition in the Gate B section above.

### 1. 🔺 The branch definition was wrong: it ablated the future, not the intervention

The design above continues each branch with `review_every_k=None` — every later scheduled
review switched off. That does **not** estimate the effect of intervention *i*. It estimates

> intervention *i* **plus every subsequent scheduled review in that episode**.

Interventions fire every 5 steps and episodes run to 19–40, so most points fold several
downstream reviews into the contrast. If the step-5 correction is useless and the step-10 one
is essential, switching both off labels the **step-5** point `needed`. That error would have
propagated into the ASK targets, the verifier, and the headline needed-fraction — i.e. into
every artifact J6 exists to produce.

**Corrected estimand.** Hold the review *policy* fixed and vary only intervention *i*:

```
Δ_i = Q(policy with intervention i present) − Q(policy with intervention i omitted)
```

Both conditions continue from the same replayed prefix with the reviewer **live on its normal
5-step schedule** for every later step, calling the planner on the branch's own state rather
than replaying the original episode's later corrections (which, after divergence, are about a
state that no longer exists). Branches therefore make live planner calls: ≈ 6,000 hosted
calls, quota not money.

**Replicates.** The old design compared one factual trajectory against two ablated branches,
which mixes the intervention effect with sampling variance — a label could flip because the
factual run was lucky. Now **2 treated and 2 untreated**, all fresh, paired by branch seed
(common random numbers) so the two conditions share sampling noise. 4 branches per point,
≈ 4,240 rollouts, ≈ 10.7 GPU-h.

**The factual trajectory becomes a validation check, not an estimator input.** It is itself a
draw from the treated condition, so it should lie inside the spread of the treated branches.
If it systematically does not, replay-and-continue is not reproducing the original run and the
entire artifact is suspect. This check is printed, not buried in a manifest.

**Indifference band.** Binarising a noisy difference at exactly zero manufactures labels out
of sampling noise. A point is `needed` if Δ > δ, `needless` if Δ < −δ, and `ambiguous`
otherwise. **δ is a rule, not a number**: the 75th percentile of
|treated[seed 101] − treated[seed 102]| over train points — the observed noise floor between
two *identically configured* runs — computed on train only, frozen, then applied to dev. A
difference that cannot clear the noise between two identical conditions is not evidence.
ASK targets come from `needed` only; `ambiguous` is excluded from fitting and reported.

A secondary short-horizon label (`delta_local`, scored at the next scheduled review boundary)
is recorded alongside: strictly focal, lower variance, cheap.

### 2. H2 was not satisfiable as written; it splits in two

"`sidekick` beats `sft_plan` at matched planner cost" cannot hold as stated. `sft_plan` is not
zero-cost — it carries a plan call and has `allow_executor_ask=True` (`systems/sft_plan.py:17`),
firing once in 114 HJ-1R episodes — but its planner cost is ≈ 1 call/episode against the
sidekick's 1 + asks. The two are cost-matched **only** at the threshold where the sidekick
never asks, which is the degenerate point.

- **H2a — does the ASK channel add capability?**
  `Q(sidekick_τ) > Q(sft_plan(sft_b_plus))`, paired, **reporting the extra planner cost that
  bought the gain**. Not a matched-cost claim and must not be written as one.
- **H2b — does it allocate a fixed budget better?** At matched planner calls (and matched
  planner tokens, reported separately): `Q(sidekick_τ) > Q(fixed_k(k_matched))` **and**
  `Q(sidekick_τ) > Q(router_seq(τ*))`.

H2b is the allocation claim and is the paper's core. The J9 primary becomes the conjunction of
H2a and H2b, replacing the three-clause form above; clause 3 of that form (fewer calls than
`fixed_k(5)`) is subsumed by H2b's matched-budget construction. `router_seq` was missing from
the cost-matched comparison entirely and is now in it.

### 3. P(ASK) must be a real probability, not a first-token proxy

Thresholding "first-token mass on the ASK marker" is only valid if `ASK_PLANNER:` is
unambiguously one token at that position. It is very likely several, and leading whitespace,
chat-template artifacts and shared prefixes with other action forms all corrupt it. Measuring
the tokenisation (as the worker brief required) detects the problem but does not fix it.

**Use the conditional sequence probability of the full ASK prefix**, obtained by teacher-forcing
those tokens and summing log-probabilities — exact, well-defined regardless of tokenisation,
and requiring no change to the action format. A reserved single control token per action class
would be cleaner still, but it would invalidate `sft_b` and every number already built on it,
so it is rejected on cost. First-token mass may be reported as a cheap correlate; it is not the
gate.

### 4. Statistical corrections that apply throughout

- **Cluster the bootstrap on task.** 114 "pairs" are 57 tasks × 2 seeds, and J10's 504 are
  168 × 3 — not independent draws. Resample **tasks**, carrying all seeds and both arms of a
  sampled task together. This applies to Gate A, every dev comparison, and J10. `hj1_gate.py`
  currently resamples pairs and must be corrected before Gate A is computed.
- **Intervention points are nested** inside episodes inside tasks. Verifier evaluation uses
  task-grouped cross-validation; no CI over points treats them as independent.
- **Policy-induced distribution shift.** J6 labels states visited by `fixed_k` on `sft_b`. The
  trained sidekick visits a different distribution because its own ASK choices change what it
  sees. Measure it — how often J8/J10 sidekick states fall outside the J6 feature
  distribution, and compare intervention depth and error-state profiles. Do not repair it using
  test trajectories. One DAgger-style aggregation round on **train** only is permissible.
- **Risk is not the same as intervention value.** Fit and report both `P(fail | s)` and
  `P(Δ > δ | s)`. A state can be high-risk where the planner cannot help, and ordinary where a
  short clarification is decisive. The contrast between the two is a result in its own right.

### 5. Gate A's stopping language was too strong

The Gate A table above says a CI including zero means "interventions add nothing a learned
policy could capture". That overclaims in exactly the place the objection bites: a periodic
reviewer can have a small *average* effect because most of its calls are useless while a few
are decisive — which is precisely the condition adaptive allocation exists to exploit. The
correct reading of a null Gate A is:

> At this sample size and compute budget, fixed periodic review did not establish sufficient
> aggregate benefit to justify training an adaptive allocator.

Gate A remains a **pre-registered resource-spending rule**, not a proof of absence. Note also
that J6's needed-fraction can be informative even when Gate A is null — a low *f* with a
high-value tail is the interesting case — so a null Gate A triggers a decision, not an
automatic stop.

🔺 **Resolved later the same day, with the user's approval: Gate A's scope narrows to
training.** The paragraph above identified the problem but left the stopping rule pointing at
both J6 and J5; that is now cut so Gate A gates J5a/J5b onward (≈ 25 GPU-h) and J6 (≈ 10.7
GPU-h) runs regardless. The reasoning, and the calendar consequence — J6 stops waiting on the
clustered bootstrap — are written into the Gate A section above, which is the operative text.
The change costs 10.7 GPU-h in the null case and buys the needed-fraction, which is the only
result here that survives the sidekick failing.

### 6. Positioning: what is and is not new

Recorded so the contribution is not overstated later. **These references come from the review
and have not been read or verified in-session** — verify before citing.

| already established | by |
|---|---|
| large planner + small executor | prior work |
| training an executor on planner-generated plans and corrections | ProST |
| a small model escalating to a stronger one | R2V-Agent; "Bayesian Self-Escalation" |
| threshold sweeps producing a cost-quality frontier | both of the above |
| counterfactual rollouts over agent trajectories as supervision | CausalFlow |

What remains defensible:

> Estimating the **causal value of an individual planner intervention** by environment replay,
> distilling those labels into an executor-internal ASK action, and testing whether that beats
> a fixed schedule **and** a post-hoc router at matched planner budget.

The sharpest distinction is against R2V-Agent, whose router predicts `P(episode eventually
fails | s)` — failure *risk*. This project's label estimates `E[Q | intervene] − E[Q | not]` —
intervention *value*. A state can carry high failure risk while planner help changes nothing;
that difference is the whole argument for the branching cost, and §4's dual-head requirement
is what will make it measurable rather than asserted.

Against CausalFlow: it asks which *agent step* caused failure and what repairs it; this asks
whether *external assistance* was worth its price. Against ProST: the matched
`sft_b_plus`/`sft_c` pair isolates exactly what ProST conflates — corrected action versus
ASK → answer → corrected action.

---

## 🔻 GATE A — the verdict (J4b, job 25404924, commit `ff71e4e`, 2026-09-17)

J4b completed clean: **114/114** dev episodes and **90/90** train seed 3, `[gate] PASS` on both
stages, `Exit_status 0`, wall 2:07:52 of a 4 h walltime, smoke purged, both campaigns archived
(`hj4b_fixed_k_dev_20260917`, and the train seed carried as `hj4_correction_train_20260917_s123`
so the frozen seeds-1-2 archive the J4 ledger references was not overwritten — the guard W-2
added did its job). All 496 planner calls resolved to `gpt-5.6-luna`; **0 api_error, 0 timeout**.

### The paired comparison, on the 114 dev pairs

| arm | TGC | solved | SGC | planner calls | calls/ep | steps/ep | `limit` errors |
|---|---|---|---|---|---|---|---|
| `fixed_k(sft_b)` | **0.5000** | 57/114 | 0.2368 (9/38) | 496 | **4.35** | 18.64 | 7 |
| `sft_plan(sft_b)` | 0.4298 | 49/114 | **0.2895** (11/38) | 114 | 1.00 | 17.68 | 15 |

`fixed_k − sft_plan` = **+7.02 pp**, paired on (task, seed), same cached plans, same adapter.

| resampling unit | 95 % CI (pp) | clusters | mean cluster size |
|---|---|---|---|
| **task (default, correct)** | **[−0.88, +15.79]** | 57 | 2.0 |
| pair (superseded) | [−0.88, +14.91] | 114 | 1.0 |

### 🔺 Verdict: **the CI includes zero.** Training is gated; J6 is not.

The point estimate lands exactly on the +7 pp threshold and the interval misses excluding zero
by 0.88 pp. Under the amended rule this reads as: *at this sample size and compute budget, fixed
periodic review did not establish sufficient aggregate benefit to justify training an adaptive
allocator.* It is **not** a proof that interventions are worthless. Consequences, as
pre-registered before the number existed:

- **J5a / J5b training does not proceed on this evidence alone.** That decision is deferred to
  after J6 reports, per the Gate A scope amendment.
- **J6 runs regardless**, as pre-registered. This is now load-bearing rather than hypothetical.

### Why this outcome makes J6 more informative, not less

Three facts from the same table point the same way:

1. **The timer costs 4.35× the planner calls for a gain that does not clear zero.** 496 calls
   against 114, for +7.02 pp [−0.88, +15.79]. If the aggregate effect is real but thin, the only
   way it becomes worth paying for is if it is *concentrated* — which is precisely the
   needed-fraction *f* that J6 measures. A null average over a mixture of worthless and decisive
   calls is exactly the signature adaptive allocation exists to exploit.
2. **The reviewer does prevent stalls**: `limit` errors fall from 15 to 7, so the timer is
   demonstrably doing *something* mechanical to episodes that would otherwise run out of steps.
3. 🔺 **But SGC moves the other way**: `fixed_k` 0.2368 vs `sft_plan` 0.2895 — the timer wins on
   task-level goal completion and **loses on scenario completion** (9 complete scenarios vs 11).
   TGC and SGC disagreeing in sign is a real tension and must not be smoothed over: the reviewer
   appears to convert some near-complete scenarios into partial ones. Whether that is the
   `harmful` tail is directly testable from J6's per-point Δ, and it is now a named thing to look
   for rather than a surprise waiting in the final run.

### Method notes

- The clustered interval is only 0.88 pp wider than the pair-level one, so **within-task
  correlation is low in this campaign** — the two seeds of a task behave near-independently. The
  clustering correction is still the right default (J10's 168 × 3 has more room to bite), but it
  is not what decided this gate, and no previously published verdict changes because of it.
- W-8 (the clustered-bootstrap unit) **died at the 60-minute codex MCP ceiling** with the
  resampler and its tests written but the recheck report and test run not done. The code was
  reviewed and the gate computed here directly rather than re-dispatching. Its unit tests: 9
  passed. Full suite at this commit: **286 passed, 1 skipped, 0 failures.**
- `hj1_gate.py` coerces a missing `tgc` to 0.0 (`float(... or 0.0)`). Pre-existing, not
  introduced by the clustering change, and harmless here because both arms report 0 broken runs —
  but it is a silent-zero path and is logged in FOLLOWUPS rather than left implicit.

---

## 🔻 GATE B (dev) — the verdict and the reliability threat (J6, job 25412541.aqua, commit `dc92a25`, 2026-09-17)

- **Job**: `25412541.aqua`, campaign `hj6_branches_dev_20260917`, split dev, adapter `sft_b`, branch seeds 101/102, commit `dc92a25`.
- **Coverage**: 1527 of 1528 branches. 382 intervention points; 374 complete; 8 dropped (1 missing every sample, 7 with a null `branch_gpr`).
- **δ (delta band)** = 0.166, computed by the pre-registered rule — the 75th percentile of |treated[101] − treated[102]| over train points. ⚠ Originally computed on partial train data as provisional; **confirmed identical (0.166) on the final 734 complete train points**, so no dev number computed against it moves.
- **Negative control**: with δ unfrozen, all 381 rows return `label_status: incomplete` rather than a fabricated label.

### Labels over the 374 complete dev points

| label | n | fraction | mean Δ |
|---|---:|---:|---:|
| needed | 59 | 0.157754 | +0.342686 |
| needless (= harmful) | 53 | 0.141711 | −0.356472 |
| ambiguous | 262 | 0.700535 | +0.004672 |

- **Mean Δ per point** = +0.006817.
- **Headline needed fraction**: f_dev = **0.1578** (59 of 374).
- **Paper figure**: **1 − f = 0.8422** (84.22 % of scheduled planner reviews produced no measurable benefit).
- **Validation**: factual outcome outside `[min(treated), max(treated)]` for 81 of 374 = **0.216578**.
- **Oracle allocation** (fire only at `needed`): +0.0541 per point against +0.0068 always-on, at 84.2 % fewer planner calls. ⚠ Recorded immediately beside it that this is **inflated by regression to the mean** and is not an achievable figure — see the reliability analysis below.
- **Cross-check**: recomputed from raw columns by a second worker type (luna, W-10) which was instructed not to read `scripts/setup/branch_counterfactual.py`. Agreement to ≥ 4 decimals on every statistic. Report: `campaign/workers/W10_RECOUNT.md`.

### Verdict against pre-registered Gate B thresholds

- **f_dev > 0.85**: f_dev = 0.158 is **not** > 0.85, so the timer is not almost-always-useful.
- **harmful > 0.15**: `harmful` (= needless) = 0.1417 is **just under** the 0.15 flag threshold — close, but did not fire.
- **f_train < 0.10**: f_train is recorded in the Gate B (train) block below (0.1131, does not fire).

---

### The label-reliability threat

This is the important finding and it has no pre-registered home, which is itself the finding.

**Split-half agreement** between branch seeds 101 and 102 over the 374 complete dev points:
- Pearson **r = 0.163962**
- Spearman **ρ = 0.222022**
- **Sign agreement**: **0.7024** over the 84 points where both per-seed deltas are nonzero.
- **Co-occurrence above band**: 56 points above band on both halves against 35.81 expected under independence (**1.56× chance**).
  - ⚠ Earlier notes in the campaign quoted this co-occurrence as **2.3× chance** from partial data; the full-dev figure is **1.56×**, and the 2.3× figure is superseded.
- **Spearman-Brown reliability**: on r = 0.164, Spearman-Brown gives the two-replicate mean that the labels are cut from a reliability of **0.282**; four replicates would give **0.440**.

#### Substantive reading

The heterogeneity is **real** — 70 % sign agreement against a 50 % null is not noise — but **weak**, with roughly 72 % of Δ's variance being sampling error.

**Gate B's three pre-registered thresholds all concern f and none of them would have caught this.** A reliability criterion is proposed for Gate B but has not yet been approved by the user, so it is recorded as a proposal, not as a gate.

---

## 🔻 GATE B (train) — verdict, fired harmful flag, and frozen delta band (J6, `hj6_branches_train_20260917`, 2026-09-18)

- **Source**: `branch_runs.jsonl` of `hj6_branches_train_20260917`, 4,188 rows at time of aggregation, re-aggregated on CPU with branch seeds 101/102.
- **Coverage**: 777 intervention points seen; **734 complete** on seeds 101/102; 43 incomplete. (261 points were already complete on all four seeds at that moment; the ×4 job is still running.)
- **δ is now FROZEN on train**: `delta_band_delta = 0.166`, by the pre-registered rule, over the 734 complete points. ⚠ This is **identical to the provisional value** used for the dev block, so no dev number computed against it moves.
- **Mean Δ per point** = **−0.0206**. Stated plainly: on train, the fixed review schedule's average effect on outcome is **negative**.
- 🔺 **This negative mean is explained, and largely explained away, by an allocation artifact.** A third of review calls fire where the untreated branch already scores 1.0, so Δ there is bounded above by zero and the review cannot help. Excluding those points the timer is break-even and helps slightly more often than it hurts (0.164 vs 0.140). Full stratification, plus the independent compounding effect of later reviews, is in `docs/FOLLOWUPS.md` under "the `harmful` flag fired, and the cause is allocation, not format" (2026-09-18).
- **Validation**: factual outside `[min(treated), max(treated)]` for 0.16869 of 741 compared; mean signed difference +0.03529.

### Labels over the 734 complete train points (band 0.166)

| label | n | fraction |
|---|---:|---:|
| needed | 83 | 0.1131 |
| needless (= harmful) | 120 | 0.1635 |
| ambiguous | 531 | 0.7234 |


### Verdict against all three pre-registered Gate B thresholds

- **`f_train < 0.10`** → **does not fire** (0.1131). 83 needed points clears the "< 75 positives" concern, so **no fourth teacher/correction seed is required before J5b**.
- **`f_dev > 0.85`** → **does not fire** (0.158 at two replicates, 0.130 at four).
- **`harmful > 0.15`** → **🔺 FIRES** at **0.1635** (120 of 734). The pre-registered consequence is to flag the review format in `docs/FOLLOWUPS.md` (see FOLLOWUPS entry). It changes the H3 reading, per the plan's own wording: *a reviewer that hurts one time in seven changes the H3 reading*.

---

## 🔻 The ×4 replicate result (dev) — direct measurement of reliability and label movement (2026-09-18)

The dev ×4 job completed: 3,056 branch runs, 332 points complete on all four seeds × both conditions. This was run specifically to test whether replicates lift label reliability, and it is the direct measurement that the earlier two-seed analysis could only predict.

### Reliability scaling

| quantity | predicted from 2 seeds | measured at 4 seeds |
|---|---:|---:|
| mean single-replicate Pearson r | 0.164 | **0.1697** |
| reliability of the 2-replicate mean | 0.282 | **0.2902** |
| reliability of the 4-replicate mean | 0.440 | **0.4504** |


The 4-replicate figure is measured directly: three distinct 2-vs-2 splits of the four seeds, each half-mean correlated with the other and Spearman-Brown corrected. The three splits give 0.5026, 0.3074 and 0.5412; the mean is 0.4504. ⚠ Record that spread — it is estimation noise in r at n = 332 and it means 0.45 is a central estimate, not a tight one.

Mean single-replicate Spearman ρ = 0.1951.

### Label movement over the same 332 points (band 0.166)

- **2-seed mean**: needed 50, needless 48, ambiguous 234
- **4-seed mean**: needed 43, needless 43, ambiguous 246
- **Agreement**: 276/332 = **0.8313**; outright needed ↔ needless flips = **0**

### Substantive reading and consequence for the headline

Every disagreement is a borderline point crossing the band, never a sign reversal, which is what noise reduction looks like rather than labels breaking.

**Consequence for the headline**: The two-replicate *f* was inflated by noise pushing borderline points over the band. At four replicates, f_dev falls to **0.130** and **1 − f rises from 0.843 to 0.870**. The fixed schedule is *more* wasteful than the earlier figure suggested, not less.


---

## 🔻 GATE B (train), FOUR replicates — `f_train < 0.10` FIRES (2026-09-18)

The train ×4 job completed (6,216 branch rows) and its own final aggregation wrote the
four-seed labels at 12:18. These supersede the two-seed numbers in the block above for every
purpose except sample size.

| | n | needed | f | needless | ambiguous | mean Δ |
|---|---:|---:|---:|---:|---:|---:|
| all points, 2-seed rule | 734 | 83 | 0.1131 | 120 | 531 | −0.0206 |
| **same 397 points, 2-seed rule** | 397 | 46 | 0.1159 | 67 | 284 | −0.0189 |
| **same 397 points, 4-seed rule** | 397 | **25** | **0.0630** | 46 | 326 | −0.0144 |
| the 337 dropped points, 2-seed rule | 337 | 37 | 0.1098 | 53 | 247 | −0.0227 |

**The drop is caused by the extra replicates, not by the smaller point set.** On an identical
397 points the needed count falls 46 → 25 purely from averaging four seeds instead of two, and
the 337 points lost to the crash defect have f = 0.1098 against the kept points' 0.1159 —
indistinguishable, which is the same conclusion the selection-bias test reached independently.
Label agreement between the two rules is 0.8388 with only 2 needed↔needless flips, so this is
borderline points settling toward the band, not labels changing sign.

**Roughly half of the `needed` labels at two replicates were noise.** That is the direct,
measured version of what the reliability analysis predicted: two-replicate reliability is 0.29,
so a band-threshold rule applied to it manufactures positives.

### Verdict

- **`f_train < 0.10` → 🔺 FIRES.** f_train = 0.0630. Extrapolating the four-seed rate to all
  777 points gives ≈ 49 needed, still well under the pre-registered 75-positive threshold.
  The pre-registered consequence is to **add a fourth teacher/correction seed before J5b**.
- `harmful > 0.15` → does **not** fire on the four-seed labels: needless is 46/397 = 0.1159,
  against 0.1635 on the two-seed labels. The flag that fired yesterday was itself partly a
  noise artifact, which is consistent with everything else here.
- Dev moves the same way: f_dev 0.158 (2-seed) → 0.130 (4-seed).

### What it means for the campaign

The headline gets **stronger**: on train, 1 − f rises from 0.887 to **0.937**. Over nine in ten
of a fixed schedule's expert calls change nothing measurable.

The training signal gets **weaker**, and this is the binding problem. J5b's ASK targets come
from `needed`, and there are 25 of them at four replicates — 49 if the lost branches were
recovered. An ASK policy cannot be learned from that. The pre-registered response (a fourth
teacher seed) costs a further `fixed_k` campaign plus its branches, and per the root-cause
entry in FOLLOWUPS that is now a **planner-quota** decision rather than a GPU one: branching a
fourth seed is roughly 4 planner calls × the new branches.

⚠ Both readings come from the same fact and neither should be quoted without the other. The
interventions are rarely needed *because* they are rarely needed — which is the paper result —
and that same scarcity is what leaves too few positives to train the policy the campaign was
built to test.

---

## 🔻 δ SENSITIVITY — the label band, and what the gate verdict actually rests on (2026-09-18)

Gate B's verdict is not robust to a defensible re-derivation of δ. This block records the
sensitivity so that no single number is quoted without it.

### Why the question arose

δ is pre-registered as **a rule, not a number**: the 75th percentile of
`|treated[101] − treated[102]|` over train points — "the noise floor between two identically
configured runs". Frozen at **0.166**.

That yardstick is the spread of a difference between **two single draws**. The statistic it is
applied to, Δ, is a difference between **two four-replicate means**. Those are not on the same
scale: the null used to set the band is noisier than the estimator being thresholded, so the
band is wider than the noise floor it is meant to represent, which inflates `ambiguous` and
suppresses both `needed` and `needless`.

### What was measured

The frozen rule reproduces exactly from the raw data (75th percentile = 0.1660 over n = 741),
which confirms the point definition and percentile method match how 0.166 was originally
derived.

- **Within-condition SD** is 0 at the median — scores are 0/1-heavy and replicate perfectly at
  many points. The noise lives in the upper tail (train p90 ≈ 0.289).
- **Observed SD(Δ)** falls from 0.1925 (seeds 101,102) to **0.1495** (all four). The shrinkage
  ratio is 0.80, not the naive 1/√2 ≈ 0.71 — on a discrete, skewed score distribution SD is not
  a clean scale parameter, which is itself a reason to treat any analytic adjustment as
  approximate.
- **Common random numbers are doing real work**: treated/untreated correlation at the same
  branch seed is r ≈ 0.66 on train (0.59 on dev). Var(Δ) therefore carries a −2ρσ²/n term, so
  any δ derived without CRN is an **upper bound** on the appropriate band.
- Applying the same 75th-percentile rule to a same-condition null of two 2-replicate means —
  which is on the same scale as a four-replicate Δ, needing no further √2 adjustment — gives
  **δ = 0.100 on train** and **δ = 0.200 on dev**.

### Label sensitivity (complete four-replicate points)

⚠ `f` is the **needed** fraction, `needed / n`. It is not the needless fraction; an earlier
analysis pass conflated the two and reported the needless column as `f`.

Train, n = 397:

| δ | needed | needless | ambiguous | f = needed/397 | 1 − f | needed extrapolated to 777 |
|---|---:|---:|---:|---:|---:|---:|
| 0.083 | 62 | 78 | 257 | 0.1562 | 0.8438 | ≈ 121 |
| **0.100 (train-derived)** | **54** | 67 | 276 | **0.1360** | **0.8640** | **≈ 106** |
| 0.140 | 32 | 52 | 313 | 0.0806 | 0.9194 | ≈ 63 |
| **0.166 (frozen)** | **25** | 46 | 326 | **0.0630** | **0.9370** | **≈ 49** |
| 0.200 (dev-derived) | 18 | 33 | 346 | 0.0453 | 0.9547 | ≈ 35 |

Dev, n = 332:

| δ | needed | needless | ambiguous | f = needed/332 | 1 − f |
|---|---:|---:|---:|---:|---:|
| 0.083 | 85 | 66 | 181 | 0.2560 | 0.7440 |
| 0.100 | 72 | 61 | 199 | 0.2169 | 0.7831 |
| 0.166 (frozen) | 43 | 43 | 246 | 0.1295 | 0.8705 |
| 0.200 | 36 | 33 | 263 | 0.1084 | 0.8916 |

(On dev at the frozen δ, needed and needless are both 43, so the two definitions of `f`
coincide there by accident — which is why the dev figure was unaffected by the conflation.)

### What this does to the gate

- At the **frozen** δ = 0.166: f_train = 0.0630, `f_train < 0.10` **FIRES**, ≈ 49 positives
  against the pre-registered 75.
- At the **train-derived** δ = 0.100: f_train = 0.1360, the gate **does not fire**, and ≈ 106
  extrapolated positives clears 75.
- At the **dev-derived** δ = 0.200: f_train = 0.0453, the gate fires harder, ≈ 35 positives.

**The campaign's central verdict turns on a parameter that a defensible derivation can move in
either direction.** That is the finding. It is not evidence that the frozen δ is wrong, and it
is not a licence to pick the value that yields the most positives.

### Cost, honestly stated

Narrowing δ buys positives by reclassifying points out of `ambiguous`, so it necessarily takes
some points that are near the boundary. Half-vs-half label agreement on train falls from
0.7229 at δ = 0.166 to 0.6851 at δ = 0.100 — about 4 points of stability for roughly double the
positives.

⚠ A previously recorded agreement figure of 0.8388 measures a **different quantity** (agreement
between the two-replicate and four-replicate labels on the same points, not agreement between
two disjoint replicate halves). The two should not be compared, and whichever is quoted should
be re-derived under a single stated protocol first.

### Status

**No amendment is made here.** δ remains frozen at 0.166 and every headline number stands as
recorded. This block exists so the sensitivity is on the record before any decision, and so
that a later decision to amend — or not to — is made in the open with the trade-off visible.

### Ceiling points — a third of train can never be `needed` (2026-09-18)

A point whose untreated arm already scores 1.000 cannot have Δ > 0: the treated arm has nowhere
to go. Such a point is structurally incapable of the `needed` label, and it enters the mean Δ
only as zero or as harm.

| split | complete n | ceiling (untreated = 1.000) | floor | contestable |
|---|---:|---:|---:|---:|
| train | 397 | **131 (33.00 %)** | 3 (0.76 %) | 263 (66.25 %) |
| dev | 332 | **68 (20.48 %)** | 0 | 264 (79.52 %) |

Robust to float noise: the counts are identical at a ≥ 0.999 threshold.

**The invariant that matters: excluding ceiling points does not create a single positive.**
`needed` is 25 on train at δ = 0.166 whether computed over all 397 complete points, the 266
non-ceiling, or the 263 contestable — and likewise 54 (train, δ = 0.100), 43 (dev, δ = 0.166),
72 (dev, δ = 0.100). The exclusion moves a **denominator**, never a numerator. So it changes
every reported *fraction* and changes the ASK training set not at all.

What it does to f:

| split, δ | f over all complete | f over contestable |
|---|---:|---:|
| train, 0.166 (frozen) | 25/397 = 0.0630 | 25/263 = **0.0951** |
| train, 0.100 | 54/397 = 0.1360 | 54/263 = **0.2053** |
| dev, 0.166 (frozen) | 43/332 = 0.1295 | 43/264 = **0.1629** |
| dev, 0.100 | 72/332 = 0.2169 | 72/264 = **0.2727** |

🔺 **Gate B's verdict does not turn on this.** At the frozen δ the gate condition `f_train < 0.10`
fires on *every* point set (0.0630 all, 0.0940 non-ceiling, 0.0951 contestable — the last only
just); at δ = 0.100 it fires on none. **δ moves the verdict; the ceiling exclusion does not.**
That is worth stating explicitly, because the ceiling correction is the more obviously
"correct-looking" adjustment and it is the one that changes nothing about trainability.

### What the ceiling drag does to the headline mean Δ

Ceiling points carry mean Δ = −0.0492 (train) and −0.0446 (dev) — pure harm by construction,
since help is identically zero there. Weighted by their share, that is a drag of −0.0162 on
train and −0.0091 on dev, and the mixture reconstructs the overall mean exactly.

| split | point set | n | mean Δ | mean help | mean harm |
|---|---|---:|---:|---:|---:|
| train | all complete | 397 | **−0.014393** | 0.034101 | 0.048494 |
| train | ceiling | 131 | −0.049172 | 0.000000 | 0.049172 |
| train | contestable | 263 | **+0.002766** | 0.051475 | 0.048709 |
| dev | all complete | 332 | +0.009702 | 0.058932 | 0.049230 |
| dev | ceiling | 68 | −0.044588 | 0.000000 | 0.044588 |
| dev | contestable | 264 | **+0.023686** | 0.074112 | 0.050426 |

**On train the sign of the headline flips**, from −0.0144 to +0.0028, purely by removing points
where the intervention could not have helped. On dev the positive estimate roughly doubles.
Both are small relative to SD(Δ) ≈ 0.16–0.18 over a few hundred points, so neither is a claim of
a real effect — the point is that the all-points mean is a **biased-downward** summary of the
intervention's value, because a third of the train points score it on a question it cannot win.

**No amendment is made here either.** The pre-registered estimand is over all points and stays
that way. This is recorded so that the all-points mean is never quoted as "the intervention
hurts on average" without the decomposition beside it.

---

## 🔻 Recent Results & Campaign Restructuring (2026-09-19)

### 1. W-24 — Paired sign-flip permutation null: train ASK labels are indistinguishable from noise

- **Report**: `campaign/workers/W24_PERMNULL.md`, commit `41938fa`.
- **HPC Job**: `25443463.aqua` on `cpu1n040`, exit 0 [OBSERVED campaign/workers/scratch_W24/w24_out.txt:1].
- **Protocol**: Paired sign-flip permutation null, 10,000 permutations, seed 20260918. For each complete point and branch seed, treated and untreated outcomes are swapped with probability 0.5. Pairing preserved [OBSERVED campaign/workers/W24_PERMNULL.md:18, 54-70].
- **Train (n = 397 complete points)**:
  - At frozen δ = 0.166: observed `needed` = 25 vs null mean 26.97 (null 95% [19, 36]), one-sided **p = 0.7124** — *below* the null mean. Observed `needless` = 46 vs null mean 26.95 (null 95% [19, 36]), **p = 0.0000**. Two-sided asymmetry (`needed - needless` = −21), **p = 0.0052** [OBSERVED campaign/workers/W24_PERMNULL.md:54-58, 170].
  - At train-derived δ = 0.100: observed `needed` = 54 vs null mean 52.26, **p = 0.4121**; `needless` = 67 vs null mean 52.08, p = 0.0050. Widening the band recovers more noise, not more signal [OBSERVED campaign/workers/W24_PERMNULL.md:66-70].
  - Observed mean Δ = −0.01439 vs null mean 0.000094 (one-sided p = 0.9926, below 95% null interval [−0.01162, 0.01179]) [OBSERVED campaign/workers/W24_PERMNULL.md:56].
- **Dev (n = 332 complete points)**:
  - At δ = 0.166: observed `needed` = 43 vs null mean 32.78 (p = 0.0204); observed `needless` = 43 vs null mean 32.88 (p = 0.0225); asymmetry = 0 (two-sided p = 1.0000) [OBSERVED campaign/workers/W24_PERMNULL.md:112-113, 174].
- **Conclusion**: On train, `needed` does not exceed chance under exchangeability. The labels produce noise, precluding `sft_c` training on this pool [OBSERVED campaign/workers/W24_PERMNULL.md:54-72, 183-193].

### 2. W-25 — Substitution analysis: later reviews confound the untreated arm

- **Report**: `campaign/workers/W25_SUBSTITUTION.md`, commit `113b249`.
- **HPC Job**: `25447958.aqua` on `cpu1n040`, exit 0 [OBSERVED campaign/workers/scratch_W25/w25_out.txt:1-12].
- **Mechanism**: In the J6 branch harness, the untreated arm had its focal review at step $s$ omitted, but the 5-step timer remained live. When an untreated run survived past $s$, it received substitute reviews at $s+5, s+10, \dots$ (median `n_later` reviews ranged 0 to 3+). Thus Δ measured *review timing/delay*, not total value of intervention [OBSERVED campaign/workers/W25_SUBSTITUTION.md:20-21, 38-41].
- **Dose-Response**: On train all-complete (n = 397), Spearman correlation between untreated `n_later` reviews and Δ is **ρ = −0.1634 (p = 0.0007)** [OBSERVED campaign/workers/W25_SUBSTITUTION.md:139].
- **Clean Counterfactual Subset (`n_later = 0`, train n = 175)**:
  - At δ = 0.166: observed `needed` = 11 vs null mean 5.18 (one-sided **p = 0.0051**, above 97.5th percentile of 9). Mean help = 0.0284 vs null mean 0.0152 (**p = 0.0007**) [OBSERVED campaign/workers/W25_SUBSTITUTION.md:158-161].
  - At δ = 0.100: observed `needed` = 20 vs null mean 10.74 (**p = 0.0010**) [OBSERVED campaign/workers/W25_SUBSTITUTION.md:169].
- **Caveats**:
  - Dev does not replicate the dose-response: dev Spearman ρ = +0.0949 (p = 0.0838, n.s.) [OBSERVED campaign/workers/W25_SUBSTITUTION.md:140].
  - Compositional confound: the `n_later = 0` bucket is 54.3% ceiling points on train (where untreated = 1.0) vs 2.1% in `3+` [OBSERVED campaign/workers/W25_SUBSTITUTION.md:214-222].
  - This analysis is doubly post-hoc. It licenses a clean counterfactual pilot (`suppress_next` mode in A8), not a formal claim [OBSERVED campaign/workers/W25_SUBSTITUTION.md:13, 206-224].

### 3. A7 — Value function V(state) = P(success | state) is no better than a step counter

- **Report**: `campaign/workers/A7_VALUE_FUNCTION.md`, commit `b6af8f4`.
- **Artifact**: `artifacts/verifiers/value_fn_20260919/` (job `25451256.aqua`).
- **Data**: 996 historical episodes, 15,618 steps (12,383 train / 3,235 dev) across 6 balanced campaigns [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:44-48].
- **Performance**:
  - Dev AUROC: **0.6212** (train 0.6508), dev Brier 0.2396, dev ECE 0.0866. Task-level bootstrap 95% CI: **[0.5457, 0.6891]** [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:59-69].
  - Feature-blind floor (train step-index prior applied to dev): **0.6245** [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:76-77].
  - k-NN ceiling proxy (k=5): **0.6356** [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:81-82].
- **Finding**: Dev AUROC lands *below the feature-blind floor*. The linear head over `feature_lr_v1` extracts zero task-state signal beyond step position. Dropped from live J8 routing [OBSERVED campaign/workers/A7_VALUE_FUNCTION.md:76-90].

### 4. A9 / A9b — J7 verifier threshold respecification: the threshold was meetable; 0.59 is a genuine miss

- **Report**: `campaign/workers/A9_THRESHOLD.md`, commit `0499d01`.
- **Mathematical Correction & Retraction**: The working assumption that label reliability ρ ≈ 0.45 imposes an AUROC ceiling of √0.45 ≈ 0.67 is **formally retracted**. √ρ is a bound on Pearson correlation, not AUROC. Under a Gaussian true-score model at ρ = 0.4504, a perfect latent-effect predictor achieves **AUROC 0.9622** on band-thresholded labels [OBSERVED campaign/workers/A9_THRESHOLD.md:29-32, 156-166]. A split-half empirical proxy on J7's own dev evaluation subset (n = 86) achieves **mean AUROC 0.9285** (range 0.8391 to 0.9776) [OBSERVED campaign/workers/A9_THRESHOLD.md:33-35, 266-269]. Both 0.65 and 0.70 were mathematically reachable.
- **Performance on J7 Dev (n = 86)**:
  - Fitted AUROC = **0.5917** [0.4677, 0.7111] [OBSERVED campaign/workers/A9_THRESHOLD.md:25-40].
  - Univariate features: `transcript_chars` = **0.6095**, `step` = **0.6001** [OBSERVED campaign/workers/A9_THRESHOLD.md:210-213].
  - Feature-blind floors: constant = 0.5000, step prior = 0.5070 [OBSERVED campaign/workers/A9_THRESHOLD.md:195-197].
- **Resolution**: 0.5917 is a genuine miss of the pre-registered threshold. The threshold is not lowered post-hoc. Preregistration is amended with floor/ceiling/interval reporting rules disclosed as written after seeing 0.5917 [OBSERVED campaign/workers/A9_THRESHOLD.md:85-89, 384-443].

### 5. A10 — Probe `hash_match` diagnosis and silent-zero fixes

- **Report**: `campaign/workers/STATUS_A_10.md`, `brief_A10_two_defects.md`, commit `5511775`.
- **Defect 1 (`hash_match`)**: `state_probe.py` reported 0 unconditionally because `gold_obs` compared against the observation after the *next* action. Because `snapshot_hash` covers the cumulative IO log, equality was impossible. Probe schema bumped v3 → v4. Version-3 `hash_match` values are uninformative/meaningless. `state_equivalent` (0.676) is unaffected [OBSERVED brief_A10_two_defects.md:20-46].
- **Defect 2 (`hj1_gate.py`)**: Silent coercion of missing dictionary fields (`x or 0.0`) to zero was fixed to differentiate missing data (null) from true recorded zeros [OBSERVED brief_A10_two_defects.md:54-79].

### 6. J8 Frontier Harness & Infrastructure (A4, A5b, A6, A8, A12, A13)

- **A4** (commit `c9e1733`): `make_verifier` in `src/sidekick/runner.py:196` wired to return bare `FeatureVerifier.load(path)` with `.score(state)` [OBSERVED campaign/workers/STATUS_A_4.md:7-8].
- **A5b** (commit `be4d2d6`): Generated 12 J8 YAML configurations in `configs/`: `hj8_executor_alone_bplus.yaml`, `hj8_sft_plan_bplus.yaml`, `hj8_fixed_k_{3,5,10}.yaml`, `hj8_router_seq_tau{03,05,07}.yaml`, `hj8_sidekick_tau{03,05,07}.yaml`, `hj8_oracle_escalation.yaml`. `scripts/setup/verify_configs.py` exits 0 [OBSERVED campaign/workers/STATUS_A_5b.md:22-32, 140-143].
- **A6** (commit `da4c115`): PBS job harness `scripts/pbs/hj8_frontier.pbs` written for the 12-arm J8 frontier evaluation [OBSERVED campaign/workers/STATUS_A_6.md:3-5].
- **A8** (commit `a25d8c9`): Clean-counterfactual branch mode implemented in `scripts/setup/branch_counterfactual.py` with `--untreated-mode suppress_next` and `EpisodePrefix.skip_next_scheduled_review` in `src/sidekick/systems/loop.py:95` [OBSERVED campaign/workers/STATUS_A_8.md:13-28, 66-67].
- **A12** (commit `0105d9e`): J10 analysis script `scripts/analysis/j10_report.py` created before data collection, supporting task-level bootstrap, preregistered hypothesis evaluations, and null handling for missing metrics [OBSERVED campaign/workers/STATUS_A_12.md:5-24].
- **A13** (commit `8c64881`): Guard checks added to `scripts/pbs/hj8_frontier.pbs` for adapter weights presence and `SMOKE_ONLY=1` preflight verification [OBSERVED campaign/workers/STATUS_A_13.md:20-22].

### 7. J8a — two baselines on dev (`executor_alone`, `sft_plan`; job 25460140, 2026-09-19)

Campaigns `hj8_executor_alone_bplus_20260919` and `hj8_sft_plan_bplus_20260919`,
job `25460140.aqua` on `gpu1n009`, commit `79ce6c73`, adapter `sft_b_plus`,
dev 57 tasks × seeds {1,2} = 114/114 each, `ARMSET=free`. **These are the two
J8a baselines, not a frontier.** No live-planner arm has run; nothing here
speaks to adaptive-vs-fixed allocation. Dev has been inspected many times:
calibrate and bound, not a thesis result. Full write-up:
`campaign/workers/A15_J8A.md`. Analysis job `25463395.aqua`.

**Zero hosted planner quota.** `executor_alone`: 114/114 `n_planner_calls=0`,
zero planner events, `planner_tokens_total=0`, `usd_total=0.0`. `sft_plan`: 114
`provider="cache"` replays of one packet, 0 tokens, 0 hosted `codex` events,
`usd_total=0.0`. Independent `n_broken=0` on both arms (`BROKEN` =
api_error/timeout/crash/parse_error; `limit` is a scored outcome).

| | `executor_alone` | `sft_plan` |
|---|---|---|
| solved / 114 | 15 | 46 |
| TGC (unpaired mean) | 0.131579 | 0.403509 |
| mean goal_pass_rate | 0.528886 | 0.700009 |
| planner calls / episode | 0.0 | 1.0 (cache) |
| mean steps | 21.94 | 19.62 |
| `limit` episodes | 31 | 21 |
| hit `max_steps=40` | 32 | 21 |

⚠ The job-log per-seed TGC means (executor 0.1404 / 0.1228, sft_plan 0.4211 /
0.386) are unpaired and are not the result.

**Paired contrast `sft_plan − executor_alone`**, `hj1_gate.paired_diff(resample="task")`,
10,000 resamples, seed 20260915, 57 tasks / 114 pairs / 0 dropped:

- TGC **+27.19 pp**, task-clustered 95% CI **[16.67, 37.72]**
- goal-pass-rate **+17.11 pp**, task-clustered 95% CI **[10.36, 23.74]**
- planner calls **+1.00** per episode (degenerate)
- steps **−2.32**, task-clustered 95% CI **[−5.53, 0.83]** (includes 0)

The TGC/goal-pass gaps show the **cached plan's contribution** against a bare
trained executor. They do **not** show that adaptive allocation beats fixed
allocation.

`j10_report.py` ran **unmodified** on these two archives, inventoried both
arms as complete, and emitted no contrast: it requires the full J10 arm set
and only contrasts `sidekick − *`. That is a J10-script limitation, not a
data problem. Goal-pass CIs were computed by the A15 helper with the same
`paired_diff` call the script uses for TGC.

### 8. Discard Record: 2026-09-19 Smoke Collision (`b1_pilot_train_20260919_smoke` & `hj8_*_20260919livesmoke_smoke`)

The result trees `/scratch/n12194778/sidekick/results/b1_pilot_train_20260919_smoke` and every `hj8_*_20260919livesmoke_smoke` tree (`/scratch/n12194778/sidekick/results/hj8_*_20260919livesmoke_smoke`) contain **no valid data** and must never be analysed or resumed from because a vLLM port 8000 collision on node `gpu0n007` between jobs `25519712` and `25519749` routed B1 requests to J8's server (failing with 404 missing LoRA alias `sft_b` on 20/20 rows) and subsequent B1 node-wide cleanup killed J8's server mid-run (arms 2–10 failed on step 1).



