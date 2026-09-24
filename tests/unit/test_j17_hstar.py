"""scripts/analysis/j17_hstar.py on a synthetic results tree whose answers are known by arithmetic.

The tree has j17_depth_fixes' layout (family_sources): a planner_alone cap-81 ceiling that is also
the prefix arms' source, and six prefix arms (two receivers x m = 6, 9, 11). Source episodes are
full sidekick Event records, so the validation replays them through sidekick's own
build_handoff_prefix / prefix_is_terminal. Per task suffix the source:

  _1  12 CODE then COMPLETE (13 executed): never exhausted, the flag is true at every m;
  _2  8 CODE then three REPORT, then the step limit: at m = 9 and 11 the flag is false (8 <= m), but the
      prefix is not terminal, so the executor takes control -- the defect h* repairs;
  _3  5 CODE then COMPLETE (6 executed): at every m the prefix ends the episode (terminal).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j17_depth_fixes as j17d
from scripts.analysis import j17_hstar as jh

TASKS = [f"s{s}_{t}" for s in (1, 2) for t in (1, 2, 3)]
PLANS = {"_1": ["CODE"] * 12 + ["COMPLETE"], "_2": ["CODE"] * 8 + ["REPORT"] * 3, "_3": ["CODE"] * 5 + ["COMPLETE"]}
N_SRC = {"_1": 13, "_2": 8, "_3": 6}
SOURCE_GP = {"_1": 0.9, "_2": 0.2, "_3": 1.0}
ARM_GP = {6: {"_1": 0.7, "_2": 0.5, "_3": 1.0}, 9: {"_1": 0.8, "_2": 0.6, "_3": 1.0},
          11: {"_1": 0.8, "_2": 0.7, "_3": 1.0}}


def _event(task, seed, system, step, actor, etype, payload=None, error=None, h=None):
    return {"run_id": f"synth/{system}/{seed}/{task}", "task_id": task, "system": system, "seed": seed,
            "step": step, "ts": "2026-01-01T00:00:00+00:00", "actor": actor, "event_type": etype,
            "payload": payload or {}, "env_state_hash": h, "error_type": error}


def _write(d: Path, result: dict, events: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "result.json").write_text(json.dumps(result), encoding="utf-8")
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")


def source_episode(system_dir: Path, task: str, seed: int) -> None:
    kinds = PLANS[task[-2:]]
    e = [_event(task, seed, "planner_alone", 0, "system", "run_start", h="h0"),
         _event(task, seed, "planner_alone", 0, "environment", "observation", {"text": "", "done": False}, h="h0")]
    step = 0
    for step, kind in enumerate(kinds, start=1):
        payload = {"kind": kind, "code": f"print({step})"} if kind == "CODE" else {"kind": kind, "message": "m"}
        e.append(_event(task, seed, "planner_alone", step, "planner", "action", payload))
        if kind in ("CODE", "COMPLETE"):
            e.append(_event(task, seed, "planner_alone", step, "environment", "observation",
                            {"text": str(step), "done": kind == "COMPLETE", "kind": kind}, h=f"h{step}"))
        else:
            e.append(_event(task, seed, "planner_alone", step, "executor", "report", {"message": "m"}))
    limited = kinds[-1] != "COMPLETE"
    if limited:
        e.append(_event(task, seed, "planner_alone", step, "system", "error", {"limit": "max_steps"}, "limit"))
    e += [_event(task, seed, "planner_alone", step, "environment", "evaluate", {"success": not limited}),
          _event(task, seed, "planner_alone", step, "system", "run_end", {}, "limit" if limited else None)]
    gp = SOURCE_GP[task[-2:]]
    result = {"task_id": task, "seed": seed, "system": "planner_alone", "goal_pass_rate": gp,
              "tgc": 1.0 if gp == 1.0 else 0.0, "success": gp == 1.0, "n_planner_calls": step, "steps": step,
              "error_type": "limit" if limited else None,
              "totals": {"per_actor": {"executor": {"n_calls": 0}}}}
    _write(system_dir / str(seed) / task, result, e)


def prefix_episode(system_dir: Path, task: str, seed: int, m: int, source_campaign: Path) -> None:
    sfx = task[-2:]
    n_src = N_SRC[sfx]
    eff = min(m, n_src)
    live = sfx != "_3"  # _3's prefix always ends the source episode
    e = [_event(task, seed, "prefix_handoff", 0, "system", "run_start", {"prefix": {"start_step": eff + 1}}),
         _event(task, seed, "prefix_handoff", eff, "system", "report",
                {"effective_m": eff, "n_source_actions": n_src, "handoff_occurred": eff < n_src,
                 "hash_ok": True, "replayed_planner_tokens": 0, "source_campaign": str(source_campaign)}),
         _event(task, seed, "prefix_handoff", 0, "environment", "observation", {"text": "", "done": False})]
    last = eff
    if live:
        e += [_event(task, seed, "prefix_handoff", eff + 1, "executor", "action", {"kind": "CODE", "code": "x"}),
              _event(task, seed, "prefix_handoff", eff + 1, "environment", "observation", {"done": False}),
              _event(task, seed, "prefix_handoff", eff + 2, "executor", "action", {"kind": "COMPLETE"}),
              _event(task, seed, "prefix_handoff", eff + 2, "environment", "observation", {"done": True})]
        last = eff + 2
    e += [_event(task, seed, "prefix_handoff", last, "environment", "evaluate", {}),
          _event(task, seed, "prefix_handoff", last, "system", "run_end", {})]
    gp = ARM_GP[m][sfx]
    result = {"task_id": task, "seed": seed, "system": "prefix_handoff", "goal_pass_rate": gp,
              "tgc": 1.0 if gp == 1.0 else 0.0, "success": gp == 1.0, "n_planner_calls": 0, "steps": last,
              "error_type": None, "totals": {"per_actor": {"executor": {"n_calls": 2 if live else 0}}}}
    _write(system_dir / str(seed) / task, result, e)


def build_tree(root: Path) -> None:
    src = j17d.family_sources(root)
    for s in src["ceiling"]:
        for seed in s["seeds"]:
            for t in TASKS:
                source_episode(s["root"], t, seed)
    for rx in j17d.RECEIVERS:
        for m in j17d.DEPTHS:
            for s in src[f"{rx}_m{m}"]:
                for seed in s["seeds"]:
                    for t in TASKS:
                        prefix_episode(s["root"], t, seed, m, s["packet_source"])


@pytest.fixture
def report(tmp_path: Path, monkeypatch) -> dict:
    root = tmp_path / "results"
    build_tree(root)
    monkeypatch.setattr(jh, "FORBIDDEN_OUT_ROOTS", (tmp_path / "forbidden",))
    monkeypatch.setattr(jh, "EXPECTED_FLAG_FALSE", {11: {"terminal": 6, "live": 6}, 9: {"terminal": 6, "live": 6}})
    out = tmp_path / "out" / "hstar.json"
    code = jh.main(["--out", str(out), "--results-root", str(root), "--n-boot", "40", "--seed", "7",
                    "--flag-report", str(tmp_path / "absent.json")])
    assert code == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_validation_holds_and_counts_by_hand(report: dict):
    v = report["validation"]
    assert v["all_hold"] is True
    for rx in ("bplus", "zs"):
        # 1: h_flag true => h*: m6 flags _1 and _2 (12 keys), m9 / m11 flag _1 only (6 keys).
        assert [v["v1_h_flag_true_implies_hstar"][f"{rx}_m{m}"]["n_h_flag_true"] for m in (6, 9, 11)] == [12, 6, 6]
        # 2: the flag-false episodes split by the SOURCE's terminality, recomputed by sidekick's code.
        v2 = v["v2_flag_false_hstar_equals_not_source_terminal"]
        assert (v2[f"{rx}_m6"]["n_flag_false"], v2[f"{rx}_m6"]["n_source_terminal"]) == (6, 6)
        for m in (9, 11):
            assert (v2[f"{rx}_m{m}"]["n_flag_false"], v2[f"{rx}_m{m}"]["n_source_terminal"],
                    v2[f"{rx}_m{m}"]["n_source_live"]) == (12, 6, 6)
            assert v2[f"{rx}_m{m}"]["matches_expected"] is True
        assert all(r["holds"] for r in v["record_agreement"].values())
    assert v["v3_v4_synthetic"]["all_hold"] is True
    c = report["handoff_control_counts"]["bplus"]["m11"]
    assert (c["n_h_flag_true"], c["n_live_but_unflagged"], c["n_terminal"]) == (6, 6, 6)


def test_the_blocks_read_h_star(report: dict):
    h11 = report["handoff_only"]["bplus"]["m11"]
    assert (h11["n"], h11["n_handoff"], h11["n_silenced"]) == (18, 12, 6)
    gp = report["handoff_only_contrasts"]["bplus"]["m9_to_m11"]["goal_pass"]
    # h from m11's h*: _1 (0.8 -> 0.8) and _2 (0.6 -> 0.7) hand off: (6 x 0 + 6 x 0.1) / 12 = +5 pp.
    # With the flag only _1 would, and the handoff-only span would be 0.
    assert gp["handoff_only"]["diff_pp"] == pytest.approx(5.0)
    assert gp["silenced"]["diff_pp"] == pytest.approx(0.0)
    assert gp["all"]["diff_pp"] == pytest.approx(100 * 0.6 / 18)
    ni = report["ni"]["bplus"]["m11"]["goal_pass"]
    # prefix m11 - ceiling on h* pairs: _1 0.8 - 0.9, _2 0.7 - 0.2: (-0.6 + 3.0) / 12 = +20 pp.
    assert ni["handoff_only"]["diff_pp"] == pytest.approx(20.0)
    assert report["changes_vs_flag"] == {"status": "absent"}


def test_rescued_episodes_against_the_source_planner(report: dict):
    r = report["rescued_m11"]["bplus"]
    assert r["n"] == 6 and r["n_planless"] == 0
    assert r["summary"]["goal_pass"]["diff_pp"] == pytest.approx(50.0)
    assert (r["summary"]["goal_pass"]["mean_arm"], r["summary"]["goal_pass"]["mean_source_planner"]) == (0.7, 0.2)
    assert r["summary"]["goal_pass"]["n_arm_above"] == 6
    assert r["source_error_types"] == {"limit": 6}
    assert r["source_action_kinds_after_prefix"] == {"REPORT": 18}
    assert r["n_sources_only_report_after_prefix"] == 6
    assert {e["task_id"][-2:] for e in r["episodes"]} == {"_2"}


def test_with_hstar_swaps_the_indicator_and_keeps_the_flag():
    rows = {("a_1", 1): {"goal_pass_rate": 1.0, "_facts": {"handoff_occurred": False, "executor_n_calls": 3}}}
    out = jh.with_hstar(rows, {("a_1", 1): {"h_star": True}})
    facts = out[("a_1", 1)]["_facts"]
    assert (facts["handoff_occurred"], facts["h_flag"], facts["h_star"], facts["executor_n_calls"]) == (True, False, True, 3)
    assert rows[("a_1", 1)]["_facts"]["handoff_occurred"] is False  # the input row is not mutated
    assert jh.with_hstar(rows, {})[("a_1", 1)]["_facts"]["handoff_occurred"] is None


def test_changes_vs_flag_groups_moves_by_ledger_row_and_checks_all_episode_values():
    old = {"handoff_only": {"bplus": {"m11": {"n_handoff": 71, "goal_pass": {"mean_handoff": 0.79, "mean_all": 0.81}}}},
           "handoff_only_contrasts": {"zs": {"m9_to_m11": {"tgc": {
               "all": {"diff_pp": 2.0}, "handoff_only": {"diff_pp": 3.0},
               "decomposition": {"share_handoff": {"point": 0.5}}}}}},
           "ni": {"bplus": {"m11": {"goal_pass": {"handoff_only": {"reading": "fails"}}}}}}
    new = json.loads(json.dumps(old))
    new["handoff_only"]["bplus"]["m11"]["n_handoff"] = 88
    new["handoff_only"]["bplus"]["m11"]["goal_pass"]["mean_handoff"] = 0.75
    new["handoff_only_contrasts"]["zs"]["m9_to_m11"]["tgc"]["handoff_only"]["diff_pp"] = 4.5
    new["handoff_only_contrasts"]["zs"]["m9_to_m11"]["tgc"]["decomposition"]["share_handoff"]["point"] = 0.6
    new["ni"]["bplus"]["m11"]["goal_pass"]["handoff_only"]["reading"] = "holds"
    ch = jh.changes_vs_flag(new, old)
    assert sorted(ch["by_row"]) == ["HO-01", "HO-02", "HO-07", "HO-08", "HO-NI-01"]
    assert ch["by_row"]["HO-01"]["changes"]["handoff_only.bplus.m11.n_handoff"] == {"old": 71, "new": 88, "delta": 17}
    assert ch["all_episode_values_unchanged"] is True
    new["handoff_only_contrasts"]["zs"]["m9_to_m11"]["tgc"]["all"]["diff_pp"] = 2.5
    assert jh.changes_vs_flag(new, old)["all_episode_values_unchanged"] is False


@pytest.mark.parametrize("marker", ["test_normal", "test_challenge", "j10_", "j11_", "j12_"])
def test_refuse_path_names_each_marker(marker: str):
    assert jh.refuse_path(Path(f"/x/{marker}thing")) is not None
    assert jh.refuse_path(Path("/x/hj17_prefix_c81_bplus_m11_20260923")) is None


def test_main_refuses_heldout_roots_and_an_out_under_the_raw_results(tmp_path: Path, monkeypatch, capsys):
    assert jh.main(["--out", str(tmp_path / "o.json"), "--results-root", str(tmp_path / "j12_x")]) == 2
    assert jh.main(["--out", str(tmp_path / "o.json"), "--results-root", str(tmp_path / "test_challenge")]) == 2
    monkeypatch.setattr(jh, "FORBIDDEN_OUT_ROOTS", (tmp_path,))
    assert jh.main(["--out", str(tmp_path / "o.json"), "--results-root", str(tmp_path / "r")]) == 2
    assert "REFUSED" in capsys.readouterr().out
    assert not (tmp_path / "o.json").exists()
