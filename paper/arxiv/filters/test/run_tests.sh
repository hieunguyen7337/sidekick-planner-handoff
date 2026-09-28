#!/usr/bin/env bash
set -u

[ -n "${PBS_JOBID:-}" ] || { echo "run inside a job: timeout 900 hpc bash $0"; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
A="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ -f "$A/env.sh" ]; then
  # shellcheck source=/dev/null
  . "$A/env.sh"
fi

CASES_FILE="$SCRIPT_DIR/cases.txt"
FILTER_STRIP="$A/filters/strip_internal.lua"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

total=0
passed=0
failed=0

trim() {
  local var="$*"
  var="${var%"${var##*[![:space:]]}"}"
  printf '%s' "$var"
}

case_num=0
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  
  case_num=$((case_num + 1))
  total=$((total + 1))
  
  mode="${line%% ||| *}"
  rest="${line#* ||| }"
  input="${rest%% ||| *}"
  expected="${rest#* ||| }"
  
  keep_val=0
  if [ "$mode" = "keep" ]; then
    keep_val=1
  fi
  
  log_file="$TMP_DIR/strip_case_${case_num}.log"
  
  got="$(printf '%s\n' "$input" | KEEP_IDS="$keep_val" STRIP_LOG="$log_file" timeout 60 pandoc -f markdown -t plain --wrap=none --lua-filter "$FILTER_STRIP" 2>/dev/null)"
  got="$(trim "$got")"
  expected="$(trim "$expected")"
  
  if [ "$got" = "$expected" ]; then
    echo "PASS $case_num"
    passed=$((passed + 1))
  else
    echo "FAIL $case_num"
    echo "  input:    $input"
    echo "  expected: $expected"
    echo "  got:      $got"
    failed=$((failed + 1))
  fi
done < "$CASES_FILE"

# Header identifiers and heading code spans, checked in LaTeX output.
# header_cases.txt: <markdown heading> ||| <fixed string expected in the LaTeX output>
HEADER_CASES="$SCRIPT_DIR/header_cases.txt"
FILTER_PREP="$A/filters/latex_prep.lua"
if [ -f "$HEADER_CASES" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "$line" ] && continue
    case_num=$((case_num + 1))
    total=$((total + 1))
    input="${line%% ||| *}"
    expected="$(trim "${line#* ||| }")"
    got="$(printf '%s\n\nBody text.\n' "$input" | KEEP_IDS=0 STRIP_LOG="$TMP_DIR/hdr_${case_num}.log" timeout 60 pandoc -f markdown -t latex --wrap=none --lua-filter "$FILTER_STRIP" --lua-filter "$FILTER_PREP" 2>/dev/null | head -n 3)"
    if printf '%s' "$got" | grep -q -F -- "$expected"; then
      echo "PASS $case_num"
      passed=$((passed + 1))
    else
      echo "FAIL $case_num"
      echo "  input:    $input"
      echo "  expected: ...$expected..."
      echo "  got:      $got"
      failed=$((failed + 1))
    fi
  done < "$HEADER_CASES"
fi

echo ""
if [ "$failed" -eq 0 ]; then
  echo "ALL PASS $passed/$total"
else
  echo "FAILED $failed/$total"
fi

echo ""
echo "--- Running strip_internal.lua on preprint ---"
PAPER_PATH="$(cd "$A/.." && pwd)/preprint_dev_v2_20260924.md"
if [ ! -f "$PAPER_PATH" ]; then
  PAPER_PATH="/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/paper/preprint_dev_v2_20260924.md"
fi

PAPER_LOG="$TMP_DIR/paper_strip.log"
if [ -f "$PAPER_PATH" ]; then
  KEEP_IDS=0 STRIP_LOG="$PAPER_LOG" timeout 60 pandoc "$PAPER_PATH" -t plain --lua-filter "$FILTER_STRIP" -o /dev/null 2>/dev/null || true
  if [ -f "$PAPER_LOG" ]; then
    summary_line="$(grep '^SUMMARY' "$PAPER_LOG" || true)"
    residual_count="$(grep -c '^RESIDUAL' "$PAPER_LOG" || true)"
    echo "$summary_line"
    echo "RESIDUAL count: $residual_count"
  fi
else
  echo "Paper not found at $PAPER_PATH"
fi

if [ "$failed" -gt 0 ]; then
  exit 1
fi
