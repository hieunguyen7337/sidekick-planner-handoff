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


# ---- Amendment 2: a replay that cannot pass its own check (unit DIVRULE, 2026-09-25) -----------------------
def _crash(root: Path, code: str, keys, reason: str = "replay_divergence") -> None:
    """These episodes of arm `code` become crashes whose last attempt's error event carries `reason`."""
    for task, seed in keys:
        ep = root / CAMPAIGNS[code]["campaign"] / SYSTEM[code] / str(seed) / task
        row = json.loads((ep / "result.json").read_text(encoding="utf-8"))
        row.update(error_type="crash", tgc=0.0)
        (ep / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
        events = [{"event_type": "run_start"},
                  {"event_type": "error", "actor": "system", "step": 11, "error_type": "crash",
                   "payload": {"reason": reason}}]
        (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_am2_no_divergent_key_changes_nothing_but_adds_the_block(tmp_path: Path, monkeypatch):
    """(a) and an ordinary crash in a prefix arm (still incomplete): the report equals the pre-amendment one."""
    clean = write_tree(tmp_path / "clean", REPLICATE)
    crashed = write_tree(tmp_path / "crashed", REPLICATE)
    _crash(crashed, "M_zs_6", [("sc03_1", 2)], reason="replay_error")
    new = [build(root) for root in (clean, crashed)]
    monkeypatch.setattr(j11.j10, "a1_am5_arms", lambda arms, *_a, **_k: arms)
    monkeypatch.setattr(j11, "am2_evaluate_contrast", lambda spec, arms, **kw: lp.evaluate_contrast(spec, arms, **kw))
    old = [build(root) for root in (clean, crashed)]
    blocks = []
    for (rep, rc), (base, rc0) in zip(new, old):
        blocks.append(rep.pop("j11_am2_divergence"))
        base.pop("j11_am2_divergence")
        assert rc == rc0 and json.dumps(rep, sort_keys=True, default=str) == json.dumps(base, sort_keys=True, default=str)
        assert {c: (v["n_divergent"], v["keys"]) for c, v in blocks[-1]["per_arm"].items()} == {
            c: (0, []) for c in j11.PREFIX_ARMS}
        assert blocks[-1]["contrasts"] == {} and blocks[-1]["handoff_only_companions"] == {}
    assert new[0][1] == 0 and new[1][1] == 1
    assert new[1][0]["contrasts"]["L5"]["status"] == "INCOMPLETE"
    assert blocks[1]["per_arm"]["M_zs_6"]["n_crash_other"] == 1


def test_am2_one_divergent_key_reads_its_contrasts_on_335_pairs(tmp_path: Path):
    """(b) M^bplus_11 diverges on one key, where A1 scores 1.0: L2-L4 lose it on both sides and are read on 335
    pairs against 335; the gate, L1 and L5 keep 336; the readings are those of the full matrix."""
    key = ("sc00_1", 1)
    root = write_tree(tmp_path, dict(REPLICATE, A1=lambda t, s: 1.0 if (t, s) == key else 0.5))
    _crash(root, "M_bplus_11", [key])
    # R1: §B.1's crash-only resumption run is confirmed by the operator (without it: INCOMPLETE, see test_refill_*).
    report, rc = build(root, divergent_refill_confirmed=True)
    assert rc == 0 and report["status"] == "COMPLETE", report["headline"]
    c = report["contrasts"]
    assert {k: c[k]["n_pairs"] for k in lp.L_IDS} == {"L1": 336, "L2": 335, "L3": 335, "L4": 335, "L5": 336}
    assert {k: c[k]["n_expected"] for k in lp.L_IDS} == {"L1": 336, "L2": 335, "L3": 335, "L4": 335, "L5": 336}
    # L2 = A1 - Mb11 = .50 - .72 on every remaining key: the excluded key's 1.0 is gone from A1 too.
    assert c["L2"]["point_pp"] == -22.0 and c["L2"]["scenario"]["ci95_pp"] == [-22.0, -22.0]
    assert report["gate"]["n_pairs"] == 336 and readings(report) == ALL_SUPPORTED
    arm = report["arms"]["M_bplus_11"]
    assert (arm["n_crash"], arm["complete"]) == (1, True) and not [k for k in arm if k.startswith("_")]
    assert lp.EXPECTED_PAIRS == 114  # lp_report's own globals are restored
    blk = report["j11_am2_divergence"]
    assert blk["per_arm"]["M_bplus_11"] == {"n_divergent": 1, "keys": ["1/sc00_1"], "n_crash_other": 0,
                                            "arm_complete": True}
    assert blk["n_divergent_total"] == 1 and set(blk["contrasts"]) == {"L2", "L3", "L4"}
    assert blk["contrasts"]["L3"] == {"left": "M_bplus_11", "right": "M_bplus_6", "n_excluded": 1,
                                     "excluded_keys": ["1/sc00_1"], "verdict": "ok", "n_pairs": 335,
                                     "n_expected": 335, "status": "COMPLETE"}
    comp = blk["handoff_only_companions"]
    assert comp["L4_handoff_only"]["n_pairs"] == comp["L4_handoff_only"]["n_pairs_h_flag"] == 335
    assert report["reporting_only"]["handoff_only"]["L3_handoff_only"]["goal_pass"]["n_pairs"] == 335
    assert "L5_handoff_only" not in comp


def test_am2_two_prefix_arms_remove_the_union(tmp_path: Path):
    """(c) L5 = M^zs_11 - M^zs_6: {sc00_1/1} and {sc00_1/1, sc01_2/2} remove 2 keys, 334 pairs."""
    root = write_tree(tmp_path, REPLICATE)
    _crash(root, "M_zs_11", [("sc00_1", 1)])
    _crash(root, "M_zs_6", [("sc00_1", 1), ("sc01_2", 2)])
    report, rc = build(root, divergent_refill_confirmed=True)  # R1: §B.1 confirmed by the operator
    assert rc == 0, report["headline"]
    l5 = report["contrasts"]["L5"]
    assert (l5["n_pairs"], l5["n_expected"], l5["status"], l5["point_pp"]) == (334, 334, "COMPLETE", 20.0)
    blk = report["j11_am2_divergence"]
    assert blk["contrasts"]["L5"]["excluded_keys"] == ["1/sc00_1", "2/sc01_2"]
    assert blk["contrasts"]["L5"]["n_excluded"] == 2 and set(blk["contrasts"]) == {"L5"}


def test_am2_more_than_16_divergent_keys_leave_the_contrast_incomplete(tmp_path: Path):
    """(d) 17 keys: L2-L4 draw no reading (the arm itself is complete); 16 keys: read on 320 pairs."""
    for n in (17, 16):
        root = write_tree(tmp_path / str(n), REPLICATE)
        _crash(root, "M_bplus_11", [(t, 1) for t in TASKS[:n]])
        report, rc = build(root, divergent_refill_confirmed=True)  # R1: §B.1 confirmed by the operator
        c = report["contrasts"]
        assert report["arms"]["M_bplus_11"]["complete"] is True
        assert c["L1"]["status"] == c["L5"]["status"] == "COMPLETE"
        if n == 17:
            assert rc == 1 and report["status"] == "INCOMPLETE"
            for k in ("L2", "L3", "L4"):
                assert c[k]["status"] == "INCOMPLETE" and "cap 16" in c[k]["reason"], k
                assert c[k]["reading"] == lp.INCOMPLETE
            assert report["j11_am2_divergence"]["contrasts"]["L2"]["verdict"] == "over_cap"
            assert any(r.startswith("L2 ") and "cap 16" in r for r in report["incomplete"])
        else:
            assert rc == 0 and readings(report) == ALL_SUPPORTED, report["headline"]
            assert {k: c[k]["n_pairs"] for k in ("L2", "L3", "L4")} == {"L2": 320, "L3": 320, "L4": 320}


def test_am2_a_divergent_key_plus_an_ordinary_crash_is_incomplete(tmp_path: Path):
    """(e) §B.3: any other residual crash keeps the contrast incomplete. A divergence-looking crash in A1 (which
    replays no environment) is an ordinary crash and is named in the block."""
    root = write_tree(tmp_path, REPLICATE)
    _crash(root, "M_bplus_11", [("sc00_1", 1)])
    _crash(root, "M_bplus_11", [("sc02_3", 2)], reason="replay_error")
    _crash(root, "A1", [("sc04_1", 1)])
    report, rc = build(root)
    assert rc == 1 and report["arms"]["M_bplus_11"]["complete"] is False
    for k in ("L2", "L3", "L4"):
        assert report["contrasts"][k]["status"] == "INCOMPLETE", k
    blk = report["j11_am2_divergence"]
    assert blk["per_arm"]["M_bplus_11"] == {"n_divergent": 1, "keys": ["1/sc00_1"], "n_crash_other": 1,
                                            "arm_complete": False}
    assert blk["non_replay_divergent"]["keys"] == {"A1": ["1/sc04_1"]}
    assert report["arms"]["A1"]["complete"] is False


# ---- R1 (2026-09-25): the J11 pre-read audit's findings ------------------------------------------------------
def test_n2_not_run_is_decided_before_missing_campaigns_when_the_replay_arms_never_started(tmp_path: Path):
    # §6: above 16 planless C keys no replay arm starts (j11_arm.pbs refuses them), so only C and E exist.
    root = write_tree(tmp_path, {code: REPLICATE[code] for code in ("C", "E")})
    planless(root, [(TASKS[i], 1) for i in range(17)])
    report, rc = build(root)
    assert rc == 1 and report["status"] == "NOT_RUN", report["headline"]
    assert report["headline"] == "NOT RUN (prereg §6 abort rule): 17 planless C keys > cap 16"
    assert len(report["missing_campaigns"]) == 7  # T, A, A1, the four prefix arms: listed, not the status
    assert {r["reading"] for r in report["readings"].values()} == {j11.NOT_RUN}
    assert "## Missing campaigns" in j11.render_markdown(report)


def test_n3_c_below_336_non_crashed_is_not_run_whatever_campaigns_exist(tmp_path: Path):
    root = write_tree(tmp_path, REPLICATE, errors={("C", "sc05_2", 1): "crash"}, skip=("E",))
    report, rc = build(root)
    assert rc == 1 and report["status"] == "NOT_RUN", report["headline"]
    assert report["not_run_reasons"] == ["C has 335/336 non-crashed episodes (crash 1, missing 0)"]
    assert report["planless"]["c_below_matrix"] is True and report["missing_campaigns"]  # E absent: still NOT_RUN
    assert {r["reading"] for r in report["readings"].values()} == {j11.NOT_RUN_C}


def _j10_report(path: Path, p6: str = "supported", split: str = "test_normal", status: str = "COMPLETE",
                **extra) -> Path:
    data = {"protocol": "A1", "status": status, "split": split, "not_the_j10_result": split != "test_normal",
            "label": "J10 A1 registered analysis", "verdicts": {"P1": "supported", "P6": p6},
            "arms": {"planner_alone_cap81": {"goal_pass_mean": 0.8, "n_scored": 336, "n_expected": 336,
                                             "complete": True}}} | extra
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_seam_a_not_run_j10_report_is_read_and_the_combined_statement_is_not_drawn(tmp_path: Path):
    # The J10 / J11 contract: every J10 report carries status, split and verdicts; under NOT_RUN every verdict is
    # "not_run" and the arms carry counts only (j10_report.a1_r2_not_run_report).
    not_run = {"status": "NOT_RUN", "p6": "not_run", "not_the_j10_result": False,
               "verdicts": {p: "not_run" for p in ("P1", "P2", "P3", "P4", "P5", "P6")},
               "not_run_reasons": ["arm planner_alone_cap81 incomplete"],
               "arms": {"planner_alone_cap81": {"n_scored": 300, "n_expected": 336, "complete": False}}}
    root = write_tree(tmp_path / "res", REPLICATE)
    report, rc = build(root, j10_report_path=_j10_report(tmp_path / "j10_nr.json", **not_run))
    comb = report["combined_with_j10"]
    assert rc == 0 and report["status"] == "COMPLETE" and report["readings"]["L1"]["reading"] == "replicates"
    assert comb["status"] == "not_drawn" and comb["j10_not_run"] is True and comb["j10_status"] == "NOT_RUN"
    assert comb["statement"] == "combined statement with J10 P6: not drawn: J10 not run"
    assert comb["j10_not_run_reasons"] == ["arm planner_alone_cap81 incomplete"] and "p6_holds" not in comb
    assert comb["statement"] in j11.render_markdown(report)
    assert report["descriptive"]["ceiling_goal_pass_luna"]["status"] == "not_available"
    # A NOT_RUN report flagged not_the_j10_result is still read (only split and verdicts are checked under NOT_RUN).
    rep2, rc2 = build(root, j10_report_path=_j10_report(tmp_path / "j10_nr2.json", **(not_run | {
        "not_the_j10_result": True})))
    assert rc2 == 0 and rep2["combined_with_j10"]["statement"] == j11.COMBINED_J10_NOT_RUN
    # Still refused: a NOT_RUN report from another split, and any report without a verdicts block.
    for name, kw, why in (("dev_nr.json", not_run | {"split": "dev"}, "its split is 'dev'"),
                          ("noverd.json", not_run | {"verdicts": None}, "no verdicts block"),
                          ("noverd_c.json", {"verdicts": None}, "no verdicts block")):
        read, refusal = j11.load_j10_report(_j10_report(tmp_path / name, **kw))
        assert read is None and why in refusal, (name, refusal)
    rep3, rc3 = j11.build_report(split="test_normal", confirm_heldout_test_split=True, n_boot=B,
                                 results_root=tmp_path / "absent",
                                 j10_report_path=_j10_report(tmp_path / "noverd2.json", **(not_run | {"verdicts": None})))
    assert rc3 == 2 and rep3["status"] == "REFUSED" and "no verdicts block" in rep3["headline"]


def test_n4_combined_statement_with_j10_p6(tmp_path: Path):
    j10_path = _j10_report(tmp_path / "j10.report.json")
    root = write_tree(tmp_path / "res", REPLICATE)
    report, rc = build(root, j10_report_path=j10_path)
    comb = report["combined_with_j10"]
    assert rc == 0 and comb["status"] == "drawn" and (comb["p6_holds"], comb["l1_holds"]) == (True, True)
    assert comb["statement"] == ("J10's P6 is supported (gpt-5.6-luna) and J11's L1 replicates (P27): the channel "
                                 "result holds on held-out data for two planners.")
    assert comb["statement"] in j11.render_markdown(report)
    # The sign-flip agrees with every bootstrap reading here (56 clusters, constant differences): no sentence.
    assert all(r["signflip_disagreement"] is None for r in report["readings"].values())
    # §4's other cases, and the undecided ones, on the pure function.
    st = lambda p6, l1: j11.combined_statement({"verdicts": {"P6": p6}}, l1, registered=True)["statement"]  # noqa: E731
    assert st("supported", "fails_to_replicate").startswith("Exactly one holds: J10's P6 is supported")
    assert st("not_supported", "replicates").startswith("Exactly one holds: J11's L1 replicates")
    assert st("reversed", "not_resolved").endswith("that is the generality result.")
    assert st("on_boundary", "replicates") == "combined statement with J10 P6: not drawn, J10 P6 is 'on_boundary'"
    assert "J11 L1 has no reading" in st("supported", lp.NONE_FAMILY)
    # Absent: pending. A J10 report from another split is refused before anything is read.
    assert j11.combined_statement(None, "replicates", registered=True)["statement"] == j11.COMBINED_PENDING
    report, rc = j11.build_report(split="test_normal", confirm_heldout_test_split=True, n_boot=B,
                                  results_root=tmp_path / "absent",
                                  j10_report_path=_j10_report(tmp_path / "j10_dev.json", split="dev"))
    assert rc == 2 and report["status"] == "REFUSED" and "its split is 'dev'" in report["headline"]


def test_n5_planner_strength_is_descriptive_and_delta_p_is_listed_as_omitted(tmp_path: Path):
    report, rc = build(write_tree(tmp_path, REPLICATE))
    desc = report["descriptive"]
    assert desc["label"].startswith("DESCRIPTIVE: no direction, no verdict")
    assert (desc["ceiling_goal_pass"]["planner"], desc["ceiling_goal_pass"]["goal_pass_mean"]) == ("P27", 0.75)
    assert desc["ceiling_goal_pass_luna"]["status"] == "not_available"
    assert desc["delta_vs_luna"]["status"] == "not_computed"
    amb = {a["id"]: a for a in report["ambiguities"]}["lp_descriptive_delta_and_planner_strength"]
    assert "evaluate_delta" in amb["script_behaviour"] and "NOT computed" in amb["script_behaviour"]
    assert j11._luna_ceiling({"arms": {"planner_alone_cap81": {"goal_pass_mean": 0.8}}})["goal_pass_mean"] == 0.8


def test_n6_the_handoff_occurred_companion_is_printed_beside_each_h_star_row(tmp_path: Path):
    flag = lambda t, s: SCEN[t] < 28  # noqa: E731
    live = lambda t, s: SCEN[t] < 42  # noqa: E731
    design = dict(REPLICATE, M_bplus_6=lambda t, s: 0.5 if SCEN[t] < 42 else 0.6)
    root = write_tree(tmp_path, design, flags={"M_bplus_11": flag, "M_zs_11": lambda t, s: True},
                      live={"M_bplus_11": live})
    report, rc = build(root)
    lines = j11.render_markdown(report).splitlines()
    l3 = [x for x in lines if x.startswith("| L3_handoff_only |")]
    assert len(l3) == 2 and "| h* | 336 | 252 | 22.0 |" in l3[0] and "| handoff_occurred | 336 | 168 | 22.0 |" in l3[1]
    assert sum(1 for x in lines if x.startswith("| L4_handoff_only |")) == 2


def test_n7_a_disagreeing_sign_flip_goes_in_the_readings_sentence(tmp_path: Path):
    spec = lp.CONTRAST_BY_ID["L3"]  # 'greater' at 0: the sign-flip level is 0.025
    c = {"status": "COMPLETE", "scenario": {"lo": 0.004, "hi": 0.08, "point": 0.04}, "signflip": {"p_value": 0.031}}
    sf = j11.signflip_disagreement(c, spec)
    assert (sf["agrees"], sf["bootstrap_side"], sf["signflip_side"], sf["level"]) == (False, "above", None, 0.025)
    assert sf["sentence"] == ("the scenario sign-flip p = 0.031 (greater) does not reject at 0.025 while the "
                              "bootstrap interval excludes +0.00 pp (A1 §5.5; not decision-bearing)")
    assert j11.signflip_disagreement(dict(c, signflip={"p_value": 0.01}), spec)["sentence"] is None
    # L4 ('less' at +7.00 pp): an interval that includes 7 against a rejecting sign-flip.
    l4 = {"status": "COMPLETE", "scenario": {"lo": 0.0, "hi": 0.075, "point": 0.03}, "signflip": {"p_value": 0.02}}
    assert "rejects at 0.025 while the bootstrap interval includes +7.00 pp" in \
        j11.signflip_disagreement(l4, lp.CONTRAST_BY_ID["L4"])["sentence"]
    # In a read: the contrasts' block carries the check; a disagreement's sentence is printed in the reading's.
    report, rc = build(write_tree(tmp_path, REPLICATE))
    assert rc == 0 and report["contrasts"]["L3"]["signflip_disagreement"]["agrees"] is True
    report["readings"]["L3"]["signflip_disagreement"] = sf["sentence"]
    line = next(x for x in j11.render_markdown(report).splitlines() if x.startswith("- L3:"))
    assert line.startswith("- L3: **supported** (") and line.endswith(f"; {sf['sentence']})")


def test_n9_the_sensitivity_counts_and_texts_subtract_divergent_keys(tmp_path: Path):
    root = write_tree(tmp_path, REPLICATE)
    planless(root, [("sc00_1", 2)])
    _crash(root, "M_bplus_11", [("sc01_1", 1)])
    report, rc = build(root, divergent_refill_confirmed=True)
    s = report["sensitivity_planless"]
    assert rc == 0 and s["n_expected"] == 335  # the gate's and L1's
    assert s["gate"]["n_expected"] == 335
    assert {c: s["contrasts"][c]["n_expected"] for c in lp.L_IDS} == {"L1": 335, "L2": 334, "L3": 334, "L4": 334,
                                                                      "L5": 335}
    assert {c: s["contrasts"][c]["n_pairs"] for c in lp.L_IDS} == {"L1": 335, "L2": 334, "L3": 334, "L4": 334,
                                                                   "L5": 335}
    assert "| L3 | 334 | 334 |" in j11.render_markdown(report)
    # The boundary texts, on the pure rewrite: J11 §3, each contrast's own counts.
    sens = {"excluded_keys": ["2/sc00_1"], "gate": {"verdict": "too_weak"},
            "contrasts": {c: {"reading": "not_supported"} for c in lp.L_IDS}}
    before = {"readings": {c: {"reading": "supported", "why": "-"} for c in lp.L_IDS}}
    after = {"readings": dict(before["readings"], L3={"reading": lp.ON_BOUNDARY, "why": "Amendment 4: ..."})}
    n_x = {"gate": 335, **{c: 334 for c in lp.L_IDS}}
    contrasts = {c: {"n_expected": 335} for c in lp.L_IDS}
    _g, read = j11.j11_boundary_texts({"verdict": "passes"}, before, {"verdict": "passes"}, after, sens, contrasts,
                                      n_x, 336)
    assert read["readings"]["L3"]["why"] == (f"{j11.PREREG} §3: reads 'supported' on 335 pairs but 'not_supported' "
                                             "without 2/sc00_1 (334 pairs); on the boundary, never resolved")
    gate, read = j11.j11_boundary_texts({"verdict": "passes"}, before, {"verdict": lp.ON_BOUNDARY}, before, sens,
                                        contrasts, n_x, 336)
    assert gate["why"] == (f"{j11.PREREG} §3: the gate reads 'passes' on 336 pairs but 'too_weak' without 2/sc00_1 "
                           "(335 pairs)")
    assert {r["reading"] for r in read["readings"].values()} == {j11.NONE_GATE_BOUNDARY}


def test_n10_the_am2_block_is_printed_even_when_empty_and_n8_strings_cite_the_right_documents(tmp_path: Path):
    root = write_tree(tmp_path, REPLICATE)
    answer = [{"event_type": "run_start"}, {"event_type": "intervention", "actor": "planner",
                                            "payload": {"forced": False}}]
    for i in range(4):  # 4 / 336 = 1.19 pp on T: L1's reading carries the Amendment 1 §I bound
        ep = root / CAMPAIGNS["T"]["campaign"] / "fixed_k" / "1" / f"sc0{i}_1"
        (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in answer), encoding="utf-8")
    report, rc = build(root)
    md = j11.render_markdown(report)
    assert f"## Replay divergence ({j11.AM2} §B.5)" in md
    assert "Divergent keys over the prefix arms: 0 (cap 16 per contrast)." in md
    assert "| M_bplus_11 | - | 0 | 0 | True |" in md
    assert report["j11_am2_divergence"]["refill_confirmed_by_operator"] is None
    # The three strings that cited the wrong document.
    assert report["holm"]["scope"] == j11.HOLM_SCOPE and f"{j11.PREREG} §3" in j11.HOLM_SCOPE
    assert f"({lp.PREREG}:81-82)" in j11.HOLM_SCOPE
    assert "(J10 A1 Amendment 1 §I, no reading changes)" in next(x for x in md.splitlines() if x.startswith("- L1:"))
    assert "Amendment 4" not in j11.NONE_GATE_BOUNDARY and "J11 §3" in j11.NONE_GATE_BOUNDARY


def test_refill_confirmation_gates_a_divergent_key_on_the_registered_read(tmp_path: Path):
    """Amendment 2 §B.1: a divergent key counts only after a crash-only resumption run, which the files cannot show."""
    root = write_tree(tmp_path, REPLICATE)
    _crash(root, "M_bplus_11", [("sc00_1", 1)])
    report, rc = build(root)
    blk = report["j11_am2_divergence"]
    assert rc == 1 and report["status"] == "INCOMPLETE"
    assert "divergent_keys_need_refill_confirmation:1" in report["incomplete"]
    assert blk["refill_confirmed_by_operator"] is False and blk["resumption_condition"]["required"] is True
    md = j11.render_markdown(report)
    assert "INCOMPLETE until confirmed" in md and "--divergent-refill-confirmed" in md
    report, rc = build(root, divergent_refill_confirmed=True)
    assert rc == 0 and report["status"] == "COMPLETE" and readings(report) == ALL_SUPPORTED
    assert report["j11_am2_divergence"]["refill_confirmed_by_operator"] is True
