#!/usr/bin/env bash
# ==============================================================================
# check_tex.sh - Comprehensive quality, sanity, and secrecy check for LaTeX paper
# ==============================================================================
# Usage:
#   check_tex.sh <outdir>
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
if [ $# -lt 1 ]; then
  echo "Usage: $0 <outdir>" >&2
  exit 2
fi

OUTDIR_ARG="$1"
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

run_checks() {
  echo "=============================================================================="
  echo "arXiv LaTeX & PDF Quality Verification Report"
  echo "Directory: $OUTDIR"
  echo "Job ID:    ${PBS_JOBID:-none}"
  echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "=============================================================================="

  local fail_count=0
  local warn_count=0

  # Check 1: LaTeX Compilation Errors in main.log
  echo "--- [1/8] LaTeX Engine Errors ---"
  if [ -f "$OUTDIR/main.log" ]; then
    local tex_errs
    tex_errs=$(perl -ne '
      if (/^! / || /^(\.\/)?main\.tex:[0-9]+:/) {
        my $first = $_;
        my $second = <>;
        my $third = <>;
        print "FAIL: LaTeX Error: $first";
        print "  $second" if defined $second;
        print "  $third" if defined $third;
      }
    ' "$OUTDIR/main.log")
    if [ -n "$tex_errs" ]; then
      echo "$tex_errs"
      local cnt
      cnt=$(echo "$tex_errs" | grep -c '^FAIL:' || true)
      fail_count=$((fail_count + cnt))
    else
      echo "No compilation errors found in main.log."
    fi
  else
    echo "FAIL: main.log missing, compilation did not run."
    fail_count=$((fail_count + 1))
  fi

  # Check 2: Undefined Citations & References
  echo "--- [2/8] Undefined Citations & References ---"
  if [ -f "$OUTDIR/main.log" ]; then
    # Parse undefined citations and references from main.log
    local undef_keys
    undef_keys=$(perl -ne '
      if (/(?:Citation|Reference)\s+[`\x27\x{2018}]([^\x27\x{2019}\x60]+)[\x27\x{2019}\x60]\s+on\s+page\s+[0-9]+\s+undefined/i ||
          /Package\s+natbib\s+Warning:\s+Citation\s+[`\x27\x{2018}]([^\x27\x{2019}\x60]+)[\x27\x{2019}\x60]\s+undefined/i) {
        $keys{$1} = 1;
      }
      if (/There were undefined references/i) { $undef_ref_flag = 1; }
      if (/Label\(s\) may have changed/i) { $labels_changed_flag = 1; }
      END {
        for my $k (sort keys %keys) {
          print "KEY\t$k\n";
        }
        print "FLAG\tThere were undefined references\n" if $undef_ref_flag;
        print "FLAG\tLabel(s) may have changed. Rerun LaTeX.\n" if $labels_changed_flag;
      }
    ' "$OUTDIR/main.log")

    if [ -n "$undef_keys" ]; then
      while IFS=$'\t' read -r ktype kval; do
        [ -z "$ktype" ] && continue
        if [ "$ktype" = "KEY" ]; then
          echo "FAIL: Undefined citation/reference key: $kval"
          fail_count=$((fail_count + 1))
        elif [ "$ktype" = "FLAG" ]; then
          echo "FAIL: LaTeX warning flag: $kval"
          fail_count=$((fail_count + 1))
        fi
      done <<< "$undef_keys"
    else
      echo "No undefined citation or reference warnings in main.log."
    fi
  fi

  if [ -f "$OUTDIR/main.blg" ]; then
    local blg_errs
    blg_errs=$(perl -ne '
      if (/I didn\x27t find a database entry for\s+[`\x27]([^\x27]+)[\x27]/i || /error message/i) {
        print "FAIL: BibTeX error: $_";
      }
      if (/^Warning--(.+)$/) {
        print "WARN: BibTeX warning: $1\n";
      }
    ' "$OUTDIR/main.blg")
    if [ -n "$blg_errs" ]; then
      echo "$blg_errs"
      local b_fail
      b_fail=$(echo "$blg_errs" | grep -c '^FAIL:' || true)
      local b_warn
      b_warn=$(echo "$blg_errs" | grep -c '^WARN:' || true)
      fail_count=$((fail_count + b_fail))
      warn_count=$((warn_count + b_warn))
    fi
  fi

  # Check 3: Missing Figures
  echo "--- [3/8] Figure File Integrity ---"
  local fig_fail_before=$fail_count
  if [ -f "$OUTDIR/main.log" ]; then
    local log_fig_errs
    log_fig_errs=$(perl -ne '
      if (/File\s+[`\x27]([^\x27]+)[\x27]\s+not\s+found/i || /LaTeX Error:\s+File\s+.*not\s+found/i) {
        print "FAIL: LaTeX missing file: $_";
      }
    ' "$OUTDIR/main.log")
    if [ -n "$log_fig_errs" ]; then
      echo "$log_fig_errs"
      local fcnt
      fcnt=$(echo "$log_fig_errs" | grep -c '^FAIL:' || true)
      fail_count=$((fail_count + fcnt))
    fi
  fi

  if [ -f "$OUTDIR/main.tex" ]; then
    local tex_figs
    tex_figs=$(perl -ne '
      while (/\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}/g) {
        my $p = $1;
        $p =~ s/^\s+|\s+$//g;
        print "$p\n" if length($p);
      }
    ' "$OUTDIR/main.tex" | sort -u)

    local n_figs=0
    while IFS= read -r fpath; do
      [ -z "$fpath" ] && continue
      n_figs=$((n_figs + 1))
      if [ ! -f "$OUTDIR/$fpath" ]; then
        echo "FAIL: Referenced figure file missing in outdir: $fpath"
        fail_count=$((fail_count + 1))
      fi
    done <<< "$tex_figs"
    if [ "$fail_count" -eq "$fig_fail_before" ]; then
      echo "All $n_figs referenced figure files present; no missing-file lines in main.log."
    fi
  else
    echo "FAIL: main.tex missing, figure references not checked."
    fail_count=$((fail_count + 1))
  fi

  # Check 4: Glyphs and Unicode Mapping
  echo "--- [4/8] Glyphs & Unicode Mapping ---"
  if [ -f "$OUTDIR/main.log" ]; then
    local glyph_errs
    glyph_errs=$(perl -ne '
      if (/Missing character:\s+There is no/ || /Unicode character .* not set up for use with LaTeX/ || /Package inputenc Error/) {
        print "FAIL: Glyph error: $_";
      }
    ' "$OUTDIR/main.log")
    if [ -n "$glyph_errs" ]; then
      echo "$glyph_errs"
      local gcnt
      gcnt=$(echo "$glyph_errs" | grep -c '^FAIL:' || true)
      fail_count=$((fail_count + gcnt))
    fi
  fi

  if [ -f "$OUTDIR/main.tex" ]; then
    local unmapped_chars
    unmapped_chars=$(perl -CSD -ne '
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
    ' "$OUTDIR/main.tex")
    if [ -n "$unmapped_chars" ]; then
      while IFS=$'\t' read -r uchar uhex; do
        [ -z "$uchar" ] && continue
        echo "FAIL: Non-ASCII character '$uchar' ($uhex) has no \\newunicodechar mapping in main.tex"
        fail_count=$((fail_count + 1))
      done <<< "$unmapped_chars"
    else
      echo "All non-ASCII characters in main.tex are covered by \\newunicodechar."
    fi
  fi

  # Check 5: Overfull Boxes & Floats
  echo "--- [5/8] Layout, Overfull Boxes & Floats ---"
  if [ -f "$OUTDIR/main.log" ] && [ -f "$OUTDIR/main.tex" ]; then
    perl -e '
      use strict;
      use warnings;

      binmode(STDOUT, ":encoding(UTF-8)");
      binmode(STDERR, ":encoding(UTF-8)");

      my $log_file = shift @ARGV;
      my $tex_file = shift @ARGV;

      my @tex_lines;
      if (-f $tex_file) {
        my $tfh;
        if (open $tfh, "<:encoding(UTF-8)", $tex_file) {
          @tex_lines = <$tfh>;
          close $tfh;
        } elsif (open $tfh, "<:raw", $tex_file) {
          @tex_lines = <$tfh>;
          close $tfh;
        }
      }

      open my $lfh, "<:raw", $log_file or die "Cannot open $log_file: $!";

      my $current_page = 0;
      my $total_overfull_hbox = 0;
      my $total_overfull_vbox = 0;
      my $total_float_too_large = 0;
      my @severe_warns;

      while (my $line = <$lfh>) {
        if ($line =~ /\[(\d+)[\s\]]/) {
          $current_page = $1;
        }

        if ($line =~ /Overfull \\vbox/i) {
          $total_overfull_vbox++;
        }

        if ($line =~ /Float too large/i) {
          $total_float_too_large++;
        }

        if ($line =~ /Overfull \\hbox\s+\(([0-9.]+)pt too wide\)\s+in\s+paragraph\s+at\s+lines\s+(\d+)--(\d+)/) {
          my ($pt, $lstart, $lend) = ($1, $2, $3);
          $total_overfull_hbox++;
          if ($pt > 10.0) {
            push @severe_warns, { pt => $pt, kind => "paragraph", lstart => $lstart, lend => $lend, page => $current_page + 1 };
          }
        } elsif ($line =~ /Overfull \\hbox\s+\(([0-9.]+)pt too wide\)\s+in\s+alignment\s+at\s+lines\s+(\d+)--(\d+)/) {
          my ($pt, $lstart, $lend) = ($1, $2, $3);
          $total_overfull_hbox++;
          if ($pt > 10.0) {
            push @severe_warns, { pt => $pt, kind => "alignment", lstart => $lstart, lend => $lend, page => $current_page + 1 };
          }
        } elsif ($line =~ /Overfull \\hbox\s+\(([0-9.]+)pt too wide\)\s+detected\s+at\s+line\s+(\d+)/) {
          my ($pt, $lstart) = ($1, $2);
          $total_overfull_hbox++;
          if ($pt > 10.0) {
            push @severe_warns, { pt => $pt, kind => "detected", lstart => $lstart, lend => $lstart, page => $current_page + 1 };
          }
        }
      }
      close $lfh;

      print "Total Overfull \\hbox count: $total_overfull_hbox\n";
      print "Total Overfull \\vbox count: $total_overfull_vbox\n";
      print "Total Float too large count: $total_float_too_large\n";

      for my $w (@severe_warns) {
        my $snippet = "";
        my $sline = $w->{lstart};
        my $eline = $w->{lend};
        my $max_lines = 3;
        my $cnt = 0;
        for (my $i = $sline - 1; $i < scalar(@tex_lines) && $i < $eline && $cnt < $max_lines; $i++) {
          my $l = $tex_lines[$i];
          chomp $l;
          $snippet .= ($cnt == 0 ? "" : " / ") . $l;
          $cnt++;
        }
        $snippet = substr($snippet, 0, 160);
        printf "WARN: Overfull \\hbox (%.1fpt too wide) in %s at lines %s--%s (approx. page %d): %s\n",
          $w->{pt}, $w->{kind}, $w->{lstart}, $w->{lend}, $w->{page}, $snippet;
      }

      if ($total_overfull_hbox > 0) {
        print "WARN_COUNT_HBOX $total_overfull_hbox\n";
      }
      if ($total_overfull_vbox > 0) {
        print "WARN: Found $total_overfull_vbox Overfull \\vbox instances\n";
        print "WARN_COUNT_VBOX 1\n";
      }
      if ($total_float_too_large > 0) {
        print "WARN: Found $total_float_too_large Float too large instances\n";
        print "WARN_COUNT_FLOAT 1\n";
      }
    ' "$OUTDIR/main.log" "$OUTDIR/main.tex" > "$OUTDIR/.box_report.tmp"

    local severe_w
    severe_w=$(grep -c '^WARN: Overfull \\hbox' "$OUTDIR/.box_report.tmp" || true)
    local vbox_w
    vbox_w=$(grep -c '^WARN_COUNT_VBOX' "$OUTDIR/.box_report.tmp" || true)
    local float_w
    float_w=$(grep -c '^WARN_COUNT_FLOAT' "$OUTDIR/.box_report.tmp" || true)
    warn_count=$((warn_count + severe_w + vbox_w + float_w))

    grep -v '^WARN_COUNT_' "$OUTDIR/.box_report.tmp" || true
    rm -f "$OUTDIR/.box_report.tmp"
  fi

  # Check 6: Private Strings and Residual Ledger IDs
  echo "--- [6/8] Secrecy, Private Paths & Ledger ID Check ---"
  if [ -f "$OUTDIR/main.pdf" ]; then
    timeout 60 pdftotext -layout "$OUTDIR/main.pdf" "$OUTDIR/main.txt" 2>/dev/null || true
    if [ -f "$OUTDIR/main.txt" ]; then
      # for human reading only; secrecy_scan.pl handles hyphen-split lines itself
      perl -0pe 's/-[ \t]*\n[ \t]*/-/g' "$OUTDIR/main.txt" > "$OUTDIR/main_dehyphen.txt"
    fi
  fi

  local labels_file="${PUBLIC_LABELS:-$A/public_labels.txt}"
  timeout 300 perl "$A/secrecy_scan.pl" "$OUTDIR" "$labels_file" > "$OUTDIR/.secrecy_report.tmp"
  local sec_rc=$?
  if [ "$sec_rc" -ne 0 ]; then
    echo "FAIL: secrecy_scan.pl exited $sec_rc"
    fail_count=$((fail_count + 1))
  fi

  local sec_fails sec_warns
  sec_fails=$(grep -a '^TOTAL_SECRECY_FAILS' "$OUTDIR/.secrecy_report.tmp" | awk '{print $2}')
  sec_warns=$(grep -a '^TOTAL_SECRECY_WARNS' "$OUTDIR/.secrecy_report.tmp" | awk '{print $2}')
  if [ -n "$sec_fails" ] && [ "$sec_fails" -gt 0 ]; then
    fail_count=$((fail_count + sec_fails))
  fi
  if [ -n "$sec_warns" ] && [ "$sec_warns" -gt 0 ]; then
    warn_count=$((warn_count + sec_warns))
  fi
  grep -a -v -E '^TOTAL_SECRECY_(FAILS|WARNS)' "$OUTDIR/.secrecy_report.tmp" || true
  rm -f "$OUTDIR/.secrecy_report.tmp"

  # Check 7: Filter Tests Result
  echo "--- [7/8] Filter Test Suite Result ---"
  if [ -f "$OUTDIR/filter_tests.txt" ]; then
    local pass_line
    pass_line=$(grep -E '^ALL PASS' "$OUTDIR/filter_tests.txt" | head -1 || true)
    local has_failed
    has_failed=$(grep -E '^FAILED' "$OUTDIR/filter_tests.txt" | head -1 || true)
    if [ -n "$pass_line" ] && [ -z "$has_failed" ]; then
      echo "Filter tests: PASS ($pass_line)"
    else
      if [ -n "$has_failed" ]; then
        echo "FAIL: Filter test failure detected: $has_failed"
      else
        local last_test_line
        last_test_line=$(grep -v '^[[:space:]]*$' "$OUTDIR/filter_tests.txt" | tail -n 1 || true)
        echo "FAIL: Filter tests did not pass (no 'ALL PASS' found). Last output line: $last_test_line"
      fi
      fail_count=$((fail_count + 1))
    fi
  else
    echo "FAIL: filter_tests.txt not found in outdir."
    fail_count=$((fail_count + 1))
  fi

  # Check 8: Document Information & Submission Summary
  echo "--- [8/8] Document Information & Submission Comments ---"
  local pdf_pages="0"
  if [ -f "$OUTDIR/main.pdf" ]; then
    pdf_pages=$(pdfinfo "$OUTDIR/main.pdf" 2>/dev/null | grep -E '^Pages:' | awk '{print $2}')
    pdf_pages="${pdf_pages:-0}"
  fi

  local fig_count="0"
  local tbl_count="0"
  if [ -f "$OUTDIR/main.tex" ]; then
    fig_count=$(grep -c '\\begin{figure}' "$OUTDIR/main.tex" || true)
    tbl_count=$(grep -c '\\begin{longtable}' "$OUTDIR/main.tex" || true)
  fi

  # arXiv metadata fields (help/prep.html: "Our metadata fields only accept ASCII input";
  # "abstracts longer than 1920 characters will not be accepted"; "Anonymous submissions
  # are not accepted").
  local abs_chars="0"
  if [ -f "$OUTDIR/abstract.txt" ]; then
    abs_chars=$(LC_ALL=C.UTF-8 wc -m < "$OUTDIR/abstract.txt" | tr -d '[:space:]')
    if [ "$abs_chars" -gt 1920 ]; then
      echo "FAIL: Abstract length ($abs_chars chars) exceeds the arXiv limit of 1920; cut at least $((abs_chars - 1920)) characters"
      fail_count=$((fail_count + 1))
    fi
  else
    echo "FAIL: abstract.txt missing (build.sh step 7)"
    fail_count=$((fail_count + 1))
  fi
  local field
  for field in abstract title authors; do
    if [ ! -f "$OUTDIR/$field.txt" ]; then
      echo "FAIL: $field.txt missing (build.sh step 7)"
      fail_count=$((fail_count + 1))
      continue
    fi
    local nonascii
    nonascii=$(perl -CSD -ne 'while (/(.{0,20})([^\x00-\x7f])(.{0,20})/g) { printf "U+%04X in ...%s[%s]%s...\n", ord($2), $1, $2, $3 }' "$OUTDIR/$field.txt")
    if [ -n "$nonascii" ]; then
      echo "FAIL: $field.txt has non-ASCII characters (arXiv metadata is ASCII-only):"
      echo "$nonascii" | sed 's/^/    /'
      fail_count=$((fail_count + 1))
    fi
    if [ ! -s "$OUTDIR/$field.txt" ] || ! grep -q '[^[:space:]]' "$OUTDIR/$field.txt"; then
      echo "FAIL: $field.txt is empty"
      fail_count=$((fail_count + 1))
    fi
  done
  if [ -f "$OUTDIR/title.txt" ]; then
    echo "arXiv Title:   $(head -c 400 "$OUTDIR/title.txt")"
    if ! grep -q '[a-z]' "$OUTDIR/title.txt"; then
      echo "FAIL: title is all uppercase (arXiv: \"Do not use all uppercase letters\")"
      fail_count=$((fail_count + 1))
    fi
  fi
  if [ -f "$OUTDIR/authors.txt" ]; then
    echo "arXiv Authors: $(head -c 400 "$OUTDIR/authors.txt")"
    if grep -q -i -E '(^|[^a-z])(group|team|lab|consortium|collaboration|anonymous|et al)([^a-z]|$)' "$OUTDIR/authors.txt"; then
      echo "WARN: the author field names a group, not people; arXiv refuses anonymous submissions and wants \"Firstname Lastname\" (a named collaboration must also list every author in the PDF)"
      warn_count=$((warn_count + 1))
    fi
  fi
  if [ -f "$OUTDIR/main.pdf" ]; then
    local pdf_author
    pdf_author=$(pdfinfo "$OUTDIR/main.pdf" 2>/dev/null | sed -n 's/^Author:[[:space:]]*//p')
    echo "PDF Author metadata: ${pdf_author:-<empty>}"
    if [ -z "$pdf_author" ]; then
      echo "FAIL: PDF Author metadata is empty (template.tex pdfauthor)"
      fail_count=$((fail_count + 1))
    fi
  fi

  # Bibliography as printed (main.bbl)
  if [ -f "$OUTDIR/main.bbl" ]; then
    local bbl_bad bbl_q
    bbl_bad=$(grep -n -i -E 'not stated|unknown author|anonymous|\bTODO\b|\bXXX\b' "$OUTDIR/main.bbl" || true)
    if [ -n "$bbl_bad" ]; then
      echo "FAIL: placeholder author/title text in the printed bibliography (fix the .bib entry):"
      echo "$bbl_bad" | cut -c1-200 | sed 's/^/    main.bbl:/'
      fail_count=$((fail_count + $(echo "$bbl_bad" | grep -c .)))
    fi
    bbl_q=$(grep -n -E '[?!] [a-z]' "$OUTDIR/main.bbl" || true)
    if [ -n "$bbl_q" ]; then
      echo "WARN: a title word after '?' or '!' is lowercased by the bibliography style (brace it in the .bib, e.g. {A} Critical Survey):"
      echo "$bbl_q" | cut -c1-160 | sed 's/^/    main.bbl:/'
      warn_count=$((warn_count + 1))
    fi
  fi

  if [ -f "$OUTDIR/strip_internal.log" ]; then
    local s_line
    s_line=$(grep -E '^SUMMARY' "$OUTDIR/strip_internal.log" || true)
    echo "Strip filter summary: ${s_line:-none}"
    local res_count
    res_count=$(grep -c '^RESIDUAL' "$OUTDIR/strip_internal.log" || true)
    echo "Residual ledger references count: $res_count"
  fi

  echo "Page count:   $pdf_pages"
  echo "Figure count: $fig_count"
  echo "Table count:  $tbl_count"
  echo "Abstract:     $abs_chars characters"
  echo "arXiv Comments: ${pdf_pages} pages, ${fig_count} figures"

  echo "=============================================================================="
  if [ "$fail_count" -eq 0 ]; then
    if [ "$warn_count" -gt 0 ]; then
      echo "CHECK: PASS (0 fails, $warn_count warnings)"
    else
      echo "CHECK: PASS"
    fi
    return 0
  else
    echo "CHECK: FAIL ($fail_count fails, $warn_count warnings)"
    return 1
  fi
}

run_checks 2>&1 | tee "$OUTDIR/check_report.txt"
exit "${PIPESTATUS[0]}"
