#!/usr/bin/env python3
"""Harness for the independent guards in scripts/pbs/b1_pilot.pbs.

Not a pytest module. pyproject.toml testpaths is tests/ only, and these checks
are bash-guard behaviour that does not belong in the 413-test suite.

Each case feeds the PBS selftest a defective (or good) input and asserts the
script aborts or passes. A guard that has never been shown to fire is not a
guard.

A21: PREFLIGHT identity is completed_branch_keys + branches_to_run == 1600 on
resume, and exactly 1600 on a fresh tree. Fixtures live under this scratch
dir; nothing is written under /scratch/.../results/.

Zero planner calls. Does not qsub. Does not write under /scratch/.../results/.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
PBS = REPO / "scripts/pbs/b1_pilot.pbs"
PREREG = REPO / "docs/prereg_b1_pilot.md"
PY = Path("/scratch/n12194778/sidekick/env/bin/python")
FORBIDDEN = "/scratch/n12194778/sidekick/results/hj6_branches_train_20260917"
OUTROOTS = REPO / "campaign/workers/scratch_A20/outroots"

# Frozen §13 tokens. Compared against the PBS source, not against a live qsub.
PREREG_FLAGS = [
    "--campaign-root",
    "--split train",
    "--out-root",
    "--branch-seeds 101 102 103 104",
    "--workers 10",
    "--resume",
    "--env appworld",
    "--config",
    "--delta-band-delta 0.166",
    "--untreated-mode suppress_next",
    "--max-planner-calls-total 10000",
]

FOREIGN_NEEDLE = (
    "FATAL: out-root already holds branches that are not from this frozen sample:"
)


def make_outroot(label: str, n_done: int, n_errors: int = 0) -> Path:
    """Write a synthetic out-root. Error rows must not count as completions."""
    root = OUTROOTS / label
    root.mkdir(parents=True, exist_ok=True)
    jsonl = root / "branch_runs.jsonl"
    if n_done == 0 and n_errors == 0:
        if jsonl.exists():
            jsonl.unlink()
        return root
    lines: list[str] = []
    for i in range(n_done):
        row = {
            "campaign": "hj4_correction_train_20260917",
            "seed": i // 8,
            "task_id": f"done_{i:04d}",
            "i": 0,
            "condition": "treated" if i % 2 == 0 else "untreated",
            "branch_seed": 101 + (i % 4),
            "branch_gpr": 0.5,
        }
        lines.append(json.dumps(row, sort_keys=True))
    for j in range(n_errors):
        row = {
            "campaign": "hj4_correction_train_20260917",
            "seed": 999,
            "task_id": f"error_{j:04d}",
            "i": 0,
            "condition": "treated",
            "branch_seed": 101,
            "branch_error_type": "timeout",
        }
        lines.append(json.dumps(row, sort_keys=True))
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def run_selftest(case: str, out_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["B1_GUARD_SELFTEST"] = "1"
    env["GUARD_CASE"] = case
    env["PY"] = str(PY)
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    if out_root is not None:
        env["GUARD_OUT_ROOT"] = str(out_root)
    return subprocess.run(
        ["bash", str(PBS)],
        cwd=str(REPO),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )


def expect_fatal(case: str, needle: str, out_root: Path | None = None) -> str:
    proc = run_selftest(case, out_root=out_root)
    out = proc.stdout
    assert proc.returncode != 0, (
        f"{case}: guard did not abort (rc={proc.returncode})\n{out}"
    )
    assert "FATAL" in out, f"{case}: no FATAL in output\n{out}"
    assert needle in out, f"{case}: missing {needle!r}\n{out}"
    return out


def expect_ok(case: str, needle: str, out_root: Path | None = None) -> str:
    proc = run_selftest(case, out_root=out_root)
    out = proc.stdout
    assert proc.returncode == 0, f"{case}: unexpected abort rc={proc.returncode}\n{out}"
    assert "FATAL" not in out, f"{case}: unexpected FATAL\n{out}"
    assert needle in out, f"{case}: missing {needle!r}\n{out}"
    return out


def test_preflight_ok() -> str:
    """1. Fresh tree, branches_to_run: 1600 → passes."""
    return expect_ok(
        "preflight_ok",
        "PREFLIGHT guard: sample identity holds (completed_branch_keys + branches_to_run == 1600) and max_planner_calls_total matches prereg §13",
        out_root=make_outroot("fresh", 0),
    )


def test_preflight_6216() -> str:
    """2. Fresh tree, branches_to_run: 6216 → aborts (wrapper not used)."""
    return expect_fatal(
        "preflight_6216",
        "FATAL: PREFLIGHT branches_to_run is 6216, expected 1600 (6216 means the wrapper was not used)",
        out_root=make_outroot("fresh", 0),
    )


def test_preflight_fresh_1400() -> str:
    """3. Fresh tree, branches_to_run: 1400 → aborts. A short fresh run is not a resume."""
    return expect_fatal(
        "preflight_fresh_1400",
        "FATAL: PREFLIGHT branches_to_run is 1400, expected 1600 on a fresh out-root (a short fresh run is not a resume; 6216 means the wrapper was not used)",
        out_root=make_outroot("fresh", 0),
    )


def test_preflight_resume_ok() -> str:
    """4. Resume with 200 completed and branches_to_run: 1400 → passes.

    Fixture includes 5 error rows that completed_branch_keys must ignore.
    Counting raw lines would make 205+1400 != 1600 and fail this case.
    """
    return expect_ok(
        "preflight_resume_ok",
        "PREFLIGHT guard: sample identity holds (completed_branch_keys + branches_to_run == 1600) and max_planner_calls_total matches prereg §13",
        out_root=make_outroot("resume_200", 200, n_errors=5),
    )


def test_preflight_resume_1700() -> str:
    """5. Resume with 200 completed and branches_to_run: 1500 → aborts (1700 ≠ 1600)."""
    return expect_fatal(
        "preflight_resume_1700",
        "completed_branch_keys=200 + branches_to_run=1500 = 1700, which exceeds 1600",
        out_root=make_outroot("resume_200", 200, n_errors=5),
    )


def test_preflight_resume_foreign() -> str:
    """6. Resume where completed + to_run exceeds 1600 → specific foreign-branches message."""
    out = expect_fatal(
        "preflight_resume_foreign",
        FOREIGN_NEEDLE,
        out_root=make_outroot("resume_200", 200, n_errors=5),
    )
    assert (
        "completed_branch_keys=200 + branches_to_run=1600 = 1800, which exceeds 1600. "
        "This is not a resume of the B1 200-point sample."
    ) in out, f"preflight_resume_foreign: missing verbatim foreign body\n{out}"
    return out


def test_preflight_bad_cap() -> str:
    """7a. max_planner_calls_total ≠ 10000 → aborts on the fresh path."""
    return expect_fatal(
        "preflight_bad_cap",
        "FATAL: PREFLIGHT max_planner_calls_total is 999999, expected 10000",
        out_root=make_outroot("fresh", 0),
    )


def test_preflight_bad_cap_resume() -> str:
    """7b. max_planner_calls_total ≠ 10000 → aborts on the resume path (identity holds)."""
    return expect_fatal(
        "preflight_bad_cap_resume",
        "FATAL: PREFLIGHT max_planner_calls_total is 999999, expected 10000",
        out_root=make_outroot("resume_200", 200, n_errors=5),
    )


def test_preflight_6216_resume() -> str:
    """6216 remains fatal on the resume path (wrapper not used)."""
    return expect_fatal(
        "preflight_6216_resume",
        "FATAL: PREFLIGHT branches_to_run is 6216, expected 1600 (6216 means the wrapper was not used)",
        out_root=make_outroot("resume_200", 200, n_errors=5),
    )


def test_outroot_hj6() -> str:
    return expect_fatal(
        "outroot_hj6",
        f"FATAL: out-root is or is inside {FORBIDDEN}",
    )


def test_outroot_hj6_child() -> str:
    return expect_fatal(
        "outroot_hj6_child",
        f"FATAL: out-root is or is inside {FORBIDDEN}",
    )


def test_outroot_ok() -> str:
    return expect_ok(
        "outroot_ok",
        "out-root guard:",
    )


def test_cmd_missing_untreated() -> str:
    return expect_fatal(
        "cmd_missing_untreated",
        "FATAL: assembled command is missing --untreated-mode suppress_next",
    )


def test_cmd_schedule_live() -> str:
    return expect_fatal(
        "cmd_schedule_live",
        "FATAL: assembled command is missing --untreated-mode suppress_next",
    )


def test_cmd_ok() -> str:
    return expect_ok(
        "cmd_ok",
        "untreated-mode guard: suppress_next present on assembled command",
    )


def test_bash_n() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(PBS)],
        cwd=str(REPO),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, f"bash -n failed\n{proc.stdout}"


def test_flag_for_flag() -> list[str]:
    pbs = PBS.read_text(encoding="utf-8")
    prereg = PREREG.read_text(encoding="utf-8")
    # §13 block in the committed prereg.
    m = re.search(
        r"timeout 35100 \"\$\{PY\}\" \"\$\{REPO\}/campaign/workers/scratch_A16/run_b1_pilot.py\" \\(.*?)--max-planner-calls-total 10000",
        prereg,
        flags=re.S,
    )
    assert m is not None, "could not find §13 invocation in prereg"
    section13 = m.group(0)
    missing: list[str] = []
    for flag in PREREG_FLAGS:
        if flag not in pbs:
            missing.append(f"PBS missing {flag!r}")
        if flag not in section13 and flag not in (
            "--campaign-root",
            "--out-root",
            "--config",
        ):
            # those three appear as --campaign-root "${CAMPAIGN_ROOT}" etc in both
            pass
        if flag not in section13:
            missing.append(f"prereg §13 missing {flag!r}")
    assert "run_b1_pilot.py" in pbs
    assert "timeout" in pbs and "35100" in pbs
    assert "PYTHONPATH" in pbs and "scripts/setup" in pbs
    assert "--limit" not in pbs.split("PILOT_CMD=(")[1].split(")")[0]
    assert missing == [], missing
    return [f"ok {flag}" for flag in PREREG_FLAGS]


def test_operator_confirm_fresh() -> str:
    """OPERATOR_CONFIRM is a single clearly-marked parsed-values line."""
    out = expect_ok(
        "preflight_ok",
        "[b1] OPERATOR_CONFIRM branches_to_run=1600 max_planner_calls_total=10000 completed_branch_keys=0 completed_plus_to_run=1600",
        out_root=make_outroot("fresh", 0),
    )
    return out


def main() -> int:
    print(f"python={sys.version.replace(chr(10), ' ')}")
    print(f"pbs={PBS}")
    failures: list[str] = []
    outputs: dict[str, str] = {}
    tests = [
        ("bash_n", test_bash_n),
        ("flag_for_flag", test_flag_for_flag),
        ("preflight_ok", test_preflight_ok),
        ("preflight_6216", test_preflight_6216),
        ("preflight_fresh_1400", test_preflight_fresh_1400),
        ("preflight_resume_ok", test_preflight_resume_ok),
        ("preflight_resume_1700", test_preflight_resume_1700),
        ("preflight_resume_foreign", test_preflight_resume_foreign),
        ("preflight_bad_cap", test_preflight_bad_cap),
        ("preflight_bad_cap_resume", test_preflight_bad_cap_resume),
        ("preflight_6216_resume", test_preflight_6216_resume),
        ("operator_confirm_fresh", test_operator_confirm_fresh),
        ("outroot_hj6", test_outroot_hj6),
        ("outroot_hj6_child", test_outroot_hj6_child),
        ("outroot_ok", test_outroot_ok),
        ("cmd_missing_untreated", test_cmd_missing_untreated),
        ("cmd_schedule_live", test_cmd_schedule_live),
        ("cmd_ok", test_cmd_ok),
    ]
    for name, fn in tests:
        try:
            result = fn()
            outputs[name] = result if isinstance(result, str) else repr(result)
            print(f"PASS {name}")
            if isinstance(result, str):
                for line in result.strip().splitlines():
                    print(f"  | {line}")
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
    print(f"n_pass={len(tests) - len(failures)} n_fail={len(failures)}")
    if failures:
        print("FAILURES")
        for item in failures:
            print(item)
        return 1
    print("ALL_GUARDS_FIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
