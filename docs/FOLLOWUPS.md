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

- **`HEAVY_JOBS.md` HJ-1 is internally inconsistent**: 57 x 6 arms x 2 seeds = 684 requires
  `oracle_escalation` at all 57 tasks, but the arm description says a 20-task probe, which would give
  610. Pick one before HJ-1 is reported.
