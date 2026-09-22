"""An unknown env kind must refuse, not run on the mock (A5, 2026-09-23).

`make_env` used to return MockEnv for any kind it did not recognise, so a misspelt `env:`
- or a second environment whose adapter is not wired in yet - would run a whole campaign on
the mock and report believable numbers. Both entry points now refuse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sidekick.environments.mock_env import MockEnv
from sidekick.runner import ENV_KINDS, make_env, run_campaign


def test_mock_still_builds_the_mock() -> None:
    assert isinstance(make_env("mock", "x", {}), MockEnv)


def test_make_env_refuses_an_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown env kind 'appwrld'"):
        make_env("appwrld", "x", {})


def test_run_campaign_refuses_before_writing_anything(tmp_path: Path) -> None:
    out = tmp_path / "results"

    with pytest.raises(ValueError, match="unknown env kind 'bfcl'"):
        run_campaign(
            system="planner_alone",
            split="dev",
            tasks=1,
            seeds=[1],
            out=out,
            config={"env": "bfcl"},
            workers=1,
            campaign_id="c_refuse",
        )

    assert not (out / "c_refuse").exists()


def test_the_known_kinds_are_the_ones_make_env_builds() -> None:
    assert set(ENV_KINDS) == {"appworld", "mock"}
