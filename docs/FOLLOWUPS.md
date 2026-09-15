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
