# Unit CTRL: two exploratory dev control arms (wrong-task plan, self-plan)

Read `campaign/workers/briefs/20260924_common_rules.md` first. It binds this unit, with **one change**: you write
directly into the plan worktree `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15` (call it
WT), because private clones are not permitted. **Do not commit, do not `git add`, do not stash, do not qsub.**
Claude reviews the diff and commits. Another unit is editing `scripts/pbs/j10_arm.pbs`, `scripts/pbs/j12_arm.pbs`,
`configs/j12_*`, `scripts/analysis/j12_*` and `tests/unit/test_j12_*`; do not touch those, nor anything `j10_*` /
`j11_*`, nor any `docs/prereg_*` file.

## Why
A literature review (Fan et al. 2609.20804; Liu et al. 2604.12147) says a reviewer will ask whether the planner's
plan helps through its *information* or through being *any plan-shaped text*, and whether an *external* plan beats
the executor's *own* plan. Our dev floor `sft_plan` (tailored executor + one replayed luna plan,
`configs/hj8_sft_plan_bplus.yaml`, campaign `hj8_sft_plan_bplus_20260921iaware`, 0.7181 goal_pass) has neither
control. Both arms are **exploratory on dev** (never "registered"), 57 dev tasks x seeds 1, 2 = 114 episodes each,
**zero hosted calls**, one H100.

## Arm 1: wrong-task plan (WTP)
- Config `configs/dev_sft_plan_wrongtask_bplus.yaml`: `configs/hj8_sft_plan_bplus.yaml` with only `campaign_id:
  dev_sft_plan_wrongtask_bplus_20260924` and one new key `planner.packet_task_map:
  configs/dev_wrongtask_plan_map.json` changed/added. Header comment lists the changed keys (house style; see
  `configs/dev_advise_neutral_fixed_k_1_fullctx.yaml`).
- For episode (task t, seed s) the cached-packet planner replays the packet of (pi(t), s) from the same
  `packet_source` (`hj1b_planner_20260915`). The executor still receives its own task t. `on_missing: fail` stays.
- The map `pi`, built by a new dev-only script `scripts/setup/make_wrongtask_map.py` (refuses any non-dev split):
  1. the 57 dev task ids; plan length = characters of the first plan text in each task's hj1b packet, mean over
     seeds 1, 2 (find where CachedPacketPlanner reads the plan; cite it);
  2. sort tasks by (plan length, task_id);
  3. pick the smallest cyclic shift k >= 1 over that order such that scenario(t) != scenario(pi(t)) for every t,
     where scenario is defined exactly as `scripts/analysis/cluster_inference.py` defines it (cite the line);
  4. write `configs/dev_wrongtask_plan_map.json` = {"k", "order", "map": {t: pi(t)}, "plan_chars": {t: n}}.
  So pi is a permutation, a derangement, scenario-distinct, and length-matched to a neighbour.
- Every episode records its source task in an event payload (e.g. `packet_task_source`) so the analysis can check
  the remap happened. A task missing from the map is a hard error, never a silent fall-through to the right plan.

## Arm 2: self-plan (SP)
- Config `configs/dev_sft_plan_selfplan_bplus.yaml` from `configs/hj8_sft_plan_bplus.yaml`: campaign_id
  `dev_sft_plan_selfplan_bplus_20260924`; the planner block becomes a **locally served planner that is the executor
  itself**: `type: vllm`, `model: sft_b_plus` (the LoRA alias the executor's vLLM serves, so the plan comes from the
  same weights that execute), base URL = the executor's server, `temperature: 0.7`, `max_tokens: 2048`,
  `chat_template_kwargs.enable_thinking: false`, **no** `packet_source` (every key plans live). Copy the vllm
  planner keys' layout from `configs/lp2_hj8_sft_plan_bplus.yaml`.
- The plan prompt must be the one luna's hj1b plans were produced with. Verify (cite both code paths) that
  VllmPlanner's plan call sends the same plan prompt text as the codex planner's; if it differs, report the diff and
  do not "fix" it without asking.
- A plan that fails to parse or is empty is recorded (count it; the episode proceeds as the harness already does
  for a planless key). No new retries.
- Serving: one GPU, granite + `sft_b_plus`, one vLLM server used by both roles. Prefer the smallest change to
  `scripts/pbs/hj12_live.pbs` (it already serves this executor): e.g. export `SIDEKICK_PLANNER_BASE_URL` to the
  executor's URL for configs whose planner is vllm and whose `planner.model` equals the executor's `lora_name`, and
  refuse any other vllm-planner config (this wrapper serves no second model). Confirm with a test that planner
  requests would carry `model: sft_b_plus` and that the served-model probe (A5 hardening) accepts the alias.

## Both arms
- Register both stems wherever `hj12_live.pbs` lists runnable dev arms (see how `dev_advise_neutral_fixed_k_1_fullctx`
  was added in commit 9460b06, and its `arms_select` selftest). Never name anything `j10_*`.
- **Adapter build.** Report [OBSERVED] which adapter path `hj12_live.pbs` serves as `sft_b_plus`, and whether it is
  the build in the `run_start` events of `hj8_sft_plan_bplus_20260921iaware` and of the tailored executor-alone
  campaign `hj8_executor_alone_bplus_20260919` (ledger ADV-FC-02 records an earlier build mismatch). Do not create
  extra arms; just report.
- **Line citations.** Paper and preregs cite source lines (`grep -rn 'planner.py:[0-9]\|runner.py:[0-9]\|loop.py:[0-9]'
  docs paper scripts tests`). Put new logic in a new module (e.g. `src/sidekick/agents/packet_remap.py`) and make any
  edit to an existing cited file **line-neutral** for every cited line (same content on the same line number).
- **Tests** (new files under `tests/unit/`): the map's properties (permutation, derangement, scenario-distinct, sorted
  order, deterministic); the remap lookup and its hard error; both configs differ from the source only in the listed
  keys; the wrapper's routing/refusal for the self-plan config; the `arms_select` selftest for both stems. Run the
  new tests plus `tests/unit/test_dev_arms.py`, `tests/unit/test_hj12_live*.py` (whatever exists) and the planner /
  runner tests through `hpc` (common rules). Then run the **full suite** once via hpc and report pass/fail counts
  (the last full run was 1310 passed).
- Build the map by running your script through `hpc` and include the JSON.

## Report (<= 400 words)
Files created/edited with one line each; the map's k and three example pairs with their plan lengths; the adapter
build answer; the plan-prompt comparison; test counts (new, targeted, full suite) with PBS job ids; the exact
`qsub` lines Claude should use later for each arm (do not run them). Tag claims [OBSERVED path:line] / [INFERRED].
