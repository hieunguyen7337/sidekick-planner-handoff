"""CLI serving config for the state probe: chat_template_kwargs, stop, schema 3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from sidekick.environments.mock_env import MockEnv  # noqa: E402
from sidekick.protocols.schemas import Event  # noqa: E402
import state_probe as sp  # noqa: E402


REQUIRED = [
    "--model",
    "ibm-granite/granite-4.2-8b",
    "--base-url",
    "http://127.0.0.1:8000",
    "--out",
    "probe.json",
]


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": "COMPLETE"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


class _FakeClient:
    def __init__(self) -> None:
        self.payload: dict | None = None

    def post(self, url: str, json: dict):
        self.payload = json
        return _FakeResponse()

    def close(self) -> None:
        return None


class StubProbeEnv(MockEnv):
    def __init__(self, experiment_name: str = "", api_docs_prompt: str = "stub_api() -> str"):
        super().__init__()
        self.experiment_name = experiment_name
        self._stub_api_docs_prompt = api_docs_prompt

    @property
    def instruction(self) -> str:
        return "Use the available AppWorld API to complete this task."

    @property
    def api_docs_prompt(self) -> str:
        return self._stub_api_docs_prompt


@pytest.fixture(autouse=True)
def stub_appworld(monkeypatch):
    monkeypatch.setattr(sp, "AppWorldEnv", StubProbeEnv)


class StubExecutor:
    def __init__(self, model: str = "stub") -> None:
        self.model = model
        self.lora_name = None
        self.chat_template_kwargs = {"enable_thinking": False}
        self.stop = ["</py>", "</python>"]
        self.calls = 0

    def complete(self, messages, **kw):
        self.calls += 1
        return "```python\npass\n```", None


def _event(
    run_id: str,
    task_id: str,
    step: int,
    event_type: str,
    payload: dict | None = None,
) -> Event:
    return Event(
        run_id=run_id,
        task_id=task_id,
        system="planner_alone",
        seed=1,
        step=step,
        ts="2026-09-16T00:00:00+00:00",
        actor="planner" if event_type == "action" else "system",
        event_type=event_type,
        payload=payload or {},
    )


def _write_campaign(tmp_path: Path, n_pairs: int = 2) -> Path:
    root = tmp_path / "campaign"
    run_dir = root / "planner_alone" / "1" / "task-1"
    run_dir.mkdir(parents=True)
    events = [_event("run-1", "task-1", 0, "run_start")]
    for step in range(1, n_pairs + 1):
        events.append(
            _event(
                "run-1",
                "task-1",
                step,
                "action",
                {"kind": "CODE", "code": "pass", "raw_output": "pass"},
            )
        )
        events.append(_event("run-1", "task-1", step, "observation", {"text": "ok"}))
    (run_dir / "events.jsonl").write_text(
        "".join(event.model_dump_json() + "\n" for event in events)
    )
    (run_dir / "result.json").write_text(json.dumps({"success": True}))
    return root


def test_chat_template_kwargs_reach_executor_payload():
    args = sp.build_parser().parse_args(
        REQUIRED + ["--chat-template-kwargs", '{"enable_thinking": false}']
    )
    client = _FakeClient()
    executor = sp.executor_from_args(args, http_client=client)
    try:
        executor.complete([{"role": "user", "content": "go"}])
    finally:
        executor.close()
    assert executor.chat_template_kwargs == {"enable_thinking": False}
    assert client.payload is not None
    assert client.payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_stop_given_twice_is_a_two_element_list():
    args = sp.build_parser().parse_args(
        REQUIRED + ["--stop", "</py>", "--stop", "</python>"]
    )
    client = _FakeClient()
    executor = sp.executor_from_args(args, http_client=client)
    try:
        executor.complete([{"role": "user", "content": "go"}])
    finally:
        executor.close()
    assert executor.stop == ["</py>", "</python>"]
    assert client.payload is not None
    assert client.payload["stop"] == ["</py>", "</python>"]


def test_omitting_kwargs_and_stop_leaves_executor_none():
    args = sp.build_parser().parse_args(REQUIRED)
    client = _FakeClient()
    executor = sp.executor_from_args(args, http_client=client)
    try:
        assert executor.chat_template_kwargs is None
        assert executor.stop is None
        executor.complete([{"role": "user", "content": "go"}])
    finally:
        executor.close()
    assert client.payload is not None
    assert "chat_template_kwargs" not in client.payload
    assert "stop" not in client.payload


def test_report_schema_version_is_3(tmp_path):
    campaign = _write_campaign(tmp_path)
    out = tmp_path / "probe.json"
    report = sp.run_probe(
        str(campaign),
        "planner_alone",
        StubExecutor("granite"),
        0,
        0,
        out_path=out,
        max_points=1,
        seed=0,
    )
    assert report["schema_version"] == 3
    assert sp.PROBE_SCHEMA_VERSION == 3
    assert report["chat_template_kwargs"] == {"enable_thinking": False}
    assert report["stop"] == ["</py>", "</python>"]
    on_disk = json.loads(out.read_text())
    assert on_disk["schema_version"] == 3
    assert on_disk["chat_template_kwargs"] == {"enable_thinking": False}
    assert on_disk["stop"] == ["</py>", "</python>"]


def test_malformed_chat_template_kwargs_fails_loudly(capsys):
    parser = sp.build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(REQUIRED + ["--chat-template-kwargs", "{not-json"])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "chat-template-kwargs" in err
    assert "JSON" in err
    with pytest.raises(SystemExit):
        parser.parse_args(REQUIRED + ["--chat-template-kwargs", '["not", "an", "object"]'])
    err2 = capsys.readouterr().err
    assert "JSON object" in err2
