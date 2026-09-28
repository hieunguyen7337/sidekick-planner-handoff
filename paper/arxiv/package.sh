#!/usr/bin/env bash
# ==============================================================================
# package.sh - Package arXiv submission tarball and perform clean-room build check
# ==============================================================================
# Usage:
#   package.sh <outdir> <tarball>
#
# Environment variables:
#   FORCE=1        Package even if check_tex.sh reported CHECK: FAIL
#   KEEP_CLEAN=1   Keep the clean-room directories ($PAPER_BUILD/.clean.* / .clean25.*)
#   TL2025=0       Skip the second clean room on TeX Live 2025 (arXiv's default TL)
#   TL2025_BIN=..  TL2025 bin dir (default $PUBTOOLS/tl2025/texlive/bin/x86_64-linux)
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
  echo "Usage: $0 <outdir> <tarball>" >&2
  exit 2
fi

OUTDIR_ARG="$1"
TARBALL_ARG="$2"

if [ ! -d "$OUTDIR_ARG" ]; then
  echo "ERROR: Output directory does not exist: $OUTDIR_ARG" >&2
  exit 2
fi

OUTDIR="$(readlink -f "$OUTDIR_ARG")"
case "$OUTDIR" in
  /scratch/n12194778/paper_build/*|/mnt/weka/scratch/n12194778/paper_build/*)
    ;;
  *)
    echo "ERROR: <outdir> must resolve under /scratch/n12194778/paper_build/ or /mnt/weka/scratch/n12194778/paper_build/ (resolved: $OUTDIR)" >&2
    exit 2
    ;;
esac

# 4. Check mandatory build artifacts
for req_file in "main.tex" "main.bbl" "main.pdf"; do
  if [ ! -f "$OUTDIR/$req_file" ]; then
    echo "ERROR: Required artifact $OUTDIR/$req_file not found. Run build.sh first." >&2
    exit 2
  fi
done

# 5. Check verification report status
FORCE="${FORCE:-0}"
if [ -f "$OUTDIR/check_report.txt" ]; then
  last_check_line="$(grep -v '^[[:space:]]*$' "$OUTDIR/check_report.txt" | tail -n 1 || true)"
  if [[ "$last_check_line" == *"CHECK: FAIL"* ]]; then
    if [ "$FORCE" != "1" ]; then
      echo "ERROR: $OUTDIR/check_report.txt reports failure: $last_check_line" >&2
      echo "Packaging aborted. Fix the reported issues or set FORCE=1 to bypass." >&2
      exit 1
    else
      echo "WARNING: check_report.txt reported failure ($last_check_line), but FORCE=1 is set. Proceeding."
    fi
  fi
fi

# 6. Create temporary staging directory
staging_dir="$(mktemp -d "$PAPER_BUILD/.pkg.XXXXXX")"
cleanup_staging() {
  if [ -d "$staging_dir" ]; then
    rm -rf "$staging_dir"
  fi
}
trap cleanup_staging EXIT

echo "=============================================================================="
echo "Staging arXiv Submission Package"
echo "Source dir:  $OUTDIR"
echo "Staging dir: $staging_dir"
echo "=============================================================================="

# Copy core TeX and BBL files
cp -f "$OUTDIR/main.tex" "$staging_dir/main.tex"
cp -f "$OUTDIR/main.bbl" "$staging_dir/main.bbl"

# Sanity-check \pdfoutput=1 within first 5 lines
pdfoutput_found="$(head -n 5 "$staging_dir/main.tex" | grep -c '\\pdfoutput=1' || true)"
if [ "$pdfoutput_found" -eq 0 ]; then
  echo "WARN: \\pdfoutput=1 not found within the first 5 lines of main.tex"
else
  echo "Sanity check: \\pdfoutput=1 present in first 5 lines of main.tex"
fi

# Note on 00README.json
echo "INFO: 00README.json is not needed for single pdflatex top-level main.tex with .bbl (arXiv auto-detects); omitting."

# Parse and copy only referenced figures
fig_validation_failed=0
fig_list="$(perl -ne '
  while (/\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}/g) {
    my $p = $1;
    $p =~ s/^\s+|\s+$//g;
    print "$p\n" if length($p);
  }
' "$staging_dir/main.tex" | sort -u)"

if [ -n "$fig_list" ]; then
  while IFS= read -r rel_fig; do
    [ -z "$rel_fig" ] && continue

    # Check for invalid figure path conventions
    if [[ "$rel_fig" == /* ]]; then
      echo "FAIL: Absolute figure path not allowed in arXiv submission: $rel_fig" >&2
      fig_validation_failed=1
      continue
    fi
    if [[ "$rel_fig" == *".."* ]]; then
      echo "FAIL: Relative path traversing parent (..) not allowed in figure path: $rel_fig" >&2
      fig_validation_failed=1
      continue
    fi
    if [[ "$rel_fig" =~ [[:space:]] ]]; then
      echo "FAIL: Figure path contains whitespace: $rel_fig" >&2
      fig_validation_failed=1
      continue
    fi

    src_fig="$OUTDIR/$rel_fig"
    dest_fig="$staging_dir/$rel_fig"
    if [ ! -f "$src_fig" ]; then
      echo "FAIL: Figure referenced in main.tex does not exist: $src_fig" >&2
      fig_validation_failed=1
      continue
    fi

    mkdir -p "$(dirname "$dest_fig")"
    cp -f "$src_fig" "$dest_fig"
    echo "  Staged figure: $rel_fig"
  done <<< "$fig_list"
fi

if [ "$fig_validation_failed" -ne 0 ]; then
  echo "ERROR: Figure path validation failed. Cannot package submission." >&2
  exit 1
fi

# Ensure output directory for tarball exists and create tarball
mkdir -p "$(dirname "$TARBALL_ARG")"
TARBALL_DIR="$(cd "$(dirname "$TARBALL_ARG")" && pwd)"
TARBALL_BASE="$(basename "$TARBALL_ARG")"
TARBALL_ABS="$TARBALL_DIR/$TARBALL_BASE"

echo "Creating tarball: $TARBALL_ABS"
timeout 120 tar -czf "$TARBALL_ABS" -C "$staging_dir" .

echo "--- Tarball File Listing ---"
timeout 60 tar -tzvf "$TARBALL_ABS"

echo "--- Tarball Size ---"
ls -lh "$TARBALL_ABS"
size_bytes="$(wc -c < "$TARBALL_ABS" | tr -d '[:space:]')"
echo "Size in bytes: $size_bytes bytes"

# 7. Clean-Room Build Check
echo "=============================================================================="
echo "Clean-Room Compilation Verification"
echo "=============================================================================="
clean_dir="$(mktemp -d "$PAPER_BUILD/.clean.XXXXXX")"
tl25_dir=""
echo "Clean-room test directory: $clean_dir"
# Remove the clean rooms on exit (KEEP_CLEAN=1 keeps them for inspection).
cleanup_all() {
  cleanup_staging
  if [ "${KEEP_CLEAN:-0}" != "1" ]; then
    [ -n "$clean_dir" ] && [ -d "$clean_dir" ] && rm -rf "$clean_dir"
    [ -n "$tl25_dir" ] && [ -d "$tl25_dir" ] && rm -rf "$tl25_dir"
  else
    echo "KEEP_CLEAN=1: clean rooms kept: $clean_dir ${tl25_dir}"
  fi
}
trap cleanup_all EXIT

timeout 120 tar -xzf "$TARBALL_ABS" -C "$clean_dir"

cd "$clean_dir"

# Stricter than the build: fresh HOME, no TEXMFHOME, no shell escape, no writes outside
# the directory -- nothing from the build machine's user tree can leak in.
mkdir -p "$clean_dir/.home"
PDFLATEX_BIN="$(command -v pdflatex)"
clean_env=(env HOME="$clean_dir/.home" TEXMFHOME=/nonexistent openout_any=p shell_escape=f)

pass=1
while [ "$pass" -le 4 ]; do
  echo "Running clean pdflatex pass $pass..."
  timeout 300 "${clean_env[@]}" "$PDFLATEX_BIN" -no-shell-escape -interaction=nonstopmode -file-line-error main.tex > /dev/null 2>&1 || true
  if [ "$pass" -ge 2 ]; then
    if [ -f "$clean_dir/main.log" ]; then
      if grep -E 'Rerun to get|Label\(s\) may have changed|Table widths have changed' "$clean_dir/main.log" > /dev/null 2>&1; then
        if [ "$pass" -lt 4 ]; then
          pass=$((pass + 1))
          continue
        fi
      fi
    fi
    break
  fi
  pass=$((pass + 1))
done

echo "clean-room passes: $pass"

clean_fail_reasons=()

# Verify PDF existence and error log
if [ ! -f "$clean_dir/main.pdf" ]; then
  clean_fail_reasons+=("main.pdf not generated")
elif [ -f "$clean_dir/main.log" ]; then
  log_errors="$(grep -E '^! ' "$clean_dir/main.log" || true)"
  if [ -n "$log_errors" ]; then
    clean_fail_reasons+=("LaTeX '!' errors in main.log")
  fi
fi

# Verify undefined citations/references
if [ -f "$clean_dir/main.log" ]; then
  undef_hits="$(perl -ne '
    if (/(?:Citation|Reference)\s+[`\x27\x{2018}]([^\x27\x{2019}\x60]+)[\x27\x{2019}\x60]\s+on\s+page\s+[0-9]+\s+undefined/i ||
        /Package\s+natbib\s+Warning:\s+Citation\s+[`\x27\x{2018}]([^\x27\x{2019}\x60]+)[\x27\x{2019}\x60]\s+undefined/i ||
        /There were undefined references/i) {
      print "$_";
    }
  ' "$clean_dir/main.log")"
  if [ -n "$undef_hits" ]; then
    clean_fail_reasons+=("Undefined citations or references in clean log")
  fi

  missing_files="$(grep -E 'File `.*` not found|LaTeX Error: File .* not found' "$clean_dir/main.log" || true)"
  if [ -n "$missing_files" ]; then
    clean_fail_reasons+=("Missing files referenced during clean compile")
  fi

  missing_chars="$(grep -c 'Missing character' "$clean_dir/main.log" || true)"
  if [ "${missing_chars:-0}" -gt 0 ]; then
    clean_fail_reasons+=("$missing_chars 'Missing character' lines in clean log")
  fi

  # Box warnings: report, and flag a difference from the build's own log
  clean_overfull="$(grep -c '^Overfull \\[hv]box' "$clean_dir/main.log" || true)"
  build_overfull="$(grep -c '^Overfull \\[hv]box' "$OUTDIR/main.log" 2>/dev/null || true)"
  clean_underfull="$(grep -c '^Underfull \\[hv]box' "$clean_dir/main.log" || true)"
  build_underfull="$(grep -c '^Underfull \\[hv]box' "$OUTDIR/main.log" 2>/dev/null || true)"
  echo "Overfull boxes: build ${build_overfull:-?}, clean ${clean_overfull:-?}; underfull: build ${build_underfull:-?}, clean ${clean_underfull:-?}"
  if [ "${clean_overfull:-0}" != "${build_overfull:-0}" ]; then
    echo "WARN: overfull box count differs between the build and the clean room"
  fi

  if [ "$pass" -ge 4 ]; then
    rerun_hits="$(grep -E 'Rerun to get|Label\(s\) may have changed|Table widths have changed' "$clean_dir/main.log" || true)"
    if [ -n "$rerun_hits" ]; then
      clean_fail_reasons+=("Rerun requested after pass 4")
    fi
  fi
fi

# Verify page count match
orig_pages="$(pdfinfo "$OUTDIR/main.pdf" 2>/dev/null | grep -E '^Pages:' | awk '{print $2}')"
clean_pages="$(pdfinfo "$clean_dir/main.pdf" 2>/dev/null | grep -E '^Pages:' | awk '{print $2}')"

echo "Page count original: ${orig_pages:-unknown}"
echo "Page count clean-room: ${clean_pages:-unknown}"

if [ -n "$orig_pages" ] && [ -n "$clean_pages" ]; then
  if [ "$orig_pages" != "$clean_pages" ]; then
    clean_fail_reasons+=("Page count mismatch: original=$orig_pages vs clean=$clean_pages")
  fi
else
  clean_fail_reasons+=("Could not determine page counts via pdfinfo")
fi

PDFTOTEXT_BIN="$(command -v pdftotext)"
text_same() {  # text_same <a.pdf> <b.pdf> <tmpdir>
  timeout 60 "$PDFTOTEXT_BIN" -layout "$1" "$3/.a.txt" 2>/dev/null
  timeout 60 "$PDFTOTEXT_BIN" -layout "$2" "$3/.b.txt" 2>/dev/null
  cmp -s "$3/.a.txt" "$3/.b.txt"
}
if [ -f "$clean_dir/main.pdf" ]; then
  if text_same "$OUTDIR/main.pdf" "$clean_dir/main.pdf" "$clean_dir"; then
    echo "Clean-room PDF text identical to the build's."
  else
    echo "WARN: clean-room PDF text differs from the build's ($(diff "$clean_dir/.a.txt" "$clean_dir/.b.txt" | grep -c '^[<>]') differing lines)"
  fi
fi

# 8. Optional second clean room on TeX Live 2025, arXiv's default TeX Live. The build
#    toolchain is TinyTeX / TeX Live 2026, which arXiv does not offer (it offers 2025 and
#    2023), so a package or kernel change could pass here and break there.
#    TL2025=0 skips it; TL2025_BIN points at another TL2025 bin directory.
TL2025_BIN="${TL2025_BIN:-$PUBTOOLS/tl2025/texlive/bin/x86_64-linux}"
if [ "${TL2025:-1}" != "0" ] && [ -x "$TL2025_BIN/pdflatex" ]; then
  echo "=============================================================================="
  echo "TeX Live 2025 Clean-Room Compilation ($TL2025_BIN)"
  echo "=============================================================================="
  "$TL2025_BIN/pdflatex" --version 2>/dev/null | head -n 1
  tl25_dir="$(mktemp -d "$PAPER_BUILD/.clean25.XXXXXX")"
  timeout 120 tar -xzf "$TARBALL_ABS" -C "$tl25_dir"
  mkdir -p "$tl25_dir/.home"
  cd "$tl25_dir"
  for p in 1 2 3; do
    timeout 300 env PATH="$TL2025_BIN:/usr/bin:/bin" HOME="$tl25_dir/.home" TEXMFHOME=/nonexistent \
      openout_any=p shell_escape=f "$TL2025_BIN/pdflatex" -no-shell-escape -interaction=nonstopmode \
      -file-line-error main.tex > /dev/null 2>&1 || true
  done
  tl25_pages="$(pdfinfo "$tl25_dir/main.pdf" 2>/dev/null | grep -E '^Pages:' | awk '{print $2}')"
  tl25_errs="$(grep -c '^! ' "$tl25_dir/main.log" 2>/dev/null || true)"
  echo "TL2025: $(grep -m1 -E '^LaTeX2e <' "$tl25_dir/main.log" 2>/dev/null); errors ${tl25_errs:-?}; pages ${tl25_pages:-none}"
  if [ ! -f "$tl25_dir/main.pdf" ]; then
    clean_fail_reasons+=("TL2025: main.pdf not generated")
  else
    [ "${tl25_errs:-0}" -gt 0 ] && clean_fail_reasons+=("TL2025: $tl25_errs LaTeX '!' errors")
    [ "${tl25_pages:-x}" != "${orig_pages:-y}" ] && clean_fail_reasons+=("TL2025 page count ${tl25_pages:-?} != build ${orig_pages:-?}")
    if grep -q -E 'There were undefined references|Citation .* undefined' "$tl25_dir/main.log"; then
      clean_fail_reasons+=("TL2025: undefined references")
    fi
    if text_same "$OUTDIR/main.pdf" "$tl25_dir/main.pdf" "$tl25_dir"; then
      echo "TL2025 PDF text identical to the build's."
    else
      echo "WARN: TL2025 PDF text differs from the build's ($(diff "$tl25_dir/.a.txt" "$tl25_dir/.b.txt" | grep -c '^[<>]') differing lines)"
    fi
  fi
else
  echo "INFO: TeX Live 2025 clean room skipped (TL2025=${TL2025:-1}; $TL2025_BIN/pdflatex not found or disabled)"
fi

echo "=============================================================================="
if [ ${#clean_fail_reasons[@]} -eq 0 ]; then
  echo "CLEAN-ROOM: PASS (${clean_pages:-unknown} pages)"
  exit 0
else
  reasons_joined="$(IFS=', '; echo "${clean_fail_reasons[*]}")"
  echo "CLEAN-ROOM: FAIL ($reasons_joined)"
  exit 1
fi
