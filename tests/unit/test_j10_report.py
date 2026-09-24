"""J10 analysis script: refuse rather than invent, and never coerce None to 0."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "j10_report",
    Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "j10_report.py",
)
j10 = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(j10)

REQUIRED = (
    "planner_alone",
    "executor_alone",
    "prompt_only",
    "fixed_k",
    "sft_plan",
    "sidekick",
)
TASKS = [f"scen_{i}_{j}" for i in range(4) for j in (1, 2, 3)]  # 12 tasks, 4 scenarios
SEEDS = (1, 2, 3)


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
    error_type=None,
    success=None,
    steps: int = 10,
    n_asks: int = 0,
    planner_tokens: int = 100,
    usd: float = 0.02,
    goal_pass_rate=None,
) -> Path:
    dest = root / system / str(seed) / task_id / "result.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if success is None:
        success = bool(tgc == 1.0) and error_type is None
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
        "totals": _totals(planner_tokens, usd, n_planner_calls),
    }
    if goal_pass_rate is not None:
        row["goal_pass_rate"] = goal_pass_rate
    dest.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return dest


def write_complete_matrix(
    tmp_path: Path,
    *,
    tgc: dict[str, float],
    calls: dict[str, int],
    planner_tokens: dict[str, int] | None = None,
) -> Path:
    """One directory per arm, matching runner layout."""
    tokens = planner_tokens or {
        "planner_alone": 1000,
        "executor_alone": 0,
        "prompt_only": 50,
        "fixed_k": 400,
        "sft_plan": 50,
        "sidekick": 80,
    }
    for arm in REQUIRED:
        for task_id in TASKS:
            for seed in SEEDS:
                write_run(
                    tmp_path,
                    arm,
                    seed,
                    task_id,
                    tgc=tgc[arm],
                    n_planner_calls=calls[arm],
                    planner_tokens=tokens[arm],
                    usd=0.01 * max(calls[arm], 1),
                )
    return tmp_path


def argv_for(tmp_path: Path, extra: list[str] | None = None) -> list[str]:
    args = [
        "--split",
        "dev",
        "--seeds",
        "1,2,3",
        "--expected-n-tasks",
        str(len(TASKS)),
        "--k-matched",
        "5",
        "--plumbing-check",
    ]
    for arm in REQUIRED:
        args.extend(["--arm", f"{arm}={tmp_path / arm}"])
    if extra:
        args.extend(extra)
    return args


def test_refuses_test_normal_without_confirmation(tmp_path: Path):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path)
    args[args.index("dev")] = "test_normal"
    rc = j10.main_v1(args)
    assert rc == 2


def test_refuses_test_challenge_without_confirmation(tmp_path: Path):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 0.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path)
    args[args.index("dev")] = "test_challenge"
    rc = j10.main_v1(args)
    assert rc == 2


def test_path_containing_test_normal_is_refused_on_dev(tmp_path: Path, capsys):
    evil = tmp_path / "camp_test_normal" / "sidekick"
    evil.mkdir(parents=True)
    rc = j10.main_v1(
        [
            "--split",
            "dev",
            "--seeds",
            "1",
            "--arm",
            f"sidekick={evil}",
            "--plumbing-check",
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert rc == 2
    assert report["refused"] is True
    assert "test_normal" in report["reason"]


def test_plumbing_check_is_refused_on_test_normal_even_with_confirm(tmp_path: Path):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path) + ["--confirm-heldout-test-split"]
    args[args.index("dev")] = "test_normal"
    rc = j10.main_v1(args)
    assert rc == 2


def test_confirm_allows_synthetic_test_normal_without_plumbing(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 0.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path)
    args[args.index("dev")] = "test_normal"
    args.remove("--plumbing-check")
    args.append("--i-understand-this-is-the-single-j10-look")
    rc = j10.main_v1(args)
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["split"] == "test_normal"
    assert report["plumbing_check"] is False


def test_missing_metric_is_not_coerced_to_zero_and_refuses(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={arm: 2 for arm in REQUIRED},
    )
    # One sidekick cell: tgc missing, no error_type. The campaign defect is averaging this as 0.
    write_run(
        tmp_path,
        "sidekick",
        1,
        TASKS[0],
        tgc=None,
        n_planner_calls=2,
        error_type=None,
        success=False,
    )
    rc = j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["hypothesis_decisions_refused"] is True
    assert report["arms"]["sidekick"]["tgc_mean"] is None
    assert report["arms"]["sidekick"]["n_missing_metric"] == 1
    assert report["missing_and_crashed"]["sidekick"]["n_missing_metric"] == 1
    assert any("incomplete_arm:sidekick" in r for r in report["incomplete_reasons"])
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_crash_with_unmeasured_tgc_is_scored_zero_and_counted(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={"planner_alone": 10, "executor_alone": 0, "prompt_only": 1, "fixed_k": 5, "sft_plan": 1, "sidekick": 1},
    )
    write_run(
        tmp_path,
        "sidekick",
        2,
        TASKS[1],
        tgc=None,
        n_planner_calls=1,
        error_type="crash",
        success=False,
    )
    rc = j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["hypothesis_decisions_refused"] is False
    assert report["arms"]["sidekick"]["n_scored_failure"] == 1
    assert report["arms"]["sidekick"]["n_missing_metric"] == 0
    n = len(TASKS) * len(SEEDS)
    assert report["arms"]["sidekick"]["tgc_mean"] == pytest.approx((n - 1) / n)


def test_recorded_tgc_one_on_limit_run_refuses_rather_than_picking(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    write_run(
        tmp_path,
        "fixed_k",
        1,
        TASKS[0],
        tgc=1.0,
        n_planner_calls=1,
        error_type="limit",
        success=False,
    )
    rc = j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["arms"]["fixed_k"]["n_scored_failure_disagrees_with_recorded_tgc"] == 1
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_missing_arm_is_headline_and_refuses(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 0.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path)
    # Drop the sidekick --arm pair.
    idx = args.index(f"sidekick={tmp_path / 'sidekick'}")
    del args[idx]
    del args[idx - 1]
    rc = j10.main_v1(args)
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["headline"].startswith("PLUMBING CHECK")
    assert "INCOMPLETE" in report["headline"]
    assert any("missing_arm:sidekick" in r for r in report["incomplete_reasons"])
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_missing_run_is_not_filled_with_zero(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    missing = tmp_path / "sidekick" / "3" / TASKS[0] / "result.json"
    missing.unlink()
    rc = j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["arms"]["sidekick"]["n_missing_run"] == 1
    assert report["arms"]["sidekick"]["tgc_mean"] is None
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_h2_holds_on_constructed_data(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={
            "planner_alone": 1.0,
            "executor_alone": 0.0,
            "prompt_only": 0.0,
            "fixed_k": 1.0,
            "sft_plan": 0.0,
            "sidekick": 1.0,
        },
        calls={
            "planner_alone": 12,
            "executor_alone": 0,
            "prompt_only": 1,
            "fixed_k": 5,
            "sft_plan": 1,
            "sidekick": 1,
        },
    )
    rc = j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["hypothesis_decisions_refused"] is False
    assert report["resample_unit"] == "task"
    h2 = report["hypotheses"]["H2"]
    assert h2["status"] == "decided"
    assert h2["holds"] is True
    assert h2["detail"]["clauses"]["1_vs_fixed_k_k_matched"]["holds"] is True
    assert h2["detail"]["clauses"]["2_vs_sft_plan"]["holds"] is True
    assert h2["detail"]["clauses"]["3_calls_vs_fixed_k_5"]["holds"] is True
    assert report["contrasts"]["tgc_sidekick_minus_sft_plan"]["ci95_pp"][0] > 0
    assert report["contrasts"]["calls_sidekick_minus_fixed_k_k5"]["ci95"][1] < 0
    assert report["plumbing_check"] is True
    assert report["label"].startswith("PLUMBING CHECK")


def test_h2_clause2_fails_when_sidekick_equals_sft_plan(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={
            "planner_alone": 12,
            "executor_alone": 0,
            "prompt_only": 1,
            "fixed_k": 5,
            "sft_plan": 1,
            "sidekick": 1,
        },
    )
    rc = j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    h2 = report["hypotheses"]["H2"]
    assert h2["holds"] is False
    assert h2["detail"]["clauses"]["2_vs_sft_plan"]["holds"] is False


def test_resample_unit_is_task_not_pair(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 0.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert report["resample_unit"] == "task"
    assert "not independent" in report["resample_unit_justification"]
    assert report["contrasts"]["tgc_sidekick_minus_sft_plan"]["resample"] == "task"
    assert report["contrasts"]["tgc_sidekick_minus_sft_plan"]["resample_unit_for_decision"] == "task"


def test_unknown_arm_label_is_refused(capsys):
    rc = j10.main_v1(
        [
            "--split",
            "dev",
            "--seeds",
            "1",
            "--arm",
            "not_an_arm=/tmp/x",
            "--plumbing-check",
        ]
    )
    assert rc == 2
    report = json.loads(capsys.readouterr().out)
    assert report["refused"] is True


def test_unresolved_ambiguities_are_attached_and_cite_prereg():
    assert j10.UNRESOLVED_AMBIGUITIES
    ids = {row["id"] for row in j10.UNRESOLVED_AMBIGUITIES}
    assert "one_sided_vs_two_sided_bootstrap" in ids
    assert "h2_three_clause_vs_h2a_h2b" in ids
    for row in j10.UNRESOLVED_AMBIGUITIES:
        assert row["citations"]
        assert any("docs/prereg_v1.md:" in c or "campaign/RUNS.md:" in c or "scripts/" in c or "src/" in c for c in row["citations"])


def test_h3_is_not_invented_from_j10_archives(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 0.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    j10.main_v1(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert report["hypotheses"]["H3"]["status"] == "not_a_j10_archive_quantity"


PARTIAL_ARMS = ("sft_plan", "executor_alone")


def write_named_arms(
    tmp_path: Path,
    arms: tuple[str, ...],
    *,
    tgc: dict[str, float],
    calls: dict[str, int],
    goal_pass_rate: dict[str, float] | None = None,
) -> None:
    gpr = goal_pass_rate or {}
    for arm in arms:
        for task_id in TASKS:
            for seed in SEEDS:
                write_run(
                    tmp_path,
                    arm,
                    seed,
                    task_id,
                    tgc=tgc[arm],
                    n_planner_calls=calls[arm],
                    goal_pass_rate=gpr.get(arm),
                )


def argv_partial(tmp_path: Path, arms: tuple[str, ...], extra: list[str] | None = None) -> list[str]:
    args = [
        "--split",
        "dev",
        "--seeds",
        "1,2,3",
        "--expected-n-tasks",
        str(len(TASKS)),
        "--partial-matrix",
    ]
    for arm in arms:
        args.extend(["--arm", f"{arm}={tmp_path / arm}"])
    if extra:
        args.extend(extra)
    return args


def test_partial_matrix_emits_tgc_and_goal_pass_contrasts(tmp_path: Path, capsys):
    write_named_arms(
        tmp_path,
        PARTIAL_ARMS,
        tgc={"sft_plan": 1.0, "executor_alone": 0.0},
        calls={"sft_plan": 1, "executor_alone": 0},
        goal_pass_rate={"sft_plan": 1.0, "executor_alone": 0.0},
    )
    rc = j10.main_v1(argv_partial(tmp_path, PARTIAL_ARMS))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1  # H1/H2 are not decided in partial mode
    assert report["partial_matrix"] is True
    assert report["plumbing_check"] is True
    assert "PLUMBING CHECK, NOT A RESULT" in report["label"]
    assert "PLUMBING CHECK, NOT A RESULT" in report["headline"]
    tgc_c = report["contrasts"]["tgc_sft_plan_minus_executor_alone"]
    gpr_c = report["contrasts"]["goal_pass_rate_sft_plan_minus_executor_alone"]
    assert tgc_c["ci95"] is not None and tgc_c["ci95_pp"] is not None
    assert gpr_c["ci95"] is not None and gpr_c["ci95_pp"] is not None
    assert tgc_c["resample"] == "task"
    assert gpr_c["resample"] == "task"
    assert tgc_c["ci95"][0] > 0
    assert gpr_c["ci95"][0] > 0
    assert tgc_c["n_pairs"] == len(TASKS) * len(SEEDS)
    assert gpr_c["n_pairs"] == len(TASKS) * len(SEEDS)
    assert gpr_c["pairs_dropped_missing_field"] == 0
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_full_j10_still_refuses_incomplete_matrix(tmp_path: Path, capsys):
    write_named_arms(
        tmp_path,
        PARTIAL_ARMS,
        tgc={"sft_plan": 1.0, "executor_alone": 0.0},
        calls={"sft_plan": 1, "executor_alone": 0},
        goal_pass_rate={"sft_plan": 1.0, "executor_alone": 0.0},
    )
    args = [
        "--split",
        "dev",
        "--seeds",
        "1,2,3",
        "--expected-n-tasks",
        str(len(TASKS)),
        "--plumbing-check",
        "--arm",
        f"sft_plan={tmp_path / 'sft_plan'}",
        "--arm",
        f"executor_alone={tmp_path / 'executor_alone'}",
    ]
    rc = j10.main_v1(args)
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["partial_matrix"] is False
    assert "INCOMPLETE" in report["headline"]
    assert any("missing_arm:" in r for r in report["incomplete_reasons"])
    assert any("k_matched_not_supplied" in r for r in report["incomplete_reasons"])
    assert report["contrasts"] == {}
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_full_j10_still_refuses_when_k_matched_absent(tmp_path: Path, capsys):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 1.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path)
    idx = args.index("--k-matched")
    del args[idx : idx + 2]
    rc = j10.main_v1(args)
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert any("k_matched_not_supplied" in r for r in report["incomplete_reasons"])
    assert "k_matched_not_supplied" in report["headline"]
    assert report["contrasts"] == {}
    assert report["hypotheses"]["H2"]["status"] == "refused"


def test_missing_goal_pass_rate_is_dropped_and_counted(tmp_path: Path, capsys):
    write_named_arms(
        tmp_path,
        PARTIAL_ARMS,
        tgc={"sft_plan": 1.0, "executor_alone": 0.0},
        calls={"sft_plan": 1, "executor_alone": 0},
        goal_pass_rate={"sft_plan": 0.8, "executor_alone": 0.2},
    )
    write_run(
        tmp_path,
        "sft_plan",
        1,
        TASKS[0],
        tgc=1.0,
        n_planner_calls=1,
    )
    rc = j10.main_v1(argv_partial(tmp_path, PARTIAL_ARMS))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    n = len(TASKS) * len(SEEDS)
    gpr_c = report["contrasts"]["goal_pass_rate_sft_plan_minus_executor_alone"]
    tgc_c = report["contrasts"]["tgc_sft_plan_minus_executor_alone"]
    assert gpr_c["pairs_dropped_missing_field"] == 1
    assert gpr_c["n_pairs"] == n - 1
    assert tgc_c["n_pairs"] == n
    assert report["arms"]["sft_plan"]["n_goal_pass_rate_missing"] == 1
    assert report["arms"]["sft_plan"]["n_goal_pass_rate_recorded"] == n - 1
    assert report["arms"]["sft_plan"]["goal_pass_rate_mean"] == pytest.approx(0.8)
    assert report["missing_and_crashed"]["sft_plan"]["n_goal_pass_rate_missing"] == 1


def test_partial_matrix_never_emits_unnamed_arms(tmp_path: Path, capsys):
    write_named_arms(
        tmp_path,
        PARTIAL_ARMS,
        tgc={"sft_plan": 1.0, "executor_alone": 0.0},
        calls={"sft_plan": 1, "executor_alone": 0},
        goal_pass_rate={"sft_plan": 1.0, "executor_alone": 0.0},
    )
    rc = j10.main_v1(argv_partial(tmp_path, PARTIAL_ARMS))
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert set(report["arms"]) == set(PARTIAL_ARMS)
    assert report["named_arms"] == list(PARTIAL_ARMS)
    for key in report["contrasts"]:
        rest = key
        if rest.startswith("goal_pass_rate_"):
            rest = rest[len("goal_pass_rate_") :]
        elif rest.startswith("tgc_"):
            rest = rest[len("tgc_") :]
        else:
            raise AssertionError(f"unexpected contrast key {key}")
        left, sep, right = rest.partition("_minus_")
        assert sep
        assert left in PARTIAL_ARMS
        assert right in PARTIAL_ARMS
    for arm in report["arms"]:
        assert arm in PARTIAL_ARMS


# ===========================================================================
# A1 protocol (docs/prereg_j10_amendment_20260924.md §5-§6 + 2026-09-23 revisions)
# ===========================================================================

A1_TASKS = [f"sc{i}_{j}" for i in range(4) for j in (1, 2, 3)]  # 4 scenarios x 3 tasks
A1_SEEDS = (1, 2)
A1_ALL_ARMS = tuple(j10.A1_ARMS)
DEV_RESULTS = Path("/scratch/n12194778/sidekick/results")
REPO_ROOT = Path(__file__).resolve().parents[2]


def write_a1_arm(
    root: Path,
    label: str,
    goal_pass,
    *,
    tgc: float = 0.0,
    error_types: dict | None = None,
    manifest_split: str | None = "dev",
    success=False,
    handoff: dict | None = None,
) -> Path:
    """One arm tree in runner layout. goal_pass / success: a value or a {(task, seed): value}
    map. handoff: {(task, seed): bool} written as the prefix arm's `report` event."""
    arm_root = root / label
    for task_id in A1_TASKS:
        for seed in A1_SEEDS:
            key = (task_id, seed)
            dest = arm_root / "sys" / str(seed) / task_id
            dest.mkdir(parents=True, exist_ok=True)
            gp = goal_pass[key] if isinstance(goal_pass, dict) else goal_pass
            if handoff is not None and key in handoff:
                events = [{"event_type": "run_start", "payload": {}},
                          {"event_type": "report", "payload": {"handoff_occurred": handoff[key]}}]
                (dest / "events.jsonl").write_text(
                    "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
            row = {
                "run_id": f"synth/{label}/{seed}/{task_id}",
                "task_id": task_id,
                "system": "sys",
                "seed": seed,
                "success": success[key] if isinstance(success, dict) else success,
                "tgc": tgc,
                "goal_pass_rate": gp,
                "steps": 5,
                "n_planner_calls": 1,
                "error_type": (error_types or {}).get(key),
            }
            (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
            if manifest_split is not None:
                (dest / "manifest.json").write_text(
                    json.dumps({"provenance": {"split": manifest_split}}), encoding="utf-8"
                )
    return arm_root


# Dyadic constants: every per-episode difference is exact, so every bootstrap mean
# equals it and each CI, p-value and Holm adjustment can be written down by hand.
A1_CONSTANT_GP = {
    "executor_alone": 0.25,
    "sft_plan": 0.5,
    "planner_alone_cap81": 0.75,
    "prefix_m9": 0.625,
    "prefix_m11": 0.75,
    "prefix_zs_m9": 0.5,
    "prefix_zs_m11": 0.5,
    "advise_k1_fullctx": 0.5,
    "advise_k10_fullctx": 0.5,
    "takeover_k10": 0.75,
    # A1 arms 1b, 11, 12: no registered prediction names them (r3: 11-12 are exploratory
    # rows E2-E5 only), so these values move no verdict.
    "executor_alone_bplus": 0.375,
    "show_k10": 0.625,
    "advise_k10_neutral": 0.5,
}
A1_COST_REPORT = {
    "arms": {
        "advise_k1_fullctx": {"noncached_tokens_per_episode": 1414410.0,
                              "hosted_calls_per_episode": 19.0, "n_episodes": 24},
        "prefix_m11": {"noncached_tokens_per_episode": 443361.0,
                       "hosted_calls_per_episode": 11.25, "n_episodes": 24},
    }
}


def write_a1_matrix(tmp_path: Path, gp: dict | None = None, **kw) -> dict[str, Path]:
    values = dict(A1_CONSTANT_GP, **(gp or {}))
    return {label: write_a1_arm(tmp_path, label, values[label], **kw) for label in A1_ALL_ARMS}


def a1_report(arm_dirs, **kw):
    kw.setdefault("split", "dev")
    kw.setdefault("seeds", list(A1_SEEDS))
    kw.setdefault("expected_n_tasks", len(A1_TASKS))
    return j10.build_report_a1(arm_dirs=arm_dirs, **kw)


def by_id(report: dict) -> dict:
    return {p["id"]: p for p in report["predictions"]}


def test_a1_registry_is_data_and_matches_the_registration():
    preds = {p["id"]: p for p in j10.A1_PREDICTIONS}
    assert set(preds) == {"P1", "P2", "P3", "P4", "P5", "P6"}
    assert (preds["P1"]["left"], preds["P1"]["right"]) == ("advise_k1_fullctx", "prefix_m11")
    assert (preds["P3"]["left"], preds["P3"]["right"], preds["P3"]["threshold_pp"]) == (
        "prefix_m11", "planner_alone_cap81", -7.00)
    assert (preds["P4"]["left"], preds["P4"]["right"]) == ("prefix_zs_m11", "prefix_zs_m9")
    assert (preds["P5"]["left"], preds["P5"]["right"]) == ("advise_k1_fullctx", "sft_plan")
    assert (preds["P6"]["left"], preds["P6"]["right"], preds["P6"]["role"]) == (
        "takeover_k10", "advise_k10_fullctx", "primary")
    assert preds["P2"]["kind"] == "cost_ratio" and preds["P2"]["min_ratio"] == 2.0
    family = [p["id"] for p in j10.A1_PREDICTIONS if p["holm_family"]]
    # A1 r2 §5.3: P5 is supported by a NON-rejection, so Holm would make it easier; it is out.
    assert family == ["P1", "P3", "P4", "P6"]
    for p in j10.A1_PREDICTIONS:
        assert p["rule"] in j10.A1_RULES
    assert j10.A1_BOOTSTRAP_N == 10_000 and j10.A1_BOOTSTRAP_SEED == 20260924
    assert j10.POOL04_SEEDS == (20260924, 1, 2, 3, 7, 101, 999)
    assert j10.POOL04_WINDOW_PP == 1.00


def test_a1_constructed_matrix_verdicts_and_holm_by_hand(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 0, report["headline"]
    p = by_id(report)
    # P1: 0.5 − 0.75 = −25 pp everywhere → CI [−25, −25]; two-sided p = 0.
    c1 = p["P1"]["contrast"]["scenario"]
    assert (c1["diff_pp"], c1["ci95_pp"], c1["n_pairs"], c1["n_clusters"]) == (-25.0, [-25.0, -25.0], 24, 4)
    assert p["P1"]["contrast"]["task"]["n_clusters"] == 12
    assert p["P1"]["p_value"] == 0.0
    # P3: 0.75 − 0.75 = 0 > −7 → supported; p(greater than −7) = 0.
    assert p["P3"]["contrast"]["scenario"]["ci95_pp"] == [0.0, 0.0]
    assert p["P3"]["p_value"] == 0.0
    # P4 / P5: difference exactly 0 → p = 1 (both tails hold all mass).
    assert p["P4"]["p_value"] == 1.0 and p["P5"]["p_value"] == 1.0
    # P6: 0.75 − 0.5 = +25 pp → p = 0.
    assert p["P6"]["contrast"]["scenario"]["ci95_pp"] == [25.0, 25.0]
    # Holm, m = 4, raw [0, 0, 1, 0] → adjusted [0, 0, 1, 0]. P5 is outside the family (A1 r2 §5.3).
    assert report["multiplicity"]["family"] == ["P1", "P3", "P4", "P6"]
    assert [p[i]["holm"]["p_adjusted"] for i in ("P1", "P3", "P4", "P6")] == [0, 0, 1, 0]
    assert "holm" not in p["P5"]
    assert report["verdicts"] == {
        "P1": "supported",
        "P2": "supported",
        "P3": "supported",
        "P4": "not_supported",  # point estimate 0 is not positive
        "P5": "supported",
        "P6": "supported",
    }
    assert p["P2"]["ratio"] == round(1414410.0 / 443361.0, 4)
    # P4 / P5 lower bounds sit exactly ON the threshold → POOL-04 fires, and the
    # seven recomputed bounds agree (a constant difference cannot move).
    for pid in ("P4", "P5"):
        pool = p[pid]["pool04"]
        assert pool["fired"] is True and pool["stable"] is True
        assert [row["seed"] for row in pool["bounds_by_seed"]] == list(j10.POOL04_SEEDS)
        assert [row["lo_pp"] for row in pool["bounds_by_seed"]] == [0.0] * 7
    for pid in ("P1", "P3", "P6"):
        assert p[pid]["pool04"]["fired"] is False
    assert report["not_the_j10_result"] is True


def test_holm_adjust_by_hand():
    # m=4: 0.005×4=0.02; 0.01×3=0.03; 0.03×2=0.06; 0.04×1=0.04 → running max 0.06.
    assert j10.holm_adjust([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert j10.holm_adjust([0.5, 0.6]) == pytest.approx([1.0, 1.0])


def _synthetic(pid, rule, t, point, lo, hi, p):
    return {"id": pid, "kind": "paired_contrast", "rule": rule, "threshold_pp": t,
            "holm_family": True, "decidable": True, "p_value": p,
            "_point": point / 100, "_lo": lo / 100, "_hi": hi / 100,
            "pool04": {"fired": False, "stable": True}}


def test_holm_can_withdraw_a_ci_supported_prediction():
    results = [
        _synthetic("P1", "negative_excludes_zero_with_reversal", 0.0, -6, -10, -2, 0.004),
        _synthetic("P3", "lower_bound_above_threshold", -7.0, -1, -5, 3, 0.03),
        _synthetic("P4", "positive_graded", 0.0, 2, -1, 5, 0.2),
        _synthetic("P5", "not_positive_excluding_zero", 0.0, -3, -8, 1, 0.6),
        _synthetic("P6", "lower_bound_above_threshold", 0.0, 4, 0.5, 9, 0.012),
    ]
    info = j10.a1_decide_family(results)
    r = {x["id"]: x for x in results}
    # sorted p: 0.004(P1)x5=0.02, 0.012(P6)x4=0.048, 0.03(P3)x3=0.09, 0.2(P4)x2=0.4, 0.6(P5)x1=0.6
    assert info["m"] == 5
    assert [r[i]["holm"]["p_adjusted"] for i in ("P1", "P3", "P4", "P5", "P6")] == pytest.approx(
        [0.02, 0.09, 0.4, 0.6, 0.048])
    assert {i: r[i]["verdict"] for i in r} == {
        "P1": "supported",
        "P3": "not_supported",  # CI lower bound −5 > −7, but Holm-adjusted p = 0.09
        "P4": "directionally_consistent",
        "P5": "supported",
        "P6": "supported",
    }


def test_pool04_flip_across_seeds_is_on_boundary_never_supported(tmp_path: Path, monkeypatch):
    dirs = write_a1_matrix(tmp_path)

    def fake_means(diffs, clusters, *, n_boot=10_000, seed=20260924):
        lo = -0.002 if seed == 7 else 0.005  # +0.50 pp at the registered seed
        return sorted([lo] * 300 + [0.10] * (n_boot - 300))

    monkeypatch.setattr(j10, "cluster_bootstrap_means", fake_means)
    p6 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P6"]
    report, _ = a1_report({k: dirs[k] for k in ("takeover_k10", "advise_k10_fullctx")},
                          predictions=p6, supporting=[])
    row = by_id(report)["P6"]
    assert row["verdict_unadjusted"] == "supported"
    assert row["verdict_holm"] == "supported"
    pool = row["pool04"]
    assert pool["fired"] is True and pool["stable"] is False
    by_seed = {b["seed"]: b["lo_pp"] for b in pool["bounds_by_seed"]}
    assert by_seed == {20260924: 0.5, 1: 0.5, 2: 0.5, 3: 0.5, 7: -0.2, 101: 0.5, 999: 0.5}
    assert row["verdict"] == "on_boundary"


def _planless_arm3(arm_root: Path, keys: list[tuple[str, int]]) -> None:
    """Arm 3 in its runner layout (planner_alone/<seed>/<task>), with these episodes' last
    attempt writing no plan -- the keys A1 §4.2 plans live and the sensitivity drops."""
    (arm_root / "sys").rename(arm_root / "planner_alone")
    for task_id, seed in keys:
        (arm_root / "planner_alone" / str(seed) / task_id / "events.jsonl").write_text(
            json.dumps({"event_type": "run_start", "payload": {}}) + "\n"
            + json.dumps({"event_type": "parse_error", "payload": {"text": "?"}}) + "\n",
            encoding="utf-8")


def test_a1_planless_keys_are_listed_and_a_stable_verdict_stands(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    _planless_arm3(dirs["planner_alone_cap81"], [("sc1_2", 1)])
    p6 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P6"]
    report, rc = a1_report({k: dirs[k] for k in ("takeover_k10", "advise_k10_fullctx", "planner_alone_cap81")},
                           predictions=p6, supporting=[])
    assert rc == 0, report["incomplete_reasons"]
    c = report["planless_contingency"]
    assert (c["keys"], c["n_keys"], c["cap"]) == (["1/sc1_2"], 1, 1)  # int(24 * 0.05)
    [row] = c["sensitivity"]["rows"]
    assert row["id"] == "P6" and row["differs"] is False
    assert row["contrast_without_keys"]["n_pairs"] == 23
    assert c["sensitivity"]["not_re_read"] == []
    assert by_id(report)["P6"]["verdict"] == "supported"


def test_a1_a_verdict_that_changes_without_the_planless_keys_is_on_the_boundary(tmp_path: Path):
    # +25 pp on every pair but three planless ones in scenario sc0, where takeover fails and
    # advice passes. With them the scenario CI reaches below zero; without them it is +25 pp.
    keys = [("sc0_1", 1), ("sc0_2", 1), ("sc0_3", 2)]
    grid = [(t, s) for t in A1_TASKS for s in A1_SEEDS]
    dirs = {
        "takeover_k10": write_a1_arm(tmp_path, "takeover_k10", {k: 0.0 if k in keys else 0.75 for k in grid}),
        "advise_k10_fullctx": write_a1_arm(tmp_path, "advise_k10_fullctx",
                                           {k: 1.0 if k in keys else 0.5 for k in grid}),
        "planner_alone_cap81": write_a1_arm(tmp_path, "planner_alone_cap81", 0.75),
    }
    _planless_arm3(dirs["planner_alone_cap81"], keys)
    p6 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P6"]
    report, rc = a1_report(dirs, predictions=p6, supporting=[])
    row = by_id(report)["P6"]
    [sens] = report["planless_contingency"]["sensitivity"]["rows"]
    assert sens["verdict_holm_without_keys"] == "supported"
    assert sens["verdict_holm_all_pairs"] != "supported" and sens["differs"] is True
    assert row["verdict"] == "on_boundary"
    assert row["verdict_before_key_exclusion"] == row["verdict_holm"]
    assert report["verdicts"]["P6"] == "on_boundary"
    # 3 of 24 is above the 5 % cap (1): the wrapper would have refused, and the report says so.
    assert rc == 1 and "planless_keys_above_cap:3>1" in report["incomplete_reasons"]


def test_a1_planless_contingency_without_arm_3(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    p6 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P6"]
    report, _ = a1_report({k: dirs[k] for k in ("takeover_k10", "advise_k10_fullctx")},
                          predictions=p6, supporting=[])
    c = report["planless_contingency"]
    assert c["keys"] is None and c["sensitivity"] is None and "not given" in c["note"]


def test_crash_is_not_an_outcome_limit_is(tmp_path: Path):
    key = (A1_TASKS[0], 1)
    dirs = {
        "prefix_m11": write_a1_arm(tmp_path, "prefix_m11", 0.75, error_types={key: "crash"}),
        "advise_k1_fullctx": write_a1_arm(tmp_path, "advise_k1_fullctx", 0.5,
                                          error_types={key: "limit"}),
    }
    p1 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P1"]
    report, rc = a1_report(dirs, predictions=p1, supporting=[])
    assert rc == 1
    arms = report["arms"]
    assert arms["prefix_m11"]["n_crash"] == 1 and arms["prefix_m11"]["complete"] is False
    assert arms["advise_k1_fullctx"]["n_crash"] == 0 and arms["advise_k1_fullctx"]["complete"] is True
    assert arms["advise_k1_fullctx"]["error_types"]["limit"] == 1
    row = by_id(report)["P1"]
    assert row["verdict"] == "refused_incomplete"
    assert row["contrast"]["n_pairs"] == 23  # the crashed pair is dropped, not scored 0


def test_split_provenance_mismatch_refuses_every_prediction(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, manifest_split="dev")
    report, rc = a1_report(dirs, split="test_normal", confirm_heldout_test_split=True,
                           cost_report=A1_COST_REPORT)
    assert rc == 1
    assert any(r.startswith("split_provenance_mismatch") for r in report["incomplete_reasons"])
    assert set(report["verdicts"].values()) == {"refused_incomplete"}


def test_a1_protocol_refusals(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    _, rc = a1_report(dirs, split="test_challenge", confirm_heldout_test_split=True)
    assert rc == 2
    _, rc = a1_report(dirs, split="test_normal")
    assert rc == 2
    _, rc = a1_report(dirs, split="test_normal", confirm_heldout_test_split=True, n_boot=2000)
    assert rc == 2
    _, rc = a1_report(dirs, out_path=Path("/scratch/n12194778/sidekick/results/x.json"))
    assert rc == 2


def test_permutation_p_is_reported_beside_the_verdict_not_decision_bearing(tmp_path, monkeypatch):
    dirs = write_a1_matrix(tmp_path)
    calls = []

    def stub(diffs, clusters, *, threshold, alternative, seed):
        calls.append((list(diffs), list(clusters), threshold, alternative, seed))
        # p = 0.5 would contradict every "supported" verdict if it were decision-bearing.
        return {"p": 0.5, "method": "exact", "n_patterns": 16, "n_clusters": 4}

    monkeypatch.setattr(j10, "_load_cluster_signflip", lambda: stub)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    p = by_id(report)
    for pid in ("P1", "P3", "P4", "P5", "P6"):
        perm = p[pid]["permutation_sensitivity"]
        assert perm["status"] == "ok" and perm["p_value"] == 0.5
        assert perm["decision_bearing"] is False
        assert (perm["method"], perm["n_patterns"]) == ("exact", 16)
    assert p["P1"]["verdict"] == "supported"
    # P1, P3, P4, P5, P6, then Amendment 1's CF1 (§C applies §5.5 to it).
    assert len(calls) == 6
    cf1 = report["amendment1"]["cf"]["predictions"][0]["permutation_sensitivity"]
    assert cf1["decision_bearing"] is False and cf1["p_value"] == 0.5
    # P3 (A1:270): one-sided at its −7 pp threshold; the routine does the shift.
    diffs, clusters, threshold, alternative, seed = calls[1]
    assert diffs == pytest.approx([0.0] * 24)
    assert sorted(set(clusters)) == ["sc0", "sc1", "sc2", "sc3"]
    assert (threshold, alternative, seed) == (pytest.approx(-0.07), "greater", 20260924)
    # Every other prediction is two-sided at its threshold.
    assert {c[3] for i, c in enumerate(calls) if i != 1} == {"two-sided"}
    assert report["permutation_rule"]["one_sided"] == {"P3": "greater"}
    monkeypatch.setattr(j10, "_load_cluster_signflip", lambda: None)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert by_id(report)["P1"]["permutation_sensitivity"]["status"] == "unavailable"


def test_permutation_uses_the_registered_routine_exact_below_2_pow_20(tmp_path):
    # 4 scenario clusters -> 16 patterns, enumerated. P3's arm − ceiling is 0 everywhere,
    # i.e. +7 pp above its −7 pp threshold on every cluster: the 'greater' p is the one
    # all-positive pattern of 16 that is as extreme, 1/16; P6's +25 pp two-sided p is 2/16.
    dirs = write_a1_matrix(tmp_path)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    p = by_id(report)
    p3, p6 = p["P3"]["permutation_sensitivity"], p["P6"]["permutation_sensitivity"]
    assert (p3["method"], p3["n_patterns"], p3["n_clusters"]) == ("exact", 16, 4)
    assert p3["p_value"] == pytest.approx(1 / 16) and p3["alternative"] == "greater"
    assert p6["p_value"] == pytest.approx(2 / 16) and p6["alternative"] == "two-sided"


def test_p6_reversed_mirrors_p1_unadjusted_ci_and_holm_adjusted_two_sided_p():
    rules = j10.A1_RULES
    p1_rule, p6_rule = rules["negative_excludes_zero_with_reversal"], rules["positive_excludes_zero_with_reversal"]
    assert p1_rule["direction"] == p6_rule["direction"] == "two-sided"
    p6 = next(p for p in j10.A1_PREDICTIONS if p["id"] == "P6")
    assert p6["rule"] == "positive_excludes_zero_with_reversal"
    # A1:377-378 (F4): the registered-orientation upper bound.
    assert p6["dev_reference"]["ci95_pp_scenario"] == [1.29, 13.49]

    def family(p6_point, p6_lo, p6_hi, p6_p):
        results = [
            _synthetic("P1", "negative_excludes_zero_with_reversal", 0.0, 6, 2, 10, 0.004),
            _synthetic("P6", "positive_excludes_zero_with_reversal", 0.0, p6_point, p6_lo, p6_hi, p6_p),
        ]
        j10.a1_decide_family(results)
        return {r["id"]: r["verdict"] for r in results}

    # Both CIs sit on the wrong side of zero, both Holm-adjusted p reject: both reversed.
    assert family(-5, -9, -1, 0.01) == {"P1": "reversed", "P6": "reversed"}
    # The same P6 interval with a Holm-adjusted p above 0.05 (m = 2: max(2 x 0.004, 0.06))
    # is not reversed -- as for P1.
    assert family(-5, -9, -1, 0.06) == {"P1": "reversed", "P6": "not_supported"}
    assert family(5, 1, 9, 0.01)["P6"] == "supported"
    assert family(2, -1, 5, 0.01)["P6"] == "not_supported"


def test_p6_reversed_on_a_constructed_matrix(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, gp={"takeover_k10": 0.25})  # 0.25 − 0.5 = −25 pp
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    row = by_id(report)["P6"]
    assert row["contrast"]["scenario"]["ci95_pp"] == [-25.0, -25.0]
    assert row["verdict_unadjusted"] == row["verdict"] == "reversed"


def test_pool04_reports_the_200k_bound_only_when_it_fires(tmp_path: Path, monkeypatch):
    dirs = write_a1_matrix(tmp_path)
    seen = []

    def fake_means(diffs, clusters, *, n_boot=10_000, seed=20260924):
        seen.append((n_boot, seed))
        return [-0.002 if seed == 7 else 0.005] * n_boot  # +0.50 pp, inside the 1 pp window

    monkeypatch.setattr(j10, "cluster_bootstrap_means", fake_means)
    p6 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P6"]
    report, _ = a1_report({k: dirs[k] for k in ("takeover_k10", "advise_k10_fullctx")},
                          predictions=p6, supporting=[], exploratory=[])
    pool = by_id(report)["P6"]["pool04"]
    assert pool["bound_200k"] == {"n_boot": 200_000, "seed": 20260924, "lo_pp": 0.5, "hi_pp": 0.5,
                                  "verdict": "supported", "decision_bearing": False}
    assert (200_000, 20260924) in seen
    # The seven seeds alone decide: seed 7 flips, so it is on the boundary whatever 200k says.
    assert pool["stable"] is False and by_id(report)["P6"]["verdict"] == "on_boundary"
    assert report["stability_rule"]["reported_bound"] == {"n_boot": 200_000, "seed": 20260924}
    monkeypatch.undo()
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)  # real bootstrap: P1 is far from 0
    assert by_id(report)["P1"]["pool04"]["fired"] is False
    assert "bound_200k" not in by_id(report)["P1"]["pool04"]
    assert "bound_200k" in by_id(report)["P4"]["pool04"]  # P4's lower bound sits on 0


def test_supporting_registry_is_r2_table_verbatim():
    lines = (REPO_ROOT / j10.A1_PREREG).read_text(encoding="utf-8").splitlines()
    rows = {s["id"]: s for s in j10.A1_SUPPORTING}
    assert list(rows) == ["S1", "S2", "S3", "S4", "S5", "S6"]
    # Each row's citation points at the r2 table line that registers it, in its orientation.
    expected = {
        "S1": ("advise_k1_fullctx", "prefix_m9", "`advise_k1 − prefix_m9`"),
        "S2": ("advise_k10_fullctx", "prefix_m11", "`advise_k10 − prefix_m11`"),
        "S3": ("prefix_m11", "prefix_m9", "`prefix_m11 − prefix_m9` (tailored depth)"),
        "S4": (["prefix_m11", "prefix_m9"], ["prefix_zs_m11", "prefix_zs_m9"],
               "`(m11 − m9)_tailored − (m11 − m9)_untailored` (R2)"),
        "S5": ("prefix_m11", "executor_alone_bplus", "`prefix_m11 − executor_alone_bplus`"),
    }
    for sid, (left, right, text) in expected.items():
        assert (rows[sid]["left"], rows[sid]["right"]) == (left, right)
        line_no = int(rows[sid]["citation"].rsplit(":", 1)[1])
        assert text in lines[line_no - 1], sid
    assert rows["S3"]["dev_reference"]["ci95_pp_scenario"] == [0.15, 8.75]
    assert rows["S4"]["dev_reference"] == {"diff_pp": 2.81, "ci95_pp_scenario": [-2.57, 8.96],
                                           "n_pairs": 171, "source": "POOL-03"}
    s6 = rows["S6"]
    assert "handoff-only depth" in lines[int(s6["citation"].rsplit(":", 1)[1]) - 1]
    assert s6["receivers"] == {"tailored": ["prefix_m11", "prefix_m9"],
                               "untailored": ["prefix_zs_m11", "prefix_zs_m9"]}
    # r1's S4 (ceiling − untailored m11) is not in r2's table: exploratory, not supporting.
    assert [(e["id"], e["left"], e["right"]) for e in j10.A1_EXPLORATORY] == [
        ("E1", "planner_alone_cap81", "prefix_zs_m11"),
        ("E2", "takeover_k10", "show_k10"),
        ("E3", "show_k10", "advise_k10_fullctx"),
        ("E4", "advise_k10_neutral", "advise_k10_fullctx"),
        ("E5", "takeover_k10", "advise_k10_neutral")]


def test_arms_11_and_12_are_exploratory_rows_cited_to_the_r3_p7_table():
    # A1 r3 completed P7 from an unresolved B2: no P7 prediction, and arms 11-12 appear only
    # as the exploratory rows E2-E5, each citing the r3 table line that registers it.
    lines = (REPO_ROOT / j10.A1_PREREG).read_text(encoding="utf-8").splitlines()
    rows = {e["id"]: e for e in j10.A1_EXPLORATORY}
    for eid in ("E2", "E3", "E4", "E5"):
        e = rows[eid]
        line = lines[int(e["citation"].rsplit(":", 1)[1]) - 1]
        assert line.startswith(f"| {eid} | `{e['left']} − {e['right']}`"), eid
        assert e["dev_reference"]["n_pairs"] == 171
    assert not [p for p in j10.A1_PREDICTIONS if p["id"].startswith("P7")]
    assert {"show_k10", "advise_k10_neutral"} <= set(j10.A1_ARMS)


def test_supporting_and_exploratory_contrasts_on_a_constructed_matrix(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    s = {r["id"]: r for r in report["supporting_contrasts"]}
    # Constant dyadic values (A1_CONSTANT_GP): every interval is its point.
    assert s["S1"]["goal_pass"]["scenario"]["ci95_pp"] == [-12.5, -12.5]  # 0.5 − 0.625
    assert s["S2"]["goal_pass"]["scenario"]["diff_pp"] == -25.0           # 0.5 − 0.75
    assert s["S3"]["goal_pass"]["scenario"]["diff_pp"] == 12.5            # 0.75 − 0.625
    # DiD: (0.75 − 0.625) − (0.5 − 0.5) = +12.5 pp, both clusterings.
    s4 = s["S4"]["goal_pass"]
    assert (s4["n_pairs"], s4["scenario"]["ci95_pp"], s4["task"]["ci95_pp"]) == (24, [12.5, 12.5], [12.5, 12.5])
    assert s["S5"]["goal_pass"]["scenario"]["diff_pp"] == 37.5            # 0.75 − 0.375
    assert all(r["decision_bearing"] is False for r in s.values())
    e = {r["id"]: r for r in report["exploratory_contrasts"]}
    assert list(e) == ["E1", "E2", "E3", "E4", "E5"]
    assert all(r["exploratory"] is True and r["decision_bearing"] is False for r in e.values())
    assert e["E1"]["goal_pass"]["scenario"]["diff_pp"] == 25.0            # 0.75 − 0.5
    # Arms 11-12 (A1 r3, exploratory): show 0.625, neutral 0.5, takeover 0.75, advice 0.5.
    assert [e[k]["goal_pass"]["scenario"]["diff_pp"] for k in ("E2", "E3", "E4", "E5")] == [
        12.5, 12.5, 0.0, 25.0]
    # No events.jsonl in this tree: every handoff flag is missing, and says so.
    assert report["no_handoff_counts"]["prefix_m11"] == {
        "m": 11, "n_scored": 24, "n_handoff": 0, "n_no_handoff": 0, "n_flag_missing": 24,
        "citation": f"{j10.A1_PREREG}:520-523"}


def test_handoff_only_depth_and_no_handoff_counts(tmp_path: Path):
    # Scenarios sc0, sc1 hand off at m = 11; sc2, sc3 finish within m (no handoff).
    handoff = {(t, s): t.startswith(("sc0", "sc1")) for t in A1_TASKS for s in A1_SEEDS}
    m11 = {k: (0.875 if h else 0.75) for k, h in handoff.items()}
    dirs = {
        "prefix_m11": write_a1_arm(tmp_path, "prefix_m11", m11, handoff=handoff),
        "prefix_m9": write_a1_arm(tmp_path, "prefix_m9", 0.625,
                                  handoff={k: False for k in handoff}),
        "prefix_zs_m11": write_a1_arm(tmp_path, "prefix_zs_m11", 0.5, handoff=handoff),
        "prefix_zs_m9": write_a1_arm(tmp_path, "prefix_zs_m9", 0.5),
    }
    # An earlier attempt said "handed off"; only the last attempt's report counts.
    ev = dirs["prefix_zs_m11"] / "sys" / "1" / "sc3_1" / "events.jsonl"
    ev.write_text("".join(json.dumps(e) + "\n" for e in [
        {"event_type": "run_start"}, {"event_type": "report", "payload": {"handoff_occurred": True}},
        {"event_type": "run_start"}, {"event_type": "report", "payload": {"handoff_occurred": False}},
    ]), encoding="utf-8")
    report, _ = a1_report(dirs, predictions=[])
    counts = report["no_handoff_counts"]
    assert {a: (c["n_handoff"], c["n_no_handoff"], c["n_flag_missing"]) for a, c in counts.items()} == {
        "prefix_m11": (12, 12, 0), "prefix_m9": (0, 24, 0),
        "prefix_zs_m11": (12, 12, 0), "prefix_zs_m9": (0, 0, 24)}
    s6 = next(r for r in report["supporting_contrasts"] if r["id"] == "S6")
    tailored = s6["goal_pass"]["tailored"]
    assert tailored["status"] == "ok" and (tailored["n_pairs"], tailored["n_handoff"]) == (24, 12)
    # d = 0.25 on handoff episodes, 0.125 elsewhere: handoff-only +25 pp, all +18.75 pp.
    assert tailored["handoff_only"]["diff_pp"] == 25.0
    assert tailored["handoff_only"]["ci95_pp_scenario"] == [25.0, 25.0]
    assert tailored["all"]["diff_pp"] == 18.75
    assert s6["goal_pass"]["untailored"]["handoff_only"]["diff_pp"] == 0.0
    assert s6["handoff_flag_mismatch_between_receivers"] == 0
    # S3 over all episodes reports the same +18.75 pp: §7 item 4's "both" populations.
    s3 = next(r for r in report["supporting_contrasts"] if r["id"] == "S3")
    assert s3["goal_pass"]["scenario"]["diff_pp"] == 18.75


def test_sgc_for_p1_and_p6_is_descriptive(tmp_path: Path):
    ok = {(t, s): True for t in A1_TASKS for s in A1_SEEDS}
    one_fail = dict(ok)
    one_fail[("sc0_2", 1)] = False  # unit (sc0, 1) fails; the other 7 pass
    dirs = write_a1_matrix(tmp_path)
    dirs["prefix_m11"] = write_a1_arm(tmp_path / "x", "prefix_m11", 0.75, success=ok)
    dirs["advise_k1_fullctx"] = write_a1_arm(tmp_path / "x", "advise_k1_fullctx", 0.5, success=one_fail)
    # A crash leaves its unit unscored, not failed (A1 F6).
    dirs["takeover_k10"] = write_a1_arm(tmp_path / "x", "takeover_k10", 0.75, success=ok,
                                        error_types={("sc3_1", 2): "crash"})
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    sgc = report["sgc"]
    assert set(sgc) == {"P1", "P6"}
    p1 = sgc["P1"]
    assert (p1["left"], p1["right"], p1["descriptive"], p1["decision_bearing"]) == (
        "advise_k1_fullctx", "prefix_m11", True, False)
    assert (p1["n_units_registered"], p1["n_units_shared"]) == (8, 8)
    assert (p1["n_passed_left"], p1["n_passed_right"], p1["diff_pp"]) == (7, 8, -12.5)
    p6 = sgc["P6"]
    assert (p6["n_units_unscored_left"], p6["n_units_shared"]) == (1, 7)
    assert (p6["sgc_left"], p6["sgc_right"]) == (1.0, 0.0)


def test_p2_ratio_interval_is_information_only_and_is_f_f_draw_for_draw():
    import random as _random

    p2 = next(p for p in j10.A1_PREDICTIONS if p["id"] == "P2")
    rng = _random.Random(11)
    left_rows, right_rows = [], []
    for task_id in A1_TASKS:
        for seed in A1_SEEDS:
            left_rows.append({"task_id": task_id, "seed": seed,
                              "noncached_tokens_per_episode": 1e6 * (1 + rng.random())})
            right_rows.append({"task_id": task_id, "seed": seed,
                               "noncached_tokens_per_episode": 4e5 * (1 + rng.random())})
    cost = json.loads(json.dumps(A1_COST_REPORT))
    cost["arms"]["advise_k1_fullctx"]["episodes"] = left_rows
    cost["arms"]["prefix_m11"]["episodes"] = right_rows
    row = j10.a1_evaluate_cost_prediction(p2, cost, expected_n=24)
    # The verdict stays on the arm means (A1:296), whatever the interval says.
    assert row["verdict"] == "supported" and row["ratio"] == round(1414410.0 / 443361.0, 4)
    iv = row["ratio_interval"]
    assert iv["status"] == "ok" and iv["information_only"] is True and iv["decision_bearing"] is False
    assert (iv["n_pairs"], iv["n_clusters"], iv["seed"], iv["n_boot"]) == (24, 4, 20260924, 10_000)
    # Same numbers as j16_robustness.cost_contrast (F-f, the dev [2.47, 4.06] source).
    j16 = j10._load_j16()
    a = {(r["task_id"], r["seed"]): r for r in left_rows}
    b = {(r["task_id"], r["seed"]): r for r in right_rows}
    ff = j16.cost_contrast(a, b, "noncached_tokens_per_episode", (("scenario", 20260924),), 10_000)
    ff_ci = ff[j16._boot_name("scenario", 20260924)]["ratio_ci95"]
    assert iv["ci95"] == [round(ff_ci[0], 4), round(ff_ci[1], 4)]
    assert iv["point"] == round(ff["mean_left"] / ff["mean_right"], 4)
    # A cost report without per-episode rows still gives the point verdict.
    bare = j10.a1_evaluate_cost_prediction(p2, A1_COST_REPORT, expected_n=24)
    assert bare["verdict"] == "supported" and bare["ratio_interval"]["status"] == "not_computed"


def test_no_r2_record_is_left_open():
    # Each r2-vs-code record was removed when the code came to implement r2.
    assert {a["status"] for a in j10.A1_AMBIGUITIES} == {"resolved_by_r2"}


def test_load_predictions_refuses_an_unknown_permutation_side_or_supporting_kind(tmp_path: Path):
    bad = tmp_path / "bad.json"
    p3 = dict(next(p for p in j10.A1_PREDICTIONS if p["id"] == "P3"), permutation_alternative="upper")
    bad.write_text(json.dumps([p3]), encoding="utf-8")
    with pytest.raises(ValueError, match="permutation_alternative"):
        j10.load_predictions(bad)
    bad.write_text(json.dumps({"predictions": list(j10.A1_PREDICTIONS),
                               "supporting": [{"id": "X", "kind": "triple"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown kind"):
        j10.load_predictions(bad)


def test_a_p7_is_a_registry_entry_not_code(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    p7 = {"id": "P7", "kind": "paired_contrast", "metric": "goal_pass", "left": "prefix_m9",
          "right": "executor_alone", "rule": "lower_bound_above_threshold",
          "threshold_pp": 0.0, "holm_family": True}
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"predictions": list(j10.A1_PREDICTIONS) + [p7]}), encoding="utf-8")
    preds, support = j10.load_predictions(path)
    report, rc = a1_report(dirs, predictions=preds, supporting=support, cost_report=A1_COST_REPORT)
    assert rc == 0
    assert report["multiplicity"]["m"] == 5  # P1, P3, P4, P6 + the added P7 (P5 is outside, A1 r2 §5.3)
    assert report["verdicts"]["P7"] == "supported"  # 0.625 − 0.25 = +37.5 pp
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([dict(p7, rule="no_such_rule")]), encoding="utf-8")
    with pytest.raises(ValueError):
        j10.load_predictions(bad)


def test_cost_prediction_p2():
    p2 = next(p for p in j10.A1_PREDICTIONS if p["id"] == "P2")
    row = j10.a1_evaluate_cost_prediction(p2, A1_COST_REPORT, expected_n=24)
    assert row["verdict"] == "supported" and row["calls_strictly_more"] is True
    cheap = json.loads(json.dumps(A1_COST_REPORT))
    cheap["arms"]["advise_k1_fullctx"]["noncached_tokens_per_episode"] = 1.5 * 443361.0
    assert j10.a1_evaluate_cost_prediction(p2, cheap, expected_n=24)["verdict"] == "not_supported"
    assert j10.a1_evaluate_cost_prediction(p2, None, expected_n=24)["verdict"] == "not_computed"
    assert j10.a1_evaluate_cost_prediction(p2, A1_COST_REPORT, expected_n=336)["verdict"] == "refused_incomplete"


def test_main_dispatches_a1_by_default_and_v1_on_request(tmp_path: Path, capsys):
    dirs = write_a1_matrix(tmp_path)
    argv = ["--split", "dev", "--expected-n-tasks", str(len(A1_TASKS))]
    for label, path in dirs.items():
        argv += ["--arm", f"{label}={path}"]
    rc = j10.main(argv)
    report = json.loads(capsys.readouterr().out)
    assert report["protocol"] == "A1" and rc == 1  # P2 has no cost report
    assert report["verdicts"]["P2"] == "not_computed"
    rc = j10.main(["--protocol", "v1", "--split", "dev", "--seeds", "1", "--arm",
                   "not_an_arm=/tmp/x", "--plumbing-check"])
    assert rc == 2


def test_bootstrap_is_draw_for_draw_j8_frontier_and_hj1_gate():
    """Same RNG consumption and percentile indices as the engine A1 §5.2 names."""
    import random as _random

    spec = importlib.util.spec_from_file_location(
        "j8_frontier_for_j10_test", REPO_ROOT / "scripts" / "analysis" / "j8_frontier.py")
    j8 = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(j8)
    rng = _random.Random(3)
    left, right = {}, {}
    for task_id in A1_TASKS:
        for seed in A1_SEEDS:
            left[(task_id, seed)] = {"goal_pass_rate": rng.random()}
            right[(task_id, seed)] = {"goal_pass_rate": rng.random()}
    ours = j10.a1_contrast(left, right, "goal_pass_rate", seed=j10.SEED)
    theirs_scen = j8.paired_diff_scenario(left, right, "goal_pass_rate")
    theirs_task = j10.paired_diff(left, right, "goal_pass_rate", resample="task")
    assert ours["scenario"]["ci95_pp"] == theirs_scen["ci95_pp"]
    assert ours["scenario"]["diff_pp"] == theirs_scen["diff_pp"]
    assert ours["task"]["ci95_pp"] == theirs_task["ci95_pp"]


def _dev_arm(name: str) -> dict:
    root = DEV_RESULTS / name
    if not root.is_dir():
        pytest.skip(f"dev campaign {root} not on this machine")
    loaded = j10.load_arm_tree(root)
    tasks = j10.discover_tasks({name: loaded}, list(A1_SEEDS))
    return j10.a1_arm_episodes(name, loaded, tasks, list(A1_SEEDS))


def test_regression_p1_reproduces_the_a1_dev_reference():
    """A1 §6 P1: −14.81 pp, scenario [−21.20, −7.96], task [−21.73, −8.02].

    The dev basis report stores the contrast but not the episodes, so the check
    re-runs the contrast on the dev campaigns it summarises, under the bootstrap
    seed those numbers were computed with (hj1_gate.SEED = 20260915), and also
    confirms the stored key says the same.
    """
    advise = _dev_arm("hj13_advise_fixed_k_1_fullctx_20260923")
    prefix = _dev_arm("hj17_prefix_c81_bplus_m11_20260923")
    assert advise["n_scored"] == prefix["n_scored"] == 114
    cmp = j10.a1_contrast(advise["episodes"], prefix["episodes"], "goal_pass_rate",
                          seed=j10.DEV_BASIS_BOOTSTRAP_SEED)
    assert cmp["n_pairs"] == 114
    assert cmp["scenario"]["diff_pp"] == -14.81
    assert cmp["scenario"]["ci95_pp"] == [-21.20, -7.96]
    assert cmp["task"]["ci95_pp"] == [-21.73, -8.02]
    stored = json.loads((REPO_ROOT / j10.A1_DEV_BASIS).read_text(encoding="utf-8"))
    key = stored["contrasts"]["goal_pass_all_advise_k1_minus_c81_bp_m11"]
    assert key["diff_pp"] == cmp["scenario"]["diff_pp"]
    assert key["ci95_pp"] == cmp["scenario"]["ci95_pp"]
    assert key["ci95_pp_task"] == cmp["task"]["ci95_pp"]
    # Under the registered seed the verdict is the same; only the interval moves.
    reg = j10.a1_contrast(advise["episodes"], prefix["episodes"], "goal_pass_rate")
    assert reg["scenario"]["diff_pp"] == -14.81
    assert reg["scenario"]["hi"] < 0


def test_regression_p6_dev_reference_upper_bound_is_13_49_not_13_48():
    takeover = _dev_arm("hj12_takeover_fixed_k_10_20260923")
    advise10 = _dev_arm("hj12_advise_fixed_k_10_fullctx_20260923")
    cmp = j10.a1_contrast(takeover["episodes"], advise10["episodes"], "goal_pass_rate",
                          seed=j10.DEV_BASIS_BOOTSTRAP_SEED)
    assert cmp["n_pairs"] == 114
    assert cmp["scenario"]["diff_pp"] == 6.69
    # Direct orientation gives +13.49; negating advise − takeover gives +13.48
    # (one order statistic apart under lo = means[250], hi = means[9750]).
    assert cmp["scenario"]["ci95_pp"] == [1.29, 13.49]
    rev = j10.a1_contrast(advise10["episodes"], takeover["episodes"], "goal_pass_rate",
                          seed=j10.DEV_BASIS_BOOTSTRAP_SEED)
    assert [-v for v in reversed(rev["scenario"]["ci95_pp"])] == [1.29, 13.48]


# ===========================================================================
# Amendment 1 (pre-data additions after the adversarial review): family CF, handoff-only NI,
# decomposition, chord, limits, the P1 constraint and BY-FDR. Every expected value is by hand.
# ===========================================================================

# Overrides that keep every registered bound away from its threshold, so POOL-04 never fires
# (and never draws 200,000 resamples) in these tests: P1 −50, P4 +12.5, P5 −25, CF1 +25 pp.
AM1_GP = {"advise_k1_fullctx": 0.25, "prefix_zs_m11": 0.625, "advise_k10_neutral": 0.75}
HANDOFF_KEYS = [(t, s) for t in A1_TASKS if t.endswith("_1") for s in A1_SEEDS]  # 8 of 24, every scenario
GRID = [(t, s) for t in A1_TASKS for s in A1_SEEDS]


def test_am1_registry_keeps_the_frozen_family_and_adds_cf_alone():
    [cf1] = j10.A1_AM1_CF
    assert (cf1["id"], cf1["left"], cf1["right"], cf1["family"]) == (
        "CF1", "advise_k10_neutral", "advise_k10_fullctx", "CF")
    assert cf1["rule"] == "positive_excludes_zero_with_reversal" and cf1["threshold_pp"] == 0.0
    assert cf1["dev_reference"]["diff_pp"] == 3.73 and cf1["dev_reference"]["ci95_pp_scenario"] == [-0.06, 8.24]
    assert "CF1" not in {p["id"] for p in j10.A1_PREDICTIONS}
    assert [s["id"] for s in j10.A1_AM1_CF_SECONDARY] == ["CF2", "CF3"]
    assert [s["same_contrast_as"] for s in j10.A1_AM1_CF_SECONDARY] == ["E3", "E5"]
    assert j10.A1_AM1_NI_MARGIN_PP == -7.00
    assert j10.A1_AM1.endswith("Amendment 1")


def test_am1_cf_is_its_own_family_and_p1_p6_are_untouched(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 0, report["headline"]
    assert report["multiplicity"]["family"] == ["P1", "P3", "P4", "P6"]
    assert set(report["verdicts"]) == {"P1", "P2", "P3", "P4", "P5", "P6"}
    cf = report["amendment1"]["cf"]
    assert cf["status"] == "run"
    assert (cf["multiplicity"]["family"], cf["multiplicity"]["m"]) == (["CF1"], 1)
    [cf1] = cf["predictions"]
    # 0.75 − 0.5 = +25 pp on every pair → CI [25, 25], p = 0; Holm with m = 1 leaves p alone.
    assert cf1["contrast"]["scenario"]["ci95_pp"] == [25.0, 25.0]
    assert cf1["holm"]["m"] == 1 and cf1["holm"]["p_adjusted"] == 0.0
    assert cf1["verdict"] == "supported" and cf1["reading"].startswith("advice written under a neutral prompt")
    assert cf1["pool04"]["fired"] is False and "permutation_sensitivity" in cf1
    assert report["headline"].endswith("Amendment 1 CF1: supported.")
    sec = {s["id"]: s for s in cf["secondary"]}
    # CF2: show 0.625 − advice 0.5 = +12.5 → above. CF3: takeover 0.75 − neutral 0.75 = 0 → not resolved.
    assert (sec["CF2"]["side"], sec["CF2"]["status"]) == ("above", "ok")
    assert sec["CF2"]["reading"] == "the planner's action shown as text beats correction-prompt advice"
    assert sec["CF3"]["side"] == "not_resolved"
    assert sec["CF3"]["reading"] == "the added effect of execution is not resolved at 336 pairs"
    assert sec["CF2"]["decision_bearing"] is False and sec["CF3"]["adjusted"] is False
    assert report["amendment1"]["p1_reporting_constraint"]["never_as"] == [
        "advice at matched budget", "ruling out a budget effect"]


def test_am1_cf_not_run_when_arms_11_12_are_absent(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    dirs.pop("advise_k10_neutral")
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    cf = report["amendment1"]["cf"]
    assert cf["status"] == "not_run" and cf["verdicts"] == {"CF1": "arm_absent"}
    assert report["headline"].endswith("Amendment 1 CF1: not run.")
    assert {s["id"]: s["status"] for s in cf["secondary"]} == {"CF2": "ok", "CF3": "arm_absent"}


def test_am1_cf1_goes_on_the_boundary_when_the_planless_keys_move_it(tmp_path: Path):
    # test_a1_a_verdict_that_changes_without_the_planless_keys_is_on_the_boundary, for CF1.
    keys = [("sc0_1", 1), ("sc0_2", 1), ("sc0_3", 2)]
    dirs = {
        "advise_k10_neutral": write_a1_arm(tmp_path, "advise_k10_neutral",
                                           {k: 0.0 if k in keys else 0.75 for k in GRID}),
        "advise_k10_fullctx": write_a1_arm(tmp_path, "advise_k10_fullctx",
                                           {k: 1.0 if k in keys else 0.5 for k in GRID}),
        "planner_alone_cap81": write_a1_arm(tmp_path, "planner_alone_cap81", 0.75),
    }
    _planless_arm3(dirs["planner_alone_cap81"], keys)
    p6 = [dict(p) for p in j10.A1_PREDICTIONS if p["id"] == "P6"]
    report, _ = a1_report(dirs, predictions=p6, supporting=[])
    cf = report["amendment1"]["cf"]
    [sens] = cf["key_exclusion"]["rows"]
    assert sens["id"] == "CF1" and sens["verdict_holm_without_keys"] == "supported"
    assert sens["differs"] is True
    [cf1] = cf["predictions"]
    assert cf1["verdict"] == "on_boundary" and cf1["reading"] is None
    assert report["verdicts"]["P6"] == "arm_absent"  # P1-P6's own contingency is unaffected


def test_am1_handoff_only_ni_by_hand(tmp_path: Path):
    # prefix_m11 hands off on 8 keys (one task per scenario) and scores 0.25 there, 0.75 elsewhere;
    # planner_alone_cap81 scores 0.75. d = −0.5 on handoff pairs, 0 on silenced ones.
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    write_a1_arm(tmp_path, "prefix_m11", {k: 0.25 if k in HANDOFF_KEYS else 0.75 for k in GRID},
                 handoff={k: k in HANDOFF_KEYS for k in GRID})
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    b1 = {r["id"]: r for r in report["amendment1"]["handoff_only_ni"]}
    gp = b1["B1a"]["goal_pass"]
    assert (gp["n_pairs"], gp["n_handoff"], gp["n_silenced"], gp["n_flag_missing"]) == (24, 8, 16, 0)
    # Every scenario holds 2 handoff pairs, so Σd·h/Σh = −0.5 in every resample.
    assert gp["handoff_only"]["diff_pp"] == -50.0
    assert gp["handoff_only"]["ci95_pp_scenario"] == [-50.0, -50.0]
    assert gp["silenced"]["diff_pp"] == 0.0
    assert gp["all"]["diff_pp"] == round(-0.5 * 8 / 24 * 100, 2)  # −16.67
    assert gp["ni"]["reading"] == "fails" and gp["ni"]["fired"] is False
    assert gp["p_value_two_sided_at_margin"] == 0.0  # every resample sits below −7
    assert b1["B1a"]["decision_bearing"] is False
    # P3's all-episode verdict is decided on its own contrast (−16.67 < −7 → not supported).
    assert report["verdicts"]["P3"] == "not_supported"
    # prefix_zs_m11 wrote no report events: every flag is missing, so no handoff-only estimand.
    zs = b1["B1b"]["goal_pass"]
    assert (zs["n_handoff"], zs["n_flag_missing"]) == (0, 24)
    assert zs["ni"]["reading"] == "undefined"


def test_am1_handoff_only_ni_holds_when_handoff_pairs_match(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    write_a1_arm(tmp_path, "prefix_m11", 0.75, handoff={k: k in HANDOFF_KEYS for k in GRID})
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    gp = report["amendment1"]["handoff_only_ni"][0]["goal_pass"]
    assert gp["handoff_only"]["diff_pp"] == 0.0 and gp["ni"]["reading"] == "holds"


def test_am1_decomposition_by_hand(tmp_path: Path):
    # m9 scores 0.25 everywhere; m11 scores 0.25 on its 8 handoff keys and 0.75 on the 16 silenced
    # ones. The whole rise, 0.5 × 16/24 = 33.33 pp, is earned where m11 did NOT hand off.
    dirs = write_a1_matrix(tmp_path, dict(AM1_GP, prefix_m9=0.25))
    write_a1_arm(tmp_path, "prefix_m11", {k: 0.25 if k in HANDOFF_KEYS else 0.75 for k in GRID},
                 handoff={k: k in HANDOFF_KEYS for k in GRID})
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    dec = report["amendment1"]["decomposition"]["tailored"]
    assert (dec["target"], dec["base"]) == ("prefix_m11", "prefix_m9")
    gp = dec["goal_pass"]
    assert (gp["n_handoff"], gp["n_silenced"]) == (8, 16)
    assert gp["delta_total"]["diff_pp"] == 33.33
    assert gp["contribution_handoff"]["diff_pp"] == 0.0
    assert gp["contribution_silenced"]["diff_pp"] == 33.33
    assert gp["share_of_rise_from_handoff"]["point"] == 0.0
    assert gp["share_of_rise_from_handoff"]["n_resamples_rise_not_positive_scenario"] == 0
    assert gp["gain_on_handoff_subset"]["diff_pp"] == 0.0
    assert gp["gain_on_silenced_subset"]["diff_pp"] == 50.0
    assert report["amendment1"]["b4_companions"]["P3"] == "amendment1.handoff_only_ni[B1a]"


def _write_control(arm_root: Path, flag: dict, live: set, eff: int = 11) -> None:
    """Rewrite a prefix arm's events: the handoff record (flag, effective_m) and, for `live` keys,
    an executor action at step eff + 1 -- the executor took control (h* = 1)."""
    for (task_id, seed), f in flag.items():
        events = [{"event_type": "run_start", "actor": "system", "step": 0, "payload": {}},
                  {"event_type": "report", "actor": "system", "step": eff,
                   "payload": {"handoff_occurred": f, "effective_m": eff}}]
        if (task_id, seed) in live:
            events.append({"event_type": "action", "actor": "executor", "step": eff + 1,
                           "payload": {"kind": "CODE", "code": "x"}})
        events.append({"event_type": "evaluate", "actor": "environment", "step": eff + 1, "payload": {}})
        (arm_root / "sys" / str(seed) / task_id / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_am1_hstar_companions_sit_beside_the_flag_ones_by_hand(tmp_path: Path):
    # prefix_m11's flag is true on HANDOFF_KEYS (8) and it scores 0.25 there; the executor also took
    # control on the _2 tasks (8 keys, flag false: the source stopped within m without finishing),
    # scoring 0.5 there; the _3 tasks (8) are terminal at 0.75. planner_alone_cap81 scores 0.75.
    live_unflagged = [k for k in GRID if k[0].endswith("_2")]
    gp11 = {k: 0.25 if k in HANDOFF_KEYS else 0.5 if k in live_unflagged else 0.75 for k in GRID}
    dirs = write_a1_matrix(tmp_path, dict(AM1_GP, prefix_m9=0.25))
    write_a1_arm(tmp_path, "prefix_m11", gp11)
    _write_control(dirs["prefix_m11"], {k: k in HANDOFF_KEYS for k in GRID}, set(HANDOFF_KEYS) | set(live_unflagged))
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    am1 = report["amendment1"]
    assert am1["hstar"]["status"] == "ok" and am1["hstar"]["decision_bearing"] is False
    counts = am1["handoff_control_counts"]["prefix_m11"]
    assert (counts["n_h_flag_true"], counts["n_live_but_unflagged"], counts["n_terminal"]) == (8, 8, 8)
    # The flag-based B1a is unchanged: d = −0.5 on its 8 keys.
    b1 = {r["id"]: r for r in am1["handoff_only_ni"]}["B1a"]["goal_pass"]
    assert (b1["n_handoff"], b1["handoff_only"]["diff_pp"]) == (8, -50.0)
    # h*: (8 x −0.5 + 8 x −0.25) / 16 = −37.5 pp over 16 handoff pairs; silenced = the 8 terminal at 0.
    b1h = {r["id"]: r for r in am1["handoff_only_ni_hstar"]}["B1a"]
    assert b1h["h"] == "h_star" and "h*" in b1h["estimand"]
    gp = b1h["goal_pass"]
    assert (gp["n_handoff"], gp["n_silenced"], gp["handoff_only"]["diff_pp"], gp["silenced"]["diff_pp"]) == (
        16, 8, -37.5, 0.0)
    assert gp["ni"]["reading"] == "fails"
    # §B2 with h*: m11 − m9 = 0 on flagged, +0.25 on live-unflagged, +0.5 on terminal keys.
    dec = am1["decomposition_hstar"]["tailored"]["goal_pass"]
    assert (dec["n_handoff"], dec["contribution_handoff"]["diff_pp"], dec["delta_total"]["diff_pp"]) == (
        16, round(8 * 0.25 / 24 * 100, 2), 25.0)
    assert am1["decomposition"]["tailored"]["goal_pass"]["n_handoff"] == 8
    s6 = next(r for r in report["supporting_contrasts"] if r["id"] == "S6")
    assert s6["goal_pass"]["tailored"]["n_handoff"] == 8 and s6["goal_pass_hstar"]["tailored"]["n_handoff"] == 16
    assert s6["goal_pass_hstar"]["tailored"]["handoff_only"]["diff_pp"] == 12.5  # (0 x 8 + 0.25 x 8) / 16
    assert am1["b4_companions_hstar"]["P3"] == "amendment1.handoff_only_ni_hstar[B1a]"
    assert am1["b4_companions"]["P3"] == "amendment1.handoff_only_ni[B1a]"
    assert "multiplicity_sensitivity_hstar" in am1


def test_am1_hstar_failure_is_recorded_and_never_fatal(tmp_path: Path, monkeypatch):
    from scripts.analysis import handoff_control

    def boom(*_a, **_k):
        raise OSError("unreadable")

    monkeypatch.setattr(handoff_control, "arm_control", boom)
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert report["amendment1"]["hstar"]["status"] == "error"
    assert "OSError" in report["amendment1"]["hstar"]["error"]
    assert "handoff_only_ni" in report["amendment1"] and report["verdicts"]


def test_am1_chord_by_hand(tmp_path: Path):
    # Costs: floor sft_plan 100, reference planner 500, m11 300 (f = 0.5), m9 200 (f = 0.25).
    # Quality: floor 0.5, reference 0.75. m11 0.75 → 0.75 − (0.5 + 0.5 × 0.25) = +12.5 pp;
    # m9 0.625 → 0.625 − (0.5 + 0.25 × 0.25) = +6.25 pp. The zs arms have no cost row.
    cost = {"arms": {
        "sft_plan": {"noncached_tokens_per_episode": 100.0},
        "planner_alone_cap81": {"noncached_tokens_per_episode": 500.0},
        "prefix_m11": {"noncached_tokens_per_episode": 300.0, "hosted_calls_per_episode": 11.0,
                       "n_episodes": 24},
        "prefix_m9": {"noncached_tokens_per_episode": 200.0},
        "advise_k1_fullctx": {"noncached_tokens_per_episode": 1000.0, "hosted_calls_per_episode": 19.0,
                              "n_episodes": 24},
    }}
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    report, _ = a1_report(dirs, cost_report=cost)
    chord = report["amendment1"]["chord"]["arms"]
    assert chord["prefix_m11"]["cost_fraction"] == 0.5
    assert chord["prefix_m11"]["goal_pass"]["scenario"]["ci95_pp"] == [12.5, 12.5]
    assert chord["prefix_m11"]["goal_pass"]["n_triples"] == 24
    assert chord["prefix_m11"]["goal_pass"]["positive_means_above_chord"] is True
    assert chord["prefix_m9"]["cost_fraction"] == 0.25
    assert chord["prefix_m9"]["goal_pass"]["scenario"]["diff_pp"] == 6.25
    assert chord["prefix_m9"]["goal_pass"]["task"]["ci95_pp"] == [6.25, 6.25]
    assert chord["prefix_zs_m9"]["status"] == "not_computed"
    # Without a cost report nothing is plugged in.
    report2, _ = a1_report(dirs)
    assert {a["status"] for a in report2["amendment1"]["chord"]["arms"].values()} == {"not_computed"}


def test_am1_limit_split_and_limit_as_zero_by_hand(tmp_path: Path):
    # P6: takeover 0.75 vs advice, which hits the limit on the 8 HANDOFF_KEYS scoring 0.25 there and
    # 0.5 elsewhere. d = 0.5 on the 8 limit pairs, 0.25 on the 16 others; whole = 8/24 = 33.33 pp,
    # split 16.67 + 16.67. Limit-as-0 sets those 0.25s to 0: (8 × 0.75 + 16 × 0.25) / 24 = 41.67 pp.
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    write_a1_arm(tmp_path, "advise_k10_fullctx", {k: 0.25 if k in HANDOFF_KEYS else 0.5 for k in GRID},
                 error_types={k: "limit" for k in HANDOFF_KEYS})
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    lim = report["amendment1"]["limits"]
    assert lim["rates"]["advise_k10_fullctx"] == {"n_scored": 24, "n_limit": 8, "limit_rate": round(8 / 24, 6)}
    assert lim["rates"]["takeover_k10"]["n_limit"] == 0
    p6 = lim["split"]["P6"]
    assert (p6["left"], p6["right"]) == ("takeover_k10", "advise_k10_fullctx")
    assert (p6["n_limit_pairs"], p6["n_neither"], p6["n_limit_left"], p6["n_limit_right"]) == (8, 16, 0, 8)
    assert p6["all"]["diff_pp"] == 33.33
    assert p6["contribution_limit_pairs"]["diff_pp"] == 16.67
    assert p6["contribution_neither"]["diff_pp"] == 16.67
    assert p6["mean_on_limit_pairs"]["diff_pp"] == 50.0 and p6["mean_on_neither"]["diff_pp"] == 25.0
    assert p6["post_treatment"] is True and p6["not_a_corrected_estimate"] is True
    assert lim["limit_as_zero"]["P6"]["scenario"]["diff_pp"] == 41.67
    # CF1 shares the advice arm, so its split has the same 8 limit pairs.
    assert lim["split"]["CF1"]["n_limit_pairs"] == 8
    assert set(lim["split"]) == {"P1", "P6", "CF1", "CF3"}


def test_am1_by_fdr_flags_a_verdict_it_would_withdraw():
    # m = 4, m·c(m) = 25/3. sorted: 0.004 → 0.0333; 0.03 → 0.125; 0.2 → 0.5556; 0.5 → 1 (capped).
    entries = [
        {"id": "P1", "p": 0.004, "verdict": "supported", "flaggable": True},
        {"id": "P6", "p": 0.03, "verdict": "supported", "flaggable": True},
        {"id": "P5", "p": 0.5, "verdict": "supported", "flaggable": False},
        {"id": "S1", "p": 0.2},
        {"id": "E9", "p": None},
    ]
    out = j10.am1_by_fdr(entries)
    assert out["status"] == "ok" and out["m"] == 4 and out["not_in_family"] == ["E9"]
    p_by = {r["id"]: r["p_by"] for r in out["rows"]}
    assert p_by == pytest.approx({"P1": 0.004 * 25 / 3, "P6": 0.125, "P5": 1.0, "S1": 0.2 * 25 / 9})
    flags = {f["id"]: f for f in out["flags"]}
    assert set(flags) == {"P1", "P6"}  # P5 is supported by a non-rejection: nothing to withdraw
    assert flags["P1"]["survives_by"] is True
    assert flags["P6"]["survives_by"] is False and "does NOT survive" in flags["P6"]["sentence"]


def test_am1_by_fdr_family_counts_each_contrast_once(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    ms = report["amendment1"]["multiplicity_sensitivity"]
    ids = [r["id"] for r in ms["rows"]] + ms["not_in_family"]
    # E4 is CF1 and is counted once, as CF1; S6 is a ratio row outside §F's list.
    assert ids[:6] == ["P1", "P3", "P4", "P5", "P6", "CF1"]
    assert sorted(ids[6:]) == sorted(["S1", "S2", "S3", "S4", "S5", "E1", "E2", "E3", "E5", "B1a", "B1b"])
    assert "E4" not in ids and "S6" not in ids
    # No prefix arm wrote report events, so B1 has no handoff-only p and sits outside the family.
    assert ms["not_in_family"] == ["B1a", "B1b"] and ms["m"] == 15


# ---- Amendment 4 companion: a1_am4_calls (unit ATTRIB, 2026-09-25) ----------------------------------
# Arm 3's plan event: 1,000 input of which 500 cached, 100 output, 50 reasoning. At
# configs/cost/prices_2026-09.yaml: 500 x 0.20e-6 + 500 x 0.02e-6 + 150 x 1.20e-6 = $0.000290.
AM4_PLAN_USAGE = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 1000, "cached_input_tokens": 500,
                  "output_tokens": 100, "reasoning_output_tokens": 50, "n_calls": 1}
AM4_KEY = ("sc0_1", 1)


def _am4_set(arm_root: Path, values: dict, field: str) -> None:
    for (task_id, seed), value in values.items():
        path = arm_root / "sys" / str(seed) / task_id / "result.json"
        row = json.loads(path.read_text(encoding="utf-8"))
        row[field] = value
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def _am4_events(arm_root: Path, key: tuple, events: list) -> None:
    (arm_root / "sys" / str(key[1]) / key[0] / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _am4_matrix(tmp_path: Path, prefix_calls: int = 2) -> dict[str, Path]:
    """advise_k1 makes 2 live calls per episode and, on AM4_KEY only, also replays arm 3's plan, so that
    episode is charged 3. prefix_m11 is charged `prefix_calls` for its replayed prefix everywhere and
    carries no cache event (its AM4_KEY episode records the handoff). arm 2 (sft_plan) replays the plan
    on AM4_KEY, which is its one charged call."""
    dirs = write_a1_matrix(tmp_path)
    source = tmp_path / "arm3" / "planner_alone" / "1" / "sc0_1" / "events.jsonl"
    source.parent.mkdir(parents=True)
    source.write_text("".join(json.dumps(e) + "\n" for e in [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "step": 0, "payload": {"packet": {"goal": "g"}},
         "usage": AM4_PLAN_USAGE},
        # A later planner action with 90,000 fresh input: never the event a replay is priced from.
        {"event_type": "action", "actor": "planner", "step": 1, "payload": {"kind": "CODE"},
         "usage": dict(AM4_PLAN_USAGE, input_tokens=90_000, cached_input_tokens=0)},
    ]), encoding="utf-8")
    cached = {"model": "gpt-5.6-luna", "provider": "cache", "input_tokens": 0, "cached_input_tokens": 0,
              "output_tokens": 0, "reasoning_output_tokens": 0, "n_calls": 1, "raw": {"cached_from": str(source)}}
    live = dict(AM4_PLAN_USAGE, input_tokens=10, cached_input_tokens=0)
    replay = [{"event_type": "run_start", "actor": "system", "payload": {}},
              {"event_type": "plan", "actor": "planner", "step": 0, "payload": {"packet": {"goal": "g"}},
               "usage": cached}]
    _am4_set(dirs["advise_k1_fullctx"], {k: 3 if k == AM4_KEY else 2 for k in GRID}, "n_planner_calls")
    _am4_events(dirs["advise_k1_fullctx"], AM4_KEY, replay + [
        {"event_type": "intervention", "actor": "planner", "step": s, "payload": {}, "usage": live} for s in (1, 2)])
    _am4_set(dirs["prefix_m11"], {k: prefix_calls for k in GRID}, "n_planner_calls")
    _am4_events(dirs["prefix_m11"], AM4_KEY, [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "report", "actor": "system", "step": 11, "payload": {"handoff_occurred": True, "effective_m": 11}}])
    _am4_set(dirs["sft_plan"], {k: "sft_plan" for k in GRID}, "system")
    _am4_events(dirs["sft_plan"], AM4_KEY, replay)
    return dirs


def _am4_cost(usd: dict, tokens: dict | None = None) -> dict:
    """A1_COST_REPORT plus usd_per_episode (and, if given, noncached tokens) with per-episode rows, one
    constant per arm; the rows carry the arm's tokens so that the per-episode mean equals the arm mean."""
    cost = json.loads(json.dumps(A1_COST_REPORT))
    for label, value in usd.items():
        arm = cost["arms"].setdefault(label, {"n_episodes": 24})
        arm["usd_per_episode"] = value
        if tokens and label in tokens:
            arm["noncached_tokens_per_episode"] = tokens[label]
        tok = arm.get("noncached_tokens_per_episode")
        arm["episodes"] = [{"task_id": t, "seed": s, "usd_per_episode": value, "noncached_tokens_per_episode": tok}
                           for t, s in GRID]
    return cost


def test_am4_calls_live_and_attributed_by_hand(tmp_path: Path, monkeypatch):
    dirs = _am4_matrix(tmp_path)
    cost = _am4_cost({"advise_k1_fullctx": 0.001, "prefix_m11": 0.002})
    report, _ = a1_report(dirs, cost_report=cost)
    am4 = report["a1_am4_calls"]
    assert am4["status"] == "ok" and list(am4["per_arm"]) == list(j10.A1_AM4_ARMS)  # arms 2, 3, 4-7, 8-12
    # advise_k1: 23 episodes charged 2 and AM4_KEY charged 3 -> 49 / 24 = 2.041667 attributed; live drops
    # the one replayed call -> 48 / 24 = 2.0. USD: (24 x 0.001 + 0.000290) / 24 = 0.00101208 -> 0.001012.
    # Tokens: the plan event is 1,000 + 100 + 50 = 1,150 non-cached tokens, so
    # (24 x 1,414,410 + 1,150) / 24 = 1,414,457.916667.
    assert am4["per_arm"]["advise_k1_fullctx"] == {
        "n_episodes": 24, "calls_attributed_mean": 2.041667, "calls_live_mean": 2.0, "n_cached_plan_events": 1,
        "tokens_attributed_mean": 1414457.916667, "tokens_as_published_mean": 1414410.0,
        "usd_attributed_mean": 0.001012, "usd_as_published_mean": 0.001}
    # The prefix arm is charged its replayed prefix under both conventions (A1:347-349).
    assert am4["per_arm"]["prefix_m11"] == {
        "n_episodes": 24, "calls_attributed_mean": 2.0, "calls_live_mean": 2.0, "n_cached_plan_events": 0,
        "tokens_attributed_mean": 443361.0, "tokens_as_published_mean": 443361.0,
        "usd_attributed_mean": 0.002, "usd_as_published_mean": 0.002}
    p2 = am4["p2_calls_clause"]
    assert p2["attributed"] == {"advise_k1": 2.041667, "prefix_m11": 2.0, "holds": True}
    assert p2["live"] == {"advise_k1": 2.0, "prefix_m11": 2.0, "holds": False}
    assert p2["holds_both"] is False and p2["note"] == j10.A1_AM4_NOTE
    tk = am4["p2_tokens_clause"]
    assert tk["attributed"] == {"advise_k1": 1414457.916667, "prefix_m11": 443361.0,
                                "ratio": round(1414457.916667 / 443361.0, 6), "holds": True}  # 3.190304
    assert tk["live"] == {"advise_k1": 1414410.0, "prefix_m11": 443361.0,
                          "ratio": round(1414410.0 / 443361.0, 6), "holds": True}  # 3.190196
    assert (tk["holds_both"], tk["min_ratio"], tk["note"]) == (True, 2.0, j10.A1_AM4_TOKENS_NOTE)
    # No other key or value moves: the same report without the companion.
    monkeypatch.setattr(j10, "a1_am4_calls", lambda rep, *_a, **_k: rep)
    base, _ = a1_report(dirs, cost_report=cost)
    rest = {k: v for k, v in report.items() if k != "a1_am4_calls"}
    assert json.dumps(rest, sort_keys=True, default=str) == json.dumps(base, sort_keys=True, default=str)


def test_am4_sft_plan_is_not_charged_twice_and_both_conventions_can_hold(tmp_path: Path):
    dirs = _am4_matrix(tmp_path, prefix_calls=1)
    cost = _am4_cost({"advise_k1_fullctx": 0.001, "prefix_m11": 0.002, "sft_plan": 0.003},
                     tokens={"advise_k1_fullctx": 1990.0, "prefix_m11": 1000.0, "sft_plan": 500.0})
    am4 = a1_report(dirs, cost_report=cost)[0]["a1_am4_calls"]
    sft = am4["per_arm"]["sft_plan"]
    # Every arm-2 episode is charged 1; on AM4_KEY that call is the replayed plan: live 23 / 24 = 0.958333.
    assert (sft["calls_attributed_mean"], sft["calls_live_mean"], sft["n_cached_plan_events"]) == (1.0, 0.958333, 1)
    # j12 already charges sft_plan its source plan (j12_cost_axes.py:361-367), so nothing is added.
    assert sft["usd_attributed_mean"] == sft["usd_as_published_mean"] == 0.003
    assert sft["tokens_attributed_mean"] == sft["tokens_as_published_mean"] == 500.0
    p2 = am4["p2_calls_clause"]
    assert (p2["attributed"]["holds"], p2["live"]["holds"], p2["holds_both"]) == (True, True, True)
    # Tokens: as published 1,990 / 1,000 = 1.99 < 2 fails; attributed (24 x 1,990 + 1,150) / 24 = 2,037.916667,
    # 2.037917 >= 2 holds -- so the clause fails Amendment 4's both-conventions reading.
    tk = am4["p2_tokens_clause"]
    assert tk["attributed"] == {"advise_k1": 2037.916667, "prefix_m11": 1000.0, "ratio": 2.037917, "holds": True}
    assert tk["live"] == {"advise_k1": 1990.0, "prefix_m11": 1000.0, "ratio": 1.99, "holds": False}
    assert tk["holds_both"] is False
    # Without a cost report the calls are still read; USD is null and the note says why.
    bare = a1_report(dirs)[0]["a1_am4_calls"]
    assert bare["per_arm"]["advise_k1_fullctx"]["calls_live_mean"] == 2.0
    assert bare["per_arm"]["advise_k1_fullctx"]["usd_attributed_mean"] is None
    assert bare["notes"]["advise_k1_fullctx"] == ["no cost-report row for this arm"]


def test_am4_failure_is_recorded_and_never_fatal(tmp_path: Path, monkeypatch):
    def boom():
        raise ImportError("j12_cost_axes unavailable")

    monkeypatch.setattr(j10, "_load_j12", boom)
    report, _ = a1_report(write_a1_matrix(tmp_path), cost_report=A1_COST_REPORT)
    assert report["a1_am4_calls"] == {"status": "error", "error": "ImportError: j12_cost_axes unavailable"}
    assert report["verdicts"]["P2"] == "supported"


# ---- Amendment 5: a replay that cannot pass its own check (unit DIVRULE, 2026-09-25) -----------------------
AM5_KEY = ("sc0_1", 1)


def _am5_crash(arm_root: Path, keys, reason: str = "replay_divergence") -> None:
    """Rewrite these episodes of an arm as crashes whose last attempt's error event carries `reason`."""
    for task_id, seed in keys:
        dest = arm_root / "sys" / str(seed) / task_id
        row = json.loads((dest / "result.json").read_text(encoding="utf-8"))
        row["error_type"] = "crash"
        (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
        events = [{"event_type": "run_start", "actor": "system", "step": 0, "payload": {}},
                  {"event_type": "error", "actor": "system", "step": 11, "error_type": "crash",
                   "payload": {"reason": reason, "detail": "synthetic"}}]
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _am5_rows_cost(per_arm: dict, odd: dict | None = None) -> dict:
    """A j12_cost_axes-shaped report: constant per-episode rows per arm (odd[(label, key)] overrides one row),
    and each arm's published means over all 24 rows, as j12 publishes them."""
    import statistics

    arms = {}
    for label, fields in per_arm.items():
        rows = [{"task_id": t, "seed": s, **fields, **(odd or {}).get((label, (t, s)), {})} for t, s in GRID]
        arm = {"n_episodes": len(rows), "episodes": rows}
        for f in fields:
            arm[f] = round(statistics.fmean(r[f] for r in rows), 6)
        arms[label] = arm
    return {"arms": arms}


AM5_P2_COST = {"advise_k1_fullctx": {"noncached_tokens_per_episode": 1414410.0, "hosted_calls_per_episode": 19.0},
               "prefix_m11": {"noncached_tokens_per_episode": 443361.0, "hosted_calls_per_episode": 11.25}}
# The divergent episode's rows: prefix_m11 charged its replayed prefix only (0 here), advice 2,000,000 tokens.
AM5_P2_ODD = {("prefix_m11", AM5_KEY): {"noncached_tokens_per_episode": 0.0, "hosted_calls_per_episode": 0.0},
              ("advise_k1_fullctx", AM5_KEY): {"noncached_tokens_per_episode": 2_000_000.0}}


def _am5_off(monkeypatch) -> None:
    """Every Amendment 5 hook replaced by the call it wraps: the report as it was before the amendment."""
    monkeypatch.setattr(j10, "a1_am5_arms", lambda arms, *_a, **_k: arms)
    monkeypatch.setattr(j10, "a1_am5_pair", lambda arms, left, right: (arms[left], arms[right]))
    monkeypatch.setattr(j10, "a1_am5_cost_prediction",
                        lambda pred, cost, n, _arms, **kw: j10.a1_evaluate_cost_prediction(pred, cost, n, **kw))
    monkeypatch.setattr(j10, "a1_am5_p2_arms", lambda arms: arms)
    monkeypatch.setattr(j10, "a1_am5_p2_cost", lambda _arms, cost: cost)
    monkeypatch.setattr(j10, "a1_am5_divergence", lambda rep, *_a, **_k: rep)


def test_am5_zero_divergent_keys_leave_every_key_and_value_unchanged(tmp_path: Path, monkeypatch):
    """(a) and constraint 3: no divergent key -- on a clean matrix, and with an ORDINARY crash in a replay arm,
    which keeps today's behaviour (arm incomplete) -- the report equals the pre-amendment one but for the block."""
    cost = _am5_rows_cost(AM5_P2_COST)
    clean = write_a1_matrix(tmp_path / "clean")
    crashed = write_a1_matrix(tmp_path / "crashed")
    _am5_crash(crashed["prefix_m11"], [AM5_KEY], reason="replay_error")
    new = [a1_report(d, cost_report=cost) for d in (clean, crashed)]
    _am5_off(monkeypatch)
    old = [a1_report(d, cost_report=cost) for d in (clean, crashed)]
    blocks = []
    for (rep, rc), (base, rc0) in zip(new, old):
        block = rep.pop("a1_am5_divergence")
        blocks.append(block)
        assert "a1_am5_divergence" not in base and rc == rc0
        assert json.dumps(rep, sort_keys=True, default=str) == json.dumps(base, sort_keys=True, default=str)
        assert {a: (v["n_divergent"], v["keys"]) for a, v in block["per_arm"].items()} == {
            a: (0, []) for a in j10.A1_PREFIX_ARMS}
        assert block["n_divergent_total"] == 0 and block["contrasts"] == {} and block["companions"] == {}
        assert block["cap"] == 16 and block["non_replay_divergent"]["keys"] == {}
    assert new[0][1] == 0 and new[1][1] == 1
    assert new[1][0]["arms"]["prefix_m11"]["complete"] is False
    assert by_id(new[1][0])["P1"]["verdict"] == "refused_incomplete"
    assert blocks[1]["per_arm"]["prefix_m11"]["n_crash_other"] == 1


def test_am5_one_divergent_key_leaves_both_arms_of_its_contrasts_only(tmp_path: Path):
    """(b) and (g). prefix_m11 diverges on AM5_KEY, where advice scores 1.0 (0.5 elsewhere). Every contrast,
    companion and sensitivity that uses prefix_m11 loses the key on BOTH sides and is complete on 23 pairs;
    every other contrast keeps its 24; the block lists the key."""
    dirs = write_a1_matrix(tmp_path, {"advise_k1_fullctx": {k: 1.0 if k == AM5_KEY else 0.5 for k in GRID}})
    _am5_crash(dirs["prefix_m11"], [AM5_KEY])
    _planless_arm3(dirs["planner_alone_cap81"], [("sc1_2", 1)])  # §4.2: one planless key (cap 1)
    report, rc = a1_report(dirs, cost_report=_am5_rows_cost(AM5_P2_COST, AM5_P2_ODD))
    assert rc == 0 and report["incomplete_reasons"] == [], report["headline"]
    arm = report["arms"]["prefix_m11"]
    assert (arm["n_crash"], arm["n_scored"], arm["complete"]) == (1, 23, True)  # §B.3: complete
    assert not [k for k in arm if k.startswith("_")]
    p = by_id(report)
    # P1 = advise − prefix_m11 = 0.5 − 0.75 on the 23 remaining pairs: the key's 1.0 is gone from advice too.
    c1 = p["P1"]["contrast"]
    assert (c1["n_pairs"], c1["n_shared"], c1["n_left_only"], c1["n_right_only"]) == (23, 23, 0, 0)
    assert c1["scenario"]["ci95_pp"] == [-25.0, -25.0] and p["P1"]["decidable"] is True
    assert (p["P3"]["contrast"]["n_pairs"], p["P3"]["decidable"]) == (23, True)
    # P5 = advise − sft_plan uses no replay arm: all 24 pairs, the key's +50 pp kept -> 50 / 24 = +2.08 pp.
    assert (p["P5"]["contrast"]["n_pairs"], p["P5"]["contrast"]["scenario"]["diff_pp"]) == (24, 2.08)
    assert p["P4"]["contrast"]["n_pairs"] == p["P6"]["contrast"]["n_pairs"] == 24
    # P2 on the rows without the key: 23 each, means back to the constants (published: 424,887.625 for m11).
    obs = p["P2"]["observed"]
    assert (obs["left_n_episodes"], obs["right_n_episodes"]) == (23, 23)
    assert (obs["left_tokens_per_episode"], obs["right_tokens_per_episode"]) == (1414410.0, 443361.0)
    assert obs["right_calls_per_episode"] == 11.25 and p["P2"]["ratio"] == round(1414410.0 / 443361.0, 4)
    assert p["P2"]["decidable"] is True and p["P2"]["ratio_interval"]["n_pairs"] == 23
    assert report["verdicts"]["P1"] == report["verdicts"]["P2"] == report["verdicts"]["P3"] == "supported"
    # Amendment 4's P2 clauses read the same 23 episodes on both sides.
    am4 = report["a1_am4_calls"]["per_arm"]
    assert am4["advise_k1_fullctx"]["n_episodes"] == am4["prefix_m11"]["n_episodes"] == 23
    assert am4["prefix_m11"]["tokens_as_published_mean"] == 443361.0
    assert am4["sft_plan"]["n_episodes"] == 24
    # §4.2: the sensitivity drops the planless key AND sees the divergent one (22); P5 only the planless (23).
    rows = {r["id"]: r for r in report["planless_contingency"]["sensitivity"]["rows"]}
    assert rows["P1"]["contrast_without_keys"]["n_pairs"] == 22 and rows["P5"]["contrast_without_keys"]["n_pairs"] == 23
    # Companions: S2 (advise_k10 − m11), B1a (m11 − arm 3), P1's limit split: 23; S1 (advise − m9): untouched.
    s2 = next(r for r in report["supporting_contrasts"] if r["id"] == "S2")
    assert s2["goal_pass"]["n_pairs"] == 23
    assert report["amendment1"]["limits"]["split"]["P1"]["n_pairs"] == 23
    blk = report["a1_am5_divergence"]
    assert blk["per_arm"]["prefix_m11"] == {"n_divergent": 1, "keys": ["1/sc0_1"], "n_crash_other": 0,
                                            "arm_complete": True}
    assert {a: v["n_divergent"] for a, v in blk["per_arm"].items()} == {
        "prefix_m9": 0, "prefix_m11": 1, "prefix_zs_m9": 0, "prefix_zs_m11": 0}
    assert blk["n_divergent_total"] == 1 and set(blk["contrasts"]) == {"P1", "P2", "P3"}
    assert blk["contrasts"]["P1"] == {"left": "advise_k1_fullctx", "right": "prefix_m11", "n_excluded": 1,
                                      "excluded_keys": ["1/sc0_1"], "verdict": "ok", "n_pairs": 23,
                                      "decision": "supported"}
    assert blk["contrasts"]["P2"]["n_pairs"] == 23
    comp = blk["companions"]
    assert comp["S2"] == {"arms": ["advise_k10_fullctx", "prefix_m11"], "n_excluded": 1, "n_pairs": 23}
    assert comp["amendment1.B1a"]["n_pairs"] == 23 and comp["amendment1.limits.split.P1"]["n_pairs"] == 23
    assert "S1" not in comp and "amendment1.limits.split.P6" not in comp


def test_am5_two_replay_arms_remove_the_union_of_their_keys(tmp_path: Path):
    """(c) P4 = prefix_zs_m11 − prefix_zs_m9: {sc0_1/1} ∪ {sc0_1/1, sc1_1/2} = 2 keys, 22 pairs."""
    dirs = write_a1_matrix(tmp_path)
    _am5_crash(dirs["prefix_zs_m11"], [("sc0_1", 1)])
    _am5_crash(dirs["prefix_zs_m9"], [("sc0_1", 1), ("sc1_1", 2)])
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 0, report["headline"]
    p4 = by_id(report)["P4"]
    assert (p4["contrast"]["n_pairs"], p4["decidable"], p4["verdict"]) == (22, True, "not_supported")
    blk = report["a1_am5_divergence"]
    assert blk["contrasts"]["P4"]["excluded_keys"] == ["1/sc0_1", "2/sc1_1"]
    assert blk["contrasts"]["P4"]["n_excluded"] == 2 and blk["n_divergent_total"] == 3
    # E1 (arm 3 − prefix_zs_m11) loses 1 key; S4 (all four prefix arms) and the untailored decomposition 2.
    assert blk["companions"]["E1"]["n_pairs"] == 23
    assert blk["companions"]["S4"]["n_pairs"] == 22
    assert blk["companions"]["amendment1.decomposition.untailored"]["n_pairs"] == 22
    assert "P1" not in blk["contrasts"] and by_id(report)["P1"]["contrast"]["n_pairs"] == 24


def test_am5_seventeen_divergent_keys_make_the_contrast_incomplete_sixteen_do_not(tmp_path: Path):
    """(d) 17 > 16 removed keys: P1, P2, P3 draw no reading, though the arm itself is complete (§B.3);
    at exactly 16 they are read on the remaining 8 pairs."""
    for n, n_pairs in ((17, 7), (16, 8)):
        dirs = write_a1_matrix(tmp_path / str(n))
        _am5_crash(dirs["prefix_m11"], GRID[:n])
        report, rc = a1_report(dirs, cost_report=_am5_rows_cost(AM5_P2_COST))
        p = by_id(report)
        assert report["arms"]["prefix_m11"]["complete"] is True
        assert p["P1"]["contrast"]["n_pairs"] == p["P3"]["contrast"]["n_pairs"] == n_pairs
        assert p["P6"]["verdict"] == "supported" and p["P5"]["decidable"] is True
        if n == 17:
            assert rc == 1
            for pid in ("P1", "P2", "P3"):
                assert p[pid]["verdict"] == "refused_incomplete", pid
            assert "replay_divergence_above_cap:P1=17>16" in report["incomplete_reasons"]
            assert "cap 16" in p["P2"]["reason"]
            assert report["a1_am5_divergence"]["contrasts"]["P1"]["verdict"] == "over_cap"
        else:
            assert rc == 0, report["headline"]
            assert p["P1"]["decidable"] and p["P3"]["decidable"] and p["P2"]["decidable"]
            assert report["a1_am5_divergence"]["contrasts"]["P1"]["verdict"] == "ok"


def test_am5_a_divergent_key_plus_an_ordinary_crash_is_incomplete(tmp_path: Path):
    """(e) §B.3: any other residual crash still makes the arm incomplete."""
    dirs = write_a1_matrix(tmp_path)
    _am5_crash(dirs["prefix_m11"], [AM5_KEY])
    _am5_crash(dirs["prefix_m11"], [("sc2_1", 2)], reason="replay_error")
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 1
    arm = report["arms"]["prefix_m11"]
    assert (arm["n_crash"], arm["complete"]) == (2, False)
    assert "incomplete_arm:prefix_m11 scored=22/24 crash=2 missing=0" in report["incomplete_reasons"]
    p = by_id(report)
    assert p["P1"]["verdict"] == p["P3"]["verdict"] == "refused_incomplete"
    assert p["P1"]["contrast"]["n_pairs"] == 22
    assert report["a1_am5_divergence"]["per_arm"]["prefix_m11"] == {
        "n_divergent": 1, "keys": ["1/sc0_1"], "n_crash_other": 1, "arm_complete": False}


def test_am5_a_divergent_key_in_a_non_replay_arm_is_an_ordinary_crash(tmp_path: Path):
    """Constraint 3: impossible by construction; if seen, the arm stays incomplete and the block names it."""
    dirs = write_a1_matrix(tmp_path)
    _am5_crash(dirs["advise_k1_fullctx"], [AM5_KEY])
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 1 and report["arms"]["advise_k1_fullctx"]["complete"] is False
    assert by_id(report)["P1"]["verdict"] == "refused_incomplete"
    blk = report["a1_am5_divergence"]
    assert blk["non_replay_divergent"]["keys"] == {"advise_k1_fullctx": ["1/sc0_1"]}
    assert blk["contrasts"] == {} and blk["n_divergent_total"] == 0


def test_am5_b3_chord_cost_plug_in_is_read_without_the_divergent_key(tmp_path: Path):
    """B3: prefix_m11 costs 300 per episode but 0 on its divergent key, so its published mean is 287.5 and
    f = (287.5 − 100) / 400 = 0.46875. Without the key f = (300 − 100) / 400 = 0.5, and the residual
    0.75 − (0.5 + 0.5 × 0.25) = +12.5 pp on the 23 triples left."""
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    _am5_crash(dirs["prefix_m11"], [AM5_KEY])
    tokens = "noncached_tokens_per_episode"
    cost = _am5_rows_cost({"sft_plan": {tokens: 100.0}, "planner_alone_cap81": {tokens: 500.0},
                           "prefix_m11": {tokens: 300.0, "hosted_calls_per_episode": 11.0},
                           "advise_k1_fullctx": {tokens: 1000.0, "hosted_calls_per_episode": 19.0}},
                          {("prefix_m11", AM5_KEY): {tokens: 0.0, "hosted_calls_per_episode": 0.0}})
    assert cost["arms"]["prefix_m11"][tokens] == 287.5
    report, _ = a1_report(dirs, cost_report=cost)
    chord = report["amendment1"]["chord"]["arms"]["prefix_m11"]
    assert (chord["cost_fraction"], chord["cost_arm"]) == (0.5, 300.0)
    assert chord["goal_pass"]["n_triples"] == 23 and chord["goal_pass"]["scenario"]["ci95_pp"] == [12.5, 12.5]
    note = report["a1_am5_divergence"]["companions"]["amendment1.chord.prefix_m11"]
    assert note["n_pairs"] == 23 and note["cost_plug_in"].startswith("B3 cost plug-in re-read")
    # prefix_m9 has no divergent key: its chord is as published.
    assert report["amendment1"]["chord"]["arms"]["prefix_m9"]["status"] == "not_computed"

