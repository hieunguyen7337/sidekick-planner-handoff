"""LP planner-strength report: the gate, L1-L5 readings and the §4 overall claim on constructed data.

The episode trees are built in the runner's layout (<campaign>/<system>/<seed>/<task>/), 57 tasks
in 19 scenarios x seeds {1, 2}, one campaign per arm, named by the campaign_id each LP config
declares (read here from the real configs, read-only) -- so every count is the registered 114.
No real results tree is ever read.

Arm values are chosen so that each contrast is either a constant (an exact, degenerate interval)
or the pattern Z: +a in 10 scenarios and -a in 9. Every scenario-bootstrap mean of Z is an odd
multiple of a/19 (1.32 pp for a = 0.25), so its interval straddles zero with both bounds outside
POOL-04's 1 pp window -- "includes zero" without a boundary.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import lp_report as lp

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = [f"sc{i:02d}" for i in range(19)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2, 3)]
SCEN_INDEX = {t: int(t[2:4]) for t in TASKS}
CAMPAIGNS = lp.resolve_campaigns(lp.PLANNERS)
NONE_GATE = "none (planner failed the informativeness gate)"


def Z(i: int, amp: float = 0.25) -> float:
    return amp if i < 10 else -amp


def write_episode(campaign_dir: Path, seed: int, task_id: str, gp: float, *, error_type=None) -> None:
    dest = campaign_dir / "arm" / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": f"{campaign_dir.name}/arm/{seed}/{task_id}",
        "task_id": task_id,
        "seed": seed,
        "system": "arm",
        "goal_pass_rate": gp,
        "tgc": 0.0 if error_type else gp,
        "success": gp == 1.0,
        "steps": 12,
        "n_planner_calls": 2,
        "error_type": error_type,
    }
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")


def write_arm(root: Path, campaign: str, value, *, error_types=None) -> None:
    fn = value if callable(value) else (lambda i, v=value: v)
    for seed in lp.SEEDS:
        for task in TASKS:
            write_episode(root / campaign, seed, task, fn(SCEN_INDEX[task]),
                          error_type=(error_types or {}).get((task, seed)))


# E = .25; luna T - A = +.10 (Δ_p reference); luna ceiling .80.
REFERENCE = {"E": 0.25, "T_luna": 0.7, "A_luna": 0.6, "C_luna": 0.8}
# gate C - E = +50; L1 T - A = +25; L2 A1 - Mb11 = -22; L3 Mb11 - Mb6 = +22;
# L4 C - Mb11 = +3 (upper < +7); L5 Mz11 - Mz6 = +20.
REPLICATE = {"C": 0.75, "T": 0.75, "A": 0.5, "A1": 0.5, "F": 0.3,
             "M_bplus_6": 0.5, "M_bplus_9": 0.6, "M_bplus_11": 0.72,
             "M_zs_6": 0.4, "M_zs_9": 0.5, "M_zs_11": 0.6}
FAILS = {**REPLICATE, "T": lambda i: 0.5 + Z(i)}  # L1 = Z: includes zero
REVERSED = {**REPLICATE, "T": 0.25}  # L1 = -25
GATE_FAIL = {**REPLICATE, "C": 0.25}  # C = E
BOUNDARY = {**REPLICATE, "T": 0.875}  # L1 = .375, faked onto the boundary


def write_tree(root: Path, designs: dict, *, errors=None, skip=()) -> Path:
    for planner, design in designs.items():
        for code in lp.PLANNER_ARM_ORDER:
            if (planner, code) in skip:
                continue
            write_arm(root, CAMPAIGNS[planner][code]["campaign"], design[code],
                      error_types=(errors or {}).get((planner, code)))
    for code, name in lp.REFERENCE_CAMPAIGNS.items():
        write_arm(root, name, REFERENCE[code])
    return root


def readings(block: dict) -> dict:
    return {c: r["reading"] for c, r in block["readings"].items()}


ALL_SUPPORTED = {"L1": "replicates", "L2": "supported", "L3": "supported", "L4": "supported",
                 "L5": "supported"}


def test_registration_is_read_from_the_configs_and_matches_the_prereg(tmp_path: Path):
    text = (REPO_ROOT / lp.PREREG).read_text(encoding="utf-8")
    assert CAMPAIGNS["P8"]["C"]["campaign"] == "lp1_planner_alone_cap81_qwen8b_v2_20260923"
    assert CAMPAIGNS["P27"]["C"]["campaign"] == "lp2_planner_alone_cap81_qwen38_27b_20260923"
    for planner, n in (("P8", 1), ("P27", 2)):
        assert set(CAMPAIGNS[planner]) == set(lp.PLANNER_ARM_ORDER)
        for code, arm in CAMPAIGNS[planner].items():
            assert (REPO_ROOT / arm["config"]).is_file()
            assert arm["campaign"].startswith(f"lp{n}_")
            assert arm["campaign"] not in lp.VOID_CAMPAIGNS
    for name in lp.REFERENCE_CAMPAIGNS.values():
        assert name in text
    assert lp.VOID_CAMPAIGNS[0] in text and "VOID" in text
    assert [(c["id"], c["left"], c["right"]) for c in lp.CONTRASTS] == [
        ("L1", "T", "A"), ("L2", "A1", "M_bplus_11"), ("L3", "M_bplus_11", "M_bplus_6"),
        ("L4", "C", "M_bplus_11"), ("L5", "M_zs_11", "M_zs_6")]
    assert {c["id"]: (c["threshold_pp"], c["p_direction"]) for c in lp.CONTRASTS} == {
        "L1": (0.0, "two-sided"), "L2": (0.0, "less"), "L3": (0.0, "greater"),
        "L4": (7.0, "less"), "L5": (0.0, "greater")}
    assert (lp.GATE["left"], lp.GATE["right"]) == ("C", "E")
    assert lp.EXPECTED_PAIRS == 114 and lp.N_BOOT == 10_000 and lp.BOOTSTRAP_SEED == 20260924
    assert lp.j10.POOL04_SEEDS == (20260924, 1, 2, 3, 7, 101, 999)
    assert lp.j10.POOL04_WINDOW_PP == 1.00
    # A config naming the VOID first LP-1 campaign is refused, not analysed.
    (tmp_path / "configs").mkdir()
    (tmp_path / lp.ARM_CONFIGS["P8"]["C"]).write_text(f"campaign_id: {lp.VOID_CAMPAIGNS[0]}\n",
                                                      encoding="utf-8")
    with pytest.raises(lp.ProtocolError, match="VOID"):
        lp.resolve_campaigns(("P8",), tmp_path)


def test_gate_fails_when_C_equals_E_and_no_L_is_read(tmp_path: Path):
    report, rc = lp.build_report(results_root=write_tree(tmp_path, {"P8": GATE_FAIL, "P27": REPLICATE}))
    assert rc == 0 and report["status"] == "COMPLETE", report["headline"]
    p8, p27 = report["planners"]["P8"], report["planners"]["P27"]
    assert p8["gate"]["verdict"] == "too_weak" and p8["gate"]["point_pp"] == 0.0
    assert p8["gate"]["n_pairs"] == 114
    # L1-L5 are still computed and reported, and none is read.
    assert readings(p8) == {c: NONE_GATE for c in lp.L_IDS}
    for c in lp.L_IDS:
        block = p8["contrasts"][c]
        assert block["status"] == "COMPLETE" and block["reading"] == NONE_GATE
        assert block["scenario"]["ci95_pp"] and "p_holm" in block
    assert p8["holm"]["m"] == 5
    assert p27["gate"]["verdict"] == "passes" and p27["gate"]["point_pp"] == 50.0
    assert readings(p27) == ALL_SUPPORTED
    claim = report["overall_claim"]
    assert claim["claim"] == "not_registered_case"
    assert "fewer than two planners pass" in claim["reason"] and "P8: too_weak" in claim["reason"]


def test_both_replicate_generalises_and_L4_reads_against_plus_7(tmp_path: Path):
    report, rc = lp.build_report(results_root=write_tree(tmp_path, {"P8": REPLICATE, "P27": REPLICATE}))
    assert rc == 0 and report["label"] == "LP registered analysis (dev)"
    assert report["overall_claim"]["claim"] == "generalises" and report["overall_claim"]["which"] is None
    for p in lp.PLANNERS:
        block = report["planners"][p]
        assert readings(block) == ALL_SUPPORTED
        c = block["contrasts"]
        assert {k: c[k]["n_pairs"] for k in lp.L_IDS} == {k: 114 for k in lp.L_IDS}
        assert c["L1"]["scenario"]["ci95_pp"] == [25.0, 25.0] and c["L1"]["p_raw_direction"] == "two-sided"
        assert (c["L1"]["scenario"]["n_clusters"], c["L1"]["task"]["n_clusters"]) == (19, 57)
        # L4 = C - Mb11 = +3 everywhere: upper +3 < +7. Its p is 2 x share of draws >= +7.00 pp,
        # which is 0; at a zero threshold the same draws would give p = 1 and no support.
        l4 = c["L4"]
        assert l4["scenario"]["ci95_pp"] == [3.0, 3.0] and l4["threshold_pp"] == 7.0
        assert l4["p_raw"] == 0.0 and l4["p_raw_direction"] == "less"
        assert lp.j10.bootstrap_pvalue([0.03] * 10, 0.0, "less") == 1.0
        assert l4["signflip"]["threshold"] == pytest.approx(0.07) and l4["signflip"]["alternative"] == "less"
        assert l4["pool04"]["status"] == "not_fired"
        assert c["L2"]["p_raw_direction"] == "less" and c["L3"]["p_raw_direction"] == "greater"
        for k in lp.L_IDS:
            assert (c[k]["signflip"]["method"], c[k]["signflip"]["n_patterns"]) == ("exact", 2 ** 19)
            assert c[k]["tgc_secondary"]["n_pairs"] == 114
        assert block["holm"]["family"] == list(lp.L_IDS) and block["holm"]["m"] == 5
        d = block["descriptive"]
        assert d["delta_vs_luna"]["status"] == "COMPLETE" and d["delta_vs_luna"]["point_pp"] == 15.0
        assert d["ceiling_goal_pass"]["goal_pass_mean"] == 0.75 and d["F_goal_pass"]["goal_pass_mean"] == 0.3
    strength = report["descriptive"]["planner_strength"]["by_planner"]
    assert {p: s["goal_pass_mean"] for p, s in strength.items()} == {"luna": 0.8, "P8": 0.75, "P27": 0.75}


def test_one_fails_to_replicate_is_bounded(tmp_path: Path):
    report, rc = lp.build_report(results_root=write_tree(tmp_path, {"P8": FAILS, "P27": REPLICATE}))
    assert rc == 0
    l1 = report["planners"]["P8"]["contrasts"]["L1"]
    lo, hi = l1["scenario"]["ci95_pp"]
    assert lo < -1.0 and hi > 1.0 and l1["pool04"]["status"] == "not_fired"
    assert l1["reading"] == "fails_to_replicate" and "includes zero" in l1["reading_why"]
    assert readings(report["planners"]["P27"])["L1"] == "replicates"
    claim = report["overall_claim"]
    assert (claim["claim"], claim["which"]) == ("bounded", "P27")


def test_reversed_and_fails_is_luna_specific(tmp_path: Path):
    report, rc = lp.build_report(results_root=write_tree(tmp_path, {"P8": REVERSED, "P27": FAILS}))
    assert rc == 0
    l1 = report["planners"]["P8"]["contrasts"]["L1"]
    assert l1["scenario"]["ci95_pp"] == [-25.0, -25.0]
    assert l1["p_raw"] == 0.0 and l1["p_holm"] == 0.0  # two-sided p: a reversal can reject
    assert l1["reading"] == "reversed"
    assert readings(report["planners"]["P27"])["L1"] == "fails_to_replicate"
    assert report["overall_claim"]["claim"] == "luna_specific"


def _rec(point, lo, hi, p, boundary=False):
    return {"status": "COMPLETE", "point": point / 100, "lo": lo / 100, "hi": hi / 100,
            "p_raw": p, "boundary": boundary}


PASS = {"verdict": "passes"}


def test_holm_is_within_one_planner_with_m_5():
    records = {"L1": _rec(4, 1.5, 7, 0.009), "L2": _rec(-1, -4, 2, 0.5), "L3": _rec(1, -2, 4, 0.5),
               "L4": _rec(5, 2, 9, 0.5), "L5": _rec(1, -2, 4, 0.5)}
    out = lp.read_planner(PASS, records)
    assert out["holm"]["m"] == 5 and out["holm"]["family"] == list(lp.L_IDS)
    # m = 5: 0.009 x 5 = 0.045 <= .05. Holm across both planners (m = 10) would give 0.09.
    assert out["holm"]["p"]["L1"]["p_holm"] == pytest.approx(0.045)
    assert lp.j10.holm_adjust([0.009] + [0.5] * 4 + [0.5] * 5)[0] == pytest.approx(0.09)
    assert out["readings"]["L1"]["reading"] == "replicates"
    # Another planner's p-values never enter: read_planner sees one planner's records only,
    # and the same records give the same adjusted p whatever the other planner holds.
    other = {k: _rec(10, 5, 15, 0.0) for k in lp.L_IDS}
    assert lp.read_planner(PASS, other)["holm"]["p"]["L1"]["p_holm"] == 0.0
    assert lp.read_planner(PASS, records)["holm"]["p"]["L1"]["p_holm"] == pytest.approx(0.045)
    # The same interval with p = 0.011 fails Holm (0.055): excludes zero, yet not read as replicating.
    records["L1"] = _rec(4, 1.5, 7, 0.011)
    out = lp.read_planner(PASS, records)
    assert out["readings"]["L1"]["reading"] == "not_resolved" and "Holm" in out["readings"]["L1"]["why"]
    # L4's interval [+2, +9] crosses +7: not supported whatever its p.
    assert out["readings"]["L4"]["reading"] == "not_supported"


def test_overall_claim_covers_every_registered_and_unregistered_case():
    def claim(g8, l8, g27, l27):
        return lp.overall_claim({"P8": {"gate": g8, "L1": l8}, "P27": {"gate": g27, "L1": l27}})

    assert claim("passes", "replicates", "passes", "replicates")["claim"] == "generalises"
    bounded = claim("passes", "fails_to_replicate", "passes", "replicates")
    assert (bounded["claim"], bounded["which"]) == ("bounded", "P27")
    assert claim("passes", "replicates", "passes", "reversed")["which"] == "P8"
    assert claim("passes", "reversed", "passes", "not_resolved")["claim"] == "luna_specific"
    assert claim("passes", "fails_to_replicate", "passes", "fails_to_replicate")["claim"] == "luna_specific"
    for args, why in (
        (("too_weak", NONE_GATE, "passes", "replicates"), "fewer than two planners pass"),
        (("incomplete", "none (informativeness gate not evaluable: C_p - E incomplete)", "passes",
          "replicates"), "fewer than two planners pass"),
        (("passes", "on_the_boundary", "passes", "replicates"), "P8 (on_the_boundary)"),
        (("passes", "replicates", "passes", "incomplete"), "P27 (incomplete)"),
        (("passes", "none (Holm family incomplete)", "passes", "replicates"), "Holm family incomplete"),
    ):
        out = claim(*args)
        assert out["claim"] == "not_registered_case" and why in out["reason"], (args, out)
    only = lp.overall_claim({"P8": {"gate": "passes", "L1": "replicates"}})
    assert only["claim"] == "not_registered_case" and "P27 not analysed" in only["reason"]


def test_crash_is_dropped_and_incomplete_while_limit_and_parse_error_are_scored(tmp_path: Path):
    crash, limit, parse = (TASKS[0], 1), (TASKS[1], 2), (TASKS[2], 1)
    root = write_tree(tmp_path, {"P8": REPLICATE}, errors={
        ("P8", "A"): {crash: "crash"}, ("P8", "C"): {limit: "limit"}, ("P8", "M_zs_6"): {parse: "parse_error"}})
    report, rc = lp.build_report(planners=("P8",), results_root=root)
    assert rc == 1 and report["status"] == "INCOMPLETE"
    assert report["label"].startswith("NON-REGISTERED")
    p8 = report["planners"]["P8"]
    a, c, mz6 = p8["arms"]["A"], p8["arms"]["C"], p8["arms"]["M_zs_6"]
    assert (a["n_crash"], a["n_scored"], a["complete"]) == (1, 113, False)
    assert a["error_types"] == {"crash": 1, "none": 113}
    assert c["error_types"] == {"limit": 1, "none": 113} and c["complete"] is True
    assert mz6["error_types"] == {"none": 113, "parse_error": 1} and mz6["complete"] is True
    l1 = p8["contrasts"]["L1"]
    assert l1["status"] == "INCOMPLETE" and l1["n_pairs"] == 113
    assert "scenario" not in l1 and "p_raw" not in l1  # counts only (§3)
    assert "A 113/114 non-crashed (crash 1, missing 0)" in l1["reason"]
    assert l1["reading"] == "incomplete"
    for k in ("L2", "L3", "L4", "L5"):  # L4 holds the limit episode, L5 the parse_error one
        assert p8["contrasts"][k]["status"] == "COMPLETE" and p8["contrasts"][k]["n_pairs"] == 114
        assert p8["contrasts"][k]["reading"] == "none (Holm family incomplete)"
        assert "p_holm" not in p8["contrasts"][k]
    assert p8["holm"] is None
    assert p8["gate"]["status"] == "COMPLETE" and p8["gate"]["n_pairs"] == 114
    assert p8["descriptive"]["delta_vs_luna"]["status"] == "INCOMPLETE"


def test_bound_near_zero_that_flips_across_seeds_is_on_the_boundary(tmp_path: Path, monkeypatch):
    real = lp.j10.cluster_bootstrap_means

    def fake(diffs, clusters, *, n_boot=10_000, seed=20260924):
        if diffs and all(d == 0.375 for d in diffs):  # L1 (and its TGC twin) only
            lo = -0.002 if seed == 7 else 0.005  # +0.50 pp at the registered seed, -0.20 at seed 7
            return sorted([lo] * 300 + [0.375] * (n_boot - 300))
        return real(diffs, clusters, n_boot=n_boot, seed=seed)

    monkeypatch.setattr(lp.j10, "cluster_bootstrap_means", fake)
    report, rc = lp.build_report(planners=("P8",), results_root=write_tree(tmp_path, {"P8": BOUNDARY}))
    assert rc == 0
    l1 = report["planners"]["P8"]["contrasts"]["L1"]
    assert l1["scenario"]["ci95_pp"][0] == 0.5
    pool = l1["pool04"]
    assert pool["fired"] and pool["on_boundary"] and pool["status"] == "on_boundary"
    assert {b["seed"]: b["lo_pp"] for b in pool["bounds_by_seed"]} == {
        20260924: 0.5, 1: 0.5, 2: 0.5, 3: 0.5, 7: -0.2, 101: 0.5, 999: 0.5}
    assert pool["verdicts_by_seed"] == ["excludes_zero_positive", "includes_zero"]
    # The interval and Holm alone would have read "replicates" ...
    assert l1["p_holm"] == 0.0 and l1["holm_rejects"] is True
    # ... but a verdict that differs on any seed is on the boundary, never resolved.
    assert l1["reading"] == "on_the_boundary"
    assert readings(report["planners"]["P8"]) == {**ALL_SUPPORTED, "L1": "on_the_boundary"}
    assert report["overall_claim"]["claim"] == "not_registered_case"


def test_upper_bound_rules_recheck_only_the_upper_bound():
    rule = lp.j10.A1_RULES[lp.UPPER]
    assert rule["bounds"] == ("hi",)
    series = {"keys": [(t, s) for t in TASKS for s in lp.SEEDS], "diffs": [0.03] * 114}
    # L4 at +3 pp: the lower bound is far from +7 and never re-checked; the upper is 4 pp away.
    primary = {"point": 0.03, "lo": 0.03, "hi": 0.03}
    pool = lp.j10.a1_pool04({"rule": lp.UPPER, "threshold_pp": 7.0}, series, primary, n_boot=100, seed=1)
    assert pool["bounds_checked"] == ["hi"] and pool["fired"] is False
    # An upper bound 0.5 pp under +7 fires and, with a constant series, is stable.
    near = {"keys": series["keys"], "diffs": [0.065] * 114}
    pool = lp._translate_pool04(
        lp.j10.a1_pool04({"rule": lp.UPPER, "threshold_pp": 7.0}, near,
                         {"point": 0.065, "lo": 0.065, "hi": 0.065}, n_boot=100, seed=1), lp.UPPER)
    assert pool["fired"] and pool["status"] == "stable"
    assert pool["verdicts_by_seed"] == ["upper_below_threshold"]


def test_refuses_an_output_dir_under_scratch_or_the_results_tree(tmp_path: Path, monkeypatch):
    empty = tmp_path / "results"
    empty.mkdir()
    target = Path("/scratch/n12194778/lp_report_refusal_probe_do_not_create")
    assert lp.main(["--planners", "P8", "--results-root", str(empty), "--out-dir", str(target)]) == 2
    assert not target.exists()
    monkeypatch.setattr(lp, "FORBIDDEN_OUT_ROOTS", ())  # tmp_path may itself sit on /scratch
    inside = empty / "reports"
    assert lp.main(["--planners", "P8", "--results-root", str(empty), "--out-dir", str(inside)]) == 2
    assert not inside.exists()
    assert lp.main(["--planners", "P9", "--results-root", str(empty), "--out-dir", str(tmp_path / "o")]) == 2


def test_main_writes_json_and_md_and_names_missing_campaigns(tmp_path: Path, monkeypatch, capsys):
    root = write_tree(tmp_path / "results", {"P8": REPLICATE}, skip={("P8", "M_zs_9")})
    monkeypatch.setattr(lp, "FORBIDDEN_OUT_ROOTS", ())
    out_dir = tmp_path / "out"
    rc = lp.main(["--planners", "P8", "--results-root", str(root), "--out-dir", str(out_dir),
                  "--date", "20260930"])
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["exit_code"] == 3
    report = json.loads((out_dir / "lp_planner_strength_20260930.report.json").read_text(encoding="utf-8"))
    assert report["status"] == "MISSING_CAMPAIGNS" and report["date"] == "20260930"
    assert [m["campaign"] for m in report["missing_campaigns"]] == [CAMPAIGNS["P8"]["M_zs_9"]["campaign"]]
    p8 = report["planners"]["P8"]
    assert readings(p8) == ALL_SUPPORTED  # m = 9 is in no contrast
    assert report["overall_claim"]["claim"] == "not_registered_case"
    md = (out_dir / "lp_planner_strength_20260930.md").read_text(encoding="utf-8")
    assert "MISSING_CAMPAIGNS" in md and CAMPAIGNS["P8"]["M_zs_9"]["campaign"] in md
    assert "not_registered_case" in md and "P27 not analysed" in md
    for k in lp.L_IDS:
        c = p8["contrasts"][k]
        lo, hi = c["scenario"]["ci95_pp"]
        assert f"| {k} | {c['definition']} | {c['predicted']} | 114 | {c['point_pp']:+.2f} | [{lo:+.2f}, {hi:+.2f}]" in md
    assert f"{p8['gate']['point_pp']:+.2f} pp over 114 pairs" in md
