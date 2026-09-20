"""SIDEKICK_VLLM_BASE_URL wins over frozen yaml executor.base_url."""
from __future__ import annotations

import json
from pathlib import Path

from sidekick.runner import (
    DEFAULT_PRICES,
    make_executor,
    resolve_executor_base_url,
    run_single,
)

YAML_8000 = "http://127.0.0.1:8000"
ENV_URL = "http://127.0.0.1:27123"
DEFAULT_URL = "http://127.0.0.1:8000"


def test_env_overrides_yaml_8000(monkeypatch) -> None:
    monkeypatch.setenv("SIDEKICK_VLLM_BASE_URL", ENV_URL)
    ex = make_executor(
        {
            "executor": {
                "type": "vllm",
                "model": "test-model",
                "base_url": YAML_8000,
            }
        }
    )
    assert ex.base_url == ENV_URL


def test_yaml_wins_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("SIDEKICK_VLLM_BASE_URL", raising=False)
    yaml_url = "http://127.0.0.1:9999"
    ex = make_executor(
        {
            "executor": {
                "type": "vllm",
                "model": "test-model",
                "base_url": yaml_url,
            }
        }
    )
    assert ex.base_url == yaml_url


def test_default_when_neither_env_nor_yaml(monkeypatch) -> None:
    monkeypatch.delenv("SIDEKICK_VLLM_BASE_URL", raising=False)
    ex = make_executor({"executor": {"type": "vllm", "model": "test-model"}})
    assert ex.base_url == DEFAULT_URL


def test_empty_env_does_not_override_yaml(monkeypatch) -> None:
    monkeypatch.setenv("SIDEKICK_VLLM_BASE_URL", "   ")
    yaml_url = "http://127.0.0.1:9999"
    assert resolve_executor_base_url({"base_url": yaml_url}) == yaml_url


def test_run_single_records_effective_base_url(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SIDEKICK_VLLM_BASE_URL", ENV_URL)
    prices = DEFAULT_PRICES if DEFAULT_PRICES.is_file() else tmp_path / "prices.yaml"
    if not prices.is_file():
        prices.write_text(
            "schedule_date: '2026-09-15'\n"
            "source: test\n"
            "models:\n"
            "  gpt-5.6-luna: {input: 0.20, cached_input: 0.02, output: 1.20}\n"
            "local:\n"
            "  usd_per_gpu_hour: 2.50\n",
            encoding="utf-8",
        )
    job = {
        "out": str(tmp_path),
        "run_id": "cid/executor_alone/1/copy_hello",
        "system": "executor_alone",
        "task_id": "copy_hello",
        "seed": 1,
        "config": {
            "executor": {"type": "mock", "base_url": YAML_8000},
        },
        "prices_path": str(prices),
        "env_kind": "mock",
        "campaign_id": "cid",
        "experiment_name": "cid/executor_alone/1/copy_hello",
    }
    run_single(job)
    manifest = json.loads(
        (tmp_path / job["run_id"] / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["executor_base_url"] == ENV_URL
