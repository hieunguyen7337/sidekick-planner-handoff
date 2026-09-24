"""scripts/analysis/preprint_number_audit.sh on synthetic preprint and ledger files (R7.8).

Each hardened check gets a passing and a failing fixture. The fixture preprint is five lines of YAML
front matter (the abstract is line 4), a blank line, a heading and a blank line, so its body starts at
line 9; every expected line number below is counted from that layout by hand. The script is
grep/awk only and reads nothing but the two files it is given.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
AUDIT = REPO / "scripts" / "analysis" / "preprint_number_audit.sh"
MINUS = "−"
HEADER = ("| claim_id | claim (one sentence) | artifact path | JSON key or line | status | figure |\n"
          "|---|---|---|---|---|---|\n")
CLEAN = ("violations per check: pp 0, rates 0, signed 0, CI 0, wording 0, registered 0, abstract 0, "
         "stated counts 0")


def _ledger(tmp_path: Path, *rows: tuple[str, str, str]) -> Path:
    """rows are (claim_id, claim, status); the claim cell carries the figures."""
    path = tmp_path / "ledger.md"
    body = "".join(f"| {cid} | {claim} | `r.json` | `k` | {status} | fig |\n" for cid, claim, status in rows)
    path.write_text("# Claims ledger\n\n" + HEADER + body, encoding="utf-8")
    return path


def _paper(tmp_path: Path, body: str, abstract: str = "We study prefixes.") -> Path:
    path = tmp_path / "paper.md"
    path.write_text(f'---\ntitle: "T"\nabstract: |\n  {abstract}\n---\n\n## Results\n\n{body}\n',
                    encoding="utf-8")
    return path


def run_audit(paper: Path, ledger: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["timeout", "60", "bash", str(AUDIT), str(paper), str(ledger)],
                          text=True, capture_output=True)


def _hits(proc: subprocess.CompletedProcess[str], prefix: str) -> list[str]:
    return [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith(prefix)]


def _has(proc: subprocess.CompletedProcess[str], line: str) -> bool:
    return line in [x.strip() for x in proc.stdout.splitlines()]


# ---- the interface the original checks already had ------------------------------------------------

def test_missing_file_is_fatal(tmp_path):
    proc = run_audit(tmp_path / "absent.md", _ledger(tmp_path))
    assert proc.returncode == 2
    assert "FATAL: missing" in proc.stderr


def test_clean_paper_keeps_original_sections_and_exits_0(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", "gain +3.73 pp", "exploratory"))
    proc = run_audit(_paper(tmp_path, "The gain is +3.73 pp (exploratory; UF-01)."), ledger)
    assert proc.returncode == 0, proc.stdout
    assert _has(proc, "total distinct pp figures: 1, missing: 0")
    assert _has(proc, "total distinct rates: 0, missing: 0")
    assert _has(proc, "=== forbidden claims (each should be 0 unless noted) ===")
    assert proc.stdout.rstrip().endswith("=== exit 0 (0 = every figure traced to the ledger) ===")
    # 1 pp figure (3.73) + 0 rates + 1 signed figure (+3.73) + 0 intervals; one id, UF-01.
    assert _has(proc, "numbers checked: 2 (pp figures 1 + four-decimal rates 0 + signed figures 1 + CI tuples 0)")
    assert _has(proc, "ledger ids cited: 1")
    assert _has(proc, CLEAN)


def test_unsourced_pp_figure_still_fails_the_original_check(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", "gain 3.73 pp", "exploratory"))
    proc = run_audit(_paper(tmp_path, "The gain is 9.99 pp."), ledger)
    assert proc.returncode == 1
    assert _hits(proc, "MISSING FROM LEDGER") == ["MISSING FROM LEDGER: 9.99 pp"]


# ---- 1. signed figures ------------------------------------------------------------------------------

def test_signed_figures_pass_with_either_minus(tmp_path):
    # U+2212 in the paper against "-" in the ledger, and the other way round.
    ledger = _ledger(tmp_path, ("UF-01", "gain +3.73 pp", "exploratory"),
                     ("UF-02", "loss -0.94 pp", "exploratory"),
                     ("UF-03", f"loss {MINUS}1.20 pp", "exploratory"))
    proc = run_audit(_paper(tmp_path, f"Gains are +3.73 pp, {MINUS}0.94 pp and -1.20 pp."), ledger)
    assert proc.returncode == 0, proc.stdout
    assert _has(proc, "total distinct signed figures: 3, violations: 0")


def test_signed_figure_with_the_wrong_sign_fails(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", "gain +3.73 pp", "exploratory"),
                     ("UF-02", "replay +2.0544 pp", "exploratory"))
    body = f"Advice loses {MINUS}3.73 pp.\nReplay adds +2.05 pp."
    proc = run_audit(_paper(tmp_path, body), ledger)
    # The unsigned check is blind to both: "3.73" and "2.05" are substrings of the ledger.
    assert _has(proc, "total distinct pp figures: 2, missing: 0")
    # 2.0544 printed to 2 decimals is 2.05: a hint only; the ledger must carry the printed figure.
    assert _hits(proc, "SIGNED FIGURE") == [
        "SIGNED FIGURE MISSING FROM LEDGER: -3.73 (L9; ledger has only +3.73)",
        "SIGNED FIGURE MISSING FROM LEDGER: +2.05 (L10; ledger has +2.0544 (more decimals))",
    ]
    assert _has(proc, "total distinct signed figures: 2, violations: 2")
    assert proc.returncode == 1


# ---- 2. CI tuples -----------------------------------------------------------------------------------

def test_ci_tuples_pass_as_the_same_ordered_pair(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", "gap +6.13 pp, 95% CI [+0.75, +12.71]", "exploratory"),
                     ("UF-02", f"advice CI [{MINUS}0.06, +8.24]", "exploratory"))
    body = (f"The gap is +6.13 pp ([+0.75, +12.71]); advice sits at [{MINUS}0.06, +8.24] and a citation "
            "reads [3, 4].\nUnsigned, the first reads [0.75, 12.71].")
    proc = run_audit(_paper(tmp_path, body), ledger)
    assert proc.returncode == 0, proc.stdout
    # [+0.75, +12.71] and [0.75, 12.71] are one pair; [3, 4] has no sign or decimal point.
    assert _has(proc, "total distinct CI tuples: 2, violations: 0")


def test_ci_endpoints_from_different_intervals_fail(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", f"CI [{MINUS}0.06, +1.00]", "exploratory"),
                     ("UF-02", f"CI [{MINUS}2.00, +8.24]", "exploratory"))
    body = f"Advice sits at [{MINUS}0.06, +8.24].\nReversed, it is [+1.00, {MINUS}0.06]."
    proc = run_audit(_paper(tmp_path, body), ledger)
    # Every endpoint appears in the ledger with its sign, so only the tuple check sees the problem.
    assert _has(proc, "total distinct signed figures: 3, violations: 0")
    assert _hits(proc, "CI MISSING") == [
        "CI MISSING FROM LEDGER: [-0.06, +8.24] (L9)",
        "CI MISSING FROM LEDGER: [+1.00, -0.06] (L10; ledger has it reversed)",
    ]
    assert _has(proc, "total distinct CI tuples: 2, violations: 2")
    assert proc.returncode == 1


# ---- 3a. forbidden wording ---------------------------------------------------------------------------

def test_hedged_wording_and_code_spans_pass(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", "gap +1.55 pp", "exploratory"))
    body = ("Live takeover is not distinguishable from replay at a matched trigger (+1.55 pp).\n"
            "The column `matches` counts pairs.")
    proc = run_audit(_paper(tmp_path, body), ledger)
    assert proc.returncode == 0, proc.stdout
    assert _hits(proc, "FORBIDDEN WORDING") == []


def test_forbidden_wording_is_flagged_with_its_line(tmp_path):
    ledger = _ledger(tmp_path, ("UF-01", "gap +1.55 pp", "exploratory"))
    body = ("Live takeover matches oracle replay (+1.55 pp).\n"
            "Appendix B explains why. The replay is statistically\n"
            "indistinguishable from takeover.")
    proc = run_audit(_paper(tmp_path, body), ledger)
    assert _hits(proc, "FORBIDDEN WORDING") == [
        "FORBIDDEN WORDING: L9 'matches'",
        "FORBIDDEN WORDING: L10 'explains'",
        "FORBIDDEN WORDING: L11 'indistinguishable'",
    ]
    assert proc.returncode == 1


# ---- 3b. registration wording beside an exploratory id ---------------------------------------------

def _status_ledger(tmp_path: Path) -> Path:
    # QWEN-02's claim holds an unescaped "|", as four real rows do: status must be read from the right.
    return _ledger(tmp_path, ("UF-01", "gap +1.55 pp", "exploratory"),
                   ("DEC-01", "decomposition", "**registered (C1 decomposition, dev)**"),
                   ("QWEN-02", "counts `a|b` pairs", "exploratory (F5), limiting"))


def test_registered_beside_registered_id_or_negated_passes(tmp_path):
    body = "UF-01 is exploratory and not pre-registered.\nThe registered decomposition DEC-01 holds."
    proc = run_audit(_paper(tmp_path, body), _status_ledger(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert _hits(proc, "REGISTERED BESIDE") == []
    assert _has(proc, "ledger ids cited: 2")


def test_registered_beside_exploratory_id_fails(tmp_path):
    body = "The pre-registered contrast UF-01 gains +1.55 pp.\nQWEN-02 was registered in advance."
    proc = run_audit(_paper(tmp_path, body), _status_ledger(tmp_path))
    assert _hits(proc, "REGISTERED BESIDE") == [
        "REGISTERED BESIDE EXPLORATORY ID: L9 'pre-registered' with UF-01",
        "REGISTERED BESIDE EXPLORATORY ID: L10 'registered' with QWEN-02",
    ]
    assert proc.returncode == 1


# ---- 4. exploratory labels in the abstract ---------------------------------------------------------

def test_abstract_labels_exploratory_ids(tmp_path):
    abstract = "Takeover helps by +1.55 pp (exploratory; UF-01). The decomposition DEC-01 is registered."
    proc = run_audit(_paper(tmp_path, "UF-01 again.", abstract=abstract), _status_ledger(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert _has(proc, "ledger ids cited in the abstract: 2 (exploratory: 1), violations: 0")


def test_unlabelled_exploratory_id_in_abstract_fails(tmp_path):
    # The label is in the NEXT sentence, and the body's own UF-01 is not in the abstract.
    abstract = "Takeover helps by +1.55 pp (UF-01). It is exploratory."
    proc = run_audit(_paper(tmp_path, "UF-01 again.", abstract=abstract), _status_ledger(tmp_path))
    assert _hits(proc, "EXPLORATORY ID") == ["EXPLORATORY ID UNLABELLED IN ABSTRACT: L4 UF-01"]
    assert _has(proc, "ledger ids cited in the abstract: 1 (exploratory: 1), violations: 1")
    assert proc.returncode == 1


def test_unlabelled_exploratory_id_under_a_markdown_abstract_heading_fails(tmp_path):
    paper = tmp_path / "md.md"
    paper.write_text("# Title\n\n## Abstract\n\nTakeover helps (UF-01).\n\n## 1. Intro\n\nUF-01 again.\n",
                     encoding="utf-8")
    proc = run_audit(paper, _status_ledger(tmp_path))
    assert _hits(proc, "EXPLORATORY ID") == ["EXPLORATORY ID UNLABELLED IN ABSTRACT: L5 UF-01"]
    assert proc.returncode == 1


# ---- 5. stated counts --------------------------------------------------------------------------------

def test_stated_counts_that_match_this_run_pass(tmp_path):
    # This run: pp 1 (1.55), rates 0, signed 1 (+1.55), CI 0, numbers 1 + 0 + 1 + 0 = 2, ids 1, violations 0.
    body = ("Takeover gains +1.55 pp (exploratory; UF-01).\n\n"
            "Number audit: 1 distinct percentage-point figures, 0 four-decimal rates, 1 signed figures, "
            "0 CI tuples, 2 numbers checked, 1 ledger ids cited, 0 violations; it exits 0.")
    proc = run_audit(_paper(tmp_path, body), _status_ledger(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert _has(proc, "stated audit counts found: 8, violations: 0")
    assert _has(proc, CLEAN)


def test_stale_stated_counts_fail(tmp_path):
    # One wording violation ("matches"), so this run exits 1, not the 0 the paper states. The
    # statement wraps across lines 11-12, as it does in the real preprint.
    body = ("Takeover matches replay at +1.55 pp (exploratory; UF-01).\n\n"
            "`scripts/analysis/preprint_number_audit.sh` exits 0 on this draft over\n"
            "5 distinct percentage-point figures and 3 ledger ids.")
    proc = run_audit(_paper(tmp_path, body), _status_ledger(tmp_path))
    assert _hits(proc, "STATED") == [
        "STATED EXIT CODE DIFFERS: L11 'exits 0' (this run: 1)",
        "STATED COUNT DIFFERS: L12 '5 distinct percentage-point figures' (this run: 1)",
        "STATED COUNT DIFFERS: L12 '3 ledger ids' (this run: 1)",
    ]
    assert _has(proc, "stated audit counts found: 3, violations: 3")
    assert _has(proc, "violations per check: pp 0, rates 0, signed 0, CI 0, wording 1, registered 0, "
                      "abstract 0, stated counts 3")
    assert proc.returncode == 1


# ---- the real preprint -------------------------------------------------------------------------------

def test_default_invocation_runs_every_check_on_the_real_preprint():
    if not (REPO / "paper" / "preprint_dev_20260923.md").is_file():
        pytest.skip("no preprint in this checkout")
    proc = subprocess.run(["timeout", "60", "bash", str(AUDIT)], text=True, capture_output=True)
    assert proc.returncode in (0, 1), proc.stderr
    assert "=== this run's counts (the only audit counts the preprint may state) ===" in proc.stdout
    assert len(_hits(proc, "violations per check:")) == 1
