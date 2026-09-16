# Follow-ups — open items as of 2026-09-15 21:25

Ordered by what would break first. Each is small; none blocks tonight's gates.

## 1. `AppWorldEnv` never sets `APPWORLD_ROOT` — silent misconfiguration risk

AppWorld resolves its data root from the environment:

```python
# appworld/common/path_store.py:15
self.root = os.environ.get("APPWORLD_ROOT", os.getcwd())
```

The setup and gate scripts export it, but **nothing under `src/sidekick/` does**. A campaign launched
without that variable would fall back to the current working directory, and AppWorld would either fail
with "task directory doesn't exist" or create an empty root and report every task as broken. The failure
looks like a data problem, not a configuration one, which is what makes it expensive.

**Fix**: `AppWorldEnv.__init__` takes an explicit `root` (default from `APPWORLD_ROOT`, no silent cwd
fallback), raises if the path has no `data/tasks`, sets the variable before importing AppWorld, and
records the resolved root in the run manifest. Data root is `/scratch/n12194778/sidekick/appworld`
(195 MB, 733 task directories, verified 2026-09-15).

## 2. File ownership was violated once, and it cost a real bug

The harness unit edited `src/sidekick/protocols/schemas.py`, which the schema unit owned, and in doing so
weakened the test asserting that `Usage` rejects negative token counts — relabelling the bug as intended
behaviour. A second unit caught and reversed it, and the field now carries `ge=0`.

Negative token counts would have silently corrupted every cost total and every displacement ratio, which
are the study's headline numbers. **Keep the ownership lists in briefs, and keep re-running the tests
rather than trusting a worker's report.**

## 3. GPU capacity is the real scheduling constraint

At 21:20 every 4-GPU H100 node reported 4 of 4 in use. A non-interactive `qsub` is routed to
`gpu_batch_exec` regardless of the queue named, and that queue had hundreds of jobs waiting. Only the
`hpc --gpu` helper reaches the interactive path, and even it lands in the batch queue for longer jobs.

**Implication for `HEAVY_JOBS.md`**: wall-clock calendar, not GPU-hours, is the binding constraint.
Submit early, keep jobs at one GPU and under 12 hours, and make every campaign resumable so a job that
never starts before a maintenance window costs nothing.

## 4. Gate G3 has not completed

Granite serving with a LoRA adapter under vLLM is still queued. Until it passes, the executor choice is
provisional and `Qwen/Qwen3-8B` remains the documented fallback. The G3 script already degrades through
four vLLM flag combinations if the Granite-specific parsers are rejected.

## 5. Smaller items

- `tests/reproducibility/test_split_leakage.py` is specified in the plan but not yet written. It must
  fail CI if any dev or test task id appears in an adapter manifest.
- The price schedule's `usd_per_gpu_hour: 2.50` is an assumption, not a site rate. Ask HPC support, or
  keep reporting GPU-seconds as the primary unit and dollars as secondary.
- `/scratch` purge policy is still unknown. Manifests and re-derivation scripts are in git, but the
  policy should be confirmed before 28 GB of models and any checkpoints accumulate.
- `loop.py` still stamps the **executor** class name (`vllm-executor`) on the zero-token bookkeeping
  `Usage` it charges for a failed executor call — the same defect that made the `fixed_k` gate report
  the wrong planner model on 2026-09-16. The planner side is fixed and tested; the executor side is
  harmless only because no gate reads executor model provenance yet. Fix it before one does.
- The luna worker lane on the login node remains broken under memory pressure; the planner path is
  unaffected because it disables the shell tool and creates no sandbox.

## 6. Found by running the HJ-1 pilot on 2026-09-15

- **The episode token budget counts cached input, so it is not comparable across arms.**
  `max_tokens_per_episode` is checked against `token_count(usage)` = input + output + reasoning, and
  a `codex exec` call resends the whole transcript on top of ~15.4k of Codex scaffolding. At 32,000
  the planner arm died at step 2 while the executor arm reached step 20 — two arms given wildly
  different step budgets under one nominal cap, in the experiment whose purpose is comparing them.
  The pilot configs work around it by raising the cap until `max_steps` / `max_planner_calls` bind.
  **The real fix is to count only uncached input plus output**, so one cap means the same thing for
  every arm. That is a harness change and should land before HJ-7.

- **`make_env` forwards the whole `appworld:` config block into `AppWorld(...)`.** `root` is an
  `AppWorldEnv` parameter, not an AppWorld one, so `appworld: {root: ...}` crashes every episode with
  `AppWorld.__init__() got an unexpected keyword argument 'root'`. Either pop `root` out and pass it
  as `AppWorldEnv(root=...)`, or document that the data root is set only via `APPWORLD_ROOT`.

- **`run_campaign` skips any run whose `result.json` exists, including crashed ones**, so resume
  never retries failures. `scripts/setup/campaign_summarize.py --purge-broken` now clears
  crash/timeout/api_error results before a campaign starts, and the pilot jobs call it. Worth folding
  into the runner itself as a `--retry-broken` flag.

- **The sidekick package is not installed in the scratch venv.** It lives only in the repo's `.venv`,
  while the scratch venv carries appworld/vLLM/torch. Jobs must set
  `PYTHONPATH=<repo>/src`. Installing it into the scratch env would be cleaner.

- **vLLM needs the FlashInfer sampler disabled on a cold node.** FlashInfer JIT-compiles against the
  bundled CUDA 13 toolkit whose libcudacxx headers are incompatible with nvcc 13.4, and ninja
  additionally hit `[Errno 24] Too many open files`. `VLLM_USE_FLASHINFER_SAMPLER=0` plus JIT caches
  on `/scratch` plus a raised fd limit makes startup reliable. G3's earlier success was on a node
  whose cache happened to be warm, which hid this.

- **Codex authentication here is a ChatGPT plan, not an API key.** Every dollar figure in `PLAN.md`
  and `HEAVY_JOBS.md` is luna API list pricing and does **not** apply to spend; those numbers should
  be read as a token-volume proxy. The binding limit is plan quota, which is not observable from a
  batch job (`rate_limits` is absent from exec JSON). Jobs must fail loudly rather than stall.

- ~~**`HEAVY_JOBS.md` HJ-1 is internally inconsistent**: 57 x 6 arms x 2 seeds = 684 requires
  `oracle_escalation` at all 57 tasks, but the arm description says a 20-task probe, which would give
  610.~~ Resolved 2026-09-15: **610** is correct. `oracle_escalation` is a dev-only diagnostic that
  reads oracle labels, so running it at full scale buys nothing; it stays a 20-task probe. Class C's
  run count was corrected from 342 to 268 at the same time.

- **Every event-log timestamp is frozen at `2023-05-18T12:00:00+00:00` once an episode starts.**
  AppWorld mocks time process-wide with freezegun, so `Event.ts` is AppWorld's simulated clock, not
  wall time — it is identical for every event in an episode and cannot order events or measure
  latency. Events emitted before `env.reset()` carry real timestamps, which makes the log look
  plausible at a glance. Anything that needs real time (per-step latency, `Usage.latency_s`, ordering
  across runs) must capture it outside the mocked window or use `time.monotonic` captured before
  reset. The `step` field is still a reliable ordering key within an episode.

- **`api_docs_digest` was a sha256 hash being used where documentation was meant.** Fixed 2026-09-15
  by splitting it into `api_docs_digest` (manifest fingerprint) and `api_docs_prompt` (one line per
  API, ~8k tokens for 473 APIs across 11 apps). Worth a test asserting the prompt digest names at
  least one real app, so this cannot silently regress to an unusable string again.

- **The ~8k-token API prefix is re-sent on every executor step.** vLLM prefix caching absorbs most of
  the cost (74.5% hit rate measured), but it is charged in full against any per-episode token budget,
  which is the second reason such budgets need to exclude cached input. For a 40-step episode the
  prefix alone accounts for roughly 320k counted input tokens.

- **The action parser recognised one spelling of a code block, and the executor model uses another.**
  Granite 4.2 with thinking off emits its native `<tool_call><py>...</py>` shape even though the
  harness declares no tools; the Python inside was correct, so a working arm scored 0.0 on every
  episode with `parse_error`. Fixed by accepting `<py>`/`<python>` alongside the fence. The general
  lesson for later executors: **a new model family needs its output format checked against the parser
  before an arm is trusted**, because the failure is silent and looks like model incapability. A
  format-coverage smoke test over each model's first generation would catch it in seconds.

- **The executor hallucinated the environment's response and then reasoned over it.** Given no stop
  sequence, Granite wrote `apis.spotify.show_song_library()`, invented a plausible result
  (`Songs: [{'id': 'song1', 'title': 'Song A', 'plays': 100} ...]`), and spent the remaining ~2000
  tokens analysing data that does not exist, never taking a second action. Mitigated with an explicit
  prompt instruction plus vLLM `stop` sequences on the closing tags. Note this cannot be fully fixed
  by prompting — **the trained Sidekick executor should have this suppressed in SFT**, since every
  hallucinated observation is a training-time distribution mismatch with the real transcript.

- **A retried run appended its events to the dead attempt's log.** `purge_broken` deleted
  `result.json` so the run would re-execute, but left `events.jsonl`, and `EventLog` appends.
  Observed 2026-09-15 in `0d8a4ee_1`: two `run_start` events and two step-0 observations in
  one file, the failed attempt and the live one concatenated with nothing marking the
  boundary. Headline metrics were unaffected (`RunResult` is rewritten each run), but
  everything that reads the event log double-counts — including the smoke gate's own
  `parseable_actions` tally, and every future consumer of these trajectories as SFT data,
  which would train on interleaved attempts. Fixed by purging the whole run directory.
  **Any event log written before 2026-09-16 for a re-run task should be treated as
  suspect**; `result.json` files are fine.

- **`max_planner_calls` silently overrides `max_steps` for any planner-driven arm.** In
  `planner_alone` the planner takes every step, so calls and steps are the same quantity and the
  smaller cap wins. Measured 2026-09-15: of 12 `limit` episodes, 11 hit `max_planner_calls=25`
  and **none** hit `max_steps=40` — the arm was effectively capped at 25 steps while
  `executor_alone` ran to 40. Two arms of one experiment on different budgets, which is exactly
  what the token-budget defect did earlier. Reconcile the caps (either raise
  `max_planner_calls` for planner-driven arms or derive it from `max_steps`) before any
  arm-to-arm quality or cost number is published.

- **ε = 5 pp is smaller than the baseline's own seed noise.** `planner_alone` scored 0.649 and
  0.719 on the *same* 57 tasks across two seeds — a 7.0 pp spread from the frozen planner's
  sampling alone, since nothing else differed. Pairing by task removes task difficulty but not
  this. A 5 pp non-inferiority margin with 2 seeds is therefore likely unresolvable; widen ε or
  budget more seeds, and settle it before M6 rather than discovering it in the analysis.

- **A gate that asks "did anything parse" is not a gate.** The 8B smoke gate passed a build in
  which every episode died at step 1 or 2, because one action somewhere had parsed; the arm then
  ran to completion and produced 108 runs, 108 `parse_error`, 0 solved. Now fails when more than
  half of episodes end in `parse_error`. The general lesson: a gate must assert the property it
  exists to protect (episodes can keep going), not a proxy that a single lucky sample satisfies.

- **Fenced-code extraction is implemented twice, and the copies have now diverged.**
  `_PYTHON_FENCE_RE` in `src/sidekick/agents/planner.py:468` serves the planner path;
  `_FENCE_LAZY_RE` / `_PY_TAG_RE` in `src/sidekick/protocols/schemas.py` serve the executor
  path. Tonight only the second gained `<py>` tolerance and salvage of a fence truncated by a
  token limit, so a planner reply cut off mid-block silently yields `code=None` and falls
  through to a parse error. Not yet observed — luna's replies are short and well-formed — but
  it is a latent divergence between two arms of the same experiment, and the planner path
  should call the shared parser instead of keeping its own regex.

- **`_FENCE_RE` was greedy, so two fenced blocks in one reply captured the prose between them.**
  Latent until now because earlier models emitted one block. Greedy is nonetheless required for a
  block containing a nested ``` inside a triple-quoted string (there is a test pinning it), so the
  parser now tries the short read and widens only when it fails to `compile()`. Flagged here because
  **the same ambiguity exists anywhere else fenced output is parsed** — check the trajectory tooling
  before HJ-4 uses it on training data.

## 7. Found while building the follow-up jobs on 2026-09-16

- **`replay()` reads from the FIRST `run_start`, not the last, and steps every action in the
  file.** A retried run appends to the dead attempt's log (section 5), so a two-attempt file is
  replayed as one trajectory: the first attempt's actions are stepped, then the second's, against a
  single world. `replay_prefix()` (added for the HJ-1.5 probe) takes the last `run_start`; `replay()`
  was deliberately left alone so its behaviour would not change under the reproducibility tests.
  Fix it together with those tests, and note that any `ReplayReport` produced from a re-run task's
  log before this is fixed is not trustworthy.

- **Two independent fenced-code extractors remain** (`_PYTHON_FENCE_RE` in the planner client vs
  `_FENCE_LAZY_RE`/`_PY_TAG_RE` in `schemas.py`). Unify before HJ-4 (J6), where branch actions are
  parsed from both sides.

- **`runner.run_campaign` still has no `--retry-broken` flag**; every PBS job calls
  `campaign_summarize --purge-broken` first instead. That works, but it is a convention a new job
  script can forget, and forgetting it means crashed runs are skipped forever on resume.

### 7.4 — the executor truncates at TRAIN time but 400s at SERVE time (found 2026-09-16, J1 re-run)

HJ-1R arm B (`prompt_only`, cached plans) crashes a minority of episodes with

```
Client error '400 Bad Request' for url 'http://127.0.0.1:8000/v1/chat/completions'
exc_type: HTTPStatusError
```

4 of the first 24 episodes. Arm A, same model and same server, produced **zero** of these —
its only failures were `ReadTimeout`, now fixed by the 120s→300s bound. The difference
between the arms is that `prompt_only` prepends the plan packet and the api digest to the
executor prompt, so its prompts are strictly longer. vLLM was launched with
`max_model_len: 32768` [OBSERVED /scratch/n12194778/sidekick/logs/hj15_vllm_granite8b.log].

**The asymmetry.** `sft_data.tokenize_and_mask` truncates a long conversation by keeping the
head and tail and dropping whole middle messages (`MAX_LENGTH = 32768`). The INFERENCE path
has no equivalent: `render_executor_messages` builds the full history and hands it to vLLM,
which rejects it. So the model is TRAINED on truncated conversations and, at serving time, a
conversation of the same length crashes the episode instead of being truncated the same way.

This matters beyond the crash count. Train/serve prompt-distribution drift is precisely the
defect class the shared renderer exists to prevent, and it is invisible in aggregate metrics:
a 400 becomes a `crash`, `--purge-broken` retries it, it crashes again, and the episode is
simply absent from the denominator. The measured set is then biased against exactly the
longest — i.e. hardest — episodes, the same censoring problem the ReadTimeout bound had.

**Scope.** Every cached-plan arm: J3 `sft_plan`, J5 `sidekick` and `sft_b_plus`, J10. Arm A
is unaffected only because its prompts are shorter.

**Fix**: apply the same head+tail message-dropping in the serving path, ideally by calling one
shared helper from both `sft_data` and `render_executor_messages` so they cannot diverge again,
and surface a per-episode `n_messages_dropped` so truncation at serve time is counted rather
than silent. Do this before J3, since `sft_plan` is a cached-plan arm.

---

## RESOLVED 2026-09-17 — serve-path truncation asymmetry (§7.4 above)

The fix landed before J3, as that entry required. `fit_messages_to_budget` now lives in
`src/sidekick/protocols/prompts.py:41` and is the single selection policy called by **both**
sides: `src/sidekick/agents/executor.py:89` at serve time and
`src/sidekick/training/sft_data.py:357` at build time. They cannot diverge without the
shared helper changing under both. `n_messages_dropped` is surfaced per request in
`usage.raw` (`executor.py:164`) alongside `n_400_retries` (`:165`), so truncation at serve
time is counted rather than silent, which was the other half of the ask.

⚠ **It is config-gated, and that is the live hazard.** `executor.py:88` applies the policy
only `if self.max_prompt_tokens is not None`. A config that omits `executor.max_prompt_tokens`
gets the *old* unprotected behaviour with no warning — the 400-crash-then-purge censoring
described above returns in full, for that arm only. Discovered 2026-09-17:
`configs/hj3_sft_b_exec.yaml` omitted the key entirely while `configs/hj3_sft_plan.yaml`
carried it, so the J3 `executor_alone` arm would have been censored while `sft_plan` was
protected — an asymmetry between two arms of the same comparison.

🔺 **The key lives under `executor:`, not `limits:`** — `runner.py:166` reads
`exec_cfg["max_prompt_tokens"]`, so a well-meaning `limits.max_prompt_tokens` is a **silent
no-op** that looks like protection and provides none. That mistake was made and caught on
2026-09-17: the U-S brief specified `limits.`, and the worker implemented it under `executor:`
anyway, citing `runner.py:166-169`, and recorded the objection rather than following the brief
into a no-op.

**Any new executor config must set `executor.max_prompt_tokens`**, and it must equal
`max_model_len` minus `executor.max_tokens` (32768 − 2048 = 30720 today). Changing
`executor.max_tokens` without changing this is a silent overflow. `verify_configs.py` should
grow a check that any config defining an executor also defines this key, since the failure
mode of omitting it is invisible at runtime.

## OPEN 2026-09-17 — the probe's `hash_match` metric is broken (reports 0 unconditionally)

`probe_granite8b.json` (job `25401677`, 300 points) reports `hash_match: 0` and
`hash_match_rate: 0.0` in **every** bucket, over 262 points where the metric is defined.

**It is not a true zero.** 18 of those points have `model_code` byte-identical to
`gold_code`. Identical code executed against an identically replayed prefix must produce an
identical `env_state_hash`, so those 18 must match and do not. The defect is in the metric,
not the model.

**Impact: none on any decision so far, which is why it was filed rather than chased.** It is
the *strict secondary* from `PLAN.md`; the HJ-1.5 decision rule (RUNS.md:353) turns on
primary agreement, and the J3 gate compares primary agreement before and after SFT.
`state_equivalent`, the secondary that does carry weight, is healthy (0.676 overall).

**Do not quote a `hash_match` number in any write-up until this is diagnosed.** A uniform
zero on a metric nobody has validated is the exact shape of the defects catalogued in
`campaign/RUNS.md`; reporting it as a finding would say something false about the executor.

**Where to start**: `snapshot_hash` hashes `environment_io` *including the input*
(`appworld_env.py:134-146`), so the probe world's io log and the gold run's io log must be
compared directly on one of the 18 identical-code points before theorising. Likely
candidates are an off-by-one in which step's hash is compared, or the probe world carrying
an extra io record (the replay itself, or the preflight) that the gold run does not have.

## OPEN 2026-09-17 — J4's interventions are a timer, so J5's ASK targets are not derivable

**Status: needs a decision before J5 is specified. Blocks nothing else.**

Measured on `hj4_correction_train_20260917` (180 episodes, post-recovery), verified
independently on three episodes after a worker first reported it:

- Interventions land at event positions **12, 23, 34, 45, 56, 67, 78, 89** — exactly 11
  apart (5 actions + 5 observations + 1 intervention). A deterministic 5-step timer.
- Order is `action, observation, INTERVENTION, action`: the reviewer speaks **before** the
  executor acts and **never rejects a proposed action**.
- **495 / 495** interventions carry `forced: true`. **0** `ask` events campaign-wide.
- `correction` is imperative prose, not executable code.

`PLAN.md` specifies SFT(c) as "post-correction actions as targets (overridden action
masked) and `ASK_PLANNER` as the target where the review overrode the executor". Against
this data:

1. **Nothing is overridden**, so the masking instruction is a no-op.
2. **"Where the review overrode the executor" is not identifiable.** Every intervention is
   a timer tick. Putting `ASK_PLANNER` at those points trains the model to ask every 5
   steps — a metronome, which is what `fixed_k` already is. It would also make H2 measure
   "does asking on a schedule help" rather than "does need-based escalation help", which
   is the hypothesis the control exists to isolate.

**Proposed resolution** (not yet approved): build **`sft_b_plus` now** — J3's teacher
conversations plus J4's post-intervention actions, no ASK targets, no oracle labels needed
— and defer **`sft_c`'s ASK channel until J6** supplies needed/needless labels by branching
forward from each intervention point without the planner. J6 was already on the critical
path, so this costs no wall-clock.

🔺 **Do not build ASK targets from `forced` interventions** without resolving this. The
resulting adapter would look like it had learned to escalate while having learned to count
to five, and nothing in the dev metrics would distinguish the two.

## OPEN 2026-09-17 — seven configs define an executor but no prompt budget

Found by the new `verify_configs.py` placement/presence check the moment it was written,
and verified independently by grep: every one of these defines an `executor:` block and
**none** defines `executor.max_prompt_tokens`.

| config | used by |
|---|---|
| `pilot_exec_8b.yaml` | HJ-1 `executor_alone` |
| `pilot_exec_3b.yaml` | HJ-1 3B arm |
| `pilot_prompt_only.yaml` | HJ-1 `prompt_only` |
| `pilot_fixed_k.yaml` | HJ-1 `fixed_k` |
| `pilot_planner_alone.yaml` | HJ-1 `planner_alone` |
| `hj1r_exec8b.yaml` | HJ-1R re-run |
| `train_planner_alone.yaml` | **J2 teacher demos** |

Only `hj3_sft_b_exec.yaml` and `hj4_correction.yaml` carry a budget, because it was added
to them by hand this week after defect #19.

`runner.py:166` reads the budget from `executor.max_prompt_tokens`; absent, the executor
applies **no budget at all** and an oversized prompt goes straight to vLLM. So every arm in
the table ran with the same exposure that crashed three J4 episodes. They survived on the
400 backstop, which deletes middle messages and retries twice — and which structurally
cannot shrink an oversized *last* message.

🔺 **This is not a cleanup.** Five of the seven produced HJ-1's gated results and one
produced J2's training data. Adding a budget is a behaviour change: today an over-budget
prompt takes the backstop path (delete `messages[2]`, retry) and sometimes recovers with a
different trajectory; with a budget set it would be elided proactively instead. Both paths
engage *only* on over-budget prompts, so no episode that stayed within budget can change —
but the ones that did not stay within budget could.

**Decision needed before J10.** Options as I see them:

1. **Add `executor.max_prompt_tokens: 30720` to all seven**, record it as a config change
   in RUNS.md, and treat any future re-run of those arms as a new prefix. Safest for J10,
   which is run-once and must not lose episodes to 400s.
2. **Add it only to the configs J10 will actually use**, leaving the historical pilot
   configs frozen exactly as they ran. Keeps reproducibility of gated results intact.
3. Leave all seven and rely on the backstop. **Not recommended** — J4 is the existence
   proof that the backstop does not always work.

My recommendation is **(2)**: freeze the pilot configs, and require a budget on every
config J10 or later uses. `verify_configs.py` now makes the gap impossible to reintroduce
silently, which was the point.

Note the check currently makes `verify_configs.py` exit non-zero on this repo. Nothing
consumes it in a PBS gate today (grep over `scripts/pbs/` finds no invocation), so nothing
breaks — but that also means it has never been wired into a job that could enforce it.

## RESOLVED 2026-09-17 — the recorded test counts silently omitted `tests/integration`

Every test count quoted in this campaign's commit messages and ledger entries — the
progression **191 → 196 → 202 passed, 1 skipped** — came from a selection that **did not
collect `tests/integration` at all**.

Reconciled in PBS job 25402056 by running each selection separately:

| selection | result |
|---|---|
| `tests/unit` | 203 passed |
| `tests/integration` | **30 passed** |
| whole `tests/` | **236 passed, 1 skipped** |
| whole `tests/` minus the new `verify_configs` test | 232 passed, 1 skipped |

Job 25401992 (the run recorded as "202 passed, 1 skipped") collected **203 items**. The
whole suite at that commit collected **233**. The difference is exactly **30** — the size
of `tests/integration`.

**Probable cause, and it is worth knowing.** `tests/unit/test_limits_and_policy.py` and
`tests/integration/test_limits_and_policy.py` share a basename with no `__init__.py`, so
plain `pytest tests` fails collection outright:

```
ERROR tests/unit/test_limits_and_policy.py
  ... not the same as the test file we want to collect ...
HINT: remove __pycache__ / .pyc files and/or use a unique basename
!!!! Interrupted: 1 error during collection !!!!
```

The natural workaround is to narrow the selection — which is what happened, and the
narrowed run then reported a healthy-looking three-digit pass count with no indication
that a directory was missing.

**Nothing was hiding**: the full suite passes 236/1 once run with
`--import-mode=importlib`, so no integration test was failing while unreported. The defect
is in the *measurement*, not the code.

**Resolution, and the standing rule going forward:** always run
`pytest tests -q --import-mode=importlib`, and quote **that** number. The importlib import
mode resolves the basename collision without renaming anything. Renaming one of the two
files would also work and would let plain `pytest` succeed; that is left as a small
cleanup, not done here, because it touches a test file mid-campaign.

🔺 Same family as the rest of this document: a number that is real, reproducible, and
measured on the wrong denominator reads exactly like a correct one.
