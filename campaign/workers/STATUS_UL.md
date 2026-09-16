# STATUS_UL — AppWorld state-probe environment guard

## Done

- 2026-09-17: [OBSERVED src/sidekick/replay.py:64] Made `replay_prefix`
  require an explicit `BaseEnv`; [OBSERVED scripts/setup/state_probe.py:536]
  and [OBSERVED tests/unit/test_replay_prefix.py:73] callers pass an
  environment.
- 2026-09-17: [OBSERVED scripts/setup/state_probe.py:532] State probes
  construct one `AppWorldEnv` per point, replay into that world, and run a
  one-time preflight [OBSERVED scripts/setup/state_probe.py:286] for the
  environment type, task instruction, API docs, and the `inbox.txt` toy-world
  fingerprint.
- 2026-09-17: [OBSERVED tests/unit/test_state_probe_resume.py:53] Added offline
  regression tests for the required environment and preflight failures;
  lifecycle tests use a stub and do not start AppWorld.

## Verification

- 2026-09-17: [INFERRED from jq query on
  `/scratch/n12194778/sidekick/results/probe_granite8b.json`] All 9 reported
  agreements had empty gold API sets; corrected agreement count is 0.
- [INFERRED] The mandated PBS suite was attempted with the brief's command but
  was blocked before test execution by `hpc: qsub failed: Unknown Host.` and
  `qsub: cannot connect to server aqua (errno=15008)`.

## Resume

- Files owned: `src/sidekick/replay.py`, `scripts/setup/state_probe.py`,
  `tests/unit/test_replay_prefix.py`, `tests/unit/test_state_probe_resume.py`,
  `campaign/workers/STATUS_UL.md`.
- [INFERRED] Do not rerun the state probe. The orchestrator must rerun the unit
  suite when PBS connectivity is available.
