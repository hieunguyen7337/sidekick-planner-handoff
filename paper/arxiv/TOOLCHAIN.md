# Publication Toolchain

## 1. Overview & Golden Rule

This directory contains the scripts and configuration for the publication toolchain used to build arXiv-ready LaTeX papers, compile Pandoc Markdown manuscripts, and render visual quality check artifacts (contact sheets and high-resolution page zooms).

> **THE ONE RULE:**
> Every compilation, package installation, conversion, and rendering step **MUST** run inside a PBS job via `hpc`.
> **NEVER** run TeX engines (`pdflatex`, `bibtex`), `pandoc`, `tlmgr`, `micromamba`, `curl`, `tar`, or image rendering utilities directly on the login node (`aquarius01`).

---

## 2. Directory Layout

The toolchain components and build artifacts are strictly isolated outside the repository tree:

| Path | Purpose / Description |
| :--- | :--- |
| `/scratch/n12194778/pubtools/TinyTeX/` | Standalone TeX Live / TinyTeX distribution root. |
| `/scratch/n12194778/pubtools/bin/` | Symlink shim directory containing select binaries (`pandoc`, `pdftoppm`, `pdfinfo`, etc.). |
| `/scratch/n12194778/pubtools/poppler/` | Dedicated conda-forge environment providing Poppler rendering tools. |
| `/scratch/n12194778/pubtools/micromamba/` | Standalone micromamba executable (`bin/`), root prefix, and package cache (`pkgs/`). |
| `/scratch/n12194778/pubtools/downloads/` | Cached distribution tarballs and binaries (TinyTeX tarball `TinyTeX-1-linux-x86_64-v<YYYY.MM>.tar.xz`, pandoc fallback tarball if ever used, etc.). |
| `/scratch/n12194778/pubtools/logs/` | Toolchain installation, repair, and build logs. |
| `/scratch/n12194778/pubtools/VERSIONS.txt` | Key-value provenance manifest listing installed tool and package versions. |
| `/scratch/n12194778/pubtools/PANDOC_SOURCE.txt` | Origin recording of the active pandoc binary (`quarto-module` or `static`). |
| `/scratch/n12194778/paper_build/` | Output directory for all paper compilation artifacts (never committed to repository). |

> **Storage & Mirror Resolution:**
> Note that `/scratch` resolves to `/mnt/weka/scratch` on cluster storage (for example, `tlmgr` reports the installation directory as `/mnt/weka/scratch/n12194778/pubtools/TinyTeX`). In addition, `tlmgr` automatically selects a nearby CTAN mirror via `mirror.ctan.org` (the installation run used AARNet and cicku AU mirrors).

---

## 3. Toolchain Versions

*Populated upon completion of `install_toolchain.sh`.*

| Component | Version / Provenance |
| :--- | :--- |
| TinyTeX Release | `v2026.09` (`TinyTeX-1-linux-x86_64-v2026.09.tar.xz`) |
| TeX Live Year | `2026` |
| `tlmgr` | `tlmgr revision 79639 (2026-07-10 18:45:34 +0200)` |
| `pdflatex` | `pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)` |
| `bibtex` | `BibTeX 0.99e (TeX Live 2026)` |
| `pandoc` | `pandoc 3.6.3` (source: `quarto-module`, symlink to `/mnt/weka/pkg/rhel94/AuthenticAMD-25/software/quarto/1.7.32-x64/bin/tools/x86_64/pandoc`) |
| Pandoc Source | `quarto-module` |
| Quarto | `1.7.32` |
| Poppler (`pdftoppm` / `pdfinfo`) | `poppler 26.09.0` (conda-forge, via micromamba) |
| `micromamba` | `2.9.0` |

Recorded 2026-09-28 from `VERSIONS.txt` (job 25952130.aqua, cpu1n048); re-run the installer to refresh it.

---

## 4. Environment Configuration (`env.sh`)

Inside any PBS batch job, source `env.sh` using its absolute path:

```bash
source /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/env.sh
```

Current verbatim content of `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/env.sh`:

```bash
# source this inside a PBS job; it only sets environment variables
# Do not run directly on the login node.

export PUBTOOLS=/scratch/n12194778/pubtools

# Prepend TinyTeX bin and pubtools shim bin if not already in PATH (order: $PUBTOOLS/bin then TinyTeX)
case ":$PATH:" in
  *":$PUBTOOLS/TinyTeX/bin/x86_64-linux:"*) ;;
  *) export PATH="$PUBTOOLS/TinyTeX/bin/x86_64-linux:$PATH" ;;
esac

case ":$PATH:" in
  *":$PUBTOOLS/bin:"*) ;;
  *) export PATH="$PUBTOOLS/bin:$PATH" ;;
esac

export PAPER_BUILD=/scratch/n12194778/paper_build
export PUBTOOLS_PY=/scratch/n12194778/sidekick/env/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
```

---

## 5. Usage in PBS Jobs

To use the toolchain, invoke `hpc` passing a single bash command string that sources `env.sh` and runs your build steps. Because `hpc` accepts an argv list, compound commands must be wrapped in `bash -c`:

```bash
# Example paper build run in a PBS job:
timeout 900 hpc bash -c '
  source /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/env.sh
  mkdir -p "$PAPER_BUILD/my_paper"
  cd "$PAPER_BUILD/my_paper"
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  bibtex main
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
'
```

---

## 6. Running and Repairing the Installation

### Execution Command
Run the installer inside a PBS batch job:

```bash
timeout 3000 hpc -t 01:00:00 bash /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/install_toolchain.sh
```

### Idempotency & Diagnostics
- The installer is fully idempotent. On re-runs, existing functional binaries and cached download archives are detected and skipped.
- Detailed execution logs are appended to `/scratch/n12194778/pubtools/logs/install_<TIMESTAMP>.log`.
- If a compilation run encounters a missing LaTeX package or `.sty` file, `install_toolchain.sh` includes an automatic resolution loop that queries `tlmgr search --global --file "/<FILE>"` and auto-installs the required package, logging `AUTO-INSTALLED: <pkg> (for <FILE>)`.
- To manually install an additional package inside a PBS job:
  ```bash
  timeout 600 hpc bash -c '
    source /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/env.sh
    tlmgr install <package_name>
  '
  ```

### Test Document Validation
The installer validates the pipeline end-to-end with outputs located in `/scratch/n12194778/paper_build/toolchain_test/`:
- **Pandoc Natbib & LaTeX Pipeline**:
  `test.md` → pandoc `--natbib` → `test.tex` → pdflatex/bibtex/pdflatex×2 → `test.pdf` (1 page) → `test_60-1.png`, `test_110-1.png`, `sheet_01.png`
- **Package Load Tests**:
  - `loadtest.tex` (all listed packages with newtx)
  - `loadtest_ptm.tex` (mathptmx)

---

## 7. Package Mapping (LaTeX Package -> TeX Live / tlmgr Name)

When adding or troubleshooting packages, note that certain LaTeX packages map to different bundle names in TeX Live:

| LaTeX Package / Command | TeX Live / `tlmgr` Bundle | Notes |
| :--- | :--- | :--- |
| `longtable`, `array`, `tabularx` | `tools` | Bundled in standard LaTeX tools |
| `graphicx`, `color`, `graphics` | `graphics` | Bundled in graphics distribution |
| `lmodern` | `lm` | Latin Modern scalable fonts |
| `amssymb` | `amsfonts` | Extended AMS mathematical symbols |
| `mathptmx` | `psnfss` | Standard PostScript font set (`times`, `helvetic`, `courier`, `symbol`, `zapfding`) |
| `textcomp` | `latex` | Built into the modern LaTeX format kernel |
| `newtxtext`, `newtxmath` | `newtx` | Times Roman math & text support |
| `xpatch` | `xpatch` | Macro patching extension required by `newtx` |
| `scalefnt` | `carlisle` | Font scaling utility required by `newtx` |
| `centernot` | `oberdiek` | Centered negation symbol required by `newtx` (pulls in `grfext`, `grffile`) |
| `ts1-qtmr` | `tex-gyre` | TS1 text-companion metrics for newtxtext, needed for § and other TS1 glyphs |

`newtx` also needs `xpatch`, `carlisle` (scalefnt), `oberdiek` (centernot) — found by the auto-resolve loop on the first successful run, now in the explicit list.

---

## 8. Architectural & Design Decisions

1. **Symlink Shim Directory (`$PUBTOOLS/bin`)**:
   The dedicated Poppler conda environment includes shared utilities (such as `curl`, `openssl`, `xz`, `bzip2`) that could shadow system packages and interfere with host networking or SSL certificates. Instead of exposing `$PUBTOOLS/poppler/bin` directly on `PATH`, individual preview binaries (`pdftoppm`, `pdfinfo`, `pdftotext`, `pdffonts`, `pdfimages`, `pdfseparate`, `pdfunite`) are symlinked into `$PUBTOOLS/bin`.
2. **Strict PATH Isolation (No `tlmgr path add`)**:
   Neither the installer nor `env.sh` modifies `~/bin`, `/usr/local/bin`, or user shell profiles (`~/.bashrc`, `~/.condarc`). Path resolution is strictly scoped to jobs that source `env.sh`.
3. **Quarto Pandoc Symlink**:
   Pandoc is linked directly from the site module binary (`$EBROOTQUARTO/bin/tools/x86_64/pandoc`), avoiding the overhead of `module load quarto` during fast compile cycles.

---

## 9. Visual Quality Inspection Workflow

Visual layout verification of compiled PDF documents is conducted via raster preview generation and contact sheets:

1. **Contact Sheet Generation (60 DPI preview grid)**:
   Render 60 DPI page images and combine them into multi-page contact sheets using `contact_sheet.py`:
   ```bash
   timeout 600 hpc bash -c 'source /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/env.sh; cd $PAPER_BUILD/x; pdftoppm -r 60 -png paper.pdf p60; "$PUBTOOLS_PY" /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/contact_sheet.py --out sheet p60-*.png'
   ```

2. **Detailed Zoom Inspection (110 DPI)**:
   Where fine typographical alignment or formula layout requires inspection, render single targeted pages at 110 DPI:
   ```bash
   timeout 600 hpc bash -c 'source /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/env.sh; cd $PAPER_BUILD/x; pdftoppm -r 110 -png -f N -l N paper.pdf zoom'
   ```

---

## 10. Known Pitfalls

1. **TinyTeX Asset Naming**:
   TinyTeX release tarball naming changed from `TinyTeX-1.tar.gz` / `TinyTeX-1-v<VERSION>.tar.gz` to platform-specific `.tar.xz` archives (e.g., `TinyTeX-1-linux-x86_64-v<YYYY.MM>.tar.xz`). The `daily/TinyTeX-1.tar.gz` URL is obsolete and returns HTTP 404. Decompression requires GNU tar / `xz`.
2. **Never Run `tlmgr path add`**:
   `tlmgr path add` attempts to create symlinks in system directories or `~/bin`, which violates isolation and fails without root privileges. PATH configuration must remain strictly scoped through `env.sh`.
3. **`hpc` Argument Handling**:
   `hpc` takes an argument list rather than interpreting a raw shell pipeline or composite command string. Compound commands (chaining with `;`, `&&`, or redirects) must be wrapped in `bash -c '...'`.
4. **Login Node Rule & Job Timeouts**:
   PBS jobs require ~100 s in queue wait time. Any `timeout <seconds> hpc ...` wrapper command must specify at least `timeout 600` so that execution is not aborted while waiting in the scheduling queue.
