from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "setup"))

from verify_configs import validate_prompt_budget  # noqa: E402


def _errors(tmp_path: Path, cfg: dict) -> list[str]:
    return validate_prompt_budget(cfg, str(tmp_path / "config.yaml"))


def test_executor_prompt_budget_present_and_positive_passes(tmp_path):
    assert _errors(
        tmp_path,
        {"executor": {"type": "vllm", "max_prompt_tokens": 30720}},
    ) == []


def test_executor_prompt_budget_absent_fails_with_exact_key_path(tmp_path):
    errors = _errors(tmp_path, {"executor": {"type": "vllm"}})
    assert errors
    assert "executor.max_prompt_tokens" in errors[0]


def test_prompt_budget_under_limits_is_misplaced(tmp_path):
    errors = _errors(
        tmp_path,
        {"executor": {"type": "vllm"}, "limits": {"max_prompt_tokens": 30720}},
    )
    assert any("misplaced" in error and "limits.max_prompt_tokens" in error for error in errors)


def test_config_without_executor_passes(tmp_path):
    assert _errors(tmp_path, {"planner": {"type": "mock"}}) == []


def test_allowlisted_frozen_pilot_without_prompt_budget_passes(tmp_path):
    errors = validate_prompt_budget(
        {"executor": {"type": "vllm"}},
        "configs/pilot_exec_8b.yaml",
    )
    assert errors == []


def test_non_allowlisted_config_without_prompt_budget_fails(tmp_path):
    errors = validate_prompt_budget(
        {"executor": {"type": "vllm"}},
        "configs/new_config.yaml",
    )
    assert any("missing required key executor.max_prompt_tokens" in error for error in errors)


def test_allowlisted_frozen_pilot_with_misplaced_prompt_budget_fails(tmp_path):
    errors = validate_prompt_budget(
        {"executor": {"type": "vllm"}, "limits": {"max_prompt_tokens": 30720}},
        "configs/pilot_exec_8b.yaml",
    )
    assert any("misplaced" in error and "limits.max_prompt_tokens" in error for error in errors)
