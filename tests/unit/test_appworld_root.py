"""Tests for AppWorldEnv data-root resolution. AppWorld is NOT required."""

from __future__ import annotations

import os

import pytest

from sidekick.environments.appworld_env import (
    DEFAULT_APPWORLD_ROOT,
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


def test_default_used_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.delenv("APPWORLD_ROOT", raising=False)
    fake_default = _make_root(tmp_path)
    monkeypatch.setattr(
        "sidekick.environments.appworld_env.DEFAULT_APPWORLD_ROOT", fake_default
    )
    env = AppWorldEnv()
    assert env.root == fake_default


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


def test_default_constant_points_at_installed_data():
    assert DEFAULT_APPWORLD_ROOT == "/scratch/n12194778/sidekick/appworld"
