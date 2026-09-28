"""Tests for SIDEKICK_ROOT-based lazy default resolution. No file system use outside tmp_path."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from sidekick.training.sft_data import (
    SidekickRootError,
    default_adapter_manifest,
    default_correction_campaign,
    default_teacher_jsonl,
    sidekick_root,
)


def test_unset_env_raises(monkeypatch):
    monkeypatch.delenv("SIDEKICK_ROOT", raising=False)
    with pytest.raises(SidekickRootError, match="SIDEKICK_ROOT is not set"):
        sidekick_root()
    with pytest.raises(SidekickRootError, match="SIDEKICK_ROOT is not set"):
        default_teacher_jsonl()
    with pytest.raises(SidekickRootError, match="SIDEKICK_ROOT is not set"):
        default_adapter_manifest()
    with pytest.raises(SidekickRootError, match="SIDEKICK_ROOT is not set"):
        default_correction_campaign()
    from sidekick.training import handoff_sft

    with pytest.raises(SidekickRootError, match="SIDEKICK_ROOT is not set"):
        handoff_sft.default_source()


def test_empty_env_raises(monkeypatch):
    monkeypatch.setenv("SIDEKICK_ROOT", "")
    with pytest.raises(SidekickRootError, match="SIDEKICK_ROOT is not set"):
        sidekick_root()


def test_set_env_resolves_original_paths(monkeypatch):
    monkeypatch.setenv("SIDEKICK_ROOT", "/scratch/n12194778/sidekick")
    assert str(default_teacher_jsonl()) == (
        "/scratch/n12194778/sidekick/artifacts/sft/sft_b_s123_p075.jsonl"
    )
    assert str(default_adapter_manifest()) == (
        "/scratch/n12194778/sidekick/artifacts/adapters/"
        "sft_b_s123_granite8b/manifest.json"
    )
    assert str(default_correction_campaign()) == (
        "/scratch/n12194778/sidekick/results/hj4_correction_train_20260917"
    )
    from sidekick.training import handoff_sft

    assert str(handoff_sft.default_source()) == (
        "/scratch/n12194778/sidekick/results/hj2b_planner_train_20260916"
    )


def test_set_env_to_tmp_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SIDEKICK_ROOT", str(tmp_path))
    assert default_teacher_jsonl() == tmp_path / "artifacts/sft/sft_b_s123_p075.jsonl"


def test_import_works_without_sidekick_root():
    env = {k: v for k, v in os.environ.items() if k not in ("SIDEKICK_ROOT", "APPWORLD_ROOT")}
    src = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sidekick.environments.appworld_env, sidekick.training.sft_data, "
            "sidekick.training.matched_sft, sidekick.training.handoff_sft",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr


def test_handoff_main_without_sidekick_root_raises(tmp_path, monkeypatch):
    from sidekick.training import handoff_sft

    monkeypatch.delenv("SIDEKICK_ROOT", raising=False)
    out = tmp_path / "o.jsonl"
    with pytest.raises(SidekickRootError):
        handoff_sft.main(["--out", str(out)])
    assert not out.exists()


def test_build_sft_b_plus_without_sidekick_root_raises(tmp_path, monkeypatch):
    from sidekick.training import matched_sft

    monkeypatch.delenv("SIDEKICK_ROOT", raising=False)
    with pytest.raises(SidekickRootError):
        matched_sft.build_sft_b_plus(tmp_path / "c", ["x"], tmp_path / "o.jsonl")
