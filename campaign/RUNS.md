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
