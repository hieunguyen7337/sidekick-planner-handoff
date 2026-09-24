# Unit BFCL-E2: build the Wave E dev design (configs, wrapper, tests, dev prereg draft). Zero hosted calls.

WT = /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 (branch worktree-plan-2026-09-15, HEAD cfbe6d1).
Written by Claude, 2026-09-24. Common rules: `campaign/workers/briefs/20260924_common_rules.md` (read it first).

## Context (already on the branch)
- **BFCL `multi_turn_base` environment.** Built and merged (d0dae40, cfbe6d1). Record: `docs/bfcl_env_20260924.md`.
  - Adapter: `src/sidekick/environments/bfcl_env.py`.
  - Split: `data/bfcl_split_20260924.json`, dev 50 / test 150.
  - Spike wrapper: `scripts/pbs/bfcl_arm.pbs`. It is dev only, and today runs only executor_alone with the
    zero-shot receiver.
  - Spike (b) arm config: `configs/bfcl_executor_alone_zs.yaml`. Its campaign
    `bfcl_executor_alone_zs_dev_20260924` is complete (100 episodes).
- **Scoping.** `docs/second_env_scoping_20260923.md` §0, §2 and §3 (lines 13-40, 77-104, 155-179).
- **Plan rows.** `docs/plan_top_venue_20260924.md:84-85` and `:146-162`.
- **Decided by Claude.** Do not reopen these:
  - Depth grid m ∈ {2, 4, 6}.
  - Two receivers:
    - zero-shot granite-4.2-8b (`zs`, primary);
    - the AppWorld-tailored adapter `sft_b_plus`, run out of domain (`bplus`), since BFCL has no train split.
  - The channel arms run on the zs receiver only, at k = 5. That is the AppWorld k = 10 rescaled for BFCL's
    shorter episodes (scoping §3).
  - The planner acting alone runs at cap 81 and medium effort, the same planner block as J10 arm 3.
  - Dev only: 50 dev entries × seeds 1, 2 = 100 episodes per arm.

## A. Configs: `configs/bfcl_<stem>.yaml`, campaign_id `bfcl_<stem>_dev_20260924`
Template from the named J10 config, changing only `env: bfcl`, campaign_id, `fixed_k` (10 → 5 where named), the
executor block, and `handoff.source_campaign`. The executor block is:
- zs: copied verbatim from `configs/bfcl_executor_alone_zs.yaml`;
- bplus: that block with `lora_name: sft_b_plus`, the alias and adapter path used by `configs/j10_executor_alone_bplus.yaml`.

Each config's header comment says what it copies and what it changes, in the style of the existing header.

| stem | template | receiver | hosted calls/episode (scoping §3) |
|---|---|---|---|
| planner_alone_cap81 | j10_planner_alone_cap81 | — | ~12 |
| plan_zs (one cached plan, executor acts) | j10_sft_plan | zs | 1 |
| takeover_k5 | j10_takeover_k10 | zs | ~3 |
| advise_k5_fullctx (correction prompt) | j10_advise_k10_fullctx | zs | ~3 |
| advise_k5_neutral | j10_advise_k10_neutral | zs | ~3 |
| prefix_zs_m2, prefix_zs_m4, prefix_zs_m6 | j10_prefix_zs_m9 | zs | 0 (replay of planner_alone_cap81's dev campaign) |
| prefix_bplus_m2, prefix_bplus_m4, prefix_bplus_m6 | j10_prefix_m9 | bplus | 0 |
| executor_alone_bplus | j10_executor_alone_bplus | bplus | 0 |

- If a J10 template's packet or plan source points at J10 arm 3, repoint it at `bfcl_planner_alone_cap81_dev_20260924`.
  Use the same key the template uses, so the channel arms replay BFCL arm 1's first plan, as the J10 arms do.
- Never name anything `j10_*`, `j11_*` or `j12_*`, and never edit those configs.

## B. Wrapper
Extend `scripts/pbs/bfcl_arm.pbs`, or add `scripts/pbs/bfcl_live.pbs` if extending would make it unreadable, so that
every arm in A can run on dev. Port each of these from `scripts/pbs/j10_arm.pbs`, citing the source lines in comments:
- **Hosted stems.** `planner.type: codex` is accepted only with `EXPECTED_CODEX_VERSION=0.153.4`, using the same
  check as J10.
- **The bplus receiver.** vLLM `--lora-modules sft_b_plus=<the path J10 uses>`, with the served-model probe.
- **Replay stems.** The source campaign must be complete, non-crashed and at 100, using the
  `require_complete_source` logic.
- **Refills.** A crash-only refill (`--purge-crashed-only`) on resubmission.
- **The tally.** The jq tally with exit codes 0 / 2 / 3 / 1, as the existing wrapper documents.

Keep every refusal the wrapper already has, and tighten it:
- SPLIT other than dev is refused (the BFCL test prereg does not exist yet);
- a stem not in A's table is refused;
- a campaign id without `_dev_` is refused.

A `MAX_PLANNER_CALLS` guard, if the J10 or hj12 wrappers have one, is ported too.

## C. Tests (`tests/unit/`), run in PBS via `hpc`
- **Configs.** Every A config parses. It has `env: bfcl`, a unique `_dev_` campaign id, the receiver and `fixed_k`
  stated above, and the grid is exactly {2, 4, 6}. Every replay arm's source is the planner_alone campaign.
- **Wrapper self-tests.** Every refusal, via the `BFCL_SELFTEST` seam, in the style of `tests/unit/test_bfcl_arm_pbs.py`.
- **A CPU end-to-end smoke with zero hosted calls.** Run 2 dev entries × 1 seed for one arm of each kind (channel,
  replay and plan) through the runner, with `--env bfcl` and the mock planner and mock executor, into a tmp output
  dir. A replay arm needs a mock-produced planner_alone source, also in tmp.
  - This proves the channel and replay machinery runs on BFCL's multi-turn episodes.
  - If the mock planner cannot drive a channel arm, stop and report what is missing. Do not change `loop.py`,
    `runner.py` or `bfcl_env.py` without reporting first.
- **The full suite.** Run it once at the end. Report the pass count; it must not drop below 1738 passed plus
  cfbe6d1's 39.

## D. Draft dev prereg: `docs/prereg_bfcl_dev_20260924.md`
Its Status line is `**Status**: DRAFT`. Contents:
- the split (seed, 50/150, the file, how it was drawn);
- the three spike gates and results, from `docs/bfcl_env_20260924.md`;
- the depth grid and why it was chosen;
- the dev arms in A, with their receivers, k and a hosted-call budget. Take the budget from scoping §3, sized for
  the arms in A, at 100 episodes each plus a dry run and 10 % retries;
- the dev read, which is exploratory and gives the effect sizes and power for the test prereg. Name the contrasts it
  prepares, mirrored from J10:
  - P6 (takeover − correction advice);
  - CF1 (neutral − correction advice);
  - P3 with its handoff-only B1 companion (prefix m6 NI to planner_alone, with h* read from events via
    `scripts/analysis/handoff_control.py`);
  - the m2 → m6 depth span;
- the test-contact rule: no `test` episode until a BFCL test prereg is frozen.

Keep it short, about 150 lines.

## Constraints
- **Zero hosted calls.** Never submit a hosted arm, never run a codex planner, and use no codex or luna workers:
  J10 hosted arms are running in this window. GPU jobs are not needed. CPU tests go through
  `hpc bash -c '...'`, with `OMP_NUM_THREADS=1` (and `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`),
  `PYTHONPATH=src:.`, `/scratch/n12194778/sidekick/env/bin/python` and `timeout`.
- **aquarius01 is a login node.** No python, pip, pytest, tar or rsync there.
- **Do not touch:**
  - `.claude/worktrees/j10-run-a8b63f0`, `j1112-run-6f40fec` or `bfcl-env`;
  - anything under `/scratch/n12194778/sidekick/results/` except your own tmp output dirs;
  - `docs/prereg_j1*`;
  - the ledger;
  - the paper.
- **Git.** No git writes and no commit. Claude reviews and commits. Ignore `.claude/worktrees/` and `.git/`.
- **Read narrowly.** Use grep or offset/limit for large files.

## Report (≤ 350 words, every claim tagged [OBSERVED path:line] or [INFERRED])
- the files created or changed;
- the test counts (the new files, and the full suite with its PBS job id);
- the smoke's outcome per arm kind;
- the hosted-call budget in D;
- anything you could not do, and why.
