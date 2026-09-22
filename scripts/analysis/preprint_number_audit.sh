#!/bin/bash
# Fabrication check for the preprint. Run it after EVERY edit to paper/*.md.
#
# Why this exists (QUAL-03): worker X46 drafted the cost table and invented 3 of its 11 TGC
# values — one was a fill-down of the row above, one was wrong by 10.52 pp — while its STATUS
# file claimed zero TODOs. The whole goal_pass column was correct, so nothing looked wrong.
# The instruction to mark uncertain values with a TODO cannot work, because a model that does
# not know it is guessing cannot comply with it. A set difference does work: every figure in
# the draft must also appear in the ledger, and each of the three invented values was absent
# from it. This check found all three in one run.
#
# A hit is not automatically a defect. A number computed as an arithmetic difference of two
# ledger values, or a digit string that is a substring of an identifier (an arXiv id, a year),
# will show up here. Read each hit; do not assume the list is either all noise or all fraud.
#
# Usage: bash scripts/analysis/preprint_number_audit.sh [preprint.md] [ledger.md]
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
P="${1:-$REPO/paper/preprint_dev_20260923.md}"
L="${2:-$REPO/docs/claims_ledger.md}"

for f in "$P" "$L"; do
  if [ ! -f "$f" ]; then echo "FATAL: missing $f" >&2; exit 2; fi
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

rc=0

echo "=== 'pp' figures in the preprint that are ABSENT from the ledger ==="
grep -oE '[0-9]+\.[0-9]+ pp' "$P" | sed 's/ pp//' | sort -u > "$TMP/pp.txt"
miss=0
while read -r n; do
  [ -z "$n" ] && continue
  if ! grep -qF -- "$n" "$L"; then echo "  MISSING FROM LEDGER: $n pp"; miss=$((miss+1)); fi
done < "$TMP/pp.txt"
echo "  total distinct pp figures: $(wc -l < "$TMP/pp.txt"), missing: $miss"
[ "$miss" -gt 0 ] && rc=1

echo "=== 4-decimal rates in the preprint that are ABSENT from the ledger ==="
grep -oE '0\.[0-9]{4}' "$P" | sort -u > "$TMP/rate.txt"
miss2=0
while read -r n; do
  [ -z "$n" ] && continue
  if ! grep -qF -- "$n" "$L"; then echo "  MISSING FROM LEDGER: $n"; miss2=$((miss2+1)); fi
done < "$TMP/rate.txt"
echo "  total distinct rates: $(wc -l < "$TMP/rate.txt"), missing: $miss2"
[ "$miss2" -gt 0 ] && rc=1

echo "=== forbidden claims (each should be 0 unless noted) ==="
echo -n "  mentions a test split: "; grep -ciE 'test_normal|test_challenge|test split|held-out test' "$P"
echo -n "  claims a breakpoint/threshold at a named depth: "; grep -ciE 'breakpoint at|threshold at m|jumps at' "$P"
echo -n "  says narrated is 'as good as'/'equal to' executed: "; grep -ciE 'as good as|equal to the executed|equivalent to the executed' "$P"
echo -n "  future-work promises: "; grep -ciE '^#+ *future work|we will run|we plan to run' "$P"
echo -n "  references F5 (expected non-zero): "; grep -c 'F5' "$P"

echo
echo "=== exit $rc (0 = every figure traced to the ledger) ==="
exit "$rc"
