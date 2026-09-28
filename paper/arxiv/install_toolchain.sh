#!/bin/bash
# ==============================================================================
# Publication Toolchain Installer
#
# Purpose:
#   Installs and configures a standalone publication toolchain under
#   /scratch/n12194778/pubtools for building arXiv LaTeX papers and rendering
#   preview images (TinyTeX / TeX Live, Pandoc, Poppler utilities).
#
# Execution:
#   This script MUST be run inside a PBS job via hpc:
#     timeout 3000 hpc -t 01:00:00 bash /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/arxiv/install_toolchain.sh
#
# Hard rule:
#   NEVER run this script directly on the login node (aquarius01).
# ==============================================================================

set -uo pipefail

# Refuse to run outside a PBS job
if [ -z "${PBS_JOBID:-}" ]; then
  echo "ERROR: Refusing to run on login node. Run via hpc / PBS job." >&2
  exit 3
fi

# Limit thread concurrency on shared resources
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

# Configuration & Directory Layout
PUB=/scratch/n12194778/pubtools
TEXDIR="$PUB/TinyTeX"
TEXBIN="$TEXDIR/bin/x86_64-linux"
SHIM="$PUB/bin"
DL="$PUB/downloads"
BUILD=/scratch/n12194778/paper_build/toolchain_test
REPO_FIG=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/figures/f1_depth_curve.pdf
export TMPDIR="$PUB/.tmp"
MM="$PUB/micromamba/bin/micromamba"

# Package lists
TL_CRITICAL=(
  natbib hyperref bookmark booktabs tools multirow graphics xcolor geometry microtype lm
  newtx fontaxes kastrup xstring txfonts psnfss times helvetic courier symbol zapfding
  xpatch carlisle oberdiek grfext grffile
)

TL_PKGS=(
  "${TL_CRITICAL[@]}"
  caption float enumitem amsmath amsfonts newunicodechar etoolbox fancyvrb upquote parskip
  footmisc url xurl pdflscape threeparttable siunitx placeins
  iftex footnotehyper framed setspace csquotes soul ulem selnolig unicode-math fontspec
  lualatex-math xkeyval kvoptions latexmk bibtex tex-gyre
)

# Ensure core directories exist
mkdir -p "$PUB" "$TEXDIR" "$TEXBIN" "$SHIM" "$DL" "$BUILD" "$TMPDIR" "$PUB/logs" "$PUB/micromamba/bin" "$PUB/micromamba/root" "$PUB/micromamba/pkgs"

# Setup logging
LOG="$PUB/logs/install_$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "=============================================================================="
echo "Publication Toolchain Installer Started"
echo "Host: $(hostname)"
echo "PBS Job ID: ${PBS_JOBID}"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Architecture: $(uname -m)"
if [ -f /etc/redhat-release ]; then
  echo "OS Release: $(cat /etc/redhat-release)"
fi
echo "Log file: $LOG"
echo "=============================================================================="

# Summary tracking structures
declare -a STAGE_NAMES=()
declare -a STAGE_STATUSES=()
declare -a STAGE_REASONS=()

stage_ok() {
  local name="$1"
  echo "[STAGE OK] $name"
  STAGE_NAMES+=("$name")
  STAGE_STATUSES+=("OK")
  STAGE_REASONS+=("")
}

stage_fail() {
  local name="$1"
  local reason="${2:-unspecified error}"
  echo "[STAGE FAIL] $name: $reason" >&2
  STAGE_NAMES+=("$name")
  STAGE_STATUSES+=("FAIL")
  STAGE_REASONS+=("$reason")
}

# ------------------------------------------------------------------------------
# Stage: net
# Probe outbound HTTP connectivity to required mirrors and endpoints
# ------------------------------------------------------------------------------
stage_net() {
  echo ""
  echo "=== Stage: net ==="
  local gh_code ctan_code conda_code
  local net_fail=0

  gh_code=$(timeout 30 curl -sI -o /dev/null -w '%{http_code}' "https://github.com" 2>&1 || echo "000")
  echo "HTTP $gh_code https://github.com"
  if [[ "$gh_code" != "200" && "$gh_code" != "301" && "$gh_code" != "302" ]]; then
    echo "WARNING: GitHub returned unexpected HTTP code: $gh_code"
    net_fail=1
  fi

  ctan_code=$(timeout 30 curl -sI -o /dev/null -w '%{http_code}' "https://mirror.ctan.org/systems/texlive/tlnet/" 2>&1 || echo "000")
  echo "HTTP $ctan_code https://mirror.ctan.org/systems/texlive/tlnet/"

  conda_code=$(timeout 30 curl -sI -o /dev/null -w '%{http_code}' "https://conda.anaconda.org/conda-forge/" 2>&1 || echo "000")
  echo "HTTP $conda_code https://conda.anaconda.org/conda-forge/"

  if [ $net_fail -ne 0 ]; then
    stage_fail "net" "github unreachable (HTTP $gh_code)"
  else
    stage_ok "net"
  fi
}

# ------------------------------------------------------------------------------
# Stage: tinytex
# Download, unpack, configure TinyTeX (TeX Live) and install LaTeX packages
# ------------------------------------------------------------------------------
stage_tinytex() {
  echo ""
  echo "=== Stage: tinytex ==="

  # Check if pdflatex already exists and works
  if [ -x "$TEXBIN/pdflatex" ] && timeout 30 "$TEXBIN/pdflatex" --version >/dev/null 2>&1; then
    echo "TinyTeX pdflatex binary already present and working. Skipping tarball download & extraction."
  else
    echo "Resolving TinyTeX-1 tarball URL..."
    local api_url="https://api.github.com/repos/rstudio/tinytex-releases/releases/latest"
    local pinned_url="https://github.com/rstudio/tinytex-releases/releases/download/v2026.09/TinyTeX-1-linux-x86_64-v2026.09.tar.xz"
    local download_url=""
    local api_json
    api_json=$(timeout 600 curl -sSfL "$api_url" 2>/dev/null || true)
    if [ -n "$api_json" ]; then
      local all_urls=()
      while IFS= read -r match_line; do
        if [ -n "$match_line" ]; then
          local u
          u=$(echo "$match_line" | sed -E 's/^"browser_download_url": *"([^"]+)"/\1/')
          all_urls+=("$u")
        fi
      done < <(echo "$api_json" | grep -oE '"browser_download_url": *"[^"]+"' || true)

      for u in "${all_urls[@]}"; do
        local bname
        bname=$(basename "$u")
        if echo "$bname" | grep -qE '^TinyTeX-1-linux-x86_64-v[0-9.]+\.tar\.xz$'; then
          download_url="$u"
          break
        fi
      done

      if [ -z "$download_url" ]; then
        for u in "${all_urls[@]}"; do
          local bname
          bname=$(basename "$u")
          if echo "$bname" | grep -qE '^TinyTeX-1-v[0-9.]+\.tar\.gz$'; then
            download_url="$u"
            break
          fi
        done
      fi
    fi

    if [ -z "$download_url" ]; then
      echo "API lookup did not match any release assets or failed; using pinned release URL."
      download_url="$pinned_url"
    fi
    echo "Selected TinyTeX URL: $download_url"

    local tarball="$DL/$(basename "$download_url")"
    if [ ! -s "$tarball" ] || ! timeout 600 tar tf "$tarball" >/dev/null 2>&1; then
      echo "Downloading $download_url to $tarball..."
      if ! timeout 600 curl -fL -o "$tarball" "$download_url"; then
        stage_fail "tinytex" "failed to download TinyTeX tarball"
        return
      fi
      if ! timeout 600 tar tf "$tarball" >/dev/null 2>&1; then
        stage_fail "tinytex" "downloaded tarball corrupted"
        return
      fi
    else
      echo "Using cached valid tarball: $tarball"
    fi

    echo "Checking xz availability..."
    local xz_bin
    xz_bin=$(command -v xz 2>/dev/null || true)
    echo "command -v xz: ${xz_bin:-not found}"
    if [[ "$tarball" == *.xz ]] && [ -z "$xz_bin" ]; then
      stage_fail "tinytex" "xz utility is required for .tar.xz archive but was not found on PATH"
      return
    fi

    echo "Extracting TinyTeX..."
    local extract_dir="$PUB/.tmp/tinytex_extract"
    rm -rf "$extract_dir"
    mkdir -p "$extract_dir"
    if ! timeout 600 tar xf "$tarball" -C "$extract_dir"; then
      stage_fail "tinytex" "failed to extract tarball"
      return
    fi

    local topdir
    topdir=$(timeout 600 tar tf "$tarball" | head -1 | cut -d/ -f1)
    if [ -z "$topdir" ] || [ ! -d "$extract_dir/$topdir" ]; then
      topdir=$(ls -A "$extract_dir" | head -1)
    fi

    echo "Moving extracted directory ($topdir) to $TEXDIR..."
    rm -rf "$TEXDIR"
    if ! mv "$extract_dir/$topdir" "$TEXDIR"; then
      stage_fail "tinytex" "failed to move $extract_dir/$topdir to $TEXDIR"
      return
    fi
    rm -rf "$extract_dir"
  fi

  # Add TinyTeX to PATH for subsequent operations in this stage
  export PATH="$TEXBIN:$PATH"

  if [ ! -x "$TEXBIN/tlmgr" ]; then
    echo "Diagnosis for missing tlmgr:"
    echo "ls $TEXDIR:"
    ls -la "$TEXDIR" 2>/dev/null || true
    echo "ls $TEXDIR/bin:"
    ls -la "$TEXDIR/bin" 2>/dev/null || true
    stage_fail "tinytex" "tlmgr binary not found at $TEXBIN/tlmgr"
    return
  fi

  echo "Setting CTAN mirror repository..."
  timeout 1200 "$TEXBIN/tlmgr" option repository https://mirror.ctan.org/systems/texlive/tlnet

  echo "Updating tlmgr self..."
  local update_out
  update_out=$(timeout 1200 "$TEXBIN/tlmgr" update --self 2>&1 || true)
  echo "$update_out"

  if echo "$update_out" | grep -qi "is older than the remote repository"; then
    echo "ERROR: Local TeX Live is older than CTAN repository (cross-year mismatch)" >&2
    stage_fail "tinytex" "local TeX Live older than CTAN (cross-year)"
    return
  fi

  echo "Installing required LaTeX packages..."
  if ! timeout 1200 "$TEXBIN/tlmgr" install "${TL_PKGS[@]}"; then
    echo "Batch installation encountered errors. Retrying each package individually..."
    local failed_pkgs=()
    local critical_failed=()
    for pkg in "${TL_PKGS[@]}"; do
      if ! timeout 120 "$TEXBIN/tlmgr" install "$pkg"; then
        echo "Failed to install package: $pkg"
        failed_pkgs+=("$pkg")
        for crit in "${TL_CRITICAL[@]}"; do
          if [ "$pkg" = "$crit" ]; then
            critical_failed+=("$pkg")
            break
          fi
        done
      fi
    done

    if [ ${#failed_pkgs[@]} -gt 0 ]; then
      echo "Non-critical package install failures: ${failed_pkgs[*]}"
    fi

    if [ ${#critical_failed[@]} -gt 0 ]; then
      stage_fail "tinytex" "critical packages failed: ${critical_failed[*]}"
      return
    fi
  fi

  echo "Verifying TeX Live binaries..."
  local pdfver bibver tlmgrver
  pdfver=$(timeout 30 "$TEXBIN/pdflatex" --version 2>&1 | head -1 || true)
  bibver=$(timeout 30 "$TEXBIN/bibtex" --version 2>&1 | head -1 || true)
  tlmgrver=$(timeout 30 "$TEXBIN/tlmgr" --version 2>&1 | head -1 || true)

  echo "pdflatex: $pdfver"
  echo "bibtex:   $bibver"
  echo "tlmgr:    $tlmgrver"

  if [ -n "$pdfver" ] && [ -n "$bibver" ]; then
    stage_ok "tinytex"
  else
    stage_fail "tinytex" "binary verification failed"
  fi
}

# ------------------------------------------------------------------------------
# Stage: pandoc
# Locate Quarto module pandoc or fallback to standalone static binary
# ------------------------------------------------------------------------------
stage_pandoc() {
  echo ""
  echo "=== Stage: pandoc ==="
  local pandoc_bin=""
  local source_type=""

  # Initialize environment modules if needed
  if ! type module >/dev/null 2>&1; then
    if [ -f /etc/profile.d/modules.sh ]; then
      source /etc/profile.d/modules.sh
    elif [ -f /usr/share/lmod/lmod/init/bash ]; then
      source /usr/share/lmod/lmod/init/bash
    fi
  fi

  if type module >/dev/null 2>&1; then
    module load quarto/1.7.32-x64 2>/dev/null || true
  fi

  if command -v quarto >/dev/null 2>&1; then
    echo "quarto version: $(quarto --version 2>/dev/null || echo 'unknown')"
    echo "quarto pandoc version: $(quarto pandoc --version 2>/dev/null | head -1 || echo 'unknown')"
    echo "EBROOTQUARTO: ${EBROOTQUARTO:-not set}"
  fi

  if [ -n "${EBROOTQUARTO:-}" ] && [ -x "$EBROOTQUARTO/bin/tools/x86_64/pandoc" ]; then
    pandoc_bin="$EBROOTQUARTO/bin/tools/x86_64/pandoc"
  elif [ -x "/mnt/weka/pkg/rhel94/AuthenticAMD-25/software/quarto/1.7.32-x64/bin/tools/x86_64/pandoc" ]; then
    pandoc_bin="/mnt/weka/pkg/rhel94/AuthenticAMD-25/software/quarto/1.7.32-x64/bin/tools/x86_64/pandoc"
  fi

  if [ -n "$pandoc_bin" ] && timeout 30 "$pandoc_bin" --version >/dev/null 2>&1; then
    ln -sfn "$pandoc_bin" "$SHIM/pandoc"
    source_type="quarto-module"
    echo "Linked Quarto pandoc ($pandoc_bin) -> $SHIM/pandoc"
  else
    echo "Quarto pandoc not found. Falling back to static standalone pandoc release..."
    local static_url="https://github.com/jgm/pandoc/releases/download/3.6.3/pandoc-3.6.3-linux-amd64.tar.gz"
    local static_tar="$DL/pandoc-3.6.3-linux-amd64.tar.gz"
    if [ ! -s "$static_tar" ] || ! timeout 600 tar tzf "$static_tar" >/dev/null 2>&1; then
      timeout 600 curl -fL -o "$static_tar" "$static_url"
    fi
    mkdir -p "$PUB/pandoc"
    timeout 600 tar xzf "$static_tar" -C "$PUB/pandoc"
    ln -sfn "$PUB/pandoc/pandoc-3.6.3/bin/pandoc" "$SHIM/pandoc"
    source_type="static"
    echo "Linked static pandoc -> $SHIM/pandoc"
  fi

  if [ -x "$SHIM/pandoc" ] && timeout 30 "$SHIM/pandoc" --version >/dev/null 2>&1; then
    local pver
    pver=$(timeout 30 "$SHIM/pandoc" --version | head -1)
    echo "Pandoc verified: $pver (source: $source_type)"
    echo "$source_type" > "$PUB/PANDOC_SOURCE.txt"
    stage_ok "pandoc"
  else
    stage_fail "pandoc" "pandoc binary verification failed"
  fi
}

# ------------------------------------------------------------------------------
# Stage: poppler
# Install standalone micromamba and create dedicated poppler environment
# ------------------------------------------------------------------------------
stage_poppler() {
  echo ""
  echo "=== Stage: poppler ==="
  echo "System pdftoppm/pdfinfo check (informational):"
  command -v pdftoppm pdfinfo || echo "None found on default PATH"

  if [ ! -x "$MM" ] || ! timeout 30 "$MM" --version >/dev/null 2>&1; then
    echo "Downloading static micromamba binary..."
    mkdir -p "$PUB/micromamba/bin"
    local mm_url="https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-linux-64"
    if ! timeout 600 curl -fL -o "$MM" "$mm_url"; then
      stage_fail "poppler" "failed to download micromamba"
      return
    fi
    chmod +x "$MM"
  fi

  if ! timeout 30 "$MM" --version >/dev/null 2>&1; then
    stage_fail "poppler" "micromamba execution test failed"
    return
  fi
  echo "Micromamba verified: $($MM --version | head -1)"

  export MAMBA_ROOT_PREFIX="$PUB/micromamba/root"
  export CONDA_PKGS_DIRS="$PUB/micromamba/pkgs"
  mkdir -p "$MAMBA_ROOT_PREFIX" "$CONDA_PKGS_DIRS"

  if [ -x "$PUB/poppler/bin/pdftoppm" ] && timeout 30 "$PUB/poppler/bin/pdftoppm" -v >/dev/null 2>&1; then
    echo "Existing Poppler environment is functional. Skipping create."
  else
    echo "Creating Poppler conda-forge environment in $PUB/poppler..."
    if [ -d "$PUB/poppler" ]; then
      rm -rf "$PUB/poppler"
    fi
    if ! timeout 1500 "$MM" create -y --no-rc -p "$PUB/poppler" -c conda-forge --override-channels poppler; then
      stage_fail "poppler" "micromamba create poppler environment failed"
      return
    fi
  fi

  # Symlink only specific rendering/inspection binaries into shim directory
  local poppler_tools=(pdftoppm pdfinfo pdftotext pdffonts pdfimages pdfseparate pdfunite)
  for tool in "${poppler_tools[@]}"; do
    if [ -f "$PUB/poppler/bin/$tool" ]; then
      ln -sfn "$PUB/poppler/bin/$tool" "$SHIM/$tool"
    fi
  done

  local ppm_ver info_ver
  ppm_ver=$(timeout 30 "$SHIM/pdftoppm" -v 2>&1 | head -1 || true)
  info_ver=$(timeout 30 "$SHIM/pdfinfo" -v 2>&1 | head -1 || true)
  echo "pdftoppm version: $ppm_ver"
  echo "pdfinfo version:   $info_ver"

  if [ -x "$SHIM/pdftoppm" ] && [ -x "$SHIM/pdfinfo" ]; then
    stage_ok "poppler"
  else
    stage_fail "poppler" "poppler binaries missing from $SHIM"
  fi
}

# ------------------------------------------------------------------------------
# Stage: versions
# Generate VERSIONS.txt with complete provenance and package revisions
# ------------------------------------------------------------------------------
stage_versions() {
  echo ""
  echo "=== Stage: versions ==="
  local vfile="$PUB/VERSIONS.txt"

  local tlmgr_full
  tlmgr_full=$(timeout 30 "$TEXBIN/tlmgr" --version 2>&1 || echo "unknown")
  local tlmgr_joined
  tlmgr_joined=$(echo "$tlmgr_full" | tr '\n' '|' | sed 's/|/ | /g' | sed 's/ | $//')
  local texlive_year
  texlive_year=$(echo "$tlmgr_full" | grep -o '20[0-9][0-9]' | head -1 || echo "unknown")

  local quarto_ver
  quarto_ver=$(quarto --version 2>/dev/null || echo "none")

  cat <<EOF > "$vfile"
date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
host: $(hostname)
job: ${PBS_JOBID:-none}
pdflatex: $(timeout 30 "$TEXBIN/pdflatex" --version 2>&1 | head -1 || echo "unknown")
bibtex: $(timeout 30 "$TEXBIN/bibtex" --version 2>&1 | head -1 || echo "unknown")
tlmgr: $tlmgr_joined
texlive_year: $texlive_year
pandoc: $(timeout 30 "$SHIM/pandoc" --version 2>&1 | head -1 || echo "unknown")
pandoc_source: $(cat "$PUB/PANDOC_SOURCE.txt" 2>/dev/null || echo "unknown")
quarto: $quarto_ver
pdftoppm: $(timeout 30 "$SHIM/pdftoppm" -v 2>&1 | head -1 || echo "unknown")
pdfinfo: $(timeout 30 "$SHIM/pdfinfo" -v 2>&1 | head -1 || echo "unknown")
micromamba: $(timeout 30 "$MM" --version 2>&1 | head -1 || echo "unknown")
EOF

  timeout 60 "$TEXBIN/tlmgr" info --only-installed --data name,revision,cat-version "${TL_PKGS[@]}" 2>/dev/null | while read -r line; do
    if [ -n "$line" ]; then
      local pname pinfo
      pname=$(echo "$line" | awk '{print $1}')
      pinfo=$(echo "$line" | cut -d' ' -f2-)
      echo "tlpkg:${pname}: ${pinfo}" >> "$vfile"
    fi
  done || true

  echo "Generated $vfile:"
  cat "$vfile"
  stage_ok "versions"
}

# ------------------------------------------------------------------------------
# Stage: envcheck
# Test sourcing env.sh from clean path and assert tools resolve under $PUB
# ------------------------------------------------------------------------------
stage_envcheck() {
  echo ""
  echo "=== Stage: envcheck ==="
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local env_file="$script_dir/env.sh"

  if [ ! -f "$env_file" ]; then
    stage_fail "envcheck" "env.sh not found at $env_file"
    return
  fi

  local check_status=0
  (
    export PATH=/usr/bin:/bin
    # shellcheck disable=SC1090
    source "$env_file"
    local tools=(pdflatex bibtex pandoc pdftoppm pdfinfo tlmgr)
    for tool in "${tools[@]}"; do
      local p
      p=$(command -v "$tool" 2>/dev/null || true)
      echo "$tool -> $p"
      if [ -z "$p" ]; then
        echo "ERROR: tool $tool not found on PATH after sourcing env.sh" >&2
        exit 1
      fi
      if [[ "$p" != /scratch/n12194778/pubtools/* ]]; then
        echo "ERROR: tool $tool resolved outside /scratch/n12194778/pubtools ($p)" >&2
        exit 1
      fi
    done
  ) || check_status=$?

  if [ $check_status -eq 0 ]; then
    stage_ok "envcheck"
  else
    stage_fail "envcheck" "tool resolution verification failed"
  fi
}

# Helper: Auto-resolve missing LaTeX package dependencies during compilation
run_pdflatex_autoresolve() {
  local target="$1"
  local basename="${target%.tex}"
  local round=0
  local max_rounds=8

  while [ $round -lt $max_rounds ]; do
    round=$((round + 1))
    local pdflatex_out
    local rc=0
    pdflatex_out=$(timeout 120 pdflatex -interaction=nonstopmode -halt-on-error "$target" 2>&1) || rc=$?
    echo "$pdflatex_out" | tail -n 15

    if [ -f "${basename}.log" ]; then
      local missing_file
      missing_file=$(grep -o "! LaTeX Error: File [\`'][^']*' not found" "${basename}.log" | head -1 | sed -E "s/! LaTeX Error: File [\`']([^']*)' not found/\1/" || true)
      if [ -n "$missing_file" ]; then
        echo "Detected missing LaTeX dependency: $missing_file (Attempt $round of $max_rounds)"
        local pkg_name
        pkg_name=$(timeout 120 tlmgr search --global --file "/$missing_file" 2>&1 | grep -v '^tlmgr:' | grep ':' | head -1 | cut -d: -f1 | tr -d '[:space:]' || true)
        if [ -n "$pkg_name" ]; then
          echo "AUTO-INSTALLED: $pkg_name (for $missing_file)"
          timeout 600 tlmgr install "$pkg_name"
          continue
        else
          echo "ERROR: Could not resolve package for $missing_file"
          return 1
        fi
      fi
    fi

    if [ $rc -eq 0 ] && [ -f "${basename}.log" ] && grep -q "Output written on" "${basename}.log"; then
      return 0
    else
      if [ -f "${basename}.log" ]; then
        echo "pdflatex failed on $target (rc=$rc). Last 40 lines of ${basename}.log:"
        tail -n 40 "${basename}.log"
      else
        echo "pdflatex failed on $target (rc=$rc) and no ${basename}.log found."
      fi
      return 1
    fi
  done
  return 1
}

# ------------------------------------------------------------------------------
# Stage: testdoc
# Compile end-to-end Markdown -> natbib -> LaTeX -> PDF -> PNG document
# ------------------------------------------------------------------------------
stage_testdoc() {
  echo ""
  echo "=== Stage: testdoc ==="

  # Recreate build scratch directory
  rm -rf "$BUILD"
  mkdir -p "$BUILD"

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck disable=SC1090
  source "$script_dir/env.sh"

  cd "$BUILD" || {
    stage_fail "testdoc" "could not cd into $BUILD"
    return
  }

  # Copy repo figure
  if [ -f "$REPO_FIG" ]; then
    cp "$REPO_FIG" "$BUILD/fig.pdf"
    echo "Copied repo figure from $REPO_FIG"
  else
    stage_fail "testdoc" "repo figure $REPO_FIG missing"
    return
  fi

  # Create test.bib
  cat << 'EOF' > "$BUILD/test.bib"
@book{knuth1984,
  author    = {Donald E. Knuth},
  title     = {The {\TeX}book},
  publisher = {Addison-Wesley},
  year      = {1984}
}

@book{lamport1994,
  author    = {Leslie Lamport},
  title     = {{\LaTeX}: A Document Preparation System},
  publisher = {Addison-Wesley},
  edition   = {2nd},
  year      = {1994}
}
EOF

  # Create test.md
  cat << 'EOF' > "$BUILD/test.md"
---
title: "Toolchain test"
author: "pubtools"
biblio-style: plainnat
natbiboptions: round
geometry: margin=1in
link-citations: true
header-includes:
  - \usepackage{newunicodechar}
  - \newunicodechar{≥}{\ensuremath{\geq}}
  - \usepackage{siunitx,threeparttable,pdflscape,placeins,enumitem,multirow,tabularx,float,footmisc,caption}
---

This paragraph validates the publication toolchain. We cite Knuth parenthetically [@knuth1984] and Lamport textually @lamport1994.
We also verify unicode character support (such as ≥ and em-dash —), inline mathematics $E=mc^2$, and raw LaTeX macros such as \SI{3.5}{\milli\second}.

| Parameter | Value | Unit |
| :--- | :--- | :--- |
| Latency | 3.5 | ms |
| Accuracy | 99.2 | % |
| Throughput | 120 | req/s |

: Evaluation benchmark summary.

![A test figure.](fig.pdf){width=55%}

\FloatBarrier

# References
EOF

  echo "Converting test.md -> test.tex via Pandoc..."
  if ! timeout 120 pandoc test.md -s --natbib --bibliography=test.bib -o test.tex; then
    stage_fail "testdoc" "pandoc conversion failed"
    return
  fi

  local cit_count
  cit_count=$(grep -c '\\citep\|\\citet' test.tex || true)
  echo "Natbib citation occurrences in test.tex: $cit_count"
  if [ "$cit_count" -lt 2 ]; then
    stage_fail "testdoc" "pandoc did not output expected natbib citation commands"
    return
  fi

  echo "Compiling test.tex with pdflatex + bibtex..."
  if ! run_pdflatex_autoresolve test.tex; then
    stage_fail "testdoc" "initial pdflatex pass failed"
    return
  fi

  if ! timeout 60 bibtex test; then
    stage_fail "testdoc" "bibtex compilation failed"
    return
  fi

  if ! run_pdflatex_autoresolve test.tex || ! run_pdflatex_autoresolve test.tex; then
    stage_fail "testdoc" "subsequent pdflatex passes failed"
    return
  fi

  # Validate test.pdf
  if [ ! -f "$BUILD/test.pdf" ]; then
    stage_fail "testdoc" "test.pdf was not generated"
    return
  fi

  local pages
  pages=$(pdfinfo test.pdf 2>/dev/null | grep -i '^Pages:' | awk '{print $2}' || true)
  echo "test.pdf page count: $pages"
  if [ "$pages" != "1" ]; then
    echo "WARNING: test.pdf has $pages pages (expected 1)"
  fi

  if grep -i "Citation .* undefined" test.log >/dev/null 2>&1; then
    echo "ERROR: Undefined citations found in test.log" >&2
    stage_fail "testdoc" "undefined citations in test.log"
    return
  fi

  if [ -f test.blg ] && grep -i "error message" test.blg >/dev/null 2>&1; then
    echo "ERROR: Error messages in test.blg" >&2
    stage_fail "testdoc" "bibtex errors in test.blg"
    return
  fi

  # Pure-LaTeX load test documents
  echo "Compiling pure-LaTeX loadtest.tex..."
  cat << 'EOF' > "$BUILD/loadtest.tex"
\documentclass{article}
\usepackage{amsmath}
\usepackage{newtxtext,newtxmath}
\usepackage{natbib,hyperref,bookmark,booktabs,longtable,array,tabularx,multirow,graphicx,xcolor,geometry,microtype,caption,float,enumitem,textcomp,newunicodechar,etoolbox,fancyvrb,upquote,parskip,footmisc,url,xurl,pdflscape,threeparttable,siunitx,placeins}
\begin{document}
Loadtest document with packages and figure.
\includegraphics[width=3cm]{fig.pdf}
\end{document}
EOF

  if ! run_pdflatex_autoresolve loadtest.tex; then
    stage_fail "testdoc" "loadtest.tex compilation failed"
    return
  fi

  echo "Compiling loadtest_ptm.tex..."
  cat << 'EOF' > "$BUILD/loadtest_ptm.tex"
\documentclass{article}
\usepackage{mathptmx}
\usepackage{amssymb}
\begin{document}
Loadtest mathptmx document.
\end{document}
EOF

  if ! run_pdflatex_autoresolve loadtest_ptm.tex; then
    stage_fail "testdoc" "loadtest_ptm.tex compilation failed"
    return
  fi

  # Render preview images
  echo "Rendering test.pdf to PNG preview images..."
  timeout 60 pdftoppm -r 60 -png test.pdf "$BUILD/test_60"
  timeout 60 pdftoppm -r 110 -png test.pdf "$BUILD/test_110"

  echo "Rendered preview files:"
  ls -la "$BUILD"/*.png
  echo "PDF info for test.pdf:"
  timeout 30 pdfinfo test.pdf

  # Contact-sheet smoke test
  echo "Generating contact sheet smoke test..."
  if ! timeout 120 "$PUBTOOLS_PY" "$script_dir/contact_sheet.py" --out "$BUILD/sheet" "$BUILD"/test_60-*.png; then
    stage_fail "testdoc" "contact_sheet.py execution failed"
    return
  fi

  echo "Contact sheet files:"
  ls -la "$BUILD"/sheet_*.png 2>/dev/null || true

  if ! compgen -G "$BUILD/sheet_*.png" >/dev/null; then
    stage_fail "testdoc" "no $BUILD/sheet_*.png was produced"
    return
  fi

  if compgen -G "$BUILD/*.png" >/dev/null; then
    stage_ok "testdoc"
  else
    stage_fail "testdoc" "png rendering failed"
  fi
}

# ------------------------------------------------------------------------------
# Main Orchestration
# ------------------------------------------------------------------------------
main() {
  stage_net
  stage_tinytex
  stage_pandoc
  stage_poppler
  stage_versions
  stage_envcheck
  stage_testdoc

  echo ""
  echo "==== SUMMARY ===="
  local any_failed=0
  for i in "${!STAGE_NAMES[@]}"; do
    local name="${STAGE_NAMES[$i]}"
    local st="${STAGE_STATUSES[$i]}"
    local rsn="${STAGE_REASONS[$i]}"
    if [ "$st" = "OK" ]; then
      echo "$name: OK"
    else
      echo "$name: FAIL: $rsn"
      any_failed=1
    fi
  done
  echo "================="

  if [ $any_failed -ne 0 ]; then
    echo "Installer finished with errors." >&2
    exit 1
  else
    echo "Installer completed successfully."
    exit 0
  fi
}

main "$@"
