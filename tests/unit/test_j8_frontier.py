"""J8 frontier analysis: pairing, bootstrap agreement, refusals, H3, F1."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_J8_SPEC = importlib.util.spec_from_file_location(
    "j8_frontier", REPO / "scripts" / "analysis" / "j8_frontier.py"
)
j8 = importlib.util.module_from_spec(_J8_SPEC)
assert _J8_SPEC.loader is not None
_J8_SPEC.loader.exec_module(j8)

_J10_SPEC = importlib.util.spec_from_file_location(
    "j10_report", REPO / "scripts" / "analysis" / "j10_report.py"
)
j10 = importlib.util.module_from_spec(_J10_SPEC)
assert _J10_SPEC.loader is not None
_J10_SPEC.loader.exec_module(j10)


def _totals(planner_tokens: int, usd: float, calls: int) -> dict:
    return {
        "planner_tokens_total": planner_tokens,
        "planner_calls_total": calls,
        "usd_total": usd,
        "per_actor": {
            "planner": {
                "input_tokens": planner_tokens,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_output_tokens": 0,
                "n_calls": calls,
                "usd": usd,
            }
        },
    }


def write_run(
    root: Path,
    system: str,
    seed: int,
    task_id: str,
    *,
    tgc,
    n_planner_calls: int,
    live_calls: int | None = None,
    error_type=None,
    success=None,
    steps: int = 10,
    n_asks: int = 0,
    planner_tokens: int = 100,
    usd: float = 0.02,
    goal_pass_rate=None,
    events: list[dict] | None = None,
) -> Path:
    dest = root / system / str(seed) / task_id / "result.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if success is None:
        success = bool(tgc == 1.0) and error_type is None
    live = n_planner_calls if live_calls is None else live_calls
    row = {
        "run_id": f"synth/{system}/{seed}/{task_id}",
        "task_id": task_id,
        "system": system,
        "seed": seed,
        "success": success,
        "tgc": tgc,
        "sgc": None,
        "steps": steps,
        "n_planner_calls": n_planner_calls,
        "n_asks": n_asks,
        "n_interventions": 0,
        "error_type": error_type,
        "totals": _totals(planner_tokens, usd, live),
    }
    if goal_pass_rate is not None:
        row["goal_pass_rate"] = goal_pass_rate
    dest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    if events is not None:
        (dest.parent / "events.jsonl").write_text(
            "".join(json.dumps(ev) + "\n" for ev in events),
            encoding="utf-8",
        )
    return dest


TASKS = [f"scen_{i}_1" for i in range(4)]
SEEDS = (1, 2)


def write_two_arms(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "arm_a"
    b = tmp_path / "arm_b"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                a,
                "sidekick",
                seed,
                task_id,
                tgc=1.0,
                n_planner_calls=2,
                live_calls=1,
                goal_pass_rate=1.0,
            )
            write_run(
                b,
                "fixed_k",
                seed,
                task_id,
                tgc=0.0,
                n_planner_calls=5,
                live_calls=5,
                goal_pass_rate=0.0,
            )
    return a, b


def _summaries(tmp_path: Path):
    a_dir, b_dir = write_two_arms(tmp_path)
    a = j8.summarise_arm("sidekick", j10.load_arm_tree(a_dir), list(SEEDS))
    b = j8.summarise_arm("fixed_k_5", j10.load_arm_tree(b_dir), list(SEEDS))
    a["root"] = a_dir
    b["root"] = b_dir
    return a, b


def test_pairing_is_by_task_id_and_seed(tmp_path: Path):
    a, b = _summaries(tmp_path)
    contrast = j8.paired_contrast(a, b, "tgc")
    assert contrast["n_pairs"] == len(TASKS) * len(SEEDS)
    assert set(a["cleaned"]) == {(t, s) for t in TASKS for s in SEEDS}
    assert all(len(k) == 2 for k in a["cleaned"])


def test_bootstrap_agrees_with_j10_on_identical_input(tmp_path: Path):
    a, b = _summaries(tmp_path)
    j8_out = j8.paired_contrast(a, b, "tgc")
    j10_out = j10.contrast_tgc(a["cleaned"], b["cleaned"])
    assert j8_out["diff"] == j10_out["diff"]
    assert j8_out["ci95"] == j10_out["ci95"]
    assert j8_out["ci95_pp"] == j10_out["ci95_pp"]
    assert j8_out["n_pairs"] == j10_out["n_pairs"]
    assert j8_out["resample_unit_for_decision"] == j10.RESAMPLE_UNIT


def test_refuses_headline_when_arm_has_fewer_than_114_rows(tmp_path: Path, capsys):
    smoke = tmp_path / "smoke"
    for i in range(3):
        write_run(
            smoke,
            "sidekick",
            1,
            f"task_{i}",
            tgc=0.0,
            n_planner_calls=1,
            error_type="crash",
        )
    out = tmp_path / "report.json"
    rc = j8.main(
        [
            "--arm",
            f"sidekick_tau05={smoke}",
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 1
    assert report["headline"] is None
    assert report["headline_refused"] is True
    assert any("sidekick_tau05" in m and "3 rows" in m for m in report["refusals"])
    assert "REFUSE headline: arm 'sidekick_tau05' has 3 rows (need 114)" in captured.out
    assert report["arms"]["sidekick_tau05"]["tgc"] is None
    assert report["arms"]["sidekick_tau05"]["planner_calls_per_episode"] is None


def test_degenerate_gate_emits_labelled_row_not_division_error():
    scores = [0.0] * 10
    y = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    row = j8.h3_row("sidekick_tau07", scores, y, n_escalations=0)
    assert row["degenerate"] is True
    assert row["n_positive"] == 5
    assert row["n_escalations"] == 0
    assert row["auroc"] == pytest.approx(0.5)
    assert row["ece"] is not None
    assert row["note"] == "degenerate gate (zero escalations)"


def test_degenerate_gate_single_class_is_still_a_row():
    scores = [0.0, 0.0, 0.0]
    y = [0, 0, 0]
    row = j8.h3_row("router_seq_tau03", scores, y, n_escalations=0)
    assert row["n_positive"] == 0
    assert row["auroc"] == pytest.approx(0.5)
    assert row["degenerate"] is True


def _f1(q_lo, q_hi, c_lo, c_hi):
    quality = {"ci95_pp": [q_lo, q_hi], "diff": (q_lo + q_hi) / 200.0, "n_pairs": 114}
    calls = {"ci95": [c_lo, c_hi], "diff": (c_lo + c_hi) / 2.0, "n_pairs": 114}
    return j8.f1_test(quality, calls)


def test_f1_holds_just_inside_both_conditions():
    row = _f1(-7.0, 1.0, -2.0, -0.0001)
    assert row["quality_within_7pp"] is True
    assert row["fewer_calls_than_fixed_k_5"] is True
    assert row["holds"] is True


def test_f1_fails_just_outside_quality_margin():
    row = _f1(-7.01, 1.0, -2.0, -0.0001)
    assert row["quality_within_7pp"] is False
    assert row["fewer_calls_than_fixed_k_5"] is True
    assert row["holds"] is False


def test_f1_fails_when_calls_ci_includes_zero():
    row = _f1(-7.0, 1.0, -2.0, 0.0)
    assert row["quality_within_7pp"] is True
    assert row["fewer_calls_than_fixed_k_5"] is False
    assert row["holds"] is False


def test_f1_fails_when_calls_are_not_strictly_fewer():
    row = _f1(-6.0, 1.0, 0.1, 1.5)
    assert row["fewer_calls_than_fixed_k_5"] is False
    assert row["holds"] is False


def test_oracle_semantics_is_runs_free():
    semantics, citation = j8.oracle_semantics_line()
    assert semantics == "runs free"
    assert "src/sidekick/runner.py:" in citation
    assert "src/sidekick/systems/loop.py:" in citation
    info = j8.establish_oracle_semantics()
    assert info["established"] is True
    assert "runs free" in info["line"]


def test_live_calls_not_substituted_for_replay_count(tmp_path: Path):
    a, _b = _summaries(tmp_path)
    # write_two_arms stored live_calls=1 and n_planner_calls=2 on sidekick
    row = next(iter(a["cleaned"].values()))
    assert row["planner_calls_live"] == 1
    assert row["planner_calls_replay_inclusive"] == 2
    assert row["calls_live_differs_from_replay"] is True
    assert a["n_episodes_live_differs_from_replay"] == len(TASKS) * len(SEEDS)


def _crash_keys(n_crash: int) -> set[tuple[str, int]]:
    keys = [(task_id, seed) for task_id in TASKS for seed in SEEDS]
    return set(keys[:n_crash])


def write_arm_with_crashes(
    root: Path,
    system: str,
    crash_keys: set[tuple[str, int]],
    *,
    tgc_ok: float,
    gpr_ok: float,
    tgc_crash: float = 0.0,
    calls_ok: int = 2,
    calls_crash: int = 2,
) -> Path:
    for task_id in TASKS:
        for seed in SEEDS:
            crashed = (task_id, seed) in crash_keys
            write_run(
                root,
                system,
                seed,
                task_id,
                tgc=tgc_crash if crashed else tgc_ok,
                n_planner_calls=calls_crash if crashed else calls_ok,
                error_type="crash" if crashed else None,
                goal_pass_rate=None if crashed else gpr_ok,
            )
    return root


def test_crashed_episodes_split_tgc_all_and_survivors(tmp_path: Path):
    crash_keys = _crash_keys(2)
    root = write_arm_with_crashes(
        tmp_path / "fixed_k_3",
        "fixed_k",
        crash_keys,
        tgc_ok=1.0,
        gpr_ok=1.0,
        calls_ok=2,
        calls_crash=4,
    )
    arm = j8.summarise_arm("fixed_k_3", j10.load_arm_tree(root), list(SEEDS))
    assert arm["n"] == 8
    assert arm["n_crashed"] == 2
    assert arm["n_survivors"] == 6
    assert arm["tgc_all"] == pytest.approx(0.75)
    assert arm["tgc_survivors"] == pytest.approx(1.0)
    assert arm["goal_pass_all"] == pytest.approx(0.75)
    assert arm["goal_pass_survivors"] == pytest.approx(1.0)
    assert arm["tgc_all"] != arm["tgc_survivors"]
    assert arm["goal_pass_all"] != arm["goal_pass_survivors"]
    assert arm["planner_calls_total"] == 6 * 2 + 2 * 4
    assert arm["crash_per_call_pct"] == pytest.approx(10.0)
    assert arm["populations_coincide"] is False


def test_survivor_contrast_drops_pairs_where_either_side_crashed(tmp_path: Path):
    crash_keys = _crash_keys(2)
    a_dir = write_arm_with_crashes(
        tmp_path / "a", "fixed_k", crash_keys, tgc_ok=1.0, gpr_ok=1.0
    )
    b_dir = write_arm_with_crashes(
        tmp_path / "b", "fixed_k", set(), tgc_ok=0.0, gpr_ok=0.0
    )
    a = j8.summarise_arm("fixed_k_3", j10.load_arm_tree(a_dir), list(SEEDS))
    b = j8.summarise_arm("fixed_k_5", j10.load_arm_tree(b_dir), list(SEEDS))
    all_c = j8.paired_contrast(a, b, "tgc", population="all")
    surv = j8.paired_contrast(a, b, "tgc", population="survivors")
    assert all_c["n_pairs"] == 8
    assert all_c["n_pairs_dropped_crash"] == 0
    assert all_c["population"] == "all-episodes"
    assert surv["n_pairs_dropped_crash"] == 2
    assert surv["n_pairs"] == 6
    assert surv["n_pairs_shared"] == 8
    assert surv["population"] == "survivors"
    gp_surv = j8.paired_contrast(a, b, "goal_pass_rate", population="survivors")
    assert gp_surv["n_pairs"] == 6
    assert gp_surv["n_pairs_dropped_crash"] == 2


def test_zero_crashes_populations_coincide(tmp_path: Path):
    a, _b = _summaries(tmp_path)
    assert a["n_crashed"] == 0
    assert a["tgc_all"] == a["tgc_survivors"]
    assert a["goal_pass_all"] == a["goal_pass_survivors"]
    assert a["populations_coincide"] is True
    a["complete_n"] = True
    notes = j8.population_notes({"sidekick": a})
    joined = "\n".join(notes)
    assert "coincide" in joined
    assert "0 crashes" in joined
    table = j8.format_table({"sidekick": a}, [])
    assert "tgc_all" in table
    assert "tgc_surv" in table
    assert "spurious" not in table.lower()


def test_all_vs_survivor_sign_disagreement_is_flagged(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(j8, "MIN_ROWS", 8)
    crash_keys = _crash_keys(6)
    a_dir = write_arm_with_crashes(
        tmp_path / "a", "fixed_k", crash_keys, tgc_ok=1.0, gpr_ok=1.0
    )
    b_dir = write_arm_with_crashes(
        tmp_path / "b", "fixed_k", set(), tgc_ok=0.5, gpr_ok=0.5
    )
    out = tmp_path / "report.json"
    rc = j8.main(
        [
            "--arm",
            f"fixed_k_3={a_dir}",
            "--arm",
            f"fixed_k_5={b_dir}",
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0
    assert "CONTRAST DISAGREEMENT" in captured.out
    assert "sign differs" in captured.out
    assert "dropped_crash=" in captured.out
    tgc_all = report["contrasts"]["tgc_all_fixed_k_3_minus_fixed_k_5"]
    tgc_surv = report["contrasts"]["tgc_survivors_fixed_k_3_minus_fixed_k_5"]
    assert tgc_all["diff"] < 0
    assert tgc_surv["diff"] > 0
    assert tgc_surv["n_pairs_dropped_crash"] == 6
    assert tgc_surv["n_pairs"] == 2
    assert any(item["sign_disagree"] for item in report["population_disagreements"])

