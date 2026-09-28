#!/usr/bin/env bash
# ==============================================================================
# build.sh - Build arXiv LaTeX paper, compile PDF, render previews, and check
# ==============================================================================
# Usage:
#   build.sh <paper.md> <outdir> [KEEP_IDS]
#
# Environment variables:
#   KEEP_IDS=1        Keep internal ledger IDs (default: 0)
#   BIB=/path/to.bib  Custom bibliography path (default: <paperdir>/bibliography.bib)
#   ZOOM="3 7"        Render 110 DPI zooms for specified page numbers
#   NO_CHECK=1        Skip final check_tex.sh step
#   NEEDLINES_MAX=12  Tables estimated at more lines than this may split (latex_prep.lua)
#   NEEDLINES_SPLIT=8 Guard (in lines) placed before such a table
#
# Outputs besides main.pdf: abstract.txt, title.txt, authors.txt (ASCII, for the arXiv
# form), source_paper.txt (the markdown path, used by check_tex.sh for md line numbers).
# ==============================================================================

set -uo pipefail

# 1. Enforce PBS job execution (Login node safety)
if [ -z "${PBS_JOBID:-}" ]; then
  echo "ERROR: run inside a job: timeout 1500 hpc bash $0 ..." >&2
  exit 2
fi

# 2. Determine toolchain root ($A) and source environment
A="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$A/env.sh" ]; then
  # shellcheck source=/dev/null
  source "$A/env.sh"
else
  echo "ERROR: Missing environment configuration at $A/env.sh" >&2
  exit 2
fi

# 3. Validate arguments
if [ $# -lt 2 ]; then
  echo "Usage: $0 <paper.md> <outdir> [KEEP_IDS]" >&2
  exit 2
fi

PAPER_ARG="$1"
OUTDIR_ARG="$2"
KEEP_IDS_ARG="${3:-}"

if [ "$KEEP_IDS_ARG" = "KEEP_IDS" ] || [ "${KEEP_IDS:-0}" = "1" ]; then
  KEEP_IDS=1
else
  KEEP_IDS=0
fi
export KEEP_IDS

ZOOM="${ZOOM:-}"
NO_CHECK="${NO_CHECK:-0}"

# 4. Resolve and validate <outdir> under /scratch/n12194778/paper_build/
mkdir -p "$OUTDIR_ARG" || {
  echo "ERROR: Unable to create output directory: $OUTDIR_ARG" >&2
  exit 2
}
OUTDIR="$(readlink -f "$OUTDIR_ARG")"
case "$OUTDIR" in
  /scratch/n12194778/paper_build/*|/mnt/weka/scratch/n12194778/paper_build/*)
    ;;
  *)
    echo "ERROR: <outdir> must resolve under /scratch/n12194778/paper_build/ or /mnt/weka/scratch/n12194778/paper_build/ (resolved: $OUTDIR)" >&2
    exit 2
    ;;
esac

# 5. Resolve and validate <paper.md>
if [ ! -f "$PAPER_ARG" ]; then
  echo "ERROR: Input markdown file does not exist: $PAPER_ARG" >&2
  exit 2
fi
PAPER_FILE="$(readlink -f "$PAPER_ARG")"
PAPER_DIR="$(dirname "$PAPER_FILE")"
export PAPER_DIR

# Main build execution routine (all output teed to build.log)
run_build() {
  echo "=============================================================================="
  echo "arXiv Paper Build Pipeline"
  echo "Paper:   $PAPER_FILE"
  echo "Outdir:  $OUTDIR"
  echo "Job ID:  ${PBS_JOBID:-none}"
  echo "Date:    $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "=============================================================================="

  # Step 1: Clean and Prepare Output Directory
  echo "--- [1/10] Preparing output directory ---"
  rm -f "$OUTDIR"/main.* "$OUTDIR"/strip_internal.log "$OUTDIR"/filter_tests.txt "$OUTDIR"/abstract.txt "$OUTDIR"/check_report.txt
  rm -f "$OUTDIR"/title.txt "$OUTDIR"/authors.txt "$OUTDIR"/source_paper.txt
  rm -rf "$OUTDIR"/figures "$OUTDIR"/render
  # check_tex.sh maps main.tex hits back to markdown line numbers through this file
  printf '%s\n' "$PAPER_FILE" > "$OUTDIR/source_paper.txt"

  BIB_SRC="${BIB:-$PAPER_DIR/bibliography.bib}"
  if [ -f "$BIB_SRC" ]; then
    cp -f "$BIB_SRC" "$OUTDIR/bibliography.bib"
    echo "Copied bibliography from $BIB_SRC to $OUTDIR/bibliography.bib"
  else
    echo "WARNING: Bibliography file not found at $BIB_SRC"
  fi

  # Step 2: Filter Tests
  echo "--- [2/10] Running filter test suite ---"
  filter_test_rc=0
  FILTER_TEST_SCRIPT="$A/filters/test/run_tests.sh"
  if [ -f "$FILTER_TEST_SCRIPT" ]; then
    timeout 300 bash "$FILTER_TEST_SCRIPT" > "$OUTDIR/filter_tests.txt" 2>&1 || filter_test_rc=$?
    echo "Filter test script returned rc: $filter_test_rc"
    if [ -f "$OUTDIR/filter_tests.txt" ]; then
      test_line="$(grep -E '^(ALL PASS|FAILED)' "$OUTDIR/filter_tests.txt" | head -n 1 || true)"
      if [ -z "$test_line" ]; then
        test_line="$(grep -v '^[[:space:]]*$' "$OUTDIR/filter_tests.txt" | tail -n 1 || true)"
      fi
      echo "Filter tests: $test_line"
    fi
  else
    echo "WARNING: Filter test script not found at $FILTER_TEST_SCRIPT"
    echo "FILTER TESTS SKIPPED: Script not found" > "$OUTDIR/filter_tests.txt"
  fi

  # Step 3: Pandoc LaTeX Generation
  echo "--- [3/10] Running Pandoc Markdown -> LaTeX ---"
  export STRIP_LOG="$OUTDIR/strip_internal.log"
  export KEEP_IDS="$KEEP_IDS"
  export PAPER_DIR="$PAPER_DIR"
  > "$STRIP_LOG"

  cd "$OUTDIR"
  pandoc_rc=0
  timeout 120 pandoc "$PAPER_FILE" -f markdown -t latex -s --template "$A/template.tex" --natbib \
    --bibliography bibliography.bib -M biblio-style=plainnat --resource-path "$PAPER_DIR" --wrap=preserve \
    --lua-filter "$A/filters/strip_internal.lua" --lua-filter "$A/filters/latex_prep.lua" -o main.tex || pandoc_rc=$?

  echo "Pandoc returned rc: $pandoc_rc"

  # Step 4: Unicode Coverage Check
  echo "--- [4/10] Checking Unicode coverage in main.tex ---"
  unicode_rc=0
  if [ -f "$OUTDIR/main.tex" ]; then
    missing_unicode="$(perl -CSD -ne '
      BEGIN { %newunicode = (); %chars = (); }
      if (/\\newunicodechar\{([^}]+)\}/) {
        $newunicode{$1} = 1;
      }
      for my $c (/[^\x00-\x7f]/g) {
        $chars{$c} = 1;
      }
      END {
        for my $c (sort keys %chars) {
          if (!$newunicode{$c}) {
            printf "%s\tU+%04X\n", $c, ord($c);
          }
        }
      }
    ' "$OUTDIR/main.tex")"

    if [ -n "$missing_unicode" ]; then
      echo "FAIL: Unmapped non-ASCII characters without \\newunicodechar in main.tex:"
      while IFS=$'\t' read -r uchar uhex; do
        [ -z "$uchar" ] && continue
        echo "  Character: '$uchar' ($uhex)"
      done <<< "$missing_unicode"
      unicode_rc=3
    else
      echo "Unicode coverage check: PASS (all non-ASCII characters covered)"
    fi
  else
    echo "ERROR: main.tex missing, cannot check Unicode coverage"
    unicode_rc=3
  fi

  # Step 5: Figures
  echo "--- [5/10] Resolving and copying figures ---"
  figure_rc=0
  if [ -f "$OUTDIR/main.tex" ]; then
    fig_list="$(perl -ne '
      while (/\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}/g) {
        my $p = $1;
        $p =~ s/^\s+|\s+$//g;
        print "$p\n" if length($p);
      }
    ' "$OUTDIR/main.tex" | sort -u)"

    if [ -n "$fig_list" ]; then
      while IFS= read -r rel_fig; do
        [ -z "$rel_fig" ] && continue
        src_fig="$PAPER_DIR/$rel_fig"
        dest_fig="$OUTDIR/$rel_fig"
        mkdir -p "$(dirname "$dest_fig")"
        if [ -f "$src_fig" ]; then
          cp -f "$src_fig" "$dest_fig"
          echo "  Copied: $rel_fig"
        else
          echo "  ERROR: Figure source missing: $src_fig"
          figure_rc=1
        fi
      done <<< "$fig_list"
    else
      echo "No figure inclusions found in main.tex."
    fi
  else
    echo "ERROR: main.tex missing, cannot copy figures"
    figure_rc=1
  fi

  # Step 6: pdflatex and bibtex Compilation
  echo "--- [6/10] Compiling with pdflatex & bibtex ---"
  cd "$OUTDIR"
  pdflatex1_rc=0
  bibtex_rc=0
  pdflatex2_rc=0
  pdflatex3_rc=0

  echo "  Running pdflatex pass 1..."
  timeout 300 pdflatex -interaction=nonstopmode -file-line-error main.tex || pdflatex1_rc=$?
  echo "  pdflatex pass 1 rc: $pdflatex1_rc"

  echo "  Running bibtex..."
  timeout 120 bibtex main || bibtex_rc=$?
  echo "  bibtex rc: $bibtex_rc"

  post_bib_passes=0
  max_post_bib_passes=5
  last_pdflatex_rc=0

  while [ "$post_bib_passes" -lt "$max_post_bib_passes" ]; do
    post_bib_passes=$((post_bib_passes + 1))
    echo "  Running pdflatex post-bibtex pass $post_bib_passes (max $max_post_bib_passes)..."
    last_pdflatex_rc=0
    timeout 300 pdflatex -interaction=nonstopmode -file-line-error main.tex || last_pdflatex_rc=$?
    echo "  pdflatex post-bibtex pass $post_bib_passes rc: $last_pdflatex_rc"

    if [ "$last_pdflatex_rc" -ne 0 ]; then
      break
    fi

    if [ "$post_bib_passes" -lt 2 ]; then
      continue
    fi

    if [ -f "$OUTDIR/main.log" ] && grep -Eq "Rerun to get|Label\(s\) may have changed|Table widths have changed" "$OUTDIR/main.log"; then
      echo "  main.log indicates rerun required (completed post-bibtex pass $post_bib_passes)..."
      continue
    else
      echo "  Labels and references settled after $post_bib_passes post-bibtex passes."
      break
    fi
  done

  echo "  Total pdflatex passes: $((1 + post_bib_passes)) (1 pre-bibtex + $post_bib_passes post-bibtex)"

  if [ -f "$OUTDIR/main.bbl" ]; then
    bbl_nonascii="$(perl -CSD -ne 'print "$_\n" for /[^\x00-\x7f]/g' "$OUTDIR/main.bbl" | sort -u)"
    if [ -n "$bbl_nonascii" ]; then
      echo "  Non-ASCII characters in main.bbl (report only):"
      while IFS= read -r bchar; do
        [ -z "$bchar" ] && continue
        bhex="$(perl -CSD -e 'printf "U+%04X", ord($ARGV[0])' "$bchar")"
        echo "    Character: '$bchar' ($bhex)"
      done <<< "$bbl_nonascii"
    else
      echo "  main.bbl contains only ASCII characters."
    fi
  fi

  # Step 7: arXiv metadata fields (abstract, title, authors) as ASCII plain text
  # -smart keeps ' and " as typed (no curly quotes, no no-break space after "et al.");
  # meta_ascii.pl maps the remaining known characters (U+2212 minus, dashes, ...) and
  # exits 3 when anything non-ASCII is left. The 1920 budget is counted AFTER folding.
  echo "--- [7/10] Extracting arXiv metadata fields (ASCII) ---"
  abstract_rc=0
  rm -f "$OUTDIR"/abstract.txt "$OUTDIR"/title.txt "$OUTDIR"/authors.txt "$OUTDIR"/.meta_*.raw
  for field in abstract title authors; do
    STRIP_LOG=/dev/null timeout 120 pandoc "$PAPER_FILE" -f markdown-smart -t plain --wrap=none \
      --template "$A/${field}_plain.tmpl" --lua-filter "$A/filters/strip_internal.lua" \
      -o "$OUTDIR/.meta_${field}.raw" || { echo "ERROR: pandoc failed for the $field field"; abstract_rc=1; continue; }
    fold_rc=0
    perl "$A/meta_ascii.pl" "$OUTDIR/.meta_${field}.raw" "$OUTDIR/${field}.txt" "$field" || fold_rc=$?
    if [ "$fold_rc" -ne 0 ]; then
      echo "FAIL: $field.txt still has non-ASCII characters (arXiv metadata is ASCII-only); map them in meta_ascii.pl or rephrase"
      abstract_rc=3
    fi
    rm -f "$OUTDIR/.meta_${field}.raw"
  done

  if [ -f "$OUTDIR/abstract.txt" ]; then
    abs_chars="$(LC_ALL=C.UTF-8 wc -m < "$OUTDIR/abstract.txt" | tr -d '[:space:]')"
    echo "abstract chars: $abs_chars (arXiv limit 1920, counted after ASCII folding)"
    if [ "$abs_chars" -gt 1920 ]; then
      echo "WARNING: Abstract character count ($abs_chars) exceeds arXiv limit of 1920! check_tex.sh will FAIL."
    fi
  else
    echo "ERROR: Failed to create $OUTDIR/abstract.txt"
    abstract_rc=1
  fi
  echo "title.txt:   $(head -c 300 "$OUTDIR/title.txt" 2>/dev/null)"
  echo "authors.txt: $(head -c 300 "$OUTDIR/authors.txt" 2>/dev/null)"

  # Step 8: Render Previews and Contact Sheets
  echo "--- [8/10] Rendering previews and contact sheets ---"
  render_rc=0
  mkdir -p "$OUTDIR/render"

  if [ -f "$OUTDIR/main.pdf" ]; then
    echo "  Rendering 60 DPI page previews..."
    timeout 300 pdftoppm -r 60 -png "$OUTDIR/main.pdf" "$OUTDIR/render/p60" || render_rc=$?

    # Collect rendered 60 DPI page images
    p60_files=()
    while IFS= read -r -d '' pfile; do
      p60_files+=("$pfile")
    done < <(find "$OUTDIR/render" -maxdepth 1 -name 'p60-*.png' -print0 | sort -zV)

    if [ ${#p60_files[@]} -gt 0 ]; then
      echo "  Generating contact sheets (${#p60_files[@]} pages)..."
      timeout 300 "$PUBTOOLS_PY" "$A/contact_sheet.py" --per-sheet 8 --cols 4 --out "$OUTDIR/render/sheet" "${p60_files[@]}" || render_rc=$?
    else
      echo "  WARNING: No p60 preview images generated for contact sheet"
    fi

    if [ -n "$ZOOM" ]; then
      echo "  Rendering 110 DPI zooms for pages: $ZOOM..."
      for p in $ZOOM; do
        if [[ "$p" =~ ^[0-9]+$ ]]; then
          timeout 300 pdftoppm -r 110 -png -f "$p" -l "$p" "$OUTDIR/main.pdf" "$OUTDIR/render/zoom_p${p}" || render_rc=$?
        fi
      done
    fi
  else
    echo "ERROR: main.pdf missing; skipping rendering"
    render_rc=1
  fi

  # Step 9: Summary
  echo "--- [9/10] Summary ---"
  if [ -f "$OUTDIR/main.pdf" ]; then
    page_count="$(pdfinfo "$OUTDIR/main.pdf" 2>/dev/null | grep -E '^Pages:' | awk '{print $2}')"
    echo "Pages: ${page_count:-unknown}"
  else
    echo "Pages: None (main.pdf missing)"
  fi

  if [ -f "$OUTDIR/strip_internal.log" ]; then
    summary_line="$(grep -E '^SUMMARY' "$OUTDIR/strip_internal.log" || true)"
    echo "Strip Filter Summary: ${summary_line:-None}"
  fi

  echo "Step return codes:"
  echo "  pandoc:           $pandoc_rc"
  echo "  unicode check:    $unicode_rc"
  echo "  figures copy:     $figure_rc"
  echo "  pdflatex pass 1:  $pdflatex1_rc"
  echo "  bibtex:           $bibtex_rc"
  echo "  pdflatex post-bibtex ($post_bib_passes passes): $last_pdflatex_rc"
  echo "  abstract:         $abstract_rc"
  echo "  render:           $render_rc"

  echo "Contact sheets:"
  find "$OUTDIR/render" -maxdepth 1 -name 'sheet_*.png' | sort | while read -r sheet_path; do
    echo "  $sheet_path"
  done

  # Step 10: Run Quality Check
  echo "--- [10/10] Quality check ---"
  first_build_rc=0
  for rc in "$pandoc_rc" "$unicode_rc" "$figure_rc" "$pdflatex1_rc" "$bibtex_rc" "$last_pdflatex_rc" "$abstract_rc" "$render_rc"; do
    if [ "$rc" -ne 0 ]; then
      first_build_rc="$rc"
      break
    fi
  done

  if [ "$NO_CHECK" = "1" ]; then
    echo "NO_CHECK=1 set: Skipping check_tex.sh"
    return "$first_build_rc"
  fi

  check_rc=0
  timeout 900 bash "$A/check_tex.sh" "$OUTDIR" || check_rc=$?

  if [ "$first_build_rc" -eq 0 ]; then
    return "$check_rc"
  else
    return "$first_build_rc"
  fi
}

run_build 2>&1 | tee "$OUTDIR/build.log"
exit "${PIPESTATUS[0]}"
