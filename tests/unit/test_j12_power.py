"""Tests for scripts/analysis/j12_power.py (power of J12's D1-D4 at the test design).

Synthetic fixtures with answers known by arithmetic: a large constant effect is supported in every
simulated read, a zero-mean effect about as often as α allows, the handoff-only dev value is
Σ d·h / Σ h, and the J12 loop reproduces am1_power.simulate draw for draw.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import am1_power as am1
from scripts.analysis import j12_power as jp

TASKS = [f"s{i}_{j}" for i in range(8) for j in (1, 2, 3)]  # 8 scenarios x 3 tasks


def arm(values: dict[str, float], handoff: dict[str, bool] | None = None, seeds=(1, 2, 3)) -> dict:
    """task -> goal_pass for every seed; handoff: task -> the m11 episode's flag."""
    return {(t, s): {"goal_pass_rate": v, "tgc": 0.0, "handoff_occurred": (handoff or {}).get(t, True)}
            for t, v in values.items() for s in seeds}


def family(m11_bplus: dict, m6_bplus: dict, m11_zs: dict, m6_zs: dict, handoff=None) -> dict:
    return {"bplus_m11": arm(m11_bplus, handoff), "bplus_m6": arm(m6_bplus),
            "zs_m11": arm(m11_zs, handoff), "zs_m6": arm(m6_zs)}


def const(v: float) -> dict[str, float]:
    return {t: v for t in TASKS}


def test_specs_are_the_registered_family():
    specs = jp.power_specs()
    assert list(specs) == ["D1", "D2", "D3", "D4"]
    assert {s["family"] for s in specs.values()} == {"J12"}
    assert all(s["direction"] == "greater" and s["threshold"] == 0.0 for s in specs.values())
    assert [(s["left"], s["right"], s["handoff_only"]) for s in specs.values()] == [
        ("bplus_m11", "bplus_m6", False), ("zs_m11", "zs_m6", False),
        ("bplus_m11", "bplus_m6", True), ("zs_m11", "zs_m6", True)]


def test_the_j12_loop_is_am1_simulate_draw_for_draw():
    # Scenario means alternate, so the rates are neither 0 nor 1 and any draw drift would show.
    values = {t: (0.25 if int(t[1]) % 2 else -0.05) for t in TASKS}
    arms = family({t: 0.5 + v for t, v in values.items()}, const(0.5), const(0.6), const(0.5),
                  handoff={t: t.endswith(("_1", "_2")) for t in TASKS})
    specs = jp.power_specs()
    rows = {n: am1.paired_rows(arms[s["left"]], arms[s["right"]]) for n, s in specs.items()}
    idx = {n: am1.index_by_scenario(r) for n, r in rows.items()}
    shifts = {n: 0.0 for n in specs}
    mine = jp.j12_simulate(idx, specs, shifts, n_sims=40, n_boot=200, seed=5, n_scenarios=12)
    theirs = am1.simulate(idx, specs, shifts, n_sims=40, n_boot=200, seed=5, n_scenarios=12)
    assert mine["per_contrast"] == theirs["per_contrast"]
    assert mine["families_all_supported"] == theirs["families_all_supported"]


def test_large_effect_gives_power_near_one_everywhere():
    arms = family(const(0.9), const(0.5), const(0.8), const(0.4))
    report = jp.build_from_arms(arms, n_sims=30, n_boot=200, seed=11, n_scenarios=12, report_path=Path("/nonexistent"))
    table = report["power_table"]["at_dev_effect"]
    assert table == {"D1": 1.0, "D2": 1.0, "D3": 1.0, "D4": 1.0, "all_four_supported": 1.0,
                     "D1_and_D2_supported": 1.0}
    # Half of a constant +0.40 is a constant +0.20: still supported in every read.
    assert report["power_table"]["at_half_effect"]["all_four_supported"] == 1.0
    assert report["half_effect_shift_pp"]["D1"] == pytest.approx(20.0)
    assert report["dev_check_against_j17"]["status"] == "absent"


def test_zero_effect_gives_power_near_alpha():
    # Scenario differences alternate +0.2 / -0.2 on both receivers: the true mean is 0 everywhere.
    zero = {t: (0.7 if int(t[1]) % 2 else 0.3) for t in TASKS}
    arms = family(zero, const(0.5), zero, const(0.5))
    report = jp.build_from_arms(arms, n_sims=200, n_boot=400, seed=3, n_scenarios=20, report_path=Path("/nonexistent"))
    at_dev = report["power_at_dev_effect"]["per_contrast"]
    for name in ("D1", "D2", "D3", "D4"):
        # One-sided 2.5 % per side at α = 0.05 two-sided equivalent; allow Monte Carlo slack.
        assert at_dev[name]["excludes_on_predicted_side"] < 0.10
        assert at_dev[name]["holm_supported"] <= at_dev[name]["excludes_on_predicted_side"]
    assert report["power_table"]["at_dev_effect"]["all_four_supported"] < 0.05
    assert report["power_table"]["at_dev_effect"]["D1_and_D2_supported"] < 0.05


def test_dev_values_and_pair_counts_by_hand():
    # bplus: m11 − m6 = 0.9 − 0.6 = +0.30 where the m11 episode handed off, 0.0 − 0.6 = −0.60 where not.
    handoff = {t: t.endswith("_1") for t in TASKS}
    m11 = {t: (0.9 if handoff[t] else 0.0) for t in TASKS}
    arms = family(m11, const(0.6), const(0.75), const(0.5), handoff=handoff)
    report = jp.build_from_arms(arms, n_sims=5, n_boot=100, seed=1, n_scenarios=8, report_path=Path("/nonexistent"))
    dev = report["dev"]
    # 72 pairs (24 tasks x 3 seeds); 24 hand off (the _1 tasks).
    assert (dev["D1"]["n_pairs"], dev["D1"]["n_handoff"], dev["D1"]["n_scenarios"]) == (72, 24, 8)
    # All: (24 x 0.3 + 48 x −0.6) / 72 = (7.2 − 28.8) / 72 = −0.30.
    assert dev["D1"]["diff_pp"] == pytest.approx(-30.0)
    # Handoff-only: Σ d·h / Σ h = 24 x 0.3 / 24 = +0.30; the h = 0 pairs do not enter.
    assert dev["D3"]["diff_pp"] == pytest.approx(30.0)
    assert dev["D3"]["n_handoff"] == 24
    assert dev["D2"]["diff_pp"] == pytest.approx(25.0) and dev["D4"]["diff_pp"] == pytest.approx(25.0)


def test_dev_check_reads_the_j17_keys(tmp_path: Path):
    fake = {"handoff_only_contrasts": {rx: {"m6_to_m11": {"goal_pass": {
        "all": {"diff_pp": 10.004, "n_pairs": 171}, "handoff_only": {"diff_pp": 20.0, "n_pairs": 71}}}}
        for rx in ("bplus", "zs")}}
    path = tmp_path / "j17.json"
    path.write_text(json.dumps(fake), encoding="utf-8")
    dev = {"D1": {"diff_pp": 10.0}, "D2": {"diff_pp": 10.0}, "D3": {"diff_pp": 20.0}, "D4": {"diff_pp": 19.99}}
    check = jp.j17_check(dev, path)
    assert check["status"] == "ok"
    assert [check["rows"][d]["matches"] for d in ("D1", "D2", "D3", "D4")] == [True, True, True, False]
    assert check["all_match"] is False and check["rows"]["D3"]["j17_n_pairs"] == 71


def test_refuses_heldout_paths(tmp_path: Path):
    with pytest.raises(RuntimeError):
        jp.main(["--root", str(tmp_path), "--out", str(tmp_path / "test_normal_power.json")])
    with pytest.raises(RuntimeError):
        jp.main(["--root", str(tmp_path / "test_challenge"), "--out", str(tmp_path / "p.json")])
