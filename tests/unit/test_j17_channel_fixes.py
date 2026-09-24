"""J17 channel fixes: every new function on hand-built data, expected values worked by hand.

The episode trees use the runner's layout (<campaign>/fixed_k/<seed>/<task>/result.json with
events.jsonl and manifest.json beside it): 4 scenarios x 3 tasks, seeds {1, 2} in an arm's
first campaign and {3} in its second, pooled exactly as b2_decomposition pools them, so each
channel contrast has 36 pairs (35 where a crash is dropped).

Arm values (goal_pass; TGC equals goal_pass unless the episode has an error_type, then 0):
  takeover_k10        0.75 everywhere; hits the limit once, on (sc03_1, 1)
  advise_k10          0.25 on the 9 limit keys A_LIMIT (sc00_1, sc01_1, sc02_1 x 3 seeds), else 0.5
  advise_k10_neutral  0.5 everywhere
  show_k10            0.75 everywhere; (sc03_3, 3) crashed
  advise_k1           0.5, seeds 1-2 only
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j17_channel_fixes as j17

SCENARIOS = [f"sc{i:02d}" for i in range(4)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2, 3)]
CAMPAIGN_SEEDS = ((1, 2), (3,))
N_BOOT = 200
A_LIMIT = {(f"sc0{i}_1", s) for i in range(3) for s in (1, 2, 3)}
T_LIMIT = {("sc03_1", 1)}
S_CRASH = ("sc03_3", 3)


def _ev(event_type, actor, step, usage=None, ts=None, **payload):
    ev = {"event_type": event_type, "actor": actor, "step": step, "payload": payload}
    if usage is not None:
        ev["usage"] = usage
    if ts is not None:
        ev["ts"] = ts
    return ev


def _code(code):
    return {"kind": "CODE", "code": code, "message": None, "ask_reason": None, "confidence": None,
            "raw_output": f"```python\n{code}\n```"}


COMPLETE = {"kind": "COMPLETE", "code": None, "message": None, "ask_reason": None, "confidence": None,
            "raw_output": "COMPLETE"}

# Lengths by hand: "Try:\n" 5 + "```python\n" 10 + "print(1)\n" 9 + "```" 3 = 27;
# "Check the API docs." = 19; "```text\n" 8 + "COMPLETE\n" 9 + "```" 3 = 20.
A1, A2, A3 = "Try:\n```python\nprint(1)\n```", "Check the API docs.", "```text\nCOMPLETE\n```"
# "```python\n" 10 + "print(3)\n" 9 + "```" 3 = 22; "no code here" = 12.
N1, N2 = "```python\nprint(3)\n```", "no code here"
EVENTS = {
    "advise_k10": {
        ("sc00_1", 1): [
            _ev("run_start", "system", 0),
            _ev("intervention", "planner", 10, correction=A1, forced=True),  # copied: its python block
            _ev("action", "executor", 10, **_code("print(1)")),
            _ev("intervention", "planner", 20, correction=A2, forced=True),  # not copied
            _ev("action", "executor", 20, **_code("x = 1")),
        ],
        ("sc01_2", 1): [
            _ev("run_start", "system", 0),
            _ev("intervention", "planner", 10, correction=A3, forced=True),  # fenced, but ```text != COMPLETE
            _ev("action", "executor", 10, **COMPLETE),
        ],
    },
    "advise_k10_neutral": {
        ("sc00_2", 1): [_ev("run_start", "system", 0), _ev("intervention", "planner", 10, correction=N1),
                        _ev("action", "executor", 10, **_code("print(3)"))],  # copied
        ("sc02_2", 2): [_ev("run_start", "system", 0), _ev("intervention", "planner", 10, correction=N2)],
    },
    "show_k10": {
        ("sc00_1", 1): [
            _ev("run_start", "system", 0),
            _ev("intervention", "planner", 10, source="shown_action", shown_kind="CODE",
                correction="```python\nprint(2)\n```"),
            _ev("action", "executor", 10, **_code("print(2)")),
            _ev("intervention", "planner", 20, source="shown_action", shown_kind="COMPLETE", correction="COMPLETE"),
            _ev("action", "executor", 20, **COMPLETE),
        ],
        # The crashed episode is not an outcome: its fenced show must not be counted.
        S_CRASH: [_ev("run_start", "system", 0),
                  _ev("intervention", "planner", 10, source="shown_action", shown_kind="CODE",
                      correction="```python\nprint(9)\n```")],
    },
}


def write_episode(campaign_dir: Path, seed: int, task_id: str, gp: float, *, error_type=None, success=None,
                  events=None, created_at=None) -> Path:
    dest = campaign_dir / "fixed_k" / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {"run_id": f"{campaign_dir.name}/fixed_k/{seed}/{task_id}", "task_id": task_id, "seed": seed,
           "system": "fixed_k", "goal_pass_rate": gp, "tgc": 0.0 if error_type else gp,
           "success": (gp == 1.0 and error_type is None) if success is None else success,
           "steps": 12, "n_planner_calls": 2, "error_type": error_type}
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    if events is not None:
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    if created_at is not None:
        (dest / "manifest.json").write_text(json.dumps({"created_at": created_at}), encoding="utf-8")
    return dest


def write_arm(root: Path, label: str, gp, *, errors=None) -> None:
    names = j17.ARM_CAMPAIGNS[label]
    for idx, name in enumerate(names):
        for seed in (CAMPAIGN_SEEDS[idx] if len(names) > 1 else (1, 2)):
            for task in TASKS:
                key = (task, seed)
                write_episode(root / name, seed, task, gp(key), error_type=(errors or {}).get(key),
                              events=EVENTS.get(label, {}).get(key))


LEDGER = """# Claims ledger

| claim_id | claim (one sentence) | artifact path | JSON key or line | status | figure |
|---|---|---|---|---|---|
| A-01 | x | `a.json` | `k` | registered | - |
| A-02 | the pairs are `action|executor` | `a.json` | `k` | **registered (F2)**, T5 | - |
| A-03 | y | `a.json` | `k` | exploratory (F3) | - |

## B
| claim_id | claim (one sentence) | artifact path | JSON key or line | status | figure |
|---|---|---|---|---|---|
| B-01 | z | `b.json` | `find ... -exec cat | jq -s` | exploratory | - |
| B-02 | w | `b.json` | `k` | pending H0 | - |
| B-03 | v | `b.json` | `k` | method; qualifies B-01 | - |
"""


def write_census_inputs(directory: Path) -> tuple[Path, Path]:
    cfg = {"config_path": "configs/hj12_prefix_m10.yaml"}
    index = {"purpose": "every campaign a report references", "campaigns": {
        "hj12_prefix_m10_20260922": {"present": True, "n_tasks": 57, "from_config": cfg},
        "hj12_prefix_m10_20260923": {"present": True, "n_tasks": 57, "from_config": cfg},  # same arm
        "hj4b_fixed_k_dev_20260917": {"present": True, "n_tasks": 57, "from_config": {"config_match": "none"}},
        "hj2b_planner_train_20260916": {"present": True, "n_tasks": 90, "from_config": {"config_path": "c.yaml"}},
        "hj12_prefix_m3_20260922": {"present": False, "n_tasks": None, "from_config": None},
    }}
    (directory / "campaign_index.json").write_text(json.dumps(index), encoding="utf-8")
    (directory / "claims_ledger.md").write_text(LEDGER, encoding="utf-8")
    return directory / "campaign_index.json", directory / "claims_ledger.md"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("results")
    write_arm(root, "takeover_k10", lambda k: 0.75, errors={k: "limit" for k in T_LIMIT})
    write_arm(root, "advise_k10", lambda k: 0.25 if k in A_LIMIT else 0.5, errors={k: "limit" for k in A_LIMIT})
    write_arm(root, "advise_k10_neutral", lambda k: 0.5)
    write_arm(root, "show_k10", lambda k: 0.75, errors={S_CRASH: "crash"})
    write_arm(root, "advise_k1", lambda k: 0.5)
    # One limit-rate-only arm, 24 episodes, 2 of them at the limit; the other eight are absent.
    for seed in (1, 2):
        for task in TASKS:
            write_episode(root / "hj8_executor_alone_bplus_20260919", seed, task, 0.5,
                          error_type="limit" if (task, seed) in {("sc00_1", 1), ("sc01_1", 2)} else None)
    index, ledger = write_census_inputs(tmp_path_factory.mktemp("docs"))
    return j17.build_report(results_root=root, n_boot=N_BOOT, seed=7, index_path=index, ledger_path=ledger)


def test_limit_split_contributions_sum_to_the_whole(built):
    report, code = built
    assert code == 0 and report["status"] == "COMPLETE"
    d0 = report["limits"]["split"]["D0"]
    # d = 0.5 on the 9 A_LIMIT pairs and 0.25 on (sc03_1, 1): 10 limit pairs summing to 4.75; the
    # 26 others are 0.25 each, summing to 6.5. Whole 11.25 / 36 = 31.25 pp; contributions
    # 4.75 / 36 = 13.19 and 6.5 / 36 = 18.06, which sum to 31.25; means 47.5 and 25.0.
    assert d0["label"] == "post-treatment mechanism, not a corrected estimate"
    assert (d0["n_pairs"], d0["n_limit_left"], d0["n_limit_right"]) == (36, 1, 9)
    assert d0["whole"]["diff_pp"] == 31.25
    assert (d0["either_limit"]["n"], d0["either_limit"]["mean_diff_pp"], d0["either_limit"]["contribution_pp"]) \
        == (10, 47.5, 13.19)
    assert (d0["neither"]["n"], d0["neither"]["mean_diff_pp"], d0["neither"]["contribution_pp"]) == (26, 25.0, 18.06)
    assert d0["contributions_sum_pp"] == d0["whole"]["diff_pp"] == 31.25
    for part in ("either_limit", "neither"):
        for key in ("mean_diff_ci95_pp_scenario", "mean_diff_ci95_pp_task",
                    "contribution_ci95_pp_scenario", "contribution_ci95_pp_task"):
            lo, hi = d0[part][key]
            assert lo <= hi
    # The neither pairs all differ by exactly 0.25, so their mean's interval is degenerate.
    assert d0["neither"]["mean_diff_ci95_pp_scenario"] == [25.0, 25.0]
    # N = neutral - advice: +0.25 on the 9 limit pairs only (all on the right), 0 elsewhere.
    n = report["limits"]["split"]["N"]
    assert (n["either_limit"]["n"], n["either_limit"]["contribution_pp"], n["neither"]["contribution_pp"]) \
        == (9, 6.25, 0.0)


def test_limit_as_zero(built):
    report, _ = built
    z = report["limits"]["as_zero"]["D0"]
    # Zeroed: 0.75 - 0 on the 9 A_LIMIT pairs (6.75), 0 - 0.5 on (sc03_1, 1) (-0.5), 0.25 on
    # the 26 others (6.5): 12.75 / 36 = 35.42 pp -- wider than 31.25, as the review says.
    assert z["diff_pp"] == 35.42 and z["n_pairs"] == 36 and z["metric"] == "goal_pass"
    assert z["sensitivity"] is True and z["threshold_pp"] == 0.0 and 0.0 <= z["p_two_sided"] <= 1.0


def test_limit_rates_per_arm(built):
    report, _ = built
    rates = report["limits"]["per_arm"]
    assert rates["takeover_k10"] == {"n": 36, "n_limit": 1, "rate": round(1 / 36, 6)}
    assert rates["advise_k10"] == {"n": 36, "n_limit": 9, "rate": 0.25}
    assert rates["show_k10"] == {"n": 35, "n_limit": 0, "rate": 0.0}  # the crash is not scored
    assert rates["advise_k1"] == {"n": 24, "n_limit": 0, "rate": 0.0}
    assert rates["hj8_executor_alone_bplus_20260919"] == {"n": 24, "n_limit": 2, "rate": round(2 / 24, 6)}
    assert rates["hj8_sft_plan_bplus_20260919"] == {"n": 0, "n_limit": 0, "rate": None}
    assert set(rates) == set(j17.ARM_CAMPAIGNS) | set(j17.LIMIT_ONLY_CAMPAIGNS)
    assert "limit-rate campaign hj8_sft_plan_bplus_20260919 is missing" in report["warnings"]


def test_metrics_by_hand_and_crash_dropped(built):
    report, _ = built
    m = report["metrics"]
    assert m["D0"]["goal_pass"]["diff_pp"] == 31.25
    # TGC: a limit episode's TGC is 0, so D0 on TGC equals the limit-as-0 sum, 12.75 / 36.
    assert m["D0"]["tgc"]["diff_pp"] == 35.42
    assert m["N"]["goal_pass"]["diff_pp"] == 6.25  # 9 x 0.25 / 36
    # S: the crashed (sc03_3, 3) leaves 35 pairs: 9 x 0.5 + 26 x 0.25 = 11 / 35 = 31.43 pp.
    assert (m["S"]["goal_pass"]["n_pairs"], m["S"]["goal_pass"]["diff_pp"]) == (35, 31.43)
    assert report["inputs"]["arms"]["show_k10"]["n_crash"] == 1
    assert report["inputs"]["arms"]["show_k10"]["campaigns"][1]["n_crash"] == 1
    # TN = 0.75 - 0.5 on every pair: a degenerate interval and p = 2 x min(0, 1) = 0.
    tn = m["TN"]["goal_pass"]
    assert (tn["diff_pp"], tn["ci95_pp_scenario"], tn["ci95_pp_task"], tn["p_two_sided"]) == \
        (25.0, [25.0, 25.0], [25.0, 25.0], 0.0)
    # TGC TN: 0.25 on 35 pairs and 0 - 0.5 on (sc03_1, 1): 8.25 / 36 = 22.92 pp.
    assert m["TN"]["tgc"]["diff_pp"] == 22.92
    # No episode succeeds, so SGC is 0 - 0 on 4 scenarios x 3 seeds; S loses unit (sc03, 3).
    assert (m["D0"]["sgc"]["diff_pp"], m["D0"]["sgc"]["n_pairs"], m["D0"]["sgc"]["p_two_sided"]) == (0.0, 12, 1.0)
    assert (m["S"]["sgc"]["n_pairs"], m["S"]["sgc"]["n_units_unscored_left"]) == (11, 1)


def test_every_contrast_object_carries_the_contract_keys(built):
    report, _ = built
    found = j17.contrast_objects(report)
    ids = {key for key, _obj in found}
    expected = {f"metrics.{c}.{m}" for c in j17.CONTRASTS for m in ("goal_pass", "tgc", "sgc")}
    expected |= {f"limits.as_zero.{c}" for c in j17.CONTRASTS}
    assert ids == expected
    for _key, obj in found:
        assert set(j17.CONTRAST_KEYS) <= obj.keys()
    by = report["by_fdr"]
    assert by["m"] == 8 and by["not_in_family"] == []
    assert {r["id"] for r in by["rows"]} == {f"metrics.{c}.goal_pass" for c in j17.CONTRASTS} | \
        {f"limits.as_zero.{c}" for c in j17.CONTRASTS}


def test_share_of_fenced_code(built):
    report, _ = built
    c = report["content"]
    a = c["advise_k10"]
    # 3 interventions; A1 and A3 carry a fenced block, A2 does not: 2 / 3. Median of 27, 19, 20.
    assert (a["n_episodes"], a["n_episodes_without_events"], a["n_interventions"]) == (36, 34, 3)
    assert (a["share_fenced_code"]["n_fenced"], a["share_fenced_code"]["share"]) == (2, round(2 / 3, 6))
    assert a["n_fenced_python"] == 1 and a["median_chars"] == 20
    assert a["copy_rate"] == round(1 / 3, 6)  # only A1's python block is reproduced
    lo, hi = a["share_fenced_code"]["ci95_scenario"]
    assert 0.5 <= lo <= hi <= 1.0  # sc00 contributes 1 of 2, sc01 1 of 1
    nt = c["advise_k10_neutral"]
    assert (nt["n_interventions"], nt["n_fenced_code"], nt["share_fenced_code"]["share"]) == (2, 1, 0.5)
    assert nt["median_chars"] == 17.0 and nt["copy_rate"] == 0.5  # (22 + 12) / 2; N1 copied
    s = c["show_k10"]
    # 35 scored episodes: the crashed one's show is not counted. The CODE show is fenced, the
    # COMPLETE show is not; b2.copy_rate finds both reproduced.
    assert (s["n_episodes"], s["n_interventions"], s["share_fenced_code"]["share"]) == (35, 2, 0.5)
    assert s["n_by_source"] == {"shown_action": 2} and s["copy_rate"] == 1.0 and s["copy"]["n_shown"] == 2


def test_fenced_block_rule():
    events = [_ev("intervention", "planner", i, correction=t) for i, t in enumerate([
        "inline ```x``` only",          # a ``` pair inside one line is not a block
        "```\nplain\n```",               # a block with no info string
        "```python\nprint(1)",           # an unclosed fence
        "```Python\nx = 1\n```",         # the python spelling, any case
    ])]
    rows = j17.intervention_rows(events)
    assert [r["fenced"] for r in rows] == [False, True, False, True]
    assert [r["fenced_python"] for r in rows] == [False, False, False, True]
    # 6 + 1 + 7 + 1 + 4; 3 + 1 + 5 + 1 + 3; 9 + 1 + 8; 9 + 1 + 5 + 1 + 3.
    assert [r["chars"] for r in rows] == [19, 13, 18, 19]


def test_by_fdr_over_a_two_report_family():
    def obj(metric, p):
        return {"metric": metric, "diff_pp": 1.0, "ci95_pp_scenario": [0.0, 2.0], "ci95_pp_task": [0.0, 2.0],
                "p_two_sided": p, "threshold_pp": 0.0, "n_pairs": 171}

    channel = {
        "metrics": {"D0": {"goal_pass": obj("goal_pass", 0.001), "tgc": obj("tgc", 0.0001)}},
        "limits": {"as_zero": {"D0": obj("goal_pass", 0.04)},
                   "split": {"D0": {"metric": "goal_pass", "whole": {"diff_pp": 1.0}}}},  # not a contrast object
        # A stale by_fdr block would be counted again if it were read.
        "by_fdr": {"rows": [{"id": "x", "metric": "goal_pass", "diff_pp": 1.0, "p_two_sided": 0.0}]},
    }
    depth = {
        "handoff_only_contrasts": {"bplus": {"m6_to_m11": {
            "goal_pass": {"all": obj("goal_pass", 0.03), "handoff_only": obj("goal_pass", None),
                          "silenced": obj("goal_pass", 0.5)},
            "tgc": {"all": obj("tgc", 0.002)}}}},
        "ni": {"zs": {"m9": {"goal_pass": {"all": obj("goal_pass", 0.2), "holds": True}}}},
    }
    out = j17.by_fdr_family(channel, depth, "campaign/results/j17_depth_fixes.report.json")
    # m = 5 goal_pass contrasts with a p (tgc, the p-less one, the split and the stale block are
    # out). c(5) = 137/60, so m c(m) = 137/12. Sorted p: 0.001, 0.03, 0.04, 0.2, 0.5 ->
    # raw 0.001 x 137/12, 0.03 x 137/24, 0.04 x 137/36, 0.2 x 137/48, min(1, 0.5 x 137/60);
    # step-up minimum from the top: the 0.03 row takes the 0.04 row's 0.04 x 137/36.
    assert out["m"] == 5
    assert out["not_in_family"] == ["handoff_only_contrasts.bplus.m6_to_m11.goal_pass.handoff_only"]
    rows = {r["id"]: r for r in out["rows"]}
    assert [r["id"] for r in out["rows"]] == [
        "metrics.D0.goal_pass", "limits.as_zero.D0",
        "handoff_only_contrasts.bplus.m6_to_m11.goal_pass.all",
        "handoff_only_contrasts.bplus.m6_to_m11.goal_pass.handoff_only",
        "handoff_only_contrasts.bplus.m6_to_m11.goal_pass.silenced",
        "ni.zs.m9.goal_pass.all",
    ]
    assert rows["metrics.D0.goal_pass"]["p_by"] == pytest.approx(0.001 * 137 / 12)
    assert rows["limits.as_zero.D0"]["p_by"] == pytest.approx(0.04 * 137 / 36)
    assert rows["handoff_only_contrasts.bplus.m6_to_m11.goal_pass.all"]["p_by"] == pytest.approx(0.04 * 137 / 36)
    assert rows["handoff_only_contrasts.bplus.m6_to_m11.goal_pass.silenced"]["p_by"] == 1.0
    assert rows["ni.zs.m9.goal_pass.all"]["p_by"] == pytest.approx(0.2 * 137 / 48)
    assert [r["survives_0_05"] for r in out["rows"]] == [True, False, False, None, False, False]
    assert rows["metrics.D0.goal_pass"]["source"] == j17.PROTOCOL
    assert rows["ni.zs.m9.goal_pass.all"]["source"] == "campaign/results/j17_depth_fixes.report.json"
    # Without the depth report the family is this report's two, and c(2) = 3/2: 0.001 x 3 = 0.003.
    alone = j17.by_fdr_family(channel)
    assert alone["m"] == 2
    assert alone["rows"][0]["p_by"] == pytest.approx(0.003) and alone["rows"][1]["p_by"] == pytest.approx(0.06)


@pytest.mark.parametrize("flag,value", [
    ("--results-root", "results_test_normal"),
    ("--noop-campaign", "j10_noop_dryrun"),
    ("--depth-report", "test_challenge_depth.json"),
    ("--out", "j10_channel.report.json"),
], ids=["root", "noop", "depth", "out"])
def test_path_refusal(tmp_path: Path, capsys, flag, value):
    assert j17.refuse_path(tmp_path) is None  # the fixture's own directory names no marker
    out = tmp_path / "channel.report.json"
    argv = ["--out", str(out), "--results-root", str(tmp_path), "--n-boot", "20"]
    if flag == "--out":
        out = tmp_path / value
        argv[1] = str(out)
    elif flag == "--results-root":
        argv[3] = str(tmp_path / value)
    else:
        argv += [flag, str(tmp_path / value)]
    assert j17.main(argv) == 2
    assert not out.exists()
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "REFUSED" and value in printed["reason"]


def test_an_unmarked_empty_root_is_not_refused(tmp_path: Path, capsys):
    # The control for the refusals: same flags, no marker. Every arm is missing, so exit 1.
    out = tmp_path / "channel.report.json"
    assert j17.main(["--out", str(out), "--results-root", str(tmp_path), "--n-boot", "20"]) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "INCOMPLETE" and report["by_fdr"]["m"] == 0
    assert report["metrics"]["D0"]["goal_pass"]["n_pairs"] == 0


def _sgc_ep(success: bool) -> dict:
    return {"goal_pass_rate": 1.0 if success else 0.0, "tgc": None, "error_type": None, "success": success}


def test_sgc_contrast_object_by_hand():
    tasks, seeds = ["a_1", "a_2", "b_1", "b_2"], [1, 2]
    keys = [(t, s) for t in tasks for s in seeds]
    left = {k: _sgc_ep(k != ("b_1", 2)) for k in keys}  # units a1 a2 b1 pass, b2 fails
    right = {k: _sgc_ep(k[0].startswith("a") and k[1] == 1) for k in keys}  # only unit (a, 1) passes
    out = j17.sgc_contrast_object(left, right, tasks, seeds, n_boot=N_BOOT, seed=3)
    # Unit diffs: (a,1) 0, (a,2) 1, (b,1) 1, (b,2) 0 -> 50 pp. Each scenario's mean is 0.5, so
    # every resample is 0.5: interval [50, 50], p = 2 x min(0, 1) = 0.
    assert (out["diff_pp"], out["ci95_pp_scenario"], out["p_two_sided"], out["n_pairs"]) == (50.0, [50.0, 50.0], 0.0, 4)
    assert (out["sgc_left"], out["sgc_right"], out["ci95_pp_task"]) == (0.75, 0.25, None)
    # A missing task leaves its unit unscored on that side and out of the pairs: diffs 0, 1, 1.
    del right[("b_2", 2)]
    out = j17.sgc_contrast_object(left, right, tasks, seeds, n_boot=N_BOOT, seed=3)
    assert (out["n_pairs"], out["n_units_unscored_right"], out["diff_pp"]) == (3, 1, 66.67)


def test_latency_block_by_hand(tmp_path: Path):
    frozen = "2023-05-18T12:00:00+00:00"
    codex = {"provider": "codex", "n_calls": 1, "latency_s": 0.0}
    cache = {"provider": "cache", "n_calls": 1, "latency_s": 5.0}
    paths = {}
    for i, (end, manifest) in enumerate([("09:00:10", True), ("09:00:20", True), ("09:01:00", True), ("09:00:30", False)]):
        events = [_ev("run_start", "system", 0, ts=frozen), _ev("plan", "planner", 0, usage=cache, ts=frozen),
                  _ev("intervention", "planner", 10, usage=codex, ts=frozen, correction="x"),
                  _ev("run_end", "system", 12, ts=f"2026-09-22T{end}+00:00")]
        d = write_episode(tmp_path / "c", 1, f"sc0{i}_1", 0.5, events=events,
                          created_at="2026-09-22T09:00:00+00:00" if manifest else None)
        paths[(f"sc0{i}_1", 1)] = d / "events.jsonl"
    out = j17.latency_block(paths)
    wall = out["per_episode_wall_s"]
    # 10, 20 and 60 s; the fourth has no manifest. Median 20, mean 30.
    assert (wall["status"], wall["n"], wall["median"], wall["mean"], wall["n_without_manifest_start"]) == \
        ("ok", 3, 20.0, 30.0, 1)
    # Four live codex calls, every latency_s 0.0 (the cached plan replay is not a call): no timing.
    call = out["per_planner_call_latency_s"]
    assert (call["status"], call["n_live_planner_events"]) == ("no_timestamps", 4)
    for i, lat in enumerate((2.0, 4.0, 9.0)):
        events = [_ev("intervention", "planner", 10, usage={"provider": "codex", "n_calls": 1, "latency_s": lat})]
        (tmp_path / "c" / "fixed_k" / "1" / f"sc0{i}_1" / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    out = j17.latency_block(paths)
    # Now median 4.0 over 3 timed calls (the fourth episode's call is still 0.0), and no run_end.
    assert (out["per_planner_call_latency_s"]["status"], out["per_planner_call_latency_s"]["median"],
            out["per_planner_call_latency_s"]["n_zero_or_missing"]) == ("ok", 4.0, 1)
    assert out["per_episode_wall_s"]["status"] == "no_timestamps"
    assert out["per_episode_wall_s"]["n_without_run_end"] == 3


def test_noop_floor_by_hand(tmp_path: Path):
    camp = tmp_path / "dev_noop_complete_20260924"
    gp = {"sc00": 1.0, "sc01": 0.25, "sc02": 0.0, "sc03": 0.0}
    for seed in (1, 2):
        for task in TASKS:
            crash = (task, seed) == ("sc03_3", 2)
            write_episode(camp, seed, task, gp[task[:4]], error_type="crash" if crash else None)
    out = j17.noop_floor(camp, n_boot=N_BOOT, seed=5)
    # 23 scored (one crash): 6 x 1.0 + 6 x 0.25 = 7.5 / 23. TGC is recorded equal to goal_pass.
    assert (out["n_scored"], out["n_crash"], out["seeds"], out["n_tasks"]) == (23, 1, [1, 2], 12)
    assert out["goal_pass"]["mean"] == round(7.5 / 23, 6) and out["tgc"]["mean"] == round(7.5 / 23, 6)
    # SGC: (sc00, 1) and (sc00, 2) pass of the 7 scored units; (sc03, 2) lost its crashed task.
    assert (out["sgc"]["mean"], out["sgc"]["n"], out["sgc"]["n_units_unscored"]) == (round(2 / 7, 6), 7, 1)
    lo, hi = out["goal_pass"]["ci95_scenario"]
    assert lo <= out["goal_pass"]["mean"] <= hi


def test_census_by_hand(tmp_path: Path):
    index, ledger = write_census_inputs(tmp_path)
    out = j17.census(index, ledger)
    assert (out["n_campaigns_in_index"], out["n_dev_campaigns"], out["n_not_present"], out["n_non_dev_present"]) == \
        (5, 3, 1, 1)
    assert out["n_distinct_dev_arms"] == 2
    assert out["dev_arms"] == {"hj12_prefix_m10": ["hj12_prefix_m10_20260922", "hj12_prefix_m10_20260923"],
                               "hj4b_fixed_k_dev": ["hj4b_fixed_k_dev_20260917"]}
    # 6 rows; the pipes inside backticks do not shift the status column; "method;" counts as method.
    assert out["ledger"]["n_rows"] == 6
    assert out["ledger"]["by_status"] == {"registered": 2, "exploratory": 2, "other": 2}
    assert out["ledger"]["other_by_first_word"] == {"method": 1, "pending": 1}
