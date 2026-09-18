"""A10 defect 2: hj1_gate must not coerce missing values to zero.

A recorded 0 is a measurement; a missing key is NOT a measurement and must
not become one. The missing count must appear in the gate's output.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "hj1_gate", REPO_ROOT / "scripts" / "setup" / "hj1_gate.py"
)
hj1_gate = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("hj1_gate", hj1_gate)
_spec.loader.exec_module(hj1_gate)


def _run(tgc=0.0, steps=10, calls=1, success=False):
    return {
        "task_id": "t1_1",
        "seed": 1,
        "success": success,
        "tgc": tgc,
        "steps": steps,
        "n_planner_calls": calls,
        "error_type": None,
    }


def test_describe_recorded_zero_is_kept_in_the_mean():
    runs = {
        ("t1_1", 1): _run(tgc=0.0),
        ("t2_1", 1): _run(tgc=1.0),
    }
    d = hj1_gate.describe(runs)
    # The recorded 0 is a real measurement: mean is (0.0 + 1.0) / 2.
    assert d["tgc_mean"] == 0.5
    assert d["tgc_missing"] == 0


def test_describe_missing_tgc_is_dropped_and_counted_not_zeroed():
    runs = {
        ("t1_1", 1): _run(tgc=1.0),
        ("t2_1", 1): {**_run(), "tgc": None},  # run crashed before scoring
        ("t3_1", 1): {k: v for k, v in _run().items() if k != "tgc"},
    }
    d = hj1_gate.describe(runs)
    # Before the A10 fix both unmeasured runs entered the mean as 0.0,
    # reporting tgc_mean 0.333 for an arm whose only measured run scored 1.0.
    assert d["tgc_mean"] == 1.0
    assert d["tgc_missing"] == 2
    assert d["n"] == 3


def test_describe_all_tgc_missing_reports_none_not_zero():
    runs = {("t1_1", 1): {k: v for k, v in _run().items() if k != "tgc"}}
    d = hj1_gate.describe(runs)
    assert d["tgc_mean"] is None
    assert d["tgc_missing"] == 1


def test_describe_steps_and_calls_follow_the_same_rule():
    runs = {
        ("t1_1", 1): _run(steps=4, calls=2),
        ("t2_1", 1): {k: v for k, v in _run().items() if k not in ("steps", "n_planner_calls")},
    }
    d = hj1_gate.describe(runs)
    assert d["steps_mean"] == 4.0
    assert d["steps_missing"] == 1
    assert d["planner_calls_total"] == 2
    assert d["planner_calls_missing"] == 1


def test_describe_all_steps_missing_is_none_not_zero():
    runs = {
        ("t1_1", 1): {
            k: v for k, v in _run().items()
            if k not in ("steps", "n_planner_calls")
        }
    }
    d = hj1_gate.describe(runs)
    assert d["steps_mean"] is None
    assert d["planner_calls_total"] is None
    assert d["steps_missing"] == 1
    assert d["planner_calls_missing"] == 1


def test_paired_diff_drops_missing_field_pairs_and_counts_them():
    base = {("t1_1", 1): _run(tgc=1.0), ("t2_1", 1): _run(tgc=0.0)}
    other = {
        ("t1_1", 1): {**_run(tgc=0.0), "tgc": None},  # missing in OTHER arm
        ("t2_1", 1): _run(tgc=1.0),
    }
    cmp = hj1_gate.paired_diff(base, other, "tgc")
    assert cmp["n_pairs"] == 1
    assert cmp["pairs_dropped_missing_field"] == 1
    # The one surviving pair: 0.0 - 1.0 = -1.0.
    assert cmp["diff_pp"] == -100.0


def test_paired_diff_recorded_zero_is_a_real_diff_not_a_drop():
    base = {("t1_1", 1): _run(tgc=1.0)}
    other = {("t1_1", 1): _run(tgc=0.0)}  # recorded 0 in the other arm
    cmp = hj1_gate.paired_diff(base, other, "tgc")
    assert cmp["n_pairs"] == 1
    assert cmp["pairs_dropped_missing_field"] == 0
    assert cmp["diff_pp"] == 100.0


def test_paired_diff_all_pairs_missing_reports_zero_pairs_and_note():
    base = {("t1_1", 1): {**_run(), "tgc": None}}
    other = {("t1_1", 1): {**_run(), "tgc": None}}
    cmp = hj1_gate.paired_diff(base, other, "tgc")
    assert cmp["n_pairs"] == 0
    assert cmp["pairs_dropped_missing_field"] == 1
    assert "note" in cmp
