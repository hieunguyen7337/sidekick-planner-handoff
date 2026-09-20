# Sidekick

**A small executor specialised to one frozen planner, trained to know when to call for help.**

A frontier-class planner is expensive and a small open-weight model is cheap but weak. The usual fix is
routing: send hard queries to the big model. Sidekick asks a different question — if a small executor is
post-trained **for one specific frozen planner**, and trained not just to act but to decide *when its own
action is not good enough*, how much of the planner's work can it take over before quality drops?

The study measures that trade-off directly:

- **Non-inferiority** of the collaboration against the planner working alone, paired by task.
- **Frontier-compute displacement**, `1 − planner_tokens(collaboration) / planner_tokens(planner_alone)`.
- **Escalation quality** — is asking for help calibrated, or just frequent?

The claim that carries the work is not that a small model matches a big one. It is that **making the
executor intervention-aware beats training it to merely follow plans**, at the same planner cost.

## Setup

| piece | choice |
|---|---|
| Frozen planner | `gpt-5.6-luna` via the Codex CLI, shell tool disabled, effort `medium` |
| Executor | `ibm-granite/granite-4.2-8b` with LoRA (`granite-4.2-3b` as the capability-gap arm) |
| Verifier | `Qwen/Qwen3-1.7B` with one calibrated escalation head |
| Environment | [AppWorld](https://github.com/StonyBrookNLP/appworld) — 750 tasks, programmatic state evaluation |
| Compute | QUT Aqua, PBS, one H100 per job |

## Status

**Campaign stage.** Baselines (HJ-1/HJ-1R), teacher collection (HJ-2B), state probe (HJ-1.5), LoRA adapter training (`sft_b`, `sft_b_plus`), counterfactual branch runs (HJ-6), and dev baseline evaluation (J8a) are complete. Harness repairs are complete, and the J8 dev frontier evaluation and B1 clean counterfactual pilot are the next submissions.

## Where to read

| document | what it is |
|---|---|
| `RESEARCH_PROJECT_SPEC.md` | the full research specification, verbatim |
| `docs/PLAN.md` | the resource-matched proof-of-concept plan actually being executed |
| `docs/HEAVY_JOBS.md` | every expensive job, fully specified and **not yet submitted** |
| `docs/feasibility/m0_gates.md` | feasibility gate results |
| `campaign/briefs/SEAM_CONTRACT.md` | the interfaces every component is written against |
| `docs/archive/` | superseded plans, kept for the record |

## Layout

```
src/sidekick/
  protocols/     schemas — packet, action, event, run result
  trajectories/  append-only event log and run manifests
  cost/          dated price schedule and per-actor ledger
  agents/        planner client (codex), executor client (vLLM), verifier, router
  environments/  AppWorld and a dependency-free mock world
  systems/       the eight system variants under comparison
  runner.py      multiprocessing campaign runner, resumable
scripts/         setup scripts and PBS job templates
campaign/        worker briefs and logs
```

Data, models and adapters live outside the repo, under `/scratch/n12194778/sidekick`.
