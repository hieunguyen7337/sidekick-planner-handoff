# A5 (U-V2) — the J8 frontier configs, and make `verify_configs.py` green

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files are `configs/*.yaml`, `scripts/setup/verify_configs.py` and its
test. Another unit owns `src/sidekick/runner.py` — **do not touch it**. Another owns
`scripts/pbs/` — **do not touch it**.

**Create the files within your first three actions, then iterate with tests.**

## Why

J8 evaluates 12 arms on the dev split. Today `configs/` has six `hj*.yaml` and **no config
anywhere in the tree contains a `verifier:` block** — so `router_seq`, `sidekick` and
`oracle_escalation` have no config at all, and the τ sweep has no precedent.

## Model your work on the existing configs

Read `configs/hj3_sft_plan.yaml` and `configs/hj4b_fixed_k_dev.yaml` first and match their shape,
key order and comment style. Both already set `executor.max_prompt_tokens: 30720`.

⚠ `configs/hj4b_fixed_k_dev.yaml:11` sets `campaign_id: hj4_correction_train_20260917` — the
*train* campaign id in a *dev* config. Do **not** copy that; give every config you write a correct,
distinct `campaign_id`.

## The configs to create

All on the **dev** split, executor adapter alias `sft_b_plus` unless stated.

**Zero-planner-call arms (these run before the quota resets):**

1. `configs/hj8_executor_alone_bplus.yaml` — `executor_alone`, `executor.lora_name: sft_b_plus`,
   no planner (follow `configs/hj3_sft_b_exec.yaml`).
2. `configs/hj8_sft_plan_bplus.yaml` — `sft_plan`, `executor.lora_name: sft_b_plus`,
   `planner.packet_source: /scratch/n12194778/sidekick/results/hj1b_planner_20260915`,
   `packet_system: planner_alone`.

🔺 **Both of these, and every other cached-packet config you write, must set
`planner.on_missing: fail`.** `CachedPacketPlanner.__init__` takes `on_missing: "fail" | "call"`,
default `"fail"` [OBSERVED src/sidekick/agents/planner.py:654-657, 665]. Setting it **explicitly**
is a hard guarantee that the arm cannot spend hosted quota: a cache miss aborts loudly instead of
making a live call. Verify the key actually reaches the constructor through `make_planner`; if it
does not, **say so in your report rather than inventing a key that does nothing.**

**Live-planner arms (these wait for the quota reset — still write the configs now):**

3. `configs/hj8_fixed_k_{3,5,10}.yaml` — `fixed_k`, `k` set per file.
4. `configs/hj8_router_seq_tau{03,05,07}.yaml` — `router_seq` with
   ```yaml
   verifier:
     kind: feature_lr
     path: /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/artifacts/verifiers/feature_lr_20260918
     threshold: 0.3   # 0.5, 0.7
   ```
   The loader is `FeatureVerifier.load(path)` [OBSERVED src/sidekick/runner.py:187-194]. **Check
   whether `load` expects the directory or a specific JSON file inside it**
   [OBSERVED src/sidekick/agents/verifier.py:227-235] and write whichever it actually accepts.
5. `configs/hj8_sidekick_tau{03,05,07}.yaml` — `sidekick` with
   `verifier: {kind: self_p_ask, threshold: τ}`. This kind also flips the executor into
   logprob mode [OBSERVED src/sidekick/runner.py:156-158, 175]. ⚠ The `sidekick` arm normally
   serves the `sft_c` adapter, which **does not exist and is not being trained**. Point these at
   `sft_b_plus` and note in the config comment that this measures the self-gate on the control
   adapter, not the trained sidekick.
6. `configs/hj8_oracle_escalation.yaml` — `oracle_escalation`. Oracle steps are looked up as
   `cfg["oracle_labels"]["<task_id>/<seed>"]`, falling back to bare `task_id`, then
   `cfg["oracle_steps"]` [OBSERVED src/sidekick/runner.py:223-232]. The dev labels file is
   `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/oracle_labels.json`. Decide and
   state how the config references it — if the runner requires labels **inline** rather than by
   path, say so explicitly; do not silently write a path key the runner ignores.

## Second task — `verify_configs.py`

It **currently exits non-zero on this repo**, and is wired into no PBS gate
[OBSERVED docs/FOLLOWUPS.md:362]. Run it, read the actual failures, and fix them. The likely cause
is the prompt-budget check over `configs/*.yaml` against the 7-name `FROZEN_PILOT_ALLOWLIST`
[OBSERVED scripts/setup/verify_configs.py:20-28, 62-81].

**Fix the configs, not the check** — unless the check itself is wrong, in which case explain why in
your report before changing it. Every new config you write must carry
`executor.max_prompt_tokens: 30720` and must pass. Finish with `verify_configs.py` exiting **0**,
and quote its final output verbatim.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job** — a training job is
  already running and the GPU queue is congested.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.**
- Suite baseline **349 passed, 1 skipped** — never fewer.
- Write `campaign/workers/STATUS_A_5.md` with resume state per milestone.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The list of configs created, and `verify_configs.py`'s final verbatim output.
- For each of the three "check whether it actually works" points above (`on_missing`,
  `FeatureVerifier.load` path shape, oracle label referencing), state what you found with
  `path:line` and what you did.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
