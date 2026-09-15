from __future__ import annotations

import inspect
import json
from pathlib import Path

from sidekick.agents.executor import VLLMExecutor
from sidekick.environments.appworld_env import AppWorldEnv
from sidekick.runner import run_campaign
from sidekick.trajectories.eventlog import EventLog


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": "COMPLETE"}}],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 2,
                "prompt_tokens_details": {"cached_tokens": 3},
            },
        }


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict):
        self.calls.append((url, json))
        return _FakeResponse()

    def close(self) -> None:
        return None


def test_vllm_maps_usage_and_gpu_seconds() -> None:
    client = _FakeClient()
    ex = VLLMExecutor(
        model="Qwen/Qwen3-8B",
        base_url="http://127.0.0.1:8000/v1",
        lora_name="sft_plan",
        gpu_fraction=0.5,
        http_client=client,
    )
    text, usage = ex.complete([{"role": "user", "content": "go"}])
    assert text == "COMPLETE"
    assert usage.provider == "vllm"
    assert usage.model == "sft_plan"
    assert usage.input_tokens == 11
    assert usage.output_tokens == 2
    assert usage.cached_input_tokens == 3
    assert usage.raw["gpu_seconds_formula"] == "latency_s * gpu_fraction"
    assert abs(usage.gpu_seconds - usage.latency_s * 0.5) < 1e-9
    assert client.calls
    url, payload = client.calls[0]
    assert url.endswith("/v1/chat/completions")
    assert payload["model"] == "sft_plan"


def test_appworld_imported_only_inside_reset() -> None:
    src = inspect.getsource(AppWorldEnv.reset)
    assert "from appworld import AppWorld" in src
    module_src = Path(inspect.getsourcefile(AppWorldEnv)).read_text(encoding="utf-8")
    # Module body must not import appworld at import time (only inside reset).
    assert "from appworld import AppWorld" not in module_src.split("def reset")[0]
    assert "observation" in (AppWorldEnv.__doc__ or "").lower()
    assert "weakens replay" in (AppWorldEnv.snapshot_hash.__doc__ or "").lower()


def test_runner_writes_results_and_is_resumable(tmp_path: Path, prices_path: Path) -> None:
    out = tmp_path / "out"
    first = run_campaign(
        system="prompt_only",
        split="dev",
        tasks=1,
        seeds=[1],
        out=out,
        config={"prices": str(prices_path), "env": "mock"},
        workers=1,
        campaign_id="camp1",
    )
    assert first["n_finished"] == 1
    assert first["n_skipped"] == 0
    combined = Path(first["combined"])
    assert combined.is_file()
    lines = [ln for ln in combined.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["success"] is True
    events = out / "camp1" / "prompt_only" / "1" / "copy_hello" / "events.jsonl"
    assert events.is_file()
    assert list(EventLog.read(events))

    second = run_campaign(
        system="prompt_only",
        split="dev",
        tasks=1,
        seeds=[1],
        out=out,
        config={"prices": str(prices_path), "env": "mock"},
        workers=1,
        campaign_id="camp1",
    )
    assert second["n_skipped"] == 1
    assert second["n_jobs"] == 0


def test_runner_all_eight_systems(tmp_path: Path, prices_path: Path) -> None:
    from sidekick.systems import SYSTEM_NAMES

    out = tmp_path / "out"
    for name in SYSTEM_NAMES:
        summary = run_campaign(
            system=name,
            split="dev",
            tasks=1,
            seeds=[1],
            out=out,
            config={"prices": str(prices_path), "env": "mock", "oracle_steps": [1], "fixed_k": 5},
            workers=1,
            campaign_id="all8",
        )
        assert summary["n_finished"] == 1, name
        row = summary["results"][0]
        assert row["success"] is True, (name, row.get("error_type"))
