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


def _totals(
    planner_tokens: int,
    usd: float,
    calls: int,
    *,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_output_tokens: int = 0,
) -> dict:
    inclusive = (
        planner_tokens
        + cached_input_tokens
        + output_tokens
        + reasoning_output_tokens
    )
    return {
        "planner_tokens_total": inclusive,
        "planner_calls_total": calls,
        "usd_total": usd,
        "per_actor": {
            "planner": {
                "input_tokens": planner_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": reasoning_output_tokens,
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
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_output_tokens: int = 0,
    replayed_planner_tokens: float | None = None,
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
        "totals": _totals(
            planner_tokens,
            usd,
            live,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_output_tokens=reasoning_output_tokens,
        ),
    }
    if goal_pass_rate is not None:
        row["goal_pass_rate"] = goal_pass_rate
    dest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    if events is None and replayed_planner_tokens is not None:
        events = [
            {
                "event_type": "run_start",
                "task_id": task_id,
                "seed": seed,
                "payload": {"replayed_planner_tokens": replayed_planner_tokens},
            }
        ]
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


def _gate_ev(step: int, p_ask=None, *, ask: bool = False) -> dict:
    payload: dict = {}
    if p_ask is not None:
        payload["p_ask"] = p_ask
    return {
        "step": step,
        "event_type": "ask" if ask else "action",
        "payload": payload,
    }


def write_h3_arm(root: Path, label: str, episodes: list[dict]) -> dict:
    system = "sidekick" if label.startswith("sidekick") else "router_seq"
    seeds = sorted({int(ep["seed"]) for ep in episodes})
    for ep in episodes:
        write_run(
            root,
            system,
            int(ep["seed"]),
            ep["task_id"],
            tgc=1.0,
            n_planner_calls=1,
            steps=int(ep["steps"]),
            events=list(ep["events"]),
        )
    arm = j8.summarise_arm(label, j10.load_arm_tree(root), seeds)
    arm["root"] = root
    return arm


def test_h3_early_end_excludes_post_episode_ticks_from_scored(tmp_path: Path):
    arm = write_h3_arm(
        tmp_path / "early",
        "sidekick_tau05",
        [
            {
                "task_id": "t_early",
                "seed": 1,
                "steps": 10,
                "events": [_gate_ev(5, 0.2), _gate_ev(10, 0.3)],
            }
        ],
    )
    labels = {"t_early/1": [5]}
    row = j8.collect_h3_for_arm(arm, labels)
    scored = row["populations"]["scored"]
    grid = row["populations"]["grid"]
    assert scored["n"] == 2
    assert grid["n"] == 8
    assert row["n"] == 2
    assert row["headline_population"] == "scored"
    assert row["n_excluded_from_scored"] == 6
    assert row["excluded_from_scored_reason"] == "past_episode_end"
    assert row["excluded_counts"]["past_episode_end"] == 6
    assert row["excluded_counts"]["within_episode_missing_slot"] == 0
    assert scored["n_positive"] == 1
    assert grid["n_positive"] == 1
    assert row["populations_coincide"] is False


def test_h3_grid_above_chance_scored_below_is_flagged(tmp_path: Path):
    arm = write_h3_arm(
        tmp_path / "disagree",
        "sidekick_tau07",
        [
            {
                "task_id": "t_dis",
                "seed": 1,
                "steps": 10,
                "events": [_gate_ev(5, 0.1), _gate_ev(10, 0.9)],
            }
        ],
    )
    labels = {"t_dis/1": [5]}
    row = j8.collect_h3_for_arm(arm, labels)
    scored_auroc = row["populations"]["scored"]["auroc"]
    grid_auroc = row["populations"]["grid"]["auroc"]
    assert scored_auroc == pytest.approx(0.0)
    assert grid_auroc > 0.5
    assert scored_auroc < 0.5
    assert row["auroc_chance_disagreement"] is True
    text = j8.format_h3_table([row])
    assert "CONTRAST DISAGREEMENT" in text
    assert "scored (primary)" in text
    assert "grid" in text
    lines = j8.h3_disagreement_lines([row])
    assert any("CONTRAST DISAGREEMENT" in line for line in lines)
    assert any("exceeds 0.5" in line for line in lines)


def test_h3_full_grid_populations_coincide(tmp_path: Path):
    events = [_gate_ev(tick, 0.4) for tick in j8.tick_grid()]
    arm = write_h3_arm(
        tmp_path / "full",
        "sidekick_tau03",
        [{"task_id": "t_full", "seed": 1, "steps": 40, "events": events}],
    )
    labels = {"t_full/1": [20]}
    row = j8.collect_h3_for_arm(arm, labels)
    assert row["populations"]["scored"]["n"] == 8
    assert row["populations"]["grid"]["n"] == 8
    assert row["populations"]["scored"]["auroc"] == row["populations"]["grid"]["auroc"]
    assert row["n_excluded_from_scored"] == 0
    assert row["populations_coincide"] is True
    assert row["auroc_chance_disagreement"] is False
    text = j8.format_h3_table([row])
    assert "scored and grid H3 populations coincide" in text
    assert "CONTRAST DISAGREEMENT" not in text
    assert "spurious" not in text.lower()


def test_h3_tick_without_p_ask_stays_in_scored(tmp_path: Path):
    arm = write_h3_arm(
        tmp_path / "nopask",
        "router_seq_tau03",
        [
            {
                "task_id": "t_ask",
                "seed": 1,
                "steps": 10,
                "events": [_gate_ev(5, ask=True), _gate_ev(10, 0.0)],
            }
        ],
    )
    labels = {"t_ask/1": [5]}
    row = j8.collect_h3_for_arm(arm, labels)
    scored = row["populations"]["scored"]
    assert scored["n"] == 2
    assert scored["n_positive"] == 1
    assert row["n_escalations"] == 1
    assert scored["auroc"] == pytest.approx(1.0)
    assert row["score_quantiles"]["n"] == 1
    assert row["score_quantiles"]["max"] == pytest.approx(0.0)


def test_h3_score_quantile_table_on_known_distribution(tmp_path: Path):
    known = [0.1, 0.2, 0.3, 0.4]
    q = j8.score_quantiles(known)
    assert q["n"] == 4
    assert q["mean"] == pytest.approx(0.25)
    assert q["min"] == pytest.approx(0.1)
    assert q["median"] == pytest.approx(0.25)
    assert q["p90"] == pytest.approx(0.37)
    assert q["p95"] == pytest.approx(0.385)
    assert q["p99"] == pytest.approx(0.397)
    assert q["max"] == pytest.approx(0.4)
    ticks = j8.tick_grid()
    events = [_gate_ev(ticks[i], known[i]) for i in range(4)]
    arm = write_h3_arm(
        tmp_path / "quant",
        "sidekick_tau05",
        [{"task_id": "t_q", "seed": 1, "steps": 20, "events": events}],
    )
    row = j8.collect_h3_for_arm(arm, {"t_q/1": []})
    assert row["score_quantiles"]["n"] == 4
    assert row["score_quantiles"]["p90"] == pytest.approx(0.37)
    table = j8.format_score_quantile_table([row])
    assert "sidekick_tau05" in table
    assert "0.250000" in table or "0.25" in table
    assert "0.370000" in table or "0.37" in table


def _one_row_arm(
    tmp_path: Path,
    label: str,
    system: str,
    **kwargs,
) -> dict:
    root = tmp_path / label
    write_run(root, system, 1, "task_a", tgc=1.0, n_planner_calls=1, **kwargs)
    arm = j8.summarise_arm(
        label,
        j10.load_arm_tree(root),
        [1],
        root=root,
        cost_key="planner_tokens_noncached",
        packet_source=tmp_path / "no_such_packet_source",
    )
    return next(iter(arm["cleaned"].values()))


def test_noncached_cost_excludes_cached_input_tokens(tmp_path: Path):
    row = _one_row_arm(
        tmp_path,
        "live",
        "planner_alone",
        planner_tokens=100,
        cached_input_tokens=40,
        output_tokens=7,
        reasoning_output_tokens=3,
        live_calls=1,
    )
    assert row["planner_tokens_live"] == pytest.approx(150.0)
    assert row["planner_tokens_noncached_live"] == pytest.approx(110.0)
    assert row["cached_input_tokens"] == pytest.approx(40.0)
    assert row["cached_share_of_inclusive_total"] == pytest.approx(40.0 / 150.0)
    assert j8.episode_cost(row, "planner_tokens_noncached") == pytest.approx(110.0)
    assert j8.episode_cost(row, "planner_tokens_live") == pytest.approx(150.0)


def test_prefix_and_live_noncached_costs_are_on_the_same_scale(tmp_path: Path):
    live = _one_row_arm(
        tmp_path,
        "planner_alone",
        "planner_alone",
        planner_tokens=80,
        cached_input_tokens=50,
        output_tokens=10,
        reasoning_output_tokens=10,
        live_calls=2,
    )
    prefix = _one_row_arm(
        tmp_path,
        "prefix_m2",
        "prefix_handoff",
        planner_tokens=0,
        cached_input_tokens=0,
        live_calls=0,
        replayed_planner_tokens=100,
    )
    assert j8.episode_cost(live, "planner_tokens_noncached") == pytest.approx(100.0)
    assert j8.episode_cost(prefix, "planner_tokens_noncached") == pytest.approx(100.0)
    assert j8.episode_cost(live, "planner_tokens_live") == pytest.approx(150.0)
    assert j8.episode_cost(prefix, "replayed_planner_tokens") == pytest.approx(100.0)


def test_old_token_cost_keys_unchanged_when_cached_tokens_present(tmp_path: Path):
    live = _one_row_arm(
        tmp_path,
        "planner_alone",
        "planner_alone",
        planner_tokens=100,
        cached_input_tokens=50,
        output_tokens=5,
        reasoning_output_tokens=5,
        live_calls=1,
    )
    prefix = _one_row_arm(
        tmp_path,
        "prefix_m2",
        "prefix_handoff",
        planner_tokens=0,
        live_calls=0,
        replayed_planner_tokens=42,
    )
    assert j8.episode_cost(live, "planner_tokens_live") == pytest.approx(160.0)
    assert j8.episode_cost(live, "replayed_planner_tokens") == pytest.approx(160.0)
    assert j8.episode_cost(prefix, "replayed_planner_tokens") == pytest.approx(42.0)
    assert j8.episode_cost(prefix, "planner_tokens_live") == pytest.approx(0.0)
    assert j8.episode_cost(live, "planner_tokens_noncached") == pytest.approx(110.0)


def write_source_plan_event(
    source_root: Path,
    seed: int,
    task_id: str,
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_output_tokens: int,
) -> Path:
    dest = source_root / "planner_alone" / str(seed) / task_id / "events.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {"event_type": "run_start", "task_id": task_id, "seed": seed, "payload": {}},
        {
            "event_type": "plan",
            "actor": "planner",
            "task_id": task_id,
            "seed": seed,
            "payload": {
                "packet": {
                    "packet_id": "p",
                    "task_id": task_id,
                    "goal": "g",
                    "created_at": "t",
                }
            },
            "usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "reasoning_output_tokens": reasoning_output_tokens,
            },
        },
    ]
    dest.write_text("".join(json.dumps(ev) + "\n" for ev in events), encoding="utf-8")
    return dest


def test_sft_plan_noncached_cost_charges_source_plan_event(tmp_path: Path):
    source = tmp_path / "hj1b"
    write_source_plan_event(
        source,
        1,
        "task_a",
        input_tokens=200,
        cached_input_tokens=80,
        output_tokens=15,
        reasoning_output_tokens=5,
    )
    sft_root = tmp_path / "sft"
    write_run(
        sft_root,
        "sft_plan",
        1,
        "task_a",
        tgc=1.0,
        n_planner_calls=1,
        live_calls=1,
        planner_tokens=0,
    )
    arm = j8.summarise_arm(
        "sft_plan",
        j10.load_arm_tree(sft_root),
        [1],
        root=sft_root,
        cost_key="planner_tokens_noncached",
        packet_source=source,
    )
    row = next(iter(arm["cleaned"].values()))
    assert row["sft_plan_replayed_plan_tokens"] == pytest.approx(220.0)
    assert j8.episode_cost(row, "planner_tokens_noncached") == pytest.approx(220.0)
    assert j8.episode_cost(row, "planner_tokens_live") == pytest.approx(0.0)
    assert arm["sft_plan_floor_costing"]["applied"] is True
    assert arm["sft_plan_floor_costing"]["route"] == "source_plan_event"
    assert arm["sft_plan_source_plan_tokens_mean"] == pytest.approx(220.0)


def test_sft_plan_unmapped_source_stays_zero_and_is_understated(tmp_path: Path):
    sft_root = tmp_path / "sft"
    write_run(
        sft_root,
        "sft_plan",
        1,
        "task_a",
        tgc=1.0,
        n_planner_calls=1,
        live_calls=1,
        planner_tokens=0,
    )
    arm = j8.summarise_arm(
        "sft_plan",
        j10.load_arm_tree(sft_root),
        [1],
        root=sft_root,
        cost_key="planner_tokens_noncached",
        packet_source=tmp_path / "empty_source",
    )
    row = next(iter(arm["cleaned"].values()))
    assert row["sft_plan_replayed_plan_tokens"] is None
    assert j8.episode_cost(row, "planner_tokens_noncached") == pytest.approx(0.0)
    costing = arm["sft_plan_floor_costing"]
    assert costing["applied"] is False
    assert costing["route"] == "understatement"
    assert costing["understatement"]["arm"] == "sft_plan"
    assert costing["understatement"]["n_missing"] == 1


def _handoff_events(task_id: str, seed: int, occurred: bool) -> list[dict]:
    return [
        {
            "event_type": "report",
            "task_id": task_id,
            "seed": seed,
            "payload": {"handoff_occurred": occurred},
        }
    ]


def _all_keys() -> list[tuple[str, int]]:
    return [(task_id, seed) for task_id in TASKS for seed in SEEDS]


def write_arm_with_handoff(
    root: Path,
    system: str,
    handoff_keys: set[tuple[str, int]],
    *,
    tgc_handoff: float,
    gpr_handoff: float,
    tgc_no: float,
    gpr_no: float,
    calls_handoff: int = 2,
    calls_no: int = 2,
    every_episode_handoff: bool = False,
) -> Path:
    for task_id in TASKS:
        for seed in SEEDS:
            key = (task_id, seed)
            occurred = True if every_episode_handoff else key in handoff_keys
            write_run(
                root,
                system,
                seed,
                task_id,
                tgc=tgc_handoff if occurred else tgc_no,
                n_planner_calls=calls_handoff if occurred else calls_no,
                live_calls=calls_handoff if occurred else calls_no,
                goal_pass_rate=gpr_handoff if occurred else gpr_no,
                events=_handoff_events(task_id, seed, occurred),
            )
    return root


def _handoff_pair(tmp_path: Path):
    keys = _all_keys()
    ho_keys = set(keys[:4])
    prefix_dir = write_arm_with_handoff(
        tmp_path / "prefix",
        "prefix_handoff",
        ho_keys,
        tgc_handoff=0.0,
        gpr_handoff=0.0,
        tgc_no=1.0,
        gpr_no=1.0,
        calls_handoff=3,
        calls_no=1,
    )
    # Reference has no handoff records. Quality still varies on the same keys
    # so a dishonest per-arm subset would yield n_pairs=0.
    ref_dir = tmp_path / "planner"
    for task_id in TASKS:
        for seed in SEEDS:
            ho = (task_id, seed) in ho_keys
            write_run(
                ref_dir,
                "planner_alone",
                seed,
                task_id,
                tgc=0.5 if ho else 1.0,
                n_planner_calls=4,
                live_calls=4,
                goal_pass_rate=0.5 if ho else 1.0,
            )
    prefix = j8.summarise_arm(
        "prefix_m9", j10.load_arm_tree(prefix_dir), list(SEEDS), root=prefix_dir
    )
    reference = j8.summarise_arm(
        "planner_alone", j10.load_arm_tree(ref_dir), list(SEEDS), root=ref_dir
    )
    prefix["complete_n"] = True
    reference["complete_n"] = True
    return prefix, reference, ho_keys


def test_handoff_only_uses_defining_arm_keys_and_restricts_reference(tmp_path: Path):
    prefix, reference, ho_keys = _handoff_pair(tmp_path)
    ho = j8.paired_contrast(prefix, reference, "tgc", "handoff-only")
    all_c = j8.paired_contrast(prefix, reference, "tgc", "all")
    assert ho["population"] == "handoff-only"
    assert ho["n_pairs"] == len(ho_keys)
    assert ho["n_pairs"] == 4
    assert ho["n_pairs_shared"] == 8
    assert ho["n_pairs_dropped_handoff"] == 4
    assert ho["handoff_keys_from"] == "prefix_m9"
    assert all_c["n_pairs"] == 8
    assert ho["diff"] == pytest.approx(-0.5)
    gp = j8.paired_contrast(prefix, reference, "goal_pass_rate", "handoff-only")
    assert gp["n_pairs"] == 4
    assert gp["diff"] == pytest.approx(-0.5)


def test_full_handoff_population_matches_all_episodes(tmp_path: Path):
    prefix_dir = write_arm_with_handoff(
        tmp_path / "prefix",
        "prefix_handoff",
        set(),
        tgc_handoff=1.0,
        gpr_handoff=1.0,
        tgc_no=0.0,
        gpr_no=0.0,
        every_episode_handoff=True,
    )
    ref_dir = tmp_path / "planner"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                ref_dir,
                "planner_alone",
                seed,
                task_id,
                tgc=0.5,
                n_planner_calls=4,
                live_calls=4,
                goal_pass_rate=0.5,
            )
    prefix = j8.summarise_arm(
        "prefix_m2", j10.load_arm_tree(prefix_dir), list(SEEDS), root=prefix_dir
    )
    reference = j8.summarise_arm(
        "planner_alone", j10.load_arm_tree(ref_dir), list(SEEDS), root=ref_dir
    )
    assert prefix["handoff_occurred_rate"] == pytest.approx(1.0)
    assert prefix["handoff_only_coincides_with_all"] is True
    assert prefix["tgc_handoff_only"] == prefix["tgc_all"]
    assert prefix["goal_pass_handoff_only"] == prefix["goal_pass_all"]
    ho = j8.paired_contrast(prefix, reference, "tgc", "handoff-only")
    all_c = j8.paired_contrast(prefix, reference, "tgc", "all")
    assert ho["n_pairs"] == all_c["n_pairs"] == 8
    assert ho["diff"] == all_c["diff"]
    assert ho["ci95"] == all_c["ci95"]
    assert prefix["n_no_handoff"] == 0


def test_no_handoff_complement_carries_reference_score(tmp_path: Path):
    prefix, reference, ho_keys = _handoff_pair(tmp_path)
    floor_dir = tmp_path / "sft"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                floor_dir,
                "sft_plan",
                seed,
                task_id,
                tgc=0.25,
                n_planner_calls=1,
                live_calls=1,
                goal_pass_rate=0.25,
            )
    floor = j8.summarise_arm(
        "sft_plan", j10.load_arm_tree(floor_dir), list(SEEDS), root=floor_dir
    )
    prefix["complete_n"] = True
    reference["complete_n"] = True
    floor["complete_n"] = True
    ni = j8.noninferiority_block(
        {
            "prefix_m9": prefix,
            "planner_alone": reference,
            "sft_plan": floor,
        },
        "planner_alone",
    )
    assert ni is not None
    rows = ni["arms"]["prefix_m9"]
    assert "goal_pass_all" in rows
    assert "goal_pass_survivors" in rows
    assert "goal_pass_handoff_only" in rows
    assert "goal_pass_no_handoff" in rows
    ho = rows["goal_pass_handoff_only"]
    nh = rows["goal_pass_no_handoff"]
    assert ho["n_pairs"] == 4
    assert nh["n_pairs"] == 4
    assert nh["population"] == "no-handoff"
    assert nh["reference_score"] == pytest.approx(1.0)
    assert nh["arm_score"] == pytest.approx(1.0)
    assert ho["reference_score"] == pytest.approx(0.5)
    assert ho["arm_score"] == pytest.approx(0.0)
    ease = rows["handoff_ease"]
    gp = ease["fields"]["goal_pass_rate"]
    assert gp["reference_higher_on_no_handoff"] is True
    assert gp["reference_far_higher_on_no_handoff"] is True
    assert ease["note"] is not None
    assert "far higher" in ease["note"]
    chord = j8.chord_residual(
        prefix,
        floor,
        reference,
        "goal_pass_rate",
        "planner_calls_live",
        "handoff-only",
    )
    assert chord["n_pairs"] == 4
    assert chord["population"] == "handoff-only"
    assert chord["reference_score"] == pytest.approx(0.5)
    chord_nh = j8.chord_residual(
        prefix,
        floor,
        reference,
        "goal_pass_rate",
        "planner_calls_live",
        "no-handoff",
    )
    assert chord_nh["n_pairs"] == 4
    assert chord_nh["reference_score"] == pytest.approx(1.0)


def _two_prefix_handoff_arms(tmp_path: Path):
    keys = _all_keys()
    m9_keys = set(keys[:4])
    m6_keys = set(keys[:6])
    m9_dir = write_arm_with_handoff(
        tmp_path / "m9",
        "prefix_m9",
        m9_keys,
        tgc_handoff=0.0,
        gpr_handoff=0.0,
        tgc_no=1.0,
        gpr_no=1.0,
        calls_handoff=3,
        calls_no=1,
    )
    m6_dir = write_arm_with_handoff(
        tmp_path / "m6",
        "prefix_m6",
        m6_keys,
        tgc_handoff=0.25,
        gpr_handoff=0.25,
        tgc_no=1.0,
        gpr_no=1.0,
        calls_handoff=2,
        calls_no=1,
    )
    ref_dir = tmp_path / "planner"
    floor_dir = tmp_path / "sft"
    for task_id in TASKS:
        for seed in SEEDS:
            ho = (task_id, seed) in m9_keys
            write_run(
                ref_dir,
                "planner_alone",
                seed,
                task_id,
                tgc=0.5 if ho else 1.0,
                n_planner_calls=4,
                live_calls=4,
                goal_pass_rate=0.5 if ho else 1.0,
            )
            write_run(
                floor_dir,
                "sft_plan",
                seed,
                task_id,
                tgc=0.25,
                n_planner_calls=1,
                live_calls=1,
                goal_pass_rate=0.25,
            )
    arms = {}
    for label, directory in (
        ("prefix_m9", m9_dir),
        ("prefix_m6", m6_dir),
        ("planner_alone", ref_dir),
        ("sft_plan", floor_dir),
    ):
        arm = j8.summarise_arm(
            label, j10.load_arm_tree(directory), list(SEEDS), root=directory
        )
        arm["complete_n"] = True
        arms[label] = arm
    return arms, m9_keys, m6_keys


def test_handoff_keys_from_second_arm_uses_pinned_set(tmp_path: Path):
    arms, m9_keys, m6_keys = _two_prefix_handoff_arms(tmp_path)
    unpinned = j8.noninferiority_block(arms, "planner_alone")
    pinned = j8.noninferiority_block(
        arms, "planner_alone", handoff_keys_from="prefix_m9"
    )
    assert unpinned is not None and pinned is not None
    m6_own = unpinned["arms"]["prefix_m6"]["goal_pass_handoff_only"]
    m6_pin = pinned["arms"]["prefix_m6"]["goal_pass_handoff_only"]
    m9_pin = pinned["arms"]["prefix_m9"]["goal_pass_handoff_only"]
    assert m6_own["n_pairs"] == len(m6_keys)
    assert m6_pin["n_pairs"] == len(m9_keys)
    assert m6_pin["n_pairs"] == m9_pin["n_pairs"]
    assert m6_pin["n_pairs"] != m6_own["n_pairs"]
    assert m6_pin["handoff_keys_from"] == "prefix_m9"
    assert m9_pin["handoff_keys_from"] == "prefix_m9"
    chord_own = j8.chord_residual(
        arms["prefix_m6"],
        arms["sft_plan"],
        arms["planner_alone"],
        "goal_pass_rate",
        "planner_calls_live",
        "handoff-only",
    )
    chord_pin = j8.chord_residual(
        arms["prefix_m6"],
        arms["sft_plan"],
        arms["planner_alone"],
        "goal_pass_rate",
        "planner_calls_live",
        "handoff-only",
        arms["prefix_m9"],
    )
    assert chord_own["n_pairs"] == len(m6_keys)
    assert chord_pin["n_pairs"] == len(m9_keys)
    assert chord_pin["handoff_keys_from"] == "prefix_m9"


def test_handoff_keys_from_pinned_arm_rows_unchanged(tmp_path: Path):
    arms, _, _ = _two_prefix_handoff_arms(tmp_path)
    unpinned = j8.noninferiority_block(arms, "planner_alone")
    pinned = j8.noninferiority_block(
        arms, "planner_alone", handoff_keys_from="prefix_m9"
    )
    assert unpinned is not None and pinned is not None
    for key in (
        "goal_pass_handoff_only",
        "tgc_handoff_only",
        "goal_pass_no_handoff",
        "tgc_no_handoff",
    ):
        assert (
            unpinned["arms"]["prefix_m9"][key]
            == pinned["arms"]["prefix_m9"][key]
        )
    chord_un = j8.chord_block(
        arms, "planner_alone", "sft_plan", "planner_calls_live"
    )
    chord_pin = j8.chord_block(
        arms,
        "planner_alone",
        "sft_plan",
        "planner_calls_live",
        handoff_keys_from="prefix_m9",
    )
    assert chord_un is not None and chord_pin is not None
    for key in (
        "goal_pass_handoff_only",
        "tgc_handoff_only",
        "goal_pass_no_handoff",
        "tgc_no_handoff",
    ):
        assert (
            chord_un["arms"]["prefix_m9"][key]
            == chord_pin["arms"]["prefix_m9"][key]
        )


def test_omitting_handoff_keys_from_matches_unpinned(tmp_path: Path):
    arms, _m9_keys, _m6_keys = _two_prefix_handoff_arms(tmp_path)
    default = j8.noninferiority_block(arms, "planner_alone")
    explicit_none = j8.noninferiority_block(
        arms, "planner_alone", handoff_keys_from=None
    )
    assert default == explicit_none
    m6 = default["arms"]["prefix_m6"]["goal_pass_handoff_only"]
    m9 = default["arms"]["prefix_m9"]["goal_pass_handoff_only"]
    assert m6["n_pairs"] == 6
    assert m9["n_pairs"] == 4
    assert m6["handoff_keys_from"] == "prefix_m6"
    assert m9["handoff_keys_from"] == "prefix_m9"
    parsed = j8.parse_args(
        [
            "--arm",
            "prefix_m9=/tmp/x",
            "--out",
            "/tmp/out.json",
        ]
    )
    assert parsed.handoff_keys_from is None


def test_unknown_handoff_keys_from_raises_with_valid_names(tmp_path: Path):
    arms, _, _ = _two_prefix_handoff_arms(tmp_path)
    with pytest.raises(ValueError, match=r"--handoff-keys-from 'ghost'") as exc:
        j8.resolve_handoff_keys_arm(arms, "ghost")
    msg = str(exc.value)
    assert "not among named arms" in msg
    for name in ("prefix_m6", "prefix_m9", "planner_alone", "sft_plan"):
        assert name in msg
    with pytest.raises(ValueError, match="prefix_m9"):
        j8.noninferiority_block(
            arms, "planner_alone", handoff_keys_from="ghost"
        )
    with pytest.raises(ValueError, match="named arms"):
        j8.chord_block(
            arms,
            "planner_alone",
            "sft_plan",
            "planner_calls_live",
            handoff_keys_from="ghost",
        )


def test_n_pairs_equals_pinned_key_set_size_on_restricted_rows(tmp_path: Path):
    arms, m9_keys, _ = _two_prefix_handoff_arms(tmp_path)
    pinned_n = len(j8.handoff_flag_keys(arms["prefix_m9"]["cleaned"], True))
    assert pinned_n == len(m9_keys)
    ni = j8.noninferiority_block(
        arms, "planner_alone", handoff_keys_from="prefix_m9"
    )
    chord = j8.chord_block(
        arms,
        "planner_alone",
        "sft_plan",
        "planner_calls_live",
        handoff_keys_from="prefix_m9",
    )
    assert ni is not None and chord is not None
    assert ni["handoff_keys_from"] == "prefix_m9"
    assert ni["handoff_keys_n"] == pinned_n
    assert chord["handoff_keys_n"] == pinned_n
    no_n = len(j8.handoff_flag_keys(arms["prefix_m9"]["cleaned"], False))
    for label in ("prefix_m6", "prefix_m9"):
        for key in ("goal_pass_handoff_only", "tgc_handoff_only"):
            assert ni["arms"][label][key]["n_pairs"] == pinned_n
            assert chord["arms"][label][key]["n_pairs"] == pinned_n
        for key in ("goal_pass_no_handoff", "tgc_no_handoff"):
            assert ni["arms"][label][key]["n_pairs"] == no_n
            assert chord["arms"][label][key]["n_pairs"] == no_n


# ---------------------------------------------------------------------------
# X19: scenario-clustered bootstrap + limit-exclusion sensitivity
# ---------------------------------------------------------------------------


def _scenario_arms(tmp_path: Path):
    """Three tasks in one scenario; the third is a huge negative outlier.

    arm 'trt' scores 1.0 on scen_a_1 / scen_a_2 and 0.0 on scen_a_3;
    arm 'ref' scores 1.0 everywhere. The task-clustered mean diff is
    (0 + 0 - 1) / 3 = -1/3, but the scenario-clustered resample keeps the
    outlier welded to its neighbours, so its interval must be wider than
    the degenerate all-or-nothing task interval.
    """
    ref_dir = tmp_path / "ref"
    trt_dir = tmp_path / "trt"
    tasks = ["scen_a_1", "scen_a_2", "scen_a_3"]
    for seed in SEEDS:
        for i, task_id in enumerate(tasks):
            trt_tgc = 0.0 if i == 2 else 1.0
            write_run(
                trt_dir, "trt", seed, task_id, tgc=trt_tgc, n_planner_calls=2,
                live_calls=2, goal_pass_rate=trt_tgc,
            )
            write_run(
                ref_dir, "ref", seed, task_id, tgc=1.0, n_planner_calls=2,
                live_calls=2, goal_pass_rate=1.0,
            )
    ref = j8.summarise_arm("ref", j10.load_arm_tree(ref_dir), list(SEEDS), root=ref_dir)
    trt = j8.summarise_arm("trt", j10.load_arm_tree(trt_dir), list(SEEDS), root=trt_dir)
    ref["complete_n"] = True
    trt["complete_n"] = True
    return trt, ref


def test_scenario_cluster_note_explains_the_mapping():
    text = j8.SCENARIO_CLUSTER_NOTE
    assert "hj1_gate.py:45-46" in text
    assert "19" in text and "57" in text


def test_scenario_of_is_imported_not_reimplemented():
    from scripts.setup.hj1_gate import scenario_of as direct

    assert j8.scenario_of is direct
    assert j8.scenario_of("50e1ac9_3") == "50e1ac9"


def test_scenario_ci_present_beside_task_ci_by_default(tmp_path: Path):
    trt, ref = _scenario_arms(tmp_path)
    out = j8.paired_contrast(trt, ref, "tgc")
    assert out["n_pairs"] == 6
    assert out["n_pairs_scenario"] == 6
    assert out["n_clusters_scenario"] == 1
    assert out["resample_unit_scenario"] == "scenario"
    assert out["resample_unit_for_decision"] == j10.RESAMPLE_UNIT
    assert out["resample"] == "task"
    assert out["diff_pp_scenario"] == out["diff_pp"]


def test_scenario_cluster_widens_interval_on_one_cluster(tmp_path: Path):
    trt, ref = _scenario_arms(tmp_path)
    out = j8.paired_contrast(trt, ref, "tgc")
    assert out["n_clusters_scenario"] == 1
    # With one cluster the scenario resample cannot vary, so its interval
    # collapses to the point estimate; the task interval stays wide.
    assert out["ci95_pp_scenario"][0] == pytest.approx(out["diff_pp"], abs=1.0)
    task_width = out["ci95_pp"][1] - out["ci95_pp"][0]
    assert task_width > 0
    assert out["diff_pp"] == pytest.approx(-100.0 / 3.0, abs=0.5)


def test_scenario_primary_leaves_task_values_under_task_keys(tmp_path: Path):
    trt, ref = _scenario_arms(tmp_path)
    promoted = j8.paired_contrast(trt, ref, "tgc", cluster="scenario")
    plain = j8.paired_contrast(trt, ref, "tgc")
    assert promoted["ci95_pp"] == plain["ci95_pp_scenario"]
    assert promoted["ci95_pp_task"] == plain["ci95_pp"]
    assert promoted["diff_pp_task"] == plain["diff_pp"]
    assert promoted["resample_unit_for_decision"] == "scenario"
    assert promoted["n_pairs"] == plain["n_pairs"]


def test_scenario_and_task_identical_when_diffs_constant(tmp_path: Path):
    ref_dir = tmp_path / "ref"
    trt_dir = tmp_path / "trt"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                trt_dir, "trt", seed, task_id, tgc=0.5, n_planner_calls=1,
                live_calls=1, goal_pass_rate=0.5,
            )
            write_run(
                ref_dir, "ref", seed, task_id, tgc=1.0, n_planner_calls=1,
                live_calls=1, goal_pass_rate=1.0,
            )
    trt = j8.summarise_arm("trt", j10.load_arm_tree(trt_dir), list(SEEDS), root=trt_dir)
    ref = j8.summarise_arm("ref", j10.load_arm_tree(ref_dir), list(SEEDS), root=ref_dir)
    out = j8.paired_contrast(trt, ref, "tgc")
    assert out["ci95_pp"] == out["ci95_pp_scenario"]
    assert out["n_clusters_scenario"] == len(TASKS)


def test_missing_metric_never_becomes_zero_in_scenario_ci(tmp_path: Path):
    ref_dir = tmp_path / "ref"
    trt_dir = tmp_path / "trt"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                trt_dir, "trt", seed, task_id, tgc=0.5, n_planner_calls=1,
                live_calls=1, goal_pass_rate=0.5,
            )
            write_run(
                ref_dir, "ref", seed, task_id, tgc=1.0, n_planner_calls=1,
                live_calls=1, goal_pass_rate=1.0,
            )
    # trt carries no tgc on the first task: the pair must be dropped from
    # the statistic and counted, never read as 0.
    for seed in SEEDS:
        path = trt_dir / "trt" / str(seed) / TASKS[0] / "result.json"
        row = json.loads(path.read_text(encoding="utf-8"))
        row["tgc"] = None
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    trt = j8.summarise_arm("trt", j10.load_arm_tree(trt_dir), list(SEEDS), root=trt_dir)
    ref = j8.summarise_arm("ref", j10.load_arm_tree(ref_dir), list(SEEDS), root=ref_dir)
    # j10's cleaning rule drops the None-tgc rows from `cleaned` before any
    # contrast is built [OBSERVED hpc 25682165.aqua: cleaned tgc has 6
    # keys, both (scen_0_1, seed) rows gone]. They never enter either CI
    # and are never read as 0; the drop is visible in the arm inventory.
    assert all(
        trt["cleaned"][k].get("tgc") is not None for k in trt["cleaned"]
    )
    out = j8.paired_contrast(trt, ref, "tgc")
    assert out["n_pairs"] == 6
    assert out["n_pairs_scenario"] == 6
    assert out["n_pairs_dropped_missing_field_scenario"] == 0
    assert out["ci95_pp_scenario"] == out["ci95_pp"]


def test_noninferiority_row_reports_scenario_hold(tmp_path: Path):
    trt, ref = _scenario_arms(tmp_path)
    row = j8.noninferiority_row(trt, ref, "tgc", "all")
    assert row["margin_pp"] == j8.F1_QUALITY_PP
    assert row["holds_scenario"] is False
    assert row["deficit_ci_upper_pp_scenario"] == pytest.approx(
        -row["ci95_pp_scenario"][0], abs=0.2
    )


def test_chord_row_reports_scenario_interval(tmp_path: Path):
    trt, ref = _scenario_arms(tmp_path)
    floor_dir = tmp_path / "floor"
    tasks = ["scen_a_1", "scen_a_2", "scen_a_3"]
    for seed in SEEDS:
        for task_id in tasks:
            write_run(
                floor_dir, "floor", seed, task_id, tgc=0.0, n_planner_calls=0,
                live_calls=0, goal_pass_rate=0.0,
            )
    floor = j8.summarise_arm(
        "floor", j10.load_arm_tree(floor_dir), list(SEEDS), root=floor_dir,
    )
    floor["complete_n"] = True
    row = j8.chord_residual(trt, floor, ref, "tgc", "planner_calls_live", "all")
    assert row["ci95_pp_scenario"] is not None
    assert row["ci95_pp_task"] == row["ci95_pp"]
    assert row["resample_unit"] == "task"


def test_build_report_default_clusters_task_and_emits_scenario(tmp_path: Path):
    sidekick_dir = tmp_path / "sidekick"
    other_dir = tmp_path / "other"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                sidekick_dir, "sidekick", seed, task_id, tgc=0.5,
                n_planner_calls=2, live_calls=2, goal_pass_rate=0.5,
            )
            write_run(
                other_dir, "other", seed, task_id, tgc=1.0, n_planner_calls=2,
                live_calls=2, goal_pass_rate=1.0,
            )
    out = tmp_path / "report.json"
    rc = j8.main(
        [
            "--arm", f"sidekick={sidekick_dir}",
            "--arm", f"other={other_dir}",
            "--out", str(out),
        ]
    )
    assert rc == 1  # refused: fewer than 114 rows
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["cluster"] == "task"
    assert "19" in report["cluster_note"]
    assert report["exclude_reference_limit"] is False
    contrast = report["contrasts"]["tgc_all_sidekick_minus_other"]
    assert contrast["resample_unit"] == "task"
    assert contrast["ci95_pp_scenario"] is not None


def test_exclude_reference_limit_cli_writes_sensitivity_block(tmp_path: Path):
    ref_dir = tmp_path / "planner"
    trt_dir = tmp_path / "trt"
    for task_id in TASKS:
        for seed in SEEDS:
            error_type = "limit" if task_id == TASKS[0] else None
            write_run(
                ref_dir, "planner_alone", seed, task_id, tgc=1.0,
                n_planner_calls=25, live_calls=25, error_type=error_type,
                goal_pass_rate=1.0,
            )
            write_run(
                trt_dir, "trt", seed, task_id, tgc=0.5, n_planner_calls=5,
                live_calls=5, goal_pass_rate=0.5,
            )
    out = tmp_path / "report.json"
    j8.main(
        [
            "--arm", f"trt={trt_dir}",
            "--arm", f"planner_alone={ref_dir}",
            "--reference-arm", "planner_alone",
            "--exclude-reference-limit",
            "--out", str(out),
        ]
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    info = report["reference_episodes_excluded_limit"]
    # `limit` rows are dropped from `cleaned` at load time (j10 cleaning:
    # error_type in the broken set never reaches a contrast), so the
    # exclusion criterion is `error_type == 'limit'` on the *loaded runs*,
    # and n_reference_before counts loaded rows, not cleaned ones.
    assert info["applied"] is True
    assert info["n_reference_before"] == 6  # 8 loaded, 2 limit rows dropped
    assert info["n_excluded"] == 0
    assert info["n_reference_after"] == 6
    assert info["loaded_rows"] == 8
    assert info["loaded_error_type_limit"] == 2
    sens = report["exclude_reference_limit_sensitivity"]
    assert sens["noninferiority"]["diagnostic_only"] is True
    assert sens["noninferiority"]["reference_n_after_exclusion"] == 6
    row = sens["noninferiority"]["arms"]["trt"]["tgc_all"]
    assert row["n_pairs"] == 6
    assert report["noninferiority"]["arms"]["trt"]["tgc_all"]["n_pairs"] == 6


def test_exclude_reference_limit_without_reference_arm_records_reason(
    tmp_path: Path,
):
    arm_dir = tmp_path / "arms"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                arm_dir, "sidekick", seed, task_id, tgc=0.5, n_planner_calls=2,
                live_calls=2, goal_pass_rate=0.5,
            )
    out = tmp_path / "report.json"
    j8.main(
        [
            "--arm", f"sidekick={arm_dir}",
            "--exclude-reference-limit",
            "--out", str(out),
        ]
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    info = report["reference_episodes_excluded_limit"]
    assert info["applied"] is False
    assert "reference-arm" in info["reason"]
    assert report["exclude_reference_limit_sensitivity"] is None

    other_dir = tmp_path / "other"
    for task_id in TASKS:
        for seed in SEEDS:
            write_run(
                other_dir, "other", seed, task_id, tgc=1.0, n_planner_calls=2,
                live_calls=2, goal_pass_rate=1.0,
            )
    rc = j8.main(
        [
            "--arm", f"sidekick={arm_dir}",
            "--arm", f"other={other_dir}",
            "--out", str(out),
        ]
    )
    assert rc == 1  # refused: fewer than 114 rows
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["cluster"] == "task"
    assert "19" in report["cluster_note"]
    assert report["exclude_reference_limit"] is False
    assert report["reference_episodes_excluded_limit"] is None
    assert report["exclude_reference_limit_sensitivity"] is None
    contrast = report["contrasts"]["tgc_all_sidekick_minus_other"]
    assert contrast["resample_unit"] == "task"
    assert contrast["ci95_pp_scenario"] is not None

