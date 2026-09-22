"""B2 decomposition report: each registered outcome fires on constructed data, in order.

The episode trees are built in the runner's layout (<campaign>/<system>/<seed>/<task>/),
57 tasks in 19 scenarios x seeds {1, 2, 3}, two campaigns per arm exactly as Amendment 1
§5 pools them, so every count below is the registered 171.

Arm values are chosen so that each contrast is either a constant (an exact, degenerate
interval) or the pattern Z: +a in 10 scenarios and -a in 9. Every scenario-bootstrap mean
of Z is an odd multiple of a/19 (1.32 pp for a = 0.25), so its interval straddles zero
with both bounds well outside POOL-04's 1 pp window -- "includes zero" without a boundary.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import b2_decomposition as b2

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = [f"sc{i:02d}" for i in range(19)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2, 3)]
SCEN_INDEX = {t: int(t[2:4]) for t in TASKS}
CAMPAIGN_SEEDS = ((1, 2), (3,))  # Amendment 1 §5: seeds 1-2 in the first campaign, 3 in the second


def Z(i: int, amp: float = 0.25) -> float:
    return amp if i < 10 else -amp


def write_episode(campaign_dir: Path, seed: int, task_id: str, gp: float, *, error_type=None,
                  calls: int = 2) -> Path:
    dest = campaign_dir / "fixed_k" / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": f"{campaign_dir.name}/fixed_k/{seed}/{task_id}",
        "task_id": task_id,
        "seed": seed,
        "system": "fixed_k",
        "goal_pass_rate": gp,
        "tgc": 0.0 if error_type else gp,
        "success": gp == 1.0,
        "steps": 12,
        "n_planner_calls": calls,
        "error_type": error_type,
        "totals": {
            "usd_total": 0.004 * calls,
            "per_actor": {"planner": {"input_tokens": 1000 * calls, "cached_input_tokens": 500,
                                      "output_tokens": 10, "reasoning_output_tokens": 5,
                                      "n_calls": calls}},
        },
    }
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    return dest


def write_arm(root: Path, code: str, value, *, error_types=None, campaigns=(0, 1)) -> None:
    for idx in campaigns:
        camp = root / b2.ARM_CAMPAIGNS[code][idx]
        for seed in CAMPAIGN_SEEDS[idx]:
            for task in TASKS:
                write_episode(camp, seed, task, value(SCEN_INDEX[task]),
                              error_type=(error_types or {}).get((task, seed)))


def write_matrix(root: Path, values: dict, **per_arm) -> Path:
    for code in b2.ARM_ORDER:
        write_arm(root, code, values[code], **per_arm.get(code, {}))
    return root


def fires(report: dict) -> dict:
    return {s["outcome"]: s["fires"] for s in report["outcome"]["trace"]}


# Contrasts: D1 = T-S, D2 = S-A, D3 = N-A, D4 = T-N (and D0 = T-A).
PROMPT_ARTEFACT = {  # D3 = +.25; D4 = Z; D1 = -.25 (blocks 2 and 3); D2 = .5 + Z
    "A": lambda i: 0.25, "S": lambda i: 0.75 + Z(i), "T": lambda i: 0.5 + Z(i), "N": lambda i: 0.5,
}
EXECUTION = {  # D1 = +.25; D4 = +.25 (blocks 1); D2 = D3 = Z
    "A": lambda i: 0.5, "S": lambda i: 0.5 + Z(i), "T": lambda i: 0.75 + Z(i), "N": lambda i: 0.5 + Z(i),
}
CONTENT = {  # D1 = Z; D2 = +.25; D3 = Z (blocks 1); D4 = +.25
    "A": lambda i: 0.25, "S": lambda i: 0.5, "T": lambda i: 0.5 + Z(i), "N": lambda i: 0.25 + Z(i),
}
UNRESOLVED = {  # D1 = D2 = D3 = D4 = Z
    "A": lambda i: 0.5, "S": lambda i: 0.5 + Z(i), "T": lambda i: 0.5 + 2 * Z(i), "N": lambda i: 0.5 + Z(i),
}
ORDER = {  # D1 = +.25 (outcome 2) AND D3 = +.25 with D4 = Z (outcome 1)
    "A": lambda i: 0.25, "S": lambda i: 0.25 + Z(i), "T": lambda i: 0.5 + Z(i), "N": lambda i: 0.5,
}
BOUNDARY = {  # D1 = .375 (faked onto the boundary); D2 = Z/2; D3 = 0; D4 = .5 / .25
    "A": lambda i: 0.5, "S": lambda i: 0.5 + Z(i, 0.125), "T": lambda i: 0.875 + Z(i, 0.125),
    "N": lambda i: 0.5,
}


def test_registration_is_data_and_matches_the_prereg():
    text = (REPO_ROOT / b2.PREREG).read_text(encoding="utf-8")
    assert b2.ARM_CAMPAIGNS == {
        "T": ("hj12_takeover_fixed_k_10_20260923", "b1_takeover_fixed_k_10_s3_20260923"),
        "A": ("hj12_advise_fixed_k_10_fullctx_20260923", "b1_advise_fixed_k_10_fullctx_s3_20260923"),
        "S": ("b2_show_fixed_k_10_20260923", "b2_show_fixed_k_10_s3_20260923"),
        "N": ("b2_advise_neutral_fixed_k_10_fullctx_20260923",
              "b2_advise_neutral_fixed_k_10_fullctx_s3_20260923"),
    }
    for names in b2.ARM_CAMPAIGNS.values():
        for name in names:
            assert name in text
    assert [(c["id"], c["left"], c["right"]) for c in b2.CONTRASTS] == [
        ("D0", "T", "A"), ("D1", "T", "S"), ("D2", "S", "A"), ("D3", "N", "A"), ("D4", "T", "N")]
    assert b2.HOLM_FAMILY == ("D1", "D2", "D3", "D4")
    assert [o["id"] for o in b2.OUTCOMES] == [
        "prompt_artefact", "execution_matters", "content_not_execution", "unresolved"]
    assert b2.EXPECTED_PAIRS == 171 and b2.N_BOOT == 10_000 and b2.BOOTSTRAP_SEED == 20260924
    assert b2.j10.POOL04_SEEDS == (20260924, 1, 2, 3, 7, 101, 999)
    assert b2.j10.POOL04_WINDOW_PP == 1.00


def test_prompt_artefact(tmp_path: Path):
    report, rc = b2.build_report(results_root=write_matrix(tmp_path, PROMPT_ARTEFACT))
    assert rc == 0 and report["status"] == "COMPLETE", report["headline"]
    assert report["outcome"]["reading"] == "prompt_artefact"
    assert fires(report) == {"prompt_artefact": True, "execution_matters": False,
                             "content_not_execution": False, "unresolved": False}
    c = report["contrasts"]
    assert {d: c[d]["n_pairs"] for d in c} == {d: 171 for d in ("D0", "D1", "D2", "D3", "D4")}
    assert c["D3"]["scenario"]["ci95_pp"] == [25.0, 25.0] and c["D3"]["p_raw"] == 0.0
    assert c["D1"]["scenario"]["ci95_pp"] == [-25.0, -25.0]
    lo, hi = c["D4"]["scenario"]["ci95_pp"]
    assert lo < -1.0 and hi > 1.0 and c["D4"]["pool04"]["status"] == "not_fired"
    assert (c["D4"]["scenario"]["n_clusters"], c["D4"]["task"]["n_clusters"]) == (19, 57)
    assert c["D0"]["holm_family"] is False and "p_holm" not in c["D0"]


def test_execution_matters(tmp_path: Path):
    report, rc = b2.build_report(results_root=write_matrix(tmp_path, EXECUTION))
    assert rc == 0
    assert report["outcome"]["reading"] == "execution_matters"
    assert fires(report) == {"prompt_artefact": False, "execution_matters": True,
                             "content_not_execution": False, "unresolved": False}
    d1 = report["contrasts"]["D1"]
    assert d1["scenario"]["ci95_pp"] == [25.0, 25.0] and d1["p_holm"] == 0.0 and d1["holm_rejects"]
    assert report["contrasts"]["D4"]["events"]["includes_zero"]["held"] is False


def test_content_not_execution(tmp_path: Path):
    report, rc = b2.build_report(results_root=write_matrix(tmp_path, CONTENT))
    assert rc == 0
    assert report["outcome"]["reading"] == "content_not_execution"
    assert fires(report) == {"prompt_artefact": False, "execution_matters": False,
                             "content_not_execution": True, "unresolved": False}
    assert report["contrasts"]["D1"]["events"]["includes_zero"]["held"] is True
    assert report["contrasts"]["D2"]["scenario"]["ci95_pp"] == [25.0, 25.0]


def test_unresolved_still_reports_every_interval(tmp_path: Path):
    report, rc = b2.build_report(results_root=write_matrix(tmp_path, UNRESOLVED))
    assert rc == 0
    assert report["outcome"]["reading"] == "unresolved"
    assert fires(report) == {"prompt_artefact": False, "execution_matters": False,
                             "content_not_execution": False, "unresolved": True}
    for block in report["contrasts"].values():
        assert block["status"] == "COMPLETE" and block["scenario"]["ci95_pp"] and block["task"]["ci95_pp"]
        assert block["signflip"]["status"] == "ok" and block["signflip"]["p_value"] is not None
    for block in report["exploratory"]["tgc_contrasts"].values():
        assert block["status"] == "COMPLETE" and block["n_pairs"] == 171


def test_first_rule_in_order_wins(tmp_path: Path):
    report, rc = b2.build_report(results_root=write_matrix(tmp_path, ORDER))
    assert rc == 0
    both = fires(report)
    assert both["prompt_artefact"] and both["execution_matters"]  # two rules hold ...
    assert report["outcome"]["reading"] == "prompt_artefact"  # ... the first is the headline
    heads = [s["outcome"] for s in report["outcome"]["trace"] if s["headline"]]
    assert heads == ["prompt_artefact"]


def test_bound_near_zero_that_flips_across_seeds_is_on_the_boundary_and_falls_through(
        tmp_path: Path, monkeypatch):
    real = b2.j10.cluster_bootstrap_means

    def fake(diffs, clusters, *, n_boot=10_000, seed=20260924):
        if diffs and all(d == 0.375 for d in diffs):  # D1 only
            lo = -0.002 if seed == 7 else 0.005  # +0.50 pp at the registered seed, -0.20 at seed 7
            return sorted([lo] * 300 + [0.375] * (n_boot - 300))
        return real(diffs, clusters, n_boot=n_boot, seed=seed)

    monkeypatch.setattr(b2.j10, "cluster_bootstrap_means", fake)
    report, rc = b2.build_report(results_root=write_matrix(tmp_path, BOUNDARY))
    assert rc == 0
    d1 = report["contrasts"]["D1"]
    assert d1["scenario"]["ci95_pp"][0] == 0.5
    pool = d1["pool04"]
    assert pool["fired"] and pool["on_boundary"] and pool["status"] == "on_boundary"
    assert {b["seed"]: b["lo_pp"] for b in pool["bounds_by_seed"]} == {
        20260924: 0.5, 1: 0.5, 2: 0.5, 3: 0.5, 7: -0.2, 101: 0.5, 999: 0.5}
    assert pool["verdicts_by_seed"] == ["excludes_zero_positive", "includes_zero"]
    # Unadjusted and Holm would both have fired "execution matters" ...
    assert d1["events"]["excludes_zero_positive_unadjusted"] is True and d1["holm_rejects"] is True
    # ... but a boundary contrast satisfies neither reading (Amendment 1 §4).
    assert d1["events"]["excludes_zero_positive"]["held"] is False
    assert d1["events"]["includes_zero"]["held"] is False
    trace = {s["outcome"]: s for s in report["outcome"]["trace"]}
    assert not trace["execution_matters"]["fires"]
    assert "boundary" in trace["execution_matters"]["conditions"][0]["why"]
    assert not trace["content_not_execution"]["fires"]
    assert report["outcome"]["reading"] == "unresolved"
    # D3 = 0 exactly: POOL-04 fires on a bound AT zero but every seed agrees -> stable, not boundary.
    assert report["contrasts"]["D3"]["pool04"]["status"] == "stable"


def _rec(point, lo, hi, p, boundary=False):
    return {"status": "COMPLETE", "point": point / 100, "lo": lo / 100, "hi": hi / 100,
            "p_raw": p, "boundary": boundary}


def test_ci_excluding_zero_does_not_count_when_holm_adjusted_p_exceeds_alpha():
    records = {"D1": _rec(3, 1.5, 6, 0.03), "D2": _rec(1, -3, 5, 0.4),
               "D3": _rec(1, -2, 4, 0.5), "D4": _rec(2, -1.5, 6, 0.3)}
    out = b2.decide_outcome(records)
    # Holm, m = 4: D1 0.03 x 4 = 0.12 > 0.05.
    assert out["holm"]["p"]["D1"]["p_holm"] == pytest.approx(0.12)
    ev = out["events"]["D1"]
    assert ev["excludes_zero_positive_unadjusted"] is True
    assert ev["excludes_zero_positive"]["held"] is False and "Holm" in ev["excludes_zero_positive"]["why"]
    assert out["reading"] == "unresolved"
    records["D1"] = _rec(3, 1.5, 6, 0.01)  # 0.01 x 4 = 0.04: the same CI now survives Holm
    assert b2.decide_outcome(records)["reading"] == "execution_matters"


def test_includes_zero_is_judged_on_the_unadjusted_interval():
    # D4: CI [+1.5, +6] excludes zero, yet Holm does NOT reject it (0.02 x 3 = 0.06). Judging
    # "includes zero" by non-rejection would make it hold and fire the prompt-artefact reading.
    records = {"D1": _rec(1, -3, 5, 0.6), "D2": _rec(1, -4, 6, 0.7),
               "D3": _rec(5, 2, 8, 0.001), "D4": _rec(3, 1.5, 6, 0.02)}
    out = b2.decide_outcome(records)
    assert out["holm"]["p"]["D4"]["rejects_at_alpha"] is False
    assert out["holm"]["p"]["D3"]["rejects_at_alpha"] is True
    incl = out["events"]["D4"]["includes_zero"]
    assert incl["held"] is False and "unadjusted" in incl["why"]
    assert out["reading"] == "unresolved"
    records["D4"] = _rec(2, -1.5, 6, 0.2)  # an interval that really includes zero
    assert b2.decide_outcome(records)["reading"] == "prompt_artefact"


def test_crash_is_dropped_and_makes_the_contrast_incomplete_below_171(tmp_path: Path):
    crash, limit = (TASKS[0], 1), (TASKS[1], 2)
    root = write_matrix(tmp_path, EXECUTION, S={"error_types": {crash: "crash"}},
                        T={"error_types": {limit: "limit"}})
    report, rc = b2.build_report(results_root=root)
    assert rc == 1 and report["status"] == "INCOMPLETE"
    s, t = report["arms"]["S"], report["arms"]["T"]
    assert (s["n_crash"], s["n_scored"], s["complete"]) == (1, 170, False)
    assert s["error_types"] == {"crash": 1, "none": 170}
    assert t["error_types"] == {"limit": 1, "none": 170} and t["complete"] is True  # limit is scored
    c = report["contrasts"]
    for d in ("D1", "D2"):
        assert c[d]["status"] == "INCOMPLETE" and c[d]["n_pairs"] == 170
        assert "scenario" not in c[d] and "p_raw" not in c[d]  # counts only (§3)
        assert "S 170/171 non-crashed (crash 1, missing 0)" in c[d]["reason"]
    for d in ("D0", "D3", "D4"):
        assert c[d]["status"] == "COMPLETE" and c[d]["n_pairs"] == 171
        assert "p_holm" not in c[d]
    assert report["outcome"]["decided"] is False
    assert report["outcome"]["incomplete_contrasts"] == ["D1", "D2"]


def test_duplicate_key_across_two_campaigns_of_one_arm_is_an_error(tmp_path: Path):
    root = write_matrix(tmp_path, EXECUTION)
    write_episode(root / b2.ARM_CAMPAIGNS["S"][1], 1, TASKS[0], 0.5)  # seed 1 in the s3 campaign
    with pytest.raises(b2.PoolingError, match="present in both"):
        b2.load_pooled_arm("S", [root / n for n in b2.ARM_CAMPAIGNS["S"]])
    report, rc = b2.build_report(results_root=root)
    assert rc == 2 and report["status"] == "ERROR"
    assert TASKS[0] in report["errors"][0] and "b2_show_fixed_k_10_s3_20260923" in report["errors"][0]


def test_missing_campaigns_are_named_with_exit_3_and_both_files_written(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "results"
    write_arm(root, "T", lambda i: 0.5, campaigns=(0,))
    write_arm(root, "A", lambda i: 0.25, campaigns=(0,))
    monkeypatch.setattr(b2, "FORBIDDEN_OUT_ROOTS", ())  # tmp_path may itself sit on /scratch
    out = tmp_path / "out" / "b2_decomposition_20260930.report.json"
    rc = b2.main(["--out-root", str(root), "--date", "20260930", "--out", str(out)])
    assert rc == 3
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "MISSING_CAMPAIGNS" and report["date"] == "20260930"
    assert [m["campaign"] for m in report["missing_campaigns"]] == [
        "b1_takeover_fixed_k_10_s3_20260923", "b1_advise_fixed_k_10_fullctx_s3_20260923",
        "b2_show_fixed_k_10_20260923", "b2_show_fixed_k_10_s3_20260923",
        "b2_advise_neutral_fixed_k_10_fullctx_20260923",
        "b2_advise_neutral_fixed_k_10_fullctx_s3_20260923"]
    assert report["contrasts"]["D0"]["status"] == "INCOMPLETE" and report["contrasts"]["D0"]["n_pairs"] == 114
    assert report["outcome"]["decided"] is False
    md = (tmp_path / "out" / "b2_decomposition_20260930.md").read_text(encoding="utf-8")
    assert "MISSING_CAMPAIGNS" in md and "b2_show_fixed_k_10_s3_20260923" in md
    assert json.loads(capsys.readouterr().out)["exit_code"] == 3
    # The raw results root is read-only: an --out under it is refused before anything is written.
    assert b2.main(["--out-root", str(root), "--out", str(root / "x.report.json")]) == 2
    assert not (root / "x.report.json").exists()


def _ev(event_type, actor, step, **payload):
    return {"event_type": event_type, "actor": actor, "step": step, "payload": payload}


def _code(code):
    return {"kind": "CODE", "code": code, "message": None, "ask_reason": None, "confidence": None,
            "raw_output": f"```python\n{code}\n```"}


def test_copy_rate_on_hand_built_events(tmp_path: Path):
    ep1 = [
        _ev("run_start", "system", 0),
        # An aborted first attempt: only the last run_start segment produced the result.
        _ev("intervention", "planner", 10, source="shown_action", correction="```python\nprint(1)\n```",
            shown_kind="CODE"),
        _ev("action", "executor", 10, **_code("print(1)")),
        _ev("run_start", "system", 0),
        _ev("plan", "planner", 0),
        _ev("action", "executor", 1, **_code("print(0)")),
        # 1. reproduced up to whitespace (and a parse retry in between)
        _ev("intervention", "planner", 10, n_interventions=1, forced=True, source="shown_action",
            correction="```python\nfor s in songs:\n    print(s)\n```", shown_kind="CODE"),
        _ev("error", "executor", 10, detail="unparseable reply, retrying"),
        _ev("action", "executor", 10, p_ask=0.1, **_code("for s in songs:\n  print(s)   \n\n")),
        _ev("observation", "environment", 10, text="ok", done=False),
        # 2. the executor writes something else
        _ev("intervention", "planner", 20, n_interventions=2, forced=True, source="shown_action",
            correction="```python\nprint(apis.spotify.show_song_library())\n```", shown_kind="CODE"),
        _ev("action", "executor", 20, **_code("print(apis.spotify.show_playlist_library())")),
        # a live advice intervention is not an S show
        _ev("intervention", "planner", 25, n_asks=1, correction="print(1)", forced=False),
        _ev("action", "executor", 25, **_code("print(1)")),
        # 3. shown, then the episode stops on the token limit: no next action
        _ev("intervention", "planner", 30, n_interventions=3, forced=True, source="shown_action",
            correction="```python\nx = 1\n```", shown_kind="CODE"),
        _ev("error", "system", 30, limit="max_tokens_per_episode"),
    ]
    ep2 = [
        _ev("run_start", "system", 0),
        # 4. a shown COMPLETE, completed
        _ev("intervention", "planner", 10, n_interventions=1, forced=True, source="shown_action",
            correction="COMPLETE", shown_kind="COMPLETE"),
        _ev("action", "executor", 10, kind="COMPLETE", code=None, message=None, ask_reason=None,
            confidence=None, raw_output="COMPLETE"),
    ]
    paths = {}
    for i, events in enumerate((ep1, ep2, None)):
        d = tmp_path / f"ep{i}"
        d.mkdir()
        if events is not None:
            (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        paths[(f"t_{i}", 1)] = d / "events.jsonl"
    cr = b2.copy_rate(paths)
    assert (cr["n_episodes"], cr["n_episodes_without_events"], cr["n_episodes_with_a_shown_action"]) == (3, 1, 2)
    assert (cr["n_shown"], cr["n_followed_by_an_executor_action"], cr["n_copied"]) == (4, 3, 2)
    assert cr["copy_rate"] == 0.5 and cr["copy_rate_among_followed"] == round(2 / 3, 6)
    assert cr["by_shown_kind"] == {"CODE": {"n_shown": 3, "n_followed": 2, "n_copied": 1},
                                   "COMPLETE": {"n_shown": 1, "n_followed": 1, "n_copied": 1}}
    assert cr["n_unrenderable_next_action"] == 0
    assert cr["label"].startswith("EXPLORATORY")


def test_pooled_loading_reproduces_published_c1_on_the_seed_1_2_campaigns():
    # CHAN-C1-02: +6.69 pp, scenario [+1.29, +13.49] at j8's seed 20260915, n = 114
    # [scripts/analysis/j10_report.py P6 dev_reference]. Same pairs, same clusters, or B2's D0
    # would not be an extension of C1.
    root = b2.RESULTS_ROOT
    dirs = {code: root / b2.ARM_CAMPAIGNS[code][0] for code in ("T", "A")}
    if not all(d.is_dir() for d in dirs.values()):
        pytest.skip("hj12 seed 1-2 campaigns not mounted")
    pooled = {code: b2.load_pooled_arm(code, [d]) for code, d in dirs.items()}
    tasks = b2.j10.discover_tasks(pooled, [1, 2])
    arms = {code: b2.j10.a1_arm_episodes(code, pooled[code], tasks, [1, 2]) for code in pooled}
    cmp = b2.j10.a1_contrast(arms["T"]["episodes"], arms["A"]["episodes"], b2.FIELD, seed=20260915)
    assert (len(tasks), cmp["n_pairs"]) == (57, 114)
    assert cmp["scenario"]["diff_pp"] == 6.69
    assert cmp["scenario"]["ci95_pp"] == [1.29, 13.49]


def test_registered_campaigns_on_the_real_results_tree_never_crash(tmp_path: Path, monkeypatch):
    root = b2.RESULTS_ROOT
    if not root.is_dir():
        pytest.skip(f"{root} not mounted")
    names = [n for code in b2.ARM_ORDER for n in b2.ARM_CAMPAIGNS[code]]
    before = {n for n in names if not (root / n).is_dir()}
    monkeypatch.setattr(b2, "FORBIDDEN_OUT_ROOTS", ())
    out = tmp_path / "b2_real.report.json"
    rc = b2.main(["--out-root", str(root), "--out", str(out), "--date", "20260923"])
    after = {n for n in names if not (root / n).is_dir()}
    report = json.loads(out.read_text(encoding="utf-8"))
    reported = {m["campaign"] for m in report["missing_campaigns"]}
    assert after <= reported <= before  # campaigns may land while the test runs
    if reported:
        assert rc == 3 and report["outcome"]["decided"] is False
    else:
        assert rc in (0, 1)
