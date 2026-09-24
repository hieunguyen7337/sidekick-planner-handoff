"""Tests for scripts/analysis/j11_power.py (power of the J11 registration at the test design).

Fixtures are synthetic with answers known by arithmetic: constant differences on the predicted side
must give a registered reading in every simulated read, a gate at exactly zero must withhold every
reading, and the P27 episodes must arrive only through lp_report's loader.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import am1_power as ap
from scripts.analysis import j11_power as jp
from scripts.analysis import lp_report as lp

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = [f"sc{i:02d}" for i in range(19)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2, 3)]
# gate C - E = +50; L1 = +25; L2 = -22; L3 = +22; L4 = +3 (< +7); L5 = +20.
DESIGN = {"E": 0.25, "C": 0.75, "T": 0.75, "A": 0.5, "A1": 0.5, "M_bplus_6": 0.5, "M_bplus_11": 0.72,
          "M_zs_6": 0.4, "M_zs_11": 0.6}


def rows_for(d: float, n_scen: int = 6) -> list[dict]:
    return [{"task": f"s{i}_{t}", "seed": s, "scenario": f"s{i}", "d": d, "h": 0.0}
            for i in range(n_scen) for t in (1, 2, 3) for s in (1, 2)]


def indices_for(values: dict[str, float]) -> dict:
    return {name: ap.index_by_scenario(rows_for(d)) for name, d in values.items()}


ALL_ON_SIDE = {"gate": 0.10, "L1": 0.10, "L2": -0.10, "L3": 0.10, "L4": -0.10, "L5": 0.10}


def test_specs_are_lp_reports_gate_and_contrasts():
    assert list(jp.SPECS) == ["gate", "L1", "L2", "L3", "L4", "L5"]
    assert {k: (s["left"], s["right"], s["direction"], s["threshold"]) for k, s in jp.SPECS.items()} == {
        "gate": ("C", "E", "greater", 0.0), "L1": ("T", "A", "two-sided", 0.0),
        "L2": ("A1", "M_bplus_11", "less", 0.0), "L3": ("M_bplus_11", "M_bplus_6", "greater", 0.0),
        "L4": ("C", "M_bplus_11", "less", 0.07), "L5": ("M_zs_11", "M_zs_6", "greater", 0.0)}


def test_analyse_read_applies_holm_and_the_registered_rules_by_hand():
    stats = {"gate": {"point": 0.05},
             "L1": {"point": 0.10, "lo": 0.02, "hi": 0.18, "p": 0.01},
             "L2": {"point": -0.10, "lo": -0.18, "hi": -0.02, "p": 0.04},
             "L3": {"point": 0.10, "lo": 0.02, "hi": 0.18, "p": 0.03},
             "L4": {"point": 0.00, "lo": -0.05, "hi": 0.05, "p": 0.005},
             "L5": {"point": 0.10, "lo": 0.02, "hi": 0.18, "p": 0.02}}
    read = jp.analyse_read(stats)
    # Holm by hand: .005 x 5, .01 x 4, .02 x 3, .03 x 2, .04 x 1, each raised to the running max.
    assert read["p_holm"] == pytest.approx({"L1": 0.04, "L2": 0.06, "L3": 0.06, "L4": 0.025, "L5": 0.06})
    assert read["gate_passes"] is True
    assert read["readings"] == {"L1": "replicates", "L2": "not_supported", "L3": "not_supported",
                                "L4": "supported", "L5": "not_supported"}
    assert jp.analyse_read(dict(stats, gate={"point": 0.0}))["gate_passes"] is False
    assert jp.analyse_read(dict(stats, L1={"point": -0.1, "lo": -0.18, "hi": -0.02, "p": 0.001}))["readings"]["L1"] == "reversed"


def test_constant_effects_on_the_predicted_side_are_always_registered():
    res = jp.simulate(indices_for(ALL_ON_SIDE), {k: 0.0 for k in ALL_ON_SIDE}, n_sims=20, n_boot=200,
                      seed=1, n_scenarios=10)
    assert res["gate_passes"] == 1.0
    assert {c: v["registered"] for c, v in res["L"].items()} == {c: 1.0 for c in lp.L_IDS}
    assert res["joint"] == {"gate_and_L1_replicates": 1.0, "gate_and_all_five_positive": 1.0}
    assert res["L1_readings_ignoring_gate"]["replicates"] == 1.0


def test_a_gate_at_zero_withholds_every_reading():
    res = jp.simulate(indices_for(dict(ALL_ON_SIDE, gate=0.0)), {k: 0.0 for k in ALL_ON_SIDE}, n_sims=10,
                      n_boot=100, seed=2, n_scenarios=10)
    assert res["gate_passes"] == 0.0
    assert {c: v["positive_under_holm"] for c, v in res["L"].items()} == {c: 1.0 for c in lp.L_IDS}
    assert {c: v["registered"] for c, v in res["L"].items()} == {c: 0.0 for c in lp.L_IDS}


def test_shifting_by_the_whole_effect_leaves_nothing_supported():
    res = jp.simulate(indices_for(ALL_ON_SIDE), dict(ALL_ON_SIDE, L4=-0.10 - 0.07), n_sims=10, n_boot=100,
                      seed=3, n_scenarios=10)
    # Every shifted difference sits exactly on its null: gate point 0, intervals [t, t].
    assert res["gate_passes"] == 0.0
    assert res["L1_readings_ignoring_gate"]["fails_to_replicate"] == 1.0
    assert {c: v["positive_under_holm"] for c, v in res["L"].items()} == {c: 0.0 for c in lp.L_IDS}


def test_half_shifts_by_hand():
    half = jp.half_shifts({"gate": 0.05, "L1": 0.08, "L2": -0.10, "L3": 0.12, "L4": -0.04, "L5": 0.06})
    assert half == pytest.approx({"gate": 0.025, "L1": 0.04, "L2": -0.05, "L3": 0.06, "L4": -0.055,
                                  "L5": 0.03})


def _write_tree(root: Path) -> dict[str, str]:
    camps = {c: b["campaign"] for c, b in lp.resolve_campaigns(("P27",))["P27"].items() if c in jp.ARM_CODES}
    camps["E"] = lp.REFERENCE_CAMPAIGNS["E"]
    for code, name in camps.items():
        for seed in (1, 2):
            for task in TASKS:
                crashed = code == "M_bplus_11" and (task, seed) in {("sc03_1", 1), ("sc07_2", 2)}
                ep = root / name / "arm" / str(seed) / task
                ep.mkdir(parents=True, exist_ok=True)
                row = {"task_id": task, "seed": seed, "goal_pass_rate": DESIGN[code], "tgc": DESIGN[code],
                       "error_type": "crash" if crashed else None}
                (ep / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return camps


def test_p27_pairs_come_only_through_lp_reports_loader(tmp_path: Path, monkeypatch):
    camps = _write_tree(tmp_path)
    calls = []
    real = lp.load_campaign
    monkeypatch.setattr(lp, "load_campaign", lambda code, d: calls.append((code, d.name)) or real(code, d))
    arms, got = jp.load_dev_arms(tmp_path)
    assert got == camps and sorted(calls) == sorted(camps.items())
    assert (arms["M_bplus_11"]["n_scored"], arms["M_bplus_11"]["n_crash"]) == (112, 2)
    rows = jp.contrast_rows(arms)
    assert {k: len(v) for k, v in rows.items()} == {"gate": 114, "L1": 114, "L2": 112, "L3": 112, "L4": 112,
                                                     "L5": 114}
    # The module opens no result file of its own.
    src = (REPO_ROOT / "scripts" / "analysis" / "j11_power.py").read_text(encoding="utf-8")
    for forbidden in ("result.json\"", ".read_text(", "rglob(", "load_arm_tree", "json.load("):
        assert forbidden not in src, forbidden


def test_build_reports_dev_values_with_their_lp_report_keys(tmp_path: Path):
    _write_tree(tmp_path)
    report = jp.build(tmp_path, n_sims=4, n_boot=50, seed=7)
    dev = report["dev"]
    assert dev["gate"]["lp_report_key"] == "planners.P27.gate" and dev["gate"]["point_pp"] == 50.0
    assert dev["gate"]["lp_report_status"] == "COMPLETE" and dev["gate"]["n_pairs"] == 114
    assert dev["L1"]["lp_report_key"] == "planners.P27.contrasts.L1"
    assert (dev["L1"]["point_pp"], dev["L1"]["ci95_pp_scenario"], dev["L1"]["p_raw"]) == (25.0, [25.0, 25.0], 0.0)
    # M^bplus_11 at 112/114: lp_report reads L2-L4 INCOMPLETE; the provisional value is still arithmetic.
    assert dev["L4"]["lp_report_status"] == "INCOMPLETE" and dev["L4"]["source"].startswith("PROVISIONAL")
    assert (dev["L4"]["n_pairs"], dev["L4"]["point_pp"]) == (112, 3.0)
    assert dev["L5"]["lp_report_status"] == "COMPLETE" and dev["L5"]["point_pp"] == 20.0
    assert report["power_table"]["gate_passes"] == {"at_dev_effect": 1.0, "at_half_effect": 1.0}
    assert report["half_effect_shift_pp"]["L4"] == pytest.approx((3.0 - 7.0) / 2)
    assert report["design"] == {"n_scenarios": 56, "tasks_per_scenario": "as on dev (3)", "seeds": [1, 2],
                                "dev_scenarios": 19}


def test_refuses_heldout_paths(tmp_path: Path):
    with pytest.raises(RuntimeError):
        jp.main(["--root", str(tmp_path), "--out", str(tmp_path / "test_normal_power.json")])
