# Sidekick: planner-to-executor handoff

**A small executor specialised to one frozen planner, trained to know when to call for help.**

A frontier-class planner is expensive and a small open-weight model is cheap but weak. The usual fix is routing: send hard queries to the big model. Sidekick asks a different question: if a small executor is post-trained for one specific frozen planner, and trained not just to act but to decide when its own action is not good enough, how much of the planner's work can it take over before quality drops?

The study measures that trade-off directly:

- **Non-inferiority** of the collaboration against the planner working alone, paired by task.
- **Frontier-compute displacement**, `1 − planner_tokens(collaboration) / planner_tokens(planner_alone)`.
- **Escalation quality** — whether asking for help is calibrated or merely frequent.

The project's starting hypothesis was that making the executor intervention-aware would beat training it merely to follow plans, at the same planner cost. The preregistrations and the claims ledger record what the registered reads found.

This repository contains the experimental harness, environment adapters, analysis scripts, preregistrations and result reports for the paper:

> **How Should a Hosted Planner Help a Small Local Agent? Preregistered Held-Out Evidence on Handoff Depth and Help Channels**  
> Nhu Hieu Nguyen (Queensland University of Technology)  
> *arXiv link to be added* — evaluated on [AppWorld](https://github.com/StonyBrookNLP/appworld) and the [Berkeley Function Calling Leaderboard (BFCL)](https://github.com/ShishirPatil/gorilla).

---

## Status

**Updated 2026-09-28.** Three preregistered held-out reads on AppWorld `test_normal` are complete, each read once: J10, the registered test read (`docs/prereg_j10_amendment_20260924.md`); J11, the channel result across planner strength (`docs/prereg_j11_lp2_test_20260924.md`); and J12, prefix depth (`docs/prereg_j12_depth_test_20260924.md`). The BFCL `multi_turn_base` arm has an exploratory dev read (`docs/prereg_bfcl_dev_20260924.md`) and a registered test protocol (`docs/prereg_bfcl_test_20260925.md`). The original protocol is `docs/prereg_v1.md`. Every claim and its status is in `docs/claims_ledger.md`, and runs are indexed in `campaign/RUNS.md`.

---

## Where to read

| Document | Description |
|---|---|
| `RESEARCH_PROJECT_SPEC.md` | Full research specification and hypothesis ledger, verbatim |
| `docs/PLAN.md` | Resource-matched plan executed across experimental stages |
| `docs/HEAVY_JOBS.md` | Specification of the heavy compute jobs as planned |
| `docs/claims_ledger.md` | Preregistered claims ledger, report JSON keys, and test outcomes |
| `docs/feasibility/m0_gates.md` | Feasibility gate criteria and initial verification results |
| `campaign/RUNS.md` | Log of campaign execution runs, configuration arms, and checkpoints |
| `campaign/briefs/SEAM_CONTRACT.md` | Protocol interfaces, action/packet schemas, and seam contracts |
| `docs/archive/` | Superseded plans and historical design notes, kept for provenance |

---

## What is not included, and why

To respect benchmark licenses, compute privacy, and storage constraints, the public repository excludes the following items:

1. **AppWorld Protected Benchmark Data**: The directories `data/tasks/`, `data/api_docs/`, `data/base_dbs/`, and `data/datasets/` were removed across repository history. AppWorld allows redistribution of this portion only in encrypted `.bundle` form. The files `campaign/workers/harm_sample_corrections.jsonl` and `tests/fixtures/hj6_branches_dev_sample.jsonl` (which quoted AppWorld train and dev content) were removed from history; an aggregate file without the correction text and a synthetic fixture sit at the same paths.
2. **Model Weights and LoRA Adapters**: Model weights and trained LoRA adapter checkpoints are not committed due to file size.
3. **Raw Trajectories and Storage Outputs**: Raw run output directories and episode trajectory logs under `/scratch` are not committed (due to multi-gigabyte volume and because detailed trajectories embed AppWorld protected environment state).
4. **Internal Release Notes and Operational Logs**: `paper/release/` (internal submission checklists and drafts) and raw worker terminal stream logs in `campaign/workers/logs/` (and root `u2b_test_run*.log` files) were removed from history; a cleaned public copy of `paper/release/ai_use.md` was re-added at the tip in a forward commit, and nothing else under `paper/release/` is published. The operational note `docs/plan_luna_reset_20260925.md` was replaced by a one-paragraph stub to preserve citation links.
5. **Literal Replacements in History**: A few literals were replaced throughout the history: persona email addresses in a dev diagnosis JSON and its test became `personaN@example.invalid`; one dev answer value in an example became a placeholder number; two song titles in examples became placeholder titles; one quoted AppWorld train instruction became `[instruction omitted: AppWorld protected content]`; and quoted correction strings in `campaign/workers/W13_CORRECTIONS.md` became `[correction text omitted]`. Commit messages received the same replacements.
6. **Citations to Removed Paths in Frozen Documents**: Where frozen preregistrations or documents cite a removed path, they now point to a stub, an aggregate replacement, or no file; see `docs/provenance/REWRITE_NOTE.md` for the complete mapping. Some registered-read evidence in the frozen preregistrations and the claims ledger cites worker and PBS job logs under `campaign/workers/logs/`; those logs were never tracked in git and are not published, so that evidence cannot be checked from this repository.

---

## History rewritten on 2026-09-28

This public repository was produced from the private research repository via a single pass of `git filter-repo` on 2026-09-28:

- **Original Commit Tip (`CUT_SHA`)**: `67ea249072e5ceb7bd427f128e2f0b564857454e`
- **Original History Bundle SHA256**: `1accf201948c1eda4fc560cb2031c796a57cd827eb86ec4671afe359c100c2d7`
- **Commit History**: Out of 333 original commits, 327 were preserved and 6 were pruned because they modified exclusively removed paths. Author and committer identities, email addresses, and timestamps were preserved without modification.
- **Frozen Content Invariance**: All frozen preregistrations (`docs/prereg_*.md`), the claims ledger (`docs/claims_ledger.md`), and preprint manuscripts (`paper/preprint_*.md`) have byte-identical git blob IDs before and after the rewrite (140 path/blob pairs verified, 0 differences).
- **Commit Hash Resolution**: Commit hashes cited within frozen documents refer to original commit hashes. They resolve to new commit hashes via `docs/provenance/commit_map.tsv` (`old_full<TAB>new_full<TAB>note`; the note marks pruned and unchanged commits and gives each pruned commit's tree-equivalent). Explanations of removed files and tree-equivalent commits are documented in `docs/provenance/REWRITE_NOTE.md`.
- **Bundle Verification**: The private plaintext git bundle allows independent verification that the original history hashes to `CUT_SHA`. The author retains an encrypted copy; it is not published because it contains AppWorld protected data.

---

## Setup

### Python Environment

This project requires Python >= 3.11. Dependencies are managed with `uv` (or `pip`):

```bash
# Using uv (recommended)
uv sync

# Or using pip in a virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Environment Variables

Set the following paths outside the repository:

- `APPWORLD_ROOT`: Directory where AppWorld and its benchmark databases reside.
- `SIDEKICK_ROOT`: Storage root for experiment checkpoints, generated data, and trajectory logs.

### AppWorld Setup

Install AppWorld and download its encrypted benchmark data according to its official instructions:

```bash
pip install appworld
appworld install
appworld download data
```

### System Configuration

| Component | Specification |
|---|---|
| **Frozen Planner** | `gpt-5.6-luna` via the Codex CLI, shell tool disabled, reasoning effort `medium` |
| **Planner-strength arms** | Local open-weight planners served with vLLM; see `docs/prereg_lp_planner_strength_20260923.md` and `docs/prereg_j11_lp2_test_20260924.md` |
| **Executor** | `ibm-granite/granite-4.2-8b` with LoRA (`granite-4.2-3b` as the capability-gap arm); zero-shot `Qwen/Qwen3-8B` as a second executor family |
| **Verifier** | `Qwen/Qwen3-1.7B` with calibrated escalation head |
| **Environments** | [AppWorld](https://github.com/StonyBrookNLP/appworld) (750 tasks, programmatic evaluation), [BFCL](https://github.com/ShishirPatil/gorilla) (`multi_turn_base`) |
| **Local Serving** | [vLLM](https://github.com/vllm-project/vllm) for local open-weight models |
| **Cluster Compute** | QUT Aqua HPC cluster (PBS), one NVIDIA H100 per job |

---

## Rerunning the analyses

### 1. Generating Figures from Committed Reports

The publication figures in `paper/figures/` (F1 through F12, in both PDF and PNG formats) and `paper/figures/figures_manifest.json` are generated directly from the committed analysis report JSON files in `campaign/results/`:

```bash
python scripts/analysis/figures.py
```

This script runs entirely on committed files without requiring raw trajectory data.

### 2. Computing Analysis Reports from Event Logs

The analysis scripts in `scripts/analysis/` (e.g., `scripts/analysis/j10_report.py`, `scripts/analysis/j11_report.py`, `scripts/analysis/j12_report.py`, `scripts/analysis/hj12_shape.py`, `scripts/analysis/j13_mechanism.py`, `scripts/analysis/j14_did.py`, `scripts/analysis/j16_inference.py`, `scripts/analysis/j16_robustness.py`, `scripts/analysis/b2_decomposition.py`, `scripts/analysis/bfcl_dev_report.py`, `scripts/analysis/bfcl_test_report.py`, `scripts/analysis/j17_dev_arms.py`, `scripts/analysis/j17_channel_fixes.py`, `scripts/analysis/j17_depth_fixes.py`) read raw episode records from run directories under `/scratch` (or `SIDEKICK_ROOT`), which are not included, and several also read committed reports in `campaign/results/`. They cannot be rerun from this repository alone; check each script's arguments (`--help`) for its inputs.

### 3. Running the Test Suite

The test suite contains unit, integration, and reproducibility tests:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 pytest -q
```

---

## Cluster-specific material

The configuration files in `configs/`, job scripts in `scripts/pbs/`, campaign logs in `campaign/`, and toolchain documentation in `paper/arxiv/TOOLCHAIN.md` record the exact execution parameters used on QUT's Aqua HPC cluster. They include PBS job identifiers, cluster hostnames, cluster usernames, and `/scratch/n12194778/...` storage paths verbatim to preserve experimental provenance. They document what was run and are not intended as portable single-command recipes. Commit metadata similarly reflects the cluster login environment.

---

## Test task ids in reports

The reports in `campaign/results/` (such as `campaign/results/j10_a1_cost_axes.report.json` and other registered-read reports) record AppWorld `test_normal` task identifiers alongside outcome and cost metrics. These reports contain only identifiers and aggregate scores; they do not include task instructions, dataset ground-truth answers, or protected environment strings. The identifiers are retained because the reports represent frozen registered-read evidence.

---

## Licence

- **Software & Data**: Source code, execution scripts, configurations, schemas, and results data are licensed under the [Apache License 2.0](LICENSE).
- **Prose & Figures**: Research manuscripts, paper text, figures, and documentation prose are licensed under the [Creative Commons Attribution 4.0 International License (CC BY 4.0)](LICENSE-docs.md).
- **Third-Party Components**: `third_party/bfcl/` is licensed under the Apache License 2.0 by the Gorilla / BFCL authors.
- **External Dependencies**: AppWorld is an external dependency governed by its own license and is not redistributed in this repository.
- See [NOTICE](NOTICE) for full copyright and attribution statements.

---

## Third-party benchmarks

- **AppWorld**: Harsh Trivedi, Tushar Khot, Mareike Hartmann, Ruskin Manku, Vinty Dong, Edward Li, Shashank Gupta, Ashish Sabharwal, Niranjan Balasubramanian. *AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents*. ACL 2024 (arXiv:2407.18901).
- **Berkeley Function Calling Leaderboard (BFCL)**: Shishir G. Patil, Huanzhi Mao, Fanjia Yan, Charlie Cheng-Jie Ji, Vishnu Suresh, Ion Stoica, Joseph E. Gonzalez. *The Berkeley Function Calling Leaderboard (BFCL): From Tool Use to Agentic Evaluation of Large Language Models*. ICML 2025 (PMLR 267, pp. 48371-48392).

The AppWorld canary string is recorded in `NOTICE`.

---

## How to cite

Please see `CITATION.cff` for citation metadata.

```bibtex
@misc{nguyen2026sidekick,
  author       = {Nguyen, Nhu Hieu},
  title        = {How Should a Hosted Planner Help a Small Local Agent? Preregistered Held-Out Evidence on Handoff Depth and Help Channels},
  year         = {2026},
  note         = {arXiv link to be added},
  url          = {https://github.com/hieunguyen7337/sidekick-planner-handoff}
}
```

When evaluating with these benchmarks, please also cite AppWorld and BFCL.

---

## Layout

```
artifacts/       calibrated verifier weights and feature artifacts
campaign/
  briefs/        component specifications and seam contracts
  results/       registered analysis reports and cost ledgers
  workers/       worker briefs and execution status logs
  RUNS.md        campaign run index
configs/         model, arm, and experiment configuration files
data/            benchmark split definitions and interim data
docs/
  archive/       superseded plans and earlier design revisions
  feasibility/   M0 feasibility gate logs and verification results
  lit/           literature screening protocols and audit logs
  provenance/    commit map (commit_map.tsv) and rewrite documentation
  claims_ledger.md registered claims ledger and report cross-references
  PLAN.md        execution plan
  HEAVY_JOBS.md  heavy compute job specifications
paper/
  arxiv/         arXiv build scripts, filters, and templates
  figures/       publication figures (PDF, PNG) and manifest
  preprint_*.md  paper manuscripts and drafts
scripts/
  analysis/      contrast, power, and figure generation scripts
  pbs/           PBS job submission templates for Aqua HPC
  setup/         environment, gateway, and verification scripts
  train/         LoRA adapter training and SFT dataset generation
src/sidekick/
  agents/        planner, executor (vLLM), verifier, and router clients
  cost/          price schedules and per-actor token ledger
  environments/  AppWorld and BFCL environment adapters, mock world
  protocols/     message, action, event, and packet schemas
  systems/       system execution variants and handoff loops
  trajectories/  event logging and run manifests
  runner.py      multiprocessing campaign runner
tests/
  fixtures/      test fixtures and synthetic trajectories
  integration/   planner, executor, and environment integration tests
  reproducibility/ split leakage and provenance tests
  unit/          component unit tests
third_party/
  bfcl/          vendored byte-for-byte subset of BFCL multi-turn eval
```
