# A5b (U-V2, re-issue) — the J8 frontier configs, and make `verify_configs.py` green

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files are `configs/*.yaml`, `scripts/setup/verify_configs.py` and its test.
**Do not touch** `src/sidekick/runner.py`, `src/sidekick/agents/`, `scripts/pbs/`,
`scripts/setup/fit_value_function.py`, `scripts/setup/branch_counterfactual.py` — other units own
those this cycle.

## Why this is a re-issue

A previous worker ran this unit and **died mid-write**: it had composed
`configs/hj8_executor_alone_bplus.yaml` and `configs/hj8_sft_plan_bplus.yaml` in memory but the
process ended before either reached disk. **Zero config files exist.** Start from nothing.

That worker did, however, establish three facts before it died, and **I have independently
verified all three against the source**. They are given here so you do not spend the unit
re-deriving them. Treat them as settled:

1. **`on_missing` does reach the constructor.**
   `on_missing=str(planner_cfg.get("on_missing", "fail"))` is passed to `CachedPacketPlanner`
   [OBSERVED src/sidekick/runner.py:147]. So writing `planner.on_missing: fail` in a config is a
   real, load-bearing zero-quota guarantee, not a decorative key.

2. 🔺 **`verifier.path` must name the JSON FILE, not the directory.**
   `FeatureVerifier.load` does `json.loads(Path(path).read_text(...))`
   [OBSERVED src/sidekick/agents/verifier.py:229]. The previous brief said to point at the
   directory `artifacts/verifiers/feature_lr_20260918` — **that was my error and it would have
   raised `IsADirectoryError` at run time.** The correct value is:
   `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/artifacts/verifiers/feature_lr_20260918/weights.json`

3. 🔺 **`oracle_labels` must be INLINE. There is no path key.**
   The runner reads `cfg.get("oracle_labels") or {}` and indexes it directly
   [OBSERVED src/sidekick/runner.py:226-232], keyed `"<task_id>/<seed>"` with a fallback to bare
   `task_id` then `cfg["oracle_steps"]`. A `path`-style key would be **silently ignored** — the
   arm would run with zero oracle steps and look like a healthy null. The dev labels file is
   `/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/oracle_labels.json`, and it is
   only **2,617 bytes / ~106 keys** [OBSERVED, `wc -c`], so inlining it is cheap. Transcribe it
   faithfully — including the **empty lists**, which mean "no oracle step for this pair" and are
   not the same as a missing key.

Also established: the system/arm name is selected by the **`--system` CLI flag**, not by a config
key — so do not invent one.

## Model your work on the existing configs

Read `configs/hj3_sft_plan.yaml` and `configs/hj4b_fixed_k_dev.yaml` first; match their shape, key
order and comment style. Both set `executor.max_prompt_tokens: 30720`.

⚠ `configs/hj4b_fixed_k_dev.yaml:11` sets `campaign_id: hj4_correction_train_20260917` — a *train*
id in a *dev* config. **Do not copy that.** Every config you write gets a correct, distinct
`campaign_id`.

## The configs to create

All on the **dev** split, executor adapter alias `sft_b_plus` unless stated.

**Zero-planner-call arms (these run BEFORE the quota reset — they must be incapable of spending):**

1. `configs/hj8_executor_alone_bplus.yaml` — `executor_alone`, `executor.lora_name: sft_b_plus`,
   no planner (follow `configs/hj3_sft_b_exec.yaml`).
2. `configs/hj8_sft_plan_bplus.yaml` — `sft_plan`, `executor.lora_name: sft_b_plus`,
   `planner.packet_source: /scratch/n12194778/sidekick/results/hj1b_planner_20260915`,
   `packet_system: planner_alone`, **`planner.on_missing: fail`**.

**Live-planner arms (these wait for the reset — still write the configs now):**

3. `configs/hj8_fixed_k_{3,5,10}.yaml` — `fixed_k`, `k` per file.
4. `configs/hj8_router_seq_tau{03,05,07}.yaml` — `router_seq`, with
   ```yaml
   verifier:
     kind: feature_lr
     path: <the weights.json path from fact 2 above>
     threshold: 0.3   # 0.5, 0.7
   ```
5. `configs/hj8_sidekick_tau{03,05,07}.yaml` — `sidekick`, `verifier: {kind: self_p_ask,
   threshold: τ}`. This kind also flips the executor into logprob mode
   [OBSERVED src/sidekick/runner.py:156-158, 175]. ⚠ The `sidekick` arm normally serves the
   `sft_c` adapter, which **does not exist and is not being trained**. Point these at
   `sft_b_plus` and say so in a config comment: this measures the self-gate on the *control*
   adapter, not a trained sidekick.
6. `configs/hj8_oracle_escalation.yaml` — `oracle_escalation`, with the labels inlined per fact 3.

## Second task — `verify_configs.py`

It **currently exits non-zero on this repo** and is wired into no PBS gate
[OBSERVED docs/FOLLOWUPS.md:362]. Run it, read the real failures, fix them. The likely cause is
the prompt-budget check over `configs/*.yaml` against the 7-name `FROZEN_PILOT_ALLOWLIST`
[OBSERVED scripts/setup/verify_configs.py:20-28, 62-81].

**Fix the configs, not the check** — unless the check itself is wrong, in which case explain why
in the report *before* changing it. Every config you write carries
`executor.max_prompt_tokens: 30720` and must pass. Finish with `verify_configs.py` exiting **0**,
and quote its final output verbatim.

⚠ A related open item [OBSERVED docs/FOLLOWUPS.md:270-273]: `verify_configs.py` should check that
any config defining an executor also defines `max_prompt_tokens`, because omitting it is a
**silent** overflow at run time. If that check is cheap to add while you are in the file, add it
and say so; if it makes existing configs fail, report rather than mass-edit frozen configs.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job** — a training job is
  running right now and the GPU queue is congested.
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Read the labels file; never write it.
- **Do not commit.** Suite baseline is now **365 passed, 1 skipped** (it rose from 349 when two
  sibling units landed tests). Never fewer, never a failure.
- Write `campaign/workers/STATUS_A_5b.md` with resume state per milestone, updated as you go —
  the previous run of this unit lost everything by not doing that.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The list of configs created, and `verify_configs.py`'s final verbatim output.
- Confirmation that each of the three established facts above was honoured, with the literal line
  from your config that implements it.
- Anything you found that contradicts the three facts — I verified them, but if the tree disagrees
  with me, **say so rather than working around it silently**.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
