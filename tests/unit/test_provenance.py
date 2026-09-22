"""Tests for the run provenance block (X16).

The failure mode these guard against is not a crash but a *confident wrong answer*: a
manifest that says `split: dev` for a test episode, or reports a clean SHA when git could
not be reached, is worse than a manifest with no provenance at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sidekick.provenance import (
    codex_cli_version,
    config_provenance,
    git_provenance,
    planner_provenance,
    run_provenance,
)


# --- what the config said --------------------------------------------------------------


def test_config_provenance_records_the_adapter_from_the_executor_block() -> None:
    """lora_name lives on `executor`, not `policy_defaults`."""
    got = config_provenance({"executor": {"lora_name": "sft_b_plus", "model": "x"}}, "configs/c.yaml")

    assert got["lora_name"] == "sft_b_plus"
    assert got["executor_model"] == "x"
    assert got["config_path"] == "configs/c.yaml"


def test_config_provenance_records_the_replayed_source_campaign() -> None:
    cfg = {"handoff": {"source_campaign": "/scratch/x/results/src_20260923", "m": 11}}

    got = config_provenance(cfg, None)

    assert got["handoff_source_campaign"] == "/scratch/x/results/src_20260923"
    assert got["handoff_m"] == 11


def test_packet_source_is_used_when_there_is_no_handoff_source() -> None:
    got = config_provenance({"planner": {"packet_source": "/scratch/x/results/p_20260923"}}, None)

    assert got["handoff_source_campaign"] == "/scratch/x/results/p_20260923"


def test_an_empty_config_yields_nulls_not_an_exception() -> None:
    got = config_provenance(None, None)

    assert got["lora_name"] is None
    assert got["config_campaign_id"] is None


# --- the campaign id override ----------------------------------------------------------


def test_campaign_id_override_is_recorded_when_the_cli_wins() -> None:
    """Ten published campaigns ran under an id their config does not declare."""
    got = run_provenance(
        cfg={"campaign_id": "arm_20260922"},
        config_path="configs/arm.yaml",
        split="dev",
        resolved_campaign_id="arm_20260923",
    )

    assert got["config_campaign_id"] == "arm_20260922"
    assert got["campaign_id_overridden"] is True


def test_no_override_is_recorded_when_the_config_id_was_used() -> None:
    got = run_provenance(
        cfg={"campaign_id": "arm_20260923"},
        config_path=None,
        split="dev",
        resolved_campaign_id="arm_20260923",
    )

    assert got["campaign_id_overridden"] is False


def test_a_config_with_no_declared_id_is_not_reported_as_overridden() -> None:
    """Absence of a declared id is not the same as the CLI having overridden one."""
    got = run_provenance(cfg={}, config_path=None, split="dev", resolved_campaign_id="x_20260924")

    assert got["campaign_id_overridden"] is False


# --- split -------------------------------------------------------------------------------


def test_split_is_stamped_verbatim() -> None:
    """`--split` is CLI-only, so this is the only record that an episode is dev or test."""
    assert run_provenance(cfg={}, config_path=None, split="test_normal")["split"] == "test_normal"
    assert run_provenance(cfg={}, config_path=None, split="dev")["split"] == "dev"


def test_split_is_never_inferred_from_the_config() -> None:
    """A `split:` key in a config is inert; reading it would invent a false record."""
    got = run_provenance(cfg={"split": "test_normal"}, config_path=None, split="dev")

    assert got["split"] == "dev"


# --- git ---------------------------------------------------------------------------------


def test_git_provenance_reports_sha_branch_and_dirty_for_a_real_repo(tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "r"
    repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, check=True, env={**env, "PATH": "/usr/bin:/bin"})
    run("init", "-q")
    (repo / "f.txt").write_text("x", encoding="utf-8")
    run("add", "f.txt")
    run("commit", "-qm", "c")

    got = git_provenance(str(repo))

    assert got["git_sha"] is not None and len(got["git_sha"]) == 40
    assert got["git_dirty"] is False

    (repo / "f.txt").write_text("y", encoding="utf-8")
    git_provenance.cache_clear()
    assert git_provenance(str(repo))["git_dirty"] is True


def test_a_directory_outside_any_repo_yields_nulls_not_a_crash(tmp_path: Path) -> None:
    """A campaign must never fail because provenance could not be collected."""
    git_provenance.cache_clear()

    got = git_provenance(str(tmp_path))

    assert got["git_sha"] is None
    # None means "could not tell", which must not be confused with clean.
    assert got["git_dirty"] is None


def test_unknown_dirty_is_not_reported_as_clean(tmp_path: Path) -> None:
    git_provenance.cache_clear()
    got = git_provenance(str(tmp_path))
    assert got["git_dirty"] is not False


def test_git_provenance_is_cached_so_a_campaign_does_not_reshell_per_episode() -> None:
    git_provenance.cache_clear()
    hint = str(Path(__file__).resolve().parent)

    git_provenance(hint)
    before = git_provenance.cache_info().hits
    git_provenance(hint)

    assert git_provenance.cache_info().hits == before + 1


# --- the block as written --------------------------------------------------------------


def test_the_block_is_json_serialisable() -> None:
    """It goes straight into manifest.json; a stray Path would abort every episode."""
    block = run_provenance(
        cfg={"handoff": {"source_campaign": Path("/scratch/x")}, "executor": {"lora_name": "a"}},
        config_path=Path("configs/c.yaml"),
        split="dev",
        resolved_campaign_id="c_20260924",
    )

    json.dumps(block)  # must not raise
    assert isinstance(block["config_path"], str)
    assert isinstance(block["handoff_source_campaign"], str)


# --- the planner (A5, 2026-09-23) --------------------------------------------------------


def _fake_cli(tmp_path: Path, text: str, rc: int = 0) -> str:
    """A stand-in `codex` that prints a version line, so no test touches the real CLI."""
    script = tmp_path / "codex"
    script.write_text(f"#!/bin/sh\necho '{text}'\nexit {rc}\n")
    script.chmod(0o755)
    return str(script)


def test_a_codex_planner_records_the_cli_version_it_will_invoke(tmp_path: Path) -> None:
    codex_cli_version.cache_clear()
    cfg = {"planner": {"type": "codex", "model": "gpt-5.6-luna", "binary": _fake_cli(tmp_path, "codex-cli 9.9.9")}}

    got = planner_provenance(cfg)

    assert got["planner_type"] == "codex"
    assert got["planner_model_requested"] == "gpt-5.6-luna"
    assert got["planner_cli_version"] == "codex-cli 9.9.9"


def test_a_failing_cli_is_recorded_as_unknown_not_as_a_version(tmp_path: Path) -> None:
    codex_cli_version.cache_clear()
    cfg = {"planner": {"type": "codex", "binary": _fake_cli(tmp_path, "boom", rc=3)}}

    assert planner_provenance(cfg)["planner_cli_version"] is None


def test_a_missing_cli_does_not_abort_the_episode(tmp_path: Path) -> None:
    codex_cli_version.cache_clear()
    cfg = {"planner": {"type": "codex", "binary": str(tmp_path / "no_such_codex")}}

    assert planner_provenance(cfg)["planner_cli_version"] is None


def test_a_local_planner_never_shells_out_for_a_codex_version(tmp_path: Path) -> None:
    codex_cli_version.cache_clear()
    cfg = {"planner": {"type": "vllm", "model": "Qwen/Qwen3-8B", "binary": _fake_cli(tmp_path, "x")}}

    got = planner_provenance(cfg)

    assert got["planner_cli_version"] is None
    assert codex_cli_version.cache_info().misses == 0


def test_the_b2_arm_fields_are_stamped_with_their_defaults() -> None:
    """correct_prompt and advice_from_act are what separate the four B2 arms."""
    assert planner_provenance({})["correct_prompt"] == "correction"
    assert planner_provenance({})["advice_from_act"] is None

    got = planner_provenance({
        "planner": {"type": "mock", "correct_prompt": "neutral"},
        "policy_defaults": {"advice_from_act": True},
    })

    assert got["correct_prompt"] == "neutral"
    assert got["advice_from_act"] is True


def test_run_provenance_carries_the_planner_block() -> None:
    block = run_provenance(cfg={"planner": {"type": "mock"}}, config_path=None, split="dev")

    assert block["planner_type"] == "mock"
    assert "planner_cli_version" in block
