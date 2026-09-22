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
) -> Path:
    """One arm tree in runner layout. goal_pass: a float or a {(task, seed): value} map."""
    arm_root = root / label
    for task_id in A1_TASKS:
        for seed in A1_SEEDS:
            key = (task_id, seed)
            dest = arm_root / "sys" / str(seed) / task_id
            dest.mkdir(parents=True, exist_ok=True)
            gp = goal_pass[key] if isinstance(goal_pass, dict) else goal_pass
            row = {
                "run_id": f"synth/{label}/{seed}/{task_id}",
                "task_id": task_id,
                "system": "sys",
                "seed": seed,
                "success": False,
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

    def stub(diffs, clusters, *, n_perm=10000, seed=20260924, alternative="two-sided"):
        calls.append((list(diffs), list(clusters), n_perm, seed, alternative))
        return 0.5  # would contradict every "supported" verdict if it were decision-bearing

    monkeypatch.setattr(j10, "_load_cluster_signflip", lambda: stub)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    p = by_id(report)
    for pid in ("P1", "P3", "P4", "P5", "P6"):
        perm = p[pid]["permutation_sensitivity"]
        assert perm["status"] == "ok" and perm["p_value"] == 0.5
        assert perm["decision_bearing"] is False
    assert p["P1"]["verdict"] == "supported"
    assert len(calls) == 5
    diffs, clusters, n_perm, seed, alternative = calls[1]  # P3, shifted by the −7 pp margin
    assert diffs == pytest.approx([0.07] * 24)
    assert sorted(set(clusters)) == ["sc0", "sc1", "sc2", "sc3"]
    assert (n_perm, seed, alternative) == (10000, 20260924, "two-sided")
    monkeypatch.setattr(j10, "_load_cluster_signflip", lambda: None)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert by_id(report)["P1"]["permutation_sensitivity"]["status"] == "unavailable"


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

