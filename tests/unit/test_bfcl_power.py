"""Tests for scripts/analysis/bfcl_power.py (power of the BFCL test predictions, E-prereg §6).

Synthetic dev trees in the real BFCL layout, with answers known by arithmetic: a huge constant effect is
supported in every simulated read, a zero-mean effect almost never, and a fixed seed gives the same
report twice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from scripts.analysis import am1_power as am1
from scripts.analysis import bfcl_dev_report as dr
from scripts.analysis import bfcl_power as bp

SEEDS = (1, 2, 3)


def write_episode(root: Path, arm: str, entry: str, seed: int, gp: float, *, prefix_live: bool = False) -> None:
    """One episode in the real layout; prefix arms get a handoff record (effective_m 6) and, if
    prefix_live, a live executor step at 7 (h* = 1)."""
    cid = f"bfcl_{arm}_dev_20260924"
    system = "prefix_handoff" if arm.startswith("prefix_") else "sys"
    ep = root / cid / system / str(seed) / entry
    ep.mkdir(parents=True, exist_ok=True)
    base = {"run_id": f"{cid}/{system}/{seed}/{entry}", "task_id": entry, "system": system, "seed": seed,
            "usage": None, "error_type": None, "payload": {}}
    events = [{**base, "step": 0, "actor": "system", "event_type": "run_start"}]
    if arm.startswith("prefix_"):
        events.append({**base, "step": 6, "actor": "system", "event_type": "report",
                       "payload": {"effective_m": 6, "n_source_actions": 8, "handoff_occurred": True}})
        if prefix_live:
            events.append({**base, "step": 7, "actor": "executor", "event_type": "action",
                           "payload": {"kind": "CODE", "code": "ls()"}})
    events.append({**base, "step": 7, "actor": "system", "event_type": "run_end"})
    (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (ep / "result.json").write_text(json.dumps({
        "task_id": entry, "seed": seed, "system": system, "error_type": None, "goal_pass_rate": gp,
        "success": gp == 1.0, "tgc": 1.0 if gp == 1.0 else 0.0, "n_planner_calls": 0,
        "totals": {"planner_calls_total": 0}}), encoding="utf-8")


def write_configs(configs: Path) -> Path:
    configs.mkdir(parents=True, exist_ok=True)
    for arm in dr.EXPECTED_ARMS:
        (configs / f"bfcl_{arm}.yaml").write_text(f"campaign_id: bfcl_{arm}_dev_20260924\n", encoding="utf-8")
    return configs


def make_tree(base: Path, values: dict[str, Callable[[int], float]], n_entries: int) -> tuple[Path, Path]:
    """values: arm -> f(entry index) = goal_pass_rate, the same at every seed."""
    root = base / "results"
    for arm, f in values.items():
        for i in range(1, n_entries + 1):
            for s in SEEDS:
                write_episode(root, arm, f"multi_turn_base_{i}", s, f(i), prefix_live=True)
    return root, write_configs(base / "configs")


HUGE = {
    "takeover_k5": lambda i: 0.9, "advise_k5_fullctx": lambda i: 0.1, "advise_k5_neutral": lambda i: 0.5,
    "prefix_zs_m6": lambda i: 0.5, "prefix_bplus_m6": lambda i: 0.5, "planner_alone_cap81": lambda i: 0.5,
}
# P6 per-entry differences alternate +0.2 / -0.2, so its true mean over entries is 0.
NULL_P6 = {
    **HUGE,
    "takeover_k5": lambda i: 0.6 if i % 2 else 0.4, "advise_k5_fullctx": lambda i: 0.4 if i % 2 else 0.6,
}
SIM = dict(n_entries=40, dev_n_boot=200)


def test_huge_effect_has_power_one(tmp_path):
    root, configs = make_tree(tmp_path, HUGE, n_entries=8)
    rep = bp.build(root, configs, n_sims=30, n_boot=200, seed=1, **SIM)
    for name in ("P6", "P6_alone", "P3", "CF1", "CF3", "B1_zs", "B1_bplus", "S3"):
        assert rep["power"][name]["full"] == 1.0, name
        assert rep["power"][name]["half"] == 1.0, name
    assert rep["families_all_supported"]["H"]["full"] == 1.0
    assert rep["families_all_supported"]["H"]["half"] == 1.0
    # P6: dev +80 pp, half-shift 40 pp; P3: dev 0 pp, half-way to -7.00 pp.
    assert rep["half_effect_shift_pp"]["P6"] == pytest.approx(40.0)
    assert rep["half_effect_shift_pp"]["P3"] == pytest.approx(3.5)
    assert rep["meta"]["n_sim"] == 30 and rep["meta"]["n_boot"] == 200 and rep["meta"]["seed"] == 1


def test_zero_effect_is_rarely_supported(tmp_path):
    root, configs = make_tree(tmp_path, NULL_P6, n_entries=10)
    rep = bp.build(root, configs, n_sims=200, n_boot=400, seed=2, **SIM)
    assert rep["dev"]["P6"]["goal_pass"]["diff_pp"] == 0.0
    assert rep["power"]["P6"]["full"] < 0.10
    assert rep["power"]["P6_alone"]["full"] < 0.10
    assert rep["power"]["P3"]["full"] == 1.0  # a constant 0 difference is inside -7.00 pp every time


def test_fixed_seed_is_deterministic(tmp_path):
    root, configs = make_tree(tmp_path, NULL_P6, n_entries=6)
    a = bp.build(root, configs, n_sims=25, n_boot=150, seed=11, **SIM)
    b = bp.build(root, configs, n_sims=25, n_boot=150, seed=11, **SIM)
    assert a["power"] == b["power"]
    assert a["power_at_dev_effect"] == b["power_at_dev_effect"]
    assert a["power_at_half_effect"] == b["power_at_half_effect"]
    assert a["dev"] == b["dev"]


def test_dev_values_match_the_dev_report(tmp_path):
    root, configs = make_tree(tmp_path, NULL_P6, n_entries=6)
    rep = bp.build(root, configs, n_sims=5, n_boot=50, seed=3, **SIM)
    dev = dr.build_report(root, configs, n_boot=SIM["dev_n_boot"], seed=dr.SEED)
    for name, spec in bp.CONTRASTS.items():
        assert rep["dev"][name]["goal_pass"] == dev["contrasts"][spec["dev_id"]]["goal_pass"], name


def test_entries_are_the_clusters(tmp_path):
    root, configs = make_tree(tmp_path, HUGE, n_entries=5)
    arms, hstars = bp.load_arms(root, configs)
    rows = bp.paired_rows(arms, hstars, bp.CONTRASTS["P6"])
    index = am1.index_by_scenario(rows)
    assert len(index) == 5  # one cluster per entry, never scenario_of's single "multi_turn_base"
    assert all(list(tasks) == [scen] and sorted(tasks[scen]) == [1, 2, 3] for scen, tasks in index.items())


def test_absent_arms_give_null_rows_with_a_reason(tmp_path):
    root, configs = make_tree(tmp_path, {"executor_alone_zs": lambda i: 0.5}, n_entries=3)
    rep = bp.build(root, configs, n_sims=5, n_boot=50, seed=1, **SIM)
    for name, row in rep["power"].items():
        assert row["full"] is None and row["half"] is None and row["reason"], name
    assert rep["families_all_supported"]["H"]["full"] is None
    assert rep["families_all_supported"]["H"]["reason"]


def test_incomplete_family_is_not_run_at_a_smaller_m(tmp_path):
    only_p6 = {k: HUGE[k] for k in ("takeover_k5", "advise_k5_fullctx")}
    root, configs = make_tree(tmp_path, only_p6, n_entries=6)
    rep = bp.build(root, configs, n_sims=10, n_boot=100, seed=1, **SIM)
    assert rep["power"]["P6"]["full"] is None and "family H incomplete" in rep["power"]["P6"]["reason"]
    assert rep["power"]["P6_alone"]["full"] == 1.0


def test_heldout_paths_are_refused(tmp_path):
    configs = write_configs(tmp_path / "configs")
    with pytest.raises(RuntimeError):
        bp.build(tmp_path / "bfcl_x_test_y", configs, n_sims=1, n_boot=10, seed=1)
    with pytest.raises(RuntimeError):
        bp.main(["--root", str(tmp_path), "--configs", str(configs), "--out", str(tmp_path / "p_test_q.json")])
