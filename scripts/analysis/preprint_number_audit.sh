#!/bin/bash
# Fabrication check for the preprint. Run it after EVERY edit to paper/*.md.
#
# Why this exists (QUAL-07): worker X46 drafted the cost table and invented 3 of its 11 TGC
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
# Hardened checks (R7.8, docs/plan_review_fixes_20260923.md). The two set differences compare
# unsigned magnitudes, so "+3.73" passes while the ledger says "−3.73", and "[+0.75, +12.71]"
# passes while the ledger holds those endpoints in two different intervals. Five checks follow
# the original ones, and a violation of any of them also fails the audit (exit 1):
#   signed figures  a figure printed with a sign appears in the ledger with the same sign;
#   CI tuples       an interval "[a, b]" appears in the ledger as the same ordered pair
#                   ("+" and "$" dropped, so [+0.75, +12.71] and [0.75, 12.71] are one pair);
#   wording         FORBIDDEN_WORDS used of a result, and REGISTERED_WORDS in a sentence that
#                   cites a ledger id whose status is exploratory;
#   abstract        an exploratory ledger id cited in the abstract is labelled "exploratory" in
#                   the same sentence;
#   stated counts   a count the preprint states about this audit (in a paragraph matching
#                   "audit:" or "number audit") equals this run's count; so does a stated exit code.
# Every new check reads U+2212 (−) as an ASCII minus. Figures match as printed strings: a ledger
# figure with more decimals that rounds to the printed one ("+2.0544" for "+2.05") is named in the
# hit, but does not clear it, because the ledger must carry what the paper prints. The caveat above
# holds for the new checks too.
#
# Usage: bash scripts/analysis/preprint_number_audit.sh [preprint.md] [ledger.md]
set -uo pipefail

# Wording check. Words that claim more than a paired contrast shows (R7.3, R7.5): whole words, any
# case, outside `code spans`, flagged wherever they occur. In this paper every use is a claim about a
# result. A narrower test, "the sentence also carries a figure or a ledger id", missed two such claims
# in the 2026-09-23 draft (L140 and L699, both "establishes") and spared only one benign use (L491).
FORBIDDEN_WORDS="matches indistinguishable explains establishes"
# A claim of registration: flagged in a sentence citing an exploratory ledger id, unless "not"
# directly precedes it.
REGISTERED_WORDS="registered pre-registered preregistered"

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
# Boundary-aware: the plain ERE '0\.[0-9]{4}' also fires inside longer numbers, which made the
# audit report two figures that do not exist. "arXiv:2510.04618" yielded a phantom 0.0461 and the
# cost "$0.000674" yielded a phantom 0.0006. A checker that reports figures the paper never claims
# trains the reader to ignore it, which is worse than having no checker, so require that the match
# is not preceded by a digit or dot and not followed by a digit.
grep -oP '(?<![\d.])0\.\d{4}(?!\d)' "$P" | sort -u > "$TMP/rate.txt"
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

# ---- hardened checks (R7.8) -------------------------------------------------------------------
# One awk pass over the ledger and then the preprint, both with U+2212 rewritten to "-". The ledger
# status comes from the table header at docs/claims_ledger.md:5,
#   | claim_id | claim (one sentence) | artifact path | JSON key or line | status | figure |
# read as the SECOND-TO-LAST cell, because four claim cells (NOISE-05, MECH-04, ADV-FC-02, QWEN-02)
# hold an unescaped "|" inside backticks and shift every cell counted from the left. An id is
# exploratory when that cell, with "**" removed, starts with "exploratory".
MINUS=$'\xe2\x88\x92'
LC_ALL=C sed "s/$MINUS/-/g" "$L" > "$TMP/ledger.txt"
LC_ALL=C sed "s/$MINUS/-/g" "$P" > "$TMP/paper.txt"
cat > "$TMP/hardened.awk" <<'AWK'
BEGIN {
  # A figure as printed: optional sign, optional "$", digits with optional thousands commas
  # ("-8,356"), optional decimals. The ledger is text, so "3.70" and "3.7" stay different.
  NUM = "[-+]?\\$?([0-9]{1,3}(,[0-9]{3})+|[0-9]+)(\\.[0-9]+)?"
  SIGNED = "[-+]\\$?([0-9]{1,3}(,[0-9]{3})+|[0-9]+)(\\.[0-9]+)?"
  UNSIGNED = "([0-9]{1,3}(,[0-9]{3})+|[0-9]+)(\\.[0-9]+)?"
  CI = "\\[ *" NUM " *(%|pp)? *, *" NUM " *(%|pp)? *\\]"
  WORD = "[A-Za-z0-9_][A-Za-z0-9_-]*"
  n = split(forbidden, w, " "); for (i = 1; i <= n; i++) FW[tolower(w[i])] = 1
  n = split(registered, w, " "); for (i = 1; i <= n; i++) RW[tolower(w[i])] = 1
}

function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
function canon(x) { sub(/\$/, "", x); return x }
function endpoint(x) { x = canon(x); sub(/^\+/, "", x); return x }
function decimals(x) { return index(x, ".") ? length(x) - index(x, ".") : 0 }
# x printed to k decimals, sign kept ("-2.0544", 2 -> "-2.05"); "" unless x has more than k decimals.
# Used only for the hint "ledger has -2.0544": a match still needs the printed string.
function rounded(x, k,    sign) {
  if (x ~ /,/ || decimals(x) <= k) return ""
  sign = substr(x, 1, 1) ~ /[-+]/ ? substr(x, 1, 1) : ""
  return sign sprintf("%." k "f", (sign == "" ? x : substr(x, 2)) + 0)
}

# Fills SIG_TOK/SIG_POS (NSIG_T of them) and CI_A/CI_B/CI_KEY/CI_REV/CI_TXT/CI_POS (NCI_T). A signed
# figure is not preceded by a letter, digit, "_" or ".", which drops "Qwen3-8B", "GPT-5.6" and dates.
function scan(txt,    s, base, pos, tok, pre, a, b, rest) {
  NSIG_T = 0; NCI_T = 0
  s = txt; base = 0
  while (match(s, SIGNED)) {
    pos = base + RSTART; tok = substr(s, RSTART, RLENGTH)
    base += RSTART + RLENGTH - 1; s = substr(s, RSTART + RLENGTH)
    pre = pos > 1 ? substr(txt, pos - 1, 1) : ""
    if (pre !~ /[A-Za-z0-9_.]/) { SIG_TOK[++NSIG_T] = canon(tok); SIG_POS[NSIG_T] = pos }
  }
  s = txt; base = 0
  while (match(s, CI)) {
    pos = base + RSTART; tok = substr(s, RSTART, RLENGTH)
    base += RSTART + RLENGTH - 1; s = substr(s, RSTART + RLENGTH)
    # An interval has a sign or a decimal point in it; "[3, 4]" is a citation or a count range.
    if (tok !~ /[-+.]/) continue
    match(tok, NUM); a = substr(tok, RSTART, RLENGTH); rest = substr(tok, RSTART + RLENGTH)
    match(rest, NUM); b = substr(rest, RSTART, RLENGTH)
    CI_A[++NCI_T] = endpoint(a); CI_B[NCI_T] = endpoint(b)
    CI_KEY[NCI_T] = CI_A[NCI_T] ";" CI_B[NCI_T]; CI_REV[NCI_T] = CI_B[NCI_T] ";" CI_A[NCI_T]
    CI_TXT[NCI_T] = "[" canon(a) ", " canon(b) "]"; CI_POS[NCI_T] = pos
  }
}

# Unsigned figures in a ledger line; used only to say "ledger has it unsigned".
function magnitudes(txt,    s, base, pos, tok, pre) {
  s = txt; base = 0
  while (match(s, UNSIGNED)) {
    pos = base + RSTART; tok = substr(s, RSTART, RLENGTH)
    base += RSTART + RLENGTH - 1; s = substr(s, RSTART + RLENGTH)
    pre = pos > 1 ? substr(txt, pos - 1, 1) : ""
    if (pre !~ /[A-Za-z0-9_.+-]/) LMAG[tok] = 1
  }
}

FILENAME == ARGV[1] {
  if ($0 ~ /^[ \t]*\|/) {
    n = split($0, cell, "|")
    last = trim(cell[n]) == "" ? n - 1 : n
    id = trim(cell[2]); st = cell[last - 1]; gsub(/\*/, "", st); st = tolower(trim(st))
    if (id ~ /^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+$/) STATUS[id] = st
  }
  scan($0)
  for (i = 1; i <= NSIG_T; i++) {
    LSIG[SIG_TOK[i]] = 1
    for (k = 2; k < decimals(SIG_TOK[i]); k++) if (!(rounded(SIG_TOK[i], k) in LSIG_AT)) LSIG_AT[rounded(SIG_TOK[i], k)] = SIG_TOK[i]
  }
  for (i = 1; i <= NCI_T; i++) {
    LCI[CI_KEY[i]] = 1
    for (k = 2; k < decimals(CI_A[i]) && k < decimals(CI_B[i]); k++) {
      key = rounded(CI_A[i], k) ";" rounded(CI_B[i], k)
      if (!(key in LCI_AT)) LCI_AT[key] = CI_TXT[i]
    }
  }
  magnitudes($0)
  next
}

# The preprint is read a paragraph at a time: consecutive lines joined with one space, with the
# offset where each line starts, so a hit maps back to its line. Headings, table rows and YAML
# front-matter keys are paragraphs of their own; a list item starts a new one.
function add(line, abs) {
  sub(/^[ \t]+/, "", line)
  if (PTXT == "") { NPL = 0; PABS = abs || (tolower(line) ~ /^\*\*abstract/) } else PTXT = PTXT " "
  PL_OFF[++NPL] = length(PTXT) + 1; PL_NO[NPL] = FNR
  PTXT = PTXT line
}
function lineof(pos,    k) {
  for (k = NPL; k > 1; k--) if (PL_OFF[k] <= pos) return PL_NO[k]
  return PL_NO[1]
}
function flush(    i, low) {
  if (PTXT == "") return
  scan(PTXT)
  for (i = 1; i <= NSIG_T; i++) note_sig(SIG_TOK[i], lineof(SIG_POS[i]))
  for (i = 1; i <= NCI_T; i++) note_ci(CI_KEY[i], CI_REV[i], CI_TXT[i], lineof(CI_POS[i]))
  sentences(PTXT)
  low = tolower(PTXT)
  if (low ~ /audit:|number[ _]audit/) stated(low)
  PTXT = ""; NPL = 0
}
function note_sig(tok, ln) {
  if (!(tok in SIG_LINES)) { SIG_ORDER[++NSIG] = tok; SIG_LINES[tok] = "L" ln }
  else if (SIG_LAST[tok] != ln) SIG_LINES[tok] = SIG_LINES[tok] ", L" ln
  SIG_LAST[tok] = ln
}
function note_ci(key, rev, txt, ln) {
  if (!(key in CI_LINES)) { CI_ORDER[++NCI] = key; CI_LINES[key] = "L" ln; CI_SHOW[key] = txt; CI_R[key] = rev }
  else if (CI_LAST[key] != ln) CI_LINES[key] = CI_LINES[key] ", L" ln
  CI_LAST[key] = ln
}

# A sentence ends at ".", "?" or "!" (after any closing ")", quote, "*" or "_") followed by a space
# or the end of the paragraph, except after a common abbreviation. A decimal point never ends one.
function sentences(txt,    n, i, j, c, start, w) {
  n = length(txt); start = 1
  for (i = 1; i <= n; i++) {
    c = substr(txt, i, 1)
    if (c != "." && c != "?" && c != "!") continue
    for (j = i + 1; j <= n && substr(txt, j, 1) ~ /[)"'*_\]]/; j++) ;
    if (j <= n && substr(txt, j, 1) != " ") continue
    w = i > 8 ? i - 8 : 1
    if (c == "." && substr(txt, w, i - w + 1) ~ /(^|[^A-Za-z])(e\.g|i\.e|et al|vs|cf|Fig|Eq|resp|approx)\.$/) continue
    sentence(txt, start, j - 1); start = j + 1; i = j
  }
  if (start <= n) sentence(txt, start, n)
}

function sentence(txt, a, b,    s, p, t, off, pos, tok, prev, nexp, list, has_label, regpos, regword, k) {
  s = substr(txt, a, b - a + 1)
  split("", SEXP); nexp = 0; list = ""; has_label = 0
  t = s; off = a - 1
  while (match(t, WORD)) {
    tok = substr(t, RSTART, RLENGTH); pos = off + RSTART
    off += RSTART + RLENGTH - 1; t = substr(t, RSTART + RLENGTH)
    sub(/-+$/, "", tok)
    if (tok in STATUS) {
      CITED[tok] = 1
      if (PABS) ABS_CITED[tok] = 1
      if (STATUS[tok] ~ /^exploratory/ && !(tok in SEXP)) {
        SEXP[tok] = pos; SEXP_ID[++nexp] = tok; list = list (nexp > 1 ? ", " : "") tok
        if (PABS) ABS_EXPL[tok] = 1
      }
    }
    if (tolower(tok) == "exploratory") has_label = 1
  }
  # Wording is read with `code spans` blanked to spaces of the same length, so offsets still map.
  p = s
  while (match(p, /`[^`]*`/)) p = substr(p, 1, RSTART - 1) sprintf("%*s", RLENGTH, "") substr(p, RSTART + RLENGTH)
  t = p; off = a - 1; prev = ""; regpos = 0
  while (match(t, WORD)) {
    tok = tolower(substr(t, RSTART, RLENGTH)); pos = off + RSTART
    off += RSTART + RLENGTH - 1; t = substr(t, RSTART + RLENGTH)
    sub(/-+$/, "", tok)
    if (tok in FW) OUT_W[++N_WORD] = "  FORBIDDEN WORDING: L" lineof(pos) " '" tok "'"
    if ((tok in RW) && prev != "not" && !regpos) { regpos = pos; regword = tok }
    prev = tok
  }
  if (regpos && nexp)
    OUT_R[++N_REG] = "  REGISTERED BESIDE EXPLORATORY ID: L" lineof(regpos) " '" regword "' with " list
  if (PABS && !has_label)
    for (k = 1; k <= nexp; k++)
      OUT_A[++N_ABS] = "  EXPLORATORY ID UNLABELLED IN ABSTRACT: L" lineof(SEXP[SEXP_ID[k]]) " " SEXP_ID[k]
}

# Counts stated about the audit, from the first "audit:" or "number audit" in a paragraph to its
# end. An integer counts when the words after it name one of this run's counts, or when it follows
# "exit"/"exits"; any other integer (a pair count, a depth) is not a statement about the audit.
function stated(low,    t, off, num, pos, pre, post, before, after, kind, lab) {
  match(low, /audit:|number[ _]audit/)
  t = substr(low, RSTART); off = RSTART - 1
  while (match(t, /[0-9]+/)) {
    num = substr(t, RSTART, RLENGTH); pos = off + RSTART
    off += RSTART + RLENGTH - 1; t = substr(t, RSTART + RLENGTH)
    pre = pos > 1 ? substr(low, pos - 1, 1) : ""
    post = substr(low, pos + length(num), 2)
    if (pre ~ /[a-z0-9_.,$+-]/ || post ~ /^[.,][0-9]/) continue
    before = substr(low, pos > 30 ? pos - 30 : 1, pos > 30 ? 30 : pos - 1)
    after = substr(low, pos + length(num), 60); sub(/^ +/, "", after)
    kind = ""; lab = ""
    if (match(before, /exit(s|ed)?( with)?( code| status)? *$/)) { kind = "exit"; lab = substr(before, RSTART) num }
    else {
      kind = count_kind(after)
      if (kind != "") lab = num " " LABEL
    }
    if (kind == "") continue
    ST_KIND[++NST] = kind; ST_VAL[NST] = num + 0; ST_LINE[NST] = lineof(pos); ST_TEXT[NST] = lab
  }
}
function count_kind(a,    d) {
  d = ""
  if (match(a, /^distinct +/)) { d = substr(a, 1, RLENGTH); a = substr(a, RLENGTH + 1) }
  if (match(a, /^(percentage-point|pp) (figures|values|numbers)/)) return label(d, a, "pp")
  if (match(a, /^((four|4)-decimal )?rates/)) return label(d, a, "rate")
  if (match(a, /^signed (figures|values|numbers)/)) return label(d, a, "signed")
  if (match(a, /^(ci tuples|confidence intervals|intervals)/)) return label(d, a, "ci")
  if (match(a, /^((ledger|claim) )?ids( cited)?/)) return label(d, a, "ids")
  if (match(a, /^(numbers|figures)( checked)?/)) return label(d, a, "numbers")
  if (match(a, /^violations?/)) return label(d, a, "violations")
  return ""
}
function label(d, a, kind) {
  if (substr(a, RLENGTH + 1, 1) ~ /[a-z]/) return ""
  LABEL = d substr(a, 1, RLENGTH)
  return kind
}

FILENAME == ARGV[2] {
  line = $0
  if (FNR == 1 && line ~ /^---[ \t]*$/) { in_fm = 1; next }
  if (in_fm) {
    if (line ~ /^---[ \t]*$/) { flush(); in_fm = 0; fm_abs = 0; next }
    if (line ~ /^abstract:/) {
      flush(); fm_abs = 1
      sub(/^abstract:[ \t]*[|>]?[-+]?[ \t]*/, "", line); gsub(/^"|"$/, "", line)
      if (line != "") add(line, 1)
      next
    }
    if (fm_abs && line ~ /^[ \t]*$/) { flush(); next }
    if (fm_abs && line ~ /^[ \t]/) { add(line, 1); next }
    flush(); fm_abs = 0; add(line, 0); flush(); next
  }
  if (line ~ /^[ \t]*$/) { flush(); next }
  if (line ~ /^#/) {
    flush(); md_abs = tolower(line) ~ /^#+[ \t]*abstract[ \t]*$/
    add(line, 0); flush(); next
  }
  if (line ~ /^[ \t]*\|/) { flush(); add(line, md_abs); flush(); next }
  if (line ~ /^[ \t]*([-*+]|[0-9]+\.)[ \t]/) flush()
  add(line, md_abs)
}

END {
  flush()
  # The hint after ";" says what the ledger does hold, most useful first; it never clears a hit.
  print "=== signed figures in the preprint that the ledger does not carry with the same sign ==="
  vs = 0
  for (i = 1; i <= NSIG; i++) {
    tok = SIG_ORDER[i]
    if (tok in LSIG) continue
    opp = (substr(tok, 1, 1) == "-" ? "+" : "-") substr(tok, 2)
    hint = ""
    if (tok in LSIG_AT) hint = "; ledger has " LSIG_AT[tok] " (more decimals)"
    else if (opp in LSIG) hint = "; ledger has only " opp
    else if (substr(tok, 2) in LMAG) hint = "; ledger has it unsigned"
    print "  SIGNED FIGURE MISSING FROM LEDGER: " tok " (" SIG_LINES[tok] hint ")"
    vs++
  }
  print "  total distinct signed figures: " NSIG + 0 ", violations: " vs

  print "=== CI tuples [a, b] in the preprint that are ABSENT from the ledger as that tuple ==="
  vc = 0
  for (i = 1; i <= NCI; i++) {
    key = CI_ORDER[i]
    if (key in LCI) continue
    hint = ""
    if (key in LCI_AT) hint = "; ledger has " LCI_AT[key] " (more decimals)"
    else if (CI_R[key] in LCI) hint = "; ledger has it reversed"
    print "  CI MISSING FROM LEDGER: " CI_SHOW[key] " (" CI_LINES[key] hint ")"
    vc++
  }
  print "  total distinct CI tuples: " NCI + 0 ", violations: " vc

  print "=== forbidden wording used of a result (" forbidden ") ==="
  for (i = 1; i <= N_WORD; i++) print OUT_W[i]
  print "  violations: " N_WORD + 0

  print "=== registration wording in a sentence that cites an exploratory ledger id ==="
  for (i = 1; i <= N_REG; i++) print OUT_R[i]
  print "  violations: " N_REG + 0

  print "=== exploratory ledger ids in the abstract without \"exploratory\" in their sentence ==="
  for (i = 1; i <= N_ABS; i++) print OUT_A[i]
  na = 0; for (k in ABS_CITED) na++
  ne = 0; for (k in ABS_EXPL) ne++
  print "  ledger ids cited in the abstract: " na " (exploratory: " ne "), violations: " N_ABS + 0

  ncited = 0; for (k in CITED) ncited++
  vtot = miss_pp + miss_rate + vs + vc + N_WORD + N_REG + N_ABS
  VAL["pp"] = n_pp + 0; VAL["rate"] = n_rate + 0; VAL["signed"] = NSIG + 0; VAL["ci"] = NCI + 0
  VAL["numbers"] = n_pp + n_rate + NSIG + NCI; VAL["ids"] = ncited; VAL["violations"] = vtot
  VAL["exit"] = vtot > 0 ? 1 : 0
  print "=== audit counts stated in the preprint that differ from this run ==="
  vn = 0
  for (i = 1; i <= NST; i++) {
    if (ST_VAL[i] == VAL[ST_KIND[i]]) continue
    print "  STATED " (ST_KIND[i] == "exit" ? "EXIT CODE" : "COUNT") " DIFFERS: L" ST_LINE[i] " '" ST_TEXT[i] "' (this run: " VAL[ST_KIND[i]] ")"
    vn++
  }
  print "  stated audit counts found: " NST + 0 ", violations: " vn

  print "=== this run's counts (the only audit counts the preprint may state) ==="
  print "  numbers checked: " VAL["numbers"] " (pp figures " n_pp + 0 " + four-decimal rates " n_rate + 0 " + signed figures " NSIG + 0 " + CI tuples " NCI + 0 ")"
  print "  ledger ids cited: " ncited
  print "  violations per check: pp " miss_pp + 0 ", rates " miss_rate + 0 ", signed " vs ", CI " vc ", wording " N_WORD + 0 ", registered " N_REG + 0 ", abstract " N_ABS + 0 ", stated counts " vn
  exit (vtot + vn > 0)
}
AWK
LC_ALL=C awk -v forbidden="$FORBIDDEN_WORDS" -v registered="$REGISTERED_WORDS" \
  -v n_pp="$(wc -l < "$TMP/pp.txt")" -v n_rate="$(wc -l < "$TMP/rate.txt")" \
  -v miss_pp="$miss" -v miss_rate="$miss2" \
  -f "$TMP/hardened.awk" "$TMP/ledger.txt" "$TMP/paper.txt" > "$TMP/hardened.out"
arc=$?
cat "$TMP/hardened.out"
# The counts section is the last thing the awk prints, so its absence means the checks never ran.
if [ "$arc" -gt 1 ] || ! grep -q "^=== this run's counts" "$TMP/hardened.out"; then
  echo "FATAL: the hardened checks did not complete (awk exit $arc)" >&2; exit 2
fi
[ "$arc" -eq 1 ] && rc=1

echo
echo "=== exit $rc (0 = every figure traced to the ledger) ==="
exit "$rc"
