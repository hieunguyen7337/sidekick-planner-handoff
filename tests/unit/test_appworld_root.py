"""Tests for AppWorldEnv data-root resolution. AppWorld is NOT required."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sidekick.environments.appworld_env import (
    AppWorldEnv,
    AppWorldRootError,
)


def _make_root(tmp_path):
    (tmp_path / "data" / "tasks").mkdir(parents=True)
    return str(tmp_path)


def test_explicit_root_wins_over_env(tmp_path, monkeypatch):
    env_root = _make_root(tmp_path / "env_root")
    arg_root = _make_root(tmp_path / "arg_root")
    monkeypatch.setenv("APPWORLD_ROOT", env_root)
    env = AppWorldEnv(root=arg_root)
    assert env.root == arg_root


def test_env_var_wins_over_default(tmp_path, monkeypatch):
    env_root = _make_root(tmp_path / "env_root")
    monkeypatch.setenv("APPWORLD_ROOT", env_root)
    env = AppWorldEnv()
    assert env.root == env_root


def test_unset_env_raises_clear_error(monkeypatch):
    monkeypatch.delenv("APPWORLD_ROOT", raising=False)
    with pytest.raises(AppWorldRootError, match="APPWORLD_ROOT is not set"):
        AppWorldEnv()


def test_empty_env_raises_clear_error(monkeypatch):
    monkeypatch.setenv("APPWORLD_ROOT", "")
    with pytest.raises(AppWorldRootError, match="APPWORLD_ROOT is not set"):
        AppWorldEnv()


def test_no_hardcoded_default_root():
    import sidekick.environments.appworld_env as mod

    assert not hasattr(mod, "DEFAULT_APPWORLD_ROOT")
    assert "n12194778" not in Path(mod.__file__).read_text(encoding="utf-8")


def test_missing_tasks_dir_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("APPWORLD_ROOT", raising=False)
    bad = str(tmp_path / "not_a_root")
    (tmp_path / "not_a_root").mkdir()
    with pytest.raises(AppWorldRootError):
        AppWorldEnv(root=bad)


def test_cwd_is_never_used(tmp_path, monkeypatch):
    monkeypatch.delenv("APPWORLD_ROOT", raising=False)
    cwd_root = _make_root(tmp_path / "cwd_root")
    monkeypatch.chdir(cwd_root)
    env = AppWorldEnv(root=_make_root(tmp_path / "real_root"))
    assert env.root != os.getcwd()


def test_env_var_set_before_reset(tmp_path, monkeypatch):
    root = _make_root(tmp_path / "r")
    env = AppWorldEnv(root=root)
    assert os.environ["APPWORLD_ROOT"] == root
    assert env.manifest_fields() == {
        "appworld_root": root,
        "experiment_name": "sidekick",
    }
