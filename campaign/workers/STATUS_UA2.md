# STATUS UA2 — SFT(b) dataset, LoRA trainer, PBS jobs

**unit:** U-A2
**state:** done (code written; unit tests run in PBS job 25399524.aqua)

## done
- `src/sidekick/training/sft_data.py` — `build_sft_dataset`, CLI, `tokenize_and_mask`.
- Imports `render_executor_messages` / `format_executor_action` from `prompts.py` (not edited).
- `scripts/train/sft_lora.py` — TRL 1.13.0 `SFTTrainer` + PEFT 0.20.0 LoRA, manual assistant masking.
- `scripts/pbs/train_sft.pbs` — env block copied from `hj1c_fixed_k.pbs:19-40`; dry-run then full train.
- `scripts/pbs/hj3_eval.pbs` — static `--lora-modules`; smoke-then-full live for `eval_sft_b.yaml` when that file exists; other arms commented.
- `tests/unit/test_sft_data.py` — 8 tests.

## Test results (REAL, hpc job on a compute node; NOT on the login node)
Job 25399524.aqua, log `/home/n12194778/.hpc-spool/20260916-192934-3849954.out`:

```
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0 -- /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/.venv/bin/python
cachedir: .pytest_cache
rootdir: /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
configfile: pyproject.toml
collecting ... collected 8 items

tests/unit/test_sft_data.py::test_jsonl_line_is_renderer_messages_plus_meta PASSED [ 12%]
tests/unit/test_sft_data.py::test_only_events_after_last_run_start PASSED [ 25%]
tests/unit/test_sft_data.py::test_file_order_not_timestamp PASSED        [ 37%]
tests/unit/test_sft_data.py::test_solved_only_skips_failures PASSED      [ 50%]
tests/unit/test_sft_data.py::test_no_solved_only_keeps_failures PASSED   [ 62%]
tests/unit/test_sft_data.py::test_not_in_split_is_dropped PASSED         [ 75%]
tests/unit/test_sft_data.py::test_leakage_raises_unconditionally PASSED  [ 87%]
tests/unit/test_sft_data.py::test_masking_unmasked_positions_are_exactly_assistant_spans PASSED [100%]

============================== 8 passed in 0.92s ===============================
```

## Objection (implemented the contract anyway)
- `api_docs_prompt` is not stored in run events [OBSERVED src/sidekick/systems/loop.py:423-452]. Recovered from event payload if present; otherwise rebuilt with `_summarise_api_docs` so training matches inference. Counted in `n_missing_api_docs`.

## next (orchestrator)
- After HJ-2B finishes: build JSONL, then `qsub scripts/pbs/train_sft.pbs`. Do not start vLLM/training from a worker.
- Eval configs (`executor.lora_name`) must equal `ALIAS_*` (default `sft_b`).

## how to resume
- Dataset: `PYTHONPATH=src python -m sidekick.training.sft_data --campaign-root ... --out ... --split train`
- Train: `qsub scripts/pbs/train_sft.pbs` (dry-run first, aborts on failure)
- Tests: `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src python -m pytest tests/unit/test_sft_data.py -v'`
