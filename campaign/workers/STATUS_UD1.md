# STATUS_UD1 — state probe (unit U-D1)

## Done
- 2026-09-16: `replay_prefix` added to `src/sidekick/replay.py` (replay() untouched).
- `scripts/setup/state_probe.py` created (probe CLI + metric functions).
- `tests/unit/test_replay_prefix.py` created — **13 passed** in PBS job 25399953
  (`python -m pytest tests/unit/test_replay_prefix.py -q` → "13 passed in 0.44s",
  env: /scratch/n12194778/sidekick/env). Pasted verbatim from /tmp/ud1_test5.log run.
- Full `tests/unit` suite: 15 modules fail at COLLECTION with
  `ModuleNotFoundError: No module named 'sidekick'` — pre-existing (no conftest.py,
  no editable install in this venv); unrelated to UD1 files. Needs a conftest.py or
  `pip install -e .` — outside my file ownership, flagged to orchestrator.

## Key findings
- `replay()` does NOT handle two-run_start logs: it takes the FIRST run_start
  (`src/sidekick/replay.py:74`) and steps every action in the file, so a retried
  log double-steps. Left as-is (behaviour frozen by brief); `replay_prefix` slices
  events after the LAST run_start, in file order (never by `ts`).
- Campaign layout [OBSERVED /scratch/n12194778/sidekick/results/hj1b_planner_20260915]:
  `campaign_root/<system>/<seed>/<task_id>/{events.jsonl,manifest.json,result.json}`;
  success flag in `result.json["success"]`.
- `state_equivalent` compares observation text whitespace-normalised (strip):
  MockEnv/AppWorld print output carries a trailing newline the recorded text lacks
  [OBSERVED debug job /tmp/ud1_dbg3.log].

## Next (for whoever runs the probe)
- Start vLLM server, then in a GPU PBS job:
  `python scripts/setup/state_probe.py --campaign-root
  /scratch/n12194778/sidekick/results/hj1b_planner_20260915 --system planner_alone
  --model granite-4.2-8b --base-url http://localhost:8000 --out <json>`
  (optionally --lora-name, --max-runs 10, --max-steps-per-run 12 to bound first pass).

## Resume
- Files owned: `src/sidekick/replay.py`, `scripts/setup/state_probe.py`,
  `tests/unit/test_replay_prefix.py`, `campaign/workers/STATUS_UD1.md`.
- All three metrics recorded per step including failures (error_type recorded,
  never dropped). hash_match reported, not gated (hash includes input code).
