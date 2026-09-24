"""Tests for the J17 v2 fill (scripts/analysis/j17_v2_fill.py).

Fixtures are synthetic so the right answer is known by arithmetic. Where every scenario has the
same composition, every scenario resample gives the same statistic, so the scenario interval
collapses onto the hand-computed point.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j17_v2_fill as fill

# Two scenarios x three tasks x two seeds = 12 episodes; scenario_of splits on the last "_".
KEYS = [(f"s{s}_{t}", seed) for s in (1, 2) for t in (1, 2, 3) for seed in (1, 2)]
TASKS = sorted({k[0] for k in KEYS})


def row(value: float, *, error_type=None, tgc=None, success=None) -> dict:
    """A j16-loader row: result.json fields plus `_facts`."""
    return {
        "goal_pass_rate": value,
        "tgc": (value if tgc is None else tgc) if error_type is None else 0.0,
        "error_type": error_type,
        "success": (value == 1.0) if success is None else success,
        "n_planner_calls": 1,
        "_facts": {"handoff_occurred": None},
    }


def ep(value: float, *, error_type=None, success=None) -> dict:
    """A j10 scored episode (j10.a1_arm_episodes shape)."""
    return {"goal_pass_rate": value, "tgc": 1.0 if value == 1.0 else 0.0, "error_type": error_type,
            "success": (value == 1.0) if success is None else success}


# --------------------------------------------------------------------------------------
# Refusal and loading
# --------------------------------------------------------------------------------------


def test_refuse_path_blocks_held_out_and_jx_names_but_not_hj12() -> None:
    for bad in ("/r/x/test_normal/y", "/r/test_challenge", "/r/j10_a1_dev", "j12_power_dev.report.json",
                "/r/hj13_x/j11_y"):
        with pytest.raises(fill.RefusedPath):
            fill.refuse_path(bad)
    for ok in ("/r/hj12_prefix_m9_20260923", "/r/hj10x", "campaign/results/j17_v2_fill_20260924.report.json"):
        fill.refuse_path(ok)


def _write_result(root: Path, campaign: str, system: str, seed: int, task: str, **fields) -> None:
    d = root / campaign / system / str(seed) / task
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"task_id": task, "seed": seed, **fields}), encoding="utf-8")


def test_load_rows_reads_one_campaign_tree_and_refuses_a_jx_campaign(tmp_path, monkeypatch) -> None:
    _write_result(tmp_path, "campA", "sys", 1, "s1_1", goal_pass_rate=0.5, tgc=0.0, error_type="limit",
                  n_planner_calls=3)
    _write_result(tmp_path, "campA", "sys", 2, "s1_1", goal_pass_rate=1.0, tgc=1.0, n_planner_calls=3)
    monkeypatch.setattr(fill, "ARM_SOURCES", {"x": (("campA", "sys", (1,)),), "bad": (("j12_x", "sys", (1,)),)})
    rows, entries = fill.load_rows(tmp_path, "x")
    assert list(rows) == [("s1_1", 1)]  # seed 2 is filtered by the source's seeds
    assert rows[("s1_1", 1)]["error_type"] == "limit"
    assert entries[0]["n_episodes"] == 1
    with pytest.raises(fill.RefusedPath):
        fill.load_rows(tmp_path, "bad")


def test_seed_subset() -> None:
    assert fill.seed_subset({("a_1", 1): 1, ("a_1", 3): 2}, (1, 2)) == {("a_1", 1): 1}


# --------------------------------------------------------------------------------------
# Step-limit counts
# --------------------------------------------------------------------------------------


def test_limit_counts_by_hand() -> None:
    rows = {("s1_1", 1): row(0.2, error_type="limit"), ("s1_2", 1): row(0.5),
            ("s1_3", 2): row(1.0), ("s2_1", 2): row(0.0, error_type="crash")}
    c = fill.limit_counts(rows)
    assert (c["n"], c["n_crash"], c["n_scored"], c["n_limit"]) == (4, 1, 3, 1)
    assert c["rate"] == pytest.approx(1 / 3)
    assert c["goal_pass_mean"] == pytest.approx((0.2 + 0.5 + 1.0) / 3)
    assert c["by_seed"] == {"1": {"n_scored": 2, "n_limit": 1}, "2": {"n_scored": 1, "n_limit": 0}}


# --------------------------------------------------------------------------------------
# Components
# --------------------------------------------------------------------------------------


def test_components_every_part_by_hand() -> None:
    diffs = {("a_1", 1): 0.3, ("a_2", 1): -0.1, ("a_3", 1): 0.2}
    flags = {("a_1", 1): 1.0, ("a_2", 1): 0.0, ("a_3", 1): 1.0}

    def stat(c):
        return sum(v[0] for v in c.values()) / sum(v[1] for v in c.values())

    assert stat(fill.components(diffs)) == pytest.approx(0.4 / 3)
    assert stat(fill.components(diffs, flags, "subset")) == pytest.approx(0.5 / 2)
    assert stat(fill.components(diffs, flags, "complement")) == pytest.approx(-0.1)
    assert stat(fill.components(diffs, flags, "contribution")) == pytest.approx(0.5 / 3)
    # contribution + complement's contribution = the whole mean
    assert 0.5 / 3 + (-0.1) / 3 == pytest.approx(0.4 / 3)
    with pytest.raises(ValueError):
        fill.components(diffs, flags, "nope")
    with pytest.raises(ValueError):
        fill.components(diffs, None, "subset")


def test_j10_diffs_limit_flags_and_zero_limits() -> None:
    left = {("a_1", 1): ep(0.8), ("a_2", 1): ep(0.4, error_type="limit"), ("a_3", 1): {"goal_pass_rate": None}}
    right = {("a_1", 1): ep(0.5, error_type="limit"), ("a_2", 1): ep(0.6), ("a_3", 1): ep(0.1)}
    d = fill.j10_diffs(left, right, "goal_pass_rate")
    assert d == {("a_1", 1): pytest.approx(0.3), ("a_2", 1): pytest.approx(-0.2)}  # a_3 has no left value
    assert fill.limit_flags(left, right, d) == {("a_1", 1): 1.0, ("a_2", 1): 1.0}
    z = fill.zero_limits(left, "goal_pass_rate")
    assert z[("a_2", 1)]["goal_pass_rate"] == 0.0 and z[("a_1", 1)]["goal_pass_rate"] == 0.8
    assert left[("a_2", 1)]["goal_pass_rate"] == 0.4  # the input is not mutated


def test_sgc_components_by_hand() -> None:
    """Seed 1 only. Left passes all of s1 and fails one task of s2; right the reverse."""
    left = {(t, 1): ep(0.0 if t == "s2_2" else 1.0) for t in TASKS}
    right = {(t, 1): ep(0.0 if t == "s1_3" else 1.0) for t in TASKS}
    comps, unscored = fill.sgc_components(left, right, TASKS, [1])
    assert comps == {("s1", 1): (1.0, 1.0), ("s2", 1): (-1.0, 1.0)}
    assert unscored == {"n_units_unscored_left": 0, "n_units_unscored_right": 0}
    del right[("s2_1", 1)]  # an incomplete unit is unscored, not failed
    comps, unscored = fill.sgc_components(left, right, TASKS, [1])
    assert list(comps) == [("s1", 1)] and unscored["n_units_unscored_right"] == 1


def test_cost_fraction_and_chord_components_by_hand() -> None:
    assert fill.cost_fraction({"cost_arm": 30.0, "cost_floor": 10.0, "cost_reference": 50.0}) == pytest.approx(0.5)
    arm = {("a_1", 1): row(0.8), ("a_2", 1): row(0.8, error_type="crash")}
    floor = {("a_1", 1): row(0.6), ("a_2", 1): row(0.6)}
    ref = {("a_1", 1): row(0.9), ("a_2", 1): row(0.9)}
    comps = fill.chord_components(arm, floor, ref, "goal_pass_rate", 0.5)
    # 0.8 - (0.6 + 0.5 * (0.9 - 0.6)) = 0.05; the crashed triple is left out
    assert list(comps) == [("a_1", 1)]
    assert comps[("a_1", 1)][0] == pytest.approx(0.05)


def test_did_components_by_hand() -> None:
    k = ("a_1", 1)
    comps = fill.did_components({k: row(0.7)}, {k: row(0.6)}, {k: row(0.5)}, {k: row(0.8)}, "goal_pass_rate")
    assert comps[k][0] == pytest.approx((0.7 - 0.6) - (0.5 - 0.8))
    assert fill.did_components({k: row(0.7)}, {}, {k: row(0.5)}, {k: row(0.8)}, "goal_pass_rate") == {}


def test_pair_diffs_drops_crashes() -> None:
    left = {("a_1", 1): row(0.9), ("a_2", 1): row(0.9, error_type="crash")}
    right = {("a_1", 1): row(0.4), ("a_2", 1): row(0.4)}
    assert fill.pair_diffs(left, right, "goal_pass_rate") == {("a_1", 1): pytest.approx(0.5)}


# --------------------------------------------------------------------------------------
# Contrast entries
# --------------------------------------------------------------------------------------


def test_reproduces_and_signed_interval() -> None:
    assert fill.reproduces(6.13, 6.1349) is True
    assert fill.reproduces(6.13, 6.1451) is False
    assert fill.reproduces([-1.56, 10.81], [-1.5559, 10.8123]) is True
    assert fill.reproduces(None, 3.0) is None
    assert fill.reproduces(3.0, None) is False
    assert fill._signed_ci([1.0, 2.0], -1) == [-2.0, -1.0]
    assert fill._signed_ci([1.0, 2.0], 1) == [1.0, 2.0]


def _same_composition_comps() -> dict:
    """d = 0.3 on task _1, 0.1 on _2 and _3, in both scenarios: mean 1.0 / 6 per scenario."""
    return {k: (0.3 if k[0].endswith("_1") else 0.1, 1.0) for k in KEYS}


def test_contrast_entry_point_interval_p_and_printed_sign() -> None:
    point_pp = 100 * 1.0 / 6
    spec = {"id": "x", "ledger": "L", "lines": "1", "definition": "d", "metric": "goal_pass",
            "population": "all", "threshold_pp": 0.0, "sign": -1,
            "printed": {"diff_pp": -16.67, "scenario": [-16.67, -16.67], "task": None}}
    e = fill.contrast_entry(spec, _same_composition_comps(), n_boot=200, seed=5)
    assert e["computed"]["diff_pp"] == pytest.approx(point_pp)
    assert e["computed"]["ci95_pp_scenario"] == [pytest.approx(point_pp), pytest.approx(point_pp)]
    assert e["as_printed"]["diff_pp"] == pytest.approx(-point_pp)
    assert e["reproduces_all_printed"] is True and e["reproduces_printed"]["ci95_pp_task"] is None
    assert e["p_two_sided"] == 0.0  # no resample reaches 0
    # Exact sign-flip over 2 scenarios, each summing to 1.0 over 6 pairs: the 4 patterns give
    # T = +1/6, 0, 0, -1/6, and |T| >= 1/6 in 2 of 4.
    assert e["p_signflip_two_sided"] == pytest.approx(0.5)
    assert e["n_pairs"] == 12


def test_contrast_entry_sgc_has_no_task_interval() -> None:
    comps = {("s1", 1): (1.0, 1.0), ("s2", 1): (0.0, 1.0), ("s1", 2): (1.0, 1.0), ("s2", 2): (0.0, 1.0)}
    spec = {"id": "x.sgc", "ledger": "L", "lines": "1", "definition": "d", "metric": "sgc", "population": "all",
            "threshold_pp": 0.0, "units": "sgc", "printed": {"diff_pp": 50.0}}
    e = fill.contrast_entry(spec, comps, n_boot=100, seed=1)
    assert e["computed"]["diff_pp"] == pytest.approx(50.0)
    assert e["computed"]["ci95_pp_task"] is None and e["computed"]["p_two_sided_task"] is None
    assert e["reproduces_all_printed"] is True


def test_contrast_entry_checks_printed_intervals_at_the_source_seed(monkeypatch) -> None:
    # A stub resampler whose interval and p are the seed itself, so the expected values are the seeds.
    def stub(comps, num, den, *, metric, threshold_pp, n_boot, seed):
        return {"diff_pp": 2.0, "ci95_pp_scenario": [float(seed), float(seed)], "ci95_pp_task": [0.0, 1.0],
                "p_two_sided": seed / 100.0, "p_signflip_two_sided": 0.5, "n_pairs": 4}
    monkeypatch.setattr(fill.dfx, "contrast_object", stub)
    spec = {"id": "x", "ledger": "L", "lines": "1", "definition": "d", "metric": "goal_pass", "population": "all",
            "threshold_pp": 0.0, "sign": -1, "source_seed": 7,
            "printed": {"diff_pp": -2.0, "scenario": [-7.0, -7.0], "task": [-1.0, 0.0]}}
    e = fill.contrast_entry(spec, {}, n_boot=10, seed=5)
    assert e["reproduction_seed"] == 7
    assert e["as_printed_at_reproduction_seed"]["ci95_pp_scenario"] == [-7.0, -7.0]  # seed 7, negated and flipped
    assert e["as_printed"]["ci95_pp_scenario"] == [-5.0, -5.0]  # the reported interval stays at seed 5
    assert e["p_two_sided"] == 0.05  # and so does the p
    assert e["reproduces_all_printed"] is True
    no_source = dict(spec, source_seed=None)
    e2 = fill.contrast_entry(no_source, {}, n_boot=10, seed=5)
    assert e2["reproduction_seed"] == 5 and e2["reproduces_printed"]["ci95_pp_scenario"] is False
    assert {s["id"] for s in fill.main_text_specs() if s["source_seed"] == fill.HJ1_SEED} == {
        "CEIL07.gp", "C1_114.gp", "C1_114.tgc", "H2.vs_prefix_m11.gp", "H2.vs_prefix_m11.tgc", "H2.vs_plan_floor.gp",
        "H2.vs_advise_k10.gp", "chord.UF07.prefix_m9", "narr.m9.tailored.exec_minus_narr",
        "narr.m9.untailored.exec_minus_narr", "narr.m11.untailored.narr_minus_exec", "narr.untailored.m9_to_m11",
        "narr.m11.tailored.narr_minus_exec"}
    assert fill.HJ1_SEED == 20260915


def test_main_text_membership_is_read_from_the_paper() -> None:
    text = ("# T\n"
            "Abstract: +6.13 pp (scenario [+0.75, +12.71], task [+0.97, +11.73]).\n"
            "| D1 | +3.83 [−1.56, +10.81] | [[NEEDS LEDGER: D1 SGC]] |\n"
            "A share of 0.5952 [0.37, 0.89] and a ratio 3.19× ([2.47, 4.06]).\n"
            "## Appendix A. Reproducibility\n"
            "For T − N +3.55 pp ([+1.00, +7.03]; [+1.34, +6.19]).\n")
    lines = fill.main_text_lines(text)
    assert len(lines) == 4  # the appendix heading and everything after it are cut
    d0 = {"printed": {"scenario": [0.75, 12.71], "task": [0.97, 11.73]}}
    tn = {"printed": {"scenario": [1.00, 7.03], "task": [1.34, 6.19]}}
    d1_gp = {"printed": {"scenario": [-1.56, 10.81], "task": None}}  # sign written as "−" in the paper
    d1_sgc = {"printed": {}, "anchor": "NEEDS LEDGER: D1 SGC",
              "as_printed": {"ci95_pp_scenario": [-10.526316, 10.526316], "ci95_pp_task": None}}
    assert fill.locate_in_main_text(d0, lines) == [2]
    assert fill.locate_in_main_text(tn, lines) == []  # printed only in the appendix
    assert fill.locate_in_main_text(d1_gp, lines) == [3]
    assert fill.locate_in_main_text(d1_sgc, lines) == [3]  # by its marker, before it is filled
    filled = ["| D1 | +3.83 [−1.56, +10.81] | 0.00 [−10.53, +10.53] |"]
    assert fill.locate_in_main_text(d1_sgc, filled) == [1]  # by its value, after
    un = fill.unmatched_intervals(lines, [d0, tn, d1_gp, d1_sgc])
    assert [(u["line"], u["interval"]) for u in un] == [(4, "[0.37, 0.89]"), (4, "[2.47, 4.06]")]


def test_main_text_specs_shape() -> None:
    specs = fill.main_text_specs()
    assert len(specs) == fill.N_MAIN_TEXT_INTERVALS == 68
    ids = [s["id"] for s in specs]
    assert len(ids) == len(set(ids))
    kinds = {s["build"][0] for s in specs}
    assert kinds <= {"channel", "channel_zero", "channel_sgc", "pair", "depth", "ni", "chord", "did"}
    assert sum(1 for s in specs if s["threshold_pp"] == -7.0) == 16  # Table 6
    assert sum(1 for s in specs if s["units"] == "sgc") == 6  # C1 at 114 and D0-D4
    assert all(s["sign"] in (1, -1) for s in specs)


def test_build_components_channel_contribution_and_limit_as_zero() -> None:
    """T - A on two pairs: a_1 (T 0.9, A 0.3 at the limit) and a_2 (0.6 vs 0.5)."""
    t = {("a_1", 1): ep(0.9), ("a_2", 1): ep(0.6)}
    a = {("a_1", 1): ep(0.3, error_type="limit"), ("a_2", 1): ep(0.5)}
    data = {"channel": {"T": t, "A": a}, "channel_tasks": ["a_1", "a_2"]}
    comps, meta = fill.build_components({"build": ("channel", "T", "A", "goal_pass_rate", "contribution", None)}, data)
    assert meta["n_flagged"] == 1
    assert sum(c[0] for c in comps.values()) / sum(c[1] for c in comps.values()) == pytest.approx(0.6 / 2)
    comps, _ = fill.build_components({"build": ("channel_zero", "T", "A")}, data)
    assert sum(c[0] for c in comps.values()) / 2 == pytest.approx(((0.9 - 0.0) + (0.6 - 0.5)) / 2)


# --------------------------------------------------------------------------------------
# BY
# --------------------------------------------------------------------------------------


def test_by_block_by_hand() -> None:
    """m = 3, c(3) = 11/6. Ranked p x 3 x c / rank: 0.001 -> 0.0055, 0.02 -> 0.055, 0.5 -> 0.9167;
    already monotone. Only the first survives at 0.05; the entry without a p is not in m."""
    entries = [{"id": i, "metric": "goal_pass", "threshold_pp": 0.0, "p": p}
               for i, p in (("a", 0.001), ("b", 0.02), ("c", 0.5), ("d", None))]
    b = fill.by_block(entries, "p")
    assert b["m"] == 3 and b["not_in_family"] == ["d"]
    got = {r["id"]: r["p_by"] for r in b["rows"]}
    c3 = 1 + 1 / 2 + 1 / 3
    assert got["a"] == pytest.approx(0.001 * 3 * c3)
    assert got["b"] == pytest.approx(0.02 * 3 * c3 / 2)
    assert got["c"] == pytest.approx(0.5 * 3 * c3 / 3)
    assert b["survivors"] == ["a"] and b["n_survive"] == 1


# --------------------------------------------------------------------------------------
# kept - dropped
# --------------------------------------------------------------------------------------


def _selection_fixture() -> tuple[dict, dict]:
    """The reference ends at its limit on task _1 (4 episodes); the arm scores 0.2 there and
    0.8 on the 8 kept episodes: kept - dropped = 60 pp in every scenario."""
    ref = {k: row(0.1, error_type="limit") if k[0].endswith("_1") else row(0.9) for k in KEYS}
    arm = {k: row(0.2) if k[0].endswith("_1") else row(0.8) for k in KEYS}
    return arm, ref


def test_kept_minus_dropped_by_hand() -> None:
    arm, ref = _selection_fixture()
    for unit in ("scenario", "task"):
        k = fill.kept_minus_dropped(arm, ref, unit, n_boot=200, seed=3)
        assert k["kept_minus_dropped_pp"] == pytest.approx(60.0)
        assert (k["n_kept"], k["n_dropped"], k["n_pairs"]) == (8, 4, 12)
        # Kept episodes all score 0.8 and dropped 0.2, so every defined resample gives 60.
        assert k["ci95_pp"] == [pytest.approx(60.0), pytest.approx(60.0)]
    assert fill.kept_minus_dropped(arm, ref, "scenario", n_boot=200, seed=3)["n_resamples_without_a_dropped_episode"] == 0


def test_selection_task_checks_the_scenario_interval_against_the_report() -> None:
    arm, ref = _selection_fixture()
    rows = {"ceiling_cap25": ref, "plan_floor": arm, "executor_alone": arm, "ceiling_cap81": ref}
    per_arm = {"plan_only": {"kept_minus_dropped_ci95_pp_scenario": [60.0, 60.0]},
               "executor_alone": {"kept_minus_dropped_ci95_pp_scenario": [59.0, 61.0]}}
    report = {"F_e_ni_both_ceilings": {"selection_induced_by_limit_exclusion": {
        "cap25": {"per_arm": per_arm}, "cap81": {"per_arm": {}}}}}
    out = fill.selection_task(rows, report, n_boot=100, seed=2)
    assert out["cap25"]["plan_only"]["scenario_reproduces_report"] is True
    assert out["cap25"]["executor_alone"]["scenario_reproduces_report"] is False
    assert out["cap25"]["ceiling_cap25"]["scenario_reproduces_report"] is None
    # The reference against itself: kept episodes 0.9, dropped 0.1.
    assert out["cap81"]["ceiling_cap81"]["task"]["kept_minus_dropped_pp"] == pytest.approx(80.0)


# --------------------------------------------------------------------------------------
# Contrast census
# --------------------------------------------------------------------------------------


CENSUS_TREE = {
    "contrasts": {
        "a_minus_b": {"diff_pp": 1.0, "ci95_pp": [0.0, 2.0],
                      "diagnostic_pair_resample": {"diff_pp": 1.0, "ci95_pp": [0.1, 1.9]}},
        "b2": {"point_pp": 3.0, "scenario": {"diff_pp": 3.0, "ci95_pp": [1.0, 5.0]},
               "task": {"diff_pp": 3.0, "ci95_pp": [1.5, 4.5]}},
    },
    "arm": {"mean": 0.5, "ci95": [0.4, 0.6]},
    "arm2": {"point": 0.5, "ci95_scenario": [0.4, 0.6]},
    "delta_total": {"point": 0.1, "ci95_scenario": [0.0, 0.2]},
    "copy": [{"x_minus_y": {"diff_pp": 1.0, "ci95_pp": [0.0, 2.0]}}],
}


def test_contrast_objects_counts_outermost_only() -> None:
    """a_minus_b (its diagnostic child is not recounted), b2 (point one level down),
    delta_total (a 'point' under a contrast-like key) and the copy: 4; arm and arm2 are means."""
    found = dict(fill.contrast_objects(CENSUS_TREE))
    assert set(found) == {"contrasts.a_minus_b", "contrasts.b2", "delta_total", "copy.0.x_minus_y"}
    assert found["contrasts.a_minus_b"] == found["copy.0.x_minus_y"] == (1.0, (0.0, 2.0))
    assert found["contrasts.b2"] == (3.0, (1.0, 5.0))
    assert fill.is_contrast_object({"point": 0.1, "ci95": [0, 1]}, "all") is False


def test_contrast_census_excludes_jx_files_and_collapses_duplicates(tmp_path) -> None:
    (tmp_path / "a.report.json").write_text(json.dumps(CENSUS_TREE), encoding="utf-8")
    (tmp_path / "j10_x.report.json").write_text(json.dumps(CENSUS_TREE), encoding="utf-8")
    c = fill.contrast_census(sorted(tmp_path.glob("*.report.json")), tmp_path)
    assert c["n_files"] == 1 and c["files_excluded_by_name"] == ["j10_x.report.json"]
    assert c["n_objects"] == 4 and c["n_distinct"] == 3
    assert c["per_file"] == {"a.report.json": 4}
