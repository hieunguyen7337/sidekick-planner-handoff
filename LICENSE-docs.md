# Documentation and Paper License: Creative Commons Attribution 4.0 International

Copyright 2026 Nhu Hieu Nguyen

Paper text, figures, and documentation prose in this repository are licensed under the Creative Commons Attribution 4.0 International License (CC BY 4.0).

- Canonical URL: https://creativecommons.org/licenses/by/4.0/
- Legal Code URL: https://creativecommons.org/licenses/by/4.0/legalcode

## How to Attribute

When reusing, quoting, or adapting the documentation, paper drafts, or figures, please provide attribution as follows:

- **Author**: Nhu Hieu Nguyen
- **Title**: *How Should a Hosted Planner Help a Small Local Agent? Preregistered Held-Out Evidence on Handoff Depth and Help Channels*
- **Repository**: https://github.com/hieunguyen7337/sidekick-planner-handoff
- **License**: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)

---

## License Scope Breakdown

This repository uses a dual-licensing structure to clearly separate prose and figures from software and data. Every file in the repository falls into one of the following licensing scopes:

### 1. Creative Commons Attribution 4.0 International (CC BY 4.0)

Applies to all research prose, documentation, manuscripts, and figures:
- **Documentation & Research Prose (`*.md`)**:
  - Root markdown files: `README.md`, `RESEARCH_PROJECT_SPEC.md`, `AGENTS.md`
  - Research design and preregistrations: `docs/**/*.md` (including `docs/prereg_*.md`, `docs/claims_ledger.md`, `docs/HEAVY_JOBS.md`, `docs/PLAN.md`, etc.)
  - Campaign documentation: `campaign/**/*.md` (including `campaign/RUNS.md`, `campaign/campaign_index.md`, worker briefs, status files)
  - Paper manuscripts and drafts: `paper/**/*.md` (including `paper/preprint_*.md`, `paper/drafts/*.md`)
- **Figures (`*.pdf`, `*.png`)**:
  - All paper figures in `paper/figures/` (e.g., `paper/figures/f1_depth_curve.pdf`, `paper/figures/f1_depth_curve.png`, etc.)
- **Paper Publication Templates & Bibliography (`*.tex`, `*.tmpl`, `*.bib`)**:
  - LaTeX template and text templates: `paper/arxiv/template.tex`, `paper/arxiv/*.tmpl`
  - Reference bibliography: `paper/bibliography.bib`

### 2. Apache License 2.0 (`LICENSE`)

Applies to all source code, software tooling, test suites, execution configurations, cluster job scripts, schemas, and result datasets/logs across the repository (including those inside `paper/`, `docs/`, or `campaign/`):
- **Source Code (`*.py`)**:
  - Python packages in `src/sidekick/`
  - Scripts in `scripts/setup/`, `scripts/train/`, `scripts/analysis/`, and `paper/arxiv/contact_sheet.py`
  - Test suites in `tests/unit/`, `tests/integration/`, `tests/reproducibility/`
- **Shell & Cluster Job Scripts (`*.sh`, `*.pbs`)**:
  - Environment and serving scripts in `scripts/setup/*.sh`
  - PBS cluster batch submission scripts in `scripts/pbs/*.pbs`
  - arXiv toolchain build and packaging scripts: `paper/arxiv/build.sh`, `paper/arxiv/check_tex.sh`, `paper/arxiv/env.sh`, `paper/arxiv/install_toolchain.sh`, `paper/arxiv/package.sh`, `paper/arxiv/filters/test/run_tests.sh`
- **Build Scripts & Transformation Tools (`*.pl`, `*.lua`)**:
  - Preprocessing and metadata scripts in `paper/arxiv/`: `paper/arxiv/meta_ascii.pl`, `paper/arxiv/secrecy_scan.pl`, `paper/arxiv/filters/latex_prep.lua`, `paper/arxiv/filters/strip_internal.lua`
- **Configuration & Dependency Manifests (`*.yaml`, `*.toml`, `*.lock`, `.gitignore`)**:
  - Experiment and model configurations: `configs/**/*.yaml`
  - Project configuration and lockfiles: `pyproject.toml`, `uv.lock`, `.gitignore`
- **Data, Fixtures, Reports, and Logs (`*.json`, `*.jsonl`, `*.csv`, `*.tsv`, `*.txt`, `*.log`, `*.exit`)**:
  - Verification artifacts and configs: `artifacts/**/*.json`
  - Campaign result tables, manifests, and reports: `campaign/results/*.json`, `campaign/campaign_index.json`, `campaign/hj1_gate.json`, `data/*.json`
  - Test fixtures: `tests/fixtures/*.json`
  - Worker output logs, stage markers, and text listings: `campaign/workers/**/*.txt`, `campaign/workers/**/*.log`, `campaign/workers/**/*.exit`, `paper/arxiv/filters/test/*.txt`, `paper/arxiv/public_labels.txt`

### 3. Third-Party Upstream License (`third_party/bfcl/`)

- The vendored subset in `third_party/bfcl/` is licensed under the Apache License 2.0 by its original authors (Gorilla / BFCL team).
- Retains its upstream copyright and license: see `third_party/bfcl/LICENSE` and `NOTICE`.
- Exception inside that directory: `third_party/bfcl/README.md` and `third_party/bfcl/SHA256SUMS` were written for this project. The README is CC BY 4.0 (section 1) and `SHA256SUMS` is Apache-2.0 (section 2).

### 4. Licensing & Attribution Metadata

- `LICENSE`: Apache License 2.0 text.
- `LICENSE-docs.md`: CC BY 4.0 terms and scope definition (this document).
- `NOTICE`: Attribution notices for this project, BFCL, and AppWorld.
- `CITATION.cff`: Citation metadata format.
