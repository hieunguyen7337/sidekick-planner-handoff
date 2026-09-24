"""scripts/pbs/bfcl_arm.pbs: refusals and the jq tally, through its self-test seams. No GPU, no qsub."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "bfcl_arm.pbs"
CFG = REPO / "configs" / "bfcl_executor_alone_zs.yaml"


def _run(tmp: Path, **env: str) -> subprocess.CompletedProcess:
    full = dict(os.environ)
    full.update({"BFCL_SELFTEST": "1", "BFCL_REPO": str(REPO), "BFCL_OUT": str(tmp / "out"), "BFCL_LOGDIR": str(tmp / "logs")})
    full.update(env)
    return subprocess.run(["bash", str(PBS)], env=full, capture_output=True, text=True, timeout=120)


def test_script_parses() -> None:
    assert subprocess.run(["bash", "-n", str(PBS)], capture_output=True).returncode == 0


def test_config_matches_the_j10_floor_receiver() -> None:
    import yaml

    ours = yaml.safe_load(CFG.read_text())
    j10 = yaml.safe_load((REPO / "configs" / "j10_executor_alone.yaml").read_text())
    assert ours["env"] == "bfcl" and ours["campaign_id"] == "bfcl_executor_alone_zs_dev_20260924"
    assert ours["executor"] == j10["executor"] and ours["limits"] == j10["limits"]
    assert "split" not in ours and ours["planner"] == {"type": "mock"}


def test_preflight_accepts_the_registered_config(tmp_path: Path) -> None:
    proc = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "selftest preflight ok" in proc.stdout
    assert "target=100 (50 tasks x 2 seeds)" in proc.stdout


@pytest.mark.parametrize(
    "env, message",
    [
        ({"SPLIT": "test"}, "SPLIT=test: this arm runs on the BFCL dev split only"),
        ({"CID": "bfcl_executor_alone_zs_test_x"}, "does not say _dev_"),
    ],
)
def test_preflight_refusals(tmp_path: Path, env: dict, message: str) -> None:
    proc = _run(tmp_path, **env)
    assert proc.returncode == 2 and message in proc.stdout


@pytest.mark.parametrize(
    "edit, message",
    [
        ({"executor": {"lora_name": "sft_b_plus"}}, "this arm is zero-shot"),
        ({"planner": {"type": "codex"}}, "must make zero hosted calls"),
        ({"env": "appworld"}, "config env is appworld, not bfcl"),
    ],
)
def test_config_refusals(tmp_path: Path, edit: dict, message: str) -> None:
    import yaml

    data = yaml.safe_load(CFG.read_text())
    for key, value in edit.items():
        if isinstance(value, dict):
            data[key] = {**data[key], **value}
        else:
            data[key] = value
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(data))
    proc = _run(tmp_path, CFG=str(cfg))
    assert proc.returncode == 2 and message in proc.stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH")
def test_tally_counts_and_error_types(tmp_path: Path) -> None:
    cid = "bfcl_selftest_dev_x"
    rows = [
        ("multi_turn_base_1", {"error_type": None, "success": True, "tgc": 1.0, "goal_pass_rate": 1.0}),
        ("multi_turn_base_2", {"error_type": "parse_error", "success": False, "tgc": 0.0, "goal_pass_rate": 0.5}),
        ("multi_turn_base_3", {"error_type": "crash", "success": False, "tgc": None, "goal_pass_rate": None}),
    ]
    for task, row in rows:
        d = tmp_path / "out" / cid / "executor_alone" / "1" / task
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"seed": 1, "task_id": task, **row}))
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", CID=cid, TASKS="3", SEEDS="1")
    # Hand count: 3 files, 1 crash, so 2 non-crashed of a target of 3 -> incomplete (3).
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "result_files=3 non_crashed=2 crashed=1 target=3" in proc.stdout
    # tgc (1 + 0 + null->0) / 3; goal_pass_rate (1 + 0.5 + null->0) / 3 = 0.5. jq versions print
    # 1/3 with 16 or 17 digits, so only the stable prefix is checked.
    assert "n=3 success=1 tgc_mean=0.333" in proc.stdout
    assert "goal_pass_rate_mean=0.5 crashed=1" in proc.stdout
    for line in ("1\tcrash", "1\tnone", "1\tparse_error"):
        assert line in proc.stdout
