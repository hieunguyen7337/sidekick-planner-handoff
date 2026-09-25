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


# Unit R2 (A4): P2's calls clause needs advise_k1 to make strictly more hosted calls than prefix_m11 under both of
# Amendment 4's conventions, so the constructed matrix charges them 19 and 11 (the dev means, A1 §6 P2).
A1_N_PLANNER_CALLS = {"advise_k1_fullctx": 19, "prefix_m11": 11}


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
    dirname: str | None = None,
    manifest: dict | None = None,
) -> Path:
    """One arm tree in runner layout. goal_pass / success: a value or a {(task, seed): value}
    map. handoff: {(task, seed): bool} written as the prefix arm's `report` event. Arm 3 is written
    under planner_alone/, the system directory A1 §4.2's planless keys are read from (unit R2, A1).
    manifest: extra manifest keys (a 'provenance' dict is merged into the split's)."""
    arm_root = root / (dirname or label)
    system = "planner_alone" if label == j10.A1_PLAN_SOURCE_ARM else "sys"
    extra = dict(manifest or {})
    extra_prov = extra.pop("provenance", {})
    for task_id in A1_TASKS:
        for seed in A1_SEEDS:
            key = (task_id, seed)
            dest = arm_root / system / str(seed) / task_id
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
                "system": system,
                "seed": seed,
                "success": success[key] if isinstance(success, dict) else success,
                "tgc": tgc[key] if isinstance(tgc, dict) else tgc,
                "goal_pass_rate": gp,
                "steps": 5,
                "n_planner_calls": A1_N_PLANNER_CALLS.get(label, 1),
                "error_type": (error_types or {}).get(key),
            }
            (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
            if manifest_split is not None:
                (dest / "manifest.json").write_text(
                    json.dumps({**extra, "provenance": {"split": manifest_split, **extra_prov}}), encoding="utf-8"
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
A1_COST_MEANS = {
    "arms": {
        "advise_k1_fullctx": {"noncached_tokens_per_episode": 1414410.0,
                              "hosted_calls_per_episode": 19.0, "n_episodes": 24},
        "prefix_m11": {"noncached_tokens_per_episode": 443361.0,
                       "hosted_calls_per_episode": 11.25, "n_episodes": 24},
    }
}
# Unit R2 (A4): the same means with j12_cost_axes' per-episode rows, one constant per arm, so that Amendment 4's
# tokens clause can be read (it needs arms.<arm>.episodes) and the P2 cost report's rows can be checked (A3).
A1_COST_REPORT = {
    "arms": {
        label: dict(arm, episodes=[
            {"task_id": t, "seed": s, "noncached_tokens_per_episode": arm["noncached_tokens_per_episode"],
             "hosted_calls_per_episode": arm["hosted_calls_per_episode"]} for t in A1_TASKS for s in A1_SEEDS])
        for label, arm in A1_COST_MEANS["arms"].items()
    }
}


def write_a1_matrix(tmp_path: Path, gp: dict | None = None, **kw) -> dict[str, Path]:
    values = dict(A1_CONSTANT_GP, **(gp or {}))
    return {label: write_a1_arm(tmp_path, label, values[label], **kw) for label in A1_ALL_ARMS}


def a1_report(arm_dirs, **kw):
    kw.setdefault("split", "dev")
    kw.setdefault("seeds", list(A1_SEEDS))
    kw.setdefault("expected_n_tasks", len(A1_TASKS))
    # Unit R2 (B6): A1 §7 item 2's 78 pairwise contrasts cost ~10 s a report; tests that do not read them skip
    # them on dev (test_r2_b6_* reads them; the registered read and main compute them always).
    kw.setdefault("pairwise", False)
    return j10.build_report_a1(arm_dirs=arm_dirs, **kw)


def by_id(report: dict) -> dict:
    return {p["id"]: p for p in report["predictions"]}


def _registered_matrix(tmp_path: Path, monkeypatch, gp: dict | None = None, *, manifest_split: str = "test_normal",
                       stamp: dict | None = None) -> dict[str, Path]:
    """Unit R2 (A2): the registered read on the 12-task fixture -- every A1 arm, each in the directory its
    config's campaign_id names, each manifest stamping what that config registers (stamp[label] overrides
    fields). The fixture's 12 tasks stand in for test_normal's 168."""
    monkeypatch.setitem(j10.A1_SPLIT_N_TASKS, "test_normal", len(A1_TASKS))
    values = dict(A1_CONSTANT_GP, **(gp or {}))
    dirs = {}
    for label in A1_ALL_ARMS:
        cid = j10._a1_r2_config(label)["campaign_id"]
        prov = dict(j10.a1_r2_expected_provenance(label), **(stamp or {}).get(label, {}))
        dirs[label] = write_a1_arm(tmp_path, label, values[label], manifest_split=manifest_split, dirname=cid,
                                   manifest={"campaign_id": cid, "provenance": prov})
    return dirs


def registered_report(dirs, **kw):
    return a1_report(dirs, split="test_normal", confirm_heldout_test_split=True, **kw)


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
    if (arm_root / "sys").is_dir():  # write_a1_arm already writes arm 3 under planner_alone/ (unit R2, A1)
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
    # Unit R2 (A5): rewritten with ONE planless key, the cap at 24 pairs (int(24 x 0.05) = 1); three keys now
    # make J10 not run (next test). +6.25 pp on every pair but the planless one in scenario sc0, where takeover
    # fails and advice passes (d = −1). Cluster means: sc0 (−1 + 5 x 0.0625) / 6 = −0.1146, the others
    # +0.0625, so any resample drawing sc0 twice is negative: P(k >= 2 of 4 draws) = 0.26 > 2.5 %, the
    # scenario CI reaches below zero. Without the key every d is +0.0625: [+6.25, +6.25].
    keys = [("sc0_1", 1)]
    grid = [(t, s) for t in A1_TASKS for s in A1_SEEDS]
    dirs = {
        "takeover_k10": write_a1_arm(tmp_path, "takeover_k10", {k: 0.0 if k in keys else 0.5625 for k in grid}),
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
    assert sens["contrast_without_keys"]["scenario"]["ci95_pp"] == [6.25, 6.25]
    assert sens["verdict_holm_all_pairs"] != "supported" and sens["differs"] is True
    assert row["contrast"]["scenario"]["diff_pp"] == round((-1 + 23 * 0.0625) / 24 * 100, 2)  # +1.82
    assert row["verdict"] == "on_boundary"
    assert row["verdict_before_key_exclusion"] == row["verdict_holm"]
    assert report["verdicts"]["P6"] == "on_boundary"
    # 1 of 24 is within the cap: the read goes ahead, and P6 is decided (on the boundary).
    assert rc == 0 and report["planless_contingency"]["n_keys"] == 1, report["headline"]


def test_r2_a5_planless_keys_above_the_cap_mean_j10_is_not_run(tmp_path: Path):
    # A1 §4.2 item 5 (:234-236) and §9 (:574-576): 3 planless keys of 24 is above the cap of int(24 x 0.05) = 1.
    # J10 is reported as not run: arm completeness counts only, no verdict and no contrast value.
    keys = [("sc0_1", 1), ("sc0_2", 1), ("sc0_3", 2)]
    dirs = {label: write_a1_arm(tmp_path, label, 0.5)
            for label in ("takeover_k10", "advise_k10_fullctx", "planner_alone_cap81")}
    _planless_arm3(dirs["planner_alone_cap81"], keys)
    report, rc = a1_report(dirs)
    assert rc == 1 and report["status"] == "NOT_RUN"
    assert report["headline"] == (
        f"J10 not run: 3 of arm 3's episodes are planless, above the cap of 1 [{j10.A1_PREREG}:234-236].")
    assert report["planless_contingency"]["keys"] == ["1/sc0_1", "1/sc0_2", "2/sc0_3"]
    # The seam j11_report --j10-report reads: status, split and a verdicts dict, every value "not_run".
    assert (report["split"], report["verdicts"]) == ("dev", {f"P{i}": "not_run" for i in range(1, 7)})
    for key in ("predictions", "supporting_contrasts", "exploratory_contrasts", "amendment1",
                "multiplicity", "sgc", "a1_am4_calls"):
        assert key not in report, key
    arm = report["arms"]["takeover_k10"]
    assert (arm["n_expected"], arm["n_scored"], arm["complete"]) == (24, 24, True)
    assert "goal_pass_mean" not in arm and "error_types" not in arm
    blob = json.dumps(report)
    assert "diff_pp" not in blob and "ci95" not in blob and "p_value" not in blob


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


def test_split_provenance_mismatch_refuses_every_prediction(tmp_path: Path, monkeypatch):
    # Unit R2 (A2): the registered read now refuses arm directories that are not the registered campaigns, so the
    # fixture is the registered one (_registered_matrix) with manifests that say dev.
    dirs = _registered_matrix(tmp_path, monkeypatch, manifest_split="dev")
    report, rc = registered_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 1
    assert any(r.startswith("split_provenance_mismatch") for r in report["incomplete_reasons"])
    assert set(report["verdicts"].values()) == {"refused_incomplete"}
    # A9: a refused row carries no reading.
    for row in report["predictions"]:
        assert not {"verdict_unadjusted", "p_value", "pool04"} & set(row), row["id"]


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
    # P3 (A1:315): one-sided at its −7 pp threshold; the routine does the shift.
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
    # A1:422-423 (F4): the registered-orientation upper bound.
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
    dirs["takeover_k10"] = write_a1_arm(tmp_path / "x", "takeover_k10", 0.75, success=ok)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    sgc = report["sgc"]
    assert set(sgc) == {"P1", "P6"}
    p1 = sgc["P1"]
    assert (p1["left"], p1["right"], p1["descriptive"], p1["decision_bearing"]) == (
        "advise_k1_fullctx", "prefix_m11", True, False)
    assert (p1["n_units_registered"], p1["n_units_shared"]) == (8, 8)
    assert (p1["n_passed_left"], p1["n_passed_right"], p1["diff_pp"]) == (7, 8, -12.5)
    assert (sgc["P6"]["n_units_unscored_left"], sgc["P6"]["n_units_shared"]) == (0, 8)
    # A crash leaves its unit unscored, not failed (A1 F6). Unit R2 (A5): a crash in arm 10 now makes J10 not
    # run, so the unit rule is checked on a1_sgc itself.
    crashed = write_a1_arm(tmp_path / "y", "takeover_k10", 0.75, success=ok, error_types={("sc3_1", 2): "crash"})
    eps = {label: j10.a1_arm_episodes(label, j10.load_arm_tree(root), A1_TASKS, list(A1_SEEDS))["episodes"]
           for label, root in (("takeover_k10", crashed), ("advise_k10_fullctx", dirs["advise_k10_fullctx"]))}
    p6 = j10.a1_sgc(eps["takeover_k10"], eps["advise_k10_fullctx"], A1_TASKS, list(A1_SEEDS))
    assert (p6["n_units_unscored_left"], p6["n_units_shared"]) == (1, 7)
    assert (p6["sgc_left"], p6["sgc_right"]) == (1.0, 0.0)
    # The same rule at report level, on P1's right-hand arm (prefix_m11, arm 5, not one of §9's abort arms): unit
    # (sc3, 2) is unscored, so 7 units are shared; advice passes 6 of them (it failed (sc0, 1)), the prefix 7.
    dirs_p1 = dict(dirs, prefix_m11=write_a1_arm(tmp_path / "z", "prefix_m11", 0.75, success=ok,
                                                 error_types={("sc3_1", 2): "crash"}))
    p1 = a1_report(dirs_p1, cost_report=A1_COST_REPORT)[0]["sgc"]["P1"]
    assert (p1["n_units_unscored_right"], p1["n_units_shared"]) == (1, 7)
    assert (p1["n_passed_left"], p1["n_passed_right"], p1["diff_pp"]) == (6, 7, round(-100 / 7, 2))
    dirs["takeover_k10"] = crashed
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, report["status"]) == (1, "NOT_RUN") and "sgc" not in report


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
    # The verdict stays on the arm means (A1:341), whatever the interval says.
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
    bare = j10.a1_evaluate_cost_prediction(p2, A1_COST_MEANS, expected_n=24)  # unit R2: the rows-free means
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
    # Unit R2 (A6): arms 11 and 12 are abandoned and reported as not run as a pair (A1:575-576), so with arm 12
    # absent CF1-CF3 are all "not_run" -- CF2 (show − advice) included -- and P1-P6 stand: exit 0.
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    dirs.pop("advise_k10_neutral")
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    cf = report["amendment1"]["cf"]
    assert cf["status"] == "not_run" and cf["verdicts"] == {"CF1": "not_run"}
    assert report["headline"].endswith("Amendment 1 CF1: not run.")
    assert {s["id"]: s["status"] for s in cf["secondary"]} == {"CF2": "not_run", "CF3": "not_run"}
    assert (rc, report["status"]) == (0, "COMPLETE"), report["headline"]
    assert report["headline"].startswith("COMPLETE: every registered prediction decided.")


def test_r2_a6_an_incomplete_arm_12_makes_cf_and_arm_11_rows_not_run_and_p1_p6_stand(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path, AM1_GP)
    dirs["advise_k10_neutral"] = write_a1_arm(tmp_path / "x", "advise_k10_neutral", 0.75,
                                              error_types={("sc1_1", 2): "crash"})
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, report["status"]) == (0, "COMPLETE"), report["headline"]
    assert report["verdicts"] == {"P1": "supported", "P2": "supported", "P3": "supported",
                                  "P4": "supported", "P5": "supported", "P6": "supported"}
    cf = report["amendment1"]["cf"]
    assert cf["status"] == "not_run" and cf["verdicts"] == {"CF1": "not_run"}
    [cf1] = cf["predictions"]
    assert cf1["verdict"] == "not_run" and "contrast" not in cf1 and "p_value" not in cf1
    assert "advise_k10_neutral incomplete (scored=23/24, crash=1)" in cf1["reason"]
    assert {s["id"]: s["status"] for s in cf["secondary"]} == {"CF2": "not_run", "CF3": "not_run"}
    # Every row that uses arm 11 or 12 is printed without values, never at reduced power.
    e = {r["id"]: r for r in report["exploratory_contrasts"]}
    assert {k: e[k]["status"] for k in e} == {"E1": "ok", "E2": "not_run", "E3": "not_run", "E4": "not_run",
                                              "E5": "not_run"}
    assert all(e[k]["goal_pass"] is None for k in ("E2", "E3", "E4", "E5"))
    for label in ("show_k10", "advise_k10_neutral"):
        arm = report["arms"][label]
        assert arm["not_run"] is True and "goal_pass_mean" not in arm and "error_types" not in arm
    assert report["arms"]["advise_k10_neutral"]["n_crash"] == 1  # completeness counts stay
    lim = report["amendment1"]["limits"]
    assert lim["split"]["CF1"]["status"] == lim["split"]["CF3"]["status"] == "not_run"
    assert "diff_pp" not in json.dumps(lim["split"]["CF1"])
    # The supporting-arms sentence names the arm; CF1 stays last.
    assert "Incomplete arms no prediction uses: advise_k10_neutral (P1-P6 stand)." in report["headline"]
    assert report["headline"].endswith("Amendment 1 CF1: not run.")
    ms = report["amendment1"]["multiplicity_sensitivity"]
    assert not {"CF1", "E2", "E3", "E5"} & {r["id"] for r in ms["rows"]}


def test_am1_cf1_goes_on_the_boundary_when_the_planless_keys_move_it(tmp_path: Path):
    # test_a1_a_verdict_that_changes_without_the_planless_keys_is_on_the_boundary, for CF1 (unit R2: one
    # planless key, within the cap; arm 11 is given, since CF runs only with arms 11 and 12 as a pair, A6).
    keys = [("sc0_1", 1)]
    dirs = {
        "advise_k10_neutral": write_a1_arm(tmp_path, "advise_k10_neutral",
                                           {k: 0.0 if k in keys else 0.5625 for k in GRID}),
        "advise_k10_fullctx": write_a1_arm(tmp_path, "advise_k10_fullctx",
                                           {k: 1.0 if k in keys else 0.5 for k in GRID}),
        "planner_alone_cap81": write_a1_arm(tmp_path, "planner_alone_cap81", 0.75),
        "show_k10": write_a1_arm(tmp_path, "show_k10", 0.625),
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
    # Unit R2 (B3): Amendment 3 registers h*, so P3's B4 entry points at the h* row; the flag map is kept beside it.
    assert report["amendment1"]["b4_companions"]["P3"] == "amendment1.handoff_only_ni_hstar[B1a]"
    assert report["amendment1"]["b4_companions_flag"]["P3"] == "amendment1.handoff_only_ni[B1a]"


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
    # Unit R2 (B3): b4_companions now points at the registered (h*) rows; the flag map is b4_companions_flag.
    assert am1["b4_companions"]["P3"] == "amendment1.handoff_only_ni_hstar[B1a]"
    assert am1["b4_companions_flag"]["P3"] == "amendment1.handoff_only_ni[B1a]"
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
    # Unit R2 (A4), Amendment 4 §C: P2 is supported only if its rule holds AND both clauses hold under both
    # conventions. Its rule holds on the cost report's means (19 > 11.25 calls; 1,414,410 / 443,361 = 3.19 >= 2),
    # but live the advice arm makes 2.0 calls to prefix_m11's 2.0: the live convention turns a supported P2 into
    # not supported. (This replaces the check that the companion moved no other key: it now moves P2.)
    p2row = by_id(report)["P2"]
    assert (p2row["verdict_before_amendment4"], p2row["verdict"]) == ("supported", "not_supported")
    assert (p2row["amendment4"]["calls_holds_both"], p2row["amendment4"]["tokens_holds_both"]) == (False, True)
    assert p2row["amendment4"]["why"] == "calls clause fails under one convention"
    assert report["verdicts"]["P2"] == "not_supported"
    # Without the companion neither clause can be read under both conventions: P2 is incomplete, not supported.
    monkeypatch.setattr(j10, "a1_am4_calls", lambda rep, *_a, **_k: rep)
    base, rc = a1_report(dirs, cost_report=cost)
    assert by_id(base)["P2"]["verdict"] == "refused_incomplete" and rc == 1
    assert "p2_amendment4_clause_not_read:calls,tokens" in base["incomplete_reasons"]
    assert base["status"] == "INCOMPLETE"
    # Everything but P2's row, the verdicts and the lines that quote them (headline, reasons, P1's sentence).
    rest = {k: v for k, v in report.items() if k not in ("a1_am4_calls", "predictions", "verdicts", "headline",
                                                          "incomplete_reasons", "status", "verdict_sentences")}
    rest_base = {k: v for k, v in base.items() if k in rest}
    assert json.dumps(rest, sort_keys=True, default=str) == json.dumps(rest_base, sort_keys=True, default=str)


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
    # Unit R2 (A4): an unreadable companion no longer leaves P2 supported -- Amendment 4 §C cannot be read, so
    # P2 is incomplete (holds_both None), and says why.
    p2 = by_id(report)["P2"]
    assert p2["verdict"] == "refused_incomplete" and p2["decidable"] is False
    assert "a1_am4_calls cannot read it (error)" in p2["reason"]
    assert p2["amendment4"]["a1_am4_calls_status"] == "error"


def test_r2_a4_p2_is_supported_only_when_both_clauses_hold_under_both_conventions(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    # Holds: 19 > 11 calls both ways (no cached plan), tokens 3.19 both ways.
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    p2 = by_id(report)["P2"]
    assert (rc, p2["verdict"], p2["amendment4"]["calls_holds_both"], p2["amendment4"]["tokens_holds_both"]) == (
        0, "supported", True, True)
    assert "verdict_before_amendment4" not in p2
    # A cost report without per-episode rows: the tokens clause is None -> P2 incomplete, with its reason.
    report, rc = a1_report(dirs, cost_report=A1_COST_MEANS)
    p2 = by_id(report)["P2"]
    assert (rc, p2["verdict"], p2["amendment4"]["tokens_holds_both"]) == (1, "refused_incomplete", None)
    assert "p2_amendment4_clause_not_read:tokens" in report["incomplete_reasons"]
    assert report["headline"].startswith("INCOMPLETE: p2_amendment4_clause_not_read:tokens")
    # A9: an incomplete P2 carries no reading.
    assert "pool04" not in p2 and "verdict_unadjusted" not in p2
    # The rule itself fails: Amendment 4 never turns a not-supported P2 into supported.
    cheap = json.loads(json.dumps(A1_COST_REPORT))
    cheap["arms"]["advise_k1_fullctx"]["noncached_tokens_per_episode"] = 1.5 * 443361.0
    p2 = by_id(a1_report(dirs, cost_report=cheap)[0])["P2"]
    assert p2["verdict"] == "not_supported" and "verdict_before_amendment4" not in p2


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
    # Unit R2 (A5): the divergent key moves from arm 8 (advise_k1_fullctx) to arm 2 (sft_plan), which replays the plan
    # but not the environment and is not one of §9's abort arms, so the report still reads and P5 is refused;
    # arms 3, 8, 9 and 10 stay complete. In arm 8 the same crash now means J10 is not run (checked at the end).
    dirs = write_a1_matrix(tmp_path)
    _am5_crash(dirs["sft_plan"], [AM5_KEY])
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 1 and report["arms"]["sft_plan"]["complete"] is False
    assert by_id(report)["P5"]["verdict"] == "refused_incomplete"
    blk = report["a1_am5_divergence"]
    assert blk["non_replay_divergent"]["keys"] == {"sft_plan": ["1/sc0_1"]}
    assert blk["contrasts"] == {} and blk["n_divergent_total"] == 0
    dirs = write_a1_matrix(tmp_path / "arm8")
    _am5_crash(dirs["advise_k1_fullctx"], [AM5_KEY])
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, report["status"]) == (1, "NOT_RUN") and "predictions" not in report
    assert report["headline"] == ("J10 not run: arm advise_k1_fullctx did not complete 24 non-crashed pairs "
                                  "(scored=23, crash=1, missing=0).")
    assert report["a1_am5_divergence"]["non_replay_divergent"]["keys"] == {"advise_k1_fullctx": ["1/sc0_1"]}


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


# ---- Unit R2: the J10 pre-read audit, Phase A (2026-09-25) ---------------------------------------------------------
def test_r2_a1_arm_3_without_planner_alone_is_refused_not_read_as_zero_keys(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    root = dirs["planner_alone_cap81"]
    (root / "planner_alone").rename(root / "sys")  # the episodes are there, under another system name
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 2 and report["refused"] is True and "predictions" not in report
    assert "holds no planner_alone/ subdirectory" in report["reason"]
    assert "<arm-3 campaign>/planner_alone/<seed>/<task_id>/" in report["reason"]
    # Its system subdirectory given in place of the campaign, and a directory that does not exist: refused.
    for bad in (root / "sys", tmp_path / "nowhere"):
        assert a1_report(dict(dirs, planner_alone_cap81=bad))[1] == 2
    # With planner_alone/ the same matrix reads: zero planless keys, and a sensitivity with nothing to drop.
    (root / "sys").rename(root / "planner_alone")
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 0 and report["planless_contingency"]["n_keys"] == 0


def test_r2_a2_expected_provenance_is_the_configs_by_hand():
    # What configs/j10_prefix_m11.yaml registers, as config_provenance / planner_provenance stamp it.
    assert j10.a1_r2_expected_provenance("prefix_m11") == {
        "config_campaign_id": "j10_prefix_m11_20260924",
        "handoff_source_campaign": "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924",
        "handoff_m": 11, "executor_model": "ibm-granite/granite-4.2-8b", "lora_name": "sft_b_plus",
        "takeover": None, "planner_type": "codex", "planner_model_requested": "gpt-5.6-luna",
        "planner_reasoning_effort": "medium", "correct_prompt": "correction", "advice_from_act": None}
    # takeover_k10 sets `takeover: true` at the top level, which the runner reads and the manifest never stamps.
    assert j10.a1_r2_expected_provenance("takeover_k10")["takeover"] is None
    assert j10._a1_r2_config("takeover_k10")["takeover"] is True
    # Every registered config names its own campaign.
    for label, rel in j10.A1_ARMS.items():
        assert j10._a1_r2_config(label)["campaign_id"].startswith(f"j10_{Path(rel).stem[len('j10_'):]}_"), label


def test_r2_a2_the_registered_read_checks_every_manifest_and_says_what_it_cannot(tmp_path: Path, monkeypatch):
    dirs = _registered_matrix(tmp_path, monkeypatch)
    report, rc = registered_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, report["status"]) == (0, "COMPLETE"), report["headline"]
    assert report["not_the_j10_result"] is False
    assert report["verdicts"] == {"P1": "supported", "P2": "supported", "P3": "supported",
                                  "P4": "not_supported", "P5": "supported", "P6": "supported"}
    m = report["registered_read_checks"]["manifests"]
    assert m["status"] == "ok" and list(m["per_arm"]) == list(j10.A1_ARMS)
    assert {a: (c["n_manifests"], c["mismatches"], c["unstamped"]) for a, c in m["per_arm"].items()} == {
        a: (24, {}, {}) for a in j10.A1_ARMS}
    shown = m["not_shown_by_the_manifest"]
    assert "adapter_directory" in shown and "served_model" in shown
    assert shown["channel_config_keys"]["per_arm"]["takeover_k10"] == {"takeover": True, "fixed_k": 10}
    assert shown["channel_config_keys"]["per_arm"]["show_k10"] == {"advice_from_act": True, "fixed_k": 10}
    cost = report["registered_read_checks"]["cost_report"]
    assert cost["status"] == "ok" and cost["p2_rows"] == {
        "advise_k1_fullctx": {"n_rows": 24, "n_not_episodes_of_the_arm_given": 0},
        "prefix_m11": {"n_rows": 24, "n_not_episodes_of_the_arm_given": 0}}
    assert cost["not_recorded_by_j12_cost_axes"] == ["split", "arm directories", "packet_source"]


def test_r2_a2_registered_read_pins_refuse(tmp_path: Path, monkeypatch):
    dirs = _registered_matrix(tmp_path, monkeypatch)

    def refused(**kw) -> str:
        report, rc = registered_report(kw.pop("dirs", dirs), cost_report=A1_COST_REPORT, **kw)
        assert rc == 2 and report["refused"] is True and "predictions" not in report
        return report["reason"]

    assert "seeds [1, 2, 3] are not exactly {1, 2}" in refused(seeds=[1, 2, 3])
    assert "seeds [1] are not exactly {1, 2}" in refused(seeds=[1])
    assert "expected task count 11 is not 12" in refused(expected_n_tasks=11)
    p3_easier = [dict(p, threshold_pp=-10.0) if p["id"] == "P3" else dict(p) for p in j10.A1_PREDICTIONS]
    assert "the predictions differ from A1_PREDICTIONS" in refused(predictions=p3_easier)
    assert "the supporting rows differ" in refused(supporting=[])
    # A directory that is not the registered campaign (the basename is the config's campaign_id).
    moved = tmp_path / "elsewhere" / "prefix_m11_rerun"
    moved.parent.mkdir()
    dirs["prefix_m11"].rename(moved)
    reason = refused(dirs=dict(dirs, prefix_m11=moved))
    assert "the directory is not the registered campaign j10_prefix_m11_20260924" in reason
    moved.rename(dirs["prefix_m11"])
    # A10: arms 1, 1b, prefix_m9, 11 and 12 are required on the registered read.
    a10 = ("executor_alone", "executor_alone_bplus", "prefix_m9", "show_k10", "advise_k10_neutral")
    reason = refused(dirs={k: v for k, v in dirs.items() if k not in a10})
    assert f"registered arms not given as --arm: {list(a10)}" in reason
    # 168 on the real split: the pin is the registered count, not whatever the fixture has.
    monkeypatch.setitem(j10.A1_SPLIT_N_TASKS, "test_normal", 168)
    assert "expected task count 12 is not 168" in refused()


def test_r2_a2_a_manifest_that_disagrees_with_its_config_is_refused(tmp_path: Path, monkeypatch):
    # The adapter alias and the replay source, each on one arm.
    stamp = {"prefix_m11": {"lora_name": "sft_b"},
             "prefix_m9": {"handoff_source_campaign": "/scratch/n12194778/sidekick/results/hj17_planner_alone_x"}}
    dirs = _registered_matrix(tmp_path, monkeypatch, stamp=stamp)
    report, rc = registered_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 2 and "predictions" not in report
    assert ("prefix_m11: 24 manifest(s) stamp lora_name='sft_b' but configs/j10_prefix_m11.yaml registers "
            "'sft_b_plus'") in report["reason"]
    assert "prefix_m9: 24 manifest(s) stamp handoff_source_campaign=" in report["reason"]
    # The campaign id at the top of the manifest is compared too.
    dirs = _registered_matrix(tmp_path / "b", monkeypatch)
    for path in (dirs["sft_plan"] / "sys").rglob("manifest.json"):
        man = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(dict(man, campaign_id="hj17_sft_plan_x")), encoding="utf-8")
    reason = registered_report(dirs, cost_report=A1_COST_REPORT)[0]["reason"]
    assert "sft_plan: 24 manifest(s) stamp campaign_id='hj17_sft_plan_x'" in reason


def test_r2_a2_main_refuses_predictions_json_on_test_normal(tmp_path: Path, capsys):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(list(j10.A1_PREDICTIONS)), encoding="utf-8")
    rc = j10.main(["--split", "test_normal", "--confirm-heldout-test-split", "--predictions-json", str(path),
                   "--arm", f"prefix_m11={tmp_path / 'x'}"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2 and out["refused"] is True and "refusing --predictions-json on test_normal" in out["reason"]


def test_r2_a3_the_p2_cost_report_must_be_over_the_arms_given(tmp_path: Path, monkeypatch):
    dirs = _registered_matrix(tmp_path, monkeypatch)

    def reason(cost) -> str:
        report, rc = registered_report(dirs, cost_report=cost)
        assert rc == 2 and "predictions" not in report
        return report["reason"]

    # Rows from another split (dev task ids): no row is an episode of the arm given.
    dev_rows = json.loads(json.dumps(A1_COST_REPORT))
    for arm in dev_rows["arms"].values():
        for r in arm["episodes"]:
            r["task_id"] = "dev_" + r["task_id"]
    assert "advise_k1_fullctx: 24 of 24 per-episode rows are not episodes of --arm" in reason(dev_rows)
    # No per-episode rows: nothing to check the report against.
    assert "prefix_m11 has no per-episode rows" in reason(A1_COST_MEANS)
    # Where the report does record its split, arm directory or packet source, they must match.
    assert "its split is 'dev'" in reason(dict(A1_COST_REPORT, split="dev"))
    assert "its packet_source" in reason(dict(A1_COST_REPORT, packet_source=str(tmp_path / "other")))
    moved = json.loads(json.dumps(A1_COST_REPORT))
    moved["arms"]["prefix_m11"]["root"] = str(tmp_path / "hj17_prefix_m11")
    assert "its arm 'prefix_m11' was read from" in reason(moved)
    ok = dict(A1_COST_REPORT, split="test_normal", packet_source=str(dirs["planner_alone_cap81"]))
    assert registered_report(dirs, cost_report=ok)[1] == 0
    # On dev the cost report is not checked (A3 is the registered read's).
    assert a1_report(write_a1_matrix(tmp_path / "dev"), cost_report=dev_rows)[1] in (0, 1)


def test_r2_a5_an_incomplete_abort_arm_means_j10_is_not_run(tmp_path: Path, monkeypatch):
    # Arm 9 is missing one episode: A1 §9, reported as not run, never at reduced power.
    dirs = write_a1_matrix(tmp_path)
    (dirs["advise_k10_fullctx"] / "sys" / "2" / "sc3_3" / "result.json").unlink()

    def boom(*_a, **_k):
        raise AssertionError("a contrast was computed on a not-run read")

    monkeypatch.setattr(j10, "a1_contrast", boom)
    monkeypatch.setattr(j10, "cluster_bootstrap_means", boom)
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, report["status"]) == (1, "NOT_RUN")
    assert report["headline"] == ("J10 not run: arm advise_k10_fullctx did not complete 24 non-crashed pairs "
                                  "(scored=23, crash=0, missing=1).")
    assert report["abort_rule"]["citation"] == f"{j10.A1_PREREG}:574-576"
    assert report["abort_rule"]["arms"] == ["planner_alone_cap81", "advise_k1_fullctx", "advise_k10_fullctx",
                                            "takeover_k10"]
    assert report["arms"]["advise_k10_fullctx"]["n_missing"] == 1
    assert set(report["arms"]) == set(j10.A1_ARMS)
    assert all("goal_pass_mean" not in a and "tgc_mean" not in a for a in report["arms"].values())
    # An incomplete arm that is not 3, 8, 9 or 10 does not stop the read (P1/P3 are refused instead).
    monkeypatch.undo()
    dirs = write_a1_matrix(tmp_path / "b")
    (dirs["prefix_m11"] / "sys" / "2" / "sc3_3" / "result.json").unlink()
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert report["status"] == "INCOMPLETE" and by_id(report)["P1"]["verdict"] == "refused_incomplete"


def test_r2_a7_b1_draws_no_reading_above_the_cap_or_with_an_incomplete_arm(tmp_path: Path):
    for n, incomplete in ((17, True), (16, False)):
        dirs = write_a1_matrix(tmp_path / str(n))
        _am5_crash(dirs["prefix_m11"], GRID[:n])
        am1 = a1_report(dirs, cost_report=_am5_rows_cost(AM5_P2_COST))[0]["amendment1"]
        assert am1["hstar"]["status"] == "ok"
        for key in ("handoff_only_ni", "handoff_only_ni_hstar"):
            b1a = {r["id"]: r for r in am1[key]}["B1a"]
            if incomplete:
                assert b1a["status"] == "incomplete" and b1a["draws_no_reading"] is True, key
                assert "17 divergent keys to remove > cap 16" in b1a["reason"]
                assert b1a["goal_pass"]["ni"]["reading"] == "incomplete"
                assert "p_value_two_sided_at_margin" not in b1a["goal_pass"]
            else:
                assert b1a.get("status") != "incomplete" and b1a["goal_pass"]["ni"]["reading"] != "incomplete"
    # An ordinary crash in prefix_zs_m11: B1b (prefix_zs_m11 − arm 3) is incomplete, B1a is read.
    dirs = write_a1_matrix(tmp_path / "zs")
    _am5_crash(dirs["prefix_zs_m11"], [AM5_KEY], reason="replay_error")
    am1 = a1_report(dirs, cost_report=A1_COST_REPORT)[0]["amendment1"]
    b1 = {r["id"]: r for r in am1["handoff_only_ni"]}
    assert b1["B1b"]["status"] == "incomplete" and b1["B1b"]["goal_pass"]["ni"]["reading"] == "incomplete"
    assert "arm(s) incomplete: ['prefix_zs_m11']" in b1["B1b"]["reason"]
    assert b1["B1a"].get("status") != "incomplete"


def test_r2_a8_a_held_out_manifest_under_split_dev_is_refused_before_anything_is_read(tmp_path: Path, monkeypatch):
    dirs = write_a1_matrix(tmp_path)
    write_a1_arm(tmp_path, "prefix_m9", 0.625, manifest_split="test_normal")

    def boom(*_a, **_k):
        raise AssertionError("an arm was loaded before the held-out guard")

    monkeypatch.setattr(j10, "load_arm_tree", boom)
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 2 and report["refused"] is True and "predictions" not in report
    assert "refusing --arm prefix_m9=" in report["reason"]
    assert "{'test_normal': 24} episode manifest(s) record a held-out split and this is --split dev" in (
        report["reason"])
    # test_challenge is never read, not even by the confirmed registered read.
    monkeypatch.undo()
    dirs = _registered_matrix(tmp_path / "reg", monkeypatch)
    write_a1_arm(tmp_path / "reg", "prefix_m9", 0.625, manifest_split="test_challenge",
                 dirname=dirs["prefix_m9"].name)
    report, rc = registered_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 2 and "{'test_challenge': 24}" in report["reason"]


def test_r2_a9_a_refused_row_carries_no_reading(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    _am5_crash(dirs["prefix_m11"], [("sc2_1", 2)], reason="replay_error")  # an ordinary crash: arm 5 incomplete
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 1
    p = by_id(report)
    for pid in ("P1", "P3"):
        assert p[pid]["verdict"] == "refused_incomplete", pid
        assert not {"verdict_unadjusted", "events_unadjusted", "p_value", "p_value_two_sided", "pool04",
                    "permutation_sensitivity"} & set(p[pid]), pid
        assert p[pid]["draws_no_reading"] is True
    assert p["P1"]["contrast"]["n_pairs"] == 23  # the descriptive contrast and its pair count stay
    for pid in ("P4", "P5", "P6"):
        assert "verdict_unadjusted" in p[pid] and "pool04" in p[pid] and "p_value" in p[pid]
    ms = report["amendment1"]["multiplicity_sensitivity"]
    assert {"P1", "P3"} <= set(ms["not_in_family"])


def test_r2_a10_an_incomplete_supporting_arm_marks_its_rows_and_p1_p6_stand(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    dirs["executor_alone_bplus"] = write_a1_arm(tmp_path / "x", "executor_alone_bplus", 0.375,
                                                error_types={("sc0_2", 1): "crash"})
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, report["status"]) == (0, "COMPLETE"), report["headline"]
    assert report["headline"] == (
        "COMPLETE: every registered prediction decided. Incomplete arms no prediction uses: executor_alone_bplus "
        "(P1-P6 stand). Supporting / exploratory rows incomplete, drawing no reading: S5. "
        "Amendment 1 CF1: not_supported.")  # CF1: neutral 0.5 − advice 0.5 = 0 in A1_CONSTANT_GP
    s = {r["id"]: r for r in report["supporting_contrasts"]}
    assert s["S5"]["status"] == "incomplete" and s["S5"]["incomplete_arms"] == ["executor_alone_bplus"]
    assert "p_value_two_sided_at_0" not in s["S5"]["goal_pass"]
    assert s["S5"]["goal_pass"]["n_pairs"] == 23  # printed, labelled incomplete
    assert {k: v["status"] for k, v in s.items() if k != "S5"} == {k: "ok" for k in ("S1", "S2", "S3", "S4", "S6")}
    assert report["supporting_incomplete_reasons"] == [
        "incomplete_arm:executor_alone_bplus scored=23/24 crash=1 missing=0"]
    assert report["incomplete_reasons"] == []
    assert "S5" in report["amendment1"]["multiplicity_sensitivity"]["not_in_family"]


def test_r2_a11_the_hstar_b1a_row_carries_the_hstar_dev_reference(tmp_path: Path):
    report, _ = a1_report(write_a1_matrix(tmp_path, AM1_GP), cost_report=A1_COST_REPORT)
    am1 = report["amendment1"]
    hstar = {r["id"]: r for r in am1["handoff_only_ni_hstar"]}["B1a"]
    ref = hstar["dev_reference"]
    assert (ref["diff_pp"], ref["ci95_pp_scenario"], ref["n_handoff"]) == (8.57, [-1.63, 18.25], 88)
    assert ref["ci95_pp_task"] == [0.67, 16.30] and ref["key"] == "ni.bplus.m11.goal_pass.handoff_only"
    # The prereg line it cites says the same.
    lines = (REPO_ROOT / j10.A1_PREREG).read_text(encoding="utf-8").splitlines()
    assert "**+8.57 pp** over 88 episodes (scenario [−1.63, +18.25], task [+0.67, +16.30])" in lines[946]
    # The flag row keeps the flag's dev value.
    flag = {r["id"]: r for r in am1["handoff_only_ni"]}["B1a"]
    assert (flag["dev_reference"]["diff_pp"], flag["dev_reference"]["n_handoff"]) == (-0.94, 71)



# ---- Unit R2: the J10 pre-read audit, Phase B (2026-09-25) ---------------------------------------------------------
def test_r2_b7_a_scored_failure_keeps_its_recorded_tgc(tmp_path: Path):
    # advise_k1 hits the step limit on two keys and records TGC 1.0 there (0 elsewhere), and on a third records no
    # TGC at all. v1's score_tgc drops the first two from every TGC contrast (None); A1 §5.1 scores them as recorded.
    lim = [("sc0_1", 1), ("sc1_1", 2), ("sc2_1", 1)]
    tgc = {k: (1.0 if k in lim[:2] else None if k == lim[2] else 0.0) for k in GRID}
    dirs = write_a1_matrix(tmp_path)
    dirs["advise_k1_fullctx"] = write_a1_arm(tmp_path / "x", "advise_k1_fullctx", 0.5, tgc=tgc,
                                             error_types={k: "limit" for k in lim})
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    arm = report["arms"]["advise_k1_fullctx"]
    assert arm["tgc_scored_as_recorded"]["n_changed"] == 2
    assert arm["tgc_scored_as_recorded"]["changed"] == ["1/sc0_1", "2/sc1_1"]
    assert arm["tgc_scored_as_recorded"]["n_failure_without_recorded_tgc_scored_0"] == 1
    assert arm["tgc_mean"] == round(2 / 24, 6)  # 0.083333: 2 of 24 at 1.0, the unrecorded one scored 0
    # P1's TGC secondary: advise 2/24 − prefix 0 = +8.33 pp over all 24 pairs (22 before).
    tg = by_id(report)["P1"]["tgc_secondary"]
    assert (tg["n_pairs"], tg["scenario"]["diff_pp"]) == (24, round(100 * 2 / 24, 2))
    # j11 and j12 import a1_arm_episodes, which is unchanged: there the two keys still read None.
    blob = j10.load_arm_tree(dirs["advise_k1_fullctx"])
    eps = j10.a1_arm_episodes("advise_k1_fullctx", blob, A1_TASKS, list(A1_SEEDS))["episodes"]
    assert eps[("sc0_1", 1)]["tgc"] is None and eps[("sc2_1", 1)]["tgc"] == 0.0
    # Every other fixture writes TGC 0 on its scored failures, so no other test's rows move.
    assert report["tgc_scored_as_recorded"]["prefix_m11"]["n_changed"] == 0


def test_r2_b1_signflip_disagreement_and_the_tgc_atom_are_in_the_sentence(tmp_path: Path, monkeypatch):
    dirs = write_a1_matrix(tmp_path)

    def stub(diffs, clusters, *, threshold, alternative, seed):
        return {"p": 0.5, "method": "exact", "n_patterns": 16, "n_clusters": 4}

    monkeypatch.setattr(j10, "_load_cluster_signflip", lambda: stub)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    s = report["verdict_sentences"]
    # P1 supported, sign-flip p 0.5 does not reject: disagreement, said in the verdict's sentence (A1 §5.5).
    assert s["P1"].startswith("P1 (advise_k1_fullctx − prefix_m11, goal_pass): supported, -25.00 pp")
    assert "the cluster sign-flip p (exact, two-sided) is 0.5000, which does not reject at 0.05 and so disagrees" \
        in s["P1"]
    # P4 not supported (point 0), p 0.5 does not reject either: they agree, nothing is said.
    assert "sign-flip" not in s["P4"]
    # TGC is 0 everywhere: P1's TGC interval is [0, 0], on threshold 0's atom (0/24); P3's threshold −7 pp has
    # its nearest atom at round(−0.07 x 24) / 24 = −2/24 = −8.33 pp, which [0, 0] is not on.
    assert "TGC's lower and upper bound sits on the threshold's nearest atom (0/24 = +0.00 pp)" in s["P1"]
    assert by_id(report)["P1"]["tgc_secondary"]["atom_note"].startswith("TGC's lower and upper bound")
    assert "atom" not in s["P3"]


def test_r2_b2_p1_p3_p6_are_worded_as_registered(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    s = report["verdict_sentences"]
    assert "never as advice at matched budget or as ruling out a budget effect (Amendment 1 §E" in s["P1"]
    assert "uninterpretable" not in s["P1"]  # P2 is supported
    assert "non-inferiority to the medium-effort planner in this harness, never to the planner at its best effort" \
        in s["P3"]
    assert "+11.97 pp goal_pass above the medium one on 114 keys [+6.14, +18.43]" in s["P3"]
    assert "(ceiling − arm +7.22 [+3.21, +11.47]; CEILHI-01, CEILHI-03)" in s["P3"]
    assert "handoff-only (h*, registered, Amendment 3) B1a:" in s["P3"] and "flag companion B1a:" in s["P3"]
    # P6 supported; E5 = takeover 0.75 − neutral 0.5 = +25.00 pp and CF1 (0.5 − 0.5) is not supported.
    assert '"actions beat the registered advice prompt"' in s["P6"]
    assert "E5 (takeover − neutral-prompt advice, exploratory): +25.00 pp [+25.00, +25.00]; CF1: not_supported" \
        in s["P6"]
    assert "correction-prompt advice" not in s["P6"]
    assert by_id(report)["P6"]["verdict_sentence"] == s["P6"]
    # P2 not supported: P1 is flagged, in its sentence, as uninterpretable as a channel result (A1:358-359).
    cheap = json.loads(json.dumps(A1_COST_REPORT))
    cheap["arms"]["advise_k1_fullctx"]["noncached_tokens_per_episode"] = 1.5 * 443361.0
    s = a1_report(dirs, cost_report=cheap)[0]["verdict_sentences"]
    assert ("P2 is not supported, so P1 is uninterpretable as a channel result and is reported as a "
            "budget-confounded comparison, whatever its sign") in s["P1"]
    # CF1 supported (neutral 0.75): P6 only as "actions beat correction-prompt advice"; E5 = 0.75 − 0.75.
    s = a1_report(write_a1_matrix(tmp_path / "am1", AM1_GP), cost_report=A1_COST_REPORT)[0]["verdict_sentences"]
    assert "E5 (takeover − neutral-prompt advice, exploratory): +0.00 pp [+0.00, +0.00]; CF1: supported" in s["P6"]
    assert 'P6 is reported only as "actions beat correction-prompt advice"' in s["P6"]
    assert s["CF1"].startswith("CF1 (advise_k10_neutral − advise_k10_fullctx, goal_pass): supported, +25.00 pp")


def test_r2_b3_hstar_rows_are_the_registered_version(tmp_path: Path):
    live_unflagged = [k for k in GRID if k[0].endswith("_2")]
    gp11 = {k: 0.25 if k in HANDOFF_KEYS else 0.5 if k in live_unflagged else 0.75 for k in GRID}
    dirs = write_a1_matrix(tmp_path, dict(AM1_GP, prefix_m9=0.25))
    write_a1_arm(tmp_path, "prefix_m11", gp11)
    _write_control(dirs["prefix_m11"], {k: k in HANDOFF_KEYS for k in GRID}, set(HANDOFF_KEYS) | set(live_unflagged))
    report, _ = a1_report(dirs, cost_report=A1_COST_REPORT)
    am1 = report["amendment1"]
    assert am1["registered_h"] == "hstar"
    assert am1["b4_companions"]["P3"] == "amendment1.handoff_only_ni_hstar[B1a]"
    assert am1["b4_companions_flag"]["P3"] == "amendment1.handoff_only_ni[B1a]"
    assert am1["multiplicity_sensitivity_registered"] == "amendment1.multiplicity_sensitivity_hstar"
    hstar = {r["id"]: r for r in am1["handoff_only_ni_hstar"]}["B1a"]
    flag = {r["id"]: r for r in am1["handoff_only_ni"]}["B1a"]
    assert hstar["version"].startswith("registered") and flag["version"].startswith("companion")
    assert am1["multiplicity_sensitivity_hstar"]["version"].startswith("registered")
    # P3's B4 companion, beside it: h* B1a, −37.5 pp over 16 handoff pairs (test_am1_hstar_companions_...).
    comp = by_id(report)["P3"]["b4_companion"]
    assert comp["key"] == "amendment1.handoff_only_ni_hstar[B1a]" and comp["h"] == "hstar"
    assert (comp["handoff_only"]["diff_pp"], comp["handoff_only"]["n_handoff"]) == (-37.5, 16)
    assert comp["flag_key"] == "amendment1.handoff_only_ni[B1a]"
    s3 = next(r for r in report["supporting_contrasts"] if r["id"] == "S3")
    assert s3["b4_companion"]["handoff_only"]["diff_pp"] == 12.5  # S6 tailored h*: (0 x 8 + 0.25 x 8) / 16
    assert "(h*, registered, Amendment 3) B1a: fails, -37.50 pp over 16 handoff pairs" in report[
        "verdict_sentences"]["P3"]


def _asks(arm_root: Path, keys: list, forced_too: bool = False) -> None:
    """Live-answered executor asks: an intervention from the planner with forced False, in the last attempt."""
    for i, (task_id, seed) in enumerate(keys):
        events = [{"event_type": "run_start", "actor": "system", "payload": {}},
                  {"event_type": "intervention", "actor": "planner", "payload": {"forced": False}},
                  {"event_type": "intervention", "actor": "planner", "payload": {"forced": False}}][: 2 + (i == 0)]
        if forced_too:
            events.append({"event_type": "intervention", "actor": "planner", "payload": {"forced": True}})
        (arm_root / "sys" / str(seed) / task_id / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_r2_b4_live_asks_are_counted_and_a_bound_of_1pp_is_in_the_sentence(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    keys = [("sc0_1", 1), ("sc1_2", 2), ("sc2_3", 1), ("sc3_1", 2)]
    _asks(dirs["prefix_m11"], keys, forced_too=True)
    # An ask in an EARLIER attempt of sft_plan's sc0_1 does not count; the last attempt made none.
    (dirs["sft_plan"] / "sys" / "1" / "sc0_1" / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in [
        {"event_type": "run_start", "payload": {}},
        {"event_type": "intervention", "actor": "planner", "payload": {"forced": False}},
        {"event_type": "run_start", "payload": {}}]), encoding="utf-8")
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    asks = report["executor_asks"]
    m11 = asks["per_arm"]["prefix_m11"]
    # 4 episodes, 5 answered calls (the first episode asked twice); the forced interventions are not asks.
    assert (m11["n_episodes_with_answered_ask"], m11["n_answered_ask_calls"], m11["bound_pp"]) == (4, 5, 16.67)
    assert asks["per_arm"]["sft_plan"]["n_episodes_with_answered_ask"] == 0
    assert asks["per_arm"]["sft_plan"]["n_episodes_without_event_log"] == 23
    assert asks["n_answered_ask_calls_total"] == 5 and asks["registered_total"]["hosted_calls"] == "<= 15,627"
    assert asks["per_contrast"]["P1"] == {"bound_pp": {"advise_k1_fullctx": 0.0, "prefix_m11": 16.67},
                                          "max_bound_pp": 16.67, "bound_reaches_1pp": True}
    assert "P6" not in asks["per_contrast"]  # no replaying arm
    assert "live-answered executor asks bound the arm means at advise_k1_fullctx 0.00 pp, prefix_m11 16.67 pp" \
        in report["verdict_sentences"]["P1"]
    assert "asks" not in report["verdict_sentences"]["P5"]  # sft_plan's bound is 0
    assert rc == 0 and report["verdicts"]["P1"] == "supported"  # no verdict changes


def test_r2_b5_content_descriptives_for_arms_9_to_12(tmp_path: Path):
    dirs = write_a1_matrix(tmp_path)
    advice = "Try this:\n```python\nprint(1)\n```\nthen check."  # 44 characters, one fenced block
    ev = [{"event_type": "run_start", "actor": "system", "payload": {}},
          {"event_type": "intervention", "actor": "planner", "payload": {"correction": advice, "forced": True}},
          {"event_type": "action", "actor": "executor", "payload": {"kind": "CODE", "code": "print(1)"}},
          {"event_type": "intervention", "actor": "planner", "payload": {"correction": "look again", "forced": True}},
          {"event_type": "action", "actor": "executor", "payload": {"kind": "CODE", "code": "x = 2"}}]
    (dirs["advise_k10_fullctx"] / "sys" / "1" / "sc0_1" / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
    shown = "```python\nprint(2)\n```"
    ev = [{"event_type": "run_start", "actor": "system", "payload": {}},
          {"event_type": "intervention", "actor": "planner",
           "payload": {"correction": shown, "source": "shown_action", "shown_kind": "CODE", "forced": True}},
          {"event_type": "action", "actor": "executor", "payload": {"kind": "CODE", "code": "print(2)"}}]
    (dirs["show_k10"] / "sys" / "2" / "sc1_1" / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
    c = a1_report(dirs, cost_report=A1_COST_REPORT)[0]["content_descriptives"]
    assert c["status"] == "ok" and set(c["arms"]) == set(j10.A1_R2_CONTENT_ARMS)
    adv = c["arms"]["advise_k10_fullctx"]
    assert (adv["n_interventions"], adv["n_fenced_code"], adv["share_fenced_code"]) == (2, 1, 0.5)
    assert adv["median_chars"] == (44 + 10) / 2 and adv["copy_rate"] == 0.5  # the python block was copied
    assert adv["n_episodes_without_events"] == 23
    show = c["arms"]["show_k10"]
    assert (show["n_interventions"], show["share_fenced_code"], show["copy_rate"]) == (1, 1.0, 1.0)
    assert show["copy"] == {"definition": "copy_rate_show", "n_shown": 1, "n_copied": 1}
    assert c["arms"]["takeover_k10"]["copy_rate"] is None
    assert c["arms"]["advise_k10_neutral"]["n_interventions"] == 0


def test_r2_b6_pairwise_limit_rates_and_p3_limit_excluded(tmp_path: Path):
    lim = HANDOFF_KEYS[:6]  # arm 3 hits its call cap on 6 keys and scores 0.25 there
    dirs = write_a1_matrix(tmp_path)
    dirs["planner_alone_cap81"] = write_a1_arm(tmp_path / "x", "planner_alone_cap81",
                                               {k: 0.25 if k in lim else 0.75 for k in GRID},
                                               error_types={k: "limit" for k in lim})
    report, rc = a1_report(dirs, cost_report=A1_COST_REPORT, pairwise=True)
    assert rc == 0, report["headline"]
    pw = report["pairwise_contrasts"]
    assert pw["n_pairs_of_arms"] == 78 == len(pw["rows"])  # 13 arms, 13 x 12 / 2
    rows = {(r["left"], r["right"]): r for r in pw["rows"]}
    p1 = rows[("advise_k1_fullctx", "prefix_m11")]
    assert (p1["registered_row"], p1["goal_pass"]["scenario"]["diff_pp"]) == ("P1", -25.0)
    assert p1["holm_p_adjusted_at_registered_threshold"] == by_id(report)["P1"]["holm"]["p_adjusted"]
    # No registered row names arms 1 and 1b: later arm − earlier, exploratory, 0.375 − 0.25.
    x = rows[("executor_alone_bplus", "executor_alone")]
    assert x["label"] == "exploratory (A1 §7 item 2): unadjusted" and x["registered_row"] is None
    assert (x["goal_pass"]["scenario"]["diff_pp"], x["goal_pass"]["task"]["ci95_pp"]) == (12.5, [12.5, 12.5])
    assert x["goal_pass"]["p_value_two_sided_at_0"] == 0.0 and x["status"] == "ok"
    # Limit rates beside the arm mean and the contrast (Amendment 1 §D1): 6 / 24 for arm 3.
    assert report["arms"]["planner_alone_cap81"]["limit_rate"] == 0.25
    assert by_id(report)["P3"]["limit_rates"] == {"prefix_m11": 0.0, "planner_alone_cap81": 0.25}
    assert rows[("prefix_m11", "planner_alone_cap81")]["limit_rates"]["planner_alone_cap81"] == 0.25
    # P3 over all pairs: 0.75 − (18 x 0.75 + 6 x 0.25) / 24 = +12.5 pp. Limit-excluded: the 6 pairs go, +0 pp.
    assert by_id(report)["P3"]["contrast"]["scenario"]["diff_pp"] == 12.5
    le = report["p3_limit_excluded"]
    assert (le["n_reference_dropped_limit"], le["goal_pass"]["n_pairs"], le["goal_pass"]["scenario"]["diff_pp"]) == (
        6, 18, 0.0)
    assert le["reading_at_minus_7"] == "holds" and le["decision_bearing"] is False
    assert "selects on the reference arm's own failures" in le["caveat"]
    # Not computed unless asked (the tests' default): the registered read and main compute it.
    assert a1_report(dirs, cost_report=A1_COST_REPORT)[0]["pairwise_contrasts"]["status"] == "not_computed"


def test_r2_b7_j9_negative_and_the_provenance_statement(tmp_path: Path, monkeypatch):
    lines = (REPO_ROOT / j10.A1_PREREG).read_text(encoding="utf-8").splitlines()
    assert "(scored AUROC 0.3867–0.5082)" in lines[54] and "0.0347" in lines[55]
    dirs = _registered_matrix(tmp_path, monkeypatch)
    report, rc = registered_report(dirs, cost_report=A1_COST_REPORT)
    assert rc == 0, report["headline"]
    assert report["j9_claim_f1"]["auroc_range"] == [0.3867, 0.5082] and report["j9_claim_f1"]["dev_only"] is True
    prov = report["provenance_statement"]
    assert prov["per_arm"]["takeover_k10"] == {"planner_model_requested": {"gpt-5.6-luna": 24},
                                               "planner_cli_version": {"None": 24}}
    assert "served a call is not observable" in prov["statement"] and "gpt-5.6-luna (" in prov["statement"]
    # The registered read computes the pairwise rows.
    assert report["pairwise_contrasts"]["n_pairs_of_arms"] == 78


def test_r2_b8_the_json_citations_point_at_the_prereg_text():
    lines = (REPO_ROOT / j10.A1_PREREG).read_text(encoding="utf-8").splitlines()
    preds = {p["id"]: p for p in j10.A1_PREDICTIONS}
    assert "result [A1:358-359]." in preds["P2"]["notes"]
    assert "uninterpretable as a channel result" in lines[357] and "budget-confounded" in lines[358]
    assert preds["P3"]["dev_reference"]["key"].endswith("−4.75 [−11.75, +1.16], A1:367-368)")
    assert "−4.75 pp, [−11.75, +1.16]" in lines[367]
    assert preds["P4"]["dev_reference"]["key"].endswith("A1 r2 quotes it stored, A1:391-392)")
    assert "−2.82 pp, [−7.16, +1.55]" in lines[390]


def test_r2_every_report_carries_status_split_and_verdicts(tmp_path: Path, capsys):
    """The seam scripts/analysis/j11_report.py --j10-report reads: whatever the status, a top-level `status`, `split`
    and `verdicts` keyed by the P rows; under NOT_RUN every verdict is "not_run" and no contrast is printed."""
    p_ids = {f"P{i}" for i in range(1, 7)}
    dirs = write_a1_matrix(tmp_path)
    ok, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, ok["status"], ok["split"], set(ok["verdicts"])) == (0, "COMPLETE", "dev", p_ids)
    (dirs["takeover_k10"] / "sys" / "1" / "sc2_2" / "result.json").unlink()  # arm 10 incomplete: §9
    not_run, rc = a1_report(dirs, cost_report=A1_COST_REPORT)
    assert (rc, not_run["status"], not_run["split"]) == (1, "NOT_RUN", "dev")
    assert not_run["verdicts"] == {p: "not_run" for p in p_ids}
    assert not_run["protocol"] == "A1" and not_run["not_the_j10_result"] is True
    assert not any(k in json.dumps(not_run) for k in ("diff_pp", "ci95", "p_value"))
    assert "predictions" not in not_run and "supporting_contrasts" not in not_run
    refused, rc = a1_report(dirs, split="test_challenge", confirm_heldout_test_split=True)
    assert (rc, refused["status"], refused["split"]) == (2, "REFUSED", "test_challenge")
    assert refused["verdicts"] == {p: "refused" for p in p_ids}
    rc = j10.main(["--split", "dev", "--seeds", "1,x", "--arm", f"prefix_m11={tmp_path}"])
    out = json.loads(capsys.readouterr().out)
    assert (rc, out["status"], out["split"], set(out["verdicts"])) == (2, "REFUSED", "dev", p_ids)
