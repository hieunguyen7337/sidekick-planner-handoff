"""J11 report: lp_report's gate, L1-L5 and Holm at J11's matrix, on constructed campaigns.

The episode trees are built in the runner's layout (<campaign>/<system>/<seed>/<task>/), 168 tasks in
56 scenarios x seeds {1, 2}, one campaign per arm, named by the campaign_id each J11 config declares
(read here from the real configs, read-only), so every count is the registered 336. Each episode has
a manifest.json recording its split. No real results tree is ever read.

Arm values are constants, so a contrast is an exact, degenerate interval and every expected number
below is arithmetic. The bootstrap runs at B = 200 (N_BOOT is monkeypatched: the registered 10,000
changes no degenerate interval and would only slow the test).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j11_report as j11
from scripts.analysis import lp_report as lp

SCENARIOS = [f"sc{i:02d}" for i in range(56)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2, 3)]
SCEN = {t: int(t[2:4]) for t in TASKS}
CAMPAIGNS = j11.resolve_campaigns("test_normal")
SYSTEM = {"C": "planner_alone", "T": "fixed_k", "A": "fixed_k", "A1": "fixed_k", "E": "executor_alone",
          "M_bplus_6": "prefix_handoff", "M_bplus_11": "prefix_handoff", "M_zs_6": "prefix_handoff",
          "M_zs_11": "prefix_handoff"}
B = 200
# gate C - E = +50; L1 T - A = +25; L2 A1 - Mb11 = -22; L3 Mb11 - Mb6 = +22;
# L4 C - Mb11 = +3 (upper < +7); L5 Mz11 - Mz6 = +20.
REPLICATE = {"E": 0.25, "C": 0.75, "T": 0.75, "A": 0.5, "A1": 0.5, "M_bplus_6": 0.5, "M_bplus_11": 0.72,
             "M_zs_6": 0.4, "M_zs_11": 0.6}
ALL_SUPPORTED = {"L1": "replicates", "L2": "supported", "L3": "supported", "L4": "supported", "L5": "supported"}


@pytest.fixture(autouse=True)
def _small_b(monkeypatch):
    monkeypatch.setattr(j11, "N_BOOT", B)


def write_episode(cdir: Path, system: str, seed: int, task: str, gp: float, *, split: str,
                  error_type=None, events=None) -> None:
    dest = cdir / system / str(seed) / task
    dest.mkdir(parents=True, exist_ok=True)
    row = {"task_id": task, "seed": seed, "system": system, "goal_pass_rate": gp,
           "tgc": 0.0 if error_type else gp, "success": gp == 1.0, "steps": 12, "error_type": error_type}
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (dest / "manifest.json").write_text(json.dumps({"provenance": {"split": split}}) + "\n", encoding="utf-8")
    if events is not None:
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def write_tree(root: Path, design: dict, *, split: str = "test_normal", tasks=TASKS, campaigns=CAMPAIGNS,
               errors=None, flags=None, skip=(), split_of=None, live=None) -> Path:
    """design[code] is a value or f(task, seed); flags[code] is f(task, seed) -> handoff_occurred, written
    in the handoff record (effective_m 11). live[code] is f(task, seed) -> the executor took control (an
    executor action at step 12, so h* = 1); by default live equals the flag."""
    for code, value in design.items():
        if code in skip:
            continue
        fn = value if callable(value) else (lambda t, s, v=value: v)
        for seed in (1, 2):
            for task in tasks:
                ev = None
                if flags and code in flags:
                    ev = [{"event_type": "run_start"},
                          {"event_type": "report", "actor": "system", "step": 11,
                           "payload": {"handoff_occurred": flags[code](task, seed), "effective_m": 11}}]
                    if ((live or {}).get(code) or flags[code])(task, seed):
                        ev.append({"event_type": "action", "actor": "executor", "step": 12,
                                   "payload": {"kind": "CODE", "code": "x"}})
                write_episode(root / campaigns[code]["campaign"], SYSTEM[code], seed, task, fn(task, seed),
                              split=(split_of or {}).get(code, split),
                              error_type=(errors or {}).get((code, task, seed)), events=ev)
    return root


def planless(root: Path, keys, campaigns=CAMPAIGNS) -> None:
    """C episodes (already scored) whose last attempt wrote no plan."""
    for task, seed in keys:
        ep = root / campaigns["C"]["campaign"] / "planner_alone" / str(seed) / task
        (ep / "events.jsonl").write_text(json.dumps({"event_type": "run_start"}) + "\n"
                                         + json.dumps({"event_type": "parse_error"}) + "\n", encoding="utf-8")


def build(root: Path, **kw):
    return j11.build_report(split="test_normal", confirm_heldout_test_split=True, results_root=root,
                            n_boot=B, **kw)


def readings(report: dict) -> dict:
    return {c: r["reading"] for c, r in report["readings"].items()}


def test_campaigns_are_read_from_the_j11_configs_and_e_is_j10_arm_1b():
    assert CAMPAIGNS["C"]["campaign"] == "j11_planner_alone_cap81_qwen38_27b_20260924"
    assert CAMPAIGNS["E"] == {"config": "configs/j10_executor_alone_bplus.yaml",
                              "campaign": "j10_executor_alone_bplus_20260924"}
    assert {c: v["campaign"] for c, v in CAMPAIGNS.items() if c != "E"} == {
        c: Path(p).stem + "_20260924" for c, p in j11.ARM_CONFIGS.items()}
    dev = j11.resolve_campaigns("dev")
    assert {c: v["campaign"] for c, v in dev.items()} == {
        c: v["campaign"] + "_dryrun" for c, v in CAMPAIGNS.items()}
    # lp_report's contrasts name exactly the J11 arms plus E: nothing is read that J11 did not run.
    used = {lp.GATE["left"], lp.GATE["right"]} | {s[k] for s in lp.CONTRASTS for k in ("left", "right")}
    assert used == set(j11.ALL_ARMS)


def test_registered_read_gate_contrasts_and_holm_at_336_pairs(tmp_path: Path):
    report, rc = build(write_tree(tmp_path, REPLICATE))
    assert rc == 0 and report["status"] == "COMPLETE", report["headline"]
    assert report["label"] == "J11 registered read (test_normal)"
    assert report["settings"]["expected_pairs"] == 336 and report["n_tasks_observed"] == 168
    g = report["gate"]
    # By hand: C - E = .75 - .25 on every key.
    assert (g["point_pp"], g["n_pairs"], g["verdict"]) == (50.0, 336, "passes")
    assert (g["scenario"]["n_clusters"], g["task"]["n_clusters"]) == (56, 168)
    c = report["contrasts"]
    assert {k: c[k]["n_pairs"] for k in lp.L_IDS} == {k: 336 for k in lp.L_IDS}
    # L1 = .75 - .50 everywhere: a degenerate interval at +25, and no bootstrap draw <= 0 or >= 0 on
    # the other side, so the two-sided p is 2 x min(0, 1) = 0.
    assert c["L1"]["scenario"]["ci95_pp"] == [25.0, 25.0] and c["L1"]["p_raw"] == 0.0
    # L4 = .75 - .72 = +3 against +7: p = 2 x share of draws >= +7 pp = 0.
    assert c["L4"]["scenario"]["ci95_pp"] == [3.0, 3.0] and c["L4"]["p_raw"] == 0.0
    assert c["L4"]["threshold_pp"] == 7.0 and c["L4"]["pool04"]["status"] == "not_fired"
    assert c["L1"]["signflip"]["n_clusters"] == 56
    assert report["holm"]["m"] == 5 and report["holm"]["family"] == list(lp.L_IDS)
    assert {k: c[k]["p_holm"] for k in lp.L_IDS} == {k: 0.0 for k in lp.L_IDS}
    assert readings(report) == ALL_SUPPORTED
    assert report["planless"]["n_keys"] == 0 and report["sensitivity_planless"] is None
    # lp_report's own globals are back at LP's dev matrix.
    assert (lp.N_TASKS, lp.EXPECTED_PAIRS, lp.SEEDS) == (57, 114, (1, 2))
    assert lp.SENSITIVITY_EXCLUDE == {"P27": (("6171bbc_3", 2),)}


def test_holm_step_by_hand_through_read_family():
    def rec(point, lo, hi, p):
        return {"status": "COMPLETE", "point": point / 100, "lo": lo / 100, "hi": hi / 100, "p_raw": p,
                "boundary": False}

    records = {"L1": rec(10, 2, 18, 0.01), "L2": rec(-10, -18, -2, 0.04), "L3": rec(10, 2, 18, 0.03),
               "L4": rec(0, -5, 5, 0.005), "L5": rec(10, 2, 18, 0.02)}
    out = j11.read_family({"verdict": "passes"}, records, 336)
    # Holm step-down by hand: sorted p .005 (L4), .01 (L1), .02 (L5), .03 (L3), .04 (L2) times 5, 4, 3,
    # 2, 1 = .025, .04, .06, .06, .04, each raised to the running maximum: .025, .04, .06, .06, .06.
    assert {k: v["p_holm"] for k, v in out["holm"]["p"].items()} == pytest.approx(
        {"L1": 0.04, "L2": 0.06, "L3": 0.06, "L4": 0.025, "L5": 0.06})
    assert {k: v["reading"] for k, v in out["readings"].items()} == {
        "L1": "replicates", "L2": "not_supported", "L3": "not_supported", "L4": "supported",
        "L5": "not_supported"}
    assert "Holm p = 0.06 > 0.05" in out["readings"]["L2"]["why"].replace("but ", "")
    # An unevaluable gate: no reading, and lp_report's "114" reads as this matrix's 336.
    out = j11.read_family({"verdict": "incomplete"}, records, 336)
    assert {v["reading"] for v in out["readings"].values()} == {lp.NONE_GATE_UNEVALUABLE}
    assert "lacks 336 non-crashed pairs" in out["readings"]["L1"]["why"]


def test_handoff_only_companions_limit_blocks_and_planless_sensitivity(tmp_path: Path):
    half = lambda t, s: SCEN[t] < 28  # noqa: E731 -- handoff in 28 of 56 scenarios
    design = dict(REPLICATE,
                  M_bplus_6=lambda t, s: 0.5 if SCEN[t] < 28 else 0.6,
                  T=lambda t, s: 1.0 if (t, s) == ("sc00_1", 2) else 0.75)
    limits = {("T", f"sc01_{j}", 1): "limit" for j in (1, 2, 3)}
    root = write_tree(tmp_path, design, errors=limits,
                      flags={"M_bplus_11": half, "M_zs_11": lambda t, s: True})
    planless(root, [("sc00_1", 2)])
    report, rc = build(root)
    assert rc == 0, report["headline"]
    c = report["contrasts"]
    # L3 = .72 - .50 = +.22 on 168 handoff keys and .72 - .60 = +.12 on 168 silenced ones: +17 in all.
    assert c["L3"]["point_pp"] == 17.0 and c["L3"]["reading"] == "supported"
    ho = report["reporting_only"]["handoff_only"]
    l3 = ho["L3_handoff_only"]["goal_pass"]
    assert (l3["n_pairs"], l3["n_handoff"], l3["n_silenced"]) == (336, 168, 168)
    assert (l3["handoff_only"]["diff_pp"], l3["silenced"]["diff_pp"], l3["all"]["diff_pp"]) == (22.0, 12.0, 17.0)
    assert "ni" not in l3 and l3["vs_threshold"] == {"threshold_pp": 0.0, "lower_above": True, "descriptive": True}
    # L4's companion is M^bplus_11 - C = -3 on every handoff key: lower -3 > -7, far from the margin.
    l4 = ho["L4_handoff_only"]["goal_pass"]
    assert l4["handoff_only"]["diff_pp"] == -3.0
    assert (l4["ni"]["reading"], l4["ni"]["lower_bound_pp"], l4["ni"]["fired"]) == ("holds", -3.0, False)
    l5 = ho["L5_handoff_only"]["goal_pass"]
    assert (l5["n_handoff"], l5["handoff_only"]["diff_pp"]) == (336, 20.0)
    # L1: three T episodes hit the limit (goal_pass kept), and (sc00_1, 2) is planless with T = 1.
    lim = report["reporting_only"]["L1_limit"]
    assert lim["limit_rates"]["T"] == {"n_scored": 336, "n_limit": 3, "limit_rate": round(3 / 336, 6)}
    assert lim["limit_rates"]["A"]["n_limit"] == 0
    assert (lim["limit_split"]["n_limit_pairs"], lim["limit_split"]["n_neither"]) == (3, 333)
    assert lim["limit_split"]["mean_on_limit_pairs"]["diff_pp"] == 25.0
    # limit-as-0: (332 x .25 + .50 + 3 x (0 - .50)) / 336 = 82.0 / 336.
    assert lim["limit_as_zero"]["scenario"]["diff_pp"] == round(82.0 / 336 * 100, 2)
    assert c["L1"]["point_pp"] == round((335 * 0.25 + 0.5) / 336 * 100, 2)
    s = report["sensitivity_planless"]
    assert report["planless"]["keys"] == ["2/sc00_1"] and report["planless"]["cap"] == 16
    assert s["excluded_keys"] == ["2/sc00_1"] and s["n_expected"] == 335
    assert s["gate"]["n_pairs"] == 335 and s["contrasts"]["L1"]["point_pp"] == 25.0
    assert readings(report) == ALL_SUPPORTED  # the same without the key: nothing on the boundary
    md = j11.render_markdown(report)
    assert "Sensitivity without 2/sc00_1 (335 pairs)" in md and "L4_handoff_only" in md
    # h* is primary; with live == flag here, the flag sensitivity carries the same numbers.
    assert ho["L3_handoff_only"]["h"] == "h_star"
    flag3 = report["reporting_only"]["handoff_only_h_flag"]["L3_handoff_only"]
    assert flag3["h"] == "h_flag" and flag3["goal_pass"]["handoff_only"]["diff_pp"] == 22.0


def test_handoff_companions_read_h_star_with_the_flag_as_sensitivity(tmp_path: Path):
    # M^bplus_11's flag is true in scenarios 0-27 only, but the executor took control in scenarios 0-41:
    # 84 keys (scenarios 28-41) are live but unflagged, as when the source planner stopped within m
    # executed actions without finishing. M^bplus_6 scores .5 there and .6 elsewhere.
    flag = lambda t, s: SCEN[t] < 28  # noqa: E731
    live = lambda t, s: SCEN[t] < 42  # noqa: E731
    design = dict(REPLICATE, M_bplus_6=lambda t, s: 0.5 if SCEN[t] < 42 else 0.6)
    root = write_tree(tmp_path, design, flags={"M_bplus_11": flag, "M_zs_11": lambda t, s: True},
                      live={"M_bplus_11": live})
    report, rc = build(root)
    assert rc == 0, report["headline"]
    ro = report["reporting_only"]
    l3 = ro["handoff_only"]["L3_handoff_only"]["goal_pass"]
    # h*: 252 live keys at .72 - .50 = +22; the flag: its 168 keys, the same +22 (all at .5 on m6).
    assert (l3["n_handoff"], l3["n_silenced"], l3["handoff_only"]["diff_pp"]) == (252, 84, 22.0)
    l3f = ro["handoff_only_h_flag"]["L3_handoff_only"]["goal_pass"]
    assert (l3f["n_handoff"], l3f["n_silenced"]) == (168, 168)
    # Silenced differ: h* leaves scenarios 42-55 (.72 - .60 = +12); the flag also counts 28-41 (+22).
    assert l3["silenced"]["diff_pp"] == 12.0 and l3f["silenced"]["diff_pp"] == round((84 * 22 + 84 * 12) / 168, 2)
    counts = ro["handoff_control_counts"]["M_bplus_11"]
    assert (counts["n_h_flag_true"], counts["n_live_but_unflagged"], counts["n_terminal"]) == (168, 84, 84)
    assert ro["handoff_indicator"]["primary"] == "h_star"
    assert "handoff_only_h_flag" in j11.render_markdown(report)


def test_executor_asks_answered_live_are_counted_with_the_amendment_1_bound(tmp_path: Path):
    root = write_tree(tmp_path, REPLICATE)
    run, ask = {"event_type": "run_start"}, {"event_type": "ask", "actor": "executor", "payload": {"n_asks": 1}}
    answer = {"event_type": "intervention", "actor": "planner", "payload": {"forced": False, "correction": "x"}}
    forced = {"event_type": "intervention", "actor": "planner", "payload": {"forced": True, "correction": "y"}}
    logs = {
        # T: four episodes, one answer each -> 4 / 336 = 1.19 pp, L1's reading carries the bound.
        **{("T", "fixed_k", f"sc0{i}_1", 1): [run, ask, answer] for i in range(4)},
        # M^bplus_6: 1 + 3 answers in two episodes (0.60 pp); an answer in an earlier attempt and a forced
        # intervention are not counted.
        ("M_bplus_6", "prefix_handoff", "sc10_1", 1): [run, ask, answer],
        ("M_bplus_6", "prefix_handoff", "sc11_2", 2): [run, ask, answer, ask, answer, ask, answer],
        ("M_bplus_6", "prefix_handoff", "sc12_3", 1): [run, ask, answer, run],
        ("M_bplus_6", "prefix_handoff", "sc13_1", 2): [run, forced],
    }
    for (code, system, task, seed), events in logs.items():
        ep = root / CAMPAIGNS[code]["campaign"] / system / str(seed) / task
        (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    report, rc = build(root)
    assert rc == 0 and readings(report) == ALL_SUPPORTED  # reporting only: nothing changes
    asks = report["reporting_only"]["executor_asks"]
    t, m6 = asks["per_arm"]["T"], asks["per_arm"]["M_bplus_6"]
    assert (t["n_episodes_with_answered_ask"], t["n_answered_ask_calls"], t["bound_pp"]) == (4, 4, 1.19)
    assert (m6["n_episodes_with_answered_ask"], m6["n_scored_episodes_with_answered_ask"],
            m6["n_answered_ask_calls"], m6["bound_pp"]) == (2, 2, 4, 0.6)
    assert m6["episodes"] == ["1/sc10_1", "2/sc11_2"] and m6["n_episodes_without_event_log"] == 332
    assert asks["per_arm"]["C"]["bound_pp"] == 0.0 and asks["per_arm"]["C"]["n_episodes_without_event_log"] == 336
    pc = asks["per_contrast"]
    assert (pc["L1"]["max_bound_pp"], pc["L1"]["bound_reaches_1pp"]) == (1.19, True)
    assert (pc["L3"]["right"], pc["L3"]["bound_reaches_1pp"]) == ({"arm": "M_bplus_6", "bound_pp": 0.6}, False)
    assert not pc["gate"]["bound_reaches_1pp"] and asks["denominator"] == 336
    md = j11.render_markdown(report)
    l1_line = next(x for x in md.splitlines() if x.startswith("- L1:"))
    assert "bound the arm means at T 1.19 pp, A 0.00 pp" in l1_line
    assert "bound the arm means" not in next(x for x in md.splitlines() if x.startswith("- L3:"))
    assert "| M_bplus_6 | 2 (2) | 4 | 0.6 | 332 |" in md


def test_a_crash_leaves_l1_incomplete_and_the_family_unread(tmp_path: Path):
    root = write_tree(tmp_path, REPLICATE, errors={("T", "sc05_2", 1): "crash"})
    report, rc = build(root)
    assert rc == 1 and report["status"] == "INCOMPLETE"
    l1 = report["contrasts"]["L1"]
    assert l1["status"] == "INCOMPLETE" and l1["n_pairs"] == 335 and l1["reading"] == lp.INCOMPLETE
    assert "lack 336 non-crashed pairs" in report["readings"]["L1"]["why"]
    assert {report["readings"][c]["reading"] for c in ("L2", "L3", "L4", "L5")} == {lp.NONE_FAMILY}
    assert report["holm"] is None and report["gate"]["verdict"] == "passes"
    assert report["reporting_only"]["L1_limit"]["status"] == "not_computed"


def test_split_provenance_other_than_test_normal_makes_the_read_incomplete(tmp_path: Path):
    report, rc = build(write_tree(tmp_path, REPLICATE, split_of={"A": "dev"}))
    assert rc == 1
    assert any(r.startswith("split_provenance_mismatch:A:") for r in report["incomplete"])
    assert report["gate"]["status"] == "INCOMPLETE"  # no arm is complete on a refused matrix


def test_abort_rule_above_16_planless_c_keys(tmp_path: Path):
    root = write_tree(tmp_path, REPLICATE)
    planless(root, [(TASKS[i], 1) for i in range(17)])
    report, rc = build(root)
    assert rc == 1 and report["status"] == "NOT_RUN"
    assert report["planless"]["n_keys"] == 17 and report["planless"]["abort_rule_fired"] is True
    assert {r["reading"] for r in report["readings"].values()} == {j11.NOT_RUN}


def test_a_missing_campaign_is_named(tmp_path: Path):
    report, rc = build(write_tree(tmp_path, REPLICATE, skip=("E",)))
    assert rc == 3 and report["status"] == "MISSING_CAMPAIGNS"
    assert [m["campaign"] for m in report["missing_campaigns"]] == ["j10_executor_alone_bplus_20260924"]


@pytest.mark.parametrize("kw,why", [
    (dict(split="test_challenge", confirm_heldout_test_split=True), "stays sealed"),
    (dict(split="test_normal"), "without --confirm-heldout-test-split"),
    (dict(split="test_normal", confirm_heldout_test_split=True, plumbing_check=True), "--plumbing-check on test_normal"),
    (dict(split="test_normal", confirm_heldout_test_split=True, n_boot=100), "non-registered bootstrap"),
    (dict(split="dev"), "without --plumbing-check"),
    (dict(split="dev", plumbing_check=True, confirm_heldout_test_split=True), "refused with --split dev"),
    (dict(split="train", plumbing_check=True), "unknown split"),
])
def test_refusals_before_anything_is_read(tmp_path: Path, kw: dict, why: str):
    kw = {"n_boot": B, **kw}
    report, rc = j11.build_report(results_root=tmp_path / "absent", **kw)
    assert rc == 2 and report["status"] == "REFUSED" and why in report["headline"]


def test_dev_plumbing_check_reads_only_dryrun_campaigns_and_refuses_heldout_paths(tmp_path: Path):
    dev = j11.resolve_campaigns("dev")
    c_tasks = ["sc00_1", "sc00_2", "sc00_3"]
    root = write_tree(tmp_path / "res", {k: v for k, v in REPLICATE.items() if k != "E"}, split="dev",
                      tasks=c_tasks, campaigns=dev)
    write_tree(root, {"E": 0.25}, split="dev", tasks=c_tasks + ["sc01_1"], campaigns=dev)  # a wider J10 dry run
    report, rc = j11.build_report(split="dev", plumbing_check=True, results_root=root, n_boot=B)
    assert rc == 0, report["headline"]
    assert report["headline"].startswith("PLUMBING CHECK, NOT A RESULT.")
    assert report["settings"]["expected_pairs"] == 6 and report["gate"]["n_pairs"] == 6
    held = tmp_path / "test_normal_copy"
    report, rc = j11.build_report(split="dev", plumbing_check=True, results_root=held, n_boot=B)
    assert rc == 2 and "contains 'test_normal'" in report["headline"]


def test_main_writes_the_registered_outputs_and_refuses_an_out_dir_in_the_results_tree(tmp_path: Path, capsys):
    root = write_tree(tmp_path / "res", REPLICATE)
    out = tmp_path / "campaign_results"
    rc = j11.main(["--split", "test_normal", "--confirm-heldout-test-split", "--results-root", str(root),
                   "--out-dir", str(out), "--n-boot", str(B)])
    assert rc == 0
    data = json.loads((out / "j11_lp2_test_normal.report.json").read_text(encoding="utf-8"))
    assert data["status"] == "COMPLETE" and data["gate"]["point_pp"] == 50.0
    assert "## Gate and L1-L5" in (out / "j11_lp2_test_normal.md").read_text(encoding="utf-8")
    rc = j11.main(["--split", "test_normal", "--confirm-heldout-test-split", "--results-root", str(root),
                   "--out-dir", str(root / "x"), "--n-boot", str(B)])
    assert rc == 2 and "REFUSED" in capsys.readouterr().out


def test_lp_matrix_restores_lp_report_globals_even_on_error():
    before = (lp.N_TASKS, lp.SEEDS, lp.EXPECTED_PAIRS, lp.SENSITIVITY_EXCLUDE)
    with pytest.raises(RuntimeError):
        with j11.lp_matrix(168, (1, 2), (("t", 1),)):
            assert (lp.N_TASKS, lp.EXPECTED_PAIRS, lp.SENSITIVITY_EXCLUDE) == (168, 336, {"P27": (("t", 1),)})
            raise RuntimeError("x")
    assert (lp.N_TASKS, lp.SEEDS, lp.EXPECTED_PAIRS, lp.SENSITIVITY_EXCLUDE) == before
    with j11.lp_matrix(3, (1, 2)):
        assert lp.SENSITIVITY_EXCLUDE == {} and lp.EXPECTED_PAIRS == 6
