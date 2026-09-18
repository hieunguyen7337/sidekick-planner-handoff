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

## RESOLVED 2026-09-17 — J4's interventions are a timer, so J5's ASK targets are not derivable

**Resolution adopted 2026-09-17**: see `campaign/RUNS.md` ("The campaign from here: gates A and B, written before the jobs (2026-09-17)") [OBSERVED campaign/RUNS.md:1342-1360].

- **Branches first**: J6 (counterfactual branches) is re-sequenced ahead of SFT(c) (J5b).
- **ASK targets come from J6 branch labels**: J5b (`sft_c`) trains the `ASK_PLANNER` channel specifically on intervention points where proceeding unaided failed (`needed` label).
- **`sft_b_plus` is the no-ASK control**: J5a (`sft_b_plus`) is built from J2 teacher demonstrations plus J4 post-correction actions with **no `ASK_PLANNER` targets**, isolating the effect of the escalation channel against an exact data-volume match.

## OPEN 2026-09-17 — verifier trained on timer-tick states only may exhibit calibration bias across arbitrary steps

The J6 counterfactual branch labels exist exclusively at timer-tick states (steps 5, 10, 15, …) where `fixed_k` interventions occurred [OBSERVED campaign/RUNS.md:1205-1215]. However, during live deployment in `sidekick` (and under `router_seq`), the verifier scores executor candidate states at *every* step.

The verifier is therefore trained on a biased subsample of states (states reached at 5-step intervals under periodic review). Consequently, dev calibration metrics (AUROC, ECE, Brier score) measured on branch labels may not transfer uniformly to arbitrary execution steps.

**Impact & investigation**: Evaluate escalation rates and needless-ask rates during the J8 dev frontier sweep; check whether the verifier over-triggers at non-timer steps or exhibits step-depth calibration drift.

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

---

## RESOLVED 2026-09-18 — the J6 branch job writes its server log and PBS stdout to paths that carry no campaign id

`scripts/pbs/hj6_branches.pbs` sets

```bash
#PBS -o campaign/workers/logs/hj6_branches.out
VLOG="${LOGDIR}/hj6_branches_vllm.log"
```

with no `${CID}` and no `${SPLIT}` in either the PBS `Output_Path` or `VLOG`, and starts the server with
`> "${VLOG}" 2>&1`. Every J6 submission (both dev and train) therefore targets the same files.

Observed 2026-09-17 with 25410220 (train) and 25412541 (dev) running concurrently on
different nodes:
- The dev job's redirect truncated the file to zero while the train job's server still held
  an open descriptor at a large offset, so the two output streams now interleave into one
  sparse file and neither can be read as a record of its own job.
- Because both vLLM servers wrote the same log with `>`, they overwrote each other at
  overlapping offsets, and the dev server's output appears to stop at 19:33 when it had not —
  **the log was unusable for diagnosing the wedged branch below**, and a reader could easily
  have concluded the server died.
- The same defect applies to the job's `Output_Path` (`campaign/workers/logs/hj6_branches.out`),
  which dev and train both write concurrently.
Execution is unaffected — the descriptor survives the truncation — but the log is no
longer evidence about either run, which is the whole reason it is kept.

This bit while diagnosing a genuine throughput question (train sustaining 4.70 completed
branches/min against dev's 7.80 for identical per-branch work -- 1.7x, measured over a 65-minute steady-state window; an earlier reading of ~4x came from dev's startup burst), and the ambiguity about
which job's server the tail belonged to cost time that a per-CID path would not have.

Fix: `VLOG="${LOGDIR}/${CID}_vllm.log"` and `#PBS -o campaign/workers/logs/hj6_branches_${CID}.out`
(or passing `-o` with campaign ID at `qsub` time). Not applied mid-run, because editing the script
while two jobs are executing from it risks the held resume job (25412609) picking up a
half-edited file. Apply before the next J6 submission after the resume completes.

**Resolution (2026-09-18, commit `2216a0b`)**: `#PBS -o` is evaluated at **submit** time and
cannot interpolate `${CID}`, which is computed inside the script — so the directive now names
the log directory `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/`
rather than a file. PBS then writes a unique `<job ID>.OU` there, ensuring train, dev and a resume
cannot share a path, and a job that dies before the script runs still leaves a findable log
[OBSERVED scripts/pbs/hj6_branches.pbs:7-15]. The script additionally `exec`s a `${CID}.${JOBTAG}.out`
log (`${CID}.${PBS_JOBID}.out`) as soon as the campaign id is known, so an early death *after* startup
still leaves a campaign-id-named log [OBSERVED scripts/pbs/hj6_branches.pbs:33-43]. `VLOG` now carries
the campaign id and job tag (`${LOGDIR}/${CID}.${JOBTAG}_vllm.log`) [OBSERVED scripts/pbs/hj6_branches.pbs:73].
This resolves the log collisions that previously cost two misdiagnoses during the J6 crash and
throughput investigations.

⚠ Same family as everything else in this document: nothing failed, nothing reported an
error, and the artifact that would have told you what happened quietly stopped being
about the run you were looking at.

## OPEN — a single wedged branch can idle a whole J6 job

In `hj6_branches_dev_20260917`, branch `fixed_k/2/37a8675_1__b2_untreated_s102` stopped writing
events at 19:17 at step 34 and never returned. The other nine workers drained the queue by 20:59,
so the job then held a GPU for hours to accomplish nothing, and `rebuild_derived` — which only
runs at the end — never wrote `branches.jsonl`. There is no per-branch timeout.

Two consequences:
1. **Aggregation is all-or-nothing at job end**: because `rebuild_derived` runs only after all
   workers finish, a single wedged worker prevents `branches.jsonl` from being produced even
   when 1,527 of 1,528 branches ran cleanly.
2. **A wedged worker is invisible without manual reconciliation**: detecting a stalled branch
   requires comparing the line count of `branch_runs.jsonl` against the directory count of
   completed branches, as the PBS job continues running without error.

**Startup rebuild hazard on `--resume`:**
`rebuild_derived` is **also called at startup** when `--resume` is set (`scripts/setup/branch_counterfactual.py:1099-1100`), not only at the end. Observed 2026-09-18: the train ×4 job started at 04:58:37 and at 05:00:30 its startup rebuild — which requires all four branch seeds per point — found no point complete and wrote an **empty** `branches.jsonl`, `oracle_labels.json` and manifest over the 2-seed aggregation the previous resume job had produced minutes earlier.

Nothing was lost, because `branch_runs.jsonl` is append-only and the 2-seed view rebuilds on CPU in about 70 s. But record the trap: **the derived files are not a safe place to keep a result while a job with a different `--branch-seeds` may start against the same tree**, and an empty `branches.jsonl` beside a healthy `branch_runs.jsonl` is expected mid-campaign rather than a sign of failure.

Suggested fixes (recorded, not implemented):
- A per-branch wall-clock timeout that records an error row and moves on.
- Periodic incremental aggregation so a killed or partial job still yields labels.

## OPEN 2026-09-18 — the `harmful` flag fired, and the cause is allocation, not format

Gate B's pre-registered `harmful > 0.15` flag fired on train: `harmful` (= `needless`) is
**0.1635** over 734 complete points, and the mean Δ per point is **−0.0206**. On dev the same
quantities are 0.1417 and +0.0068. Taken at face value this says a fixed five-step expert
review changes the outcome *for the worse* about one call in six.

The face value is misleading, and the follow-up analysis is the entry worth reading.

**A third of all review calls fire where the episode was already going to succeed.**
Stratifying the 734 train points by the outcome of the *untreated* branch — the counterfactual
in which the review never happened:

| stratum | n | mean Δ | harm | help |
|---|---:|---:|---:|---:|
| untreated already 1.0 | 232 (32 %) | −0.0884 | 0.220 | **0.000** |
| untreated in between | 493 | **+0.0098** | 0.140 | **0.164** |
| untreated already 0.0 | 9 | +0.0612 | 0.000 | 0.222 |

At the 232 ceiling points a review **cannot** help: goal-pass rate is already 1.0, so Δ is
bounded above by zero. `help = 0.000` there is a definitional consequence, not a measurement
of the reviewer. Those points alone contribute −0.0279 of the −0.0206 overall mean — i.e. the
entire negative mean and then some. **On the 493 points where there was headroom, the timer is
roughly break-even and helps slightly more often than it hurts (0.164 vs 0.140).**

**Second, independent effect: reviews compound.** Harm rises with the number of reviews still
to come — 12.9 % at none, 14.6 % at one, **25.9 % at two or more**, while help stays flat near
10 %. `r(Δ, n_later) = −0.147`, the largest of any predictor by a factor of three. It survives
stratification by position (step ≤5: −0.014 → −0.081; step 6–10: +0.015 → −0.058; step 11+:
−0.020 → −0.058) and by baseline outcome, so it is not merely a proxy for a struggling episode.

**What does *not* predict harm.** Timing is inert: `r(Δ, step) = +0.029`, and `step`, `replay_k`
and `i` are collinear by construction (`review_every_k = 5`, so step = 5(i+1)) — they return
byte-identical correlations and are one variable, not three. Content is nearly inert too:
correction length `r = −0.009`, mentions `complete_task` `r = +0.006`, contains concrete API
code `r = −0.044`. The last is the only content signal with a consistent direction —
prescriptive corrections carrying `apis.x.y(...)` harm 22.0 % of the time against 15.2 % for
prose-only advice — and it is weak.

**Reading — AMENDED 2026-09-18, see the amendment below before using this.** The flag is
real, and on the *average* it indicts the *schedule* rather than the format: a fixed timer
spends a third of its calls where nothing can be gained, and fires often enough that its
nudges accumulate. That is the condition adaptive allocation exists for, and it is direct
support for the campaign's thesis rather than evidence against it.

🔺 **AMENDMENT — the original "allocation, not format" verdict was too strong.** It was drawn
from correlations over all 734 points using crude text features (length, presence of API code,
mention of `complete_task`), all of which are near-inert. A separate qualitative read of the
40 most harmful and 40 most helpful corrections (`campaign/workers/W13_CORRECTIONS.md`) shows
the two mechanisms operate at **different scales**:

- **The mean is allocation.** The ceiling effect below explains the whole negative average.
- **The tail is format.** Among the 40 worst points, 55 % are corrections that are genuinely
  wrong — `wrong_for_task` 45 %, `contradicts_history` 10 % — against **5 %** in the 40 most
  helpful. `redundant` runs the other way: 42.5 % of harmful against 80 % of helpful, so
  redundant advice is usually benign. Mean correction length is 252.9 vs 251.2 characters
  between the groups, which independently reproduces the near-zero length correlation and says
  the difference is in content, not verbosity.

The cleanest evidence is a natural experiment inside the sample rather than a percentage. On
one task family the reviewer told the executor to *use* `csv.writer` (Δ −0.65); on a sibling
episode it said `csv.writer` **is unavailable** and to escape fields manually (Δ +0.55). Same
reviewer, same API, contradictory claims about whether it exists, and the correct one helped
while the hallucinated one hurt. That is reviewer error, and no amount of better timing fixes
it.

The mechanism is visible in the design: the reviewer sees only the last 8 transcript lines
(`loop.py:606-610`), never the action about to be taken, and its correction is injected
unconditionally — 495/495 `forced: true`. A reviewer with a keyhole view that cannot be
overridden will sometimes confidently forbid a valid API or order a premature `COMPLETE`, and
three of the worst cases are exactly that.

**So both need fixing, and they are separable.** Allocation determines *how often* a review is
wasted; format determines *how badly* the wasted ones go wrong. J7 addresses the first. The
second needs either a wider review window or a non-forced correction channel, and neither is
in the current plan.

⚠ The stratifying variable is the untreated branch's outcome, which is **observed only
counterfactually**. A live router cannot see it. Predicting "this episode is already on track"
from state alone is exactly the `FeatureVerifier`'s job (J7), and this analysis sets the target
it has to hit: identify the 32 % ceiling points and stay silent.

Open questions:
- ~~whether the reviewer repeats itself across successive ticks~~ — ANSWERED: it does. 9 of the 40 harmful records share a task with another, including verbatim re-injection of the same abort instruction at steps 15 and 20 of `7d7fbf6_3`. The helpful group also has 9 repeat tasks but shows refinement rather than re-injection, and zero aborts.
- ~~whether harmful corrections are *wrong* or merely *unnecessary*~~ — ANSWERED in the amendment above: 55 % of the worst are wrong, against 5 % of the best.
- STILL OPEN: whether a wider review window actually reduces the `wrong_for_task` rate, which is the only way to test the format hypothesis causally rather than observationally.

Numbers from `branch_runs.jsonl` of `hj6_branches_train_20260917` (4188 rows at the time),
aggregated by the repo's own `rebuild_derived` at band 0.166 frozen on train.

## OPEN 2026-09-18 — J6 branch crash rate escalates across successive jobs: 0.4 % → 10 % → 40 %

Found while checking why only 397 of 777 train points were complete on four branch
seeds when all 6,216 branch rows existed. The rows exist; 40 % of them carry a null
`branch_gpr` and `branch_error_type: "crash"`.

The first reading — "seeds 103/104 are bad" — is wrong, and the way it is wrong is the
point. A sampling seed cannot cause a crash rate. Splitting the same seeds by **which job
ran them**, using `result.json` mtime, separates the two explanations:

| era | job | seeds | n | crash rate |
|---|---|---|---:|---:|
| 1 | base `25410220` | 101 / 102 | 2,087 | **0.38 % / 0.48 %** |
| 2 | resume `25412609` | **101 / 102** | 1,021 | **9.02 % / 10.57 %** |
| 3 | ×4 `25413657` | 103 / 104 | 3,108 | **40.60 % / 39.70 %** |

**The same seeds, on the same points, crash twenty times more often in era 2 than era 1.**
The seed is irrelevant. Something degrades across successive J6 jobs, monotonically.

**Not established: the cause.** The one configuration change at era 2 is that
`BRANCH_SEEDS` went from two values to four, so the work list holds 8 branches per point
instead of 2 and the 10-worker pool can run many branches of the *same task* at once. If
AppWorld episodes for one task share state, that is an interference mechanism — but it is a
hypothesis, not a finding. Two things were checked and do **not** explain it:

- **Not the W-5 executor rewrite.** Era 1 ran pre-W-5 code and eras 2–3 ran post-W-5, which
  fits the timeline suspiciously well. But the only lines *removed* in that change are in
  the ASK-ignored path and one variable extraction, and J6 runs with
  `allow_executor_ask=False` and `verifier=None`, so neither executes.
- **Not file-descriptor exhaustion.** vLLM warns about `ulimit -n 16384` at startup, but the
  job stdout contains zero occurrences of `Too many open files`.

A crashed branch is not an early failure: its `result.json` shows a full rollout — 15 to 30
executor calls, 400–600 k tokens, `steps` at the limit — and then `tgc`, `sgc` and
`goal_pass_rate` all null. The rollout ran; the scoring returned nothing.

### It is data LOSS, not data CORRUPTION — and that was verified, not assumed

Two checks, because a 40 % failure rate that silently biased the survivors would invalidate
every four-seed number in the campaign.

**1. Selection is unbiased with respect to the effect.** Comparing the *two-seed* Δ (available
for both groups) between points that survived on four seeds and points that did not:
train −0.0189 vs −0.0227 (Welch t = +0.27), dev +0.0051 vs +0.0219 (t = −0.55). Neither is
close to significant. There is a compositional difference in ceiling-point share (train
+16.2 pp, dev −8.2 pp) but the two splits point in **opposite directions**, which is what
noise looks like.

**2. Surviving era-3 branches are exchangeable with era-1 branches.** Under common random
numbers with identical configuration, seeds 101–104 must be interchangeable. Paired over
points complete in all eight cells:

| quantity | train t | dev t |
|---|---:|---:|
| treated `branch_gpr` | −0.88 | −1.07 |
| untreated `branch_gpr` | +0.22 | −0.21 |
| Δ | −0.82 | −0.68 |

Every |t| < 1.1. Ceiling shares match (train 0.390 vs 0.408; dev 0.265 vs 0.274) and floor
shares match (0.015 vs 0.015). The branches that survived are sound.

**Consequence.** The four-replicate reliability result (0.4504) and the four-seed labels
stand. What is lost is coverage, and it is uneven: dev is 332 of 382 points complete on four
seeds (87 %), train only 397 of 777 (51 %). So for train there is a real trade-off with no
free answer — 734 points at two-replicate reliability 0.29, or 397 points at four-replicate
reliability 0.45. J5b's ASK targets come from `needed`, and on the 2-seed set that is 83
points; the 4-seed set will yield materially fewer.

**Before any further J6 submission**, establish the cause. Running the replicates as separate
jobs of two seeds each, rather than one job of four, would test the concurrency hypothesis
directly and is cheap. Re-running the lost train branches is otherwise ~20 GPU-h to recover
coverage the campaign may not need.

⚠ Same family as the rest of this document, with one improvement worth naming: the machinery
recorded the failures as `null` and `label_status: incomplete` and dropped them, rather than
coercing them to 0.0. Nothing was fabricated. But the *selection* those nulls induce is
invisible in every summary — the manifest reports `n_complete` and looks healthy — and it took
a deliberate comparison of complete-versus-dropped to show the survivors were usable.

## RESOLVED 2026-09-18 — the J6 crash cause: a planner-cost blowout, plus an argv limit

Supersedes the "crash rate escalates across successive jobs" entry above, which had the
pattern right and the cause wrong. The concurrency hypothesis recorded there is **dead** —
it was never tested and is not needed. Both real causes are established below.

Every crashed branch carries an `error` event naming the exception. Sweeping all 9,272
branch `events.jsonl` files gives 1,499 error events and exactly two exception types:

| exception | detail | train | dev | share |
|---|---|---:|---:|---:|
| `CodexExecError` | `codex exec exited 1` | 1,332 | 128 | **97.4 %** |
| `OSError` | `[Errno 7] Argument list too long: 'codex'` | 25 | 13 | **2.5 %** |

Neither is AppWorld, the executor, vLLM, concurrency, or the branch seeds. **Both are the
hosted planner.**

### Cause 1 — the Codex quota was exhausted, because J6 spent a budget of zero

`codex exec exited 1` is a failed hosted-planner call. The crashes are not spread evenly;
they arrive in bursts, by the hour the branch finished:

```
09-17 18:00 – 09-18 01:00   ~0 CodexExecError   (only the OSErrors below)
09-18 02:00                 221                 (train 93, dev 128)
09-18 04:00 – 09-18 09:00   ~2                  (recovered)
09-18 10:00                 329
09-18 11:00                 652
09-18 12:00                 256
```

Exhaust, reset, exhaust again — the signature of a rolling-window rate limit, not a code
fault. Independently corroborated: an unrelated interactive `codex` call from the
orchestrator at ~10:40 on 09-18 returned *"You've hit your usage limit … try again at
Sep 19th, 2026 9:13 PM"*, inside the sustained-failure window.

**Why the quota ran out is the actual finding.** J6 consumed:

| | branches | planner calls | planner tokens |
|---|---:|---:|---:|
| train | 6,216 | 23,769 | 276,122,937 |
| dev | 3,056 | 13,599 | 202,526,868 |
| **total** | **9,272** | **37,368** | **478,649,805** |

**The plan's cost table budgets J6 at 0 luna calls.** For scale it budgets J8 at ~3,200 and
J10 at ~11,500 — so J6 alone spent roughly three times the entire remaining campaign's
planner allowance. (The reported $23.99 is notional; luna here is quota, not money. The
quota is the binding constraint, and it was spent.)

The zero was once correct. The original branch definition ablated intervention *i* **and
every later review**, so a branch made no planner calls. The definition was amended on
2026-09-17 — correctly, because the original confounded the estimand by letting a useless
correction followed by an essential one score as `needed` — to *"in both, the reviewer stays
live on its normal 5-step schedule afterwards, calling the planner on the branch's own
state."* That amendment turned every branch into ~4 planner calls. **The cost table was never
updated to match**, so nothing downstream ever re-checked the planner budget, and the
campaign sized J6 purely in GPU-hours.

⚠ Naming the decision honestly: the ×4 replicate jobs were the orchestrator's
recommendation, submitted to raise label reliability from 0.29 to 0.45. They doubled the
branch count and therefore added roughly 18,700 planner calls. They were sized in GPU-hours
against a table that said the planner cost was zero, and the planner cost was never
re-derived from the amended definition. The reliability gain was real and measured, but it
was bought with a resource nobody was counting.

### Cause 2 — the prompt is passed in argv, and Linux caps a single argument at 128 KiB

`src/sidekick/agents/planner.py:131` (and the non-resume branch below it) builds the codex
invocation as:

```python
cmd.extend([thread_id, prompt])
```

The prompt is one `argv` entry. Linux's `MAX_ARG_STRLEN` is 32 pages = **128 KiB for a single
argument**, regardless of the much larger total `ARG_MAX`. A `fixed_k` prompt is the rendered
transcript plus the API digest; on train these run to ~19k tokens and cross the limit on long
episodes. `execve` then fails with `E2BIG`, surfacing as
`OSError: [Errno 7] Argument list too long: 'codex'`.

This is independent of the quota and was present from the start — it accounts for all the
era-1 crashes (seeds 101/102 show 5 and 11 OSErrors while showing almost no
`CodexExecError`).

🔺 **It is small but non-random, and it biases in a direction that matters.** It fires
precisely on the longest transcripts, so the episodes it silently removes are the long,
struggling ones. Any statistic conditioned on episode length — and the measured
`n_later_reviews` effect is exactly that — inherits a mild selection against long episodes.
38 of 9,272 branches is too few to move the headline numbers, but it should be fixed before
the effect is quoted.

**The fix is direct.** `codex exec --help` states: *"[PROMPT] … instructions are read from
stdin. If stdin is piped and a prompt is also provided, stdin is appended as a `<stdin>`
block."* So the prompt should be piped to the child's stdin rather than placed in argv. Note
the second sentence — passing **both** appends rather than replaces, so the prompt argument
must be dropped when piping, not duplicated.

### What this changes

- **J8 and J10 are at risk, and not for GPU reasons.** Their planner budgets (~3,200 and
  ~11,500 calls) were computed against the same table that said J6 was free. They are
  probably right in themselves, but the quota they draw on has just been drained and resets
  on a rolling window. Any future job that makes live planner calls needs its call count
  derived from the *current* system definition, not the table.
- **Re-running the ~1,460 lost branches is a planner-quota decision, not a GPU decision.** At
  ~4 calls per branch it is ~5,800 further calls — comparable to the entire J8 budget.
- **The concurrency hypothesis in the entry above should be disregarded.** Running replicates
  as separate two-seed jobs would not have helped; it would merely have spread the same
  planner calls over more wall-clock and hit the same rolling limit.
- Verified earlier and still true: the crashes are **data loss, not data corruption**.
  Surviving branches are exchangeable across eras (all |t| < 1.1) and selection is unbiased
  with respect to Δ (|t| < 0.6), so the four-replicate reliability figure and the labels
  stand.

### The general lesson, which is the one worth keeping

An amendment was made to fix a real scientific defect in the estimand. It was reviewed,
approved and recorded. Nobody re-derived the cost of the thing it amended, because the cost
lived in a different table in a different section, and that table still said zero. The
campaign then spent three times its remaining planner budget without a single gate firing,
and the first symptom was a crash rate that looked like a concurrency bug.

**When a definition changes, re-derive every quantity computed from it, not just the ones the
change was about.**

---

## 🔻 RESOLVED 2026-09-18 — a calibrator that decalibrated, and the invariant that caught it

`fit_temperature` in `scripts/setup/fit_feature_verifier.py` claimed to minimise dev NLL by 1-D
Newton steps. It never did. The NLL gradient is `dNLL/dT = (1/T²)·Σ(yᵢ−pᵢ)zᵢ`, so the stationary
condition is `Σ(yᵢ−pᵢ)zᵢ = 0`; the implementation accumulated `(1/T − (yᵢ−pᵢ))·z²/T²`, carrying a
spurious `1/T` term and weighting by `z²` instead of `z`. Its fixed point was
`Σ(y−p)z²/Σz² = 1/T`, which is not NLL stationarity.

On synthetic data where the answer is known by construction it failed in every regime: with
labels drawn from the model (true T = 1.0) it returned 0.0500, the clamp floor; with logits 3×
too large it returned 0.0500 again; with uninformative scores and random labels it returned
1.0000 and never moved. In all three it was **worse than doing nothing**.

On the real dev split it returned T = 0.129, which *sharpens* logits ~7.75×, and the J7 artifact
then reported dev Brier 0.480 and ECE 0.490. The honest pre-scaling values were 0.268 and 0.145 —
so the calibration step made Brier 1.8× worse and ECE 3.4× worse while producing output that
looked entirely plausible.

Fixed by golden-section search over log T. After the fix T = 11.04 (flattening toward the base
rate, the correct direction for a near-uninformative model), dev ECE 0.490 → 0.0136, Brier
0.480 → 0.2498, dev AUROC byte-identical at 0.5916711736073553.

### 🔺 The standing practice this produces: every fitted quantity gets an invariant

This defect was **not** caught by tests, by review, or by the number looking wrong. It was caught
by deriving the gradient by hand and checking the optimiser against a brute-force grid. That does
not scale, and it is now the fourth defect in this campaign to return believable numbers from
broken internals (see the probe's `hash_match` metric, omitted `tests/integration`, and J6 zero planner budget entries above).

What does scale is cheap, and it is now the expected practice for anything fitted:

1. **An improvement invariant.** A step that claims to improve a quantity must be asserted to
   improve it, against the no-op baseline. Calibration must not increase NLL; a fit must not
   score worse than its own initialisation. `fit_temperature` now returns 1.0 whenever the
   optimum fails to strictly beat T = 1.0.
2. **An invariance invariant.** A transform must be asserted not to change what it cannot change.
   Temperature scaling is monotone, so AUROC must come back bit-identical; a moved AUROC means
   something else broke. This is what confirmed the fix touched only what it should.
3. **Before and after, in the artifact.** `dev_nll_before` and `dev_nll_after` are now written to
   `metrics.json`, so the next instance of this failure is visible by reading the output instead
   of requiring someone to re-derive the mathematics.
4. **A known-answer test.** Any optimiser gets at least one case where the correct answer is known
   by construction, not merely plausible.

## 🔻 OPEN 2026-09-18 — the planner quota is now a scheduled resource, not a free one

J6 spent 37,368 hosted planner calls against a cost table that budgeted it at zero, and exhausted
the rolling window (see the root-cause entry above). The remaining campaign needs roughly:

| item | planner calls |
|---|---:|
| recover the 1,498 crashed branches | ≈ 6,000 |
| J8 dev frontier | ≈ 3,200 |
| J10 final | ≈ 11,500 |
| **total** | **≈ 21,000** |

That is of the same order as the spend that just drained the window, so these can no longer be
launched on a first-come basis.

**Priority, to be confirmed by the user before the quota resets (2026-09-19 ~21:13): recovery
first.** It is the only one of the three that makes data we already paid for usable, it is the
cheapest per unit of information, and until `branch_counterfactual.py`'s retry path is in place a
resume recovers nothing at all. J8 and J10 are both downstream of decisions that the recovered
labels may change.

Every J6-family submission from here carries `--max-planner-calls-total`, so a budget overrun
stops cleanly and resumably rather than running to exhaustion.

