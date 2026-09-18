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
    rc = j10.main(args)
    assert rc == 2


def test_refuses_test_challenge_without_confirmation(tmp_path: Path):
    write_complete_matrix(
        tmp_path,
        tgc={arm: 0.0 for arm in REQUIRED},
        calls={arm: 1 for arm in REQUIRED},
    )
    args = argv_for(tmp_path)
    args[args.index("dev")] = "test_challenge"
    rc = j10.main(args)
    assert rc == 2


def test_path_containing_test_normal_is_refused_on_dev(tmp_path: Path, capsys):
    evil = tmp_path / "camp_test_normal" / "sidekick"
    evil.mkdir(parents=True)
    rc = j10.main(
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
    rc = j10.main(args)
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
    rc = j10.main(args)
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
    rc = j10.main(argv_for(tmp_path))
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
    rc = j10.main(argv_for(tmp_path))
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
    rc = j10.main(argv_for(tmp_path))
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
    rc = j10.main(args)
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
    rc = j10.main(argv_for(tmp_path))
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
    rc = j10.main(argv_for(tmp_path))
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
    rc = j10.main(argv_for(tmp_path))
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
    j10.main(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert report["resample_unit"] == "task"
    assert "not independent" in report["resample_unit_justification"]
    assert report["contrasts"]["tgc_sidekick_minus_sft_plan"]["resample"] == "task"
    assert report["contrasts"]["tgc_sidekick_minus_sft_plan"]["resample_unit_for_decision"] == "task"


def test_unknown_arm_label_is_refused(capsys):
    rc = j10.main(
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
    j10.main(argv_for(tmp_path))
    report = json.loads(capsys.readouterr().out)
    assert report["hypotheses"]["H3"]["status"] == "not_a_j10_archive_quantity"
