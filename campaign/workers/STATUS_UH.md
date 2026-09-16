# STATUS — U-H truncation policy
Repo: /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15

## Done — COMPLETE
1. `src/sidekick/protocols/prompts.py`: added `fit_messages_to_budget(messages, *, max_tokens, length_fn)`.
   Keeps messages[0], [1] and last; drops whole middle messages oldest-first; returns
   `(selected, n_dropped, representable)`, unmodified list + representable=False when the
   anchor set alone is over budget.
2. `src/sidekick/training/sft_data.py`: `tokenize_and_mask` now delegates to
   `fit_messages_to_budget` (injected length_fn = `len(_tokenize_messages(ms))`). Returned
   keys unchanged. Existing `test_sft_data.py` passes unchanged.
3. `src/sidekick/agents/executor.py`: `VLLMExecutor(max_prompt_tokens=None)`; when set,
   applies the shared policy before the HTTP request with a lazily loaded
   `AutoTokenizer.from_pretrained(self.model)` (logged fallback: chars//3); truncation and
   retries recorded in `usage.raw["n_messages_dropped"]` / `["n_400_retries"]`; 400 backstop
   drops the oldest remaining middle message and retries at most twice, then re-raises.
4. `configs/hj1r_prompt_only.yaml` + `configs/hj3_sft_plan.yaml`: `max_prompt_tokens: 31744`.
5. `tests/unit/test_prompt_budget.py`: 7 tests (head/tail retention, no partial messages,
   unrepresentable anchors, anti-drift train==serve, no tokenizer/no truncation when budget
   None, 400 retry counting, executor budget fit). All stubbed, no live model.
6. `campaign/workers/STATUS_UH.md` (this file).

## Objection recorded (per SEAM_CONTRACT rule)
Brief says `max_prompt_tokens: 31744` = 32768 − 1024, but both configs set
`executor.max_tokens: 2048`, so the true safe budget is 30720. Implemented the brief's
31744 verbatim; a future run should either lower it or reconcile with max_tokens.

## Resume command
timeout 2400 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && PYTHONPATH=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/src:/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /scratch/n12194778/sidekick/env/bin/python -m pytest tests/unit -q 2>&1 | tail -20'

## Last pytest result
Full suite (via hpc/PBS): `168 passed in 9.18s` — zero failures.
test_prompt_budget.py + test_sft_data.py: `17 passed in 6.21s`.

