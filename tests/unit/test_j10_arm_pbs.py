"""scripts/pbs/j10_arm.pbs refusals and tally, via its J10_SELFTEST seam.

The self-test runs every refusal check and then exits before a lock, a vLLM server,
a purge or a runner. Nothing under /scratch/n12194778/sidekick/results is written:
J10_OUT / J10_LOGDIR point into tmp_path, and a stub `codex` replaces the real one.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "j10_arm.pbs"
FROZEN_LINE = "**Status**: **FROZEN** 2026-09-24, commit abc1234."


def _stub_dir(tmp_path: Path, version: str = "codex-cli 9.9.9") -> Path:
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    codex = stub / "codex"
    codex.write_text(f"#!/bin/bash\necho '{version}'\n", encoding="utf-8")
    codex.chmod(0o755)
    return stub


def _prereg(tmp_path: Path, status_line: str) -> Path:
    path = tmp_path / "prereg.md"
    path.write_text(f"# A1\n\n{status_line}\n\nbody\n", encoding="utf-8")
    return path


def run_pbs(tmp_path: Path, **env_extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "DRYRUN", "SYSTEM", "EXPECTED_CODEX_VERSION",
                "J10_CONFIRM", "J10_PREREG", "J10_SELFTEST_STAGE", "PBS_JOBID"):
        env.pop(key, None)
    env.update(
        J10_SELFTEST="1",
        J10_STUB_DIR=str(_stub_dir(tmp_path)),
        J10_OUT=str(tmp_path / "out"),
        J10_LOGDIR=str(tmp_path / "logs"),
        PY=sys.executable,
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    env.update(env_extra)
    return subprocess.run(["timeout", "120", "bash", str(PBS)], cwd=str(REPO), env=env,
                          text=True, capture_output=True)


def _out(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout + proc.stderr


def _variant(tmp_path: Path, name: str, replace: tuple[str, str] | None = None,
             append: str = "") -> Path:
    text = (REPO / "configs" / name).read_text(encoding="utf-8")
    if replace:
        assert replace[0] in text
        text = text.replace(replace[0], replace[1])
    dest = tmp_path / "cfg" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text + append, encoding="utf-8")
    return dest


def test_bash_syntax():
    assert subprocess.run(["bash", "-n", str(PBS)]).returncode == 0


def test_select_line_pins_h100():
    head = PBS.read_text(encoding="utf-8").splitlines()[:6]
    assert any(line.startswith("#PBS -l select=") and "gpu_id=H100" in line for line in head)


def test_test_challenge_is_always_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", SPLIT="test_challenge",
                   J10_CONFIRM="A1_FROZEN", J10_PREREG=str(_prereg(tmp_path, FROZEN_LINE)))
    assert proc.returncode == 2, _out(proc)
    assert "test_challenge" in _out(proc)


def test_the_draft_status_line_is_refused_although_it_contains_frozen(tmp_path: Path):
    # A1's DRAFT line (docs/prereg_j10_amendment_20260924.md:3 on 2026-09-23) reads
    # "... Becomes FROZEN on commit." -- a bare substring test would pass it.
    line = "**Status**: **DRAFT pending user review.** Becomes FROZEN on commit. Amends, and does not edit,"
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                   J10_CONFIRM="A1_FROZEN", J10_PREREG=str(_prereg(tmp_path, line)))
    assert proc.returncode == 2, _out(proc)
    assert "not FROZEN" in _out(proc)


@pytest.mark.parametrize("line", [
    "**Status**: FROZEN, superseding the DRAFT of 2026-09-23.",
    "**Status**: **DRAFT pending user review.** Becomes FROZEN on commit.",
])
def test_status_line_must_begin_frozen_and_not_mention_draft(tmp_path: Path, line: str):
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                   J10_CONFIRM="A1_FROZEN", J10_PREREG=str(_prereg(tmp_path, line)))
    assert proc.returncode == 2, _out(proc)


def test_frozen_prereg_still_needs_the_confirmation_token(tmp_path: Path):
    prereg = str(_prereg(tmp_path, FROZEN_LINE))
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                   J10_PREREG=prereg, J10_CONFIRM="yes")
    assert proc.returncode == 2 and "J10_CONFIRM=A1_FROZEN" in _out(proc)
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                   J10_PREREG=prereg, J10_CONFIRM="A1_FROZEN")
    assert proc.returncode == 0, _out(proc)
    text = _out(proc)
    assert "selftest: preflight passed system=fixed_k cid=j10_advise_k1_fullctx_20260924 split=test_normal target=336" in text
    assert "--expect-planner --expect-model gpt-5.6-luna" in text
    assert "codex --version: codex-cli 9.9.9" in text
    assert "planner model from config: gpt-5.6-luna" in text


def test_test_normal_refuses_a_partial_or_renamed_read(tmp_path: Path):
    common = dict(CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                  J10_PREREG=str(_prereg(tmp_path, FROZEN_LINE)), J10_CONFIRM="A1_FROZEN")
    assert run_pbs(tmp_path, TASKS="10", **common).returncode == 2
    assert run_pbs(tmp_path, SEEDS="1,2,3", **common).returncode == 2
    assert run_pbs(tmp_path, CID="j10_other", **common).returncode == 2


@pytest.mark.parametrize("expected,rc", [("9.9.9", 0), ("codex-cli 9.9.9", 0), ("0.1.0", 2)])
def test_expected_codex_version(tmp_path: Path, expected: str, rc: int):
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", DRYRUN="1",
                   EXPECTED_CODEX_VERSION=expected)
    assert proc.returncode == rc, _out(proc)
    if rc:
        assert "expected '0.1.0'" in _out(proc)


def test_planner_model_must_be_exactly_luna(tmp_path: Path):
    cfg = _variant(tmp_path, "j10_advise_k1_fullctx.yaml",
                   ("model: gpt-5.6-luna", "model: gpt-5.6-sol"))
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2, _out(proc)
    assert "registered planner is exactly gpt-5.6-luna" in _out(proc)


def test_hosted_arm_with_a_mock_planner_is_refused(tmp_path: Path):
    cfg = _variant(tmp_path, "j10_sft_plan.yaml", ("type: codex", "type: mock"))
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2 and "silently runs MockPlanner" in _out(proc)


def test_config_split_key_and_system_mismatch_are_refused(tmp_path: Path):
    cfg = _variant(tmp_path, "j10_executor_alone.yaml", append="\nsplit: test_normal\n")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2 and "split: key" in _out(proc)
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", DRYRUN="1", SYSTEM="fixed_k")
    assert proc.returncode == 2 and "disagrees with the registered system" in _out(proc)


def test_dev_run_into_the_registered_campaign_id_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", SPLIT="dev")
    assert proc.returncode == 2 and "mix dev episodes into the test tree" in _out(proc)
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", DRYRUN="1")
    assert proc.returncode == 0, _out(proc)
    line = next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)
    assert "cid=j10_executor_alone_20260924_dryrun split=dev target=114" in line
    assert line.endswith("gate=--gate")  # a planner-free arm is gated on ZERO live calls


def _write_results(root: Path, rows: list[tuple[str, int, str | None]], system: str) -> None:
    for task, seed, err in rows:
        ep = root / system / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "result.json").write_text(json.dumps(
            {"task_id": task, "seed": seed, "error_type": err}) + "\n", encoding="utf-8")


def test_dryrun_prefix_arm_replays_the_dryrun_planner_and_requires_it_complete(tmp_path: Path):
    src = tmp_path / "out" / "j10_planner_alone_cap81_20260924"
    real = "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924"
    text = (REPO / "configs" / "j10_prefix_m11.yaml").read_text(encoding="utf-8").replace(real, str(src))
    cfg = tmp_path / "cfg" / "j10_prefix_m11.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(text, encoding="utf-8")
    dry = Path(str(src) + "_dryrun")
    # Incomplete source: 3 of 4 episodes, and the registered (non-dry-run) tree is ignored.
    _write_results(src, [(f"t{i}", s, None) for i in range(2) for s in (1, 2)], "planner_alone")
    _write_results(dry, [("t0", 1, None), ("t0", 2, None), ("t1", 1, None)], "planner_alone")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 2, _out(proc)
    assert "arm 3 must complete before arms 4-7 start" in _out(proc)
    _write_results(dry, [("t1", 2, None)], "planner_alone")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 0, _out(proc)
    derived = list((tmp_path / "logs" / "j10_dryrun_cfg").glob("j10_prefix_m11_20260924_dryrun.*.yaml"))
    assert derived
    for path in derived:
        body = path.read_text(encoding="utf-8")
        assert f"source_campaign: {dry}" in body and f"packet_source: {dry}" in body
        assert "campaign_id: j10_prefix_m11_20260924_dryrun" in body
    assert "system=prefix_handoff" in _out(proc)


def test_dev_prefix_run_without_dryrun_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j10_prefix_m9.yaml", SPLIT="dev", CID="j10_prefix_m9_devcheck")
    assert proc.returncode == 2 and "use DRYRUN=1" in _out(proc)


def test_tally_exits_nonzero_while_crashes_remain_and_zero_when_complete(tmp_path: Path):
    root = tmp_path / "out" / "j10_executor_alone_20260924_dryrun"
    _write_results(root, [("t0", 1, None), ("t0", 2, "limit"), ("t1", 1, None), ("t1", 2, "crash")],
                   "executor_alone")
    env = dict(CFG="configs/j10_executor_alone.yaml", DRYRUN="1", TASKS="2",
               J10_SELFTEST_STAGE="tally")
    proc = run_pbs(tmp_path, **env)
    text = _out(proc)
    assert proc.returncode == 3, text
    assert "target=4 non_crashed=3 crashed=1" in text
    assert "limit" in text and "crash" in text and "resubmit" in text
    _write_results(root, [("t1", 2, None)], "executor_alone")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "COMPLETE: 4/4 non-crashed, 0 crashed" in _out(proc)
