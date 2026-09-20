# Brief E3 — dev evaluation of the intervention-aware adapter

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**PREREQUISITE: unit E2 must have completed and trained the adapter.** Before starting, confirm
`campaign/workers/STATUS_E2.md` reports a successful training run AND that
`/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b/` contains
`adapter_config.json` plus one of `adapter_model.safetensors` / `.bin` / `.pt`. If not, STOP and write
`campaign/workers/STATUS_E3.md` saying you are blocked.

## What this measures

Four dev arms, run on the NEW adapter, each paired against the SAME arm already measured on
`sft_b_plus` at n=114 (campaign date `20260920`). One variable changes: the adapter.

| stem | what it answers |
|---|---|
| `hj8_sft_plan_bplus` | did unprompted plan-following regress? (free — replays cached packets) |
| `hj8_fixed_k_10` | low dose (~2.75 calls/ep): does intervention stop harming? |
| `hj8_fixed_k_3` | high dose (~6.74 calls/ep): does the dose-response curve flatten? |
| `hj8_oracle_escalation` | new ceiling under label foresight |

On `sft_b_plus`, survivor goal_pass fell monotonically with dose: 0.700 (1.0 calls) → 0.662 (2.75) →
0.605 (6.74). **Whether that slope flattens is the headline result of this unit.**

## Why there are no new configs

`scripts/pbs/hj8_frontier.pbs:111-112` already makes the adapter overridable:

```
ALIAS_SFT_B_PLUS="${ALIAS_SFT_B_PLUS:-sft_b_plus}"
ADAPTER_SFT_B_PLUS="${ADAPTER_SFT_B_PLUS:-/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b}"
```

Keep the alias `sft_b_plus` (the configs' `executor.lora_name` must match it) and override only the
path. This reuses the frozen `hj8_*` configs byte-for-byte, which is exactly what makes it a clean
ablation. **Do not create, edit or copy any `hj8_*` config.**

## 🔺 The one failure that would waste the whole run

`configs/hj8_sft_plan_bplus.yaml:25` warns that an alias/adapter mismatch means requests "silently hit
the BASE model and the whole evaluation measures nothing while still producing plausible numbers."
Because we are reusing the alias `sft_b_plus` for a *different* adapter, you MUST prove the new one
was served.

In BOTH the smoke and the full run, find the line `[hj8] lora-module sft_b_plus=<path>` in the job log
and confirm the path is the **iaware** directory, not `sft_b_plus_granite8b`. Paste it verbatim into
STATUS. If it shows the old path, STOP immediately — do not let the full run proceed.

## Step 1 — smoke first (~150 calls, non-negotiable)

```
qsub -v ARMSET=live,SMOKE_ONLY=1,DATE=20260921iawaresmoke,\
ARMS="hj8_sft_plan_bplus hj8_fixed_k_10 hj8_fixed_k_3 hj8_oracle_escalation",\
ADAPTER_SFT_B_PLUS=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b \
scripts/pbs/hj8_frontier.pbs
```

Pass criteria, all of which you check and report:
- the `lora-module` line shows the iaware path (above);
- the job logs its own vLLM port and its own pid owning that port;
- all four arms pass the smoke gate, zero crash rows;
- the escalation table prints non-identical call counts where expected.

Do not start Step 2 until the smoke passes.

## Step 2 — full run

Same command without `SMOKE_ONLY`, with `DATE=20260921iaware`. Expected live planner spend is roughly
**1,230 calls** (`fixed_k_10` ~314, `fixed_k_3` ~768, `oracle_escalation` ~148; `sft_plan` replays
cached packets and spends none). Walltime `10:00:00`. Require `n = 114` per arm and report `n_broken`.

Apply the 5% quota-stall rule: if `api_error + timeout` exceeds 5% of dispatched calls, pause and
report rather than burning the budget.

## Step 3 — analysis

Run `scripts/analysis/j8_frontier.py` with BOTH sets of arms, labelled so old and new are
distinguishable, e.g. `--arm fixed_k_10_base=<20260920 dir> --arm fixed_k_10_iaware=<20260921 dir>`.
Write the report to `campaign/results/hj8_frontier_iaware_20260921.report.json`.

Report, with CIs, paired and task-clustered:
1. `sft_plan_iaware − sft_plan_base` — the regression check.
2. `fixed_k_10_iaware − fixed_k_10_base` and `fixed_k_3_iaware − fixed_k_3_base`.
3. The dose-response slope on each adapter (survivor goal_pass at 1.0 / 2.75 / 6.74 calls/ep).
4. `oracle_escalation_iaware − sft_plan_iaware` — is there now headroom above plan-only?

Report BOTH all-episodes and survivors populations, as the existing report does.

## Constraints

- **Do not read, analyse or report any `test_normal` or `test_challenge` data. Dev only.**
- **Do not modify anything under `/scratch/n12194778/sidekick/results/`**, and never write under
  `hj6_branches_train_20260917`. New DATE → new campaign ids; nothing existing is overwritten.
- `aquarius01` is a LOGIN NODE: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. All compute via
  `qsub`/`hpc`. `timeout` on everything. BLAS pinned to 1 thread.
- GPU limits `max_run=2`, `max_queued=2`.
- Do not edit `docs/prereg_v1.md` or `docs/prereg_b1_pilot.md` — FROZEN.
- **Do not commit.** Claude reviews and commits.
- Size to under 10 h; `hpc-guard` kills at 12 h wall. Write resume state into STATUS per milestone.

## Return contract

`campaign/workers/STATUS_E3.md`, under 600 words: the verbatim `lora-module` line from both runs, job
ids and exit codes, per-arm `n` and `n_broken`, live planner spend, the four contrasts above with CIs,
and every claim tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`.
