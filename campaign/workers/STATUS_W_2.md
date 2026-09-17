# W-2 resume status

## Deliverables

- [x] `configs/hj4b_fixed_k_dev.yaml`: copied from the frozen HJ-4 correction
  configuration, with the held-out dev packet source and comparison header.
- [x] `scripts/pbs/hj4b_fixed_k_dev.pbs`: GPU job with smoke, dev, and train
  seed-3 stages, gated summaries, manifests, and campaign-result archives.
- [x] `scripts/setup/verify_configs.py`: closed seven-name frozen-pilot
  allowlist; misplaced prompt-budget keys remain errors.
- [x] `tests/unit/test_verify_configs_prompt_budget.py`: three allowlist and
  non-allowlist regression tests added.
- [x] `/home/n12194778/.claude/jobs/91578989/tmp/w2_checks.sh`: PBS-hosted
  checker for config validation and the full test suite; the repository-root
  scratch copy was removed.

## Resume state

- [OBSERVED scripts/pbs/hj4b_fixed_k_dev.pbs:262] No campaign PBS job was
  submitted by this unit; the script only defines the requested future stages.
- [OBSERVED /tmp/hpc-w2-spool/20260917-104215-9.out:54] The final authorized
  PBS verification completed with `verify_configs.py exit status: 0`.
- [OBSERVED /tmp/hpc-w2-spool/20260917-104215-9.out:59] Its verbatim test
  count was `258 passed, 1 skipped in 13.54s`.
- [OBSERVED /tmp/hpc-w2-spool/20260917-102208-9.out:145] An earlier check
  ended `7 errors in 0.96s` while the shared worktree was missing
  `ConfigurableSystem` during collection.
- [OBSERVED /tmp/hpc-w2-spool/20260917-102429-9.out:67] The next check ended
  `1 error in 1.02s` because the pytest console entry point could not import
  the repository's namespace package `scripts`.
- [OBSERVED src/sidekick/runner.py:344-345] The checked-out runner has
  `--tasks`, not `--limit`, and parses multiple seeds from one argument. The
  PBS script uses the executable equivalents `--tasks 3` and `--seeds 1,2`.
- [OBSERVED scripts/pbs/hj4b_fixed_k_dev.pbs:63,174,218,234] The train stage
  uses the existing frozen config and campaign id and does not purge that tree,
  so runner resume can preserve seeds 1 and 2.
- [OBSERVED scripts/pbs/hj4b_fixed_k_dev.pbs:246-283] Stage 3 asserts the
  `_s123` archive basename and checks seed 1/2 counts before and after the run,
  while requiring 90 seed-3 episodes.
- [OBSERVED /home/n12194778/.claude/jobs/91578989/tmp/w2_checks.sh:1] The
  harness is relocated outside the repository; the repository-root copy is
  absent.
- [OBSERVED /scratch/n12194778/sidekick/results] The two new 2026-09-17
  campaign directories were absent at the final verification time.
- [OBSERVED /scratch/n12194778/sidekick/results/hj2b_planner_train_20260916/planner_alone/3]
  The cached train seed-3 planner subtree contained 90 task directories.
